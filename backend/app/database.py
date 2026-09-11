import time
from sqlalchemy import create_engine, inspect, text, event
from sqlalchemy.orm import sessionmaker, declarative_base

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
    """Record the start time on the connection's info dict (thread-local)."""
    conn.info.setdefault("_query_start_time", []).append(time.perf_counter())


@event.listens_for(engine, "after_cursor_execute")
def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Compare elapsed time; log as WARNING if it exceeds the threshold."""
    start_stack = conn.info.get("_query_start_time")
    if not start_stack:
        return
    elapsed_ms = (time.perf_counter() - start_stack.pop()) * 1000

    if elapsed_ms >= SLOW_QUERY_THRESHOLD_MS:
        # Truncate statement and params for readability — full versions may be
        # megabytes long for bulk inserts.
        truncated_sql = statement.strip().replace("\n", " ")[:300]
        truncated_params = str(parameters)[:200] if parameters else ""
        logger.warning(
            f"SLOW QUERY detected ({elapsed_ms:.1f} ms > {SLOW_QUERY_THRESHOLD_MS:.0f} ms threshold). "
            f"SQL: {truncated_sql!r}  |  Params: {truncated_params}"
        )


def ensure_database_schema_synced():
    """
    DEPRECATED: Runtime ALTER TABLE schema sync has been removed.

    All schema changes (tenant_id columns, bills.checksum, tenants.* columns,
    refresh_tokens.tenant_id) are now managed by Alembic migrations. Run:

        alembic upgrade head

    to bring the database up to date. See alembic/versions/0021_tenant_schema_hardening.py
    for the migration that covers the changes previously done inline here.

    This function is retained as a no-op to avoid breaking any call sites that
    invoke it on startup, but it performs no database operations.
    """
    pass


def get_db():
    """FastAPI dependency that yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


from sqlalchemy.orm import with_loader_criteria

@event.listens_for(SessionLocal, "do_orm_execute")
def _tenant_isolation_filter(orm_execute_state):
    """
    GLOBAL MULTI-TENANT FILTER (Row-Level Security Equivalent).
    Automatically appends `.filter(Model.tenant_id == current_tenant_id)`
    to EVERY SELECT query, ensuring a developer can NEVER accidentally leak data
    between shops by forgetting a filter clause.
    """
    if not orm_execute_state.is_select:
        return

    tenant_val = orm_execute_state.session.info.get("tenant_id")
    if tenant_val is not None:
        for mapper in Base.registry.mappers:
            # Apply to any model that has a tenant_id column
            if hasattr(mapper.class_, "tenant_id"):
                orm_execute_state.statement = orm_execute_state.statement.options(
                    with_loader_criteria(
                        mapper.class_,
                        lambda cls: cls.tenant_id == tenant_val,
                        include_aliases=True,
                        track_closure_variables=False,
                    )
                )

