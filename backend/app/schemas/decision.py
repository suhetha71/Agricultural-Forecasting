from datetime import date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# LEGACY SCHEMAS (Maintained for Backward Compatibility)
# ---------------------------------------------------------------------------
class DecisionRequest(BaseModel):
    commodity: str = Field(..., examples=["Onion"])
    market: str = Field(..., examples=["Lasalgaon"])
    current_quantity_qtl: float = Field(default=50.0, gt=0, description="Farmer quantity in Quintals")
    current_modal_price: Optional[float] = Field(None, gt=0, description="Current price in INR/Quintal")
    holding_facility: str = Field(default="ambient", description="'ambient' or 'cold_storage'")
    transport_distance_km: float = Field(default=15.0, ge=0)
    custom_monthly_storage_cost: Optional[float] = Field(None, ge=0)


class HorizonAnalysis(BaseModel):
    horizon_days: int
    target_date: date
    expected_price: float
    expected_gross_revenue: float
    storage_cost: float
    weight_loss_loss: float
    opportunity_cost_capital: float
    total_holding_cost: float
    expected_net_realization: float
    net_gain_vs_selling_today: float
    percent_roi: float
    risk_level: str  # "Low", "Moderate", "High"


class DecisionRecommendation(BaseModel):
    commodity: str
    market: str
    current_date: date
    current_price: float
    recommended_action: str  # "SELL NOW", "WAIT (3-7 Days)", "STORE (15-30 Days)"
    confidence_score: Optional[float] = Field(
        None,
        description="Null unless calibrated confidence is available; no calibrated score is currently produced.",
    )
    rationale: str
    risk_assessment: str
    safe_storage_limit_days: int
    horizons: List[HorizonAnalysis]


class WhatIfSimulationRequest(BaseModel):
    commodity: str
    current_price: float
    expected_future_price: float
    holding_days: int = Field(..., ge=1, le=180)
    quantity_qtl: float = Field(..., gt=0)
    storage_type: str = Field(default="ambient")
    monthly_storage_rent_qtl: Optional[float] = None
    monthly_shrinkage_pct: Optional[float] = None
    annual_interest_rate_pct: float = Field(default=7.0, ge=0)
    transport_cost_per_km_qtl: float = Field(default=1.5, ge=0)
    distance_km: float = Field(default=10.0, ge=0)
    fixed_transport_fee: float = Field(default=0.0, ge=0)
    other_selling_costs: float = Field(default=0.0, ge=0)
    quantity_unit: str = Field(default="quintal")  # "kg", "quintal", "tonne"


class WhatIfSimulationResponse(BaseModel):
    quantity_qtl: float
    quantity_kg: float
    immediate_gross_revenue: float
    immediate_transport_cost: float
    immediate_other_costs: float = 0.0
    immediate_net_revenue: float
    immediate_net_per_kg: float

    future_gross_revenue: float
    future_weight_after_shrinkage_qtl: float
    future_weight_after_shrinkage_kg: float
    shrinkage_loss_amount: float
    total_storage_cost: float
    capital_cost: float
    future_transport_cost: float
    future_other_costs: float = 0.0
    future_net_revenue: float
    future_net_per_kg: float

    absolute_profit_difference: float
    percentage_gain_loss: float
    breakeven_future_price: float
    verdict: str
    advice: str
    scenario_disclaimer: str = "HYPOTHETICAL SIMULATION — Adjusted parameters reflect user scenario assumptions and do not represent verified mandi transactions or guaranteed model forecasts."


# ---------------------------------------------------------------------------
# COMPREHENSIVE DECISION SUPPORT SCHEMAS (Phase-Specific Extensions)
# ---------------------------------------------------------------------------
class CostBreakdownItem(BaseModel):
    name: str
    amount: float
    cost_type: str  # "fixed" or "per_unit"
    unit_basis: Optional[str] = None
    description: str


class OptionEvaluation(BaseModel):
    option_id: str  # "sell_now", "wait", "store"
    title: str
    horizon_days: int
    target_date: Optional[date] = None
    expected_price_per_qtl: float
    expected_price_per_kg: float
    price_basis_type: str  # "Observed Mandi Spot Rate", "Short-Term ML Forecast", "Medium-Term Storage Forecast"

    initial_quantity_qtl: float
    remaining_quantity_qtl: float
    remaining_quantity_kg: float
    spoilage_loss_pct: float
    spoilage_loss_qtl: float
    spoilage_monetary_loss: float

    gross_revenue: float
    fixed_costs_total: float
    variable_costs_total: float
    transport_cost_total: float
    storage_cost_total: float
    capital_opportunity_cost: float
    other_costs_total: float
    total_deductions: float

    estimated_net_return: float
    net_return_per_kg: float
    net_difference_vs_sell_now: float
    roi_percentage: float

    uncertainty_lower_bound_price: Optional[float] = None
    uncertainty_upper_bound_price: Optional[float] = None
    uncertainty_downside_net_return: Optional[float] = None
    uncertainty_upside_net_return: Optional[float] = None

    cost_items: List[CostBreakdownItem]
    risk_level: str  # "Low", "Moderate", "High", "Critical"
    assumptions: List[str]
    warnings: List[str]


class ComprehensiveDecisionRequest(BaseModel):
    commodity: str = Field(..., examples=["Onion"])
    market: str = Field(..., examples=["Lasalgaon"])
    variety: Optional[str] = None

    quantity: float = Field(default=100.0, gt=0, description="Quantity for sale")
    quantity_unit: str = Field(default="quintal", description="'kg', 'quintal', or 'tonne'")

    current_price_override: Optional[float] = Field(None, gt=0, description="Custom quality-grade adjusted spot price in ₹/Qtl")
    wait_horizon_days: int = Field(default=7, ge=1, le=14)
    store_horizon_days: int = Field(default=30, ge=15, le=180)

    storage_facility: str = Field(default="ambient", description="'none', 'ambient', or 'cold_storage'")
    user_monthly_storage_rent_qtl: Optional[float] = Field(None, ge=0)
    user_storage_fixed_entry_fee: float = Field(default=0.0, ge=0)
    user_spoilage_monthly_pct: Optional[float] = Field(None, ge=0, le=100)

    transport_distance_km: float = Field(default=15.0, ge=0)
    transport_cost_per_km_qtl: float = Field(default=1.5, ge=0)
    transport_fixed_vehicle_fee: float = Field(default=0.0, ge=0)

    other_cost_fixed: float = Field(default=0.0, ge=0, description="Fixed gate/unloading fee")
    other_cost_per_qtl: float = Field(default=0.0, ge=0, description="Per-quintal mandi handling/cess")

    annual_interest_rate_pct: float = Field(default=7.0, ge=0, description="Opportunity cost of capital rate %")


class ComprehensiveDecisionResponse(BaseModel):
    commodity: str
    market: str
    variety: str
    quantity_qtl: float
    quantity_kg: float
    current_observed_modal_price: Optional[float] = None
    effective_selling_price_now: float
    price_is_user_adjusted: bool
    observation_date: Optional[date] = None
    data_source: str
    data_freshness_days: int

    sell_now: OptionEvaluation
    wait: OptionEvaluation
    store: OptionEvaluation

    recommended_option: str  # "SELL NOW", "WAIT (X Days)", "STORE (X Days)"
    recommendation_rationale: str
    financial_advantage_amount: float
    financial_advantage_pct: float

    key_sensitivity_drivers: List[str]
    uncertainty_impact_analysis: str
    decision_caveats: List[str]
    calculation_formulas: Dict[str, str]


# ---------------------------------------------------------------------------
# INTELLIGENT MARKET COMPARISON SCHEMAS
# ---------------------------------------------------------------------------
class MarketComparisonRequest(BaseModel):
    commodity: str = Field(..., examples=["Onion"])
    variety: Optional[str] = None
    quantity: float = Field(default=50.0, gt=0)
    quantity_unit: str = Field(default="quintal", description="'kg', 'quintal', or 'tonne'")

    state: Optional[str] = None
    selected_markets: Optional[List[str]] = None
    horizon_days: int = Field(default=0, ge=0, le=30, description="0 for Spot Rate, 7, 14, 30 for Forecast")

    transport_cost_per_km_qtl: float = Field(default=1.5, ge=0)
    transport_fixed_fee: float = Field(default=0.0, ge=0)
    other_cost_per_qtl: float = Field(default=0.0, ge=0)
    other_cost_fixed: float = Field(default=0.0, ge=0)
    reference_market: Optional[str] = None


class MarketComparisonItemDetailed(BaseModel):
    market: str
    district: str
    state: str
    variety: str
    observation_date: date
    data_source: str
    data_freshness_days: int
    is_stale_warning: bool

    price_basis: str  # "Observed Spot Rate" or "X-Day ML Forecast"
    quoted_price_per_qtl: float
    quoted_price_per_kg: float

    distance_km: float
    transport_fixed_cost: float
    transport_variable_cost: float
    total_transport_cost: float
    other_selling_costs: float

    gross_revenue: float
    total_deductions: float
    estimated_net_return: float
    net_return_per_kg: float
    net_difference_vs_reference: float

    forecast_uncertainty_spread_pct: Optional[float] = None
    forecast_reliability_tier: Optional[str] = None
    rank_by_net_return: int
    comparison_notes: List[str]


class MarketComparisonResponse(BaseModel):
    commodity: str
    variety: str
    quantity_qtl: float
    quantity_kg: float
    horizon_days: int
    reference_market: Optional[str] = None
    ranked_markets: List[MarketComparisonItemDetailed]
    best_net_market: Optional[str] = None
    max_gross_market: Optional[str] = None
    arbitrage_insight: str
    evaluation_notes: List[str]
