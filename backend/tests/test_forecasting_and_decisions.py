import math
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_forecast_endpoint_generates_real_metrics():
    response = client.get("/api/forecasts?commodity=Onion&market=Lasalgaon&horizon_days=15")
    assert response.status_code == 200
    data = response.json()
    assert data["commodity"] == "Onion"
    assert data["market"] == "Lasalgaon"
    assert data["is_sufficient_data"] is True
    assert len(data["forecasts"]) == 15
    # Check that real holdout metrics were calculated
    assert data["metrics"] is not None
    assert data["metrics"]["mae"] >= 0
    assert data["metrics"]["rmse"] >= 0
    assert data["metrics"]["mape"] >= 0
    assert data["model_used"] != "None"
    assert data["metrics"]["model_name"]
    assert all(
        isinstance(point[field], (int, float)) and math.isfinite(point[field])
        for point in data["forecasts"]
        for field in ("predicted_price", "lower_ci_80", "upper_ci_80", "lower_ci_95", "upper_ci_95")
    )


def test_forecast_endpoint_rejects_unimplemented_model_preferences():
    for unsupported in ("sarimax", "ridge-lag"):
        response = client.get(
            f"/api/forecasts?commodity=Onion&market=Lasalgaon&model={unsupported}"
        )
        assert response.status_code == 422


def test_decision_evaluation_endpoint():
    payload = {
        "commodity": "Onion",
        "market": "Lasalgaon",
        "current_quantity_qtl": 100.0,
        "holding_facility": "ambient",
        "transport_distance_km": 15.0
    }
    response = client.post("/api/decision/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["recommended_action"] in ["SELL NOW", "WAIT (3-7 Days)", "STORE (15-30 Days)"]
    assert len(data["horizons"]) == 3


def test_what_if_simulation_endpoint():
    payload = {
        "commodity": "Wheat",
        "current_price": 2400.0,
        "expected_future_price": 2700.0,
        "holding_days": 30,
        "quantity_qtl": 200.0,
        "monthly_storage_rent_qtl": 25.0,
        "monthly_shrinkage_pct": 0.8,
        "annual_interest_rate_pct": 7.0,
        "transport_cost_per_km_qtl": 1.5,
        "distance_km": 15.0
    }
    response = client.post("/api/decision/what-if", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "future_net_revenue" in data
    assert "absolute_profit_difference" in data
    assert "verdict" in data
