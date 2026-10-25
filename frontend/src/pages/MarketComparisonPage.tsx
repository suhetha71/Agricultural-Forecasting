import React, { useState, useEffect } from "react";
import {
  MarketComparisonResponse,
  MarketComparisonItemDetailed,
} from "../types";
import { api } from "../services/api";
import {
  GitCompare,
  MapPin,
  Truck,
  TrendingUp,
  Award,
  AlertTriangle,
  Info,
  Calendar,
  Layers,
  Scale,
  DollarSign,
  ShieldAlert,
} from "lucide-react";

interface MarketComparisonPageProps {
  selectedCommodity: string;
  selectedMarket: string;
}

export const MarketComparisonPage: React.FC<MarketComparisonPageProps> = ({
  selectedCommodity,
  selectedMarket,
}) => {
  // Parameters State
  const [commodity, setCommodity] = useState<string>(selectedCommodity || "Onion");
  const [variety, setVariety] = useState<string>("");
  const [quantity, setQuantity] = useState<number>(100);
  const [quantityUnit, setQuantityUnit] = useState<"kg" | "quintal" | "tonne">("quintal");
  const [stateFilter, setStateFilter] = useState<string>("");
  const [horizonDays, setHorizonDays] = useState<number>(0); // 0 = spot, 7, 14, 30

  // Cost Inputs
  const [costPerKm, setCostPerKm] = useState<number>(1.5);
  const [fixedTransportFee, setFixedTransportFee] = useState<number>(300);
  const [otherCostPerQtl, setOtherCostPerQtl] = useState<number>(10);
  const [otherCostFixed, setOtherCostFixed] = useState<number>(150);

  // Response State
  const [comparisonData, setComparisonData] = useState<MarketComparisonResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Sync if prop changes
  useEffect(() => {
    if (selectedCommodity) {
      setCommodity(selectedCommodity);
    }
  }, [selectedCommodity]);

  const fetchComparisons = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await api.compareMarketsIntelligently({
        commodity,
        variety: variety.trim() ? variety.trim() : null,
        quantity: Math.max(0.1, quantity),
        quantity_unit: quantityUnit,
        state: stateFilter.trim() ? stateFilter.trim() : null,
        horizon_days: horizonDays,
        transport_cost_per_km_qtl: costPerKm,
        transport_fixed_fee: fixedTransportFee,
        other_cost_per_qtl: otherCostPerQtl,
        other_cost_fixed: otherCostFixed,
        reference_market: selectedMarket,
      });
      setComparisonData(res);
    } catch (err: any) {
      console.error("Failed to fetch market comparisons:", err);
      setErrorMessage(err.message || "Failed to compare markets.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchComparisons();
  }, [
    commodity,
    variety,
    quantity,
    quantityUnit,
    stateFilter,
    horizonDays,
    costPerKm,
    fixedTransportFee,
    otherCostPerQtl,
    otherCostFixed,
    selectedMarket,
  ]);

  const markets = comparisonData?.ranked_markets || [];
  const bestMarket = markets.length > 0 ? markets[0] : null;
  const maxGrossMarket = comparisonData?.max_gross_market
    ? markets.find((m) => m.market === comparisonData.max_gross_market)
    : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "28px" }}>
      {/* Header & Controls Card */}
      <div
        className="glass-card"
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "20px",
          padding: "24px",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "4px" }}>
              <GitCompare size={22} style={{ color: "var(--emerald-400)" }} />
              <h2 style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--text-main)" }}>
                Intelligent Regional Market Arbitrage Engine
              </h2>
            </div>
            <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
              Ranks agricultural mandis strictly by <strong>Estimated Net Return</strong> after deducting road transit freight and auction handling fees.
            </p>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span className="badge badge-emerald" style={{ fontSize: "0.8rem", padding: "4px 10px" }}>
              Benchmark: {selectedMarket || "Lasalgaon"}
            </span>
          </div>
        </div>

        {/* Filter Controls Row */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "16px",
            background: "rgba(15, 23, 42, 0.4)",
            padding: "18px",
            borderRadius: "var(--radius-md)",
            border: "1px solid rgba(255, 255, 255, 0.05)",
          }}
        >
          {/* Commodity */}
          <div>
            <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "6px", textTransform: "uppercase", fontWeight: 600 }}>
              Commodity
            </label>
            <select
              value={commodity}
              onChange={(e) => setCommodity(e.target.value)}
              style={{
                width: "100%",
                background: "var(--surface)",
                border: "1px solid var(--border-color)",
                borderRadius: "var(--radius-sm)",
                padding: "8px 12px",
                color: "#fff",
                fontSize: "0.85rem",
              }}
            >
              <option value="Onion">Onion</option>
              <option value="Wheat">Wheat</option>
              <option value="Tomato">Tomato</option>
              <option value="Potato">Potato</option>
              <option value="Cotton">Cotton</option>
              <option value="Soyabean">Soyabean</option>
              <option value="Mustard">Mustard</option>
            </select>
          </div>

          {/* Quantity & Unit */}
          <div>
            <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "6px", textTransform: "uppercase", fontWeight: 600 }}>
              Sale Volume &amp; Unit
            </label>
            <div style={{ display: "flex", gap: "6px" }}>
              <input
                type="number"
                min="1"
                step="5"
                value={quantity}
                onChange={(e) => setQuantity(Math.max(1, parseFloat(e.target.value) || 1))}
                style={{
                  flex: 1,
                  background: "var(--surface)",
                  border: "1px solid var(--border-color)",
                  borderRadius: "var(--radius-sm)",
                  padding: "8px 10px",
                  color: "#fff",
                  fontSize: "0.85rem",
                }}
              />
              <select
                value={quantityUnit}
                onChange={(e) => setQuantityUnit(e.target.value as any)}
                style={{
                  background: "var(--surface)",
                  border: "1px solid var(--border-color)",
                  borderRadius: "var(--radius-sm)",
                  padding: "8px 10px",
                  color: "#fff",
                  fontSize: "0.85rem",
                }}
              >
                <option value="quintal">Quintal (100 kg)</option>
                <option value="kg">Kilogram (kg)</option>
                <option value="tonne">Tonne (1,000 kg)</option>
              </select>
            </div>
          </div>

          {/* Horizon Selector */}
          <div>
            <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "6px", textTransform: "uppercase", fontWeight: 600 }}>
              Selling Horizon
            </label>
            <select
              value={horizonDays}
              onChange={(e) => setHorizonDays(parseInt(e.target.value))}
              style={{
                width: "100%",
                background: "var(--surface)",
                border: "1px solid var(--border-color)",
                borderRadius: "var(--radius-sm)",
                padding: "8px 12px",
                color: "#fff",
                fontSize: "0.85rem",
              }}
            >
              <option value={0}>Spot Market Today (Latest Observed)</option>
              <option value={7}>7-Day Forecast (Short Horizon)</option>
              <option value={14}>14-Day Forecast (Mid Horizon)</option>
              <option value={30}>30-Day Forecast (Storage Horizon)</option>
            </select>
          </div>

          {/* State Filter */}
          <div>
            <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "6px", textTransform: "uppercase", fontWeight: 600 }}>
              State Geographic Filter
            </label>
            <select
              value={stateFilter}
              onChange={(e) => setStateFilter(e.target.value)}
              style={{
                width: "100%",
                background: "var(--surface)",
                border: "1px solid var(--border-color)",
                borderRadius: "var(--radius-sm)",
                padding: "8px 12px",
                color: "#fff",
                fontSize: "0.85rem",
              }}
            >
              <option value="">All Regions</option>
              <option value="Maharashtra">Maharashtra</option>
              <option value="Punjab">Punjab</option>
              <option value="Karnataka">Karnataka</option>
              <option value="Uttar Pradesh">Uttar Pradesh</option>
              <option value="Gujarat">Gujarat</option>
              <option value="Madhya Pradesh">Madhya Pradesh</option>
              <option value="Rajasthan">Rajasthan</option>
            </select>
          </div>
        </div>

        {/* Transport & Cost Parameters Slider / Inputs */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: "16px",
            paddingTop: "12px",
            borderTop: "1px solid rgba(255, 255, 255, 0.05)",
          }}
        >
          {/* Freight Rate */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>
                Freight Rate
              </span>
              <span style={{ fontSize: "0.85rem", color: "var(--emerald-400)", fontWeight: 700 }}>
                ₹{costPerKm.toFixed(2)} / km / Qtl
              </span>
            </div>
            <input
              type="range"
              min="0.5"
              max="5.0"
              step="0.25"
              value={costPerKm}
              onChange={(e) => setCostPerKm(parseFloat(e.target.value))}
              style={{ width: "100%", accentColor: "var(--emerald-500)", cursor: "pointer" }}
            />
          </div>

          {/* Fixed Vehicle Fee */}
          <div>
            <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "6px", textTransform: "uppercase", fontWeight: 600 }}>
              Fixed Vehicle Mobilization (₹)
            </label>
            <input
              type="number"
              min="0"
              step="50"
              value={fixedTransportFee}
              onChange={(e) => setFixedTransportFee(Math.max(0, parseFloat(e.target.value) || 0))}
              style={{
                width: "100%",
                background: "var(--surface)",
                border: "1px solid var(--border-color)",
                borderRadius: "var(--radius-sm)",
                padding: "6px 10px",
                color: "#fff",
                fontSize: "0.85rem",
              }}
            />
          </div>

          {/* Mandi Handling Per Quintal */}
          <div>
            <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "6px", textTransform: "uppercase", fontWeight: 600 }}>
              Mandi Cess &amp; Handling (₹/Qtl)
            </label>
            <input
              type="number"
              min="0"
              step="2"
              value={otherCostPerQtl}
              onChange={(e) => setOtherCostPerQtl(Math.max(0, parseFloat(e.target.value) || 0))}
              style={{
                width: "100%",
                background: "var(--surface)",
                border: "1px solid var(--border-color)",
                borderRadius: "var(--radius-sm)",
                padding: "6px 10px",
                color: "#fff",
                fontSize: "0.85rem",
              }}
            />
          </div>

          {/* Fixed Gate Fee */}
          <div>
            <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "6px", textTransform: "uppercase", fontWeight: 600 }}>
              Gate Entry &amp; Weighbridge (₹)
            </label>
            <input
              type="number"
              min="0"
              step="25"
              value={otherCostFixed}
              onChange={(e) => setOtherCostFixed(Math.max(0, parseFloat(e.target.value) || 0))}
              style={{
                width: "100%",
                background: "var(--surface)",
                border: "1px solid var(--border-color)",
                borderRadius: "var(--radius-sm)",
                padding: "6px 10px",
                color: "#fff",
                fontSize: "0.85rem",
              }}
            />
          </div>
        </div>
      </div>

      {/* Arbitrage Insight Banner */}
      {comparisonData?.arbitrage_insight && (
        <div
          style={{
            background: "linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(17, 24, 39, 0.95) 100%)",
            border: "1px solid rgba(16, 185, 129, 0.35)",
            borderRadius: "var(--radius-lg)",
            padding: "20px 24px",
            display: "flex",
            alignItems: "center",
            gap: "16px",
          }}
        >
          <div
            style={{
              width: "48px",
              height: "48px",
              borderRadius: "12px",
              background: "rgba(16, 185, 129, 0.2)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <Award size={26} style={{ color: "var(--emerald-400)" }} />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
              <span style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--emerald-400)", fontWeight: 700 }}>
                Optimal Selling Venue &amp; Arbitrage Finding
              </span>
            </div>
            <p style={{ fontSize: "0.95rem", color: "var(--text-main)", lineHeight: 1.5, margin: 0 }}>
              {comparisonData.arbitrage_insight}
            </p>
          </div>
        </div>
      )}

      {/* KPI Cards Row */}
      {bestMarket && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "16px" }}>
          {/* Best Market */}
          <div className="glass-card" style={{ padding: "18px 22px" }}>
            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>
              #1 Ranked Selling Venue
            </span>
            <div style={{ fontSize: "1.45rem", fontWeight: 700, color: "var(--emerald-400)", marginTop: "4px" }}>
              {bestMarket.market} Mandi
            </div>
            <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "2px" }}>
              {bestMarket.district}, {bestMarket.state}
            </div>
            <div style={{ marginTop: "12px", display: "flex", justifyContent: "space-between", fontSize: "0.8rem", borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "8px" }}>
              <span style={{ color: "var(--text-muted)" }}>Estimated Net Return:</span>
              <strong style={{ color: "#fff" }}>₹{bestMarket.estimated_net_return.toLocaleString()}</strong>
            </div>
          </div>

          {/* Quoted vs Net Realization */}
          <div className="glass-card" style={{ padding: "18px 22px" }}>
            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>
              Realization per kg
            </span>
            <div style={{ fontSize: "1.45rem", fontWeight: 700, color: "#fff", marginTop: "4px" }}>
              ₹{bestMarket.net_return_per_kg.toFixed(2)} <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>/ kg</span>
            </div>
            <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "2px" }}>
              Quoted Price: ₹{bestMarket.quoted_price_per_kg.toFixed(2)} / kg (₹{bestMarket.quoted_price_per_qtl}/Qtl)
            </div>
            <div style={{ marginTop: "12px", display: "flex", justifyContent: "space-between", fontSize: "0.8rem", borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "8px" }}>
              <span style={{ color: "var(--text-muted)" }}>Logistics Deductions:</span>
              <strong style={{ color: "var(--rose-400)" }}>-₹{bestMarket.total_deductions.toLocaleString()}</strong>
            </div>
          </div>

          {/* Volume Analyzed */}
          <div className="glass-card" style={{ padding: "18px 22px" }}>
            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>
              Consignment Weight
            </span>
            <div style={{ fontSize: "1.45rem", fontWeight: 700, color: "#fff", marginTop: "4px" }}>
              {comparisonData?.quantity_qtl.toFixed(1)} <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Quintals</span>
            </div>
            <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "2px" }}>
              {comparisonData?.quantity_kg.toLocaleString()} kg total crop weight
            </div>
            <div style={{ marginTop: "12px", display: "flex", justifyContent: "space-between", fontSize: "0.8rem", borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "8px" }}>
              <span style={{ color: "var(--text-muted)" }}>Horizon Basis:</span>
              <strong style={{ color: "var(--emerald-400)" }}>{bestMarket.price_basis}</strong>
            </div>
          </div>
        </div>
      )}

      {/* Visual Chart: Quoted Gross vs Estimated Net Return */}
      {markets.length > 0 && (
        <div className="glass-card" style={{ padding: "24px" }}>
          <h3 style={{ fontSize: "1.05rem", fontWeight: 700, color: "var(--text-main)", marginBottom: "16px" }}>
            Gross Quoted Revenue vs. Estimated Net Realization (After Freight &amp; Mandi Cess)
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            {markets.map((m) => {
              const maxGross = Math.max(...markets.map((x) => x.gross_revenue));
              const grossWidth = (m.gross_revenue / maxGross) * 100;
              const netWidth = (m.estimated_net_return / maxGross) * 100;

              return (
                <div key={m.market} style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span className={`badge ${m.rank_by_net_return === 1 ? "badge-emerald" : "badge-secondary"}`} style={{ fontSize: "0.75rem" }}>
                        #{m.rank_by_net_return}
                      </span>
                      <strong style={{ color: "#fff" }}>{m.market} Mandi</strong>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>({m.distance_km} km road transit)</span>
                    </div>
                    <div>
                      <span style={{ color: "var(--emerald-400)", fontWeight: 700 }}>₹{m.estimated_net_return.toLocaleString()}</span>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginLeft: "6px" }}>
                        (Gross: ₹{m.gross_revenue.toLocaleString()})
                      </span>
                    </div>
                  </div>

                  {/* Dual Bar */}
                  <div style={{ position: "relative", height: "16px", background: "rgba(255,255,255,0.05)", borderRadius: "4px", overflow: "hidden" }}>
                    {/* Gross Bar */}
                    <div
                      style={{
                        position: "absolute",
                        left: 0,
                        top: 0,
                        height: "100%",
                        width: `${grossWidth}%`,
                        background: "rgba(100, 116, 139, 0.4)",
                        borderRadius: "4px",
                      }}
                    />
                    {/* Net Return Bar */}
                    <div
                      style={{
                        position: "absolute",
                        left: 0,
                        top: 0,
                        height: "100%",
                        width: `${Math.max(0, netWidth)}%`,
                        background: m.rank_by_net_return === 1 ? "var(--emerald-500)" : "rgba(16, 185, 129, 0.7)",
                        borderRadius: "4px",
                        transition: "width 0.4s ease",
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          <div style={{ display: "flex", gap: "18px", marginTop: "16px", fontSize: "0.75rem", color: "var(--text-muted)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <div style={{ width: "12px", height: "12px", background: "var(--emerald-500)", borderRadius: "2px" }} />
              <span>Estimated Net Return (Take-Home Profit)</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <div style={{ width: "12px", height: "12px", background: "rgba(100, 116, 139, 0.4)", borderRadius: "2px" }} />
              <span>Gross Quoted Revenue (Before Transport)</span>
            </div>
          </div>
        </div>
      )}

      {/* Detailed Market Comparison Table */}
      <div className="glass-card" style={{ padding: "24px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: "10px" }}>
          <div>
            <h3 style={{ fontSize: "1.05rem", fontWeight: 700, color: "var(--text-main)" }}>
              Market Ranking &amp; Detailed Cost Deductions
            </h3>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "2px" }}>
              Sorted descending by Net Realization. All prices and transport deductions based on user consignment parameters.
            </p>
          </div>
        </div>

        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem", textAlign: "left" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.1)", color: "var(--text-muted)", fontSize: "0.75rem", textTransform: "uppercase" }}>
                <th style={{ padding: "12px 10px" }}>Rank &amp; Market</th>
                <th style={{ padding: "12px 10px" }}>Quoted Price</th>
                <th style={{ padding: "12px 10px" }}>Transit Distance</th>
                <th style={{ padding: "12px 10px" }}>Transport Cost</th>
                <th style={{ padding: "12px 10px" }}>Mandi Handling</th>
                <th style={{ padding: "12px 10px" }}>Estimated Net Return</th>
                <th style={{ padding: "12px 10px" }}>Net / kg</th>
                <th style={{ padding: "12px 10px" }}>Arbitrage vs Local</th>
                <th style={{ padding: "12px 10px" }}>Data Freshness</th>
              </tr>
            </thead>
            <tbody>
              {markets.map((m) => (
                <tr
                  key={m.market}
                  style={{
                    borderBottom: "1px solid rgba(255, 255, 255, 0.05)",
                    background: m.rank_by_net_return === 1 ? "rgba(16, 185, 129, 0.06)" : "transparent",
                  }}
                >
                  {/* Market & Variety */}
                  <td style={{ padding: "12px 10px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span className={`badge ${m.rank_by_net_return === 1 ? "badge-emerald" : "badge-secondary"}`}>
                        #{m.rank_by_net_return}
                      </span>
                      <div>
                        <strong style={{ color: "#fff", display: "block" }}>{m.market}</strong>
                        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                          {m.district}, {m.state} ({m.variety})
                        </span>
                      </div>
                    </div>
                  </td>

                  {/* Quoted Price */}
                  <td style={{ padding: "12px 10px" }}>
                    <strong style={{ color: "#fff" }}>₹{m.quoted_price_per_qtl.toLocaleString()}</strong>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block" }}>
                      ₹{m.quoted_price_per_kg.toFixed(2)}/kg
                    </span>
                  </td>

                  {/* Distance */}
                  <td style={{ padding: "12px 10px", color: "var(--text-muted)" }}>
                    {m.distance_km === 0 ? (
                      <span className="badge badge-emerald" style={{ fontSize: "0.75rem" }}>Local Mandi</span>
                    ) : (
                      <span>{m.distance_km} km</span>
                    )}
                  </td>

                  {/* Transport Cost */}
                  <td style={{ padding: "12px 10px", color: "var(--rose-400)" }}>
                    -₹{m.total_transport_cost.toLocaleString()}
                  </td>

                  {/* Mandi Handling */}
                  <td style={{ padding: "12px 10px", color: "var(--text-muted)" }}>
                    -₹{m.other_selling_costs.toLocaleString()}
                  </td>

                  {/* Estimated Net Return */}
                  <td style={{ padding: "12px 10px" }}>
                    <strong style={{ color: "var(--emerald-400)", fontSize: "0.95rem" }}>
                      ₹{m.estimated_net_return.toLocaleString()}
                    </strong>
                  </td>

                  {/* Net per kg */}
                  <td style={{ padding: "12px 10px", color: "#fff" }}>
                    ₹{m.net_return_per_kg.toFixed(2)}
                  </td>

                  {/* Arbitrage vs Reference */}
                  <td style={{ padding: "12px 10px" }}>
                    {m.net_difference_vs_reference === 0 ? (
                      <span style={{ color: "var(--text-muted)" }}>Benchmark</span>
                    ) : m.net_difference_vs_reference > 0 ? (
                      <span style={{ color: "var(--emerald-400)", fontWeight: 700 }}>
                        +₹{m.net_difference_vs_reference.toLocaleString()}
                      </span>
                    ) : (
                      <span style={{ color: "var(--rose-400)" }}>
                        -₹{Math.abs(m.net_difference_vs_reference).toLocaleString()}
                      </span>
                    )}
                  </td>

                  {/* Freshness & Warnings */}
                  <td style={{ padding: "12px 10px" }}>
                    {m.is_stale_warning ? (
                      <span className="badge badge-rose" style={{ fontSize: "0.75rem" }}>
                        {m.data_freshness_days}d ago
                      </span>
                    ) : (
                      <span className="badge badge-emerald" style={{ fontSize: "0.75rem" }}>
                        {m.data_freshness_days}d ago
                      </span>
                    )}
                    <span style={{ display: "block", fontSize: "0.7rem", color: "var(--text-muted)", marginTop: "2px" }}>
                      {m.observation_date}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Methodology & Calculation Explanation Accordion */}
      <div className="glass-card" style={{ padding: "22px 26px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px" }}>
          <Info size={18} style={{ color: "var(--emerald-400)" }} />
          <h4 style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--text-main)", margin: 0 }}>
            Analytical Methodology &amp; Transport Arbitration Rules
          </h4>
        </div>
        <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", lineHeight: 1.6, display: "flex", flexDirection: "column", gap: "8px" }}>
          <p style={{ margin: 0 }}>
            <strong>1. Net Return Formula:</strong> <code style={{ color: "var(--emerald-400)" }}>Net Return = (Quantity × Quoted Price) − Fixed Mobilization Fee − (Quantity × Transit Distance × Freight Rate) − Gate &amp; Mandi Cess</code>.
          </p>
          <p style={{ margin: 0 }}>
            <strong>2. Freight Costs Source:</strong> Transport costs are calculated from user-provided freight benchmarks (₹{costPerKm}/km/Qtl) and documented road transit mileage. Freight charges are never fabricated.
          </p>
          <p style={{ margin: 0 }}>
            <strong>3. Unit Integrity:</strong> Consignments are converted using canonical Indian wholesale standards: 1 Quintal = 100 kg = 0.1 Metric Tonne.
          </p>
          <p style={{ margin: 0 }}>
            <strong>4. Incompatible Varieties &amp; Grades:</strong> Quoted prices correspond to observed APMC wholesale varieties (e.g. Red Onion, Sharbati Wheat). Comparing across varieties should be done with caution.
          </p>
        </div>
      </div>
    </div>
  );
};
