import React, { useState, useEffect } from "react";
import {
  DecisionRecommendation,
  ComprehensiveDecisionResponse,
  OptionEvaluation,
  WhatIfSimulationResponse,
} from "../types";
import { api } from "../services/api";
import {
  BrainCircuit,
  Calculator,
  ShieldCheck,
  AlertTriangle,
  Clock,
  ArrowRight,
  TrendingUp,
  Package,
  Layers,
  Info,
  DollarSign,
  Scale,
  Sparkles,
  CheckCircle2,
  XCircle,
  HelpCircle,
} from "lucide-react";

interface DecisionSupportPageProps {
  decision: DecisionRecommendation | null;
  selectedCommodity: string;
  selectedMarket: string;
  isLoading: boolean;
}

export const DecisionSupportPage: React.FC<DecisionSupportPageProps> = ({
  decision,
  selectedCommodity,
  selectedMarket,
  isLoading: propLoading,
}) => {
  // Navigation between Strategic Advisor and What-If Simulator
  const [activeSubTab, setActiveSubTab] = useState<"strategic" | "what_if">("strategic");

  // -------------------------------------------------------------------------
  // STRATEGIC ADVISOR STATE
  // -------------------------------------------------------------------------
  const [quantity, setQuantity] = useState<number>(100);
  const [quantityUnit, setQuantityUnit] = useState<"kg" | "quintal" | "tonne">("quintal");
  const [priceOverride, setPriceOverride] = useState<string>("");
  const [storageFacility, setStorageFacility] = useState<"none" | "ambient" | "cold_storage">("ambient");
  const [waitDays, setWaitDays] = useState<number>(7);
  const [storeDays, setStoreDays] = useState<number>(30);
  const [customStorageRent, setCustomStorageRent] = useState<string>("");
  const [customSpoilagePct, setCustomSpoilagePct] = useState<string>("");
  const [transportDistance, setTransportDistance] = useState<number>(15);
  const [transportRate, setTransportRate] = useState<number>(1.5);
  const [fixedTransportFee, setFixedTransportFee] = useState<number>(300);
  const [otherFixedFee, setOtherFixedFee] = useState<number>(150);
  const [otherPerQtlFee, setOtherPerQtlFee] = useState<number>(10);
  const [interestAPR, setInterestAPR] = useState<number>(7.0);

  const [compDecision, setCompDecision] = useState<ComprehensiveDecisionResponse | null>(null);
  const [isCompLoading, setIsCompLoading] = useState<boolean>(false);
  const [compError, setCompError] = useState<string | null>(null);

  // -------------------------------------------------------------------------
  // WHAT-IF SIMULATOR STATE
  // -------------------------------------------------------------------------
  const [simQty, setSimQty] = useState<number>(100);
  const [simQtyUnit, setSimQtyUnit] = useState<"kg" | "quintal" | "tonne">("quintal");
  const [simHoldingDays, setSimHoldingDays] = useState<number>(30);
  const [simCurrentPrice, setSimCurrentPrice] = useState<number>(decision?.current_price || 2200);
  const [simFuturePrice, setSimFuturePrice] = useState<number>(
    decision?.current_price ? Math.round(decision.current_price * 1.15) : 2550
  );
  const [simStorageRent, setSimStorageRent] = useState<number>(50);
  const [simShrinkagePct, setSimShrinkagePct] = useState<number>(4.0);
  const [simInterestAPR, setSimInterestAPR] = useState<number>(7.0);
  const [simDistance, setSimDistance] = useState<number>(15);
  const [simFreightRate, setSimFreightRate] = useState<number>(1.5);
  const [simFixedTransport, setSimFixedTransport] = useState<number>(300);
  const [simOtherCosts, setSimOtherCosts] = useState<number>(150);

  const [simResult, setSimResult] = useState<WhatIfSimulationResponse | null>(null);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);

  // Sync spot price from prop if available
  useEffect(() => {
    if (decision?.current_price) {
      setSimCurrentPrice(decision.current_price);
      setSimFuturePrice(Math.round(decision.current_price * 1.15));
    }
  }, [decision]);

  // Fetch Comprehensive Decision
  const fetchComprehensiveDecision = async () => {
    setIsCompLoading(true);
    setCompError(null);
    setCompDecision(null);
    try {
      const res = await api.evaluateComprehensiveDecision({
        commodity: selectedCommodity,
        market: selectedMarket,
        quantity: Math.max(0.1, quantity),
        quantity_unit: quantityUnit,
        current_price_override: priceOverride.trim() ? parseFloat(priceOverride) : null,
        wait_horizon_days: waitDays,
        store_horizon_days: storeDays,
        storage_facility: storageFacility,
        user_monthly_storage_rent_qtl: customStorageRent.trim() ? parseFloat(customStorageRent) : null,
        user_spoilage_monthly_pct: customSpoilagePct.trim() ? parseFloat(customSpoilagePct) : null,
        transport_distance_km: transportDistance,
        transport_cost_per_km_qtl: transportRate,
        transport_fixed_vehicle_fee: fixedTransportFee,
        other_cost_fixed: otherFixedFee,
        other_cost_per_qtl: otherPerQtlFee,
        annual_interest_rate_pct: interestAPR,
      });
      setCompDecision(res);
    } catch (err: any) {
      console.error("Failed to evaluate decision options:", err);
      setCompError(err.message || "Failed to evaluate selling options.");
    } finally {
      setIsCompLoading(false);
    }
  };

  useEffect(() => {
    fetchComprehensiveDecision();
  }, [
    selectedCommodity,
    selectedMarket,
    quantity,
    quantityUnit,
    priceOverride,
    storageFacility,
    waitDays,
    storeDays,
    customStorageRent,
    customSpoilagePct,
    transportDistance,
    transportRate,
    fixedTransportFee,
    otherFixedFee,
    otherPerQtlFee,
    interestAPR,
  ]);

  // Run What-If Simulation
  const handleRunSimulation = async () => {
    setIsSimulating(true);
    try {
      const res = await api.simulateWhatIf({
        commodity: selectedCommodity,
        current_price: simCurrentPrice,
        expected_future_price: simFuturePrice,
        holding_days: simHoldingDays,
        quantity_qtl: simQty,
        quantity_unit: simQtyUnit,
        storage_type: "ambient",
        monthly_storage_rent_qtl: simStorageRent,
        monthly_shrinkage_pct: simShrinkagePct,
        annual_interest_rate_pct: simInterestAPR,
        transport_cost_per_km_qtl: simFreightRate,
        distance_km: simDistance,
        fixed_transport_fee: simFixedTransport,
        other_selling_costs: simOtherCosts,
      });
      setSimResult(res);
    } catch (err) {
      console.error("Simulation error:", err);
    } finally {
      setIsSimulating(false);
    }
  };

  useEffect(() => {
    handleRunSimulation();
  }, [
    selectedCommodity,
    simQty,
    simQtyUnit,
    simHoldingDays,
    simCurrentPrice,
    simFuturePrice,
    simStorageRent,
    simShrinkagePct,
    simInterestAPR,
    simDistance,
    simFreightRate,
    simFixedTransport,
    simOtherCosts,
  ]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "28px" }}>
      {/* Sub-Tab Navigation Header */}
      <div
        className="glass-card"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "16px",
          padding: "16px 24px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <BrainCircuit size={24} style={{ color: "var(--emerald-400)" }} />
          <div>
            <h2 style={{ fontSize: "1.2rem", fontWeight: 700, color: "var(--text-main)" }}>
              Agricultural Decision Support &amp; Net Return Optimization
            </h2>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "2px" }}>
              Compare selling options (Sell Now vs. Wait vs. Store) and model custom hypothetical what-if scenarios
            </p>
          </div>
        </div>

        {/* Tab Toggle */}
        <div style={{ display: "flex", background: "rgba(15, 23, 42, 0.6)", borderRadius: "var(--radius-md)", padding: "4px" }}>
          <button
            onClick={() => setActiveSubTab("strategic")}
            style={{
              padding: "8px 16px",
              borderRadius: "var(--radius-sm)",
              border: "none",
              fontSize: "0.85rem",
              fontWeight: 600,
              cursor: "pointer",
              background: activeSubTab === "strategic" ? "var(--emerald-500)" : "transparent",
              color: activeSubTab === "strategic" ? "#fff" : "var(--text-muted)",
              transition: "all 0.2s ease",
            }}
          >
            Strategic Selling Advisor
          </button>
          <button
            onClick={() => setActiveSubTab("what_if")}
            style={{
              padding: "8px 16px",
              borderRadius: "var(--radius-sm)",
              border: "none",
              fontSize: "0.85rem",
              fontWeight: 600,
              cursor: "pointer",
              background: activeSubTab === "what_if" ? "var(--emerald-500)" : "transparent",
              color: activeSubTab === "what_if" ? "#fff" : "var(--text-muted)",
              transition: "all 0.2s ease",
            }}
          >
            Interactive What-If Simulator
          </button>
        </div>
      </div>

      {/* =================================================================== */}
      {/* MODE 1: STRATEGIC SELLING ADVISOR                                  */}
      {/* =================================================================== */}
      {activeSubTab === "strategic" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "28px" }}>
          {/* Recommendation Banner */}
          {compDecision && (
            <div
              style={{
                background:
                  compDecision.recommended_option === "SELL NOW"
                    ? "linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(17, 24, 39, 0.95) 100%)"
                    : compDecision.recommended_option.includes("WAIT")
                    ? "linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(17, 24, 39, 0.95) 100%)"
                    : "linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(17, 24, 39, 0.95) 100%)",
                border: `1px solid ${
                  compDecision.recommended_option === "SELL NOW"
                    ? "rgba(239, 68, 68, 0.35)"
                    : compDecision.recommended_option.includes("WAIT")
                    ? "rgba(245, 158, 11, 0.35)"
                    : "rgba(16, 185, 129, 0.35)"
                }`,
                borderRadius: "var(--radius-lg)",
                padding: "24px 28px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
                    <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 700 }}>
                      Optimal Selling Strategy
                    </span>
                    <span
                      className={`badge ${
                        compDecision.recommended_option === "SELL NOW"
                          ? "badge-rose"
                          : compDecision.recommended_option.includes("WAIT")
                          ? "badge-amber"
                          : "badge-emerald"
                      }`}
                      style={{ fontSize: "0.9rem", padding: "5px 14px", fontWeight: 700 }}
                    >
                      {compDecision.recommended_option}
                    </span>
                  </div>

                  <h3 style={{ fontSize: "1.45rem", fontWeight: 700, color: "var(--text-main)", marginBottom: "8px" }}>
                    {compDecision.recommendation_rationale}
                  </h3>

                  <div style={{ display: "flex", gap: "18px", fontSize: "0.85rem", color: "var(--text-muted)", flexWrap: "wrap", marginTop: "12px" }}>
                    <span>
                      Financial Advantage:{" "}
                      <strong style={{ color: "var(--emerald-400)" }}>
                        {compDecision.financial_advantage_amount > 0
                          ? `+₹${compDecision.financial_advantage_amount.toLocaleString()} (+${compDecision.financial_advantage_pct.toFixed(1)}%)`
                          : "Baseline Spot Liquidation"}
                      </strong>
                    </span>
                    <span>•</span>
                    <span>
                      {compDecision.current_observed_modal_price !== null
                        ? <>Observed Spot Rate: <strong>₹{compDecision.current_observed_modal_price.toLocaleString()}/Qtl</strong></>
                        : <>No observed price; using user quote: <strong>₹{compDecision.effective_selling_price_now.toLocaleString()}/Qtl</strong></>}
                    </span>
                    <span>•</span>
                    <span>
                      {compDecision.observation_date
                        ? <>Data Freshness: <strong>{compDecision.data_freshness_days} days ago</strong> ({compDecision.observation_date})</>
                        : "No market observation date available"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Sensitivity Drivers & Uncertainty Grid */}
              <div
                style={{
                  marginTop: "20px",
                  paddingTop: "16px",
                  borderTop: "1px solid rgba(255, 255, 255, 0.08)",
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
                  gap: "20px",
                }}
              >
                {/* Key Sensitivity Drivers */}
                <div>
                  <span style={{ fontSize: "0.75rem", textTransform: "uppercase", fontWeight: 700, color: "var(--emerald-400)", display: "block", marginBottom: "8px" }}>
                    Key Economic Drivers &amp; Sensitivities
                  </span>
                  <ul style={{ margin: 0, paddingLeft: "16px", fontSize: "0.8rem", color: "var(--text-muted)", display: "flex", flexDirection: "column", gap: "6px" }}>
                    {compDecision.key_sensitivity_drivers.map((drv, idx) => (
                      <li key={idx}>{drv}</li>
                    ))}
                  </ul>
                </div>

                {/* Forecast Uncertainty Impact */}
                <div>
                  <span style={{ fontSize: "0.75rem", textTransform: "uppercase", fontWeight: 700, color: "var(--amber-400)", display: "block", marginBottom: "8px" }}>
                    Forecast Uncertainty &amp; Downside Risk
                  </span>
                  <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--text-muted)", lineHeight: 1.5 }}>
                    {compDecision.uncertainty_impact_analysis}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Consignment & Cost Controls */}
          <div className="glass-card" style={{ padding: "24px" }}>
            <h3 style={{ fontSize: "1.05rem", fontWeight: 700, color: "var(--text-main)", marginBottom: "16px" }}>
              Consignment Parameters &amp; Post-Harvest Cost Structure
            </h3>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                gap: "16px",
              }}
            >
              {/* Quantity */}
              <div>
                <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "6px", textTransform: "uppercase", fontWeight: 600 }}>
                  Consignment Quantity
                </label>
                <div style={{ display: "flex", gap: "6px" }}>
                  <input
                    type="number"
                    min="1"
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
                    <option value="quintal">Quintal</option>
                    <option value="kg">kg</option>
                    <option value="tonne">Tonne</option>
                  </select>
                </div>
              </div>

              {/* Quality Price Override */}
              <div>
                <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "6px", textTransform: "uppercase", fontWeight: 600 }}>
                  Quality Adjusted Spot Price (₹/Qtl)
                </label>
                <input
                  type="number"
                  placeholder="Leave empty for mandi modal rate"
                  value={priceOverride}
                  onChange={(e) => setPriceOverride(e.target.value)}
                  style={{
                    width: "100%",
                    background: "var(--surface)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "var(--radius-sm)",
                    padding: "8px 12px",
                    color: "#fff",
                    fontSize: "0.85rem",
                  }}
                />
              </div>

              {/* Storage Facility */}
              <div>
                <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "6px", textTransform: "uppercase", fontWeight: 600 }}>
                  Available Storage Facility
                </label>
                <select
                  value={storageFacility}
                  onChange={(e) => setStorageFacility(e.target.value as any)}
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
                  <option value="ambient">Ambient On-Farm Shed</option>
                  <option value="cold_storage">Certified Cold Storage</option>
                  <option value="none">No Storage (Immediate Sale Only)</option>
                </select>
              </div>

              {/* Storage Rent */}
              <div>
                <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "6px", textTransform: "uppercase", fontWeight: 600 }}>
                  Storage Rent (₹/Qtl/mo)
                </label>
                <input
                  type="number"
                  placeholder="Default by crop profile"
                  value={customStorageRent}
                  onChange={(e) => setCustomStorageRent(e.target.value)}
                  style={{
                    width: "100%",
                    background: "var(--surface)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "var(--radius-sm)",
                    padding: "8px 12px",
                    color: "#fff",
                    fontSize: "0.85rem",
                  }}
                />
              </div>

              {/* Custom Spoilage % */}
              <div>
                <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "6px", textTransform: "uppercase", fontWeight: 600 }}>
                  Monthly Shrinkage &amp; Spoilage (%)
                </label>
                <input
                  type="number"
                  placeholder="Default by crop profile"
                  value={customSpoilagePct}
                  onChange={(e) => setCustomSpoilagePct(e.target.value)}
                  style={{
                    width: "100%",
                    background: "var(--surface)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "var(--radius-sm)",
                    padding: "8px 12px",
                    color: "#fff",
                    fontSize: "0.85rem",
                  }}
                />
              </div>

              {/* Transport Distance */}
              <div>
                <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "6px", textTransform: "uppercase", fontWeight: 600 }}>
                  Distance to Mandi (km)
                </label>
                <input
                  type="number"
                  min="0"
                  value={transportDistance}
                  onChange={(e) => setTransportDistance(Math.max(0, parseFloat(e.target.value) || 0))}
                  style={{
                    width: "100%",
                    background: "var(--surface)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "var(--radius-sm)",
                    padding: "8px 12px",
                    color: "#fff",
                    fontSize: "0.85rem",
                  }}
                />
              </div>

              {/* Freight Rate */}
              <div>
                <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "6px", textTransform: "uppercase", fontWeight: 600 }}>
                  Freight Rate (₹/km/Qtl)
                </label>
                <input
                  type="number"
                  min="0"
                  step="0.25"
                  value={transportRate}
                  onChange={(e) => setTransportRate(Math.max(0, parseFloat(e.target.value) || 0))}
                  style={{
                    width: "100%",
                    background: "var(--surface)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "var(--radius-sm)",
                    padding: "8px 12px",
                    color: "#fff",
                    fontSize: "0.85rem",
                  }}
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
                    padding: "8px 12px",
                    color: "#fff",
                    fontSize: "0.85rem",
                  }}
                />
              </div>
            </div>
          </div>

          {/* 3 Strategy Options Comparison Cards */}
          {compDecision && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "20px" }}>
              {/* 1. SELL NOW CARD */}
              <StrategyCard
                option={compDecision.sell_now}
                isRecommended={compDecision.recommended_option === "SELL NOW"}
                accentColor="var(--rose-500)"
              />

              {/* 2. WAIT CARD */}
              <StrategyCard
                option={compDecision.wait}
                isRecommended={compDecision.recommended_option.includes("WAIT")}
                accentColor="var(--amber-500)"
              />

              {/* 3. STORE CARD */}
              <StrategyCard
                option={compDecision.store}
                isRecommended={compDecision.recommended_option.includes("STORE")}
                accentColor="var(--emerald-500)"
              />
            </div>
          )}

          {/* Mathematical Formulas & Methodology Panel */}
          {compDecision?.calculation_formulas && (
            <div className="glass-card" style={{ padding: "22px 26px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px" }}>
                <Info size={18} style={{ color: "var(--emerald-400)" }} />
                <h4 style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--text-main)", margin: 0 }}>
                  Defensible Net Return Mathematical Formulas
                </h4>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "10px", fontSize: "0.85rem", color: "var(--text-muted)", lineHeight: 1.6 }}>
                <div>
                  <strong style={{ color: "#fff" }}>Sell Now Calculation:</strong>
                  <div style={{ background: "rgba(0,0,0,0.3)", padding: "6px 12px", borderRadius: "4px", marginTop: "4px", color: "var(--emerald-400)", fontFamily: "monospace", fontSize: "0.8rem" }}>
                    {compDecision.calculation_formulas.sell_now}
                  </div>
                </div>
                <div>
                  <strong style={{ color: "#fff" }}>Wait (On-Farm Holding) Calculation:</strong>
                  <div style={{ background: "rgba(0,0,0,0.3)", padding: "6px 12px", borderRadius: "4px", marginTop: "4px", color: "var(--amber-400)", fontFamily: "monospace", fontSize: "0.8rem" }}>
                    {compDecision.calculation_formulas.wait}
                  </div>
                </div>
                <div>
                  <strong style={{ color: "#fff" }}>Store (Commercial Storage) Calculation:</strong>
                  <div style={{ background: "rgba(0,0,0,0.3)", padding: "6px 12px", borderRadius: "4px", marginTop: "4px", color: "var(--emerald-400)", fontFamily: "monospace", fontSize: "0.8rem" }}>
                    {compDecision.calculation_formulas.store}
                  </div>
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px" }}>
                  * All calculations prevent double-counting: road transit is applied strictly once upon final delivery to auction yard.
                </div>
              </div>
            </div>
          )}

          {compError && (
            <div role="alert" className="glass-card" style={{ border: "1px solid rgba(245, 158, 11, 0.35)", color: "var(--amber-400)" }}>
              {compError}
            </div>
          )}
        </div>
      )}

      {/* =================================================================== */}
      {/* MODE 2: INTERACTIVE WHAT-IF SIMULATOR                               */}
      {/* =================================================================== */}
      {activeSubTab === "what_if" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "28px" }}>
          {/* Disclaimer Header */}
          <div
            style={{
              background: "rgba(30, 41, 59, 0.7)",
              border: "1px solid rgba(245, 158, 11, 0.3)",
              borderRadius: "var(--radius-lg)",
              padding: "16px 20px",
              display: "flex",
              alignItems: "center",
              gap: "14px",
            }}
          >
            <AlertTriangle size={24} style={{ color: "var(--amber-400)", flexShrink: 0 }} />
            <div>
              <strong style={{ color: "var(--amber-400)", fontSize: "0.85rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Interactive Scenario Modeling Environment
              </strong>
              <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-muted)", marginTop: "2px" }}>
                Adjust parameters to simulate custom holding periods, private buyer quotes, warehouse rates, and logistics costs.
                Results immediately recalculate and reflect user assumptions, not official market records.
              </p>
            </div>
          </div>

          {/* Simulator Form & Results Split */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: "24px" }}>
            {/* Input Controls */}
            <div className="glass-card" style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "18px" }}>
              <h3 style={{ fontSize: "1.05rem", fontWeight: 700, color: "var(--text-main)" }}>
                Custom Scenario Inputs
              </h3>

              {/* Quantity */}
              <div>
                <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "4px", textTransform: "uppercase" }}>
                  Consignment Quantity
                </label>
                <div style={{ display: "flex", gap: "6px" }}>
                  <input
                    type="number"
                    min="1"
                    value={simQty}
                    onChange={(e) => setSimQty(Math.max(1, parseFloat(e.target.value) || 1))}
                    style={{ flex: 1, background: "var(--surface)", border: "1px solid var(--border-color)", borderRadius: "var(--radius-sm)", padding: "8px 10px", color: "#fff" }}
                  />
                  <select
                    value={simQtyUnit}
                    onChange={(e) => setSimQtyUnit(e.target.value as any)}
                    style={{ background: "var(--surface)", border: "1px solid var(--border-color)", borderRadius: "var(--radius-sm)", padding: "8px 10px", color: "#fff" }}
                  >
                    <option value="quintal">Quintal</option>
                    <option value="kg">kg</option>
                    <option value="tonne">Tonne</option>
                  </select>
                </div>
              </div>

              {/* Spot Price */}
              <div>
                <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "4px", textTransform: "uppercase" }}>
                  Spot Selling Price Today (₹/Qtl)
                </label>
                <input
                  type="number"
                  value={simCurrentPrice}
                  onChange={(e) => setSimCurrentPrice(parseFloat(e.target.value) || 0)}
                  style={{ width: "100%", background: "var(--surface)", border: "1px solid var(--border-color)", borderRadius: "var(--radius-sm)", padding: "8px 10px", color: "#fff" }}
                />
              </div>

              {/* Expected Future Price */}
              <div>
                <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "4px", textTransform: "uppercase" }}>
                  Hypothetical Future Price (₹/Qtl)
                </label>
                <input
                  type="number"
                  value={simFuturePrice}
                  onChange={(e) => setSimFuturePrice(parseFloat(e.target.value) || 0)}
                  style={{ width: "100%", background: "var(--surface)", border: "1px solid var(--border-color)", borderRadius: "var(--radius-sm)", padding: "8px 10px", color: "#fff" }}
                />
              </div>

              {/* Holding Duration Slider */}
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>
                    Holding Duration
                  </span>
                  <span style={{ fontSize: "0.85rem", color: "var(--emerald-400)", fontWeight: 700 }}>
                    {simHoldingDays} Days
                  </span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="120"
                  step="1"
                  value={simHoldingDays}
                  onChange={(e) => setSimHoldingDays(parseInt(e.target.value))}
                  style={{ width: "100%", accentColor: "var(--emerald-500)", cursor: "pointer" }}
                />
              </div>

              {/* Monthly Storage Rent */}
              <div>
                <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "4px", textTransform: "uppercase" }}>
                  Storage Rent (₹/Qtl/Month)
                </label>
                <input
                  type="number"
                  min="0"
                  value={simStorageRent}
                  onChange={(e) => setSimStorageRent(parseFloat(e.target.value) || 0)}
                  style={{ width: "100%", background: "var(--surface)", border: "1px solid var(--border-color)", borderRadius: "var(--radius-sm)", padding: "8px 10px", color: "#fff" }}
                />
              </div>

              {/* Spoilage / Shrinkage % */}
              <div>
                <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "4px", textTransform: "uppercase" }}>
                  Monthly Shrinkage Loss (%)
                </label>
                <input
                  type="number"
                  min="0"
                  step="0.5"
                  value={simShrinkagePct}
                  onChange={(e) => setSimShrinkagePct(parseFloat(e.target.value) || 0)}
                  style={{ width: "100%", background: "var(--surface)", border: "1px solid var(--border-color)", borderRadius: "var(--radius-sm)", padding: "8px 10px", color: "#fff" }}
                />
              </div>
            </div>

            {/* Simulation Results Output */}
            {simResult && (
              <div className="glass-card" style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "20px" }}>
                <div>
                  <span className="badge badge-amber" style={{ fontSize: "0.75rem", textTransform: "uppercase", marginBottom: "8px" }}>
                    Simulation Outcome
                  </span>
                  <h3
                    style={{
                      fontSize: "1.35rem",
                      fontWeight: 700,
                      color: simResult.absolute_profit_difference > 0 ? "var(--emerald-400)" : "var(--rose-400)",
                    }}
                  >
                    {simResult.verdict}
                  </h3>
                  <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginTop: "4px", lineHeight: 1.5 }}>
                    {simResult.advice}
                  </p>
                </div>

                {/* KPI Metrics */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
                  <div style={{ background: "rgba(15, 23, 42, 0.5)", padding: "14px", borderRadius: "var(--radius-md)" }}>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Immediate Net Return</span>
                    <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "#fff", marginTop: "2px" }}>
                      ₹{simResult.immediate_net_revenue.toLocaleString()}
                    </div>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>₹{simResult.immediate_net_per_kg.toFixed(2)}/kg</span>
                  </div>

                  <div style={{ background: "rgba(15, 23, 42, 0.5)", padding: "14px", borderRadius: "var(--radius-md)" }}>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Future Net Return</span>
                    <div style={{ fontSize: "1.25rem", fontWeight: 700, color: simResult.absolute_profit_difference > 0 ? "var(--emerald-400)" : "var(--rose-400)", marginTop: "2px" }}>
                      ₹{simResult.future_net_revenue.toLocaleString()}
                    </div>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>₹{simResult.future_net_per_kg.toFixed(2)}/kg</span>
                  </div>
                </div>

                {/* Breakeven Price Card */}
                <div style={{ background: "rgba(16, 185, 129, 0.08)", border: "1px solid rgba(16, 185, 129, 0.25)", padding: "14px 18px", borderRadius: "var(--radius-md)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontSize: "0.8rem", color: "var(--text-main)", fontWeight: 600 }}>
                      Minimum Breakeven Selling Price:
                    </span>
                    <strong style={{ fontSize: "1.1rem", color: "var(--emerald-400)" }}>
                      ₹{simResult.breakeven_future_price.toLocaleString()}/Qtl
                    </strong>
                  </div>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginTop: "4px" }}>
                    Prices below this threshold will generate a net loss relative to selling today after holding deductions.
                  </span>
                </div>

                {/* Deductions Breakdown */}
                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", display: "flex", flexDirection: "column", gap: "8px", borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "14px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Weight after Moisture Loss:</span>
                    <strong style={{ color: "#fff" }}>{simResult.future_weight_after_shrinkage_qtl.toFixed(1)} Qtl ({simResult.future_weight_after_shrinkage_kg.toLocaleString()} kg)</strong>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Moisture Shrinkage Value Loss:</span>
                    <strong style={{ color: "var(--rose-400)" }}>-₹{simResult.shrinkage_loss_amount.toLocaleString()}</strong>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Storage Rent Expense:</span>
                    <strong style={{ color: "var(--rose-400)" }}>-₹{simResult.total_storage_cost.toLocaleString()}</strong>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Capital Opportunity Cost:</span>
                    <strong style={{ color: "var(--rose-400)" }}>-₹{simResult.capital_cost.toLocaleString()}</strong>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// HELPER COMPONENT: Strategy Option Card
// ---------------------------------------------------------------------------
interface StrategyCardProps {
  option: OptionEvaluation;
  isRecommended: boolean;
  accentColor: string;
}

const StrategyCard: React.FC<StrategyCardProps> = ({ option, isRecommended, accentColor }) => {
  return (
    <div
      className="glass-card"
      style={{
        padding: "24px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        border: isRecommended ? `2px solid ${accentColor}` : "1px solid rgba(255, 255, 255, 0.08)",
        background: isRecommended ? "rgba(15, 23, 42, 0.85)" : "rgba(15, 23, 42, 0.5)",
        position: "relative",
      }}
    >
      {/* Recommended Tag */}
      {isRecommended && (
        <div
          style={{
            position: "absolute",
            top: "-12px",
            right: "20px",
            background: accentColor,
            color: "#fff",
            fontSize: "0.7rem",
            fontWeight: 700,
            padding: "2px 10px",
            borderRadius: "10px",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
          Recommended Option
        </div>
      )}

      <div>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
          <div>
            <h4 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#fff", margin: 0 }}>
              {option.title}
            </h4>
            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
              {option.price_basis_type}
            </span>
          </div>
          <span
            className={`badge ${
              option.risk_level === "Low"
                ? "badge-emerald"
                : option.risk_level === "Moderate"
                ? "badge-amber"
                : "badge-rose"
            }`}
            style={{ fontSize: "0.75rem" }}
          >
            {option.risk_level} Risk
          </span>
        </div>

        {/* Expected Price & Target Date */}
        <div style={{ margin: "14px 0", padding: "12px", background: "rgba(255,255,255,0.03)", borderRadius: "var(--radius-sm)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Expected Selling Price</span>
            <strong style={{ fontSize: "1.15rem", color: "#fff" }}>₹{option.expected_price_per_qtl.toLocaleString()}/Qtl</strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "4px", fontSize: "0.75rem", color: "var(--text-muted)" }}>
            <span>Realization Unit: ₹{option.expected_price_per_kg.toFixed(2)}/kg</span>
            {option.target_date && <span>Target: {option.target_date}</span>}
          </div>
        </div>

        {/* Spoilage / Weight Loss Info */}
        {option.spoilage_loss_pct > 0 && (
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "8px" }}>
            <span>Moisture Shrinkage ({option.spoilage_loss_pct}%):</span>
            <strong style={{ color: "var(--amber-400)" }}>{option.remaining_quantity_qtl.toFixed(1)} Qtl remaining</strong>
          </div>
        )}

        {/* Cost Items Breakdown */}
        <div style={{ marginTop: "12px", borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "10px", display: "flex", flexDirection: "column", gap: "6px", fontSize: "0.8rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", color: "var(--text-muted)" }}>
            <span>Gross Revenue:</span>
            <strong style={{ color: "#fff" }}>₹{option.gross_revenue.toLocaleString()}</strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", color: "var(--rose-400)" }}>
            <span>Transport Freight:</span>
            <span>-₹{option.transport_cost_total.toLocaleString()}</span>
          </div>
          {option.storage_cost_total > 0 && (
            <div style={{ display: "flex", justifyContent: "space-between", color: "var(--rose-400)" }}>
              <span>Storage Facility Rent:</span>
              <span>-₹{option.storage_cost_total.toLocaleString()}</span>
            </div>
          )}
          {option.capital_opportunity_cost > 0 && (
            <div style={{ display: "flex", justifyContent: "space-between", color: "var(--rose-400)" }}>
              <span>Capital Lock-in Cost:</span>
              <span>-₹{option.capital_opportunity_cost.toLocaleString()}</span>
            </div>
          )}
          <div style={{ display: "flex", justifyContent: "space-between", color: "var(--rose-400)" }}>
            <span>Gate &amp; Mandi Cess:</span>
            <span>-₹{option.other_costs_total.toLocaleString()}</span>
          </div>
        </div>
      </div>

      {/* Net Return Bottom Footer */}
      <div style={{ marginTop: "18px", borderTop: "1px solid rgba(255,255,255,0.08)", paddingTop: "14px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
          <div>
            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Estimated Net Return</span>
            <div style={{ fontSize: "1.4rem", fontWeight: 700, color: option.estimated_net_return > 0 ? "var(--emerald-400)" : "var(--rose-400)", marginTop: "2px" }}>
              ₹{option.estimated_net_return.toLocaleString()}
            </div>
            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>₹{option.net_return_per_kg.toFixed(2)}/kg net</span>
          </div>

          <div style={{ textAlign: "right" }}>
            {option.net_difference_vs_sell_now === 0 ? (
              <span className="badge badge-secondary" style={{ fontSize: "0.75rem" }}>Spot Baseline</span>
            ) : option.net_difference_vs_sell_now > 0 ? (
              <span className="badge badge-emerald" style={{ fontSize: "0.75rem" }}>
                +₹{option.net_difference_vs_sell_now.toLocaleString()} (+{option.roi_percentage}%)
              </span>
            ) : (
              <span className="badge badge-rose" style={{ fontSize: "0.75rem" }}>
                -₹{Math.abs(option.net_difference_vs_sell_now).toLocaleString()} ({option.roi_percentage}%)
              </span>
            )}
          </div>
        </div>

        {/* Warnings */}
        {option.warnings.length > 0 && (
          <div style={{ marginTop: "10px", fontSize: "0.75rem", color: "var(--amber-400)", lineHeight: 1.4 }}>
            {option.warnings.map((warning, index) => <div key={`${option.option_id}-warning-${index}`}>{warning}</div>)}
          </div>
        )}
      </div>
    </div>
  );
};
