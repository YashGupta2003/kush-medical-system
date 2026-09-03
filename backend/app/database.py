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
    Self-healing schema migration helper.
    Ensures missing columns (such as `checksum` on `bills`) exist in MySQL without requiring manual SQL queries.
    """
    try:
        inspector = inspect(engine)
        if "bills" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("bills")]
            if "checksum" not in columns:
                logger.info("Adding missing 'checksum' column to 'bills' table...")
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE bills ADD COLUMN checksum VARCHAR(64) NULL;"))
                    conn.execute(text("CREATE INDEX ix_bills_checksum ON bills (checksum);"))
                logger.info("Successfully added 'checksum' column and index to 'bills' table.")

        if "tenants" in inspector.get_table_names():
            tenant_columns = [c["name"] for c in inspector.get_columns("tenants")]
            with engine.begin() as conn:
                if "slug" not in tenant_columns:
                    conn.execute(text("ALTER TABLE tenants ADD COLUMN slug VARCHAR(80) NULL;"))
                if "shop_name" not in tenant_columns:
                    conn.execute(text("ALTER TABLE tenants ADD COLUMN shop_name VARCHAR(150) NULL;"))
                if "owner_name" not in tenant_columns:
                    conn.execute(text("ALTER TABLE tenants ADD COLUMN owner_name VARCHAR(150) NULL;"))
                if "gstin" not in tenant_columns:
                    conn.execute(text("ALTER TABLE tenants ADD COLUMN gstin VARCHAR(20) NULL;"))
                if "city" not in tenant_columns:
                    conn.execute(text("ALTER TABLE tenants ADD COLUMN city VARCHAR(100) NULL;"))
                if "address" not in tenant_columns:
                    conn.execute(text("ALTER TABLE tenants ADD COLUMN address TEXT NULL;"))
                if "plan" not in tenant_columns:
                    conn.execute(text("ALTER TABLE tenants ADD COLUMN plan VARCHAR(50) DEFAULT 'free';"))
                if "is_active" not in tenant_columns:
                    conn.execute(text("ALTER TABLE tenants ADD COLUMN is_active BOOLEAN DEFAULT 1;"))
                if "email_verified" not in tenant_columns:
                    conn.execute(text("ALTER TABLE tenants ADD COLUMN email_verified BOOLEAN DEFAULT 0;"))
                if "email_verification_token" not in tenant_columns:
                    conn.execute(text("ALTER TABLE tenants ADD COLUMN email_verification_token VARCHAR(64) NULL;"))

        if "refresh_tokens" in inspector.get_table_names():
            rt_columns = [c["name"] for c in inspector.get_columns("refresh_tokens")]
            if "tenant_id" not in rt_columns:
                logger.info("Adding missing 'tenant_id' column to 'refresh_tokens' table...")
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE refresh_tokens ADD COLUMN tenant_id INT NULL;"))
                    try:
                        conn.execute(text("ALTER TABLE refresh_tokens ADD CONSTRAINT fk_refresh_tokens_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id);"))
                        conn.execute(text("CREATE INDEX ix_refresh_tokens_tenant_id ON refresh_tokens (tenant_id);"))
                    except Exception as ex:
                        logger.warning(f"Failed to add foreign key to refresh_tokens: {ex}")

        # Ensure ALL tables have tenant_id if missing, except tenants itself
        tables = inspector.get_table_names()
        with engine.begin() as conn:
            for table in tables:
                if table in ("tenants", "alembic_version"):
                    continue
                columns = [c["name"] for c in inspector.get_columns(table)]
                if "tenant_id" not in columns:
                    logger.info(f"Adding missing 'tenant_id' column to '{table}' table...")
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN tenant_id INT NULL;"))
                    try:
                        conn.execute(text(f"ALTER TABLE {table} ADD CONSTRAINT fk_{table}_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id);"))
                        conn.execute(text(f"CREATE INDEX ix_{table}_tenant_id ON {table} (tenant_id);"))
                    except Exception as ex:
                        logger.warning(f"Failed to add foreign key to {table}: {ex}")

    except Exception as e:
        logger.warning(f"Schema sync check warning: {e}")


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

