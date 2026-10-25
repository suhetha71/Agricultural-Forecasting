import React, { useState, useMemo } from "react";
import { MarketObservation, ForecastPoint } from "../types";
import { BarChart2, Info, Eye, EyeOff } from "lucide-react";

interface InteractiveChartProps {
  historicalData: MarketObservation[];
  forecastData?: ForecastPoint[];
  title?: string;
  subtitle?: string;
  unit?: string;
  isLoading?: boolean;
}

export const InteractiveChart: React.FC<InteractiveChartProps> = ({
  historicalData,
  forecastData = [],
  title = "Price Trend & Forecast Horizon",
  subtitle = "Observed Agmarknet daily modal transactions vs empirical time-series forecasts",
  unit = "₹/Quintal",
  isLoading = false,
}) => {
  const [horizonFilter, setHorizonFilter] = useState<"ALL" | "30D" | "15D" | "7D">("ALL");
  const [showConfidenceBands, setShowConfidenceBands] = useState(true);
  const [showMinMax, setShowMinMax] = useState(true);
  const [hoveredPoint, setHoveredPoint] = useState<{
    date: string;
    price: number;
    type: "historical" | "forecast";
    minPrice?: number | null;
    maxPrice?: number | null;
    ciLower?: number | null;
    ciUpper?: number | null;
    x: number;
    y: number;
  } | null>(null);

  // 1. Prepare and sort historical points chronologically
  const sortedHistory = useMemo(() => {
    return [...historicalData].sort(
      (a, b) => new Date(a.observation_date).getTime() - new Date(b.observation_date).getTime()
    );
  }, [historicalData]);

  // 2. Filter forecast points by selected horizon
  const filteredForecast = useMemo(() => {
    if (!forecastData || forecastData.length === 0) return [];
    if (horizonFilter === "7D") return forecastData.filter((f) => f.horizon_days <= 7);
    if (horizonFilter === "15D") return forecastData.filter((f) => f.horizon_days <= 15);
    return forecastData; // 30D or ALL
  }, [forecastData, horizonFilter]);

  // Combine points to calculate bounds
  const hasData = sortedHistory.length > 0;

  // Calculate coordinate mapping
  const width = 860;
  const height = 360;
  const padding = { top: 30, right: 40, bottom: 45, left: 65 };

  const chartData = useMemo(() => {
    if (!hasData) return null;

    // Collect all price values to compute Y axis scale
    const allPrices: number[] = [];
    sortedHistory.forEach((h) => {
      allPrices.push(h.modal_price);
      if (h.min_price) allPrices.push(h.min_price);
      if (h.max_price) allPrices.push(h.max_price);
    });

    filteredForecast.forEach((f) => {
      allPrices.push(f.predicted_price);
      if (f.lower_ci_95) allPrices.push(f.lower_ci_95);
      if (f.upper_ci_95) allPrices.push(f.upper_ci_95);
    });

    const minPrice = Math.max(0, Math.floor(Math.min(...allPrices) * 0.92));
    const maxPrice = Math.ceil(Math.max(...allPrices) * 1.08);

    const totalDays = sortedHistory.length + filteredForecast.length;
    const xStep = (width - padding.left - padding.right) / Math.max(1, totalDays - 1);

    const getY = (price: number) => {
      const ratio = (price - minPrice) / Math.max(1, maxPrice - minPrice);
      return height - padding.bottom - ratio * (height - padding.top - padding.bottom);
    };

    // Build historical points
    const histPoints = sortedHistory.map((item, idx) => {
      const x = padding.left + idx * xStep;
      const y = getY(item.modal_price);
      return { ...item, x, y };
    });

    // Build forecast points continuing from last historical index
    const startIndex = sortedHistory.length;
    const fcPoints = filteredForecast.map((item, idx) => {
      const x = padding.left + (startIndex + idx) * xStep;
      const y = getY(item.predicted_price);
      const yLower95 = item.lower_ci_95 ? getY(item.lower_ci_95) : y;
      const yUpper95 = item.upper_ci_95 ? getY(item.upper_ci_95) : y;
      return { ...item, x, y, yLower95, yUpper95 };
    });

    return {
      minPrice,
      maxPrice,
      histPoints,
      fcPoints,
      getY,
    };
  }, [hasData, sortedHistory, filteredForecast]);

  if (isLoading) {
    return (
      <div className="glass-card" style={{ height: "420px", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ textAlign: "center" }}>
          <div
            style={{
              width: "36px",
              height: "36px",
              border: "3px solid var(--border-subtle)",
              borderTopColor: "var(--emerald-500)",
              borderRadius: "50%",
              animation: "spin 1s linear infinite",
              margin: "0 auto 16px",
            }}
          />
          <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>Computing time-series statistics...</p>
        </div>
      </div>
    );
  }

  if (!hasData) {
    return (
      <div className="glass-card" style={{ padding: "48px 24px", textAlign: "center" }}>
        <div
          style={{
            width: "56px",
            height: "56px",
            borderRadius: "14px",
            background: "rgba(255, 255, 255, 0.04)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            margin: "0 auto 16px",
            color: "var(--text-dim)",
          }}
        >
          <BarChart2 size={28} />
        </div>
        <h3 style={{ fontSize: "1.1rem", fontWeight: 600, color: "var(--text-main)", marginBottom: "8px" }}>
          No Observation Records Loaded
        </h3>
        <p style={{ color: "var(--text-muted)", fontSize: "0.875rem", maxWidth: "480px", margin: "0 auto 20px" }}>
          Select a commodity and mandi with transaction records or upload a verified Agmarknet CSV from the Data Sources section to generate charts.
        </p>
      </div>
    );
  }

  const { minPrice, maxPrice, histPoints, fcPoints, getY } = chartData!;

  // Generate SVG path strings
  const histPath = histPoints.reduce((acc, p, i) => `${acc} ${i === 0 ? "M" : "L"} ${p.x} ${p.y}`, "");

  let forecastPath = "";
  if (fcPoints.length > 0 && histPoints.length > 0) {
    const lastHist = histPoints[histPoints.length - 1];
    forecastPath = `M ${lastHist.x} ${lastHist.y} ` + fcPoints.map((p) => `L ${p.x} ${p.y}`).join(" ");
  }

  // Shaded polygon for the residual-based 95% forecast range
  let ciPolygonPath = "";
  if (fcPoints.length > 0 && histPoints.length > 0) {
    const lastHist = histPoints[histPoints.length - 1];
    const topPoints = [`M ${lastHist.x} ${lastHist.y}`].concat(fcPoints.map((p) => `L ${p.x} ${p.yUpper95}`));
    const bottomPoints = fcPoints
      .slice()
      .reverse()
      .map((p) => `L ${p.x} ${p.yLower95}`)
      .concat([`L ${lastHist.x} ${lastHist.y}`, "Z"]);
    ciPolygonPath = topPoints.join(" ") + " " + bottomPoints.join(" ");
  }

  // Generate 5 grid Y-ticks
  const yTicks = [0, 0.25, 0.5, 0.75, 1.0].map((ratio) => {
    const val = Math.round(minPrice + ratio * (maxPrice - minPrice));
    const y = getY(val);
    return { val, y };
  });

  return (
    <div className="glass-card" style={{ position: "relative" }}>
      {/* Chart Header & Controls */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: "20px",
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        <div>
          <h3 style={{ fontSize: "1.05rem", fontWeight: 700, color: "var(--text-main)" }}>{title}</h3>
          <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "2px" }}>{subtitle}</p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
          {/* Horizon Toggles */}
          <div
            style={{
              display: "flex",
              background: "rgba(0, 0, 0, 0.3)",
              borderRadius: "var(--radius-sm)",
              padding: "2px",
              border: "1px solid var(--border-subtle)",
            }}
          >
            {(["ALL", "30D", "15D", "7D"] as const).map((h) => (
              <button
                key={h}
                onClick={() => setHorizonFilter(h)}
                style={{
                  background: horizonFilter === h ? "var(--emerald-600)" : "transparent",
                  color: horizonFilter === h ? "#fff" : "var(--text-muted)",
                  border: "none",
                  padding: "4px 10px",
                  borderRadius: "6px",
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                }}
              >
                {h}
              </button>
            ))}
          </div>

          {/* Toggle Confidence Bands */}
          <button
            className="btn btn-secondary"
            onClick={() => setShowConfidenceBands(!showConfidenceBands)}
            style={{ padding: "4px 10px", fontSize: "0.75rem" }}
            title="Toggle 95% residual-based forecast range"
          >
            {showConfidenceBands ? <Eye size={12} /> : <EyeOff size={12} />}
            <span>Confidence Band</span>
          </button>
        </div>
      </div>

      {/* SVG Canvas Container */}
      <div style={{ width: "100%", overflowX: "auto" }}>
        <svg
          viewBox={`0 0 ${width} ${height}`}
          style={{ width: "100%", height: "auto", minWidth: "650px", overflow: "visible" }}
        >
          <defs>
            <linearGradient id="histGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
            </linearGradient>
            <linearGradient id="ciGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#6366f1" stopOpacity="0.18" />
              <stop offset="100%" stopColor="#6366f1" stopOpacity="0.05" />
            </linearGradient>
          </defs>

          {/* Grid Lines & Y Axis Labels */}
          {yTicks.map((tick, i) => (
            <g key={i}>
              <line
                x1={padding.left}
                y1={tick.y}
                x2={width - padding.right}
                y2={tick.y}
                stroke="rgba(255, 255, 255, 0.06)"
                strokeDasharray="4 4"
              />
              <text
                x={padding.left - 12}
                y={tick.y + 4}
                textAnchor="end"
                fontSize="11"
                fill="var(--text-dim)"
                fontFamily="var(--font-mono)"
              >
                ₹{tick.val}
              </text>
            </g>
          ))}

          {/* Shaded Confidence Band (Forecast) */}
          {showConfidenceBands && ciPolygonPath && (
            <path d={ciPolygonPath} fill="url(#ciGradient)" />
          )}

          {/* Historical Observed Path */}
          <path d={histPath} fill="none" stroke="#10b981" strokeWidth="2.5" strokeLinecap="round" />

          {/* Forecast Path (Dashed) */}
          {forecastPath && (
            <path
              d={forecastPath}
              fill="none"
              stroke="#818cf8"
              strokeWidth="2.5"
              strokeDasharray="6 4"
              strokeLinecap="round"
            />
          )}

          {/* Historical Interactive Hover Nodes */}
          {histPoints.map((p, idx) => (
            <circle
              key={`h-${idx}`}
              cx={p.x}
              cy={p.y}
              r={hoveredPoint?.date === p.observation_date ? 6 : 3.5}
              fill="#10b981"
              stroke="#0a0f1d"
              strokeWidth="2"
              style={{ cursor: "pointer", transition: "r 0.15s ease" }}
              onMouseEnter={() =>
                setHoveredPoint({
                  date: p.observation_date,
                  price: p.modal_price,
                  type: "historical",
                  minPrice: p.min_price,
                  maxPrice: p.max_price,
                  x: p.x,
                  y: p.y,
                })
              }
              onMouseLeave={() => setHoveredPoint(null)}
            />
          ))}

          {/* Forecast Interactive Hover Nodes */}
          {fcPoints.map((p, idx) => (
            <circle
              key={`f-${idx}`}
              cx={p.x}
              cy={p.y}
              r={hoveredPoint?.date === p.target_date ? 6 : 4}
              fill="#818cf8"
              stroke="#0a0f1d"
              strokeWidth="2"
              style={{ cursor: "pointer", transition: "r 0.15s ease" }}
              onMouseEnter={() =>
                setHoveredPoint({
                  date: p.target_date,
                  price: p.predicted_price,
                  type: "forecast",
                  ciLower: p.lower_ci_95,
                  ciUpper: p.upper_ci_95,
                  x: p.x,
                  y: p.y,
                })
              }
              onMouseLeave={() => setHoveredPoint(null)}
            />
          ))}

          {/* Date Axis (Selected Labels) */}
          {histPoints
            .filter((_, i) => i % Math.max(1, Math.floor(histPoints.length / 5)) === 0)
            .map((p, i) => (
              <text
                key={i}
                x={p.x}
                y={height - 15}
                textAnchor="middle"
                fontSize="11"
                fill="var(--text-dim)"
                fontFamily="var(--font-mono)"
              >
                {p.observation_date.slice(5)}
              </text>
            ))}

          {fcPoints
            .filter((_, i) => i === 0 || i === fcPoints.length - 1)
            .map((p, i) => (
              <text
                key={`f-label-${i}`}
                x={p.x}
                y={height - 15}
                textAnchor="middle"
                fontSize="11"
                fill="var(--indigo-500)"
                fontWeight="600"
                fontFamily="var(--font-mono)"
              >
                +{p.horizon_days}d
              </text>
            ))}
        </svg>

        {/* Hover Tooltip Overlay */}
        {hoveredPoint && (
          <div
            style={{
              position: "absolute",
              top: `${Math.max(10, hoveredPoint.y - 85)}px`,
              left: `${Math.min(width - 180, Math.max(20, hoveredPoint.x - 70))}px`,
              background: "rgba(17, 24, 39, 0.95)",
              border: `1px solid ${hoveredPoint.type === "historical" ? "var(--emerald-500)" : "var(--indigo-500)"}`,
              borderRadius: "var(--radius-sm)",
              padding: "10px 14px",
              boxShadow: "0 8px 24px rgba(0, 0, 0, 0.4)",
              pointerEvents: "none",
              zIndex: 30,
              fontSize: "0.75rem",
              backdropFilter: "blur(8px)",
            }}
          >
            <div style={{ color: "var(--text-muted)", marginBottom: "4px", fontWeight: 500 }}>
              {hoveredPoint.date} (
              {hoveredPoint.type === "historical" ? "Actual Agmarknet" : "Empirical Forecast"})
            </div>
            <div style={{ fontSize: "1rem", fontWeight: 700, color: "#fff", marginBottom: "2px" }}>
              ₹{hoveredPoint.price.toLocaleString("en-IN")}{" "}
              <span style={{ fontSize: "0.7rem", color: "var(--text-dim)", fontWeight: 400 }}>{unit}</span>
            </div>
            {hoveredPoint.type === "historical" && hoveredPoint.minPrice && hoveredPoint.maxPrice && (
              <div style={{ color: "var(--text-dim)", fontSize: "0.7rem" }}>
                Range: ₹{hoveredPoint.minPrice} - ₹{hoveredPoint.maxPrice}
              </div>
            )}
            {hoveredPoint.type === "forecast" && hoveredPoint.ciLower && hoveredPoint.ciUpper && (
              <div style={{ color: "var(--indigo-500)", fontSize: "0.7rem" }}>
                95% CI: ₹{hoveredPoint.ciLower} - ₹{hoveredPoint.ciUpper}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Legend */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: "24px",
          marginTop: "16px",
          paddingTop: "12px",
          borderTop: "1px solid var(--border-subtle)",
          fontSize: "0.8rem",
          color: "var(--text-muted)",
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ width: "16px", height: "3px", backgroundColor: "#10b981", borderRadius: "2px" }} />
          <span>Observed Modal Price</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span
            style={{
              width: "16px",
              height: "3px",
              backgroundColor: "#818cf8",
              borderTop: "2px dashed #818cf8",
            }}
          />
          <span>Forecast Horizon</span>
        </div>
        {showConfidenceBands && (
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span
              style={{
                width: "14px",
                height: "14px",
                backgroundColor: "rgba(99, 102, 241, 0.2)",
                border: "1px solid rgba(99, 102, 241, 0.4)",
                borderRadius: "3px",
              }}
            />
            <span>95% residual-based range</span>
          </div>
        )}
      </div>
    </div>
  );
};
