from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.database import Base, migrate_market_observation_availability
from app.models.market_observation import MarketObservation
from app.models.market_observation_revision import MarketObservationRevision
from app.schemas.market_data import GovernmentSyncResult
from app.services.api_ingestion_service import ApiIngestionService
from app.services.market_service import MarketService


@pytest.fixture
def isolated_db():
    """An in-memory database dedicated to this test; never uses app SessionLocal."""
    isolated_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(isolated_engine)
    with Session(isolated_engine) as db:
        yield db
    isolated_engine.dispose()


def _csv(modal_price: int, extra_header: str = "", extra_value: str = "") -> str:
    suffix = f",{extra_header}" if extra_header else ""
    value_suffix = f",{extra_value}" if extra_header else ""
    return (
        "State,District,Market,Commodity,Variety,Arrival_Date,Min_Price,Max_Price,"
        f"Modal_Price,Arrivals_in_qtl{suffix}\n"
        f"State,Dist,Mandi,HistoryTest,Red,2026-01-02,90,110,{modal_price},12{value_suffix}\n"
    )


def _api_record(commodity="ApiReliabilityTest", day="2026-02-01", price="100"):
    return {
        "state": "State",
        "district": "District",
        "market": "ApiReliabilityMandi",
        "commodity": commodity,
        "variety": "Red",
        "arrival_date": day,
        "modal_price": price,
        "min_price": "90",
        "max_price": "110",
        "arrivals_in_qtl": "12",
    }


def _cleanup(db: Session, commodity: str) -> None:
    ids = [
        row[0]
        for row in db.query(MarketObservation.id)
        .filter(MarketObservation.commodity == commodity)
        .all()
    ]
    if ids:
        db.query(MarketObservationRevision).filter(
            MarketObservationRevision.observation_id.in_(ids)
        ).delete(synchronize_session=False)
    db.query(MarketObservation).filter(
        MarketObservation.commodity == commodity
    ).delete(synchronize_session=False)
    db.commit()


def _run_immediate(coroutine):
    """Run the mocked ingestion coroutine without opening a Windows event loop."""
    try:
        coroutine.send(None)
    except StopIteration as completed:
        return completed.value
    raise AssertionError("The mocked ingestion path unexpectedly suspended")


def test_observation_models_expose_separate_availability_and_revision_fields():
    assert "observation_date" in MarketObservation.__table__.c
    assert "first_ingested_at" in MarketObservation.__table__.c
    assert "source_available_at" in MarketObservation.__table__.c
    assert "availability_status" in MarketObservation.__table__.c
    assert "revision_number" in MarketObservationRevision.__table__.c
    assert "modal_price" in MarketObservationRevision.__table__.c
    assert "ingested_at" in MarketObservationRevision.__table__.c
    assert "source_available_at" in MarketObservationRevision.__table__.c


def test_availability_migration_is_additive_and_idempotent():
    isolated_engine = create_engine("sqlite:///:memory:")
    try:
        with isolated_engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE market_observations ("
                "id INTEGER PRIMARY KEY, modal_price FLOAT, retrieval_timestamp DATETIME, "
                "created_at DATETIME)"
            ))
            conn.execute(text(
                "INSERT INTO market_observations "
                "(id, modal_price, retrieval_timestamp, created_at) "
                "VALUES (1, 123.0, '2026-10-24 12:00:00', '2026-10-24 12:00:00')"
            ))

            migrate_market_observation_availability(conn)
            migrate_market_observation_availability(conn)

            row = conn.execute(text(
                "SELECT modal_price, retrieval_timestamp, first_ingested_at, "
                "source_available_at, availability_status "
                "FROM market_observations WHERE id = 1"
            )).one()
            assert row.modal_price == 123.0
            assert row.retrieval_timestamp == "2026-10-24 12:00:00"
            assert row.first_ingested_at is None
            assert row.source_available_at is None
            assert row.availability_status == "UNKNOWN"
    finally:
        isolated_engine.dispose()


def test_csv_import_keeps_initial_value_and_appends_changed_revision(isolated_db):
    db = isolated_db
    commodity = "HistoryTest"
    first = MarketService.import_csv_records(db, _csv(100))
    assert first.success and first.imported_count == 1
    observation = db.query(MarketObservation).filter_by(commodity=commodity).one()
    first_ingested_at = observation.first_ingested_at
    assert first_ingested_at is not None
    assert observation.source_available_at is None
    assert observation.availability_status == "INGESTION_TIME_ONLY"

    changed = MarketService.import_csv_records(db, _csv(105))
    assert changed.success and changed.imported_count == 1
    revisions = (
        db.query(MarketObservationRevision)
        .filter_by(observation_id=observation.id)
        .order_by(MarketObservationRevision.revision_number)
        .all()
    )
    assert [revision.revision_number for revision in revisions] == [1, 2]
    assert [revision.modal_price for revision in revisions] == [100.0, 105.0]
    assert all(revision.ingested_at is not None for revision in revisions)
    assert observation.modal_price == 105.0
    assert observation.first_ingested_at == first_ingested_at

    revisions[0].modal_price = 999.0
    with pytest.raises(ValueError, match="immutable"):
        db.flush()
    db.rollback()


def test_csv_can_record_explicit_timezone_aware_source_availability(isolated_db):
    result = MarketService.import_csv_records(
        isolated_db,
        _csv(101, "Source_Available_At", "2026-01-02T09:00:00+05:30"),
    )
    assert result.success and result.imported_count == 1
    observation = isolated_db.query(MarketObservation).filter_by(
        commodity="HistoryTest"
    ).one()
    assert observation.source_available_at.replace(tzinfo=timezone.utc) == datetime(
        2026, 1, 2, 3, 30, tzinfo=timezone.utc
    )
    assert observation.availability_status == "SOURCE_TIMESTAMP"


def test_csv_revision_preserves_legacy_value_as_availability_unknown(isolated_db):
    db = isolated_db
    commodity = "HistoryTest"
    legacy = MarketObservation(
        state="State",
        district="Dist",
        market="Mandi",
        commodity=commodity,
        variety="Red",
        observation_date=date(2026, 1, 2),
        modal_price=100.0,
        source="DEMO_SEED_DATA",
        retrieval_timestamp=datetime(2026, 1, 5, tzinfo=timezone.utc),
        availability_status="UNKNOWN",
    )
    db.add(legacy)
    db.commit()

    result = MarketService.import_csv_records(db, _csv(106))
    assert result.success and result.imported_count == 1
    revisions = (
        db.query(MarketObservationRevision)
        .filter_by(observation_id=legacy.id)
        .order_by(MarketObservationRevision.revision_number)
        .all()
    )
    assert [revision.modal_price for revision in revisions] == [100.0, 106.0]
    assert revisions[0].availability_status == "UNKNOWN"
    assert revisions[0].ingested_at is None
    assert revisions[1].availability_status == "INGESTION_TIME_ONLY"
    assert revisions[1].ingested_at is not None
    assert legacy.first_ingested_at is None


def test_api_import_appends_revisions_and_records_ingestion(isolated_db, monkeypatch):
    db = isolated_db
    commodity = "ApiHistoryTest"
    values = iter(((100, 10), (107, 10), (107, 12)))

    class FakeResponse:
        status_code = 200

        def __init__(self, price, arrivals):
            self.price = price
            self.arrivals = arrivals

        def json(self):
            return {"records": [{
                "state": "State",
                "district": "Dist",
                "market": "Mandi",
                "commodity": commodity,
                "variety": "Red",
                "arrival_date": "2026-01-02",
                "modal_price": str(self.price),
                "min_price": "90",
                "max_price": "110",
                "arrivals_in_qtl": str(self.arrivals),
            }]}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            return FakeResponse(*next(values))

    monkeypatch.setattr(
        "app.services.api_ingestion_service.httpx.AsyncClient", FakeAsyncClient
    )
    first_result = _run_immediate(
        ApiIngestionService.sync_from_datagov(db, api_key="test-key")
    )
    second_result = _run_immediate(
        ApiIngestionService.sync_from_datagov(db, api_key="test-key")
    )
    third_result = _run_immediate(
        ApiIngestionService.sync_from_datagov(db, api_key="test-key")
    )
    assert first_result["imported_count"] == 1
    assert second_result["updated_count"] == 1
    assert first_result["fetched_count"] == 1
    assert second_result["fetched_count"] == 1
    assert first_result["duplicate_count"] == 0
    assert second_result["duplicate_count"] == 0
    assert first_result["skipped_count"] == 0
    assert second_result["skipped_count"] == 0
    assert third_result["updated_count"] == 1
    assert GovernmentSyncResult.model_validate(first_result).fetched_count == 1
    assert GovernmentSyncResult.model_validate(second_result).updated_count == 1

    observation = db.query(MarketObservation).filter_by(commodity=commodity).one()
    revisions = (
        db.query(MarketObservationRevision)
        .filter_by(observation_id=observation.id)
        .order_by(MarketObservationRevision.revision_number)
        .all()
    )
    assert [revision.modal_price for revision in revisions] == [100.0, 107.0, 107.0]
    assert [revision.arrivals_in_qtl for revision in revisions] == [10.0, 10.0, 12.0]
    assert all(revision.availability_status == "INGESTION_TIME_ONLY" for revision in revisions)
    assert all(revision.ingested_at is not None for revision in revisions)
    assert observation.modal_price == 107.0
    assert observation.source_available_at is None
    assert observation.source == "OFFICIAL_GOV_API"


def test_api_sync_paginates_with_offsets_and_preserves_counts(isolated_db, monkeypatch):
    requests = []
    payloads = [
        {"total": 3, "records": [_api_record(day=f"2026-02-0{day}", price=str(100 + day))]}
        for day in (1, 2, 3)
    ]

    class FakeResponse:
        status_code = 200

        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params):
            requests.append((url, dict(params)))
            return FakeResponse(payloads[len(requests) - 1])

    monkeypatch.setattr("app.services.api_ingestion_service.httpx.AsyncClient", FakeAsyncClient)
    result = _run_immediate(ApiIngestionService.sync_from_datagov(
        isolated_db, api_key="mock-key", limit=1,
        commodity_filter="ApiReliabilityTest", state_filter="State",
    ))

    assert result["success"] is True
    assert result["fetched_count"] == 3
    assert result["total_available_count"] == 3
    assert result["imported_count"] == 3
    assert result["pagination_truncated"] is False
    assert [params["offset"] for _, params in requests] == [0, 1, 2]
    assert all(params["limit"] == 1 for _, params in requests)
    assert all(params["filters[commodity]"] == "ApiReliabilityTest" for _, params in requests)


def test_api_sync_pagination_is_bounded_and_reports_truncation(isolated_db, monkeypatch):
    requests = []

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"total": 10000, "records": [{"invalid": i} for i in range(500)]}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params):
            requests.append(dict(params))
            return FakeResponse()

    monkeypatch.setattr("app.services.api_ingestion_service.httpx.AsyncClient", FakeAsyncClient)
    result = _run_immediate(ApiIngestionService.sync_from_datagov(
        isolated_db, api_key="mock-key", limit=5000
    ))

    assert len(requests) == 5
    assert [params["offset"] for params in requests] == [0, 500, 1000, 1500, 2000]
    assert all(params["limit"] == 500 for params in requests)
    assert result["success"] is False
    assert result["status"] == "NO_VALID_RECORDS"
    assert result["fetched_count"] == 2500
    assert result["skipped_count"] == 2500
    assert result["total_available_count"] == 10000
    assert result["pagination_truncated"] is True


@pytest.mark.parametrize("payload", [[], {"records": {}}, {"records": [], "total": "not-a-count"}])
def test_api_sync_rejects_malformed_response_without_writes(isolated_db, monkeypatch, payload):
    class FakeResponse:
        status_code = 200

        def json(self):
            return payload

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("app.services.api_ingestion_service.httpx.AsyncClient", FakeAsyncClient)
    result = _run_immediate(ApiIngestionService.sync_from_datagov(isolated_db, api_key="mock-key"))
    assert result["success"] is False
    assert result["status"] == "MALFORMED_RESPONSE"
    assert result["imported_count"] == 0
    assert isolated_db.query(MarketObservation).count() == 0


def test_api_sync_counts_invalid_and_duplicate_rows_without_fabricating_success(isolated_db, monkeypatch):
    valid = _api_record()
    invalid_nonfinite = _api_record(day="2026-02-02", price="NaN")
    duplicate = dict(valid)
    rows = [valid, duplicate, invalid_nonfinite, {"state": "incomplete"}]

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"total": len(rows), "records": rows}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("app.services.api_ingestion_service.httpx.AsyncClient", FakeAsyncClient)
    result = _run_immediate(ApiIngestionService.sync_from_datagov(isolated_db, api_key="mock-key"))
    assert result["success"] is True
    assert result["status"] == "PARTIAL_RESULT"
    assert result["fetched_count"] == 4
    assert result["imported_count"] == 1
    assert result["duplicate_count"] == 1
    assert result["skipped_count"] == 2
    assert isolated_db.query(MarketObservation).count() == 1
