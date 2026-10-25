export interface MarketObservation {
  id: number;
  state: string;
  district: string;
  market: string;
  commodity: string;
  variety: string;
  observation_date: string;
  min_price: number | null;
  max_price: number | null;
  modal_price: number;
  arrivals_in_qtl: number | null;
  unit: string;
  original_unit?: string | null;
  source: string;
  retrieval_timestamp: string;
  extra_metadata?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MarketSummary {
  commodity: string;
  market: string;
  state: string;
  latest_date: string | null;
  latest_modal_price: number | null;
  min_modal_price_30d: number | null;
  max_modal_price_30d: number | null;
  avg_modal_price_30d: number | null;
  price_change_7d_pct: number | null;
  total_records: number;
  source: string;
}

export interface MandiComparisonItem {
  market: string;
  district: string;
  state: string;
  latest_date: string;
  modal_price: number;
  min_price: number | null;
  max_price: number | null;
  distance_km_estimate: number;
  estimated_transport_cost_qtl: number;
  net_realization_qtl: number;
  price_difference_vs_local: number;
}

export interface ForecastPoint {
  target_date: string;
  horizon_days: number;
  predicted_price: number;
  lower_ci_80: number | null;
  upper_ci_80: number | null;
  lower_ci_95: number | null;
  upper_ci_95: number | null;
}

export type ForecastModelPreference = "auto" | "holt-winters";

export interface ModelEvaluationMetrics {
  model_name: string;
  model_version: string;
  train_start_date: string | null;
  train_end_date: string | null;
  test_start_date: string | null;
  test_end_date: string | null;
  holdout_samples: number;
  mae: number;
  rmse: number;
  mape: number;
  directional_accuracy_pct: number | null;
  evaluation_method: string;
}

export interface ForecastResponse {
  commodity: string;
  market: string;
  state: string;
  last_observed_date: string;
  last_observed_price: number;
  generated_at: string;
  model_used: string;
  model_version: string;
  metrics: ModelEvaluationMetrics | null;
  forecasts: ForecastPoint[];
  unit: string;
  is_sufficient_data: boolean;
  message: string | null;
}

export interface HorizonAnalysis {
  horizon_days: number;
  target_date: string;
  expected_price: number;
  expected_gross_revenue: number;
  storage_cost: number;
  weight_loss_loss: number;
  opportunity_cost_capital: number;
  total_holding_cost: number;
  expected_net_realization: number;
  net_gain_vs_selling_today: number;
  percent_roi: number;
  risk_level: "Low" | "Moderate" | "High";
}

export interface DecisionRecommendation {
  commodity: string;
  market: string;
  current_date: string;
  current_price: number;
  recommended_action: "SELL NOW" | "WAIT (3-7 Days)" | "STORE (15-30 Days)";
  confidence_score: number | null;
  rationale: string;
  risk_assessment: string;
  safe_storage_limit_days: number;
  horizons: HorizonAnalysis[];
}

export interface WhatIfSimulationRequest {
  commodity: string;
  current_price: number;
  expected_future_price: number;
  holding_days: number;
  quantity_qtl: number;
  quantity_unit?: "kg" | "quintal" | "tonne";
  storage_type?: string;
  monthly_storage_rent_qtl?: number | null;
  monthly_shrinkage_pct?: number | null;
  annual_interest_rate_pct: number;
  transport_cost_per_km_qtl: number;
  distance_km: number;
  fixed_transport_fee?: number;
  other_selling_costs?: number;
}

export interface WhatIfSimulationResponse {
  quantity_qtl: number;
  quantity_kg: number;
  immediate_gross_revenue: number;
  immediate_transport_cost: number;
  immediate_other_costs?: number;
  immediate_net_revenue: number;
  immediate_net_per_kg: number;
  future_gross_revenue: number;
  future_weight_after_shrinkage_qtl: number;
  future_weight_after_shrinkage_kg: number;
  shrinkage_loss_amount: number;
  total_storage_cost: number;
  capital_cost: number;
  future_transport_cost: number;
  future_other_costs?: number;
  future_net_revenue: number;
  future_net_per_kg: number;
  absolute_profit_difference: number;
  percentage_gain_loss: number;
  breakeven_future_price: number;
  verdict: string;
  advice: string;
  scenario_disclaimer?: string;
}

export interface HealthResponse {
  status: string;
  app_name: string;
  version: string;
  timestamp: string;
  database_connected: boolean;
  total_observations: number;
  total_forecasts: number;
}

export interface DataSourceStats {
  official_api_records: number;
  user_csv_records: number;
  demo_seed_records: number;
  total_records: number;
  oldest_observation_date: string | null;
  newest_observation_date: string | null;
  last_retrieval_timestamp: string | null;
}

export interface FilterOptions {
  commodities: string[];
  states: string[];
  districts?: string[];
  markets: string[];
  sources?: string[];
}

export interface ImportResult {
  success: boolean;
  imported_count: number;
  duplicate_count: number;
  skipped_count: number;
  errors: string[];
  message: string;
}

export interface PriceChangeMetric {
  window_days: number;
  window_label: string;
  absolute_change: number;
  percentage_change: number;
  start_date: string;
  end_date: string;
  start_price: number;
  end_price: number;
}

export interface AggregatedPricePoint {
  period_label: string;
  start_date: string;
  end_date: string;
  modal_price_avg: number;
  modal_price_min: number;
  modal_price_max: number;
  total_arrivals_qtl?: number | null;
  observation_count: number;
  rolling_7d_avg?: number | null;
  rolling_14d_avg?: number | null;
  rolling_30d_avg?: number | null;
}

export interface HistoricalSeriesView {
  commodity: string;
  market: string;
  granularity: string;
  total_observations: number;
  period_start: string | null;
  period_end: string | null;
  points: AggregatedPricePoint[];
  price_changes: PriceChangeMetric[];
  current_vs_historical: Record<string, any>;
}

export interface MonthlySeasonalityPoint {
  month_number: number;
  month_name: string;
  avg_modal_price: number;
  min_modal_price: number;
  max_modal_price: number;
  std_modal_price: number;
  observation_count: number;
}

export interface SeasonGroupPoint {
  season_name: string;
  months_included: string;
  avg_modal_price: number;
  observation_count: number;
  crop_season_context: string;
}

export interface SeasonalAnalysisResponse {
  commodity: string;
  market: string;
  total_observations: number;
  historical_span_days: number;
  historical_span_months: number;
  has_sufficient_multiyear_data: boolean;
  data_sufficiency_explanation: string;
  monthly_patterns: MonthlySeasonalityPoint[];
  season_patterns: SeasonGroupPoint[];
}

export interface AnomalyItem {
  observation_date: string;
  commodity: string;
  market: string;
  modal_price: number;
  baseline_price: number;
  threshold_upper: number;
  threshold_lower: number;
  deviation_amount: number;
  z_score?: number | null;
  anomaly_type: "HIGH_SPIKE" | "LOW_CRASH" | "SUSPECTED_DATA_ERROR";
  severity: "MILD" | "MODERATE" | "EXTREME";
  explanation: string;
  is_verified_data_error: boolean;
}

export interface AnomalyDetectionResponse {
  commodity: string;
  market: string;
  detection_method: string;
  threshold_multiplier: number;
  total_observations_analyzed: number;
  anomaly_count: number;
  data_error_count: number;
  anomalies: AnomalyItem[];
  method_explanation: string;
}

export interface FeatureImportanceItem {
  feature_name: string;
  display_name: string;
  importance_pct: number;
  direction: "positive" | "negative" | "neutral";
  description: string;
  sample_value?: number | null;
}

export interface ModelExplanationResponse {
  commodity: string;
  market: string;
  model_name: string;
  is_explainable: boolean;
  total_training_samples: number;
  features: FeatureImportanceItem[];
  shap_summary_available: boolean;
  shap_base_value?: number | null;
  causality_disclaimer: string;
  message?: string | null;
}

export interface HorizonRiskItem {
  horizon_days: number;
  horizon_label: string;
  holdout_mae: number;
  holdout_rmse: number;
  holdout_mape: number;
  confidence_spread_pct: number;
  reliability_tier: "High" | "Moderate" | "Extrapolated";
  risk_notes: string;
}

export interface ForecastUncertaintyResponse {
  commodity: string;
  market: string;
  evaluation_sample_size: number;
  is_sample_sufficient: boolean;
  horizons: HorizonRiskItem[];
  methodology_explanation: string;
  horizon_extrapolation_warning?: string | null;
  disclaimer: string;
}

export interface ArrivalsWeatherResponse {
  commodity: string;
  market: string;
  total_observations: number;
  arrivals_reported_count: number;
  arrivals_coverage_pct: number;
  price_arrival_correlation?: number | null;
  correlation_significance?: string | null;
  correlation_interpretation: string;
  weather_source: string;
  weather_available: boolean;
  weather_data_notes: string;
  weather_status: string;
  weather_location?: {
    name: string;
    latitude: number;
    longitude: number;
    coordinate_precision: string;
  } | null;
  weather_observations: Array<{
    observation_date: string;
    temperature_max_c?: number | null;
    temperature_min_c?: number | null;
    precipitation_mm?: number | null;
  }>;
  weather_aligned_count: number;
  weather_missing_date_count: number;
  weather_attribution_url?: string | null;
}

export interface CostBreakdownItem {
  name: string;
  amount: number;
  cost_type: "fixed" | "per_unit";
  unit_basis?: string;
  description: string;
}

export interface OptionEvaluation {
  option_id: "sell_now" | "wait" | "store";
  title: string;
  horizon_days: number;
  target_date?: string | null;
  expected_price_per_qtl: number;
  expected_price_per_kg: number;
  price_basis_type: string;
  initial_quantity_qtl: number;
  remaining_quantity_qtl: number;
  remaining_quantity_kg: number;
  spoilage_loss_pct: number;
  spoilage_loss_qtl: number;
  spoilage_monetary_loss: number;
  gross_revenue: number;
  fixed_costs_total: number;
  variable_costs_total: number;
  transport_cost_total: number;
  storage_cost_total: number;
  capital_opportunity_cost: number;
  other_costs_total: number;
  total_deductions: number;
  estimated_net_return: number;
  net_return_per_kg: number;
  net_difference_vs_sell_now: number;
  roi_percentage: number;
  uncertainty_lower_bound_price?: number | null;
  uncertainty_upper_bound_price?: number | null;
  uncertainty_downside_net_return?: number | null;
  uncertainty_upside_net_return?: number | null;
  cost_items: CostBreakdownItem[];
  risk_level: "Low" | "Moderate" | "High" | "Critical";
  assumptions: string[];
  warnings: string[];
}

export interface ComprehensiveDecisionRequest {
  commodity: string;
  market: string;
  variety?: string | null;
  quantity: number;
  quantity_unit?: "kg" | "quintal" | "tonne";
  current_price_override?: number | null;
  wait_horizon_days?: number;
  store_horizon_days?: number;
  storage_facility?: "none" | "ambient" | "cold_storage";
  user_monthly_storage_rent_qtl?: number | null;
  user_storage_fixed_entry_fee?: number;
  user_spoilage_monthly_pct?: number | null;
  transport_distance_km?: number;
  transport_cost_per_km_qtl?: number;
  transport_fixed_vehicle_fee?: number;
  other_cost_fixed?: number;
  other_cost_per_qtl?: number;
  annual_interest_rate_pct?: number;
}

export interface ComprehensiveDecisionResponse {
  commodity: string;
  market: string;
  variety: string;
  quantity_qtl: number;
  quantity_kg: number;
  current_observed_modal_price: number | null;
  effective_selling_price_now: number;
  price_is_user_adjusted: boolean;
  observation_date?: string | null;
  data_source: string;
  data_freshness_days: number;
  sell_now: OptionEvaluation;
  wait: OptionEvaluation;
  store: OptionEvaluation;
  recommended_option: string;
  recommendation_rationale: string;
  financial_advantage_amount: number;
  financial_advantage_pct: number;
  key_sensitivity_drivers: string[];
  uncertainty_impact_analysis: string;
  decision_caveats: string[];
  calculation_formulas: Record<string, string>;
}

export interface MarketComparisonRequest {
  commodity: string;
  variety?: string | null;
  quantity: number;
  quantity_unit?: "kg" | "quintal" | "tonne";
  state?: string | null;
  selected_markets?: string[] | null;
  horizon_days?: number;
  transport_cost_per_km_qtl?: number;
  transport_fixed_fee?: number;
  other_cost_per_qtl?: number;
  other_cost_fixed?: number;
  reference_market?: string | null;
}

export interface MarketComparisonItemDetailed {
  market: string;
  district: string;
  state: string;
  variety: string;
  observation_date: string;
  data_source: string;
  data_freshness_days: number;
  is_stale_warning: boolean;
  price_basis: string;
  quoted_price_per_qtl: number;
  quoted_price_per_kg: number;
  distance_km: number;
  transport_fixed_cost: number;
  transport_variable_cost: number;
  total_transport_cost: number;
  other_selling_costs: number;
  gross_revenue: number;
  total_deductions: number;
  estimated_net_return: number;
  net_return_per_kg: number;
  net_difference_vs_reference: number;
  forecast_uncertainty_spread_pct?: number | null;
  forecast_reliability_tier?: string | null;
  rank_by_net_return: number;
  comparison_notes: string[];
}

export interface MarketComparisonResponse {
  commodity: string;
  variety: string;
  quantity_qtl: number;
  quantity_kg: number;
  horizon_days: number;
  reference_market?: string | null;
  ranked_markets: MarketComparisonItemDetailed[];
  best_net_market?: string | null;
  max_gross_market?: string | null;
  arbitrage_insight: string;
  evaluation_notes: string[];
}

export interface PredictionActualRecord {
  id?: number | null;
  record_type: "WALK_FORWARD_BACKTEST" | "SAVED_LIVE_FORECAST" | string;
  commodity: string;
  variety?: string | null;
  market: string;
  state?: string | null;
  forecast_date: string;
  target_date: string;
  horizon_days: number;
  predicted_price: number;
  actual_price: number;
  absolute_error: number;
  percentage_error: number;
  baseline_predicted_price: number;
  baseline_absolute_error: number;
  model_name: string;
  model_version: string;
  price_unit: string;
  data_source: string;
  availability_mode?: "POINT_IN_TIME" | "RETROSPECTIVE" | null;
  created_at?: string | null;
}

export interface ModelAccuracyMetricSet {
  model_name: string;
  mae: number;
  rmse: number;
  mape: number;
  sample_count: number;
  directional_accuracy_pct?: number | null;
  win_rate_vs_baseline_pct?: number | null;
}

export interface HorizonEvaluationSummary {
  horizon_days: number;
  horizon_label: string;
  sample_count: number;
  missing_observations_count: number;
  candidate_metrics: ModelAccuracyMetricSet;
  baseline_metrics: ModelAccuracyMetricSet;
  outperformed_baseline: boolean;
  evaluation_verdict: string;
  reliability_tier: string;
  risk_notes: string;
}

export interface BacktestEvaluationResponse {
  commodity: string;
  market: string;
  variety?: string | null;
  state?: string | null;
  price_unit: string;
  data_source: string;
  last_observed_date: string | null;
  last_observed_price: number | null;
  evaluation_start_date: string | null;
  evaluation_end_date: string | null;
  total_historical_records: number;
  total_matched_predictions: number;
  is_sufficient_sample: boolean;
  insufficient_reason?: string | null;
  horizons: HorizonEvaluationSummary[];
  recent_prediction_records: PredictionActualRecord[];
  metric_explanations: Record<string, string>;
  methodology_notes: string;
  historical_reliability_caveats: string;
  generated_at: string;
  availability_mode: "POINT_IN_TIME" | "RETROSPECTIVE";
  availability_note?: string | null;
}

export interface EvaluationRecordsListResponse {
  commodity?: string | null;
  market?: string | null;
  horizon_days?: number | null;
  record_type?: string | null;
  total_count: number;
  records: PredictionActualRecord[];
}
