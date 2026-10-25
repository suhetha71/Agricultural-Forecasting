from datetime import date, datetime, timezone

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models.market_observation import MarketObservation
from app.schemas.analytics import ArrivalsWeatherResponse
from app.services.analytics_service import AnalyticsService
from app.services.weather_service import WeatherService, clear_weather_cache


@pytest.fixture
def isolated_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def _payload(days=("2026-01-01", "2026-01-02")):
    return {
        "daily_units": {
            "temperature_2m_max": "°C",
            "temperature_2m_min": "°C",
            "precipitation_sum": "mm",
        },
        "daily": {
            "time": list(days),
            "temperature_2m_max": [22.5 for _ in days],
            "temperature_2m_min": [11.5 for _ in days],
            "precipitation_sum": [0.2 for _ in days],
        },
    }


class _Response:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def _client(monkeypatch, get):
    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.timeout = kwargs.get("timeout")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, params):
            return get(url, params)

    monkeypatch.setattr("app.services.weather_service.httpx.Client", FakeClient)


@pytest.fixture(autouse=True)
def reset_cache():
    clear_weather_cache()
    yield
    clear_weather_cache()


def test_historical_weather_success_validates_request_and_units(monkeypatch):
    seen = {}
    _client(monkeypatch, lambda url, params: (seen.update(url=url, params=params) or _Response(_payload())))

    result = WeatherService.get_daily_weather(
        20.1472, 74.2256, date(2026, 1, 1), date(2026, 1, 2)
    )

    assert result["status"] == "AVAILABLE"
    assert len(result["records"]) == 2
    assert result["records"][0]["temperature_max_c"] == 22.5
    assert result["records"][0]["precipitation_mm"] == 0.2
    assert seen["url"] == "https://archive-api.open-meteo.com/v1/archive"
    assert seen["params"]["models"] == "era5"
    assert seen["params"]["timezone"] == "Asia/Kolkata"
    assert seen["params"]["temperature_unit"] == "celsius"
    assert seen["params"]["precipitation_unit"] == "mm"


@pytest.mark.parametrize("latitude,longitude", [(None, 75), (91, 75), (20, -181), (float("nan"), 75)])
def test_weather_rejects_missing_or_invalid_coordinates_without_request(monkeypatch, latitude, longitude):
    def unexpected_request(*args, **kwargs):
        raise AssertionError("invalid coordinates must not trigger an HTTP request")

    _client(monkeypatch, unexpected_request)
    result = WeatherService.get_daily_weather(latitude, longitude, date(2026, 1, 1), date(2026, 1, 1))
    assert result["status"] == "INVALID_COORDINATES"
    assert result["records"] == []


def test_weather_rejects_invalid_date_range_without_request(monkeypatch):
    _client(monkeypatch, lambda *args: pytest.fail("invalid range must not trigger request"))
    result = WeatherService.get_daily_weather(20, 75, date(2026, 1, 2), date(2026, 1, 1))
    assert result["status"] == "INVALID_DATE_RANGE"


def test_weather_timeout_is_a_safe_unavailable_result(monkeypatch):
    def timeout(*args, **kwargs):
        raise httpx.TimeoutException("provider timeout")

    _client(monkeypatch, timeout)
    result = WeatherService.get_daily_weather(20, 75, date(2026, 1, 1), date(2026, 1, 1))
    assert result["status"] == "PROVIDER_UNAVAILABLE"
    assert result["records"] == []


def test_weather_http_error_is_a_safe_unavailable_result(monkeypatch):
    response = httpx.Response(503, request=httpx.Request("GET", "https://archive-api.open-meteo.com"))

    class FailedResponse(_Response):
        def raise_for_status(self):
            raise httpx.HTTPStatusError("upstream details", request=response.request, response=response)

    _client(monkeypatch, lambda *args: FailedResponse({}))
    result = WeatherService.get_daily_weather(20, 75, date(2026, 1, 1), date(2026, 1, 1))
    assert result["status"] == "PROVIDER_UNAVAILABLE"
    assert result["records"] == []


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {"daily": {}, "daily_units": {}},
        {**_payload(), "daily_units": {"temperature_2m_max": "°F"}},
        {**_payload(), "daily": {**_payload()["daily"], "precipitation_sum": [1]}},
        {**_payload(), "daily": {**_payload()["daily"], "time": ["not-a-date", "2026-01-02"]}},
        {**_payload(), "daily": {**_payload()["daily"], "temperature_2m_max": [float("inf"), 22.0]}},
        {**_payload(), "daily": {**_payload()["daily"], "temperature_2m_max": [None, None], "temperature_2m_min": [None, None], "precipitation_sum": [None, None]}},
    ],
)
def test_weather_rejects_malformed_or_empty_values(payload, monkeypatch):
    _client(monkeypatch, lambda *args: _Response(payload))
    result = WeatherService.get_daily_weather(20, 75, date(2026, 1, 1), date(2026, 1, 2))
    assert result["status"] in ("MALFORMED_RESPONSE", "NO_DATA")
    assert result["records"] == []


def test_weather_success_cache_avoids_repeated_provider_request(monkeypatch):
    calls = []
    _client(monkeypatch, lambda *args: (calls.append(args) or _Response(_payload(("2026-01-01",)))))
    args = (20.0, 75.0, date(2026, 1, 1), date(2026, 1, 1))
    first = WeatherService.get_daily_weather(*args)
    second = WeatherService.get_daily_weather(*args)
    assert first == second
    assert len(calls) == 1


def test_analytics_aligns_weather_only_to_observed_market_dates(isolated_db, monkeypatch):
    db = isolated_db
    db.add_all([
        MarketObservation(
            state="Maharashtra", district="Nashik", market="Lasalgaon", commodity="Onion",
            variety="Red", observation_date=date(2026, 1, day), modal_price=100 + day,
            source="USER_CSV_IMPORT", retrieval_timestamp=datetime.now(timezone.utc),
        )
        for day in (1, 2)
    ])
    db.commit()

    monkeypatch.setattr(
        WeatherService,
        "get_daily_weather",
        lambda *args: {
            "status": "AVAILABLE",
            "records": [{
                "observation_date": date(2026, 1, 1),
                "temperature_max_c": 23.0,
                "temperature_min_c": 12.0,
                "precipitation_mm": 0.0,
            }],
            "message": "mocked weather",
        },
    )

    response = AnalyticsService.get_arrivals_weather_analysis(db, "Onion", "Lasalgaon")
    validated = ArrivalsWeatherResponse.model_validate(response)
    assert validated.weather_status == "PARTIAL"
    assert validated.weather_available is True
    assert validated.weather_aligned_count == 1
    assert validated.weather_missing_date_count == 1
    assert [row.observation_date for row in validated.weather_observations] == [date(2026, 1, 1)]
    assert validated.price_arrival_correlation is None


def test_provider_failure_does_not_break_market_arrivals_analysis(isolated_db, monkeypatch):
    db = isolated_db
    db.add(MarketObservation(
        state="Maharashtra", district="Nashik", market="Lasalgaon", commodity="Onion",
        variety="Red", observation_date=date(2026, 1, 1), modal_price=100,
        arrivals_in_qtl=5, source="USER_CSV_IMPORT", retrieval_timestamp=datetime.now(timezone.utc),
    ))
    db.commit()
    monkeypatch.setattr(
        WeatherService,
        "get_daily_weather",
        lambda *args: {"status": "PROVIDER_UNAVAILABLE", "records": [], "message": "safe error"},
    )

    result = AnalyticsService.get_arrivals_weather_analysis(db, "Onion", "Lasalgaon")
    assert result.total_observations == 1
    assert result.arrivals_reported_count == 1
    assert result.weather_status == "PROVIDER_UNAVAILABLE"
    assert result.weather_available is False
    assert result.weather_observations == []
