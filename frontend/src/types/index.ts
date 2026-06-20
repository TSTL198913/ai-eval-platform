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
}

export interface Model {
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

export interface ModelComparisonResult {
  model_name: string;
  accuracy: number;
  latency_ms: number;
  cost: number;
}

export interface CostMetrics {
  daily_cost: number;
  weekly_cost: number;
  monthly_cost: number;
  budget_used_percent: number;
  budget_limit: number;
  token_usage: number;
}

export interface HealthStatus {
  component: string;
  status: 'healthy' | 'unhealthy' | 'degraded';
  message: string;
  latency_ms?: number;
}

export interface PerformanceMetrics {
  p50_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
  error_rate: number;
  cache_hit_rate: number;
}

export interface RefreshTokenRequest {
  refresh_token: string;
}
