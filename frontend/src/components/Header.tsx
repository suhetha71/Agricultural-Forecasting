import React from "react";
import { RefreshCw, Filter, ShieldCheck, MapPin } from "lucide-react";
import { FilterOptions } from "../types";

interface HeaderProps {
  currentTab: string;
  selectedCommodity: string;
  selectedMarket: string;
  filterOptions: FilterOptions;
  onCommodityChange: (commodity: string) => void;
  onMarketChange: (market: string) => void;
  onRefresh: () => void;
  isRefreshing: boolean;
}

const tabTitles: Record<string, string> = {
  overview: "Market Overview & Daily Market Intelligence",
  price_analysis: "Historical Price & Volatility Analysis",
  forecasting: "Empirical Price Forecasting & Confidence Bounds",
  market_comparison: "Multi-Mandi Arbitrage & Spatial Comparison",
  decision_support: "Sell vs. Wait vs. Store Economic Simulator",
  model_validation: "Model Evaluation & Holdout Backtesting",
  data_sources: "AGMARKNET Data Pipeline & CSV Management",
};

export const Header: React.FC<HeaderProps> = ({
  currentTab,
  selectedCommodity,
  selectedMarket,
  filterOptions,
  onCommodityChange,
  onMarketChange,
  onRefresh,
  isRefreshing,
}) => {
  return (
    <header className="top-header">
      <div>
        <h2 style={{ fontSize: "1.15rem", fontWeight: 700, color: "var(--text-main)" }}>
          {tabTitles[currentTab] || "Agricultural Forecasting"}
        </h2>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "2px" }}>
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Active Commodity:</span>
          <span className="badge badge-emerald" style={{ padding: "2px 8px", fontSize: "0.7rem" }}>
            {selectedCommodity}
          </span>
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginLeft: "4px" }}>Benchmark Mandi:</span>
          <span className="badge badge-indigo" style={{ padding: "2px 8px", fontSize: "0.7rem" }}>
            {selectedMarket}
          </span>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        {/* Global Selectors */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <Filter size={14} style={{ color: "var(--text-dim)" }} />
          <select
            className="select-input"
            value={selectedCommodity}
            onChange={(e) => onCommodityChange(e.target.value)}
            style={{ minWidth: "130px" }}
          >
            {filterOptions.commodities.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <MapPin size={14} style={{ color: "var(--text-dim)" }} />
          <select
            className="select-input"
            value={selectedMarket}
            onChange={(e) => onMarketChange(e.target.value)}
            style={{ minWidth: "140px" }}
          >
            {filterOptions.markets.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>

        {/* Refresh Action */}
        <button
          className="btn btn-secondary"
          onClick={onRefresh}
          disabled={isRefreshing}
          style={{ padding: "8px 12px" }}
          title="Refresh Data & Calculations"
        >
          <RefreshCw
            size={16}
            style={{
              animation: isRefreshing ? "spin 1s linear infinite" : "none",
            }}
          />
          <span style={{ fontSize: "0.8rem" }}>{isRefreshing ? "Updating..." : "Refresh"}</span>
        </button>
      </div>
      <style>{`
        @keyframes spin {
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </header>
  );
};
