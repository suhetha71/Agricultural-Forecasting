"""Prove automated tests cannot modify the application SQLite database."""
from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import date
from pathlib import Path

from app.database import SessionLocal, engine
from app.models.market_observation import MarketObservation

BACKEND_DIR = Path(__file__).resolve().parents[1]
PRODUCTION_DB_PATH = BACKEND_DIR / "agricultural_forecasting.db"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_counts(db_path: Path) -> dict[str, int]:
    uri = "file:" + db_path.resolve().as_posix() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        rows = conn.execute(
            "SELECT source, COUNT(*) FROM market_observations GROUP BY source"
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM market_observations").fetchone()[0]
    finally:
        conn.close()
    counts = {source: count for source, count in rows}
    counts["__total__"] = total
    return counts


def test_engine_and_env_point_at_isolated_sqlite_file():
    engine_path = Path(engine.url.database).resolve()
    env_url = os.environ.get("DATABASE_URL", "").replace("\\", "/")
    production_posix = PRODUCTION_DB_PATH.resolve().as_posix()

    assert engine_path.exists()
    assert engine_path != PRODUCTION_DB_PATH.resolve()
    assert engine_path.name == "isolated_test.db"
    assert "isolated_test.db" in env_url
    assert production_posix not in env_url


def test_session_writes_do_not_change_production_database():
    assert PRODUCTION_DB_PATH.exists()
    hash_before = _sha256(PRODUCTION_DB_PATH)
    prod_before = _source_counts(PRODUCTION_DB_PATH)
    test_path = Path(engine.url.database).resolve()
    test_before = _source_counts(test_path)

    db = SessionLocal()
    try:
        db.add(
            MarketObservation(
                state="Isolation",
                district="Isolation",
                market="IsolationMandi",
                commodity="ISOLATION_PROBE_CROP",
                variety="Probe",
                observation_date=date(2099, 1, 1),
                modal_price=1.0,
                unit="INR/Quintal",
                source="ISOLATION_PROBE",
            )
        )
        db.commit()
        test_deleted = (
            db.query(MarketObservation)
            .filter(
                MarketObservation.commodity == "ISOLATION_PROBE_CROP",
                MarketObservation.source == "ISOLATION_PROBE",
            )
            .delete(synchronize_session=False)
        )
        db.commit()
        assert test_deleted == 1
    finally:
        db.close()

    hash_after = _sha256(PRODUCTION_DB_PATH)
    prod_after = _source_counts(PRODUCTION_DB_PATH)
    test_after = _source_counts(test_path)

    assert hash_after == hash_before
    assert prod_after == prod_before
    assert test_after.get("ISOLATION_PROBE", 0) == 0
    assert "ISOLATION_PROBE" not in prod_after
    assert test_after.get("USER_CSV_IMPORT", 0) == test_before.get("USER_CSV_IMPORT", 0)
    assert prod_after.get("USER_CSV_IMPORT", 0) == prod_before.get("USER_CSV_IMPORT", 0)


def test_deleting_user_csv_on_session_local_leaves_production_csv_rows():
    """Mirrors the dangerous ingestion test: delete USER_CSV_IMPORT via SessionLocal."""
    prod_before = _source_counts(PRODUCTION_DB_PATH)
    hash_before = _sha256(PRODUCTION_DB_PATH)
    test_path = Path(engine.url.database).resolve()
    assert prod_before.get("USER_CSV_IMPORT", 0) > 0

    db = SessionLocal()
    try:
        db.query(MarketObservation).filter(
            MarketObservation.source == "USER_CSV_IMPORT"
        ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()

    prod_after = _source_counts(PRODUCTION_DB_PATH)
    test_after = _source_counts(test_path)

    assert _sha256(PRODUCTION_DB_PATH) == hash_before
    assert prod_after == prod_before
    assert test_after.get("USER_CSV_IMPORT", 0) == 0
    assert prod_after.get("USER_CSV_IMPORT", 0) == prod_before.get("USER_CSV_IMPORT", 0)
