from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings
from app.core.logging import get_logger

logger = get_logger("database")

engine = create_engine(settings.database_url, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


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
    except Exception as e:
        logger.warning(f"Schema sync check warning: {e}")


def get_db():
    """FastAPI dependency that yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
