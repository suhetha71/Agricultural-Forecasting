"""Small, validated client for Open-Meteo's historical daily archive."""
from __future__ import annotations

import logging
import math
import threading
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
WEATHER_SOURCE = "Open-Meteo Historical Weather API / ERA5 reanalysis"
WEATHER_ATTRIBUTION_URL = "https://open-meteo.com/"
SUCCESS_CACHE_TTL_SECONDS = 6 * 60 * 60
FAILURE_CACHE_TTL_SECONDS = 60
MAX_CACHE_ENTRIES = 64

_cache: Dict[Tuple[float, float, str, str], Tuple[float, Dict[str, Any]]] = {}
_cache_lock = threading.Lock()


def _numeric(value: Any, *, lower: Optional[float] = None, upper: Optional[float] = None) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("weather values must be numeric")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("weather values must be numeric") from exc
    if not math.isfinite(parsed):
        raise ValueError("weather values must be finite")
    if lower is not None and parsed < lower:
        raise ValueError("weather value is below its valid range")
    if upper is not None and parsed > upper:
        raise ValueError("weather value is above its valid range")
    return parsed


class WeatherService:
    @staticmethod
    def _failure(status: str, message: str) -> Dict[str, Any]:
        return {"status": status, "records": [], "message": message}

    @staticmethod
    def get_daily_weather(
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """Fetch and validate ERA5 daily values; failures are safe analytics results."""
        try:
            lat = _numeric(latitude, lower=-90, upper=90)
            lon = _numeric(longitude, lower=-180, upper=180)
        except ValueError:
            return WeatherService._failure("INVALID_COORDINATES", "Weather coordinates are invalid.")
        if lat is None or lon is None:
            return WeatherService._failure("INVALID_COORDINATES", "Weather coordinates are invalid.")
        if not isinstance(start_date, date) or not isinstance(end_date, date) or start_date > end_date:
            return WeatherService._failure("INVALID_DATE_RANGE", "Weather date range is invalid.")

        key = (round(lat, 5), round(lon, 5), start_date.isoformat(), end_date.isoformat())
        now = time.monotonic()
        with _cache_lock:
            cached = _cache.get(key)
            if cached and cached[0] > now:
                return {**cached[1], "records": list(cached[1]["records"])}
            if cached:
                _cache.pop(key, None)

        result: Dict[str, Any]
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(
                    ARCHIVE_URL,
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                        "temperature_unit": "celsius",
                        "precipitation_unit": "mm",
                        "timezone": "Asia/Kolkata",
                        "models": "era5",
                    },
                )
                response.raise_for_status()
                payload = response.json()
            result = WeatherService._parse_payload(payload, start_date, end_date)
        except httpx.TimeoutException:
            logger.warning("Open-Meteo historical request timed out")
            result = WeatherService._failure("PROVIDER_UNAVAILABLE", "Weather provider timed out.")
        except httpx.HTTPStatusError as exc:
            logger.warning("Open-Meteo historical request failed with HTTP %s", exc.response.status_code)
            result = WeatherService._failure("PROVIDER_UNAVAILABLE", "Weather provider returned an error.")
        except httpx.RequestError as exc:
            logger.warning("Open-Meteo historical request failed (%s)", type(exc).__name__)
            result = WeatherService._failure("PROVIDER_UNAVAILABLE", "Weather provider could not be reached.")
        except (ValueError, TypeError, KeyError, OverflowError):
            logger.warning("Open-Meteo historical response was malformed")
            result = WeatherService._failure("MALFORMED_RESPONSE", "Weather provider returned invalid data.")

        ttl = SUCCESS_CACHE_TTL_SECONDS if result["status"] == "AVAILABLE" else FAILURE_CACHE_TTL_SECONDS
        with _cache_lock:
            if len(_cache) >= MAX_CACHE_ENTRIES:
                oldest_key = min(_cache, key=lambda cache_key: _cache[cache_key][0])
                _cache.pop(oldest_key, None)
            _cache[key] = (time.monotonic() + ttl, result)
        return {**result, "records": list(result["records"])}

    @staticmethod
    def _parse_payload(payload: Any, start_date: date, end_date: date) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("response must be an object")
        daily = payload.get("daily")
        units = payload.get("daily_units")
        if not isinstance(daily, dict) or not isinstance(units, dict):
            raise ValueError("daily values and units are required")
        expected_units = {
            "temperature_2m_max": "°C",
            "temperature_2m_min": "°C",
            "precipitation_sum": "mm",
        }
        for field, expected in expected_units.items():
            if units.get(field) != expected:
                raise ValueError("weather units are missing or unexpected")
        times = daily.get("time")
        arrays = {field: daily.get(field) for field in expected_units}
        if not isinstance(times, list) or any(not isinstance(values, list) for values in arrays.values()):
            raise ValueError("weather arrays are missing")
        if any(len(values) != len(times) for values in arrays.values()):
            raise ValueError("weather arrays have inconsistent lengths")

        records: List[Dict[str, Any]] = []
        seen = set()
        for index, raw_day in enumerate(times):
            if not isinstance(raw_day, str):
                raise ValueError("weather date is invalid")
            day = date.fromisoformat(raw_day)
            if day.isoformat() != raw_day or day < start_date or day > end_date or day in seen:
                raise ValueError("weather dates are invalid")
            seen.add(day)
            maximum = _numeric(arrays["temperature_2m_max"][index], lower=-100, upper=70)
            minimum = _numeric(arrays["temperature_2m_min"][index], lower=-100, upper=70)
            precipitation = _numeric(arrays["precipitation_sum"][index], lower=0)
            if maximum is not None and minimum is not None and maximum < minimum:
                raise ValueError("daily maximum temperature is lower than minimum")
            if maximum is None and minimum is None and precipitation is None:
                continue
            records.append({
                "observation_date": day,
                "temperature_max_c": maximum,
                "temperature_min_c": minimum,
                "precipitation_mm": precipitation,
            })
        if not records:
            return WeatherService._failure("NO_DATA", "No weather values were available for these dates.")
        return {"status": "AVAILABLE", "records": records, "message": "Historical weather retrieved."}


def clear_weather_cache() -> None:
    """Clear cache for deterministic tests and controlled runtime maintenance."""
    with _cache_lock:
        _cache.clear()
