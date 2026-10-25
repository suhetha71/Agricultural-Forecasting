import React, { useState, useEffect, useMemo, useCallback } from "react";
import {
  ForecastResponse,
  ModelExplanationResponse,
  ForecastUncertaintyResponse,
  BacktestEvaluationResponse,
  PredictionActualRecord,
  FilterOptions,
  ForecastModelPreference,
} from "../types";
import { api } from "../services/api";
import {
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Sliders,
  Calendar,
  Layers,
  HelpCircle,
  AlertTriangle,
  TrendingUp,
  BrainCircuit,
  Info,
  RefreshCw,
  BarChart2,
  Filter,
  Scale,
  Target,
  Database,
  ArrowUpRight,
  ArrowDownRight,
  Activity,
  Award,
} from "lucide-react";

interface ModelValidationPageProps {
  forecast: ForecastResponse | null;
  selectedCommodity: string;
  selectedMarket: string;
  filterOptions?: FilterOptions | null;
}

export const ModelValidationPage: React.FC<ModelValidationPageProps> = ({
  forecast,
  selectedCommodity,
  selectedMarket,
  filterOptions,
}) => {
  // Navigation sub-tabs
  const [activeSubTab, setActiveSubTab] = useState<"backtest" | "explainability" | "uncertainty">("backtest");

  // Filtering state
  const [currCommodity, setCurrCommodity] = useState<string>(selectedCommodity || "Onion");
  const [currMarket, setCurrMarket] = useState<string>(selectedMarket || "Lasalgaon");
  const [selectedHorizon, setSelectedHorizon] = useState<number | "ALL">("ALL");
  const [selectedModel, setSelectedModel] = useState<ForecastModelPreference>("auto");
  const [availabilityMode, setAvailabilityMode] = useState<"point_in_time" | "retrospective">("point_in_time");
  const [recordTypeFilter, setRecordTypeFilter] = useState<"ALL" | "WALK_FORWARD_BACKTEST" | "SAVED_LIVE_FORECAST">("ALL");

  // Data state
  const [backtest, setBacktest] = useState<BacktestEvaluationResponse | null>(null);
  const [explanation, setExplanation] = useState<ModelExplanationResponse | null>(null);
  const [uncertainty, setUncertainty] = useState<ForecastUncertaintyResponse | null>(null);

  // Loading & status states
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isAuditingLive, setIsAuditingLive] = useState<boolean>(false);
  const [auditMessage, setAuditMessage] = useState<string | null>(null);
  const [recordsPage, setRecordsPage] = useState<number>(1);
  const recordsPerPage = 12;

  // Chart tooltip hover state
  const [hoveredPoint, setHoveredPoint] = useState<{
    date: string;
    actual: number;
    predicted: number;
    baseline: number;
    error: number;
    horizon: number;
    x: number;
    y: number;
  } | null>(null);

  // Sync props when parent changes
  useEffect(() => {
    if (selectedCommodity) setCurrCommodity(selectedCommodity);
    if (selectedMarket) setCurrMarket(selectedMarket);
  }, [selectedCommodity, selectedMarket]);

  // Available markets
  const availableMarkets = useMemo(() => {
    if (filterOptions?.markets && filterOptions.markets.length > 0) {
      return filterOptions.markets;
    }
    return [currMarket, "Lasalgaon", "Khanna", "Agra", "Azadpur", "Rajkot", "Kolar", "Jaipur"];
  }, [filterOptions, currMarket]);

  // Load backtest and diagnostic data
  const loadValidationData = useCallback(async () => {
    setIsLoading(true);
    setAuditMessage(null);
    try {
      const [btRes, expRes, uncertRes] = await Promise.allSettled([
        api.getHistoricalBacktest(currCommodity, currMarket, [7, 15, 30], selectedModel, true, availabilityMode),
        api.getModelExplainability(currCommodity, currMarket),
        api.getForecastUncertainty(currCommodity, currMarket),
      ]);

      if (btRes.status === "fulfilled") {
        setBacktest(btRes.value);
      }
      if (expRes.status === "fulfilled") {
        setExplanation(expRes.value);
      }
      if (uncertRes.status === "fulfilled") {
        setUncertainty(uncertRes.value);
      }
    } catch (err) {
      console.warn("Failed to load validation backtesting data:", err);
    } finally {
      setIsLoading(false);
    }
  }, [currCommodity, currMarket, selectedModel, availabilityMode]);

  useEffect(() => {
    loadValidationData();
  }, [loadValidationData]);

  // Handle Live Forecast Audit trigger
  const handleAuditSavedForecasts = async () => {
    setIsAuditingLive(true);
    setAuditMessage(null);
    try {
      const res = await api.evaluateSavedForecasts(currCommodity, currMarket);
      setAuditMessage(res.message);
      // Reload backtest after matching newly matured live records
      await loadValidationData();
    } catch (err: any) {
      setAuditMessage(err.message || "Failed to audit saved forecasts.");
    } finally {
      setIsAuditingLive(false);
    }
  };

  // Filtered prediction records for table and charts
  const filteredRecords = useMemo(() => {
    if (!backtest || !backtest.recent_prediction_records) return [];
    return backtest.recent_prediction_records.filter((rec) => {
      const matchHorizon = selectedHorizon === "ALL" || rec.horizon_days === selectedHorizon;
      const matchType = recordTypeFilter === "ALL" || rec.record_type === recordTypeFilter;
      return matchHorizon && matchType;
    });
  }, [backtest, selectedHorizon, recordTypeFilter]);

  // Filtered horizons summary
  const displayedHorizons = useMemo(() => {
    if (!backtest || !backtest.horizons) return [];
    if (selectedHorizon === "ALL") return backtest.horizons;
    return backtest.horizons.filter((h) => h.horizon_days === selectedHorizon);
  }, [backtest, selectedHorizon]);

  // Pagination for records table
  const paginatedRecords = useMemo(() => {
    const start = (recordsPage - 1) * recordsPerPage;
    return filteredRecords.slice(start, start + recordsPerPage);
  }, [filteredRecords, recordsPage]);

  const totalPages = Math.max(1, Math.ceil(filteredRecords.length / recordsPerPage));

  // Chart data calculations
  const chartPoints = useMemo(() => {
    if (filteredRecords.length === 0) return [];
    // Sort chronologically ascending for the time-series chart
    const sorted = [...filteredRecords].sort(
      (a, b) => new Date(a.target_date).getTime() - new Date(b.target_date).getTime()
    );

    // Group by target_date if multiple horizons evaluate to the same target date, taking average
    const dateMap = new Map<string, PredictionActualRecord>();
    sorted.forEach((item) => {
      if (!dateMap.has(item.target_date)) {
        dateMap.set(item.target_date, item);
      }
    });

    return Array.from(dateMap.values());
  }, [filteredRecords]);

  // Chart bounds & SVG coordinates
  const svgWidth = 860;
  const svgHeight = 280;
  const padding = { top: 25, right: 30, bottom: 40, left: 60 };
  const innerWidth = svgWidth - padding.left - padding.right;
  const innerHeight = svgHeight - padding.top - padding.bottom;

  const chartBounds = useMemo(() => {
    if (chartPoints.length === 0) return { minPrice: 0, maxPrice: 100, yRange: 100 };
    let minP = Infinity;
    let maxP = -Infinity;
    chartPoints.forEach((p) => {
      minP = Math.min(minP, p.actual_price, p.predicted_price, p.baseline_predicted_price);
      maxP = Math.max(maxP, p.actual_price, p.predicted_price, p.baseline_predicted_price);
    });
    // Add 8% buffer
    const buffer = Math.max(50, (maxP - minP) * 0.08);
    const minVal = Math.max(0, Math.floor((minP - buffer) / 50) * 50);
    const maxVal = Math.ceil((maxP + buffer) / 50) * 50;
    return {
      minPrice: minVal,
      maxPrice: maxVal,
      yRange: Math.max(1, maxVal - minVal),
    };
  }, [chartPoints]);

  const getYCoord = (val: number) => {
    const norm = (val - chartBounds.minPrice) / chartBounds.yRange;
    return padding.top + innerHeight - norm * innerHeight;
  };

  const getXCoord = (index: number, total: number) => {
    if (total <= 1) return padding.left + innerWidth / 2;
    return padding.left + (index / (total - 1)) * innerWidth;
  };

  // Generate SVG path strings
  const actualPathStr = useMemo(() => {
    if (chartPoints.length === 0) return "";
    return chartPoints
      .map((p, i) => `${i === 0 ? "M" : "L"} ${getXCoord(i, chartPoints.length).toFixed(1)} ${getYCoord(p.actual_price).toFixed(1)}`)
      .join(" ");
  }, [chartPoints, chartBounds]);

  const predPathStr = useMemo(() => {
    if (chartPoints.length === 0) return "";
    return chartPoints
      .map((p, i) => `${i === 0 ? "M" : "L"} ${getXCoord(i, chartPoints.length).toFixed(1)} ${getYCoord(p.predicted_price).toFixed(1)}`)
      .join(" ");
  }, [chartPoints, chartBounds]);

  const basePathStr = useMemo(() => {
    if (chartPoints.length === 0) return "";
    return chartPoints
      .map((p, i) => `${i === 0 ? "M" : "L"} ${getXCoord(i, chartPoints.length).toFixed(1)} ${getYCoord(p.baseline_predicted_price).toFixed(1)}`)
      .join(" ");
  }, [chartPoints, chartBounds]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      {/* Header Banner */}
      <div className="glass-card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
            <div
              style={{
                width: "44px",
                height: "44px",
                borderRadius: "12px",
                background: "rgba(16, 185, 129, 0.15)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--emerald-400)",
              }}
            >
              <ShieldCheck size={26} />
            </div>
            <div>
              <h3 style={{ fontSize: "1.15rem", fontWeight: 700, color: "var(--text-main)" }}>
                Forecast Accuracy &amp; Real Market Validation
              </h3>
              <p style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                Rigorous chronological walk-forward backtesting against actual APMC market prices with naive baseline benchmarking
              </p>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
            <span className="badge badge-emerald" style={{ display: "flex", alignItems: "center", gap: "5px", fontSize: "0.75rem" }}>
              <CheckCircle2 size={13} /> {availabilityMode === "point_in_time" ? "Availability-Filtered Backtest" : "Retrospective Demo · Not Point-in-Time Verified"}
            </span>
            <span className="badge badge-indigo" style={{ display: "flex", alignItems: "center", gap: "5px", fontSize: "0.75rem" }}>
              <Scale size={13} /> Naive Persistence Baseline (P_t+h = P_t)
            </span>
            <span className="badge badge-amber" style={{ display: "flex", alignItems: "center", gap: "5px", fontSize: "0.75rem" }}>
              <Target size={13} /> Empirical Error Calibration
            </span>
          </div>
        </div>

        {/* Sub-tab Navigation */}
        <div style={{ display: "flex", gap: "10px", marginTop: "20px", borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "16px" }}>
          <button
            className={`tab-btn ${activeSubTab === "backtest" ? "active" : ""}`}
            onClick={() => setActiveSubTab("backtest")}
            style={{
              padding: "8px 16px",
              borderRadius: "8px",
              fontSize: "0.85rem",
              fontWeight: 600,
              background: activeSubTab === "backtest" ? "rgba(16, 185, 129, 0.15)" : "transparent",
              color: activeSubTab === "backtest" ? "var(--emerald-400)" : "var(--text-muted)",
              border: activeSubTab === "backtest" ? "1px solid rgba(16, 185, 129, 0.3)" : "1px solid transparent",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "7px",
            }}
          >
            <BarChart2 size={16} /> Real Market Backtesting &amp; Accuracy
          </button>

          <button
            className={`tab-btn ${activeSubTab === "explainability" ? "active" : ""}`}
            onClick={() => setActiveSubTab("explainability")}
            style={{
              padding: "8px 16px",
              borderRadius: "8px",
              fontSize: "0.85rem",
              fontWeight: 600,
              background: activeSubTab === "explainability" ? "rgba(99, 102, 241, 0.15)" : "transparent",
              color: activeSubTab === "explainability" ? "var(--indigo-400)" : "var(--text-muted)",
              border: activeSubTab === "explainability" ? "1px solid rgba(99, 102, 241, 0.3)" : "1px solid transparent",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "7px",
            }}
          >
            <BrainCircuit size={16} /> Explainable ML &amp; SHAP Attributions
          </button>

          <button
            className={`tab-btn ${activeSubTab === "uncertainty" ? "active" : ""}`}
            onClick={() => setActiveSubTab("uncertainty")}
            style={{
              padding: "8px 16px",
              borderRadius: "8px",
              fontSize: "0.85rem",
              fontWeight: 600,
              background: activeSubTab === "uncertainty" ? "rgba(245, 158, 11, 0.15)" : "transparent",
              color: activeSubTab === "uncertainty" ? "var(--amber-400)" : "var(--text-muted)",
              border: activeSubTab === "uncertainty" ? "1px solid rgba(245, 158, 11, 0.3)" : "1px solid transparent",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "7px",
            }}
          >
            <Sliders size={16} /> Multi-Horizon Risk &amp; Uncertainty Spreads
          </button>
        </div>
      </div>

      {/* ======================================================== */}
      {/* SUB-TAB 1: REAL MARKET BACKTESTING & ACCURACY (MAIN)     */}
      {/* ======================================================== */}
      {activeSubTab === "backtest" && (
        <>
          {/* Controls & Filter Bar */}
          <div className="glass-card" style={{ padding: "16px 20px" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "14px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
                {/* Commodity Filter */}
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <span style={{ fontSize: "0.78rem", color: "var(--text-dim)", fontWeight: 600 }}>CROP:</span>
                  <select
                    className="select-input"
                    value={currCommodity}
                    onChange={(e) => {
                      setCurrCommodity(e.target.value);
                    }}
                    style={{ fontSize: "0.82rem", padding: "5px 10px" }}
                  >
                    {(filterOptions?.commodities || ["Onion", "Wheat", "Potato", "Tomato", "Cotton", "Mustard"]).map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>

                {/* Market Filter */}
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <span style={{ fontSize: "0.78rem", color: "var(--text-dim)", fontWeight: 600 }}>MANDI:</span>
                  <select
                    className="select-input"
                    value={currMarket}
                    onChange={(e) => setCurrMarket(e.target.value)}
                    style={{ fontSize: "0.82rem", padding: "5px 10px" }}
                  >
                    {availableMarkets.map((m) => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                </div>

                {/* Horizon Filter */}
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <span style={{ fontSize: "0.78rem", color: "var(--text-dim)", fontWeight: 600 }}>HORIZON:</span>
                  <select
                    className="select-input"
                    value={selectedHorizon}
                    onChange={(e) => setSelectedHorizon(e.target.value === "ALL" ? "ALL" : Number(e.target.value))}
                    style={{ fontSize: "0.82rem", padding: "5px 10px" }}
                  >
                    <option value="ALL">All Horizons (7d, 15d, 30d)</option>
                    <option value={7}>7-Day Short-Term</option>
                    <option value={15}>15-Day Mid-Term</option>
                    <option value={30}>30-Day Storage-Horizon</option>
                  </select>
                </div>

                {/* Model Architecture */}
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <span style={{ fontSize: "0.78rem", color: "var(--text-dim)", fontWeight: 600 }}>ALGORITHM:</span>
                  <select
                    className="select-input"
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value as ForecastModelPreference)}
                    style={{ fontSize: "0.82rem", padding: "5px 10px" }}
                  >
                    <option value="auto">Auto (by history length)</option>
                    <option value="holt-winters">Holt-Winters Triple Exponential (21+ observations)</option>
                  </select>
                </div>

                {/* Availability policy */}
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <span style={{ fontSize: "0.78rem", color: "var(--text-dim)", fontWeight: 600 }}>DATA MODE:</span>
                  <select
                    className="select-input"
                    value={availabilityMode}
                    onChange={(e) => setAvailabilityMode(e.target.value as "point_in_time" | "retrospective")}
                    style={{ fontSize: "0.82rem", padding: "5px 10px" }}
                  >
                    <option value="point_in_time">Strict Point-in-Time</option>
                    <option value="retrospective">Retrospective Demo (Unverified)</option>
                  </select>
                </div>

                {/* Record Origin Filter */}
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <span style={{ fontSize: "0.78rem", color: "var(--text-dim)", fontWeight: 600 }}>TYPE:</span>
                  <select
                    className="select-input"
                    value={recordTypeFilter}
                    onChange={(e) => setRecordTypeFilter(e.target.value as any)}
                    style={{ fontSize: "0.82rem", padding: "5px 10px" }}
                  >
                    <option value="ALL">All Prediction Pairs</option>
                    <option value="WALK_FORWARD_BACKTEST">Walk-Forward Backtests</option>
                    <option value="SAVED_LIVE_FORECAST">Saved Live Forecasts</option>
                  </select>
                </div>
              </div>

              {/* Action Buttons */}
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <button
                  className="btn btn-secondary"
                  onClick={handleAuditSavedForecasts}
                  disabled={isAuditingLive || isLoading}
                  style={{ fontSize: "0.8rem", padding: "6px 12px" }}
                  title="Scan genuine saved forecast records and match with matured actual market observations"
                >
                  <Activity size={14} className={isAuditingLive ? "spin" : ""} />
                  <span>{isAuditingLive ? "Auditing..." : "Audit Live Matches"}</span>
                </button>

                <button
                  className="btn btn-primary"
                  onClick={loadValidationData}
                  disabled={isLoading}
                  style={{ fontSize: "0.8rem", padding: "6px 14px" }}
                >
                  <RefreshCw size={14} className={isLoading ? "spin" : ""} />
                  <span>Run Backtest</span>
                </button>
              </div>
            </div>

            {/* Audit Status Message Banner */}
            {auditMessage && (
              <div
                style={{
                  marginTop: "12px",
                  padding: "8px 12px",
                  background: "rgba(16, 185, 129, 0.1)",
                  border: "1px solid rgba(16, 185, 129, 0.25)",
                  borderRadius: "6px",
                  fontSize: "0.8rem",
                  color: "var(--emerald-400)",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <CheckCircle2 size={15} />
                <span>{auditMessage}</span>
              </div>
            )}
            {backtest?.availability_note && (
              <div
                style={{
                  marginTop: "12px",
                  padding: "10px 12px",
                  background: backtest.availability_mode === "RETROSPECTIVE" ? "rgba(245, 158, 11, 0.08)" : "rgba(59, 130, 246, 0.08)",
                  border: `1px solid ${backtest.availability_mode === "RETROSPECTIVE" ? "rgba(245, 158, 11, 0.28)" : "rgba(59, 130, 246, 0.25)"}`,
                  borderRadius: "6px",
                  fontSize: "0.8rem",
                  color: "var(--text-muted)",
                  lineHeight: 1.5,
                }}
              >
                <strong>{backtest.availability_mode === "RETROSPECTIVE" ? "Retrospective result:" : "Availability policy:"}</strong>{" "}
                {backtest.availability_note}
              </div>
            )}
          </div>

          {/* Insufficient Data State */}
          {backtest && !backtest.is_sufficient_sample ? (
            <div
              className="glass-card"
              style={{
                padding: "36px",
                textAlign: "center",
                border: "1px solid rgba(245, 158, 11, 0.3)",
                background: "rgba(245, 158, 11, 0.04)",
              }}
            >
              <div
                style={{
                  width: "56px",
                  height: "56px",
                  borderRadius: "50%",
                  background: "rgba(245, 158, 11, 0.15)",
                  color: "var(--amber-400)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  margin: "0 auto 16px auto",
                }}
              >
                <AlertTriangle size={28} />
              </div>
              <h4 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#fff", marginBottom: "8px" }}>
                Insufficient Historical Observations for Reliable Walk-Forward Evaluation
              </h4>
              <p style={{ maxWidth: "620px", margin: "0 auto 16px auto", fontSize: "0.85rem", color: "var(--text-muted)", lineHeight: 1.6 }}>
                {backtest.insufficient_reason}
              </p>
              <div style={{ display: "inline-flex", gap: "16px", padding: "12px 20px", background: "rgba(0,0,0,0.3)", borderRadius: "8px", fontSize: "0.82rem" }}>
                <div>
                  <span style={{ color: "var(--text-dim)" }}>Available Records:</span>{" "}
                  <strong style={{ color: "var(--amber-400)" }}>{backtest.total_historical_records}</strong>
                </div>
                <div>
                  <span style={{ color: "var(--text-dim)" }}>Required Threshold:</span>{" "}
                  <strong style={{ color: "#fff" }}>20 eligible training dates</strong>
                </div>
                <div>
                  <span style={{ color: "var(--text-dim)" }}>Data Source:</span>{" "}
                  <strong style={{ color: "var(--emerald-400)" }}>Agmarknet ({backtest.market})</strong>
                </div>
              </div>
            </div>
          ) : backtest ? (
            <>
              {/* Backtest Overview Metrics Bar */}
              <div className="grid-cols-4">
                <div className="glass-card">
                  <span style={{ fontSize: "0.72rem", color: "var(--text-dim)", textTransform: "uppercase", fontWeight: 700 }}>
                    Total Matched Pairs
                  </span>
                  <div style={{ fontSize: "1.75rem", fontWeight: 800, color: "#fff", marginTop: "6px" }}>
                    {backtest.total_matched_predictions}
                    <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontWeight: 400, marginLeft: "6px" }}>
                      observations
                    </span>
                  </div>
                  <p style={{ fontSize: "0.74rem", color: "var(--text-dim)", marginTop: "4px" }}>
                    Verified genuine prediction-vs-actual pairs without missing data leakage.
                  </p>
                </div>

                <div className="glass-card">
                  <span style={{ fontSize: "0.72rem", color: "var(--text-dim)", textTransform: "uppercase", fontWeight: 700 }}>
                    Evaluation Window
                  </span>
                  <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--indigo-400)", marginTop: "10px" }}>
                    {backtest.evaluation_start_date} → {backtest.evaluation_end_date}
                  </div>
                  <p style={{ fontSize: "0.74rem", color: "var(--text-dim)", marginTop: "8px" }}>
                    Spans {backtest.total_historical_records} chronological mandi auction dates.
                  </p>
                </div>

                <div className="glass-card">
                  <span style={{ fontSize: "0.72rem", color: "var(--text-dim)", textTransform: "uppercase", fontWeight: 700 }}>
                    Latest Observed Spot Price
                  </span>
                  <div style={{ fontSize: "1.75rem", fontWeight: 800, color: "var(--emerald-400)", marginTop: "6px" }}>
                    ₹{backtest.last_observed_price?.toLocaleString()}
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 400, marginLeft: "4px" }}>
                      /Qtl
                    </span>
                  </div>
                  <p style={{ fontSize: "0.74rem", color: "var(--text-dim)", marginTop: "4px" }}>
                    Observed on {backtest.last_observed_date} at {backtest.market} APMC.
                  </p>
                </div>

                <div className="glass-card">
                  <span style={{ fontSize: "0.72rem", color: "var(--text-dim)", textTransform: "uppercase", fontWeight: 700 }}>
                    Evaluation Integrity
                  </span>
                  <div style={{ fontSize: "1.25rem", fontWeight: 800, color: "#fff", marginTop: "8px", display: "flex", alignItems: "center", gap: "6px" }}>
                    <CheckCircle2 size={18} style={{ color: "var(--emerald-400)" }} />
                    <span>{backtest.availability_mode === "RETROSPECTIVE" ? "Not Point-in-Time Verified" : "Availability-Filtered Training"}</span>
                  </div>
                  <p style={{ fontSize: "0.74rem", color: "var(--text-dim)", marginTop: "8px" }}>
                    {backtest.availability_mode === "RETROSPECTIVE"
                      ? "Training uses final stored history, including later imports or revisions."
                      : "Training uses only eligible versions available by the UTC cutoff; unknown availability is excluded."}
                  </p>
                </div>
              </div>

              {/* MODEL COMPARISON TABLE: Candidate ML Models vs Baseline */}
              <div className="glass-card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "10px", marginBottom: "16px" }}>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <Scale size={18} style={{ color: "var(--emerald-400)" }} />
                      <h4 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-main)" }}>
                        Candidate Forecasting Algorithm vs. Naive Persistence Baseline
                      </h4>
                    </div>
                    <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "2px" }}>
                      Direct benchmark comparison on identical evaluation observations for {backtest.commodity} @ {backtest.market}
                    </p>
                  </div>

                  <span className="badge badge-indigo" style={{ fontSize: "0.72rem" }}>
                    Baseline Definition: P_(t+h) = P_t
                  </span>
                </div>

                <div className="table-responsive">
                  <table className="modern-table">
                    <thead>
                      <tr>
                        <th>Forecast Horizon</th>
                        <th>Sample Size (N)</th>
                        <th>Candidate MAE</th>
                        <th>Baseline MAE</th>
                        <th>Candidate RMSE</th>
                        <th>Baseline RMSE</th>
                        <th>Safe MAPE</th>
                        <th>Directional Hit Rate</th>
                        <th>Win Rate vs Baseline</th>
                        <th>Empirical Verdict</th>
                        <th>Reliability Tier</th>
                      </tr>
                    </thead>
                    <tbody>
                      {displayedHorizons.map((hz) => {
                        const isWinner = hz.outperformed_baseline;
                        return (
                          <tr key={hz.horizon_days}>
                            <td style={{ fontWeight: 700, color: "#fff" }}>
                              {hz.horizon_label}
                            </td>
                            <td className="mono" style={{ color: "var(--text-muted)" }}>
                              {hz.sample_count} matched
                            </td>
                            <td className="mono" style={{ color: isWinner ? "var(--emerald-400)" : "#fff", fontWeight: 700 }}>
                              ₹{hz.candidate_metrics.mae.toFixed(1)}/Qtl
                            </td>
                            <td className="mono" style={{ color: "var(--text-dim)" }}>
                              ₹{hz.baseline_metrics.mae.toFixed(1)}/Qtl
                            </td>
                            <td className="mono" style={{ color: isWinner ? "var(--emerald-400)" : "#fff", fontWeight: 700 }}>
                              ₹{hz.candidate_metrics.rmse.toFixed(1)}/Qtl
                            </td>
                            <td className="mono" style={{ color: "var(--text-dim)" }}>
                              ₹{hz.baseline_metrics.rmse.toFixed(1)}/Qtl
                            </td>
                            <td className="mono" style={{ color: "var(--indigo-400)", fontWeight: 600 }}>
                              {hz.candidate_metrics.mape.toFixed(1)}%
                            </td>
                            <td className="mono" style={{ color: "var(--emerald-400)", fontWeight: 600 }}>
                              {hz.candidate_metrics.directional_accuracy_pct !== null
                                ? `${hz.candidate_metrics.directional_accuracy_pct}%`
                                : "--"}
                            </td>
                            <td className="mono" style={{ fontWeight: 700, color: isWinner ? "var(--emerald-400)" : "var(--amber-400)" }}>
                              {hz.candidate_metrics.win_rate_vs_baseline_pct !== null
                                ? `${hz.candidate_metrics.win_rate_vs_baseline_pct}%`
                                : "--"}
                            </td>
                            <td style={{ fontSize: "0.78rem", maxWidth: "260px" }}>
                              <span
                                style={{
                                  color: isWinner ? "var(--emerald-400)" : "var(--amber-400)",
                                  fontWeight: 600,
                                }}
                              >
                                {hz.evaluation_verdict}
                              </span>
                            </td>
                            <td>
                              <span
                                className={`badge ${
                                  hz.reliability_tier === "High"
                                    ? "badge-emerald"
                                    : hz.reliability_tier === "Moderate"
                                    ? "badge-amber"
                                    : "badge-rose"
                                }`}
                                style={{ fontSize: "0.68rem" }}
                              >
                                {hz.reliability_tier}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Missing Observations Note */}
                <div style={{ marginTop: "12px", fontSize: "0.78rem", color: "var(--text-dim)", display: "flex", alignItems: "center", gap: "8px" }}>
                  <Info size={14} style={{ color: "var(--indigo-400)", flexShrink: 0 }} />
                  <span>
                    Closed mandi days (e.g., Sundays, festival closures, or unscheduled market halts) are tracked without distorting matched evaluation pairs.
                  </span>
                </div>
              </div>

              {/* INTERACTIVE PREDICTED-VERSUS-ACTUAL PRICE CHART */}
              <div className="glass-card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "10px", marginBottom: "14px" }}>
                  <div>
                    <h4 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-main)" }}>
                      Historical Predicted vs. Actual Mandi Prices
                    </h4>
                    <p style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                      Chronological out-of-sample prediction trajectories compared against observed APMC auction transactions (₹/Quintal)
                    </p>
                  </div>

                  {/* Chart Legend */}
                  <div style={{ display: "flex", alignItems: "center", gap: "16px", fontSize: "0.78rem" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      <span style={{ width: "12px", height: "3px", background: "var(--emerald-400)", borderRadius: "2px" }} />
                      <span style={{ color: "#fff" }}>Actual Market Price</span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      <span style={{ width: "12px", height: "3px", background: "var(--indigo-500)", borderRadius: "2px" }} />
                      <span style={{ color: "var(--indigo-400)" }}>Candidate Model Prediction</span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      <span style={{ width: "12px", height: "3px", background: "var(--amber-400)", borderRadius: "2px", borderTop: "1px dashed var(--amber-400)" }} />
                      <span style={{ color: "var(--amber-400)" }}>Naive Persistence Baseline</span>
                    </div>
                  </div>
                </div>

                {chartPoints.length > 0 ? (
                  <div style={{ position: "relative", width: "100%", overflowX: "auto" }}>
                    <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} style={{ width: "100%", height: "auto", display: "block" }}>
                      {/* Grid Lines */}
                      {[0, 0.25, 0.5, 0.75, 1].map((pct, idx) => {
                        const yVal = chartBounds.minPrice + pct * chartBounds.yRange;
                        const yPos = getYCoord(yVal);
                        return (
                          <g key={idx}>
                            <line
                              x1={padding.left}
                              y1={yPos}
                              x2={svgWidth - padding.right}
                              y2={yPos}
                              stroke="rgba(255,255,255,0.06)"
                              strokeDasharray="4 4"
                            />
                            <text
                              x={padding.left - 8}
                              y={yPos + 4}
                              fill="var(--text-dim)"
                              fontSize="10"
                              textAnchor="end"
                              fontFamily="monospace"
                            >
                              ₹{Math.round(yVal)}
                            </text>
                          </g>
                        );
                      })}

                      {/* X-axis date labels */}
                      {chartPoints.map((p, idx) => {
                        // Show every 6th date label
                        if (idx % Math.max(1, Math.floor(chartPoints.length / 7)) !== 0 && idx !== chartPoints.length - 1) return null;
                        const xPos = getXCoord(idx, chartPoints.length);
                        return (
                          <text
                            key={idx}
                            x={xPos}
                            y={svgHeight - 12}
                            fill="var(--text-dim)"
                            fontSize="9"
                            textAnchor="middle"
                            fontFamily="monospace"
                          >
                            {p.target_date.slice(5)}
                          </text>
                        );
                      })}

                      {/* Naive Baseline Path */}
                      <path d={basePathStr} fill="none" stroke="var(--amber-400)" strokeWidth="1.8" strokeDasharray="3 3" opacity="0.8" />

                      {/* Candidate Model Path */}
                      <path d={predPathStr} fill="none" stroke="var(--indigo-500)" strokeWidth="2.2" strokeDasharray="5 3" />

                      {/* Actual Market Observation Path */}
                      <path d={actualPathStr} fill="none" stroke="var(--emerald-400)" strokeWidth="2.5" />

                      {/* Points / Hover Nodes */}
                      {chartPoints.map((p, idx) => {
                        const xPos = getXCoord(idx, chartPoints.length);
                        const yActual = getYCoord(p.actual_price);
                        const isHovered = hoveredPoint?.date === p.target_date;

                        return (
                          <g key={idx}>
                            {/* Actual Price Dot */}
                            <circle
                              cx={xPos}
                              cy={yActual}
                              r={isHovered ? 5 : 3}
                              fill="var(--emerald-400)"
                              stroke="#0f172a"
                              strokeWidth="1.5"
                              style={{ cursor: "pointer", transition: "r 0.15s ease" }}
                              onMouseEnter={() =>
                                setHoveredPoint({
                                  date: p.target_date,
                                  actual: p.actual_price,
                                  predicted: p.predicted_price,
                                  baseline: p.baseline_predicted_price,
                                  error: p.absolute_error,
                                  horizon: p.horizon_days,
                                  x: xPos,
                                  y: yActual,
                                })
                              }
                              onMouseLeave={() => setHoveredPoint(null)}
                            />

                            {/* Candidate Prediction Point */}
                            <rect
                              x={xPos - (isHovered ? 4 : 2.5)}
                              y={getYCoord(p.predicted_price) - (isHovered ? 4 : 2.5)}
                              width={isHovered ? 8 : 5}
                              height={isHovered ? 8 : 5}
                              fill="var(--indigo-400)"
                              stroke="#0f172a"
                              strokeWidth="1.2"
                              style={{ cursor: "pointer" }}
                              onMouseEnter={() =>
                                setHoveredPoint({
                                  date: p.target_date,
                                  actual: p.actual_price,
                                  predicted: p.predicted_price,
                                  baseline: p.baseline_predicted_price,
                                  error: p.absolute_error,
                                  horizon: p.horizon_days,
                                  x: xPos,
                                  y: yActual,
                                })
                              }
                            />
                          </g>
                        );
                      })}
                    </svg>

                    {/* Interactive Tooltip Card */}
                    {hoveredPoint && (
                      <div
                        style={{
                          position: "absolute",
                          left: `${Math.min(svgWidth - 220, Math.max(10, hoveredPoint.x - 90))}px`,
                          top: `${Math.max(10, hoveredPoint.y - 120)}px`,
                          background: "rgba(15, 23, 42, 0.96)",
                          border: "1px solid rgba(255,255,255,0.15)",
                          borderRadius: "8px",
                          padding: "10px 14px",
                          boxShadow: "0 10px 25px rgba(0,0,0,0.5)",
                          fontSize: "0.78rem",
                          pointerEvents: "none",
                          zIndex: 10,
                          minWidth: "190px",
                        }}
                      >
                        <div style={{ fontWeight: 700, color: "#fff", marginBottom: "6px" }}>
                          Target Date: {hoveredPoint.date}
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", color: "var(--emerald-400)", marginBottom: "3px" }}>
                          <span>Actual Market Price:</span>
                          <strong>₹{hoveredPoint.actual.toLocaleString()}/Qtl</strong>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", color: "var(--indigo-400)", marginBottom: "3px" }}>
                          <span>Predicted Price:</span>
                          <strong>₹{hoveredPoint.predicted.toLocaleString()}/Qtl</strong>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", color: "var(--amber-400)", marginBottom: "3px" }}>
                          <span>Persistence Baseline:</span>
                          <strong>₹{hoveredPoint.baseline.toLocaleString()}/Qtl</strong>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", borderTop: "1px solid rgba(255,255,255,0.08)", paddingTop: "4px", marginTop: "4px", color: "var(--text-dim)" }}>
                          <span>Absolute Error:</span>
                          <strong style={{ color: "#fff" }}>₹{hoveredPoint.error.toFixed(1)}/Qtl</strong>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ padding: "40px", textAlign: "center", color: "var(--text-dim)" }}>
                    No matched price observations available for the selected filters.
                  </div>
                )}
              </div>

              {/* DETAILED PREDICTION-VERSUS-ACTUAL RECORDS TABLE */}
              <div className="glass-card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px", marginBottom: "16px" }}>
                  <div>
                    <h4 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-main)" }}>
                      Audited Prediction-versus-Actual Records
                    </h4>
                    <p style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                      Individual transaction pairings with data cutoff dates, target dates, errors, and provenance ({filteredRecords.length} records)
                    </p>
                  </div>

                  {/* Pagination Controls */}
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <button
                      className="btn btn-secondary"
                      disabled={recordsPage <= 1}
                      onClick={() => setRecordsPage((p) => Math.max(1, p - 1))}
                      style={{ padding: "4px 10px", fontSize: "0.78rem" }}
                    >
                      Prev
                    </button>
                    <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                      Page {recordsPage} of {totalPages}
                    </span>
                    <button
                      className="btn btn-secondary"
                      disabled={recordsPage >= totalPages}
                      onClick={() => setRecordsPage((p) => Math.min(totalPages, p + 1))}
                      style={{ padding: "4px 10px", fontSize: "0.78rem" }}
                    >
                      Next
                    </button>
                  </div>
                </div>

                <div className="table-responsive">
                  <table className="modern-table">
                    <thead>
                      <tr>
                        <th>Target Date</th>
                        <th>Cutoff Date (t)</th>
                        <th>Horizon</th>
                        <th>Predicted Price</th>
                        <th>Actual Price</th>
                        <th>Absolute Error</th>
                        <th>Percentage Error</th>
                        <th>Baseline Price</th>
                        <th>Baseline Error</th>
                        <th>Model Algorithm</th>
                        <th>Record Provenance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {paginatedRecords.map((r, i) => {
                        const beatBaseline = r.absolute_error < r.baseline_absolute_error;
                        return (
                          <tr key={r.id || `${r.target_date}-${r.horizon_days}-${i}`}>
                            <td style={{ fontWeight: 600, color: "#fff" }}>{r.target_date}</td>
                            <td className="mono" style={{ color: "var(--text-dim)", fontSize: "0.8rem" }}>
                              {r.forecast_date}
                            </td>
                            <td>
                              <span className="badge badge-indigo" style={{ fontSize: "0.7rem" }}>
                                +{r.horizon_days}d
                              </span>
                            </td>
                            <td className="mono" style={{ fontWeight: 700, color: "var(--indigo-400)" }}>
                              ₹{r.predicted_price.toFixed(1)}
                            </td>
                            <td className="mono" style={{ fontWeight: 700, color: "var(--emerald-400)" }}>
                              ₹{r.actual_price.toFixed(1)}
                            </td>
                            <td className="mono" style={{ color: beatBaseline ? "var(--emerald-400)" : "#fff", fontWeight: 600 }}>
                              ₹{r.absolute_error.toFixed(1)}
                            </td>
                            <td className="mono" style={{ color: "var(--text-muted)" }}>
                              {r.percentage_error.toFixed(1)}%
                            </td>
                            <td className="mono" style={{ color: "var(--amber-400)" }}>
                              ₹{r.baseline_predicted_price.toFixed(1)}
                            </td>
                            <td className="mono" style={{ color: "var(--text-dim)" }}>
                              ₹{r.baseline_absolute_error.toFixed(1)}
                            </td>
                            <td style={{ fontSize: "0.76rem", color: "var(--text-muted)", maxWidth: "160px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                              {r.model_name}
                            </td>
                            <td>
                              <span
                                className={`badge ${
                                  r.record_type === "SAVED_LIVE_FORECAST" ? "badge-emerald" : "badge-amber"
                                }`}
                                style={{ fontSize: "0.68rem" }}
                              >
                                {r.record_type === "SAVED_LIVE_FORECAST" ? "Live Saved" : "Walk-Forward"}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* METRIC DEFINITIONS & INTERPRETATION PANEL */}
              <div className="glass-card">
                <h4 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-main)", marginBottom: "14px" }}>
                  Validation Metrics Glossary &amp; Statistical Interpretation
                </h4>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "16px" }}>
                  <div style={{ background: "rgba(255,255,255,0.02)", padding: "14px", borderRadius: "var(--radius-sm)", border: "1px solid rgba(255,255,255,0.05)" }}>
                    <div style={{ fontWeight: 700, color: "#fff", fontSize: "0.85rem", marginBottom: "4px" }}>
                      Mean Absolute Error (MAE)
                    </div>
                    <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>
                      Average absolute divergence between model predictions and observed transaction prices in ₹/Quintal. Robust to isolated outlier days.
                    </p>
                  </div>

                  <div style={{ background: "rgba(255,255,255,0.02)", padding: "14px", borderRadius: "var(--radius-sm)", border: "1px solid rgba(255,255,255,0.05)" }}>
                    <div style={{ fontWeight: 700, color: "#fff", fontSize: "0.85rem", marginBottom: "4px" }}>
                      Root Mean Squared Error (RMSE)
                    </div>
                    <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>
                      Quadratic error metric that penalizes large forecasting misses heavily. Essential for identifying model vulnerability to sudden price shocks.
                    </p>
                  </div>

                  <div style={{ background: "rgba(255,255,255,0.02)", padding: "14px", borderRadius: "var(--radius-sm)", border: "1px solid rgba(255,255,255,0.05)" }}>
                    <div style={{ fontWeight: 700, color: "#fff", fontSize: "0.85rem", marginBottom: "4px" }}>
                      Safe Percentage Error (MAPE)
                    </div>
                    <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>
                      Relative percentage error with an epsilon threshold (₹1.0/Qtl) applied to the denominator to prevent mathematical explosion on zero or near-zero prices.
                    </p>
                  </div>

                  <div style={{ background: "rgba(255,255,255,0.02)", padding: "14px", borderRadius: "var(--radius-sm)", border: "1px solid rgba(255,255,255,0.05)" }}>
                    <div style={{ fontWeight: 700, color: "#fff", fontSize: "0.85rem", marginBottom: "4px" }}>
                      Naive Persistence Baseline
                    </div>
                    <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>
                      Standard econometric benchmark projecting P_(t+h) = P_t. Any model claiming real utility must empirically outperform this baseline on out-of-sample data.
                    </p>
                  </div>
                </div>
              </div>

              {/* HISTORICAL FORECAST RELIABILITY & RISK INTEGRATION */}
              <div className="glass-card" style={{ borderLeft: "4px solid var(--amber-400)" }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: "12px" }}>
                  <AlertTriangle size={20} style={{ color: "var(--amber-400)", flexShrink: 0, marginTop: "2px" }} />
                  <div>
                    <h5 style={{ fontWeight: 700, color: "#fff", fontSize: "0.95rem", marginBottom: "4px" }}>
                      Historical Performance Caveats &amp; Decision-Risk Integration
                    </h5>
                    <p style={{ fontSize: "0.82rem", color: "var(--text-muted)", lineHeight: 1.6, marginBottom: "8px" }}>
                      {backtest.historical_reliability_caveats}
                    </p>
                    <p style={{ fontSize: "0.78rem", color: "var(--text-dim)", lineHeight: 1.5, margin: 0 }}>
                      <strong>Integration with Decision Support Engine:</strong> Measured historical holdout RMSE and MAE directly calibrate the downside price confidence spreads in the Decision Support module. This prevents overly optimistic revenue estimates when deciding between immediate sale and crop storage.
                    </p>
                  </div>
                </div>
              </div>
            </>
          ) : null}
        </>
      )}

      {/* ======================================================== */}
      {/* SUB-TAB 2: EXPLAINABLE ML & SHAP ATTRIBUTIONS            */}
      {/* ======================================================== */}
      {activeSubTab === "explainability" && (
        <div className="glass-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px", marginBottom: "16px" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <BrainCircuit size={18} style={{ color: "var(--emerald-400)" }} />
                <h4 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-main)" }}>
                  Explainable Machine Learning &amp; SHAP Feature Attributions
                </h4>
              </div>
              <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "2px" }}>
                {explanation?.model_name || "Regularized Multi-Feature Lag Regressor"} ({explanation?.total_training_samples || 0} training samples)
              </p>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span className={`badge ${explanation?.is_explainable ? "badge-emerald" : "badge-amber"}`} style={{ fontSize: "0.75rem" }}>
                {explanation?.is_explainable ? "Model Trained & Verified" : "Data Insufficient for Training"}
              </span>
              {explanation?.shap_summary_available && (
                <span className="badge badge-indigo" style={{ fontSize: "0.75rem" }}>
                  SHAP Attributions Active
                </span>
              )}
            </div>
          </div>

          {/* Causality Disclaimer */}
          <div
            style={{
              padding: "12px 16px",
              borderRadius: "var(--radius-sm)",
              background: "rgba(99, 102, 241, 0.08)",
              border: "1px solid rgba(99, 102, 241, 0.25)",
              fontSize: "0.8rem",
              color: "var(--text-muted)",
              marginBottom: "18px",
            }}
          >
            <div style={{ display: "flex", alignItems: "flex-start", gap: "8px" }}>
              <Info size={16} style={{ color: "var(--indigo-400)", flexShrink: 0, marginTop: "1px" }} />
              <div>{explanation?.causality_disclaimer}</div>
            </div>
          </div>

          {explanation?.is_explainable && explanation.features.length > 0 ? (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#fff" }}>
                  Feature Importance Ranking (% Relative Associative Weight)
                </span>
                {explanation.shap_base_value && (
                  <span className="mono" style={{ fontSize: "0.8rem", color: "var(--text-dim)" }}>
                    Base Expected Value: ₹{explanation.shap_base_value}/Qtl
                  </span>
                )}
              </div>

              {/* Feature Bars */}
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                {explanation.features.map((feat) => (
                  <div
                    key={feat.feature_name}
                    style={{
                      background: "rgba(0,0,0,0.25)",
                      padding: "12px 16px",
                      borderRadius: "var(--radius-sm)",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <span style={{ fontWeight: 600, fontSize: "0.88rem", color: "#fff" }}>
                          {feat.display_name}
                        </span>
                        <span
                          className={`badge ${
                            feat.direction === "positive"
                              ? "badge-emerald"
                              : feat.direction === "negative"
                              ? "badge-rose"
                              : "badge-amber"
                          }`}
                          style={{ fontSize: "0.65rem", padding: "1px 6px" }}
                        >
                          {feat.direction === "positive"
                            ? "↑ Positive Impact"
                            : feat.direction === "negative"
                            ? "↓ Negative Impact"
                            : "— Neutral"}
                        </span>
                      </div>

                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        {feat.sample_value !== null && feat.sample_value !== undefined && (
                          <span className="mono" style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
                            Recent: {feat.sample_value}
                          </span>
                        )}
                        <span className="mono" style={{ fontWeight: 700, color: "var(--emerald-400)", fontSize: "0.95rem" }}>
                          {feat.importance_pct}%
                        </span>
                      </div>
                    </div>

                    <div style={{ width: "100%", height: "6px", background: "rgba(255,255,255,0.06)", borderRadius: "3px", overflow: "hidden", marginBottom: "6px" }}>
                      <div
                        style={{
                          width: `${Math.min(100, feat.importance_pct * 2.2)}%`,
                          height: "100%",
                          background:
                            feat.direction === "positive"
                              ? "linear-gradient(90deg, var(--emerald-600), var(--emerald-400))"
                              : "linear-gradient(90deg, var(--rose-600), var(--rose-400))",
                          borderRadius: "3px",
                        }}
                      />
                    </div>

                    <p style={{ fontSize: "0.75rem", color: "var(--text-dim)", margin: 0 }}>
                      {feat.description}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div style={{ padding: "20px", background: "rgba(0,0,0,0.2)", borderRadius: "var(--radius-sm)", color: "var(--text-dim)", fontSize: "0.85rem" }}>
              {explanation?.message || "Feature importance is not available until training data meets the minimum required sample depth."}
            </div>
          )}
        </div>
      )}

      {/* ======================================================== */}
      {/* SUB-TAB 3: MULTI-HORIZON OUT-OF-SAMPLE RISK              */}
      {/* ======================================================== */}
      {activeSubTab === "uncertainty" && uncertainty && (
        <div className="glass-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px", marginBottom: "16px" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <Sliders size={18} style={{ color: "var(--indigo-500)" }} />
                <h4 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-main)" }}>
                  Forecast Uncertainty &amp; Multi-Horizon Out-of-Sample Risk Spreads
                </h4>
              </div>
              <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "2px" }}>
                Empirical holdout validation across {uncertainty.evaluation_sample_size} historical observations
              </p>
            </div>

            <span className={`badge ${uncertainty.is_sample_sufficient ? "badge-emerald" : "badge-amber"}`} style={{ fontSize: "0.75rem" }}>
              {uncertainty.is_sample_sufficient ? "Empirically Calibrated" : "Limited Evaluation Sample"}
            </span>
          </div>

          {/* Extrapolation Warning */}
          {uncertainty.horizon_extrapolation_warning && (
            <div
              style={{
                padding: "12px 16px",
                borderRadius: "var(--radius-sm)",
                background: "rgba(245, 158, 11, 0.08)",
                border: "1px solid rgba(245, 158, 11, 0.25)",
                fontSize: "0.8rem",
                color: "var(--text-muted)",
                marginBottom: "16px",
              }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", gap: "8px" }}>
                <AlertTriangle size={16} style={{ color: "var(--amber-400)", flexShrink: 0, marginTop: "1px" }} />
                <div>{uncertainty.horizon_extrapolation_warning}</div>
              </div>
            </div>
          )}

          {/* Horizons Table */}
          {uncertainty.horizons.length > 0 && (
            <div className="table-responsive" style={{ marginBottom: "16px" }}>
              <table className="modern-table">
                <thead>
                  <tr>
                    <th>Forecast Horizon</th>
                    <th>Holdout MAE</th>
                    <th>Holdout RMSE</th>
                    <th>Holdout MAPE</th>
                    <th>95% Uncertainty Spread</th>
                    <th>Reliability Tier</th>
                    <th>Risk Assessment &amp; Context</th>
                  </tr>
                </thead>
                <tbody>
                  {uncertainty.horizons.map((hz) => (
                    <tr key={hz.horizon_days}>
                      <td style={{ fontWeight: 600, color: "#fff" }}>{hz.horizon_label}</td>
                      <td className="mono">₹{hz.holdout_mae}/Qtl</td>
                      <td className="mono">₹{hz.holdout_rmse}/Qtl</td>
                      <td className="mono" style={{ color: "var(--emerald-400)", fontWeight: 700 }}>
                        {hz.holdout_mape}%
                      </td>
                      <td className="mono" style={{ color: "var(--indigo-500)", fontWeight: 600 }}>
                        ±{hz.confidence_spread_pct}%
                      </td>
                      <td>
                        <span
                          className={`badge ${
                            hz.reliability_tier === "High"
                              ? "badge-emerald"
                              : hz.reliability_tier === "Moderate"
                              ? "badge-amber"
                              : "badge-rose"
                          }`}
                          style={{ fontSize: "0.68rem" }}
                        >
                          {hz.reliability_tier}
                        </span>
                      </td>
                      <td style={{ fontSize: "0.78rem", color: "var(--text-muted)", maxWidth: "300px" }}>
                        {hz.risk_notes}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div style={{ fontSize: "0.75rem", color: "var(--text-dim)", borderTop: "1px solid rgba(255,255,255,0.05)", paddingTop: "10px" }}>
            {uncertainty.disclaimer}
          </div>
        </div>
      )}
    </div>
  );
};
