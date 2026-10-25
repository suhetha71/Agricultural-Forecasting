"""Isolate pytest from the application SQLite database.

This module MUST set DATABASE_URL before importing app.database / app.main so
SQLAlchemy never binds SessionLocal to agricultural_forecasting.db during tests.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
PRODUCTION_DB_PATH = BACKEND_DIR / "agricultural_forecasting.db"

_TEST_DIR = Path(tempfile.mkdtemp(prefix="agri_forecast_isolated_tests_"))
TEST_DB_PATH = _TEST_DIR / "isolated_test.db"


def _copy_sqlite_file(source: Path, dest: Path) -> None:
    """Copy a SQLite main file and any sidecar journal/WAL files (read-only wrt source)."""
    shutil.copy2(source, dest)
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = Path(str(source) + suffix)
        if sidecar.exists():
            shutil.copy2(sidecar, Path(str(dest) + suffix))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


if PRODUCTION_DB_PATH.exists():
    _copy_sqlite_file(PRODUCTION_DB_PATH, TEST_DB_PATH)
else:
    TEST_DB_PATH.touch()

os.environ["DATABASE_URL"] = "sqlite:///" + TEST_DB_PATH.resolve().as_posix()

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.database import engine, init_db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Bind tests to the isolated file, initialize schema, and verify production is unchanged."""
    production_existed = PRODUCTION_DB_PATH.exists()
    hash_before = _sha256(PRODUCTION_DB_PATH) if production_existed else None
    size_before = PRODUCTION_DB_PATH.stat().st_size if production_existed else None

    engine_db = engine.url.database
    assert engine_db, "Test engine must have a SQLite file path"
    assert Path(engine_db).resolve() == TEST_DB_PATH.resolve()
    assert Path(engine_db).resolve() != PRODUCTION_DB_PATH.resolve()

    init_db()
    yield

    if production_existed:
        assert PRODUCTION_DB_PATH.stat().st_size == size_before
        assert _sha256(PRODUCTION_DB_PATH) == hash_before
