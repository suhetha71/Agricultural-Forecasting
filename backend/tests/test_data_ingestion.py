import os
import inspect
import httpx
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.market_observation import MarketObservation
from app.services.market_service import MarketService
from app.api.market_data import sync_gov_api
from app.schemas.market_data import GovernmentSyncRequest, GovernmentSyncResult

client = TestClient(app)
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _run_immediate(coroutine):
    """Run an async handler whose mocked path completes without event-loop I/O."""
    try:
        coroutine.send(None)
    except StopIteration as completed:
        return completed.value
    raise AssertionError("The mocked API path unexpectedly suspended on external I/O")


def test_malformed_headers_rejection():
    """CSV with missing required headers must be rejected with informative error."""
    with open(os.path.join(FIXTURES_DIR, "malformed_headers.csv"), "r") as f:
        content = f.read()

    db = SessionLocal()
    try:
        res = MarketService.import_csv_records(db, content)
        assert res.success is False
        assert "missing required headers" in res.message.lower()
    finally:
        db.close()


def test_invalid_prices_handling():
    """Rows with non-numeric or negative prices must be skipped without aborting valid rows."""
    with open(os.path.join(FIXTURES_DIR, "invalid_prices.csv"), "r") as f:
        content = f.read()

    db = SessionLocal()
    try:
        db.query(MarketObservation).filter(MarketObservation.market == "TestMandiPrices").delete()
        db.commit()

        res = MarketService.import_csv_records(db, content, source_label="USER_CSV_IMPORT")
        assert res.success is True
        # 1 valid row (2400), 2 invalid rows ("INVALID_TEXT", -450)
        assert res.imported_count == 1
        assert res.skipped_count >= 2
    finally:
        db.close()


def test_invalid_dates_handling():
    """Rows with unparseable dates must be flagged in errors and skipped."""
    with open(os.path.join(FIXTURES_DIR, "invalid_dates.csv"), "r") as f:
        content = f.read()

    db = SessionLocal()
    try:
        db.query(MarketObservation).filter(MarketObservation.market == "TestMandiDates").delete()
        db.commit()

        res = MarketService.import_csv_records(db, content, source_label="USER_CSV_IMPORT")
        assert res.success is True
        assert res.imported_count == 1
        assert res.skipped_count >= 1
    finally:
        db.close()


def test_missing_optional_fields():
    """Rows lacking min_price, max_price, or arrivals must still import modal_price safely."""
    with open(os.path.join(FIXTURES_DIR, "missing_optional_fields.csv"), "r") as f:
        content = f.read()

    db = SessionLocal()
    try:
        db.query(MarketObservation).filter(MarketObservation.market == "TestMandiMissing").delete()
        db.commit()

        res = MarketService.import_csv_records(db, content, source_label="USER_CSV_IMPORT")
        assert res.success is True
        assert res.imported_count == 1
    finally:
        db.close()


def test_import_real_official_agmarknet_csv():
    """Test importing the optional local CSV when it is available."""
    data_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "data", "official_agmarknet_october_2026.csv")
    if not os.path.exists(data_path):
        pytest.skip(
            "Optional local CSV is absent; its provenance and redistribution rights are unconfirmed."
        )

    with open(data_path, "r", encoding="utf-8") as f:
        content = f.read()

    db = SessionLocal()
    try:
        db.query(MarketObservation).filter(MarketObservation.source == "USER_CSV_IMPORT").delete()
        db.commit()

        res = MarketService.import_csv_records(db, content, source_label="USER_CSV_IMPORT")
        assert res.success is True
        assert res.imported_count > 0

        # Verify duplicate detection on immediate re-import
        res_dup = MarketService.import_csv_records(db, content, source_label="USER_CSV_IMPORT")
        assert res_dup.success is True
        assert res_dup.imported_count == 0
        assert res_dup.duplicate_count == res.imported_count
    finally:
        db.close()


def test_data_source_stats_endpoint():
    """Verify endpoint distinguishes official API, CSV imports, and demonstration seed records."""
    response = client.get("/api/market/stats")
    assert response.status_code == 200
    data = response.json()
    assert "user_csv_records" in data
    assert "demo_seed_records" in data
    assert "total_records" in data
    assert data["total_records"] > 0
    assert data["oldest_observation_date"] is not None
    assert data["newest_observation_date"] is not None


def test_sync_gov_api_without_key_returns_consistent_contract(monkeypatch):
    """API sync without key must return clear guidance on how to obtain one, not fake success."""
    monkeypatch.setattr("app.services.api_ingestion_service.settings.DATA_GOV_IN_API_KEY", "")
    assert "api_key" not in inspect.signature(sync_gov_api).parameters
    assert "request" in inspect.signature(sync_gov_api).parameters
    operation = app.openapi()["paths"]["/api/market/sync-gov-api"]["post"]
    assert "requestBody" in operation
    assert all(
        parameter["name"] != "api_key"
        for parameter in operation.get("parameters", [])
    )
    result = _run_immediate(sync_gov_api(request=GovernmentSyncRequest(), db=None))
    data = GovernmentSyncResult.model_validate(result).model_dump()
    assert data["success"] is False
    assert data["status"] == "API_KEY_REQUIRED"
    assert "https://www.data.gov.in" in data["instructions"]
    assert {
        "imported_count", "updated_count", "duplicate_count", "skipped_count", "fetched_count"
    } <= data.keys()
    assert all(data[count] == 0 for count in (
        "imported_count", "updated_count", "duplicate_count", "skipped_count", "fetched_count"
    ))
    assert "api_key" not in data


@pytest.mark.parametrize("status_code", [401, 403])
def test_sync_gov_api_with_invalid_key_returns_unauthorized_without_exposing_key(monkeypatch, status_code):
    """An upstream authorization failure has a stable response and never echoes credentials."""
    submitted_key = "invalid_demo_key_9999"
    observed_request = {}

    class UnauthorizedResponse:
        def __init__(self, response_status):
            self.status_code = response_status

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params):
            observed_request["url"] = url
            observed_request["params"] = params
            return UnauthorizedResponse(status_code)

    monkeypatch.setattr("app.services.api_ingestion_service.httpx.AsyncClient", FakeAsyncClient)
    result = _run_immediate(sync_gov_api(
        request=GovernmentSyncRequest(api_key=submitted_key),
        commodity="Onion",
        state=None,
        limit=200,
        db=None,
    ))
    data = GovernmentSyncResult.model_validate(result).model_dump()
    assert data["success"] is False
    assert data["status"] == "UNAUTHORIZED_KEY"
    assert data["imported_count"] == 0
    assert data["updated_count"] == 0
    assert data["duplicate_count"] == 0
    assert data["skipped_count"] == 0
    assert data["fetched_count"] == 0
    assert submitted_key not in str(data)
    assert submitted_key not in observed_request["url"]
    # data.gov.in itself requires the key as an upstream query parameter.
    assert observed_request["params"]["api-key"] == submitted_key
    assert observed_request["params"]["filters[commodity]"] == "Onion"




@pytest.mark.parametrize(
    "network_error_type",
    [httpx.RequestError, httpx.TimeoutException, httpx.ConnectError],
)
def test_sync_gov_api_network_error_does_not_echo_upstream_url_or_key(monkeypatch, network_error_type):
    submitted_key = "network_error_secret_key"

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params):
            raise network_error_type(f"network failure for {url}?api-key={submitted_key}")

    monkeypatch.setattr("app.services.api_ingestion_service.httpx.AsyncClient", FakeAsyncClient)
    result = _run_immediate(sync_gov_api(
        request=GovernmentSyncRequest(api_key=submitted_key),
        state=None,
        limit=200,
        db=None,
    ))
    data = GovernmentSyncResult.model_validate(result).model_dump()
    assert data["status"] == "NETWORK_ERROR"
    assert submitted_key not in str(data)


def test_sync_gov_api_malformed_json_is_reported_without_exposing_response(monkeypatch):
    secret = "response_must_not_be_returned"

    class MalformedResponse:
        status_code = 200

        def json(self):
            raise ValueError(f"invalid JSON: {secret}")

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            return MalformedResponse()

    monkeypatch.setattr("app.services.api_ingestion_service.httpx.AsyncClient", FakeAsyncClient)
    result = _run_immediate(sync_gov_api(
        request=GovernmentSyncRequest(api_key="request_secret"),
        state=None,
        limit=200,
        db=None,
    ))
    data = GovernmentSyncResult.model_validate(result).model_dump()
    assert data["status"] == "MALFORMED_RESPONSE"
    assert secret not in str(data)
    assert "request_secret" not in str(data)
