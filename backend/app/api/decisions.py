from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.decision_service import DecisionService
from app.schemas.decision import (
    DecisionRequest,
    DecisionRecommendation,
    WhatIfSimulationRequest,
    WhatIfSimulationResponse,
    ComprehensiveDecisionRequest,
    ComprehensiveDecisionResponse,
    MarketComparisonRequest,
    MarketComparisonResponse,
)

router = APIRouter(prefix="/decision", tags=["Decision Support"])


@router.post("/evaluate-options", response_model=ComprehensiveDecisionResponse)
def evaluate_comprehensive_options(
    request: ComprehensiveDecisionRequest,
    db: Session = Depends(get_db),
):
    """
    Ranks Selling Options (Sell Now, Wait on-farm, Store in warehouse)
    using actual market observations, multi-horizon forecasts, holdout uncertainty bounds,
    and user-specified fixed vs variable cost structures.
    """
    try:
        return DecisionService.evaluate_comprehensive_decision(db, request)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to evaluate decision options: {str(e)}")


@router.post("/compare-markets", response_model=MarketComparisonResponse)
def compare_markets_intelligently(
    request: MarketComparisonRequest,
    db: Session = Depends(get_db),
):
    """
    Ranks regional agricultural markets strictly by estimated net realization
    after deducting user transport costs and mandi handling fees.
    Supports spot prices and ML forecast horizons with uncertainty warnings.
    """
    try:
        return DecisionService.compare_markets_intelligently(db, request)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compare markets: {str(e)}")


@router.post("/evaluate", response_model=DecisionRecommendation)
def evaluate_decision(
    request: DecisionRequest,
    db: Session = Depends(get_db),
):
    """
    Produce an economic decision recommendation (SELL NOW, WAIT, or STORE)
    factoring in price forecast, storage rent, shrinkage, and capital opportunity cost.
    (Maintained for legacy compatibility)
    """
    try:
        return DecisionService.evaluate_selling_decision(db, request)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error evaluating decision: {str(e)}")


@router.post("/what-if", response_model=WhatIfSimulationResponse)
def simulate_what_if(
    request: WhatIfSimulationRequest,
):
    """
    Simulate financial outcome of holding vs selling today under custom user parameters.
    Clearly marks manually adjusted prices as hypothetical scenarios.
    """
    try:
        return DecisionService.simulate_what_if(request)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in simulation: {str(e)}")
