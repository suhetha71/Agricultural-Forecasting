import logging
import math
from datetime import datetime, date, timezone
from typing import Optional, Dict, Any, List
import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.market_observation import MarketObservation
from app.services.observation_revision_service import (
    append_current_revision,
    ensure_initial_revision,
)
from app.schemas.market_data import ImportResult

logger = logging.getLogger(__name__)
settings = get_settings()

DEFAULT_OGD_RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"
OGD_BASE_URL = f"https://api.data.gov.in/resource/{DEFAULT_OGD_RESOURCE_ID}"
MAX_PAGE_SIZE = 500
MAX_PAGES_PER_SYNC = 5


class ApiIngestionService:
    @staticmethod
    def _result(
        *,
        success: bool,
        status: str,
        message: str,
        imported: int = 0,
        updated: int = 0,
        duplicates: int = 0,
        skipped: int = 0,
        fetched: int = 0,
        total_available: Optional[int] = None,
        pagination_truncated: bool = False,
        instructions: Optional[str] = None,
        errors: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return {
            "success": success,
            "status": status,
            "message": message,
            "instructions": instructions,
            "imported_count": imported,
            "updated_count": updated,
            "duplicate_count": duplicates,
            "skipped_count": skipped,
            "fetched_count": fetched,
            "total_available_count": total_available,
            "pagination_truncated": pagination_truncated,
            "errors": errors or [],
        }

    @staticmethod
    def _parse_record(row: Any) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Validate one provider row without exposing upstream values in errors."""
        if not isinstance(row, dict):
            return None, "record is not an object"
        normalized = {str(key).strip().lower(): value for key, value in row.items()}

        def text_value(field: str) -> str:
            value = normalized.get(field)
            return "" if value is None else str(value).strip()

        state = text_value("state")
        district = text_value("district")
        market = text_value("market")
        commodity = text_value("commodity")
        variety = text_value("variety") or "Other"
        raw_date = text_value("arrival_date")
        raw_modal = text_value("modal_price")
        if not (state and district and market and commodity and raw_date and raw_modal):
            return None, "required fields are missing"

        parsed_date = None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                parsed_date = datetime.strptime(raw_date, fmt).date()
                break
            except ValueError:
                continue
        if parsed_date is None:
            return None, "observation date is invalid"

        def number(field: str, *, required: bool = False, positive: bool = False):
            value = normalized.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                return (None, not required)
            try:
                parsed = float(str(value).replace(",", "").strip())
            except (TypeError, ValueError):
                return None, False
            if not math.isfinite(parsed) or (parsed <= 0 if positive else parsed < 0):
                return None, False
            return parsed, True

        def optional_present(field: str) -> bool:
            value = normalized.get(field)
            return value is not None and not (
                isinstance(value, str) and not value.strip()
            )

        modal, valid = number("modal_price", required=True, positive=True)
        if not valid:
            return None, "modal price is invalid"
        minimum, valid = number("min_price")
        if not valid:
            return None, "minimum price is invalid"
        maximum, valid = number("max_price")
        if not valid:
            return None, "maximum price is invalid"
        arrivals, valid = number("arrivals_in_qtl")
        if not valid:
            return None, "arrival volume is invalid"

        return {
            "state": state,
            "district": district,
            "market": market,
            "commodity": commodity,
            "variety": variety,
            "observation_date": parsed_date,
            "modal_price": modal,
            "min_price": minimum,
            "max_price": maximum,
            "arrivals_in_qtl": arrivals,
            "optional_fields_present": {
                field: optional_present(field)
                for field in ("min_price", "max_price", "arrivals_in_qtl")
            },
        }, None

    @staticmethod
    async def sync_from_datagov(
        db: Session,
        api_key: Optional[str] = None,
        limit: int = 200,
        commodity_filter: Optional[str] = None,
        state_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Interacts with the official Government of India Open Data platform (data.gov.in)
        for daily mandi wholesale prices from AGMARKNET.
        Validates API key, handles schema variations, and upserts authenticated observations.
        """
        key = api_key or settings.DATA_GOV_IN_API_KEY
        if not key or not key.strip():
            return ApiIngestionService._result(
                success=False,
                status="API_KEY_REQUIRED",
                message="Authentication key required for official data.gov.in API access.",
                instructions=(
                    "To query the official National AGMARKNET portal via data.gov.in:\n"
                    "1. Register a free account at https://www.data.gov.in\n"
                    "2. Navigate to 'My Account' -> 'API Key' to generate your personal key.\n"
                    "3. Add DATA_GOV_IN_API_KEY=<your_key> to backend/.env, or pass the key in the sync request.\n"
                    "Note: In the meantime, the offline CSV import module supports full official Agmarknet export files."
                ),
                errors=["Missing API key in environment and request body."],
            )

        page_size = min(max(int(limit), 1), MAX_PAGE_SIZE)
        raw_records: List[Any] = []
        total_available: Optional[int] = None
        pagination_truncated = False
        offset = 0

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                for page_index in range(MAX_PAGES_PER_SYNC):
                    params = {
                        "api-key": key.strip(),
                        "format": "json",
                        "limit": page_size,
                        "offset": offset,
                    }
                    if commodity_filter:
                        params["filters[commodity]"] = commodity_filter
                    if state_filter:
                        params["filters[state]"] = state_filter

                    response = await client.get(OGD_BASE_URL, params=params)
                    if response.status_code != 200:
                        if response.status_code in (401, 403):
                            status = "UNAUTHORIZED_KEY"
                            message = "The government API rejected the supplied credentials."
                        elif response.status_code == 400:
                            status = "BAD_REQUEST"
                            message = "data.gov.in rejected the request parameters."
                        else:
                            status = f"HTTP_{response.status_code}"
                            message = f"Government API returned HTTP {response.status_code}."
                        logger.warning("data.gov.in request failed with status %s", response.status_code)
                        return ApiIngestionService._result(
                            success=False,
                            status=status,
                            message=message,
                            fetched=len(raw_records),
                            total_available=total_available,
                            errors=[message],
                        )

                    try:
                        data = response.json()
                    except (ValueError, TypeError):
                        data = None
                    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
                        return ApiIngestionService._result(
                            success=False,
                            status="MALFORMED_RESPONSE",
                            message="Government API returned an invalid response format; no records were changed.",
                            fetched=len(raw_records),
                            total_available=total_available,
                            errors=["Expected a JSON object containing a records array."],
                        )

                    if "total" in data:
                        try:
                            page_total = int(data["total"])
                            if isinstance(data["total"], bool) or page_total < 0:
                                raise ValueError
                        except (TypeError, ValueError):
                            return ApiIngestionService._result(
                                success=False,
                                status="MALFORMED_RESPONSE",
                                message="Government API returned an invalid result count; no records were changed.",
                                fetched=len(raw_records),
                                total_available=total_available,
                                errors=["The response total must be a non-negative integer."],
                            )
                        if total_available is None:
                            total_available = page_total

                    page_records = data["records"]
                    if len(page_records) > page_size:
                        return ApiIngestionService._result(
                            success=False,
                            status="MALFORMED_RESPONSE",
                            message="Government API returned more rows than requested; no records were changed.",
                            fetched=len(raw_records),
                            total_available=total_available,
                            errors=["Response page exceeded the requested limit."],
                        )
                    if not page_records:
                        if total_available is not None and offset < total_available:
                            return ApiIngestionService._result(
                                success=False,
                                status="MALFORMED_RESPONSE",
                                message="Government API returned an empty page before the reported end; no records were changed.",
                                fetched=len(raw_records),
                                total_available=total_available,
                                errors=["Pagination stopped before the reported total was reached."],
                            )
                        break

                    raw_records.extend(page_records)
                    offset += len(page_records)
                    if total_available is not None and offset >= total_available:
                        break
                    if total_available is None and len(page_records) < page_size:
                        break
                    if page_index == MAX_PAGES_PER_SYNC - 1:
                        pagination_truncated = (
                            total_available is None
                            or offset < total_available
                            or len(page_records) == page_size
                        )

        except httpx.RequestError as req_err:
            # Request exceptions may contain the full upstream URL and API key.
            err_type = type(req_err).__name__
            logger.error("Network error connecting to data.gov.in (%s)", err_type)
            return ApiIngestionService._result(
                success=False,
                status="NETWORK_ERROR",
                message="Failed to connect to data.gov.in; no records were changed.",
                fetched=len(raw_records),
                total_available=total_available,
                errors=["Network request failed; request details were omitted."],
            )

        if total_available == 0 and raw_records:
            return ApiIngestionService._result(
                success=False,
                status="MALFORMED_RESPONSE",
                message="Government API reported zero results but returned rows; no records were changed.",
                fetched=len(raw_records),
                total_available=total_available,
                errors=["The response records and total fields disagree."],
            )
        if not raw_records:
            return ApiIngestionService._result(
                success=True,
                status="EMPTY_RESULT",
                message="The government API request succeeded but returned no records for these filters.",
                total_available=total_available,
            )

        parsed_records: List[Dict[str, Any]] = []
        skipped = 0
        parse_errors: List[str] = []
        for index, row in enumerate(raw_records, start=1):
            parsed, error = ApiIngestionService._parse_record(row)
            if error:
                skipped += 1
                if len(parse_errors) < 5:
                    parse_errors.append(f"Record {index}: {error}.")
            else:
                parsed_records.append(parsed)

        if not parsed_records:
            return ApiIngestionService._result(
                success=False,
                status="NO_VALID_RECORDS",
                message="The API returned records, but none passed validation; no records were changed.",
                skipped=skipped,
                fetched=len(raw_records),
                total_available=total_available,
                pagination_truncated=pagination_truncated,
                errors=parse_errors,
            )

        imported = 0
        updated = 0
        duplicates = 0
        now_utc = datetime.now(timezone.utc)

        try:
            for parsed in parsed_records:
                state_val = parsed["state"]
                district_val = parsed["district"]
                market_val = parsed["market"]
                comm_val = parsed["commodity"]
                var_val = parsed["variety"]
                parsed_date = parsed["observation_date"]

                existing = (
                    db.query(MarketObservation)
                    .filter(
                        MarketObservation.state == state_val,
                        MarketObservation.district == district_val,
                        MarketObservation.market == market_val,
                        MarketObservation.commodity == comm_val,
                        MarketObservation.variety == var_val,
                        MarketObservation.observation_date == parsed_date,
                    )
                    .first()
                )

                if existing:
                    # Omitted optional provider fields do not erase previously known values.
                    min_val = (
                        parsed["min_price"]
                        if parsed["optional_fields_present"]["min_price"]
                        else existing.min_price
                    )
                    max_val = (
                        parsed["max_price"]
                        if parsed["optional_fields_present"]["max_price"]
                        else existing.max_price
                    )
                    arrivals_val = (
                        parsed["arrivals_in_qtl"]
                        if parsed["optional_fields_present"]["arrivals_in_qtl"]
                        else existing.arrivals_in_qtl
                    )
                    changed = any((
                        existing.modal_price != parsed["modal_price"],
                        existing.min_price != min_val,
                        existing.max_price != max_val,
                        existing.arrivals_in_qtl != arrivals_val,
                    ))
                    if not changed:
                        duplicates += 1
                        continue

                    ensure_initial_revision(db, existing)
                    existing.modal_price = parsed["modal_price"]
                    existing.min_price = min_val
                    existing.max_price = max_val
                    existing.arrivals_in_qtl = arrivals_val
                    existing.retrieval_timestamp = now_utc
                    existing.source = "OFFICIAL_GOV_API"
                    existing.source_available_at = None
                    existing.availability_status = "INGESTION_TIME_ONLY"
                    append_current_revision(db, existing)
                    updated += 1
                else:
                    new_obs = MarketObservation(
                        state=state_val,
                        district=district_val,
                        market=market_val,
                        commodity=comm_val,
                        variety=var_val,
                        observation_date=parsed_date,
                        min_price=parsed["min_price"],
                        max_price=parsed["max_price"],
                        modal_price=parsed["modal_price"],
                        arrivals_in_qtl=parsed["arrivals_in_qtl"],
                        unit="INR/Quintal",
                        original_unit="Rs/Quintal",
                        source="OFFICIAL_GOV_API",
                        retrieval_timestamp=now_utc,
                        first_ingested_at=now_utc,
                        availability_status="INGESTION_TIME_ONLY",
                    )
                    db.add(new_obs)
                    db.flush()
                    ensure_initial_revision(db, new_obs)
                    imported += 1

            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error("Database write failed during data.gov.in sync (%s)", type(exc).__name__)
            return ApiIngestionService._result(
                success=False,
                status="DATABASE_WRITE_ERROR",
                message="The synchronization batch could not be saved; no batch changes were committed.",
                skipped=skipped,
                fetched=len(raw_records),
                total_available=total_available,
                pagination_truncated=pagination_truncated,
                errors=["Database transaction failed; details were omitted."],
            )

        if skipped and not (imported or updated or duplicates):
            success = False
            status = "NO_VALID_RECORDS"
            message = "The API returned records, but none passed validation; no records were changed."
        elif pagination_truncated or skipped:
            success = True
            status = "PARTIAL_RESULT"
            message = (
                f"Sync processed {len(raw_records)} fetched rows: {imported} imported, "
                f"{updated} updated, {duplicates} unchanged, {skipped} skipped."
            )
            if pagination_truncated:
                message += f" Pagination stopped at the configured {MAX_PAGES_PER_SYNC}-page safety cap."
        else:
            success = True
            status = "COMPLETED"
            message = (
                f"Sync processed {len(raw_records)} fetched rows: {imported} imported, "
                f"{updated} updated, {duplicates} unchanged."
            )

        return ApiIngestionService._result(
            success=success,
            status=status,
            message=message,
            imported=imported,
            updated=updated,
            duplicates=duplicates,
            skipped=skipped,
            fetched=len(raw_records),
            total_available=total_available,
            pagination_truncated=pagination_truncated,
            errors=parse_errors,
        )
