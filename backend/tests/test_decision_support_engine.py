import pytest
from datetime import date
from types import SimpleNamespace
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import SessionLocal
from app.models.market_observation import MarketObservation
from app.services.decision_service import DecisionService
from app.schemas.decision import (
    ComprehensiveDecisionRequest,
    MarketComparisonRequest,
    WhatIfSimulationRequest,
)

client = TestClient(app)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# 1. NET-RETURN CALCULATIONS (Sell Now, Wait, Store)
# ---------------------------------------------------------------------------
def test_net_return_calculations_sell_now_wait_store(db_session: Session):
    """
    Verifies that Net Return = Gross Revenue − Total Deductions
    for Sell Now, Wait, and Store options, and that per-kg metrics match.
    """
    req = ComprehensiveDecisionRequest(
        commodity="Onion",
        market="Lasalgaon",
        quantity=100.0,
        quantity_unit="quintal",
        transport_distance_km=20.0,
        transport_cost_per_km_qtl=1.5,
        transport_fixed_vehicle_fee=500.0,
        other_cost_fixed=200.0,
        other_cost_per_qtl=10.0,
    )
    res = DecisionService.evaluate_comprehensive_decision(db_session, req)

    # Check Sell Now
    assert res.sell_now.gross_revenue == round(res.quantity_qtl * res.effective_selling_price_now, 2)
    assert res.sell_now.estimated_net_return == round(res.sell_now.gross_revenue - res.sell_now.total_deductions, 2)
    assert abs(res.sell_now.net_return_per_kg - (res.sell_now.estimated_net_return / res.quantity_kg)) < 0.05

    # Check Wait
    assert res.wait.estimated_net_return == round(res.wait.gross_revenue - res.wait.total_deductions, 2)
    assert abs(res.wait.net_return_per_kg - (res.wait.estimated_net_return / res.wait.remaining_quantity_kg)) < 0.05

    # Check Store
    assert res.store.estimated_net_return == round(res.store.gross_revenue - res.store.total_deductions, 2)
    assert abs(res.store.net_return_per_kg - (res.store.estimated_net_return / res.store.remaining_quantity_kg)) < 0.05


def test_sell_now_uncertainty_disclosure_does_not_guarantee_quote_realization(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.decision_service.ForecastingService.generate_forecast",
        lambda *args, **kwargs: SimpleNamespace(forecasts=[], is_sufficient_data=False, model_used="None"),
    )
    monkeypatch.setattr(
        "app.services.decision_service.ForecastingService.get_forecast_uncertainty",
        lambda *args, **kwargs: SimpleNamespace(horizons=[]),
    )
    result = DecisionService.evaluate_comprehensive_decision(
        db_session,
        ComprehensiveDecisionRequest(commodity="Onion", market="Lasalgaon", quantity=10),
    )
    assert result.recommended_option == "SELL NOW"
    assert "Actual auction realization and selling costs may differ" in result.uncertainty_impact_analysis
    assert "fully locked in" not in result.uncertainty_impact_analysis.lower()


# ---------------------------------------------------------------------------
# 2. PER-UNIT VERSUS FIXED COSTS
# ---------------------------------------------------------------------------
def test_per_unit_versus_fixed_costs(db_session: Session):
    """
    Validates that scaling the sale quantity scales variable transport and handling costs,
    while fixed vehicle fees and gate fees remain strictly constant.
    """
    fixed_vehicle = 600.0
    fixed_gate = 150.0

    # 50 Quintals
    req_50 = ComprehensiveDecisionRequest(
        commodity="Onion",
        market="Lasalgaon",
        quantity=50.0,
        quantity_unit="quintal",
        transport_distance_km=20.0,
        transport_cost_per_km_qtl=2.0,
        transport_fixed_vehicle_fee=fixed_vehicle,
        other_cost_fixed=fixed_gate,
        other_cost_per_qtl=12.0,
    )
    res_50 = DecisionService.evaluate_comprehensive_decision(db_session, req_50)

    # 100 Quintals (Double quantity)
    req_100 = ComprehensiveDecisionRequest(
        commodity="Onion",
        market="Lasalgaon",
        quantity=100.0,
        quantity_unit="quintal",
        transport_distance_km=20.0,
        transport_cost_per_km_qtl=2.0,
        transport_fixed_vehicle_fee=fixed_vehicle,
        other_cost_fixed=fixed_gate,
        other_cost_per_qtl=12.0,
    )
    res_100 = DecisionService.evaluate_comprehensive_decision(db_session, req_100)

    # Fixed costs must be identical
    assert res_50.sell_now.fixed_costs_total == res_100.sell_now.fixed_costs_total == (fixed_vehicle + fixed_gate)

    # Variable costs must double
    # Var transport: 50 * 20 * 2 = 2000 vs 100 * 20 * 2 = 4000
    # Var other: 50 * 12 = 600 vs 100 * 12 = 1200
    assert abs(res_100.sell_now.variable_costs_total - (2.0 * res_50.sell_now.variable_costs_total)) < 1.0


# ---------------------------------------------------------------------------
# 3. SPOILAGE AND REMAINING QUANTITY
# ---------------------------------------------------------------------------
def test_spoilage_and_remaining_quantity(db_session: Session):
    """
    Validates physical moisture loss / shrinkage calculations and confirms
    that post-holding transport freight is charged on delivered weight only.
    """
    req = ComprehensiveDecisionRequest(
        commodity="Onion",
        market="Lasalgaon",
        quantity=100.0,
        quantity_unit="quintal",
        store_horizon_days=30,
        user_spoilage_monthly_pct=5.0,  # 5% monthly shrinkage
    )
    res = DecisionService.evaluate_comprehensive_decision(db_session, req)

    # 100 Qtl with 5% shrinkage over 30 days = 95 Qtl remaining
    assert res.store.spoilage_loss_pct == 5.0
    assert res.store.remaining_quantity_qtl == 95.0
    assert res.store.spoilage_loss_qtl == 5.0
    assert res.store.remaining_quantity_kg == 9500.0


# ---------------------------------------------------------------------------
# 4. INVALID INPUTS AND UNITS
# ---------------------------------------------------------------------------
def test_invalid_inputs_and_units(db_session: Session):
    """
    Validates that non-positive quantities or unsupported units trigger
    informative ValueError / HTTP 400 exceptions.
    """
    # Non-positive quantity
    with pytest.raises(ValueError, match="strictly positive"):
        DecisionService.normalize_quantity_to_qtl(-5.0, "kg")

    with pytest.raises(ValueError, match="strictly positive"):
        DecisionService.normalize_quantity_to_qtl(0.0, "quintal")

    # Unsupported unit
    with pytest.raises(ValueError, match="Unsupported unit"):
        DecisionService.normalize_quantity_to_qtl(100.0, "bushels")

    # API validation test
    payload = {
        "commodity": "Onion",
        "market": "Lasalgaon",
        "quantity": -20.0,
        "quantity_unit": "quintal",
    }
    response = client.post("/api/decision/evaluate-options", json=payload)
    assert response.status_code == 422 or response.status_code == 400


# ---------------------------------------------------------------------------
# 5. MISSING MARKET DATA AND USER-QUOTE SCENARIOS
# ---------------------------------------------------------------------------
def test_missing_market_data_requires_user_quote_and_labels_no_forecast(db_session: Session):
    """
    Missing observations must not become a hard-coded market price. An explicit
    user quote can still support a clearly labelled cost-only scenario.
    """
    req = ComprehensiveDecisionRequest(
        commodity="UncommonCrop",
        market="RemoteMandi",
        quantity=50.0,
        quantity_unit="quintal",
    )
    with pytest.raises(ValueError, match="No market observation is available"):
        DecisionService.evaluate_comprehensive_decision(db_session, req)

    req.current_price_override = 2400.0
    res = DecisionService.evaluate_comprehensive_decision(db_session, req)
    assert res.current_observed_modal_price is None
    assert res.effective_selling_price_now == 2400.0
    assert res.data_source == "USER_PROVIDED_PRICE"
    assert "No market observation was available" in " ".join(res.decision_caveats)
    assert res.wait.expected_price_per_qtl == 2400.0
    assert "forecast unavailable" in res.wait.price_basis_type.lower()
    assert any("no fitted forecast" in warning.lower() for warning in res.wait.warnings)


def test_decision_api_returns_explicit_error_when_no_market_price_is_available():
    response = client.post(
        "/api/decision/evaluate-options",
        json={"commodity": "NoSuchCrop", "market": "NoSuchMarket", "quantity": 10},
    )
    assert response.status_code == 400
    assert "No market observation is available" in response.json()["detail"]


def test_legacy_decision_does_not_invent_confidence_and_uses_crop_storage_profile():
    response = client.post(
        "/api/decision/evaluate",
        json={
            "commodity": "Onion",
            "market": "Lasalgaon",
            "current_quantity_qtl": 10,
            "holding_facility": "ambient",
        },
    )
    assert response.status_code == 200
    assert response.json()["confidence_score"] is None
    assert response.json()["safe_storage_limit_days"] == DecisionService.get_crop_profile("Onion")["safe_ambient_days"]


# ---------------------------------------------------------------------------
# 6. MISSING COST ESTIMATES APPLY DEFAULTS
# ---------------------------------------------------------------------------
def test_missing_cost_estimates_defaults(db_session: Session):
    """
    Verifies that when the user leaves custom storage rent and shrinkage empty (None),
    the system automatically applies standard empirical crop profile defaults.
    """
    req = ComprehensiveDecisionRequest(
        commodity="Wheat",
        market="Khanna",
        quantity=100.0,
        quantity_unit="quintal",
        user_monthly_storage_rent_qtl=None,
        user_spoilage_monthly_pct=None,
    )
    res = DecisionService.evaluate_comprehensive_decision(db_session, req)
    profile = DecisionService.get_crop_profile("Wheat")

    # Wheat default shrinkage is 0.8%/mo
    assert res.store.spoilage_loss_pct == profile["monthly_shrinkage_pct"]
    # Check storage cost item reflects default rent of 25 ₹/Qtl/mo
    rent_item = next(item for item in res.store.cost_items if "Storage Rent" in item.name)
    assert "₹25" in rent_item.unit_basis


# ---------------------------------------------------------------------------
# 7. INSUFFICIENT STORAGE INFORMATION & PERISHABILITY
# ---------------------------------------------------------------------------
def test_insufficient_storage_information_and_perishability(db_session: Session):
    """
    STRICT REQUIREMENT: Do not recommend storing perishable crops unless
    the user indicates that suitable cold storage is available.
    """
    req_ambient_tomato = ComprehensiveDecisionRequest(
        commodity="Tomato",
        market="Kolar",
        quantity=50.0,
        quantity_unit="quintal",
        storage_facility="ambient",  # Inappropriate for highly perishable tomato
    )
    res = DecisionService.evaluate_comprehensive_decision(db_session, req_ambient_tomato)

    # Must NOT recommend Store for ambient tomato
    assert "STORE" not in res.recommended_option
    assert res.store.risk_level == "Critical"
    assert any("perishable" in w.lower() for w in res.store.warnings)


# ---------------------------------------------------------------------------
# 8. RANKING MARKETS BY ESTIMATED NET RETURN
# ---------------------------------------------------------------------------
def test_ranking_markets_by_estimated_net_return(db_session: Session):
    """
    STRICT REQUIREMENT: Rank markets using estimated net return rather than
    simply choosing the highest quoted price.
    """
    req = MarketComparisonRequest(
        commodity="Onion",
        quantity=100.0,
        quantity_unit="quintal",
        reference_market="Lasalgaon",
        transport_cost_per_km_qtl=2.5,  # Higher transport rate highlights freight penalty
    )
    res = DecisionService.compare_markets_intelligently(db_session, req)

    assert len(res.ranked_markets) > 0
    # Check that items are strictly sorted descending by estimated_net_return
    for i in range(len(res.ranked_markets) - 1):
        assert res.ranked_markets[i].estimated_net_return >= res.ranked_markets[i + 1].estimated_net_return
        assert res.ranked_markets[i].rank_by_net_return == i + 1


# ---------------------------------------------------------------------------
# 9. FORECAST UNCERTAINTY WARNINGS & DOWNSIDE RISK
# ---------------------------------------------------------------------------
def test_forecast_uncertainty_warnings(db_session: Session):
    """
    Validates that holdout uncertainty lower bounds are evaluated and that
    downside risk warnings are issued when holdout errors could flip the recommendation.
    """
    req = ComprehensiveDecisionRequest(
        commodity="Onion",
        market="Lasalgaon",
        quantity=100.0,
        quantity_unit="quintal",
    )
    res = DecisionService.evaluate_comprehensive_decision(db_session, req)

    assert res.wait.uncertainty_lower_bound_price is not None
    assert res.wait.uncertainty_upper_bound_price is not None
    assert res.wait.uncertainty_lower_bound_price < res.wait.expected_price_per_qtl
    assert res.wait.uncertainty_upper_bound_price > res.wait.expected_price_per_qtl
    assert res.wait.uncertainty_downside_net_return is not None
    assert len(res.uncertainty_impact_analysis) > 20


# ---------------------------------------------------------------------------
# 10. PREVENTION OF DOUBLE-COUNTED COSTS
# ---------------------------------------------------------------------------
def test_prevention_of_double_counted_costs(db_session: Session):
    """
    Validates that transit freight is charged only once at delivery, and storage
    rent does not duplicate transport or capital opportunity costs.
    """
    req = ComprehensiveDecisionRequest(
        commodity="Onion",
        market="Lasalgaon",
        quantity=100.0,
        quantity_unit="quintal",
        transport_distance_km=15.0,
        transport_cost_per_km_qtl=1.5,
    )
    res = DecisionService.evaluate_comprehensive_decision(db_session, req)

    # Store total deductions must equal sum of distinct cost components
    expected_sum = (
        res.store.storage_cost_total
        + res.store.capital_opportunity_cost
        + res.store.transport_cost_total
        + res.store.other_costs_total
    )
    assert abs(res.store.total_deductions - expected_sum) < 0.05
    expected_store_freight = (
        0.0
        + res.store.remaining_quantity_qtl
        * 15.0
        * 1.5
    )
    assert res.store.transport_cost_total == round(expected_store_freight, 2)


# ---------------------------------------------------------------------------
# 11. WHAT-IF SIMULATOR WITH SCENARIO ADJUSTMENTS
# ---------------------------------------------------------------------------
def test_what_if_simulator_scenarios():
    """
    Tests the interactive what-if calculator with user-provided parameters,
    verifying breakeven future price and explicit hypothetical scenario label.
    """
    req = WhatIfSimulationRequest(
        commodity="Onion",
        current_price=2200.0,
        expected_future_price=2600.0,
        holding_days=30,
        quantity_qtl=100.0,
        monthly_storage_rent_qtl=50.0,
        monthly_shrinkage_pct=4.0,
        annual_interest_rate_pct=7.0,
        transport_cost_per_km_qtl=1.5,
        distance_km=15.0,
        fixed_transport_fee=300.0,
    )
    res = DecisionService.simulate_what_if(req)

    assert res.quantity_qtl == 100.0
    assert res.future_weight_after_shrinkage_qtl == 96.0  # 4% shrinkage
    assert res.breakeven_future_price > req.current_price
    assert "HYPOTHETICAL SIMULATION" in res.scenario_disclaimer
    assert res.absolute_profit_difference == round(res.future_net_revenue - res.immediate_net_revenue, 2)


# ---------------------------------------------------------------------------
# 12. FASTAPI ENDPOINTS INTEGRATION
# ---------------------------------------------------------------------------
def test_api_evaluate_options_endpoint():
    payload = {
        "commodity": "Onion",
        "market": "Lasalgaon",
        "quantity": 100.0,
        "quantity_unit": "quintal",
    }
    response = client.post("/api/decision/evaluate-options", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "sell_now" in data
    assert "wait" in data
    assert "store" in data
    assert "recommended_option" in data
    assert "key_sensitivity_drivers" in data


def test_api_compare_markets_endpoint():
    payload = {
        "commodity": "Onion",
        "quantity": 100.0,
        "quantity_unit": "quintal",
        "reference_market": "Lasalgaon",
    }
    response = client.post("/api/decision/compare-markets", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "ranked_markets" in data
    assert len(data["ranked_markets"]) > 0
    assert "arbitrage_insight" in data
