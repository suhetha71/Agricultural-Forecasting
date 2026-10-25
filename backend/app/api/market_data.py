from datetime import date
from typing import Optional, List, Dict
from fastapi import APIRouter, Body, Depends, Query, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.market_service import MarketService
from app.services.api_ingestion_service import ApiIngestionService
from app.schemas.market_data import (
    MarketObservationRead,
    MarketSummary,
    MandiComparisonItem,
    DataSourceStats,
    ImportResult,
    GovernmentSyncRequest,
    GovernmentSyncResult,
)

router = APIRouter(prefix="/market", tags=["Market Data"])


@router.get("/observations")
def get_observations(
    commodity: Optional[str] = Query(None, description="Filter by crop name"),
    market: Optional[str] = Query(None, description="Filter by mandi name"),
    state: Optional[str] = Query(None, description="Filter by state"),
    district: Optional[str] = Query(None, description="Filter by district"),
    variety: Optional[str] = Query(None, description="Filter by variety"),
    source: Optional[str] = Query(None, description="Filter by source: OFFICIAL_GOV_API, USER_CSV_IMPORT, DEMO_SEED_DATA"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Fetch paginated, chronological mandi price observations."""
    records, total = MarketService.get_observations(
        db,
        commodity=commodity,
        market=market,
        state=state,
        district=district,
        variety=variety,
        source=source,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [MarketObservationRead.model_validate(r) for r in records],
    }


@router.get("/filters")
def get_filters(db: Session = Depends(get_db)) -> Dict[str, List[str]]:
    """Return available commodity, state, district, and market filter options."""
    return MarketService.get_filter_options(db)


@router.get("/stats", response_model=DataSourceStats)
def get_stats(db: Session = Depends(get_db)):
    """Return provenance breakdown of records (official API, CSV imports, demo seed data)."""
    return MarketService.get_data_source_stats(db)


@router.post("/sync-gov-api", response_model=GovernmentSyncResult)
async def sync_gov_api(
    request: Optional[GovernmentSyncRequest] = Body(None),
    commodity: Optional[str] = Query(None, description="Filter specific crop"),
    state: Optional[str] = Query(None, description="Filter specific state"),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """
    Triggers direct ingestion from official Government of India portal (data.gov.in / Agmarknet).
    Validates API key and safely upserts observations tagged as OFFICIAL_GOV_API.
    """
    return await ApiIngestionService.sync_from_datagov(
        db,
        api_key=request.api_key if request else None,
        limit=limit,
        commodity_filter=commodity,
        state_filter=state,
    )


@router.get("/summary", response_model=Optional[MarketSummary])
def get_summary(
    commodity: str = Query(..., description="Crop name"),
    market: str = Query(..., description="Mandi name"),
    db: Session = Depends(get_db),
):
    """Get 30-day price summary, recent momentum, and extremes."""
    summary = MarketService.get_market_summary(db, commodity=commodity, market=market)
    if not summary:
        raise HTTPException(status_code=404, detail=f"No observations found for {commodity} at {market}")
    return summary


@router.get("/compare", response_model=List[MandiComparisonItem])
def compare_mandis(
    commodity: str = Query(..., description="Crop name"),
    reference_market: Optional[str] = Query(None, description="Local mandi to calculate price difference from"),
    state: Optional[str] = Query(None, description="Filter within state"),
    cost_per_km_qtl: float = Query(1.5, ge=0.0, description="Transport cost per km per quintal"),
    db: Session = Depends(get_db),
):
    """Compare prices across mandis and calculate net realization after logistics."""
    return MarketService.compare_mandis(
        db,
        commodity=commodity,
        reference_market=reference_market,
        state=state,
        cost_per_km_qtl=cost_per_km_qtl,
    )


@router.post("/upload-csv", response_model=ImportResult)
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload official Agmarknet CSV export.
    Deduplicates records against existing database entries and tags source as USER_CSV_IMPORT.
    """
    if not file.filename.endswith((".csv", ".txt")):
        raise HTTPException(status_code=400, detail="Only CSV or text files are supported.")

    try:
        content_bytes = await file.read()
        content_str = content_bytes.decode("utf-8", errors="replace")
        result = MarketService.import_csv_records(db, content_str, source_label="USER_CSV_IMPORT")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing upload: {str(e)}")
