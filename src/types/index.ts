export interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserInfo {
  id: number;
  username: string;
  email: string;
  role: string;
}

export interface DashboardStats {
  total_records: number;
  evaluator_types: number;
  recent_records: EvaluationRecord[];
  status_distribution: Record<string, number>;
}

export interface EvaluationRecord {
  id: number;
  case_id: string;
  adapter_name: string;
  model_name: string;
  status: string;
  score: number;
  latency_ms: number;
  created_at: string;
}

export interface Evaluator {
  name: string;
  class_name: string;
  module: string;
  docstring: string;
}

export interface Model {
  id: string;
  name: string;
  provider: string;
  provider_name: string;
  status: string;
}

export interface ModelCompareRequest {
  models: { provider: string; name: string }[];
  datasets: string[];
  sample_count?: number;
}

export interface ModelCompareResult {
  model: string;
  provider: string;
  datasets: Record<string, { accuracy: number; samples: number; latency_ms: number }>;
  avg_accuracy: number;
  avg_latency_ms: number;
  total_cost_usd: number;
}

export interface ModelCompareResponse {
  models: ModelCompareResult[];
  datasets: string[];
  summary: {
    best_accuracy: string;
    fastest: string;
  };
}

export interface CostMetrics {
  daily_cost_usd: number;
  weekly_cost_usd: number;
  monthly_cost_usd: number;
  avg_latency_ms: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
  total_requests: number;
  avg_tokens_per_request: number;
  top_models_by_cost: { model_name: string; total_cost: number }[];
  budget_status: {
    daily_budget_ok: boolean;
    daily_usage_percent: number;
    daily_limit: number;
  };
}

export interface ComponentStatus {
  status?: string;
  version?: string;
  error?: string;
}

export interface HealthInfo {
  service: {
    name: string;
    version: string;
    timestamp: number;
  };
  components: {
    redis: ComponentStatus;
    database: ComponentStatus;
    rabbitmq: ComponentStatus;
  };
  metrics: {
    requests_total: number;
    avg_latency_ms: number;
    error_rate: number;
    cache_hit_rate: number;
  };
}

export interface PerformanceMetrics {
  requests_total: number;
  avg_latency_ms: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
  error_rate: number;
  cache_hit_rate: number;
  avg_tokens_per_request?: number;
  daily_cost_usd?: number;
}

export interface EvaluateRequest {
  id: string;
  type: string;
  payload: Record<string, unknown>;
}

export interface EvaluateResponse {
  case_id: string;
  score: number;
  is_valid: boolean;
  status: string;
  latency_ms?: number;
  data?: {
    score?: number;
  };
}

export interface AsyncEvaluateResponse {
  task_id: string;
  case_id: string;
  status: string;
}

export interface TaskStatus {
  task_id: string;
  state: string;
  result?: any;
}

export interface Report {
  filename: string;
  path: string;
  size: number;
  created_at: number;
}