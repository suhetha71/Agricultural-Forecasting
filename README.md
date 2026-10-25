# Agricultural Market Price Forecasting & Decision Support System

An end-to-end, production-grade agricultural market intelligence platform designed to forecast agricultural commodity wholesale prices and assist farmers and traders in making data-driven **Sell, Wait, or Store** post-harvest decisions.

---

## 🌾 Project Highlights

* **Exact Title**: Agricultural Market Price Forecasting & Decision Support System
* **Data Sources**: Supports Agmarknet-compatible CSV imports, optional `data.gov.in` synchronization, and generated demonstration data. The bundled generated data is not verified ground-truth market data.
* **Forecasting Architecture**: Real empirical time-series models (Holt-Winters Triple Exponential Smoothing, Auto-Regressive SARIMAX, and dynamic momentum trend baselines) with 80% and 95% compound confidence intervals.
* **Model Validation Transparency**: Walk-forward holdout backtesting computing real Mean Absolute Error (MAE), Root Mean Squared Error (RMSE), Mean Absolute Percentage Error (MAPE), and Directional Accuracy. Zero mock or fabricated metrics.
* **Decision Support & Simulation Engine**: Formulates post-harvest storage economics incorporating warehouse/cold storage rent, crop-specific moisture loss/shrinkage rates, cost of capital, and transport costs to evaluate whether holding stock yields a net positive return.
* **Regional Mandi Arbitrage**: Compares modal prices across neighboring markets and ranks mandis by net farmer realization after freight logistics costs.

---

## 🏗️ Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | React 19, TypeScript, Vite, Modern Responsive Glassmorphism CSS, Lucide Icons |
| **Backend** | Python 3.12, FastAPI, Uvicorn, Pydantic v2 |
| **Database** | SQLite via SQLAlchemy 2.0 ORM (with uniqueness constraints for deduplication) |
| **Data & Math** | Pandas, NumPy, SciPy, Statsmodels, Scikit-Learn |
| **Testing** | Pytest, TestClient |

---

## 🚀 Windows Setup & Run Guide

### 1. Prerequisites
Ensure you have the following installed on Windows:
* **Python 3.12+**
* **Node.js v20+** and **npm**
* **Git**

---

### 2. Backend Setup & Run

Open a **PowerShell** terminal in the project directory:

```powershell
# Navigate to backend
cd c:\Users\HAPPY\Agricultural_Forecasting\backend

# Install Python dependencies (if not already installed)
pip install -r requirements.txt

# Seed the database with generated demonstration observations (not verified market data)
python -m app.data.seed_db

# Run automated tests to verify database and model endpoints
python -m pytest tests/

# Launch the FastAPI backend server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The backend will be live at:
* **API Root**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
* **Interactive Swagger Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **Health Endpoint**: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

---

### 3. Frontend Setup & Run

Open a second **PowerShell** terminal:

```powershell
# Navigate to frontend
cd c:\Users\HAPPY\Agricultural_Forecasting\frontend

# Install dependencies (already prepared)
npm install

# Build the production bundle to verify TypeScript
npm run build

# Start the Vite development server
npm run dev
```

The frontend will be live at:
* **Dashboard URL**: [http://localhost:5173](http://localhost:5173)

---

## 📊 Application Navigation Modules

1. **Overview**: High-level executive dashboard showing active commodity modal rates, 7-day momentum, 30-day spreads, interactive price chart, and active decision engine alert banner.
2. **Price Analysis**: Chronological historical prices, min/max spreads, arrival volumes in quintals, search filter, and authenticated transaction records table.
3. **Forecasting**: 7-day, 15-day, and 30-day projection trajectories with 80% and 95% confidence intervals, and model architecture selection.
4. **Market Comparison**: Cross-mandi pricing matrix, freight transport slider (₹/km/Qtl), and net realization rankings.
5. **Decision Support**: Algorithmic Sell vs. Wait vs. Store recommendations, storage duration risk assessments, and interactive **What-If Profit Simulator**.
6. **Model Validation**: Transparent walk-forward holdout backtest metrics (MAE, RMSE, MAPE, Directional Accuracy), training/testing windows, and validation methodology.
7. **Data Sources**: AGMARKNET / data.gov.in integration status and CSV file uploader with automatic duplicate avoidance.

---

## 🧪 Testing & Verification

Run the test suite at any time from the `backend/` folder:

```powershell
python -m pytest tests/ -v
```

All 9 test cases cover:
* Root operational status
* Health endpoint and database connectivity
* Multi-mandi query and summary endpoints
* Deduplication of imported CSV observations
* Empirical time-series forecast generation with holdout error calculations
* Sell/Wait/Store recommendation generation
* What-If simulation financial calculations

## Bundled CSV Data

`backend/app/data/seed_data.csv` contains generated demonstration data. The generator in `backend/app/data/seed_db.py` uses a fixed random seed, configured benchmark prices and arrival volumes, and a random-walk process over a recent date range (excluding Sundays). These values are synthetic examples and are **not verified ground-truth market observations**.

`backend/app/data/official_agmarknet_october_2026.csv` is an optional local CSV containing aggregate market fields. It is excluded from this Git repository because the project has no source URL, publisher metadata, download date, or license information for it; its provenance and applicable redistribution rights must be confirmed before it is shared. Do not describe it as sourced from `data.gov.in` or as verified official data without that confirmation. The ingestion test uses the file when it is present locally and skips with an explanation when it is absent.

## Government Market-Price API Sync

The backend reads the optional `DATA_GOV_IN_API_KEY` setting from `backend/.env` or the process environment. The Data Sources page also accepts a key for one sync request and sends it to this application in the request body; it is not placed in the application's URL. Do not commit `.env` files or share API keys in source code.

The sync requests JSON pages with `limit` and `offset`, up to five pages per run and at most 500 rows per page. A capped run reports `pagination_truncated` and its available/fetched row counts. `imported_count` means new observations, `updated_count` means existing values changed and a revision was saved, `duplicate_count` means unchanged rows, `skipped_count` means invalid provider rows, and `fetched_count` means raw rows returned in this sync. Government, user CSV, and demo records use separate source labels. Live API access must be verified with an authorized request; mocked tests do not establish provider connectivity.

## Historical Weather Context

Price Analysis retrieves daily maximum/minimum temperature and precipitation for supported market/district coordinates from the [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api), using ERA5 reanalysis. The values are gridded reanalysis aligned by date with market observations; they are not on-site weather-station measurements. Coordinates in the application are approximate market/district metadata. Weather values are optional context only; the application does not calculate a price-weather correlation or claim causal impact. Successful requests are cached in memory for six hours and provider failures for one minute. The public free API is for non-commercial use, and weather data requires Open-Meteo attribution under CC BY 4.0; commercial deployment must use an appropriately licensed service. See [Open-Meteo terms](https://open-meteo.com/en/terms).
