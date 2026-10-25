import logging
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# For SQLite, check_same_thread needs to be False for multithreaded FastAPI workers
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def migrate_market_observation_availability(conn) -> None:
    """Add availability fields without fabricating provenance for legacy rows."""
    from sqlalchemy import text

    columns = {
        row[1]
        for row in conn.execute(text("PRAGMA table_info(market_observations)"))
    }
    if not columns:
        return

    additions = (
        ("first_ingested_at", "DATETIME"),
        ("source_available_at", "DATETIME"),
        ("availability_status", "VARCHAR(32) NOT NULL DEFAULT 'UNKNOWN'"),
    )
    for name, definition in additions:
        if name not in columns:
            conn.execute(
                text(f"ALTER TABLE market_observations ADD COLUMN {name} {definition}")
            )
    conn.execute(
        text(
            "UPDATE market_observations SET availability_status = 'UNKNOWN' "
            "WHERE availability_status IS NULL OR TRIM(availability_status) = ''"
        )
    )


def migrate_prediction_evaluation_availability(conn) -> None:
    """Add mode provenance to persisted backtest pairs without relabeling old rows."""
    from sqlalchemy import text

    columns = {
        row[1]
        for row in conn.execute(text("PRAGMA table_info(prediction_evaluations)"))
    }
    if columns and "availability_mode" not in columns:
        conn.execute(
            text("ALTER TABLE prediction_evaluations ADD COLUMN availability_mode VARCHAR(32)")
        )


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session and safely closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables and run safe incremental migrations."""
    from sqlalchemy import text
    from app.models import (  # noqa: F401
        market_observation,
        market_observation_revision,
        forecast_record,
        crop_profile,
    )
    Base.metadata.create_all(bind=engine)

    # Safe incremental column additions for SQLite
    try:
        with engine.connect() as conn:
            columns = [row[1] for row in conn.execute(text("PRAGMA table_info(market_observations)"))]
            if "original_unit" not in columns:
                conn.execute(text("ALTER TABLE market_observations ADD COLUMN original_unit VARCHAR(50) DEFAULT 'Rs/Quintal'"))
                logger.info("Migrated: added 'original_unit' to market_observations.")
            if "retrieval_timestamp" not in columns:
                conn.execute(text("ALTER TABLE market_observations ADD COLUMN retrieval_timestamp DATETIME"))
                conn.execute(text("UPDATE market_observations SET retrieval_timestamp = created_at WHERE retrieval_timestamp IS NULL"))
                logger.info("Migrated: added 'retrieval_timestamp' to market_observations.")
            migrate_market_observation_availability(conn)
            migrate_prediction_evaluation_availability(conn)
            # Update legacy source label SEED_DATA to DEMO_SEED_DATA
            conn.execute(text("UPDATE market_observations SET source = 'DEMO_SEED_DATA' WHERE source = 'SEED_DATA'"))
            conn.commit()
    except Exception as e:
        logger.warning(f"Migration note: {e}")

    logger.info("Database tables initialized successfully.")
