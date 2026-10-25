from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.config import get_settings
from app.schemas.health import HealthResponse
from app.models.market_observation import MarketObservation
from app.models.forecast_record import ForecastRecord

router = APIRouter(prefix="/health", tags=["Health"])
settings = get_settings()


@router.get("", response_model=HealthResponse)
def get_health(db: Session = Depends(get_db)):
    """
    Health check endpoint verifying application status, database connectivity,
    and current data counts.
    """
    db_connected = False
    total_obs = 0
    total_fc = 0

    try:
        # Simple connectivity check
        db.execute(text("SELECT 1"))
        db_connected = True
        total_obs = db.query(MarketObservation).count()
        total_fc = db.query(ForecastRecord).count()
    except Exception:
        db_connected = False

    return HealthResponse(
        status="healthy" if db_connected else "degraded",
        app_name=settings.APP_NAME,
        version="1.0.0",
        database_connected=db_connected,
        total_observations=total_obs,
        total_forecasts=total_fc,
    )
