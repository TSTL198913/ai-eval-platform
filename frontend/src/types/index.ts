export interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
}

export interface User {
  id: number;
  username: string;
  email: string;
  role: string;
  created_at: string;
}

export type UserInfo = User;

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  user: User;
}

export interface DashboardStats {
  total_evaluations: number;
  active_models: number;
  evaluator_count: number;
  success_rate: number;
  avg_latency_ms: number;
  monthly_cost: number;
  status_distribution?: Record<string, number>;
  total_records?: number;
  evaluator_types?: string[];
  recent_records?: EvaluationRecord[];
}

export interface Evaluator {
  name: string;
  display_name: string;
  description: string;
  module_name: string;
  class_name: string;
  supported_types: string[];
  version: string;
  enabled: boolean;
  docstring?: string;
  module?: string;
}

export interface Model {
  id?: string;
  name: string;
  provider: string;
  display_name: string;
  description: string;
  capabilities: string[];
  status: 'active' | 'inactive';
}

export interface EvaluationRecord {
  id: number;
  case_id: string;
  adapter_name: string;
  model_name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  score: number;
  latency_ms: number;
  created_at: string;
  updated_at: string;
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
  data?: Record<string, unknown>;
}

export type AsyncEvaluateResponse = EvaluateResponse;

export interface TaskStatus {
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress?: number;
  result?: EvaluateResponse;
  error?: string;
}

export interface ModelCompareRequest {
  models: Array<{ provider: string; name: string }>;
  datasets: string[];
  sample_count: number;
}

export interface ModelCompareResponse {
  models: ModelComparisonResult[];
}

export interface ModelComparisonResult {
  model_name: string;
  model?: string;
  provider?: string;
  accuracy: number;
  avg_accuracy?: number;
  latency_ms: number;
  avg_latency_ms?: number;
  cost: number;
  total_cost_usd?: number;
}

export interface CostMetrics {
  daily_cost: number;
  daily_cost_usd?: number;
  weekly_cost: number;
  weekly_cost_usd?: number;
  monthly_cost: number;
  monthly_cost_usd?: number;
  budget_used_percent: number;
  budget_limit: number;
  budget_status?: {
    daily_usage_percent?: number;
    daily_limit?: number;
  };
  token_usage: number;
  avg_latency_ms?: number;
  p95_latency_ms?: number;
  total_requests?: number;
  avg_tokens_per_request?: number;
  top_models_by_cost?: Array<{ model_name: string; cost: number; total_cost?: number }>;
}

export interface HealthStatus {
  component: string;
  status: 'healthy' | 'unhealthy' | 'degraded';
  message: string;
  latency_ms?: number;
}

export interface HealthInfo {
  status: 'healthy' | 'unhealthy' | 'degraded';
  components: {
    redis?: { status: string; version?: string; error?: string; message?: string };
    database?: { status: string; error?: string };
    rabbitmq?: { status: string; error?: string; message?: string };
  };
  service?: { name: string; version: string };
  uptime: string;
}

export interface PerformanceMetrics {
  p50_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
  error_rate: number;
  cache_hit_rate: number;
  requests_total?: number;
  avg_tokens_per_request?: number;
  daily_cost_usd?: number;
}

export interface Report {
  id: string;
  name: string;
  type: string;
  generated_at: string;
  status: 'pending' | 'completed' | 'failed';
  url?: string;
  filename?: string;
  path?: string;
  size?: number;
  created_at?: number;
}

export interface RefreshTokenRequest {
  refresh_token: string;
}
