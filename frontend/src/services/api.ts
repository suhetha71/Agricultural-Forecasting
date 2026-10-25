import {
  HealthResponse,
  FilterOptions,
  MarketObservation,
  MarketSummary,
  MandiComparisonItem,
  ForecastResponse,
  ForecastModelPreference,
  DecisionRecommendation,
  WhatIfSimulationRequest,
  WhatIfSimulationResponse,
  ImportResult,
  DataSourceStats,
  HistoricalSeriesView,
  SeasonalAnalysisResponse,
  AnomalyDetectionResponse,
  ArrivalsWeatherResponse,
  ModelExplanationResponse,
  ForecastUncertaintyResponse,
  ComprehensiveDecisionRequest,
  ComprehensiveDecisionResponse,
  MarketComparisonRequest,
  MarketComparisonResponse,
  BacktestEvaluationResponse,
  EvaluationRecordsListResponse,
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api";

export interface GovernmentSyncResponse {
  success: boolean;
  status: string;
  message: string;
  instructions?: string | null;
  imported_count: number;
  updated_count: number;
  duplicate_count: number;
  skipped_count: number;
  fetched_count: number;
  total_available_count: number | null;
  pagination_truncated: boolean;
  errors: string[];
}

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const errorText = await res.text();
    let detail = `Request failed: ${res.status}`;
    try {
      const parsed = JSON.parse(errorText);
      if (parsed.detail) detail = parsed.detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getHealth: async (): Promise<HealthResponse> => {
    return fetchJson<HealthResponse>(`${API_BASE_URL}/health`);
  },

  getFilters: async (): Promise<FilterOptions> => {
    return fetchJson<FilterOptions>(`${API_BASE_URL}/market/filters`);
  },

  getDataSourceStats: async (): Promise<DataSourceStats> => {
    return fetchJson<DataSourceStats>(`${API_BASE_URL}/market/stats`);
  },

  syncGovApi: async (params?: {
    apiKey?: string;
    commodity?: string;
    state?: string;
    limit?: number;
  }): Promise<GovernmentSyncResponse> => {
    const query = new URLSearchParams();
    if (params?.commodity) query.set("commodity", params.commodity);
    if (params?.state) query.set("state", params.state);
    if (params?.limit) query.set("limit", params.limit.toString());
    return fetchJson<GovernmentSyncResponse>(
      `${API_BASE_URL}/market/sync-gov-api${query.size ? `?${query.toString()}` : ""}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: params?.apiKey }),
      }
    );
  },

  getObservations: async (params: {
    commodity?: string;
    market?: string;
    state?: string;
    district?: string;
    variety?: string;
    source?: string;
    startDate?: string;
    endDate?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ total: number; data: MarketObservation[] }> => {
    const query = new URLSearchParams();
    if (params.commodity) query.set("commodity", params.commodity);
    if (params.market) query.set("market", params.market);
    if (params.state) query.set("state", params.state);
    if (params.district) query.set("district", params.district);
    if (params.variety) query.set("variety", params.variety);
    if (params.source) query.set("source", params.source);
    if (params.startDate) query.set("start_date", params.startDate);
    if (params.endDate) query.set("end_date", params.endDate);
    if (params.limit) query.set("limit", params.limit.toString());
    if (params.offset) query.set("offset", params.offset.toString());
    return fetchJson<{ total: number; data: MarketObservation[] }>(
      `${API_BASE_URL}/market/observations?${query.toString()}`
    );
  },

  getSummary: async (commodity: string, market: string): Promise<MarketSummary | null> => {
    try {
      return await fetchJson<MarketSummary>(
        `${API_BASE_URL}/market/summary?commodity=${encodeURIComponent(commodity)}&market=${encodeURIComponent(market)}`
      );
    } catch {
      return null;
    }
  },

  compareMandis: async (
    commodity: string,
    referenceMarket?: string,
    state?: string,
    costPerKmQtl: number = 1.5
  ): Promise<MandiComparisonItem[]> => {
    const query = new URLSearchParams({ commodity });
    if (referenceMarket) query.set("reference_market", referenceMarket);
    if (state) query.set("state", state);
    query.set("cost_per_km_qtl", costPerKmQtl.toString());
    return fetchJson<MandiComparisonItem[]>(`${API_BASE_URL}/market/compare?${query.toString()}`);
  },

  getForecast: async (
    commodity: string,
    market: string,
    horizonDays: number = 30,
    model: ForecastModelPreference = "auto"
  ): Promise<ForecastResponse> => {
    const query = new URLSearchParams({
      commodity,
      market,
      horizon_days: horizonDays.toString(),
      model,
    });
    return fetchJson<ForecastResponse>(`${API_BASE_URL}/forecasts?${query.toString()}`);
  },

  evaluateDecision: async (params: {
    commodity: string;
    market: string;
    currentQuantityQtl: number;
    currentModalPrice?: number;
    holdingFacility?: string;
    transportDistanceKm?: number;
    customMonthlyStorageCost?: number;
  }): Promise<DecisionRecommendation> => {
    return fetchJson<DecisionRecommendation>(`${API_BASE_URL}/decision/evaluate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        commodity: params.commodity,
        market: params.market,
        current_quantity_qtl: params.currentQuantityQtl,
        current_modal_price: params.currentModalPrice,
        holding_facility: params.holdingFacility || "ambient",
        transport_distance_km: params.transportDistanceKm || 15.0,
        custom_monthly_storage_cost: params.customMonthlyStorageCost,
      }),
    });
  },

  simulateWhatIf: async (payload: WhatIfSimulationRequest): Promise<WhatIfSimulationResponse> => {
    return fetchJson<WhatIfSimulationResponse>(`${API_BASE_URL}/decision/what-if`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  evaluateComprehensiveDecision: async (
    payload: ComprehensiveDecisionRequest
  ): Promise<ComprehensiveDecisionResponse> => {
    return fetchJson<ComprehensiveDecisionResponse>(`${API_BASE_URL}/decision/evaluate-options`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  compareMarketsIntelligently: async (
    payload: MarketComparisonRequest
  ): Promise<MarketComparisonResponse> => {
    return fetchJson<MarketComparisonResponse>(`${API_BASE_URL}/decision/compare-markets`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  uploadCsv: async (file: File): Promise<ImportResult> => {
    const formData = new FormData();
    formData.append("file", file);
    return fetchJson<ImportResult>(`${API_BASE_URL}/market/upload-csv`, {
      method: "POST",
      body: formData,
    });
  },

  // Market Intelligence & Analytics Endpoints
  getHistoricalViews: async (
    commodity: string,
    market: string,
    granularity: "daily" | "weekly" | "monthly" = "daily"
  ): Promise<HistoricalSeriesView> => {
    const query = new URLSearchParams({
      commodity,
      market,
      granularity,
    });
    return fetchJson<HistoricalSeriesView>(`${API_BASE_URL}/analytics/historical-views?${query.toString()}`);
  },

  getSeasonalAnalysis: async (
    commodity: string,
    market: string
  ): Promise<SeasonalAnalysisResponse> => {
    const query = new URLSearchParams({ commodity, market });
    return fetchJson<SeasonalAnalysisResponse>(`${API_BASE_URL}/analytics/seasonal?${query.toString()}`);
  },

  getAnomalies: async (
    commodity: string,
    market: string,
    thresholdMultiplier: number = 2.5,
    method: "rolling_zscore" | "iqr" = "rolling_zscore"
  ): Promise<AnomalyDetectionResponse> => {
    const query = new URLSearchParams({
      commodity,
      market,
      threshold_multiplier: thresholdMultiplier.toString(),
      method,
    });
    return fetchJson<AnomalyDetectionResponse>(`${API_BASE_URL}/analytics/anomalies?${query.toString()}`);
  },

  getArrivalsWeather: async (
    commodity: string,
    market: string
  ): Promise<ArrivalsWeatherResponse> => {
    const query = new URLSearchParams({ commodity, market });
    return fetchJson<ArrivalsWeatherResponse>(`${API_BASE_URL}/analytics/arrivals-weather?${query.toString()}`);
  },

  getModelExplainability: async (
    commodity: string,
    market: string
  ): Promise<ModelExplanationResponse> => {
    const query = new URLSearchParams({ commodity, market });
    return fetchJson<ModelExplanationResponse>(`${API_BASE_URL}/forecasts/explainability?${query.toString()}`);
  },

  getForecastUncertainty: async (
    commodity: string,
    market: string
  ): Promise<ForecastUncertaintyResponse> => {
    const query = new URLSearchParams({ commodity, market });
    return fetchJson<ForecastUncertaintyResponse>(`${API_BASE_URL}/forecasts/uncertainty?${query.toString()}`);
  },

  getHistoricalBacktest: async (
    commodity: string,
    market: string,
    horizons: number[] = [7, 15, 30],
    modelPreference: ForecastModelPreference = "auto",
    persist: boolean = true,
    availabilityMode: "point_in_time" | "retrospective" = "point_in_time"
  ): Promise<BacktestEvaluationResponse> => {
    const query = new URLSearchParams({
      commodity,
      market,
      model_preference: modelPreference,
      persist: persist.toString(),
      availability_mode: availabilityMode,
    });
    horizons.forEach((h) => query.append("horizons", h.toString()));
    return fetchJson<BacktestEvaluationResponse>(`${API_BASE_URL}/forecasts/backtest?${query.toString()}`);
  },

  getEvaluationRecords: async (params?: {
    commodity?: string;
    market?: string;
    horizonDays?: number;
    recordType?: string;
    limit?: number;
  }): Promise<EvaluationRecordsListResponse> => {
    const query = new URLSearchParams();
    if (params?.commodity) query.set("commodity", params.commodity);
    if (params?.market) query.set("market", params.market);
    if (params?.horizonDays) query.set("horizon_days", params.horizonDays.toString());
    if (params?.recordType) query.set("record_type", params.recordType);
    if (params?.limit) query.set("limit", params.limit.toString());
    return fetchJson<EvaluationRecordsListResponse>(`${API_BASE_URL}/forecasts/evaluations?${query.toString()}`);
  },

  evaluateSavedForecasts: async (
    commodity: string,
    market: string
  ): Promise<{ commodity: string; market: string; evaluated_count: number; message: string }> => {
    const query = new URLSearchParams({ commodity, market });
    return fetchJson<{ commodity: string; market: string; evaluated_count: number; message: string }>(
      `${API_BASE_URL}/forecasts/evaluate-saved?${query.toString()}`,
      { method: "POST" }
    );
  },
};
