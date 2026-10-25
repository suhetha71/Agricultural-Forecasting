from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.market_observation import MarketObservation
from app.services.market_service import MarketService

client = TestClient(app)


def test_database_has_seeded_observations():
    db = SessionLocal()
    try:
        count = db.query(MarketObservation).count()
        assert count >= 700, f"Expected at least 700 observations, got {count}"
    finally:
        db.close()


def test_market_filters_endpoint():
    response = client.get("/api/market/filters")
    assert response.status_code == 200
    data = response.json()
    assert "Onion" in data["commodities"]
    assert "Wheat" in data["commodities"]
    assert "Lasalgaon" in data["markets"]


def test_market_summary_endpoint():
    response = client.get("/api/market/summary?commodity=Onion&market=Lasalgaon")
    assert response.status_code == 200
    data = response.json()
    assert data["commodity"] == "Onion"
    assert data["market"] == "Lasalgaon"
    assert data["latest_modal_price"] > 0
    assert data["total_records"] > 0


def test_csv_import_deduplication():
    db = SessionLocal()
    try:
        csv_sample = """State,District,Market,Commodity,Variety,Arrival_Date,Min_Price,Max_Price,Modal_Price,Arrivals_in_qtl
Maharashtra,Nashik,Lasalgaon,Onion,Red,2026-01-01,1500,2000,1800,2500
"""
        # First import
        res1 = MarketService.import_csv_records(db, csv_sample, source_label="TEST_IMPORT")
        assert res1.success is True

        # Second import with the exact same row should be marked as duplicate
        res2 = MarketService.import_csv_records(db, csv_sample, source_label="TEST_IMPORT")
        assert res2.success is True
        assert res2.duplicate_count == 1
        assert res2.imported_count == 0
    finally:
        db.close()
