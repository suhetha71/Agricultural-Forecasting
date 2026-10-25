from app.api.health import router as health_router
from app.api.market_data import router as market_router
from app.api.forecasts import router as forecast_router
from app.api.decisions import router as decision_router
from app.api.analytics import router as analytics_router

__all__ = [
    "health_router",
    "market_router",
    "forecast_router",
    "decision_router",
    "analytics_router",
]
