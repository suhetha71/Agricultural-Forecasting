import math
from datetime import date, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_

from app.models.market_observation import MarketObservation
from app.services.forecasting_service import ForecastingService
from app.schemas.decision import (
    DecisionRequest,
    DecisionRecommendation,
    HorizonAnalysis,
    WhatIfSimulationRequest,
    WhatIfSimulationResponse,
    CostBreakdownItem,
    OptionEvaluation,
    ComprehensiveDecisionRequest,
    ComprehensiveDecisionResponse,
    MarketComparisonRequest,
    MarketComparisonItemDetailed,
    MarketComparisonResponse,
)

# Standard empirical post-harvest parameters by commodity
DEFAULT_CROP_PROFILES: Dict[str, Dict[str, Any]] = {
    "onion": {
        "category": "Semi-Perishable",
        "safe_ambient_days": 15,
        "safe_cold_days": 90,
        "monthly_storage_rent": 60.0,    # INR / Quintal / month
        "monthly_shrinkage_pct": 5.0,    # 5% moisture loss & physiological loss / month
    },
    "potato": {
        "category": "Semi-Perishable",
        "safe_ambient_days": 14,
        "safe_cold_days": 180,
        "monthly_storage_rent": 50.0,
        "monthly_shrinkage_pct": 3.0,
    },
    "tomato": {
        "category": "Perishable",
        "safe_ambient_days": 5,
        "safe_cold_days": 14,
        "monthly_storage_rent": 120.0,
        "monthly_shrinkage_pct": 15.0,
    },
    "wheat": {
        "category": "Non-Perishable / Grain",
        "safe_ambient_days": 180,
        "safe_cold_days": 365,
        "monthly_storage_rent": 25.0,
        "monthly_shrinkage_pct": 0.8,
    },
    "cotton": {
        "category": "Non-Perishable / Fiber",
        "safe_ambient_days": 180,
        "safe_cold_days": 365,
        "monthly_storage_rent": 30.0,
        "monthly_shrinkage_pct": 0.5,
    },
    "soyabean": {
        "category": "Non-Perishable / Oilseed",
        "safe_ambient_days": 180,
        "safe_cold_days": 365,
        "monthly_storage_rent": 30.0,
        "monthly_shrinkage_pct": 1.0,
    },
    "mustard": {
        "category": "Non-Perishable / Oilseed",
        "safe_ambient_days": 180,
        "safe_cold_days": 365,
        "monthly_storage_rent": 28.0,
        "monthly_shrinkage_pct": 0.9,
    },
}

# Estimated inter-mandi transit distance matrix (km) for major agricultural hubs
INTER_MANDI_DISTANCES: Dict[Tuple[str, str], float] = {
    ("lasalgaon", "pune"): 195.0,
    ("lasalgaon", "nashik"): 38.0,
    ("lasalgaon", "mumbai"): 225.0,
    ("lasalgaon", "nagpur"): 580.0,
    ("pune", "mumbai"): 150.0,
    ("khanna", "ludhiana"): 45.0,
    ("khanna", "delhi"): 290.0,
    ("kolar", "bangalore"): 68.0,
    ("agra", "delhi"): 210.0,
    ("rajkot", "ahmedabad"): 215.0,
    ("indore", "bhopal"): 195.0,
    ("alwar", "delhi"): 160.0,
}


class DecisionService:
    @staticmethod
    def normalize_quantity_to_qtl(quantity: float, unit: str) -> Tuple[float, float]:
        """
        Validates and converts quantity into standard Quintals (1 Qtl = 100 kg)
        and kilograms.
        """
        if quantity <= 0:
            raise ValueError(f"Quantity must be strictly positive (> 0). Received: {quantity}")

        unit_clean = unit.lower().strip()
        if unit_clean in ("quintal", "qtl", "quintals"):
            qtl = float(quantity)
            kg = qtl * 100.0
        elif unit_clean in ("kg", "kilogram", "kilograms"):
            kg = float(quantity)
            qtl = kg / 100.0
        elif unit_clean in ("tonne", "ton", "tonnes", "tons", "mt"):
            qtl = float(quantity) * 10.0
            kg = qtl * 100.0
        else:
            raise ValueError(
                f"Unsupported unit '{unit}'. Supported units are: 'kg', 'quintal' (100 kg), 'tonne' (1,000 kg)."
            )

        return round(qtl, 4), round(kg, 2)

    @staticmethod
    def get_crop_profile(commodity: str) -> Dict[str, Any]:
        """Return empirical crop storage constraints and post-harvest constants."""
        key = commodity.strip().lower()
        if key in DEFAULT_CROP_PROFILES:
            return DEFAULT_CROP_PROFILES[key]
        return {
            "category": "General Agri-Commodity",
            "safe_ambient_days": 10,
            "safe_cold_days": 60,
            "monthly_storage_rent": 45.0,
            "monthly_shrinkage_pct": 4.0,
        }

    @staticmethod
    def get_inter_mandi_distance(mandi_a: str, mandi_b: str) -> float:
        """Determines estimated road transit distance (km) between mandis."""
        a = mandi_a.strip().lower()
        b = mandi_b.strip().lower()
        if a == b:
            return 0.0
        if (a, b) in INTER_MANDI_DISTANCES:
            return INTER_MANDI_DISTANCES[(a, b)]
        if (b, a) in INTER_MANDI_DISTANCES:
            return INTER_MANDI_DISTANCES[(b, a)]
        # Default representative regional transit distance if mandis are distinct
        return 45.0

    # -----------------------------------------------------------------------
    # 1. COMPREHENSIVE DECISION SUPPORT (Sell Now vs Wait vs Store)
    # -----------------------------------------------------------------------
    @staticmethod
    def evaluate_comprehensive_decision(
        db: Session,
        request: ComprehensiveDecisionRequest
    ) -> ComprehensiveDecisionResponse:
        """
        Evaluates and ranks selling options (Sell Now, Wait, Store)
        using actual market observations, multi-horizon forecasts, holdout uncertainty,
        and explicit user-provided cost structures.
        """
        # Validate and convert quantities
        qty_qtl, qty_kg = DecisionService.normalize_quantity_to_qtl(request.quantity, request.quantity_unit)

        # 1. Fetch latest market observation
        latest_obs = (
            db.query(MarketObservation)
            .filter(
                func.lower(MarketObservation.commodity) == request.commodity.lower(),
                func.lower(MarketObservation.market) == request.market.lower(),
            )
            .order_by(desc(MarketObservation.observation_date))
            .first()
        )

        if latest_obs is None and request.current_price_override is None:
            raise ValueError(
                "No market observation is available for this commodity and market. "
                "Provide a current price quote to run a user-input scenario."
            )

        current_modal = (
            float(latest_obs.modal_price)
            if latest_obs
            else float(request.current_price_override)
        )
        obs_date = latest_obs.observation_date if latest_obs else date.today()
        source_label = latest_obs.source if latest_obs else "USER_PROVIDED_PRICE"
        freshness_days = (date.today() - obs_date).days if latest_obs else 0

        # Account for user price override (quality/grade adjustment)
        effective_p_now = float(request.current_price_override) if request.current_price_override else current_modal
        price_adjusted = request.current_price_override is not None

        # Fetch crop profile & safe storage limits
        profile = DecisionService.get_crop_profile(request.commodity)
        safe_ambient = profile["safe_ambient_days"]
        safe_cold = profile["safe_cold_days"]
        effective_safe_days = safe_cold if request.storage_facility == "cold_storage" else safe_ambient

        monthly_rent = (
            request.user_monthly_storage_rent_qtl
            if request.user_monthly_storage_rent_qtl is not None
            else profile["monthly_storage_rent"]
        )
        monthly_shrinkage = (
            request.user_spoilage_monthly_pct
            if request.user_spoilage_monthly_pct is not None
            else profile["monthly_shrinkage_pct"]
        )

        # 2. Fetch Multi-Horizon Forecasts and Uncertainty
        forecast_resp = ForecastingService.generate_forecast(
            db,
            commodity=request.commodity,
            market=request.market,
            horizon_days=max(request.wait_horizon_days, request.store_horizon_days),
        )

        forecast_lookup: Dict[int, float] = {}
        for pt in forecast_resp.forecasts:
            forecast_lookup[pt.horizon_days] = float(pt.predicted_price)

        # Fetch uncertainty holdout metrics
        uncertainty_resp = ForecastingService.get_forecast_uncertainty(
            db,
            commodity=request.commodity,
            market=request.market,
        )
        rmse_lookup: Dict[int, float] = {}
        for h_item in uncertainty_resp.horizons:
            rmse_lookup[h_item.horizon_days] = h_item.holdout_rmse

        # Fallback RMSE if sample too small
        default_rmse = current_modal * 0.06
        has_wait_holdout_error = 7 in rmse_lookup
        has_store_holdout_error = 30 in rmse_lookup

        # ===================================================================
        # OPTION 1: SELL NOW
        # ===================================================================
        transport_fixed_now = request.transport_fixed_vehicle_fee
        transport_var_now = qty_qtl * request.transport_distance_km * request.transport_cost_per_km_qtl
        transport_total_now = transport_fixed_now + transport_var_now

        other_fixed_now = request.other_cost_fixed
        other_var_now = qty_qtl * request.other_cost_per_qtl
        other_total_now = other_fixed_now + other_var_now

        gross_now = qty_qtl * effective_p_now
        total_deductions_now = transport_total_now + other_total_now
        net_return_now = gross_now - total_deductions_now
        net_per_kg_now = net_return_now / qty_kg

        sell_now_costs = [
            CostBreakdownItem(
                name="Vehicle Mobilization Fee",
                amount=round(transport_fixed_now, 2),
                cost_type="fixed",
                description="Fixed vehicle arrangement & transit base fee",
            ),
            CostBreakdownItem(
                name="Distance Freight Transit",
                amount=round(transport_var_now, 2),
                cost_type="per_unit",
                unit_basis=f"{qty_qtl:.1f} Qtl × {request.transport_distance_km:.0f} km × ₹{request.transport_cost_per_km_qtl}/km/Qtl",
                description="Variable road transport freight to local mandi",
            ),
            CostBreakdownItem(
                name="Mandi Gate & Loading Fee",
                amount=round(other_fixed_now, 2),
                cost_type="fixed",
                description="Fixed gate entry and paperwork fee",
            ),
            CostBreakdownItem(
                name="Handling, Cess & Unloading",
                amount=round(other_var_now, 2),
                cost_type="per_unit",
                unit_basis=f"{qty_qtl:.1f} Qtl × ₹{request.other_cost_per_qtl}/Qtl",
                description="Per-quintal auction yard labor and mandi cess",
            ),
        ]

        sell_now_opt = OptionEvaluation(
            option_id="sell_now",
            title="Sell Immediately (Spot Market)",
            horizon_days=0,
            target_date=obs_date,
            expected_price_per_qtl=round(effective_p_now, 2),
            expected_price_per_kg=round(effective_p_now / 100.0, 2),
            price_basis_type="Adjusted User Selling Price" if price_adjusted else "Observed Mandi Spot Rate",
            initial_quantity_qtl=qty_qtl,
            remaining_quantity_qtl=qty_qtl,
            remaining_quantity_kg=qty_kg,
            spoilage_loss_pct=0.0,
            spoilage_loss_qtl=0.0,
            spoilage_monetary_loss=0.0,
            gross_revenue=round(gross_now, 2),
            fixed_costs_total=round(transport_fixed_now + other_fixed_now, 2),
            variable_costs_total=round(transport_var_now + other_var_now, 2),
            transport_cost_total=round(transport_total_now, 2),
            storage_cost_total=0.0,
            capital_opportunity_cost=0.0,
            other_costs_total=round(other_total_now, 2),
            total_deductions=round(total_deductions_now, 2),
            estimated_net_return=round(net_return_now, 2),
            net_return_per_kg=round(net_per_kg_now, 2),
            net_difference_vs_sell_now=0.0,
            roi_percentage=0.0,
            cost_items=sell_now_costs,
            risk_level="Low",
            assumptions=[
                "Immediate cash realization at current spot/grade quote.",
                "Zero holding period; eliminates physical storage losses and capital lock-in.",
                f"Transport distance benchmarked at {request.transport_distance_km:.1f} km.",
            ],
            warnings=[],
        )

        # ===================================================================
        # OPTION 2: WAIT (Short-Term On-Farm Holding, e.g. 7 Days)
        # ===================================================================
        h_wait = request.wait_horizon_days
        wait_target_date = obs_date + timedelta(days=h_wait)
        wait_forecast_available = h_wait in forecast_lookup
        p_wait = forecast_lookup.get(h_wait, effective_p_now)

        # Holdout error calibration
        rmse_wait = rmse_lookup.get(7, default_rmse)
        p_wait_low = max(0.0, p_wait - 1.96 * rmse_wait)
        p_wait_high = p_wait + 1.96 * rmse_wait

        # On-farm holding natural shrinkage (minimal moisture evaporation over short duration)
        wait_spoilage_rate = (monthly_shrinkage * (h_wait / 30.0)) / 100.0
        qty_wait_qtl = round(qty_qtl * max(0.0, 1.0 - wait_spoilage_rate), 4)
        qty_wait_kg = round(qty_wait_qtl * 100.0, 2)
        spoilage_loss_wait_qtl = round(qty_qtl - qty_wait_qtl, 4)
        spoilage_loss_wait_amount = round(spoilage_loss_wait_qtl * p_wait, 2)

        # Zero commercial storage fee assumed for short-term on-farm holding
        storage_total_wait = 0.0

        # Capital lock-in cost over h_wait days
        capital_cost_wait = (qty_qtl * effective_p_now) * (request.annual_interest_rate_pct / 100.0) * (h_wait / 365.0)

        # Future transport on delivered quantity
        transport_fixed_wait = request.transport_fixed_vehicle_fee
        transport_var_wait = qty_wait_qtl * request.transport_distance_km * request.transport_cost_per_km_qtl
        transport_total_wait = transport_fixed_wait + transport_var_wait

        other_fixed_wait = request.other_cost_fixed
        other_var_wait = qty_wait_qtl * request.other_cost_per_qtl
        other_total_wait = other_fixed_wait + other_var_wait

        gross_wait = qty_wait_qtl * p_wait
        total_deductions_wait = transport_total_wait + storage_total_wait + capital_cost_wait + other_total_wait
        net_return_wait = gross_wait - total_deductions_wait
        net_per_kg_wait = net_return_wait / qty_wait_kg if qty_wait_kg > 0 else 0.0
        diff_wait = net_return_wait - net_return_now
        roi_wait = (diff_wait / net_return_now * 100.0) if net_return_now > 0 else 0.0

        # Downside net return at lower bound of 95% holdout confidence interval
        gross_wait_downside = qty_wait_qtl * p_wait_low
        net_return_wait_downside = gross_wait_downside - total_deductions_wait

        gross_wait_upside = qty_wait_qtl * p_wait_high
        net_return_wait_upside = gross_wait_upside - total_deductions_wait

        wait_warnings = []
        if not wait_forecast_available:
            wait_warnings.append(
                "No fitted forecast is available for this horizon; the current quote is held constant for this calculation."
            )
        if not has_wait_holdout_error:
            wait_warnings.append(
                "No empirical 7-day holdout error is available; the displayed sensitivity range uses an illustrative 6% proxy, not a measured confidence interval."
            )
        if h_wait > safe_ambient and request.storage_facility != "cold_storage":
            wait_warnings.append(
                f"Holding {h_wait} days exceeds safe ambient window ({safe_ambient} days) for {request.commodity}. Spoilage may accelerate."
            )
        if net_return_wait_downside < net_return_now:
            wait_warnings.append(
                f"Downside risk alert: If prices drop to the 95% holdout lower bound (₹{p_wait_low:,.0f}/Qtl), "
                f"waiting yields ₹{abs(net_return_wait_downside - net_return_now):,.0f} LESS than selling today."
            )

        wait_costs = [
            CostBreakdownItem(
                name="Vehicle Mobilization Fee",
                amount=round(transport_fixed_wait, 2),
                cost_type="fixed",
                description="Fixed vehicle arrangement fee for deferred delivery",
            ),
            CostBreakdownItem(
                name="Distance Freight Transit",
                amount=round(transport_var_wait, 2),
                cost_type="per_unit",
                unit_basis=f"{qty_wait_qtl:.1f} Qtl × {request.transport_distance_km:.0f} km × ₹{request.transport_cost_per_km_qtl}/km/Qtl",
                description="Freight applied to actual remaining delivered weight",
            ),
            CostBreakdownItem(
                name="Commercial Storage Rent",
                amount=0.0,
                cost_type="fixed",
                description="₹0 — On-farm / temporary holding without warehouse lease",
            ),
            CostBreakdownItem(
                name="Capital Opportunity Cost",
                amount=round(capital_cost_wait, 2),
                cost_type="per_unit",
                unit_basis=f"{request.annual_interest_rate_pct:.1f}% APR for {h_wait} days on ₹{qty_qtl * effective_p_now:,.0f}",
                description="Imputed interest cost on deferred cash flow",
            ),
            CostBreakdownItem(
                name="Handling & Mandi Charges",
                amount=round(other_total_wait, 2),
                cost_type="per_unit",
                description="Gate entry and unloading costs at future auction",
            ),
        ]

        wait_opt = OptionEvaluation(
            option_id="wait",
            title=f"Wait {h_wait} Days (On-Farm Holding)",
            horizon_days=h_wait,
            target_date=wait_target_date,
            expected_price_per_qtl=round(p_wait, 2),
            expected_price_per_kg=round(p_wait / 100.0, 2),
            price_basis_type=(
                f"{h_wait}-Day Forecast ({forecast_resp.model_used})"
                if wait_forecast_available
                else "Current quote held constant; forecast unavailable"
            ),
            initial_quantity_qtl=qty_qtl,
            remaining_quantity_qtl=qty_wait_qtl,
            remaining_quantity_kg=qty_wait_kg,
            spoilage_loss_pct=round(wait_spoilage_rate * 100.0, 2),
            spoilage_loss_qtl=spoilage_loss_wait_qtl,
            spoilage_monetary_loss=spoilage_loss_wait_amount,
            gross_revenue=round(gross_wait, 2),
            fixed_costs_total=round(transport_fixed_wait + other_fixed_wait, 2),
            variable_costs_total=round(transport_var_wait + other_var_wait + capital_cost_wait, 2),
            transport_cost_total=round(transport_total_wait, 2),
            storage_cost_total=0.0,
            capital_opportunity_cost=round(capital_cost_wait, 2),
            other_costs_total=round(other_total_wait, 2),
            total_deductions=round(total_deductions_wait, 2),
            estimated_net_return=round(net_return_wait, 2),
            net_return_per_kg=round(net_per_kg_wait, 2),
            net_difference_vs_sell_now=round(diff_wait, 2),
            roi_percentage=round(roi_wait, 2),
            uncertainty_lower_bound_price=round(p_wait_low, 2),
            uncertainty_upper_bound_price=round(p_wait_high, 2),
            uncertainty_downside_net_return=round(net_return_wait_downside, 2),
            uncertainty_upside_net_return=round(net_return_wait_upside, 2),
            cost_items=wait_costs,
            risk_level="Moderate" if diff_wait > 0 else "High",
            assumptions=[
                f"Short-term on-farm holding: No commercial warehouse rent is charged.",
                f"Estimated moisture shrinkage of {wait_spoilage_rate * 100.0:.2f}% ({spoilage_loss_wait_qtl:.1f} Qtl).",
                f"Capital opportunity cost calculated at {request.annual_interest_rate_pct:.1f}% APR.",
            ],
            warnings=wait_warnings,
        )

        # ===================================================================
        # OPTION 3: STORE (Medium-Term Commercial Storage, e.g. 30 Days)
        # ===================================================================
        h_store = request.store_horizon_days
        store_target_date = obs_date + timedelta(days=h_store)
        store_forecast_available = h_store in forecast_lookup
        p_store = forecast_lookup.get(h_store, effective_p_now)

        rmse_store = rmse_lookup.get(30, default_rmse * math.sqrt(h_store / 7.0))
        p_store_low = max(0.0, p_store - 1.96 * rmse_store)
        p_store_high = p_store + 1.96 * rmse_store

        # Check Perishability / Storage Feasibility
        is_perishable = profile["category"] == "Perishable"
        is_ambient = request.storage_facility in ("ambient", "none")
        storage_feasible = not (is_perishable and is_ambient)

        store_warnings = []
        if not store_forecast_available:
            store_warnings.append(
                "No fitted forecast is available for this horizon; the current quote is held constant for this calculation."
            )
        if not has_store_holdout_error:
            store_warnings.append(
                "No empirical 30-day holdout error is available; the displayed sensitivity range uses an illustrative proxy, not a measured confidence interval."
            )
        if is_perishable and is_ambient:
            store_warnings.append(
                f"CRITICAL WARNING: {request.commodity} is highly perishable (maximum safe ambient shelf-life is {safe_ambient} days). "
                "Commercial storage without certified cold chain controls will result in catastrophic spoilage (>50%)."
            )
        elif h_store > effective_safe_days:
            store_warnings.append(
                f"Storage duration ({h_store} days) exceeds recommended safe limits ({effective_safe_days} days) for {request.commodity}."
            )

        # Spoilage / Weight Loss
        store_spoilage_rate = (monthly_shrinkage * (h_store / 30.0)) / 100.0
        if is_perishable and is_ambient:
            store_spoilage_rate = min(0.60, store_spoilage_rate + 0.35)

        qty_store_qtl = round(qty_qtl * max(0.0, 1.0 - store_spoilage_rate), 4)
        qty_store_kg = round(qty_store_qtl * 100.0, 2)
        spoilage_loss_store_qtl = round(qty_qtl - qty_store_qtl, 4)
        spoilage_loss_store_amount = round(spoilage_loss_store_qtl * p_store, 2)

        # Storage Costs (Fixed entry fee + monthly rent based on initial stored volume)
        storage_fixed = request.user_storage_fixed_entry_fee
        storage_var = (monthly_rent * (h_store / 30.0)) * qty_qtl
        storage_total_store = storage_fixed + storage_var

        # Capital lock-in cost
        capital_cost_store = (qty_qtl * effective_p_now) * (request.annual_interest_rate_pct / 100.0) * (h_store / 365.0)

        # Future Transport: Charged strictly on remaining delivered quantity to prevent double-counting!
        transport_fixed_store = request.transport_fixed_vehicle_fee
        transport_var_store = qty_store_qtl * request.transport_distance_km * request.transport_cost_per_km_qtl
        transport_total_store = transport_fixed_store + transport_var_store

        other_fixed_store = request.other_cost_fixed
        other_var_store = qty_store_qtl * request.other_cost_per_qtl
        other_total_store = other_fixed_store + other_var_store

        gross_store = qty_store_qtl * p_store
        total_deductions_store = storage_total_store + capital_cost_store + transport_total_store + other_total_store
        net_return_store = gross_store - total_deductions_store
        net_per_kg_store = net_return_store / qty_store_kg if qty_store_kg > 0 else 0.0
        diff_store = net_return_store - net_return_now
        roi_store = (diff_store / net_return_now * 100.0) if net_return_now > 0 else 0.0

        gross_store_downside = qty_store_qtl * p_store_low
        net_return_store_downside = gross_store_downside - total_deductions_store

        gross_store_upside = qty_store_qtl * p_store_high
        net_return_store_upside = gross_store_upside - total_deductions_store

        if net_return_store_downside < net_return_now:
            store_warnings.append(
                f"Holdout risk alert: If {h_store}-day prices align with the 95% holdout lower bound (₹{p_store_low:,.0f}/Qtl), "
                f"storing results in a net deficit of ₹{abs(net_return_store_downside - net_return_now):,.0f} vs selling today."
            )

        store_costs = [
            CostBreakdownItem(
                name="Warehouse Entry & Handling",
                amount=round(storage_fixed, 2),
                cost_type="fixed",
                description="Fixed warehouse in-handling / documentation fee",
            ),
            CostBreakdownItem(
                name="Storage Rent",
                amount=round(storage_var, 2),
                cost_type="per_unit",
                unit_basis=f"₹{monthly_rent:.0f}/Qtl/mo × {qty_qtl:.1f} Qtl × {h_store / 30.0:.2f} months",
                description=f"Lease fee for {request.storage_facility} warehouse",
            ),
            CostBreakdownItem(
                name="Capital Opportunity Cost",
                amount=round(capital_cost_store, 2),
                cost_type="per_unit",
                unit_basis=f"{request.annual_interest_rate_pct:.1f}% APR for {h_store} days on ₹{qty_qtl * effective_p_now:,.0f}",
                description="Opportunity cost of delayed crop liquidation",
            ),
            CostBreakdownItem(
                name="Future Mandi Freight",
                amount=round(transport_total_store, 2),
                cost_type="per_unit",
                unit_basis=f"Charged on {qty_store_qtl:.1f} Qtl remaining weight after shrinkage",
                description="Transport fee to final auction point (zero double-counting)",
            ),
            CostBreakdownItem(
                name="Other Mandi Cess & Handling",
                amount=round(other_total_store, 2),
                cost_type="per_unit",
                description="Discharge fees and mandi taxes at final sale",
            ),
        ]

        store_opt = OptionEvaluation(
            option_id="store",
            title=f"Store {h_store} Days ({request.storage_facility.replace('_', ' ').title()})",
            horizon_days=h_store,
            target_date=store_target_date,
            expected_price_per_qtl=round(p_store, 2),
            expected_price_per_kg=round(p_store / 100.0, 2),
            price_basis_type=(
                f"{h_store}-Day Forecast ({forecast_resp.model_used})"
                if store_forecast_available
                else "Current quote held constant; forecast unavailable"
            ),
            initial_quantity_qtl=qty_qtl,
            remaining_quantity_qtl=qty_store_qtl,
            remaining_quantity_kg=qty_store_kg,
            spoilage_loss_pct=round(store_spoilage_rate * 100.0, 2),
            spoilage_loss_qtl=spoilage_loss_store_qtl,
            spoilage_monetary_loss=spoilage_loss_store_amount,
            gross_revenue=round(gross_store, 2),
            fixed_costs_total=round(storage_fixed + transport_fixed_store + other_fixed_store, 2),
            variable_costs_total=round(storage_var + capital_cost_store + transport_var_store + other_var_store, 2),
            transport_cost_total=round(transport_total_store, 2),
            storage_cost_total=round(storage_total_store, 2),
            capital_opportunity_cost=round(capital_cost_store, 2),
            other_costs_total=round(other_total_store, 2),
            total_deductions=round(total_deductions_store, 2),
            estimated_net_return=round(net_return_store, 2),
            net_return_per_kg=round(net_per_kg_store, 2),
            net_difference_vs_sell_now=round(diff_store, 2),
            roi_percentage=round(roi_store, 2),
            uncertainty_lower_bound_price=round(p_store_low, 2),
            uncertainty_upper_bound_price=round(p_store_high, 2),
            uncertainty_downside_net_return=round(net_return_store_downside, 2),
            uncertainty_upside_net_return=round(net_return_store_upside, 2),
            cost_items=store_costs,
            risk_level="Critical" if (is_perishable and is_ambient) else "High" if diff_store < 0 else "Moderate",
            assumptions=[
                f"Commercial warehouse rate benchmarked at ₹{monthly_rent:.0f}/Qtl/month.",
                f"Physical shrinkage of {store_spoilage_rate * 100.0:.1f}% ({spoilage_loss_store_qtl:.1f} Qtl loss).",
                f"Transport charged once on delivered weight (₹{transport_total_store:,.0f}); zero duplicate transit fee.",
            ],
            warnings=store_warnings,
        )

        # ===================================================================
        # 4. RECOMMENDATION SYNTHESIS & SENSITIVITY DRIVERS
        # ===================================================================
        # Candidates for recommendation
        candidates = [("SELL NOW", 0.0, sell_now_opt)]

        if diff_wait > 0 and (not wait_warnings or "CRITICAL" not in str(wait_warnings)):
            candidates.append((f"WAIT ({h_wait} Days)", diff_wait, wait_opt))

        if storage_feasible and diff_store > 0:
            candidates.append((f"STORE ({h_store} Days)", diff_store, store_opt))

        # Sort by net gain vs selling today
        candidates.sort(key=lambda x: x[1], reverse=True)
        recommended_action, max_gain, winning_opt = candidates[0]

        # Financial advantage
        adv_amount = max(0.0, max_gain)
        adv_pct = (adv_amount / net_return_now * 100.0) if net_return_now > 0 else 0.0

        # Rationales
        if recommended_action == "SELL NOW":
            if is_perishable and is_ambient and diff_store > 0:
                rationale = (
                    f"Immediate liquidation is strongly advised. While seasonal models indicate future price upside, "
                    f"{request.commodity} is perishable and cannot be stored without cold storage facilities. "
                    f"Spot sale locks in ₹{net_return_now:,.0f} net realization without degradation."
                )
            elif diff_wait <= 0 and diff_store <= 0:
                rationale = (
                    f"Selling immediately produces the highest net realization (₹{net_return_now:,.0f}). "
                    f"Expected future price appreciation fails to cover cumulative deductions for transport, "
                    f"weight shrinkage, and capital opportunity costs."
                )
            else:
                rationale = (
                    f"Spot liquidation provides the safest risk-adjusted return (₹{net_return_now:,.0f}). "
                    "Holding gains are marginal and do not adequately compensate for price volatility."
                )
        elif "WAIT" in recommended_action:
            if wait_forecast_available:
                rationale = (
                    f"Short-term on-farm holding ({h_wait} days) is estimated to yield an extra ₹{adv_amount:,.0f} "
                    f"(+{adv_pct:.1f}% net return). The fitted forecast is ₹{p_wait:,.0f}/Qtl; this estimate is uncertain."
                )
            else:
                rationale = (
                    f"At the unchanged current quote, short-term holding is estimated to yield an extra ₹{adv_amount:,.0f}. "
                    "No model forecast was available, so this is a cost-only scenario rather than a price prediction."
                )
        else:
            if store_forecast_available:
                rationale = (
                    f"Medium-term storage ({h_store} days) in {request.storage_facility.replace('_', ' ')} has the highest "
                    f"estimated net return of ₹{winning_opt.estimated_net_return:,.0f} (+₹{adv_amount:,.0f} over selling today), "
                    f"using a fitted forecast of ₹{p_store:,.0f}/Qtl. This is not a guaranteed outcome."
                )
            else:
                rationale = (
                    f"At the unchanged current quote, medium-term storage has the highest calculated net return of "
                    f"₹{winning_opt.estimated_net_return:,.0f}; no model forecast was available, so this is a cost-only scenario."
                )

        # Identify Key Sensitivity Drivers
        sensitivity_drivers: List[str] = []
        # Factor 1: Expected Price Momentum
        delta_p = (winning_opt.expected_price_per_qtl - effective_p_now)
        sensitivity_drivers.append(
            f"Price Trajectory: Projected price change of {delta_p:+,.0f} ₹/Qtl ({delta_p / effective_p_now * 100.0:+.1f}%) "
            f"drives ₹{abs(delta_p * winning_opt.remaining_quantity_qtl):,.0f} gross revenue variance."
        )
        # Factor 2: Weight Shrinkage / Spoilage
        if winning_opt.spoilage_monetary_loss > 0:
            sensitivity_drivers.append(
                f"Moisture Shrinkage: {winning_opt.spoilage_loss_pct:.1f}% weight loss ({winning_opt.spoilage_loss_qtl:.1f} Qtl) "
                f"deducts ₹{winning_opt.spoilage_monetary_loss:,.0f} from potential gross earnings."
            )
        # Factor 3: Storage Rental
        if winning_opt.storage_cost_total > 0:
            sensitivity_drivers.append(
                f"Storage Overhead: Commercial lease fee of ₹{winning_opt.storage_cost_total:,.0f} accounts for "
                f"{(winning_opt.storage_cost_total / winning_opt.total_deductions * 100.0):.1f}% of all post-harvest deductions."
            )
        # Factor 4: Logistics Freight
        sensitivity_drivers.append(
            f"Transport Freight: Road transit at ₹{request.transport_cost_per_km_qtl}/km/Qtl for {request.transport_distance_km:.0f} km "
            f"deducts ₹{winning_opt.transport_cost_total:,.0f} across the {winning_opt.remaining_quantity_qtl:.1f} Qtl delivered."
        )

        # Uncertainty Impact Analysis
        if winning_opt.option_id == "sell_now":
            uncertainty_analysis = (
                "The sell-now calculation uses the current observed or user-provided quote and does not rely on a future-price forecast. "
                "Actual auction realization and selling costs may differ from this estimate (calculated net return: ₹{:,.0f})."
            ).format(net_return_now)
        else:
            empirical_interval_available = (
                has_wait_holdout_error
                if winning_opt.option_id == "wait"
                else has_store_holdout_error
            )
            interval_label = (
                "95% empirical holdout lower bound"
                if empirical_interval_available
                else "illustrative sensitivity range (not an empirical confidence interval)"
            )
            p_low = winning_opt.uncertainty_lower_bound_price or 0.0
            downside_net = winning_opt.uncertainty_downside_net_return or 0.0
            if downside_net < net_return_now:
                uncertainty_analysis = (
                    f"High Sensitivity to Price Assumptions: If prices fall to ₹{p_low:,.0f}/Qtl "
                    f"({interval_label}), net return drops to ₹{downside_net:,.0f}, "
                    f"resulting in an estimated loss of ₹{net_return_now - downside_net:,.0f} relative to selling today. "
                    "Risk-averse farmers should consider locking in spot prices if liquidity is prioritized."
                )
            else:
                uncertainty_analysis = (
                    f"Illustrative Upside: Even at ₹{p_low:,.0f}/Qtl ({interval_label}), "
                    f"the net realization remains ₹{downside_net:,.0f} (+₹{downside_net - net_return_now:,.0f} higher than today), "
                    "providing strong statistical margin of safety."
                )

        decision_caveats = [
            "Net return calculations are engineering approximations based on reported mandi wholesale benchmarks and user-provided freight/storage costs.",
            "Actual auction realizations may vary depending on crop moisture, grading quality, sorting dockage, and local buyer competition.",
            "Forecast prediction intervals represent empirical holdout error dispersion and do not guarantee future market prices against unexpected trade policy changes.",
        ]
        if not latest_obs:
            decision_caveats.append(
                "No market observation was available. Current-price calculations use only the user-provided quote; future prices remain at that quote because no forecast could be fitted."
            )
        if not forecast_resp.is_sufficient_data:
            decision_caveats.append(
                "Historical data was insufficient for a fitted price forecast; wait/store prices use the current quote as an explicit cost-only scenario."
            )
        if not has_wait_holdout_error or not has_store_holdout_error:
            decision_caveats.append(
                "At least one uncertainty range uses an illustrative percentage proxy because the required empirical holdout error was unavailable; it is not a measured confidence interval."
            )
        if freshness_days > 7:
            decision_caveats.append(
                f"Notice: Latest recorded observation for {request.commodity} at {request.market} is {freshness_days} days old ({obs_date}). "
                "Confirm local physical arrivals before dispatching consignments."
            )

        calculation_formulas = {
            "sell_now": "Net Return = (Quantity_qtl × Current_Price) − Fixed_Transport − (Quantity_qtl × Distance_km × Freight_Rate) − Fixed_Mandi_Fee − (Quantity_qtl × Mandi_Cess)",
            "wait": "Net Return = (Quantity_remaining × Forecast_Wait_Price) − Fixed_Transport − (Quantity_remaining × Distance_km × Freight_Rate) − Fixed_Mandi_Fee − (Quantity_remaining × Mandi_Cess) − Capital_Opportunity_Cost",
            "store": "Net Return = (Quantity_remaining × Forecast_Store_Price) − Warehouse_Fixed_Fee − (Quantity_initial × Monthly_Rent × Months) − Capital_Cost − Transport_Remaining − Other_Selling_Costs",
            "capital_opportunity_cost": "Capital_Cost = (Quantity_initial × Current_Price) × (Annual_Interest_Rate / 100) × (Holding_Days / 365)",
            "remaining_quantity": "Quantity_remaining = Quantity_initial × [1 − (Monthly_Shrinkage_Rate × Days / 30)]",
        }

        return ComprehensiveDecisionResponse(
            commodity=request.commodity,
            market=request.market,
            variety=latest_obs.variety if latest_obs else "Other",
            quantity_qtl=qty_qtl,
            quantity_kg=qty_kg,
            current_observed_modal_price=(
                round(float(latest_obs.modal_price), 2) if latest_obs else None
            ),
            effective_selling_price_now=round(effective_p_now, 2),
            price_is_user_adjusted=price_adjusted,
            observation_date=obs_date,
            data_source=source_label,
            data_freshness_days=freshness_days,
            sell_now=sell_now_opt,
            wait=wait_opt,
            store=store_opt,
            recommended_option=recommended_action,
            recommendation_rationale=rationale,
            financial_advantage_amount=round(adv_amount, 2),
            financial_advantage_pct=round(adv_pct, 2),
            key_sensitivity_drivers=sensitivity_drivers,
            uncertainty_impact_analysis=uncertainty_analysis,
            decision_caveats=decision_caveats,
            calculation_formulas=calculation_formulas,
        )

    # -----------------------------------------------------------------------
    # 2. INTELLIGENT MARKET COMPARISON (Arbitrage & Net Realization)
    # -----------------------------------------------------------------------
    @staticmethod
    def compare_markets_intelligently(
        db: Session,
        request: MarketComparisonRequest
    ) -> MarketComparisonResponse:
        """
        Ranks regional agricultural markets by estimated net return after deducting
        user-provided or benchmarked transport freight and handling costs.
        Supports both spot prices and ML forecast horizons.
        """
        qty_qtl, qty_kg = DecisionService.normalize_quantity_to_qtl(request.quantity, request.quantity_unit)

        # 1. Query latest records per market for this commodity
        subquery = (
            db.query(
                MarketObservation.market,
                func.max(MarketObservation.observation_date).label("max_date")
            )
            .filter(func.lower(MarketObservation.commodity) == request.commodity.lower())
        )
        if request.state:
            subquery = subquery.filter(func.lower(MarketObservation.state) == request.state.lower())
        if request.selected_markets:
            mkt_lowers = [m.lower().strip() for m in request.selected_markets]
            subquery = subquery.filter(func.lower(MarketObservation.market).isin(mkt_lowers))
        subquery = subquery.group_by(MarketObservation.market).subquery()

        query = (
            db.query(MarketObservation)
            .join(
                subquery,
                and_(
                    MarketObservation.market == subquery.c.market,
                    MarketObservation.observation_date == subquery.c.max_date
                )
            )
            .filter(func.lower(MarketObservation.commodity) == request.commodity.lower())
        )
        if request.variety:
            query = query.filter(func.lower(MarketObservation.variety) == request.variety.lower())

        latest_mandis = query.all()

        if not latest_mandis:
            # Fallback query without variety filter if strict variety match yields 0
            subquery2 = (
                db.query(
                    MarketObservation.market,
                    func.max(MarketObservation.observation_date).label("max_date")
                )
                .filter(func.lower(MarketObservation.commodity) == request.commodity.lower())
                .group_by(MarketObservation.market)
                .subquery()
            )
            latest_mandis = (
                db.query(MarketObservation)
                .join(
                    subquery2,
                    and_(
                        MarketObservation.market == subquery2.c.market,
                        MarketObservation.observation_date == subquery2.c.max_date
                    )
                )
                .filter(func.lower(MarketObservation.commodity) == request.commodity.lower())
                .all()
            )

        if not latest_mandis:
            return MarketComparisonResponse(
                commodity=request.commodity,
                variety=request.variety or "All Varieties",
                quantity_qtl=qty_qtl,
                quantity_kg=qty_kg,
                horizon_days=request.horizon_days,
                reference_market=request.reference_market,
                ranked_markets=[],
                best_net_market=None,
                max_gross_market=None,
                arbitrage_insight="No active market records found for the requested commodity.",
                evaluation_notes=["Ensure official records have been synced or imported."],
            )

        # 2. Determine Reference Market Net Return if provided
        ref_market_name = (request.reference_market or latest_mandis[0].market).strip().lower()

        items: List[MarketComparisonItemDetailed] = []
        today = date.today()

        for obs in latest_mandis:
            mkt_name = obs.market
            obs_date = obs.observation_date
            freshness_days = (today - obs_date).days if obs_date else 0
            is_stale = freshness_days > 14

            # Determine distance relative to reference market
            distance_km = DecisionService.get_inter_mandi_distance(ref_market_name, mkt_name)

            # Determine Quoted Price: Spot vs Forecast
            quoted_price = float(obs.modal_price)
            price_basis = "Observed Spot Rate"
            forecast_spread = None
            reliability_tier = None
            notes = []

            if request.horizon_days > 0:
                # Generate/lookup forecast for this specific mandi
                try:
                    f_resp = ForecastingService.generate_forecast(
                        db, commodity=request.commodity, market=mkt_name, horizon_days=request.horizon_days
                    )
                    matching_f = next((f for f in f_resp.forecasts if f.horizon_days == request.horizon_days), None)
                    if matching_f:
                        quoted_price = float(matching_f.predicted_price)
                        price_basis = f"{request.horizon_days}-Day ML Forecast"
                        if f_resp.metrics:
                            # 95% spread = 2 * 1.96 * RMSE / price
                            forecast_spread = round((2.0 * 1.96 * f_resp.metrics.rmse / max(quoted_price, 1.0)) * 100.0, 1)
                        reliability_tier = "High" if request.horizon_days <= 7 else "Moderate" if request.horizon_days <= 14 else "Extrapolated"
                    else:
                        notes.append("Forecast horizon beyond model sample; spot rate fallback applied.")
                except Exception:
                    notes.append("Forecast generation unavailable for this mandi; spot rate fallback applied.")

            # Financial Calculations
            transport_fixed = request.transport_fixed_fee
            transport_var = qty_qtl * distance_km * request.transport_cost_per_km_qtl
            transport_total = transport_fixed + transport_var

            other_costs = request.other_cost_fixed + (qty_qtl * request.other_cost_per_qtl)

            gross_rev = qty_qtl * quoted_price
            total_ded = transport_total + other_costs
            net_return = gross_rev - total_ded
            net_per_kg = net_return / qty_kg

            if is_stale:
                notes.append(f"Data Stale: Observation is {freshness_days} days old ({obs_date}).")
            if distance_km == 0:
                notes.append("Local Mandi: Zero inter-mandi road transit cost.")

            items.append(
                MarketComparisonItemDetailed(
                    market=mkt_name,
                    district=obs.district,
                    state=obs.state,
                    variety=obs.variety,
                    observation_date=obs_date,
                    data_source=obs.source,
                    data_freshness_days=freshness_days,
                    is_stale_warning=is_stale,
                    price_basis=price_basis,
                    quoted_price_per_qtl=round(quoted_price, 2),
                    quoted_price_per_kg=round(quoted_price / 100.0, 2),
                    distance_km=round(distance_km, 1),
                    transport_fixed_cost=round(transport_fixed, 2),
                    transport_variable_cost=round(transport_var, 2),
                    total_transport_cost=round(transport_total, 2),
                    other_selling_costs=round(other_costs, 2),
                    gross_revenue=round(gross_rev, 2),
                    total_deductions=round(total_ded, 2),
                    estimated_net_return=round(net_return, 2),
                    net_return_per_kg=round(net_per_kg, 2),
                    net_difference_vs_reference=0.0,  # Computed below
                    forecast_uncertainty_spread_pct=forecast_spread,
                    forecast_reliability_tier=reliability_tier,
                    rank_by_net_return=1,
                    comparison_notes=notes,
                )
            )

        # 3. Rank Strictly by Estimated Net Return Descending
        items.sort(key=lambda x: x.estimated_net_return, reverse=True)

        # Calculate rank and reference differences
        ref_item = next((it for it in items if it.market.strip().lower() == ref_market_name), items[0])
        ref_net = ref_item.estimated_net_return

        for idx, item in enumerate(items):
            item.rank_by_net_return = idx + 1
            item.net_difference_vs_reference = round(item.estimated_net_return - ref_net, 2)

        best_net_item = items[0]
        max_gross_item = max(items, key=lambda x: x.quoted_price_per_qtl)

        # 4. Synthesize Arbitrage Insight
        if best_net_item.market == max_gross_item.market:
            insight = (
                f"{best_net_item.market} delivers both the highest quoted price (₹{best_net_item.quoted_price_per_qtl:,.0f}/Qtl) "
                f"and the highest net realization (₹{best_net_item.estimated_net_return:,.0f}), providing an optimal selling venue."
            )
        else:
            diff_freight = (max_gross_item.total_transport_cost - best_net_item.total_transport_cost)
            insight = (
                f"Transport Cost Arbitrage Alert: While {max_gross_item.market} quotes the highest gross price "
                f"(₹{max_gross_item.quoted_price_per_qtl:,.0f}/Qtl vs ₹{best_net_item.quoted_price_per_qtl:,.0f}/Qtl at {best_net_item.market}), "
                f"the ₹{diff_freight:,.0f} additional transit freight erodes the price premium. "
                f"Selling at {best_net_item.market} yields ₹{best_net_item.estimated_net_return - max_gross_item.estimated_net_return:,.0f} "
                f"MORE in net return after accounting for transport."
            )

        evaluation_notes = [
            f"Quantity analyzed: {qty_qtl:.1f} Quintals ({qty_kg:,.0f} kg) using standard APMC conversion.",
            f"Transport rate: ₹{request.transport_cost_per_km_qtl:.2f}/km/Qtl + ₹{request.transport_fixed_fee:.0f} fixed vehicle mobilization charge.",
            "Rankings prioritize net realization over gross quotes to prevent unprofitable long-distance hauling.",
        ]

        return MarketComparisonResponse(
            commodity=request.commodity,
            variety=request.variety or "All Available Varieties",
            quantity_qtl=qty_qtl,
            quantity_kg=qty_kg,
            horizon_days=request.horizon_days,
            reference_market=request.reference_market,
            ranked_markets=items,
            best_net_market=best_net_item.market,
            max_gross_market=max_gross_item.market,
            arbitrage_insight=insight,
            evaluation_notes=evaluation_notes,
        )

    # -----------------------------------------------------------------------
    # 3. INTERACTIVE WHAT-IF SIMULATOR
    # -----------------------------------------------------------------------
    @staticmethod
    def simulate_what_if(request: WhatIfSimulationRequest) -> WhatIfSimulationResponse:
        """
        Interactive simulation calculator allowing farmers and analysts to model
        custom scenarios: holding duration, prices, storage rents, shrinkage, and freight.
        Strictly labels manually adjusted prices as hypothetical scenarios.
        """
        qty_qtl, qty_kg = DecisionService.normalize_quantity_to_qtl(request.quantity_qtl, request.quantity_unit)

        profile = DecisionService.get_crop_profile(request.commodity)
        monthly_rent = (
            request.monthly_storage_rent_qtl
            if request.monthly_storage_rent_qtl is not None
            else profile["monthly_storage_rent"]
        )
        monthly_shrinkage = (
            request.monthly_shrinkage_pct
            if request.monthly_shrinkage_pct is not None
            else profile["monthly_shrinkage_pct"]
        )

        # Immediate sale calculations
        immediate_transport = request.fixed_transport_fee + (qty_qtl * request.transport_cost_per_km_qtl * request.distance_km)
        immediate_other = request.other_selling_costs
        immediate_gross = qty_qtl * request.current_price
        immediate_net = immediate_gross - immediate_transport - immediate_other
        immediate_net_per_kg = immediate_net / qty_kg if qty_kg > 0 else 0.0

        # Future sale calculations
        shrinkage_rate = (monthly_shrinkage * (request.holding_days / 30.0)) / 100.0
        weight_after_shrinkage_qtl = round(max(0.0, qty_qtl * (1.0 - shrinkage_rate)), 4)
        weight_after_shrinkage_kg = round(weight_after_shrinkage_qtl * 100.0, 2)
        shrinkage_loss_amount = round((qty_qtl - weight_after_shrinkage_qtl) * request.expected_future_price, 2)

        future_storage_cost = (monthly_rent * (request.holding_days / 30.0)) * qty_qtl
        capital_cost = (
            (qty_qtl * request.current_price)
            * (request.annual_interest_rate_pct / 100.0)
            * (request.holding_days / 365.0)
        )
        # Future transport on remaining weight
        future_transport = request.fixed_transport_fee + (weight_after_shrinkage_qtl * request.transport_cost_per_km_qtl * request.distance_km)
        future_other = request.other_selling_costs
        future_gross = weight_after_shrinkage_qtl * request.expected_future_price
        future_net = future_gross - future_storage_cost - capital_cost - future_transport - future_other
        future_net_per_kg = future_net / weight_after_shrinkage_kg if weight_after_shrinkage_kg > 0 else 0.0

        profit_diff = future_net - immediate_net
        pct_diff = round((profit_diff / immediate_net) * 100.0, 2) if immediate_net > 0 else 0.0

        # Breakeven future price calculation:
        # Breakeven: future_net == immediate_net
        # Q_remain * P_be - future_deductions == immediate_net
        future_deductions = future_storage_cost + capital_cost + future_transport + future_other
        breakeven_price = (immediate_net + future_deductions) / weight_after_shrinkage_qtl if weight_after_shrinkage_qtl > 0 else 0.0

        if profit_diff > 0:
            verdict = "FINANCIALLY ADVANTAGEOUS TO HOLD"
            advice = (
                f"Holding for {request.holding_days} days yields an estimated extra net profit of ₹{profit_diff:,.2f} "
                f"(+{pct_diff}%) after deducting all storage fees (₹{future_storage_cost:,.0f}), "
                f"shrinkage loss (₹{shrinkage_loss_amount:,.0f}), and capital opportunity costs (₹{capital_cost:,.0f}). "
                f"Minimum future selling price required to break even is ₹{breakeven_price:,.2f}/Qtl."
            )
        else:
            verdict = "BETTER TO SELL IMMEDIATELY"
            advice = (
                f"Selling today produces ₹{abs(profit_diff):,.2f} MORE in net realization than holding. "
                f"The expected price increase does not cover the ₹{future_storage_cost + shrinkage_loss_amount + capital_cost:,.2f} "
                f"in holding expenses and moisture weight loss. Future price must exceed ₹{breakeven_price:,.2f}/Qtl to break even."
            )

        return WhatIfSimulationResponse(
            quantity_qtl=round(qty_qtl, 4),
            quantity_kg=round(qty_kg, 2),
            immediate_gross_revenue=round(immediate_gross, 2),
            immediate_transport_cost=round(immediate_transport, 2),
            immediate_other_costs=round(immediate_other, 2),
            immediate_net_revenue=round(immediate_net, 2),
            immediate_net_per_kg=round(immediate_net_per_kg, 2),
            future_gross_revenue=round(future_gross, 2),
            future_weight_after_shrinkage_qtl=round(weight_after_shrinkage_qtl, 4),
            future_weight_after_shrinkage_kg=round(weight_after_shrinkage_kg, 2),
            shrinkage_loss_amount=round(shrinkage_loss_amount, 2),
            total_storage_cost=round(future_storage_cost, 2),
            capital_cost=round(capital_cost, 2),
            future_transport_cost=round(future_transport, 2),
            future_other_costs=round(future_other, 2),
            future_net_revenue=round(future_net, 2),
            future_net_per_kg=round(future_net_per_kg, 2),
            absolute_profit_difference=round(profit_diff, 2),
            percentage_gain_loss=pct_diff,
            breakeven_future_price=round(breakeven_price, 2),
            verdict=verdict,
            advice=advice,
        )

    # -----------------------------------------------------------------------
    # 4. LEGACY METHOD COMPATIBILITY
    # -----------------------------------------------------------------------
    @staticmethod
    def evaluate_selling_decision(
        db: Session,
        request: DecisionRequest
    ) -> DecisionRecommendation:
        """Legacy compatibility wrapper for /api/decision/evaluate."""
        comp_req = ComprehensiveDecisionRequest(
            commodity=request.commodity,
            market=request.market,
            quantity=request.current_quantity_qtl,
            quantity_unit="quintal",
            current_price_override=request.current_modal_price,
            storage_facility=request.holding_facility,
            transport_distance_km=request.transport_distance_km,
            user_monthly_storage_rent_qtl=request.custom_monthly_storage_cost,
        )
        res = DecisionService.evaluate_comprehensive_decision(db, comp_req)

        # Also compute 15-day horizon for 3-horizon legacy response
        comp_req_15 = ComprehensiveDecisionRequest(
            commodity=request.commodity,
            market=request.market,
            quantity=request.current_quantity_qtl,
            quantity_unit="quintal",
            current_price_override=request.current_modal_price,
            store_horizon_days=15,
            storage_facility=request.holding_facility,
            transport_distance_km=request.transport_distance_km,
            user_monthly_storage_rent_qtl=request.custom_monthly_storage_cost,
        )
        res_15 = DecisionService.evaluate_comprehensive_decision(db, comp_req_15)

        horizons: List[HorizonAnalysis] = [
            HorizonAnalysis(
                horizon_days=res.wait.horizon_days,
                target_date=res.wait.target_date or date.today(),
                expected_price=res.wait.expected_price_per_qtl,
                expected_gross_revenue=res.wait.gross_revenue,
                storage_cost=res.wait.storage_cost_total,
                weight_loss_loss=res.wait.spoilage_monetary_loss,
                opportunity_cost_capital=res.wait.capital_opportunity_cost,
                total_holding_cost=res.wait.total_deductions,
                expected_net_realization=res.wait.estimated_net_return,
                net_gain_vs_selling_today=res.wait.net_difference_vs_sell_now,
                percent_roi=res.wait.roi_percentage,
                risk_level=res.wait.risk_level,
            ),
            HorizonAnalysis(
                horizon_days=15,
                target_date=res_15.store.target_date or date.today(),
                expected_price=res_15.store.expected_price_per_qtl,
                expected_gross_revenue=res_15.store.gross_revenue,
                storage_cost=res_15.store.storage_cost_total,
                weight_loss_loss=res_15.store.spoilage_monetary_loss,
                opportunity_cost_capital=res_15.store.capital_opportunity_cost,
                total_holding_cost=res_15.store.total_deductions,
                expected_net_realization=res_15.store.estimated_net_return,
                net_gain_vs_selling_today=res_15.store.net_difference_vs_sell_now,
                percent_roi=res_15.store.roi_percentage,
                risk_level=res_15.store.risk_level,
            ),
            HorizonAnalysis(
                horizon_days=res.store.horizon_days,
                target_date=res.store.target_date or date.today(),
                expected_price=res.store.expected_price_per_qtl,
                expected_gross_revenue=res.store.gross_revenue,
                storage_cost=res.store.storage_cost_total,
                weight_loss_loss=res.store.spoilage_monetary_loss,
                opportunity_cost_capital=res.store.capital_opportunity_cost,
                total_holding_cost=res.store.total_deductions,
                expected_net_realization=res.store.estimated_net_return,
                net_gain_vs_selling_today=res.store.net_difference_vs_sell_now,
                percent_roi=res.store.roi_percentage,
                risk_level=res.store.risk_level,
            ),
        ]

        legacy_action = res.recommended_option
        if "STORE" in legacy_action:
            legacy_action = "STORE (15-30 Days)"
        elif "WAIT" in legacy_action:
            legacy_action = "WAIT (3-7 Days)"
        else:
            legacy_action = "SELL NOW"

        return DecisionRecommendation(
            commodity=res.commodity,
            market=res.market,
            current_date=res.observation_date or date.today(),
            current_price=res.effective_selling_price_now,
            recommended_action=legacy_action,
            confidence_score=None,
            rationale=res.recommendation_rationale,
            risk_assessment=res.uncertainty_impact_analysis,
            safe_storage_limit_days=(
                DecisionService.get_crop_profile(request.commodity)["safe_cold_days"]
                if request.holding_facility == "cold_storage"
                else DecisionService.get_crop_profile(request.commodity)["safe_ambient_days"]
            ),
            horizons=horizons,
        )
