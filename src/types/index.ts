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
  status: string;
  evaluations: number;
  avg_accuracy: number;
  avg_latency_ms: number;
}

export interface ModelCompareRequest {
  models: string[];
  dataset: string;
}

export interface ModelCompareResult {
  model: string;
  accuracy: number;
  latency_ms: number;
  cost: number;
}

export interface ModelCompareResponse {
  report_id: string;
  results: ModelCompareResult[];
}

export interface CostMetrics {
  daily_cost_usd: number;
  weekly_cost_usd: number;
  monthly_cost_usd: number;
  top_models: any[];
  budget_status: {
    daily_usage_percent: number;
  };
}

export interface ComponentStatus {
  status: string;
  version?: string;
  error?: string;
}

export interface HealthInfo {
  service: {
    name: string;
    version: string;
    debug: boolean;
  };
  components: {
    redis: ComponentStatus;
    database: ComponentStatus;
    rabbitmq: ComponentStatus;
    circuit_breakers?: {
      count: number;
      breakers: Record<string, string>;
    };
  };
}

export interface PerformanceMetrics {
  requests_per_minute: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
  error_rate: number;
  cache_hit_rate: number;
  avg_tokens_per_request: number;
  daily_cost_usd: number;
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