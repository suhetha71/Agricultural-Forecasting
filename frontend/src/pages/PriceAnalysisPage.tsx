import React, { useState, useEffect } from "react";
import {
  MarketObservation,
  MarketSummary,
  FilterOptions,
  HistoricalSeriesView,
  SeasonalAnalysisResponse,
  AnomalyDetectionResponse,
  ArrivalsWeatherResponse,
} from "../types";
import { InteractiveChart } from "../components/InteractiveChart";
import { api } from "../services/api";
import {
  ArrowDown,
  ArrowUp,
  Filter,
  Calendar,
  Layers,
  FileSpreadsheet,
  Database,
  AlertTriangle,
  CloudRain,
  TrendingDown,
  TrendingUp,
  Info,
  Sliders,
  CheckCircle2,
  Activity,
} from "lucide-react";

interface PriceAnalysisPageProps {
  observations: MarketObservation[];
  summary: MarketSummary | null;
  filterOptions?: FilterOptions;
  isLoading: boolean;
  onNavigateTab?: (tab: string) => void;
}

export const PriceAnalysisPage: React.FC<PriceAnalysisPageProps> = ({
  observations,
  summary,
  filterOptions,
  isLoading,
  onNavigateTab,
}) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedSource, setSelectedSource] = useState<string>("ALL");
  const [selectedState, setSelectedState] = useState<string>("ALL");
  const [selectedDistrict, setSelectedDistrict] = useState<string>("ALL");
  const [sortAsc, setSortAsc] = useState(false);

  // Analytics State
  const [granularity, setGranularity] = useState<"daily" | "weekly" | "monthly">("daily");
  const [historicalView, setHistoricalView] = useState<HistoricalSeriesView | null>(null);
  const [seasonalData, setSeasonalData] = useState<SeasonalAnalysisResponse | null>(null);
  const [anomalyData, setAnomalyData] = useState<AnomalyDetectionResponse | null>(null);
  const [arrivalsWeatherData, setArrivalsWeatherData] = useState<ArrivalsWeatherResponse | null>(null);

  // Anomaly Configuration State
  const [anomalyMultiplier, setAnomalyMultiplier] = useState<number>(2.5);
  const [anomalyMethod, setAnomalyMethod] = useState<"rolling_zscore" | "iqr">("rolling_zscore");
  const [isAnalyticsLoading, setIsAnalyticsLoading] = useState<boolean>(false);

  const activeCommodity = summary?.commodity || (observations[0]?.commodity) || "Onion";
  const activeMarket = summary?.market || (observations[0]?.market) || "Lasalgaon";

  // Fetch Analytics & Intelligence Data
  const loadMarketIntelligence = async () => {
    if (!activeCommodity || !activeMarket) return;
    setIsAnalyticsLoading(true);
    try {
      const [histRes, seasonRes, anomalyRes, arrWeatherRes] = await Promise.allSettled([
        api.getHistoricalViews(activeCommodity, activeMarket, granularity),
        api.getSeasonalAnalysis(activeCommodity, activeMarket),
        api.getAnomalies(activeCommodity, activeMarket, anomalyMultiplier, anomalyMethod),
        api.getArrivalsWeather(activeCommodity, activeMarket),
      ]);

      if (histRes.status === "fulfilled") setHistoricalView(histRes.value);
      if (seasonRes.status === "fulfilled") setSeasonalData(seasonRes.value);
      if (anomalyRes.status === "fulfilled") setAnomalyData(anomalyRes.value);
      if (arrWeatherRes.status === "fulfilled") setArrivalsWeatherData(arrWeatherRes.value);
    } catch (e) {
      console.warn("Failed to load advanced analytics", e);
    } finally {
      setIsAnalyticsLoading(false);
    }
  };

  useEffect(() => {
    loadMarketIntelligence();
  }, [activeCommodity, activeMarket, granularity, anomalyMultiplier, anomalyMethod]);

  // Available unique districts from observations
  const availableDistricts = Array.from(
    new Set(
      observations
        .map((o) => o.district)
        .filter((d) => d && d.trim().length > 0 && d !== "General")
    )
  ).sort();

  const filteredObservations = observations
    .filter((obs) => {
      if (selectedSource !== "ALL" && obs.source !== selectedSource) return false;
      if (selectedState !== "ALL" && obs.state !== selectedState) return false;
      if (selectedDistrict !== "ALL" && obs.district !== selectedDistrict) return false;
      if (searchTerm.trim()) {
        const term = searchTerm.toLowerCase();
        const matches =
          obs.commodity.toLowerCase().includes(term) ||
          obs.market.toLowerCase().includes(term) ||
          obs.variety.toLowerCase().includes(term) ||
          obs.district.toLowerCase().includes(term) ||
          obs.state.toLowerCase().includes(term) ||
          obs.observation_date.includes(term);
        if (!matches) return false;
      }
      return true;
    })
    .sort((a, b) => {
      const timeA = new Date(a.observation_date).getTime();
      const timeB = new Date(b.observation_date).getTime();
      return sortAsc ? timeA - timeB : timeB - timeA;
    });

  const getSourceBadge = (source: string) => {
    switch (source) {
      case "OFFICIAL_GOV_API":
        return {
          label: "Official data.gov.in",
          className: "badge badge-emerald",
          description: "Authenticated Government of India Agmarknet OGD API",
        };
      case "USER_CSV_IMPORT":
        return {
          label: "User CSV Import",
          className: "badge badge-indigo",
          description: "Authenticated CSV file ingested by user",
        };
      case "DEMO_SEED_DATA":
      default:
        return {
          label: "Demonstration Data",
          className: "badge badge-amber",
          description: "Baseline demonstration record",
        };
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "28px" }}>
      {/* 1. Historical Granularity & Price Change Metrics Bar */}
      <div className="glass-card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "16px", marginBottom: "16px" }}>
          <div>
            <h3 style={{ fontSize: "1.05rem", fontWeight: 700, color: "var(--text-main)" }}>
              Historical Price Movements &amp; Aggregations — {activeCommodity} ({activeMarket})
            </h3>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "2px" }}>
              Analyzes {historicalView?.total_observations ?? observations.length} observations ({historicalView?.period_start ?? "..."} to {historicalView?.period_end ?? "..."}). Missing dates are never treated as zero prices.
            </p>
          </div>

          {/* Granularity Switcher */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "0.8rem", color: "var(--text-dim)" }}>View Scale:</span>
            <div style={{ display: "flex", background: "rgba(0,0,0,0.3)", borderRadius: "var(--radius-sm)", padding: "2px", border: "1px solid var(--border-subtle)" }}>
              {(["daily", "weekly", "monthly"] as const).map((g) => (
                <button
                  key={g}
                  onClick={() => setGranularity(g)}
                  style={{
                    background: granularity === g ? "var(--emerald-600)" : "transparent",
                    color: granularity === g ? "#fff" : "var(--text-muted)",
                    border: "none",
                    padding: "4px 12px",
                    borderRadius: "6px",
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    cursor: "pointer",
                    textTransform: "capitalize",
                  }}
                >
                  {g}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Price Change Indicators Grid */}
        {historicalView?.price_changes && historicalView.price_changes.length > 0 && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "12px", background: "rgba(0,0,0,0.2)", padding: "14px", borderRadius: "var(--radius-sm)" }}>
            {historicalView.price_changes.map((pc) => (
              <div key={pc.window_days} style={{ borderLeft: `3px solid ${pc.percentage_change >= 0 ? "var(--emerald-400)" : "var(--rose-500)"}`, paddingLeft: "10px" }}>
                <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>{pc.window_label}</div>
                <div style={{ fontSize: "1.15rem", fontWeight: 700, color: pc.percentage_change >= 0 ? "var(--emerald-400)" : "var(--rose-500)", marginTop: "2px" }}>
                  {pc.percentage_change >= 0 ? `+₹${pc.absolute_change}` : `-₹${Math.abs(pc.absolute_change)}`}
                  <span style={{ fontSize: "0.8rem", marginLeft: "4px" }}>({pc.percentage_change >= 0 ? "+" : ""}{pc.percentage_change}%)</span>
                </div>
                <div style={{ fontSize: "0.7rem", color: "var(--text-dim)", marginTop: "2px" }}>
                  From ₹{pc.start_price} ({pc.start_date}) to ₹{pc.end_price} ({pc.end_date})
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 2. Current Price vs Relevant Historical Baselines */}
      {historicalView?.current_vs_historical && (
        <div className="grid-cols-4">
          <div className="glass-card">
            <span style={{ fontSize: "0.75rem", color: "var(--text-dim)", textTransform: "uppercase", fontWeight: 700 }}>
              Current vs. 7-Day Mean
            </span>
            <div style={{ fontSize: "1.35rem", fontWeight: 800, color: "#fff", marginTop: "6px" }}>
              ₹{historicalView.current_vs_historical.vs_7d_mean?.baseline_mean ?? "--"}
            </div>
            <div style={{ fontSize: "0.8rem", fontWeight: 600, color: (historicalView.current_vs_historical.vs_7d_mean?.percent_diff ?? 0) >= 0 ? "var(--emerald-400)" : "var(--rose-500)", marginTop: "4px" }}>
              {(historicalView.current_vs_historical.vs_7d_mean?.percent_diff ?? 0) >= 0 ? "+" : ""}{historicalView.current_vs_historical.vs_7d_mean?.percent_diff}% vs 7-day average
            </div>
            <div style={{ fontSize: "0.7rem", color: "var(--text-dim)", marginTop: "4px" }}>
              {historicalView.current_vs_historical.vs_7d_mean?.observation_count} observations ({historicalView.current_vs_historical.vs_7d_mean?.period_label})
            </div>
          </div>

          <div className="glass-card">
            <span style={{ fontSize: "0.75rem", color: "var(--text-dim)", textTransform: "uppercase", fontWeight: 700 }}>
              Current vs. 30-Day Mean
            </span>
            <div style={{ fontSize: "1.35rem", fontWeight: 800, color: "#fff", marginTop: "6px" }}>
              ₹{historicalView.current_vs_historical.vs_30d_mean?.baseline_mean ?? "--"}
            </div>
            <div style={{ fontSize: "0.8rem", fontWeight: 600, color: (historicalView.current_vs_historical.vs_30d_mean?.percent_diff ?? 0) >= 0 ? "var(--emerald-400)" : "var(--rose-500)", marginTop: "4px" }}>
              {(historicalView.current_vs_historical.vs_30d_mean?.percent_diff ?? 0) >= 0 ? "+" : ""}{historicalView.current_vs_historical.vs_30d_mean?.percent_diff}% vs 30-day average
            </div>
            <div style={{ fontSize: "0.7rem", color: "var(--text-dim)", marginTop: "4px" }}>
              {historicalView.current_vs_historical.vs_30d_mean?.observation_count} observations ({historicalView.current_vs_historical.vs_30d_mean?.period_label})
            </div>
          </div>

          <div className="glass-card">
            <span style={{ fontSize: "0.75rem", color: "var(--text-dim)", textTransform: "uppercase", fontWeight: 700 }}>
              Current vs. 90-Day Mean
            </span>
            <div style={{ fontSize: "1.35rem", fontWeight: 800, color: "#fff", marginTop: "6px" }}>
              ₹{historicalView.current_vs_historical.vs_90d_mean?.baseline_mean ?? "--"}
            </div>
            <div style={{ fontSize: "0.8rem", fontWeight: 600, color: (historicalView.current_vs_historical.vs_90d_mean?.percent_diff ?? 0) >= 0 ? "var(--emerald-400)" : "var(--rose-500)", marginTop: "4px" }}>
              {(historicalView.current_vs_historical.vs_90d_mean?.percent_diff ?? 0) >= 0 ? "+" : ""}{historicalView.current_vs_historical.vs_90d_mean?.percent_diff}% vs 90-day average
            </div>
            <div style={{ fontSize: "0.7rem", color: "var(--text-dim)", marginTop: "4px" }}>
              {historicalView.current_vs_historical.vs_90d_mean?.observation_count} observations ({historicalView.current_vs_historical.vs_90d_mean?.period_label})
            </div>
          </div>

          <div className="glass-card">
            <span style={{ fontSize: "0.75rem", color: "var(--text-dim)", textTransform: "uppercase", fontWeight: 700 }}>
              Current vs. All-Time Mean
            </span>
            <div style={{ fontSize: "1.35rem", fontWeight: 800, color: "#fff", marginTop: "6px" }}>
              ₹{historicalView.current_vs_historical.vs_all_time_mean?.baseline_mean ?? "--"}
            </div>
            <div style={{ fontSize: "0.8rem", fontWeight: 600, color: (historicalView.current_vs_historical.vs_all_time_mean?.percent_diff ?? 0) >= 0 ? "var(--emerald-400)" : "var(--rose-500)", marginTop: "4px" }}>
              {(historicalView.current_vs_historical.vs_all_time_mean?.percent_diff ?? 0) >= 0 ? "+" : ""}{historicalView.current_vs_historical.vs_all_time_mean?.percent_diff}% vs series average
            </div>
            <div style={{ fontSize: "0.7rem", color: "var(--text-dim)", marginTop: "4px" }}>
              {historicalView.current_vs_historical.vs_all_time_mean?.observation_count} total observations
            </div>
          </div>
        </div>
      )}

      {/* 3. Main Historical Interactive Chart */}
      <InteractiveChart
        historicalData={filteredObservations.length > 0 ? filteredObservations : observations}
        title={`Historical Wholesale Price Series — ${activeCommodity} (${activeMarket})`}
        subtitle="Daily modal transactions, trading ranges, and market arrival volumes"
        isLoading={isLoading || isAnalyticsLoading}
      />

      {/* 4. Seasonal Patterns & Indian Crop Calendar Panel */}
      {seasonalData && (
        <div className="glass-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px", marginBottom: "16px" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <Calendar size={18} style={{ color: "var(--emerald-400)" }} />
                <h4 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-main)" }}>
                  Seasonal Patterns &amp; Indian Agricultural Crop Calendar
                </h4>
              </div>
              <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "2px" }}>
                Historical depth: {seasonalData.historical_span_months} months ({seasonalData.historical_span_days} calendar days, {seasonalData.total_observations} observations)
              </p>
            </div>

            <span
              className={`badge ${seasonalData.has_sufficient_multiyear_data ? "badge-emerald" : "badge-amber"}`}
              style={{ fontSize: "0.75rem" }}
            >
              {seasonalData.has_sufficient_multiyear_data ? "Multi-Year Verified Cycle" : "Intra-Sample Observed Averages"}
            </span>
          </div>

          {/* Data Sufficiency Notice */}
          <div
            style={{
              padding: "12px 16px",
              borderRadius: "var(--radius-sm)",
              background: seasonalData.has_sufficient_multiyear_data ? "rgba(16, 185, 129, 0.08)" : "rgba(245, 158, 11, 0.08)",
              border: `1px solid ${seasonalData.has_sufficient_multiyear_data ? "rgba(16, 185, 129, 0.25)" : "rgba(245, 158, 11, 0.25)"}`,
              fontSize: "0.8rem",
              color: "var(--text-muted)",
              marginBottom: "18px",
            }}
          >
            <div style={{ display: "flex", alignItems: "flex-start", gap: "8px" }}>
              <Info size={16} style={{ color: seasonalData.has_sufficient_multiyear_data ? "var(--emerald-400)" : "var(--amber-400)", flexShrink: 0, marginTop: "1px" }} />
              <div>{seasonalData.data_sufficiency_explanation}</div>
            </div>
          </div>

          {/* Indian Crop Seasons Breakdown */}
          {seasonalData.season_patterns.length > 0 && (
            <div style={{ marginBottom: "20px" }}>
              <h5 style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--text-dim)", textTransform: "uppercase", marginBottom: "10px" }}>
                Agro-Climatic Season Breakdown
              </h5>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "12px" }}>
                {seasonalData.season_patterns.map((sp) => (
                  <div key={sp.season_name} style={{ background: "rgba(255,255,255,0.02)", padding: "14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-color)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontWeight: 700, color: "#fff", fontSize: "0.9rem" }}>{sp.season_name}</span>
                      <span className="badge badge-indigo" style={{ fontSize: "0.65rem" }}>{sp.months_included}</span>
                    </div>
                    <div style={{ fontSize: "1.3rem", fontWeight: 800, color: "var(--emerald-400)", marginTop: "8px" }}>
                      ₹{sp.avg_modal_price.toLocaleString("en-IN")}{" "}
                      <span style={{ fontSize: "0.75rem", color: "var(--text-dim)", fontWeight: 400 }}>/Qtl Avg</span>
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "6px" }}>
                      {sp.crop_season_context} ({sp.observation_count} observations)
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Monthly Breakdown Cards */}
          {seasonalData.monthly_patterns.length > 0 && (
            <div>
              <h5 style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--text-dim)", textTransform: "uppercase", marginBottom: "10px" }}>
                Monthly Modal Price Distribution
              </h5>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))", gap: "10px" }}>
                {seasonalData.monthly_patterns.map((mp) => (
                  <div key={mp.month_number} style={{ background: "rgba(0,0,0,0.25)", padding: "10px 12px", borderRadius: "var(--radius-sm)", textAlign: "center" }}>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-dim)", fontWeight: 600 }}>{mp.month_name.slice(0, 3)}</div>
                    <div style={{ fontSize: "1rem", fontWeight: 700, color: "#fff", marginTop: "4px" }}>
                      ₹{mp.avg_modal_price.toLocaleString("en-IN")}
                    </div>
                    <div style={{ fontSize: "0.68rem", color: "var(--text-dim)", marginTop: "2px" }}>
                      {mp.observation_count} days
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 5. Statistical Price Anomaly Detection Panel */}
      {anomalyData && (
        <div className="glass-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "14px", marginBottom: "16px" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <AlertTriangle size={18} style={{ color: "var(--amber-400)" }} />
                <h4 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-main)" }}>
                  Statistical Price Anomaly &amp; Data Error Detection
                </h4>
              </div>
              <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "2px" }}>
                {anomalyData.method_explanation}
              </p>
            </div>

            {/* Threshold & Method Controls */}
            <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <Sliders size={14} style={{ color: "var(--text-dim)" }} />
                <span style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>Sensitivity:</span>
                <select
                  className="select-input"
                  value={anomalyMultiplier}
                  onChange={(e) => setAnomalyMultiplier(parseFloat(e.target.value))}
                  style={{ fontSize: "0.75rem", padding: "4px 8px" }}
                >
                  <option value={2.0}>2.0σ (Sensitive)</option>
                  <option value={2.5}>2.5σ (Standard)</option>
                  <option value={3.0}>3.0σ (Conservative)</option>
                  <option value={3.5}>3.5σ (Extreme Only)</option>
                </select>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <span style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>Method:</span>
                <select
                  className="select-input"
                  value={anomalyMethod}
                  onChange={(e) => setAnomalyMethod(e.target.value as any)}
                  style={{ fontSize: "0.75rem", padding: "4px 8px" }}
                >
                  <option value="rolling_zscore">Rolling Z-Score</option>
                  <option value="iqr">Tukey's IQR</option>
                </select>
              </div>
            </div>
          </div>

          {/* Anomaly Summary Badges */}
          <div style={{ display: "flex", alignItems: "center", gap: "14px", marginBottom: "16px", flexWrap: "wrap" }}>
            <span className="badge badge-emerald" style={{ fontSize: "0.75rem" }}>
              {anomalyData.total_observations_analyzed} Observations Evaluated
            </span>
            <span className={`badge ${anomalyData.anomaly_count > 0 ? "badge-amber" : "badge-emerald"}`} style={{ fontSize: "0.75rem" }}>
              {anomalyData.anomaly_count} Statistical Anomalies Flagged
            </span>
            {anomalyData.data_error_count > 0 && (
              <span className="badge badge-rose" style={{ fontSize: "0.75rem" }}>
                {anomalyData.data_error_count} Suspected Data Errors
              </span>
            )}
            <span style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
              *Unusual observations are strictly preserved in the database for auditing and not purged.
            </span>
          </div>

          {/* Anomalies Table */}
          {anomalyData.anomalies.length > 0 ? (
            <div className="table-responsive">
              <table className="modern-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Observed Price</th>
                    <th>Rolling Baseline</th>
                    <th>Normal Threshold</th>
                    <th>Z-Score / Dev</th>
                    <th>Classification</th>
                    <th>Severity</th>
                    <th>Explanation &amp; Diagnosis</th>
                  </tr>
                </thead>
                <tbody>
                  {anomalyData.anomalies.slice(0, 10).map((a, idx) => (
                    <tr key={idx}>
                      <td className="mono" style={{ fontWeight: 600 }}>{a.observation_date}</td>
                      <td className="mono" style={{ fontWeight: 700, color: a.anomaly_type === "HIGH_SPIKE" ? "var(--rose-400)" : a.anomaly_type === "LOW_CRASH" ? "var(--amber-400)" : "#fff" }}>
                        ₹{a.modal_price.toLocaleString("en-IN")}
                      </td>
                      <td className="mono" style={{ color: "var(--text-dim)" }}>₹{a.baseline_price.toLocaleString("en-IN")}</td>
                      <td className="mono" style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
                        ₹{a.threshold_lower.toLocaleString("en-IN")} – ₹{a.threshold_upper.toLocaleString("en-IN")}
                      </td>
                      <td className="mono" style={{ fontWeight: 600 }}>
                        {a.z_score !== null && a.z_score !== undefined
                          ? `${a.z_score > 0 ? "+" : ""}${a.z_score}σ`
                          : `₹${a.deviation_amount > 0 ? "+" : ""}${a.deviation_amount}`}
                      </td>
                      <td>
                        <span
                          className={`badge ${
                            a.anomaly_type === "HIGH_SPIKE"
                              ? "badge-rose"
                              : a.anomaly_type === "LOW_CRASH"
                              ? "badge-amber"
                              : "badge-rose"
                          }`}
                          style={{ fontSize: "0.65rem", padding: "2px 8px" }}
                        >
                          {a.anomaly_type.replace(/_/g, " ")}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${a.severity === "EXTREME" ? "badge-rose" : a.severity === "MODERATE" ? "badge-amber" : "badge-indigo"}`} style={{ fontSize: "0.65rem" }}>
                          {a.severity}
                        </span>
                      </td>
                      <td style={{ fontSize: "0.78rem", color: "var(--text-muted)", maxWidth: "340px" }}>
                        {a.explanation}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {anomalyData.anomalies.length > 10 && (
                <div style={{ textAlign: "center", marginTop: "10px", fontSize: "0.75rem", color: "var(--text-dim)" }}>
                  Showing top 10 of {anomalyData.anomalies.length} flagged observations.
                </div>
              )}
            </div>
          ) : (
            <div style={{ padding: "20px", background: "rgba(16, 185, 129, 0.05)", borderRadius: "var(--radius-sm)", textAlign: "center", color: "var(--emerald-400)", fontSize: "0.85rem" }}>
              <CheckCircle2 size={16} style={{ display: "inline", marginRight: "6px", verticalAlign: "middle" }} />
              All historical observations reside within standard {anomalyMultiplier}σ statistical bounds. No price anomalies or data errors detected.
            </div>
          )}
        </div>
      )}

      {/* 6. Market Arrivals & Weather Context Card */}
      {arrivalsWeatherData && (
        <div className="glass-card">
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "14px" }}>
            <Activity size={18} style={{ color: "var(--indigo-500)" }} />
            <h4 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-main)" }}>
              Market Arrivals &amp; Agro-Meteorological Weather Context
            </h4>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
            {/* Arrivals Analysis */}
            <div style={{ background: "rgba(255,255,255,0.02)", padding: "16px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-color)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#fff" }}>Reported Mandi Arrivals</span>
                <span className="badge badge-emerald" style={{ fontSize: "0.65rem" }}>
                  {arrivalsWeatherData.arrivals_coverage_pct}% Reported Coverage
                </span>
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-dim)", marginTop: "4px" }}>
                {arrivalsWeatherData.arrivals_reported_count} of {arrivalsWeatherData.total_observations} records report physical volume
              </div>

              {arrivalsWeatherData.price_arrival_correlation !== null && arrivalsWeatherData.price_arrival_correlation !== undefined ? (
                <div style={{ marginTop: "12px", background: "rgba(0,0,0,0.25)", padding: "12px", borderRadius: "var(--radius-sm)" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>Price-Arrival Correlation (Pearson r)</div>
                  <div style={{ fontSize: "1.2rem", fontWeight: 800, color: arrivalsWeatherData.price_arrival_correlation < -0.2 ? "var(--amber-400)" : "var(--indigo-500)", marginTop: "2px" }}>
                    {arrivalsWeatherData.price_arrival_correlation > 0 ? "+" : ""}{arrivalsWeatherData.price_arrival_correlation}
                    <span style={{ fontSize: "0.75rem", color: "var(--text-dim)", marginLeft: "8px", fontWeight: 400 }}>
                      {arrivalsWeatherData.correlation_significance}
                    </span>
                  </div>
                  <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "6px" }}>
                    {arrivalsWeatherData.correlation_interpretation}
                  </p>
                </div>
              ) : (
                <div style={{ marginTop: "12px", fontSize: "0.8rem", color: "var(--text-dim)" }}>
                  {arrivalsWeatherData.correlation_interpretation}
                </div>
              )}
            </div>

            {/* Weather Integration */}
            <div style={{ background: "rgba(255,255,255,0.02)", padding: "16px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-color)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <CloudRain size={16} style={{ color: "var(--indigo-500)" }} />
                  <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#fff" }}>Agro-Meteorological Archive</span>
                </div>
                <span className={`badge ${arrivalsWeatherData.weather_available ? "badge-indigo" : "badge-amber"}`} style={{ fontSize: "0.65rem" }}>
                  {arrivalsWeatherData.weather_status.replaceAll("_", " ")}
                </span>
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-dim)", marginTop: "4px" }}>
                Source: {arrivalsWeatherData.weather_source} · Status: {arrivalsWeatherData.weather_status}
              </div>
              {arrivalsWeatherData.weather_location && (
                <div style={{ fontSize: "0.72rem", color: "var(--text-dim)", marginTop: "6px" }}>
                  Location metadata: {arrivalsWeatherData.weather_location.name} ({arrivalsWeatherData.weather_location.latitude.toFixed(4)}, {arrivalsWeatherData.weather_location.longitude.toFixed(4)}). {arrivalsWeatherData.weather_location.coordinate_precision}.
                </div>
              )}

              <div style={{ marginTop: "12px", background: "rgba(0,0,0,0.25)", padding: "12px", borderRadius: "var(--radius-sm)", fontSize: "0.75rem", color: "var(--text-muted)", lineHeight: 1.5 }}>
                {arrivalsWeatherData.weather_data_notes}
              </div>
              {arrivalsWeatherData.weather_observations.length > 0 && (
                <div style={{ marginTop: "12px" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-dim)", marginBottom: "6px" }}>
                    Retrieved weather on market-observation dates (latest 7 shown; °C and mm)
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr 1fr 1fr", gap: "6px", fontSize: "0.72rem" }}>
                    <strong>Date</strong><strong>Max °C</strong><strong>Min °C</strong><strong>Precip. mm</strong>
                    {arrivalsWeatherData.weather_observations.slice(-7).map((day) => (
                      <React.Fragment key={day.observation_date}>
                        <span>{day.observation_date}</span>
                        <span>{day.temperature_max_c ?? "Missing"}</span>
                        <span>{day.temperature_min_c ?? "Missing"}</span>
                        <span>{day.precipitation_mm ?? "Missing"}</span>
                      </React.Fragment>
                    ))}
                  </div>
                  {arrivalsWeatherData.weather_attribution_url && (
                    <div style={{ marginTop: "8px", fontSize: "0.7rem", color: "var(--text-dim)" }}>
                      Weather and gridded reanalysis data © Open-Meteo, CC BY 4.0. <a href={arrivalsWeatherData.weather_attribution_url} target="_blank" rel="noreferrer">Source and attribution</a>.
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 7. Historical Transaction Table */}
      <div className="glass-card">
        {/* Header & Controls */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px", flexWrap: "wrap", gap: "14px" }}>
          <div>
            <h3 style={{ fontSize: "1.05rem", fontWeight: 700, color: "var(--text-main)" }}>
              Individual Mandi Transaction Records
            </h3>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "2px" }}>
              Showing {filteredObservations.length} of {observations.length} recorded market transactions
            </p>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "10px", fontSize: "0.8rem" }}>
            <span style={{ color: "var(--text-dim)" }}>Price Unit:</span>
            <span className="mono" style={{ color: "var(--emerald-400)", fontWeight: 700 }}>
              ₹ / Quintal (100 kg)
            </span>
          </div>
        </div>

        {/* Filter Controls Row */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap", marginBottom: "18px", padding: "12px 14px", background: "rgba(0, 0, 0, 0.2)", borderRadius: "var(--radius-sm)" }}>
          {/* Search Input */}
          <div style={{ flex: 1, minWidth: "180px" }}>
            <input
              type="text"
              placeholder="Search date, mandi, district, variety..."
              className="text-input"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ width: "100%", fontSize: "0.85rem" }}
            />
          </div>

          {/* Source Filter */}
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <Database size={14} style={{ color: "var(--text-dim)" }} />
            <select
              className="select-input"
              value={selectedSource}
              onChange={(e) => setSelectedSource(e.target.value)}
              style={{ fontSize: "0.8rem" }}
            >
              <option value="ALL">All Sources</option>
              <option value="OFFICIAL_GOV_API">Official data.gov.in</option>
              <option value="USER_CSV_IMPORT">User CSV Import</option>
              <option value="DEMO_SEED_DATA">Demonstration Data</option>
            </select>
          </div>

          {/* State Filter */}
          {filterOptions?.states && filterOptions.states.length > 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>State:</span>
              <select
                className="select-input"
                value={selectedState}
                onChange={(e) => setSelectedState(e.target.value)}
                style={{ fontSize: "0.8rem" }}
              >
                <option value="ALL">All States</option>
                {filterOptions.states.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
          )}

          {/* District Filter */}
          {availableDistricts.length > 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>District:</span>
              <select
                className="select-input"
                value={selectedDistrict}
                onChange={(e) => setSelectedDistrict(e.target.value)}
                style={{ fontSize: "0.8rem" }}
              >
                <option value="ALL">All Districts</option>
                {availableDistricts.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>
          )}

          {/* Sort Toggle */}
          <button
            className="btn btn-secondary"
            onClick={() => setSortAsc(!sortAsc)}
            style={{ padding: "6px 12px", fontSize: "0.8rem" }}
          >
            {sortAsc ? <ArrowUp size={14} /> : <ArrowDown size={14} />}
            <span>{sortAsc ? "Oldest First" : "Latest First"}</span>
          </button>

          {/* Reset Filters */}
          {(searchTerm || selectedSource !== "ALL" || selectedState !== "ALL" || selectedDistrict !== "ALL") && (
            <button
              className="btn btn-secondary"
              onClick={() => {
                setSearchTerm("");
                setSelectedSource("ALL");
                setSelectedState("ALL");
                setSelectedDistrict("ALL");
              }}
              style={{ padding: "6px 10px", fontSize: "0.75rem", color: "var(--rose-400)" }}
            >
              Clear Filters
            </button>
          )}
        </div>

        {/* Data Table */}
        <div className="table-responsive">
          <table className="modern-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>State &amp; District</th>
                <th>Market / Mandi</th>
                <th>Variety</th>
                <th>Modal Price</th>
                <th>Min / Max Range</th>
                <th>Arrivals (Qtl)</th>
                <th>Unit</th>
                <th>Data Source &amp; Reliability</th>
              </tr>
            </thead>
            <tbody>
              {filteredObservations.map((obs) => {
                const badge = getSourceBadge(obs.source);
                return (
                  <tr key={obs.id}>
                    <td className="mono" style={{ fontWeight: 600 }}>{obs.observation_date}</td>
                    <td>
                      <div>{obs.state}</div>
                      {obs.district && obs.district !== "General" && (
                        <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>{obs.district}</div>
                      )}
                    </td>
                    <td style={{ fontWeight: 600, color: "var(--text-main)" }}>{obs.market}</td>
                    <td style={{ color: "var(--text-muted)" }}>{obs.variety || "Standard"}</td>
                    <td className="mono" style={{ fontWeight: 700, color: "var(--emerald-400)", fontSize: "0.95rem" }}>
                      ₹{obs.modal_price.toLocaleString("en-IN")}
                    </td>
                    <td className="mono" style={{ color: "var(--text-dim)", fontSize: "0.8rem" }}>
                      {obs.min_price && obs.max_price
                        ? `₹${obs.min_price} - ₹${obs.max_price}`
                        : obs.min_price
                        ? `≥ ₹${obs.min_price}`
                        : "--"}
                    </td>
                    <td className="mono">
                      {obs.arrivals_in_qtl ? obs.arrivals_in_qtl.toLocaleString("en-IN") : "--"}
                    </td>
                    <td style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
                      {obs.unit || "Rs/Quintal"}
                    </td>
                    <td>
                      <span className={badge.className} style={{ fontSize: "0.65rem", padding: "2px 8px" }} title={badge.description}>
                        {badge.label}
                      </span>
                    </td>
                  </tr>
                );
              })}

              {filteredObservations.length === 0 && (
                <tr>
                  <td colSpan={9} style={{ textAlign: "center", padding: "40px", color: "var(--text-dim)" }}>
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "10px" }}>
                      <div>No market observations match your filter criteria.</div>
                      {onNavigateTab && (
                        <button
                          className="btn btn-primary"
                          onClick={() => onNavigateTab("data_sources")}
                          style={{ fontSize: "0.8rem", marginTop: "4px" }}
                        >
                          <FileSpreadsheet size={14} />
                          <span>Import Agmarknet CSV Data</span>
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
