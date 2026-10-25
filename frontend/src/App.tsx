import React, { useState, useEffect, useCallback } from "react";
import { Sidebar } from "./components/Sidebar";
import { Header } from "./components/Header";
import { OverviewPage } from "./pages/OverviewPage";
import { PriceAnalysisPage } from "./pages/PriceAnalysisPage";
import { ForecastingPage } from "./pages/ForecastingPage";
import { MarketComparisonPage } from "./pages/MarketComparisonPage";
import { DecisionSupportPage } from "./pages/DecisionSupportPage";
import { ModelValidationPage } from "./pages/ModelValidationPage";
import { DataSourcesPage } from "./pages/DataSourcesPage";
import { api } from "./services/api";
import {
  HealthResponse,
  FilterOptions,
  MarketSummary,
  MarketObservation,
  ForecastResponse,
  ForecastModelPreference,
  DecisionRecommendation,
} from "./types";
import { AlertCircle, RefreshCw } from "lucide-react";

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>("overview");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [filterOptions, setFilterOptions] = useState<FilterOptions>({
    commodities: ["Onion", "Wheat", "Tomato", "Potato", "Cotton"],
    states: ["Maharashtra", "Punjab", "Karnataka", "Uttar Pradesh", "Gujarat"],
    markets: ["Lasalgaon", "Khanna", "Kolar", "Agra", "Rajkot"],
  });

  const [selectedCommodity, setSelectedCommodity] = useState<string>("Onion");
  const [selectedMarket, setSelectedMarket] = useState<string>("Lasalgaon");

  const [summary, setSummary] = useState<MarketSummary | null>(null);
  const [observations, setObservations] = useState<MarketObservation[]>([]);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [decision, setDecision] = useState<DecisionRecommendation | null>(null);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // 1. Initial Health & Filter Options Fetch
  const loadInitialContext = useCallback(async () => {
    try {
      const healthData = await api.getHealth();
      setHealth(healthData);

      const filters = await api.getFilters();
      if (filters.commodities.length > 0) {
        setFilterOptions(filters);
        if (!filters.commodities.includes(selectedCommodity)) {
          setSelectedCommodity(filters.commodities[0]);
        }
        if (!filters.markets.includes(selectedMarket)) {
          setSelectedMarket(filters.markets[0]);
        }
      }
    } catch (err: any) {
      console.warn("Backend connectivity check failed:", err.message);
      setHealth({
        status: "disconnected",
        app_name: "Agricultural Market Price Forecasting & Decision Support System",
        version: "1.0.0",
        timestamp: new Date().toISOString(),
        database_connected: false,
        total_observations: 0,
        total_forecasts: 0,
      });
    }
  }, [selectedCommodity, selectedMarket]);

  // 2. Fetch Market Data, Forecasts, and Decision for selected Commodity & Market
  const loadMarketAnalytics = useCallback(async () => {
    if (!selectedCommodity || !selectedMarket) return;
    setIsLoading(true);
    setErrorMessage(null);
    setSummary(null);
    setObservations([]);
    setForecast(null);
    setDecision(null);

    try {
      // Parallel requests for optimal load performance
      const [summaryRes, obsRes, forecastRes, decisionRes] = await Promise.allSettled([
        api.getSummary(selectedCommodity, selectedMarket),
        api.getObservations({ commodity: selectedCommodity, market: selectedMarket, limit: 100 }),
        api.getForecast(selectedCommodity, selectedMarket, 30, "auto"),
        api.evaluateDecision({
          commodity: selectedCommodity,
          market: selectedMarket,
          currentQuantityQtl: 100,
        }),
      ]);

      const failedLoads: string[] = [];
      if (summaryRes.status === "fulfilled") {
        setSummary(summaryRes.value);
      } else {
        setSummary(null);
        failedLoads.push("market summary");
      }
      if (obsRes.status === "fulfilled") {
        setObservations(obsRes.value.data);
      } else {
        setObservations([]);
        failedLoads.push("market observations");
      }
      if (forecastRes.status === "fulfilled") {
        setForecast(forecastRes.value);
      } else {
        setForecast(null);
        failedLoads.push("forecast");
      }
      if (decisionRes.status === "fulfilled") {
        setDecision(decisionRes.value);
      } else {
        setDecision(null);
        failedLoads.push("decision support");
      }
      if (failedLoads.length) {
        setErrorMessage(`Could not load ${failedLoads.join(", ")} for ${selectedCommodity} at ${selectedMarket}. Retry or check the backend connection.`);
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to load market intelligence data.");
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [selectedCommodity, selectedMarket]);

  useEffect(() => {
    loadInitialContext();
  }, [loadInitialContext]);

  useEffect(() => {
    loadMarketAnalytics();
  }, [loadMarketAnalytics]);

  const handleRefresh = () => {
    setIsRefreshing(true);
    loadMarketAnalytics();
  };

  const handleCustomForecast = async (model: ForecastModelPreference, horizon: number) => {
    setIsLoading(true);
    try {
      const res = await api.getForecast(selectedCommodity, selectedMarket, horizon, model);
      setForecast(res);
    } catch (err: any) {
      setErrorMessage(`Forecast generation error: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <Sidebar
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        systemStatus={health?.status || "disconnected"}
      />

      {/* Main Content Area */}
      <div className="main-content">
        <Header
          currentTab={activeTab}
          selectedCommodity={selectedCommodity}
          selectedMarket={selectedMarket}
          filterOptions={filterOptions}
          onCommodityChange={setSelectedCommodity}
          onMarketChange={setSelectedMarket}
          onRefresh={handleRefresh}
          isRefreshing={isRefreshing}
        />

        <main className="page-body">
          {errorMessage && (
            <div
              style={{
                marginBottom: "20px",
                padding: "12px 18px",
                borderRadius: "var(--radius-sm)",
                background: "rgba(239, 68, 68, 0.12)",
                border: "1px solid rgba(239, 68, 68, 0.3)",
                color: "var(--rose-500)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                fontSize: "0.85rem",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <AlertCircle size={16} />
                <span>{errorMessage}</span>
              </div>
              <button
                className="btn btn-secondary"
                onClick={handleRefresh}
                style={{ padding: "4px 10px", fontSize: "0.75rem" }}
              >
                Retry
              </button>
            </div>
          )}

          {activeTab === "overview" && (
            <OverviewPage
              summary={summary}
              observations={observations}
              forecast={forecast}
              decision={decision}
              isLoading={isLoading}
              onNavigateTab={setActiveTab}
            />
          )}

          {activeTab === "price_analysis" && (
            <PriceAnalysisPage
              observations={observations}
              summary={summary}
              filterOptions={filterOptions}
              isLoading={isLoading}
              onNavigateTab={setActiveTab}
            />
          )}

          {activeTab === "forecasting" && (
            <ForecastingPage
              forecast={forecast}
              observations={observations}
              isLoading={isLoading}
              onRefreshForecast={handleCustomForecast}
            />
          )}

          {activeTab === "market_comparison" && (
            <MarketComparisonPage
              selectedCommodity={selectedCommodity}
              selectedMarket={selectedMarket}
            />
          )}

          {activeTab === "decision_support" && (
            <DecisionSupportPage
              decision={decision}
              selectedCommodity={selectedCommodity}
              selectedMarket={selectedMarket}
              isLoading={isLoading}
            />
          )}

          {activeTab === "model_validation" && (
            <ModelValidationPage
              forecast={forecast}
              selectedCommodity={selectedCommodity}
              selectedMarket={selectedMarket}
              filterOptions={filterOptions}
            />
          )}

          {activeTab === "data_sources" && (
            <DataSourcesPage
              health={health}
              onDataImported={() => {
                loadInitialContext();
                loadMarketAnalytics();
              }}
            />
          )}
        </main>
      </div>
    </div>
  );
};

export default App;
