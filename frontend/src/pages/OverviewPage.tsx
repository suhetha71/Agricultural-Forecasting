import React from "react";
import {
  TrendingUp,
  DollarSign,
  Calendar,
  Layers,
  ArrowRight,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { MetricCard } from "../components/MetricCard";
import { InteractiveChart } from "../components/InteractiveChart";
import {
  MarketSummary,
  MarketObservation,
  ForecastResponse,
  DecisionRecommendation,
} from "../types";

interface OverviewPageProps {
  summary: MarketSummary | null;
  observations: MarketObservation[];
  forecast: ForecastResponse | null;
  decision: DecisionRecommendation | null;
  isLoading: boolean;
  onNavigateTab: (tab: string) => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({
  summary,
  observations,
  forecast,
  decision,
  isLoading,
  onNavigateTab,
}) => {
  const currentPrice = summary?.latest_modal_price ?? 0;
  const change7d = summary?.price_change_7d_pct;
  const range30d =
    summary?.min_modal_price_30d && summary?.max_modal_price_30d
      ? `₹${summary.min_modal_price_30d} - ₹${summary.max_modal_price_30d}`
      : "N/A";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "28px" }}>
      {/* Decision Engine Alert Banner */}
      {decision && (
        <div
          style={{
            background:
              decision.recommended_action === "SELL NOW"
                ? "linear-gradient(135deg, rgba(239, 68, 68, 0.12) 0%, rgba(17, 24, 39, 0.8) 100%)"
                : decision.recommended_action.includes("WAIT")
                ? "linear-gradient(135deg, rgba(245, 158, 11, 0.12) 0%, rgba(17, 24, 39, 0.8) 100%)"
                : "linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(17, 24, 39, 0.8) 100%)",
            border: `1px solid ${
              decision.recommended_action === "SELL NOW"
                ? "rgba(239, 68, 68, 0.3)"
                : decision.recommended_action.includes("WAIT")
                ? "rgba(245, 158, 11, 0.3)"
                : "rgba(16, 185, 129, 0.3)"
            }`,
            borderRadius: "var(--radius-lg)",
            padding: "20px 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "16px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <div
              style={{
                width: "48px",
                height: "48px",
                borderRadius: "12px",
                background: "rgba(255, 255, 255, 0.05)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color:
                  decision.recommended_action === "SELL NOW"
                    ? "var(--rose-500)"
                    : decision.recommended_action.includes("WAIT")
                    ? "var(--amber-500)"
                    : "var(--emerald-400)",
              }}
            >
              <Zap size={24} />
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 700 }}>
                  Active Selling Decision Engine
                </span>
                <span
                  className={`badge ${
                    decision.recommended_action === "SELL NOW"
                      ? "badge-rose"
                      : decision.recommended_action.includes("WAIT")
                      ? "badge-amber"
                      : "badge-emerald"
                  }`}
                  style={{ fontSize: "0.75rem", padding: "3px 10px" }}
                >
                  {decision.recommended_action}
                </span>
              </div>
              <p style={{ fontSize: "0.9rem", color: "var(--text-main)", marginTop: "4px", maxWidth: "750px" }}>
                {decision.rationale}
              </p>
            </div>
          </div>

          <button
            className="btn btn-secondary"
            onClick={() => onNavigateTab("decision_support")}
            style={{ fontSize: "0.85rem" }}
          >
            <span>Open Decision Simulator</span>
            <ArrowRight size={14} />
          </button>
        </div>
      )}

      {/* Data Freshness & Provenance Status Banner */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 18px",
          background: "rgba(255, 255, 255, 0.02)",
          borderRadius: "var(--radius-md)",
          border: "1px solid var(--border-color)",
          flexWrap: "wrap",
          gap: "10px",
          fontSize: "0.82rem",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "16px", flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <Calendar size={15} style={{ color: "var(--emerald-400)" }} />
            <span style={{ color: "var(--text-muted)" }}>Latest Available Observation:</span>
            <span className="mono" style={{ fontWeight: 700, color: "var(--text-main)" }}>
              {summary?.latest_date || (observations.length > 0 ? observations[observations.length - 1].observation_date : "No records")}
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ color: "var(--text-muted)" }}>Update Cadence:</span>
            <span className="badge badge-indigo" style={{ fontSize: "0.7rem", padding: "2px 8px" }}>
              Daily Wholesale Mandi Reporting
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ color: "var(--text-muted)" }}>Current Series Source:</span>
            <span
              className={`badge ${
                summary?.source === "OFFICIAL_GOV_API"
                  ? "badge-emerald"
                  : summary?.source === "USER_CSV_IMPORT"
                  ? "badge-indigo"
                  : "badge-amber"
              }`}
              style={{ fontSize: "0.7rem", padding: "2px 8px" }}
            >
              {summary?.source === "OFFICIAL_GOV_API"
                ? "Official data.gov.in"
                : summary?.source === "USER_CSV_IMPORT"
                ? "User CSV Import"
                : "Demonstration Data"}
            </span>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ color: "var(--text-dim)", fontSize: "0.75rem" }}>Original Unit:</span>
          <span className="mono" style={{ color: "var(--text-muted)", fontSize: "0.75rem", fontWeight: 600 }}>
            ₹ / Quintal (100 kg)
          </span>
        </div>
      </div>

      {/* Empty State Guard if 0 records */}
      {observations.length === 0 && !isLoading ? (
        <div
          className="glass-card"
          style={{
            textAlign: "center",
            padding: "48px 24px",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "16px",
          }}
        >
          <div
            style={{
              width: "60px",
              height: "60px",
              borderRadius: "50%",
              background: "rgba(99, 102, 241, 0.15)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--indigo-500)",
            }}
          >
            <Layers size={30} />
          </div>
          <div>
            <h3 style={{ fontSize: "1.15rem", fontWeight: 700, color: "var(--text-main)" }}>
              No Observations Found for Selected Mandi &amp; Crop
            </h3>
            <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", maxWidth: "500px", marginTop: "6px" }}>
              There are currently no wholesale price records for {summary?.commodity || "this crop"} at {summary?.market || "this mandi"}. You can import authentic official Agmarknet CSV records or sync from data.gov.in.
            </p>
          </div>
          <button
            className="btn btn-primary"
            onClick={() => onNavigateTab("data_sources")}
            style={{ marginTop: "8px", fontSize: "0.85rem" }}
          >
            <span>Go to Data Ingestion &amp; CSV Upload</span>
            <ArrowRight size={14} />
          </button>
        </div>
      ) : (
        <>
          {/* Metric Cards Row */}
          <div className="grid-cols-4">
            <MetricCard
              label="Current Modal Price"
              value={currentPrice > 0 ? `₹${currentPrice.toLocaleString("en-IN")}` : "Loading..."}
              subtext="₹ / Quintal (Benchmark)"
              changePct={change7d}
              icon={DollarSign}
              badgeText="Daily Agmarknet"
              badgeVariant="emerald"
            />

            <MetricCard
              label="7-Day Price Shift"
              value={change7d !== undefined && change7d !== null ? `${change7d > 0 ? "+" : ""}${change7d}%` : "0.0%"}
              subtext="Rolling 7-day rate momentum"
              changePct={change7d}
              icon={TrendingUp}
              badgeText="Momentum"
              badgeVariant={change7d && change7d > 0 ? "emerald" : "amber"}
            />

            <MetricCard
              label="30-Day Trading Range"
              value={range30d}
              subtext="Min to Max modal price"
              icon={Calendar}
              badgeText="Spread"
              badgeVariant="indigo"
            />

            <MetricCard
              label="Historical Observations"
              value={summary?.total_records ?? observations.length}
              subtext="Recorded transaction days"
              icon={Layers}
              badgeText="Database Backed"
              badgeVariant="emerald"
            />
          </div>

          {/* Main Interactive Chart */}
          <InteractiveChart
            historicalData={observations}
            forecastData={forecast?.forecasts || []}
            title={`${summary?.commodity || "Crop"} Price Trajectory & 30-Day Horizon`}
            subtitle={`Observed wholesale prices at ${summary?.market || "Mandi"} with illustrative residual-based forecast ranges`}
            isLoading={isLoading}
          />
        </>
      )}

      {/* Bottom Insights Columns */}
      <div className="grid-cols-2">
        {/* Model Performance Snapshot */}
        <div className="glass-card">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }}>
            <h4 style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--text-main)" }}>
              Model Forecasting Architecture
            </h4>
            <span className="badge badge-emerald" style={{ fontSize: "0.7rem" }}>
              {forecast?.model_used || "No fitted model"}
            </span>
          </div>

          <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginBottom: "16px" }}>
            Predictions are generated via auto-regressive statistical smoothing and time-series decomposition. Real historical test holdouts evaluate errors before projecting future horizons.
          </p>

          {forecast?.metrics ? (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px", background: "rgba(0,0,0,0.25)", padding: "14px", borderRadius: "var(--radius-sm)" }}>
              <div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>Mean Absolute Error</div>
                <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "#fff", marginTop: "2px" }}>
                  ₹{forecast.metrics.mae} <span style={{ fontSize: "0.7rem", color: "var(--text-dim)" }}>/Qtl</span>
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>MAPE Error Rate</div>
                <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--emerald-400)", marginTop: "2px" }}>
                  {forecast.metrics.mape}%
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>Directional Accuracy</div>
                <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--indigo-500)", marginTop: "2px" }}>
                  {forecast.metrics.directional_accuracy_pct ?? "--"}%
                </div>
              </div>
            </div>
          ) : (
            <div style={{ padding: "12px", background: "rgba(0,0,0,0.2)", borderRadius: "var(--radius-sm)", color: "var(--text-dim)", fontSize: "0.8rem" }}>
              Holdout evaluation metrics available once time-series models converge.
            </div>
          )}

          <div style={{ marginTop: "16px", textAlign: "right" }}>
            <button
              className="btn btn-secondary"
              onClick={() => onNavigateTab("model_validation")}
              style={{ fontSize: "0.8rem", padding: "6px 12px" }}
            >
              <span>View Full Validation Report</span>
              <ArrowRight size={12} />
            </button>
          </div>
        </div>

        {/* Quick Navigation Cards */}
        <div className="glass-card">
          <h4 style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--text-main)", marginBottom: "16px" }}>
            Decision Support &amp; Analytics Tools
          </h4>
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            <div
              onClick={() => onNavigateTab("market_comparison")}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "12px 14px",
                background: "rgba(255,255,255,0.03)",
                borderRadius: "var(--radius-sm)",
                cursor: "pointer",
                transition: "background 0.2s ease",
              }}
            >
              <div>
                <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "#fff" }}>
                  Mandi Price Comparison
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
                  Compare nearby market rates and calculate transport net realization
                </div>
              </div>
              <ArrowRight size={16} style={{ color: "var(--emerald-400)" }} />
            </div>

            <div
              onClick={() => onNavigateTab("decision_support")}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "12px 14px",
                background: "rgba(255,255,255,0.03)",
                borderRadius: "var(--radius-sm)",
                cursor: "pointer",
                transition: "background 0.2s ease",
              }}
            >
              <div>
                <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "#fff" }}>
                  Sell vs. Wait vs. Store Simulator
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
                  Simulate crop storage fees, weight loss shrinkage, and holding profits
                </div>
              </div>
              <ArrowRight size={16} style={{ color: "var(--emerald-400)" }} />
            </div>

            <div
              onClick={() => onNavigateTab("data_sources")}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "12px 14px",
                background: "rgba(255,255,255,0.03)",
                borderRadius: "var(--radius-sm)",
                cursor: "pointer",
                transition: "background 0.2s ease",
              }}
            >
              <div>
                <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "#fff" }}>
                  Data Management &amp; CSV Ingestion
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
                  Upload official Agmarknet CSV files with duplicate avoidance
                </div>
              </div>
              <ArrowRight size={16} style={{ color: "var(--emerald-400)" }} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
