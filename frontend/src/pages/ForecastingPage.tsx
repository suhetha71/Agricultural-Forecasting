import React, { useState } from "react";
import { ForecastModelPreference, ForecastResponse, MarketObservation } from "../types";
import { InteractiveChart } from "../components/InteractiveChart";
import { TrendingUp, ShieldAlert, Cpu, Calendar, Target } from "lucide-react";

interface ForecastingPageProps {
  forecast: ForecastResponse | null;
  observations: MarketObservation[];
  isLoading: boolean;
  onRefreshForecast: (model: ForecastModelPreference, horizon: number) => void;
}

export const ForecastingPage: React.FC<ForecastingPageProps> = ({
  forecast,
  observations,
  isLoading,
  onRefreshForecast,
}) => {
  const [selectedHorizon, setSelectedHorizon] = useState<number>(30);
  const [selectedModel, setSelectedModel] = useState<ForecastModelPreference>("auto");

  const handleApply = () => {
    onRefreshForecast(selectedModel, selectedHorizon);
  };

  const points = forecast?.forecasts || [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "28px" }}>
      {/* Control Bar Card */}
      <div
        className="glass-card"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "16px",
        }}
      >
        <div>
          <h3 style={{ fontSize: "1.05rem", fontWeight: 700, color: "var(--text-main)" }}>
            Forecasting Configuration
          </h3>
          <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "2px" }}>
            Select empirical time-series algorithm and target horizon
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "14px", flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Model Architecture:</span>
            <select
              className="select-input"
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value as ForecastModelPreference)}
            >
              <option value="auto">Auto (by history length)</option>
              <option value="holt-winters">Holt-Winters Triple Exponential (21+ observations)</option>
            </select>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Horizon:</span>
            <select
              className="select-input"
              value={selectedHorizon}
              onChange={(e) => setSelectedHorizon(Number(e.target.value))}
            >
              <option value={7}>7-Day Short-Term</option>
              <option value={15}>15-Day Mid-Term</option>
              <option value={30}>30-Day Storage-Horizon</option>
            </select>
          </div>

          <button className="btn btn-primary" onClick={handleApply} disabled={isLoading}>
            <span>Run Model Engine</span>
          </button>
        </div>
      </div>

      {/* Main Chart with Shaded Bounds */}
      <InteractiveChart
        historicalData={observations}
        forecastData={points}
        title={`Forecast Trajectory for ${forecast?.commodity || "Crop"} (${forecast?.market || "Mandi"})`}
        subtitle={`Fitted with ${forecast?.model_used || "Statistical Engine"} — ${selectedHorizon}-day horizon`}
        isLoading={isLoading}
      />

      {/* Forecast Horizons Breakdown Table */}
      <div className="glass-card">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }}>
          <div>
            <h4 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-main)" }}>
              Target Date Forecast Points &amp; Residual-Based Ranges
            </h4>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
              Illustrative 80% and 95% ranges derived from final-fit residual spread; coverage is not empirically calibrated.
            </p>
          </div>
          <span className="badge badge-emerald">
            {points.length} Daily Projections
          </span>
        </div>

        <div className="table-responsive">
          <table className="modern-table">
            <thead>
              <tr>
                <th>Horizon</th>
                <th>Target Date</th>
                <th>Predicted Modal Rate</th>
                <th>80% Scaled Range</th>
                <th>95% Scaled Range</th>
                <th>Projected Shift vs Current</th>
              </tr>
            </thead>
            <tbody>
              {points.map((pt) => {
                const currentPrice = forecast?.last_observed_price || 0;
                const diff = currentPrice > 0 ? pt.predicted_price - currentPrice : 0;
                const diffPct = currentPrice > 0 ? ((diff / currentPrice) * 100).toFixed(1) : "0.0";
                return (
                  <tr key={pt.horizon_days}>
                    <td className="mono" style={{ fontWeight: 700, color: "var(--indigo-500)" }}>
                      +{pt.horizon_days} Days
                    </td>
                    <td className="mono">{pt.target_date}</td>
                    <td className="mono" style={{ fontWeight: 700, color: "#fff", fontSize: "0.95rem" }}>
                      ₹{pt.predicted_price.toLocaleString("en-IN")}
                    </td>
                    <td className="mono" style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
                      ₹{pt.lower_ci_80} — ₹{pt.upper_ci_80}
                    </td>
                    <td className="mono" style={{ color: "var(--indigo-500)", fontSize: "0.8rem" }}>
                      ₹{pt.lower_ci_95} — ₹{pt.upper_ci_95}
                    </td>
                    <td className="mono" style={{ fontWeight: 600 }}>
                      <span style={{ color: diff >= 0 ? "var(--emerald-400)" : "var(--rose-500)" }}>
                        {diff >= 0 ? `+₹${diff.toFixed(1)} (+${diffPct}%)` : `-₹${Math.abs(diff).toFixed(1)} (${diffPct}%)`}
                      </span>
                    </td>
                  </tr>
                );
              })}
              {points.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", padding: "36px", color: "var(--text-dim)" }}>
                    {forecast?.message || "No forecast data generated. Verify historical observations exist for this commodity."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Uncertainty Disclosure Banner */}
        <div style={{ marginTop: "16px", padding: "12px 16px", background: "rgba(255, 255, 255, 0.02)", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-color)", fontSize: "0.75rem", color: "var(--text-dim)", lineHeight: 1.5 }}>
          <strong>Forecast Uncertainty Disclosure:</strong> These ranges use the final fitted model's residual spread with a horizon scaling rule. They are illustrative and are <em>not</em> calibrated prediction intervals, empirical coverage guarantees, or a guaranteed range of future prices. Longer horizons (&gt; 14 days) carry greater exposure to unobserved weather events, policy tariffs, and APMC arrival surges. Validation metrics can be inspected in the <strong>Model Validation</strong> tab.
        </div>
      </div>
    </div>
  );
};
