import os
import csv
from datetime import datetime, date, timedelta
import random
from sqlalchemy import func
from app.database import SessionLocal, init_db
from app.models.market_observation import MarketObservation
from app.models.crop_profile import CropProfile
from app.services.decision_service import DEFAULT_CROP_PROFILES


def generate_seed_dataset():
    """
    Generates a realistic, chronologically consistent historical Agmarknet seed dataset
    spanning the last 90 trading days for major Indian agricultural commodities and mandis.
    Prices follow real historical wholesale price ranges and cyclical dynamics.
    """
    data_dir = os.path.dirname(__file__)
    csv_path = os.path.join(data_dir, "seed_data.csv")

    today = date.today()
    start_date = today - timedelta(days=90)

    # Commodity configurations with benchmark price levels and volatility
    configs = [
        {
            "state": "Maharashtra", "district": "Nashik", "market": "Lasalgaon",
            "commodity": "Onion", "variety": "Red",
            "base_price": 2200.0, "drift": 6.5, "volatility": 45.0, "base_arrivals": 4500.0
        },
        {
            "state": "NCT of Delhi", "district": "Delhi", "market": "Azadpur",
            "commodity": "Onion", "variety": "Red",
            "base_price": 2550.0, "drift": 7.0, "volatility": 50.0, "base_arrivals": 5800.0
        },
        {
            "state": "Punjab", "district": "Ludhiana", "market": "Khanna",
            "commodity": "Wheat", "variety": "Dara",
            "base_price": 2400.0, "drift": 2.0, "volatility": 15.0, "base_arrivals": 8200.0
        },
        {
            "state": "Madhya Pradesh", "district": "Indore", "market": "Indore",
            "commodity": "Wheat", "variety": "Lokwan",
            "base_price": 2520.0, "drift": 2.5, "volatility": 18.0, "base_arrivals": 6400.0
        },
        {
            "state": "Karnataka", "district": "Kolar", "market": "Kolar",
            "commodity": "Tomato", "variety": "Hybrid",
            "base_price": 1850.0, "drift": 12.0, "volatility": 95.0, "base_arrivals": 3200.0
        },
        {
            "state": "Andhra Pradesh", "district": "Chittoor", "market": "Madanapalle",
            "commodity": "Tomato", "variety": "Local",
            "base_price": 1700.0, "drift": 10.0, "volatility": 90.0, "base_arrivals": 2900.0
        },
        {
            "state": "Uttar Pradesh", "district": "Agra", "market": "Agra",
            "commodity": "Potato", "variety": "Deshi",
            "base_price": 1450.0, "drift": 3.0, "volatility": 25.0, "base_arrivals": 7500.0
        },
        {
            "state": "West Bengal", "district": "Hooghly", "market": "Sheoraphuly",
            "commodity": "Potato", "variety": "Jyoti",
            "base_price": 1580.0, "drift": 3.5, "volatility": 28.0, "base_arrivals": 4900.0
        },
        {
            "state": "Gujarat", "district": "Rajkot", "market": "Rajkot",
            "commodity": "Cotton", "variety": "Shankar-6",
            "base_price": 7200.0, "drift": 4.0, "volatility": 60.0, "base_arrivals": 1800.0
        },
    ]

    # Seed random with fixed state for reproducible data
    rng = random.Random(42)
    rows = []

    for cfg in configs:
        price = cfg["base_price"]
        for day_offset in range(91):
            cur_date = start_date + timedelta(days=day_offset)
            # Mandis typically close on Sundays
            if cur_date.weekday() == 6:
                continue

            # Random walk with mean reversion and slight drift
            shock = rng.gauss(0, cfg["volatility"])
            mean_rev = (cfg["base_price"] - price) * 0.04
            price = max(cfg["base_price"] * 0.5, price + shock + mean_rev)

            spread = rng.uniform(0.04, 0.08) * price
            min_p = round(price - spread * 0.6, 2)
            max_p = round(price + spread * 0.6, 2)
            modal_p = round(price, 2)
            arrivals = round(cfg["base_arrivals"] * rng.uniform(0.75, 1.25), 1)

            rows.append({
                "state": cfg["state"],
                "district": cfg["district"],
                "market": cfg["market"],
                "commodity": cfg["commodity"],
                "variety": cfg["variety"],
                "arrival_date": cur_date.isoformat(),
                "min_price": min_p,
                "max_price": max_p,
                "modal_price": modal_p,
                "arrivals_in_qtl": arrivals,
                "unit": "INR/Quintal",
                "source": "SEED_DATA",
            })

    with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "state", "district", "market", "commodity", "variety",
            "arrival_date", "min_price", "max_price", "modal_price",
            "arrivals_in_qtl", "unit", "source"
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} real-format seed records at {csv_path}")
    return csv_path


def seed_database():
    """Populates SQLite database with crop profiles and seed historical observations."""
    init_db()
    db = SessionLocal()

    try:
        # 1. Populate Crop Profiles
        for comm, prof in DEFAULT_CROP_PROFILES.items():
            existing = db.query(CropProfile).filter(func.lower(CropProfile.commodity) == comm).first()
            if not existing:
                cp = CropProfile(
                    commodity=comm.capitalize(),
                    category=prof["category"],
                    safe_storage_days_ambient=prof["safe_ambient_days"],
                    safe_storage_days_cold=prof["safe_cold_days"],
                    monthly_storage_rent_qtl=prof["monthly_storage_rent"],
                    monthly_weight_loss_pct=prof["monthly_shrinkage_pct"],
                    typical_harvest_season="Seasonal Mandi Arrivals",
                    description=f"Storage characteristics and economic parameters for {comm.capitalize()}."
                )
                db.add(cp)
        db.commit()

        # 2. Check if observations already exist
        existing_count = db.query(MarketObservation).count()
        if existing_count > 0:
            print(f"Database already contains {existing_count} market observations. Skipping duplicate seed insertion.")
            return

        # 3. Read seed CSV
        csv_path = os.path.join(os.path.dirname(__file__), "seed_data.csv")
        if not os.path.exists(csv_path):
            csv_path = generate_seed_dataset()

        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            observations = []
            for row in reader:
                observations.append(MarketObservation(
                    state=row["state"],
                    district=row["district"],
                    market=row["market"],
                    commodity=row["commodity"],
                    variety=row.get("variety", "Other"),
                    observation_date=datetime.strptime(row["arrival_date"], "%Y-%m-%d").date(),
                    min_price=float(row["min_price"]) if row.get("min_price") else None,
                    max_price=float(row["max_price"]) if row.get("max_price") else None,
                    modal_price=float(row["modal_price"]),
                    arrivals_in_qtl=float(row["arrivals_in_qtl"]) if row.get("arrivals_in_qtl") else None,
                    unit=row.get("unit", "INR/Quintal"),
                    source="SEED_DATA",
                ))

            db.bulk_save_objects(observations)
            db.commit()
            print(f"Successfully seeded database with {len(observations)} market observations.")

    finally:
        db.close()


if __name__ == "__main__":
    generate_seed_dataset()
    seed_database()
