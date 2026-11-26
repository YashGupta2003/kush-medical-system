"""
Database engine, session lifecycle, and GLOBAL MULTI-TENANT ISOLATION.

Isolation contract
------------------
Every ORM operation that touches a table carrying a ``tenant_id`` column is
scoped to the tenant stored in ``session.info["tenant_id"]``:

* SELECT                 -> ``with_loader_criteria`` (covers joined loads/aliases)
* bulk UPDATE / DELETE   -> explicit ``WHERE <model>.tenant_id = :tenant``
* ORM INSERT (``session.add``) -> ``before_flush`` fills a missing ``tenant_id``
* bulk INSERT statements -> a warning is emitted (they must set tenant_id)

Two explicit, auditable escape hatches exist for the few genuinely global
operations (tenant registration, cross-tenant integrity scans, regional
sentinel aggregation):

* ``session.info["skip_tenant_filter"] = True`` (whole session), or
* ``statement.execution_options(skip_tenant_filter=True)`` (one statement), or
* ``with bypass_tenant_filter(db): ...`` (recommended, restores state).

A missing tenant context is *not* an error: Celery tasks legitimately run
unscoped. Use ``with tenant_context(db, tenant_id):`` to opt a global session
into a specific tenant (this both scopes reads and stamps writes).

``before_flush`` also refuses to silently reassign an existing row to another
tenant. Use ``bypass_tenant_filter`` explicitly when that is intentional.
"""
import time
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import and_, create_engine, event, inspect, or_, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import (
    declarative_base,
    sessionmaker,
    with_loader_criteria,
    Session as SASession,
)
from sqlalchemy.pool import NullPool

from app.config import settings
from app.core.logging import get_logger

logger = get_logger("database")

# ---------------------------------------------------------------------------
# Production-grade connection pool.
#
# pool_size=20      — keep 20 connections open and ready at all times.
#                     Sized for up to ~20 concurrent API workers on a single
#                     uvicorn/gunicorn instance; increase for multi-worker.
# max_overflow=40   — allow 40 extra connections during traffic bursts
#                     (total ceiling: 60). These are returned to the pool
#                     and closed once the burst subsides.
# pool_timeout=30   — raise after 30 s if no connection is available
#                     (instead of blocking indefinitely).
# pool_pre_ping=True — test each connection before lending it out; silently
#                     reconnects if MySQL closed a stale connection (e.g. after
#                     the 8-hour wait_timeout).
# pool_recycle=3600 — force-recycle connections after 1 hour to prevent
#                     the "MySQL server has gone away" error on long-lived
#                     workers.
# connect_args      — explicit connect timeout so a hard network failure does
#                     not freeze the process.
# ---------------------------------------------------------------------------
if settings.database_url.startswith("sqlite"):
    is_memory_sqlite = ":memory:" in settings.database_url
    sqlite_kwargs = {
        "connect_args": {"check_same_thread": False, "timeout": 15},
        "pool_pre_ping": True,
    }
    if not is_memory_sqlite:
        # Never cache open file handles to disk SQLite across Celery worker processes
        # (prevents stale unlinked inode reads after DB reset/restore and multi-process locks).
        sqlite_kwargs["poolclass"] = NullPool
    engine = create_engine(settings.database_url, **sqlite_kwargs)
    if not is_memory_sqlite:
        @event.listens_for(engine, "connect")
        def _configure_sqlite_wal(dbapi_conn, connection_record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.execute("PRAGMA busy_timeout=5000")
            cur.close()
else:
    engine = create_engine(
        settings.database_url,
        pool_size=20,
        max_overflow=40,
        pool_timeout=30,
        pool_pre_ping=True,
        pool_recycle=3600,
        connect_args={"connect_timeout": 10},
    )
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ---------------------------------------------------------------------------
# Slow-query profiler — logs any SQL statement that takes longer than
# SLOW_QUERY_THRESHOLD_MS to execute. Helps catch N+1 patterns and missing
# index scans before they reach production under real traffic.
#
# Uses SQLAlchemy's before/after_cursor_execute events rather than a
# per-request middleware so it works for both synchronous endpoint calls AND
# Celery background tasks that share the same engine.
# ---------------------------------------------------------------------------
SLOW_QUERY_THRESHOLD_MS: float = 200.0   # tune as needed


@event.listens_for(engine, "before_cursor_execute")
def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Record the start time on the connection's info dict."""
    conn.info.setdefault("_query_start_time", []).append(time.perf_counter())


@event.listens_for(engine, "after_cursor_execute")
def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Compare elapsed time; log as WARNING if it exceeds the threshold."""
    start_stack = conn.info.get("_query_start_time")
    if not start_stack:
        return
    elapsed_ms = (time.perf_counter() - start_stack.pop()) * 1000

    if elapsed_ms >= SLOW_QUERY_THRESHOLD_MS:
        # Log the statement but NEVER the parameter values. Bound parameters
        # routinely contain customer names, phone numbers and auth-adjacent
        # data, and this log file is retained on disk.
        truncated_sql = statement.strip().replace("\n", " ")[:300]
        logger.warning(
            f"SLOW QUERY detected ({elapsed_ms:.1f} ms > {SLOW_QUERY_THRESHOLD_MS:.0f} ms threshold). "
            f"SQL: {truncated_sql!r}"
        )


# ===========================================================================
# Multi-tenant isolation
# ===========================================================================

TENANT_CONTEXT_KEY = "tenant_id"
TENANT_SKIP_KEY = "skip_tenant_filter"
SKIP_EXECUTION_OPTION = "skip_tenant_filter"

# The curated drug-interaction / condition graph is reference data shared by
# every shop: those edge rows deliberately have tenant_id=NULL and must remain
# readable from a tenant-scoped session. All other NULL-tenant rows stay
# invisible — that is the whole point of the guard.
GLOBAL_GRAPH_EDGE_TYPES = ("INTERACTS_WITH", "TREATS")


class TenantIsolationError(RuntimeError):
    """Raised when code tries to move an existing row between tenants."""


def _tenant_criterion(tenant_val):
    # IMPORTANT: the tenant must be referenced as a real closure variable.
    # Putting it in a lambda default argument hides it from SQLAlchemy's
    # cache-key tracking, which caused all tenants after the first to reuse
    # the first tenant's compiled WHERE clause (a cross-tenant data leak).
    tenant = tenant_val
    return lambda cls: cls.tenant_id == tenant


def _graph_tenant_criterion(tenant_val):
    tenant = tenant_val
    global_types = GLOBAL_GRAPH_EDGE_TYPES
    return lambda cls: or_(
        cls.tenant_id == tenant,
        and_(cls.tenant_id.is_(None), cls.edge_type.in_(global_types)),
    )


def _isolation_skipped(state) -> bool:
    return bool(
        state.execution_options.get(SKIP_EXECUTION_OPTION)
        or state.session.info.get(TENANT_SKIP_KEY)
    )


def _tenant_isolation_filter(state) -> None:
    """`do_orm_execute` listener: scope every tenant-aware ORM statement."""
    if _isolation_skipped(state):
        return

    tenant_val = state.session.info.get(TENANT_CONTEXT_KEY)
    if tenant_val is None:
        # Deliberate: unscoped sessions are how Celery's cross-tenant scans and
        # the tenant-registration flow work. Call tenant_context() to opt in.
        return

    # ---- SELECT: with_loader_criteria also covers joined/aliased loads -----
    if state.is_select:
        for mapper in Base.registry.mappers:
            if not hasattr(mapper.class_, "tenant_id"):
                continue
            if mapper.class_.__name__ == "GraphEdge" and hasattr(mapper.class_, "edge_type"):
                criterion = _graph_tenant_criterion(tenant_val)
            else:
                criterion = _tenant_criterion(tenant_val)
            state.statement = state.statement.options(
                with_loader_criteria(
                    mapper.class_,
                    criterion,
                    include_aliases=True,
                    # The tenant value is a real closure variable above, so
                    # SQLAlchemy includes it in the statement cache key.
                    track_closure_variables=True,
                )
            )
        return

    # ---- Bulk ORM UPDATE / DELETE ------------------------------------------
    # with_loader_criteria does NOT apply to these statements; the target
    # mapper is available on the execute state, so add the predicate directly.
    if state.is_update or state.is_delete:
        mapper = state.bind_mapper
        if mapper is None:
            # Tables addressed via __table__ have no bind_mapper; fall back to
            # matching the statement's target table name.
            target_table = getattr(state.statement, "table", None)
            table_name = getattr(target_table, "name", None)
            mapper = next(
                (m for m in Base.registry.mappers
                 if m.class_.__tablename__ == table_name and hasattr(m.class_, "tenant_id")),
                None,
            )
        if mapper is not None and hasattr(mapper.class_, "tenant_id"):
            state.statement = state.statement.where(
                getattr(mapper.class_, "tenant_id") == tenant_val
            )
        return

    # ---- Bulk INSERT statements --------------------------------------------
    # ORM `session.add()` is handled by before_flush below. Core-style
    # `session.execute(insert(...))` bypasses mapper events, so warn rather
    # than silently creating an invisible (NULL-tenant) row.
    if state.is_insert:
        mapped = state.bind_mapper
        if mapped is not None and hasattr(mapped.class_, "tenant_id"):
            values = getattr(state.statement, "_values", None)
            has_tenant = values is not None and any(
                getattr(col, "key", None) == TENANT_CONTEXT_KEY for col in values
            )
            if not has_tenant:
                logger.warning(
                    "Bulk INSERT into %s without tenant_id under an active tenant "
                    "context %s — the row will be invisible. Set tenant_id explicitly.",
                    mapped.class_.__tablename__, tenant_val,
                )


def _propagate_tenant_on_flush(session: SASession, flush_context, instances) -> None:
    """`before_flush` listener: stamp new rows, forbid tenant reassignment."""
    if session.info.get(TENANT_SKIP_KEY):
        return
    tenant_val = session.info.get(TENANT_CONTEXT_KEY)
    if tenant_val is None:
        return

    for obj in session.new:
        if hasattr(obj, TENANT_CONTEXT_KEY) and getattr(obj, TENANT_CONTEXT_KEY) is None:
            # Curated drug-interaction/condition edges are global reference
            # data. They are created with tenant_id=None on purpose, and the
            # flush may happen after a temporary bypass has exited.
            if (
                type(obj).__name__ == "GraphEdge"
                and getattr(obj, "edge_type", None) in GLOBAL_GRAPH_EDGE_TYPES
            ):
                continue
            setattr(obj, TENANT_CONTEXT_KEY, tenant_val)

    for obj in session.dirty:
        if not hasattr(obj, TENANT_CONTEXT_KEY):
            continue
        state = inspect(obj)
        if not state.modified:
            continue
        history = state.attrs[TENANT_CONTEXT_KEY].history
        if history.added and history.deleted and history.added[0] != history.deleted[0]:
            raise TenantIsolationError(
                f"Refusing to move {type(obj).__name__}#{getattr(obj, 'id', '?')} "
                f"from tenant {history.deleted[0]} to {history.added[0]}. "
                f"Use `with bypass_tenant_filter(db):` if this is intentional."
            )


def install_tenant_isolation(session_factory):
    """Register the isolation listeners on any SQLAlchemy session factory.

    Exported so the test suite can install the *same* guard on its in-memory
    session factory instead of running with isolation silently disabled.
    """
    event.listen(session_factory, "do_orm_execute", _tenant_isolation_filter)
    event.listen(session_factory, "before_flush", _propagate_tenant_on_flush)
    return session_factory


install_tenant_isolation(SessionLocal)


def _evict_mismatched_identity_map(db: SASession, tenant_id: Optional[int]) -> None:
    """Drop cached rows that would be invisible under ``tenant_id``.

    ``Session.get()`` never emits SQL for an identity-map hit. Without this,
    switching tenants (or leaving a global bypass) could hand a caller a row
    loaded under the previous scope even though every SQL path is filtered.

    An expired tenant attribute may need a lazy database refresh. Callers keep
    the appropriate scope active while invoking this helper, and a failed
    transaction is handled by conservatively evicting the cached object.
    """
    if tenant_id is None:
        return
    for obj in list(db.identity_map.values()):
        state = inspect(obj)
        if TENANT_CONTEXT_KEY not in state.mapper.columns:
            continue
        # Never discard in-memory edits; correctness of the write is more
        # important than a read leak, and callers should flush first.
        if state.modified:
            continue
        try:
            obj_tenant = getattr(obj, TENANT_CONTEXT_KEY)
        except SQLAlchemyError:
            db.expunge(obj)
            continue
        if obj_tenant == tenant_id:
            continue
        db.expunge(obj)


@contextmanager
def tenant_context(db: SASession, tenant_id: Optional[int]) -> Iterator[SASession]:
    """Temporarily scope ``db`` to ``tenant_id`` (restores the prior context)."""
    previous = db.info.get(TENANT_CONTEXT_KEY)
    if tenant_id is not None and tenant_id != previous and not db.info.get(TENANT_SKIP_KEY):
        _evict_mismatched_identity_map(db, tenant_id)

    db.info[TENANT_CONTEXT_KEY] = tenant_id
    try:
        yield db
    finally:
        if previous is None:
            db.info.pop(TENANT_CONTEXT_KEY, None)
        else:
            db.info[TENANT_CONTEXT_KEY] = previous


@contextmanager
def bypass_tenant_filter(db: SASession) -> Iterator[SASession]:
    """Temporarily lift isolation for a documented, global operation."""
    previous_skip = db.info.get(TENANT_SKIP_KEY)
    previous_tenant = db.info.get(TENANT_CONTEXT_KEY)
    db.info[TENANT_SKIP_KEY] = True
    try:
        yield db
    finally:
        # Rows deliberately loaded from other tenants during the bypass must
        # not survive once the tenant scope is restored. Do this while the
        # bypass is still active so refreshing an expired attribute cannot be
        # filtered by the tenant guard.
        try:
            if not previous_skip and previous_tenant is not None:
                _evict_mismatched_identity_map(db, previous_tenant)
        finally:
            if previous_skip:
                db.info[TENANT_SKIP_KEY] = previous_skip
            else:
                db.info.pop(TENANT_SKIP_KEY, None)


def ensure_database_schema_synced():
    """
    DEPRECATED: Runtime ALTER TABLE schema sync has been removed.

    All schema changes (tenant_id columns, bills.checksum, tenants.* columns,
    refresh_tokens.tenant_id) are managed by Alembic migrations. Run:

        alembic upgrade head

    to bring the database up to date. See alembic/versions/0021_tenant_schema_hardening.py
    for the migration that covers the changes previously done inline here.

    Retained as a no-op to avoid breaking call sites.
    """
    pass


def get_db():
    """FastAPI dependency that yields a DB session and always closes it."""
    db = SessionLocal()
    # A session may be reused across requests in tests; never inherit a tenant
    # context from a previous request. Auth dependencies set it explicitly.
    db.info.pop(TENANT_CONTEXT_KEY, None)
    db.info.pop(TENANT_SKIP_KEY, None)
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
