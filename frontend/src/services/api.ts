import axios, { AxiosInstance, AxiosResponse } from 'axios';
import { ApiResponse, LoginRequest, LoginResponse, DashboardStats, Evaluator, Model, ModelCompareRequest, ModelCompareResponse, CostMetrics, HealthInfo, PerformanceMetrics, EvaluationRecord, EvaluateRequest, EvaluateResponse, AsyncEvaluateResponse, TaskStatus, Report } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      const event = new CustomEvent('auth-logout');
      window.dispatchEvent(event);
      window.location.href = '/login';
    }
    throw error;
  }
);

async function handleResponse<T>(response: AxiosResponse<ApiResponse<T>>): Promise<T> {
  if (response.data.code !== 0) {
    throw new Error(response.data.message);
  }
  return response.data.data;
}

export const authApi = {
  login: async (data: LoginRequest): Promise<LoginResponse> => {
    const response = await api.post<ApiResponse<LoginResponse>>('/api/v1/auth/login', data);
    return handleResponse(response);
  },
  refresh: async (refreshToken: string): Promise<LoginResponse> => {
    const response = await api.post<ApiResponse<LoginResponse>>('/api/v1/auth/refresh', { refresh_token: refreshToken });
    return handleResponse(response);
  },
};

export const dashboardApi = {
  getStats: async (): Promise<DashboardStats> => {
    const response = await api.get<ApiResponse<DashboardStats>>('/api/v1/dashboard/stats');
    return handleResponse(response);
  },
};

export const evaluatorApi = {
  getAll: async (): Promise<Evaluator[]> => {
    const response = await api.get<ApiResponse<Evaluator[]>>('/api/v1/evaluators');
    return handleResponse(response);
  },
  getByName: async (name: string): Promise<Evaluator> => {
    const response = await api.get<ApiResponse<Evaluator>>(`/api/v1/evaluators/${name}`);
    return handleResponse(response);
  },
};

export const modelApi = {
  getAll: async (): Promise<Model[]> => {
    const response = await api.get<ApiResponse<Model[]>>('/api/v1/models');
    return handleResponse(response);
  },
  compare: async (data: ModelCompareRequest): Promise<ModelCompareResponse> => {
    const response = await api.post<ApiResponse<ModelCompareResponse>>('/api/v1/models/compare', data);
    return handleResponse(response);
  },
};

export const evaluationApi = {
  evaluate: async (data: EvaluateRequest): Promise<EvaluateResponse> => {
    const response = await api.post<ApiResponse<EvaluateResponse>>('/api/v1/evaluate', data);
    return handleResponse(response);
  },
  evaluateAsync: async (data: EvaluateRequest): Promise<AsyncEvaluateResponse> => {
    const response = await api.post<ApiResponse<AsyncEvaluateResponse>>('/api/v1/evaluate/async', data);
    return handleResponse(response);
  },
  getRecords: async (params?: { evaluator?: string; status?: string; limit?: number }): Promise<{ count: number; records: EvaluationRecord[] }> => {
    const response = await api.get<ApiResponse<{ count: number; records: EvaluationRecord[] }>>('/api/v1/records', { params });
    const data = await handleResponse(response);
    return { count: data.count, records: data.records || [] };
  },
  searchRecords: async (params: { evaluator?: string; status?: string; limit?: number }): Promise<{ count: number; records: EvaluationRecord[] }> => {
    const response = await api.get<ApiResponse<{ count: number; records: EvaluationRecord[] }>>('/api/v1/records/search', { params });
    return handleResponse(response);
  },
  getTaskStatus: async (taskId: string): Promise<TaskStatus> => {
    const response = await api.get<ApiResponse<TaskStatus>>(`/api/v1/tasks/${taskId}`);
    return handleResponse(response);
  },
};

export const costApi = {
  getMetrics: async (): Promise<CostMetrics> => {
    const response = await api.get<ApiResponse<CostMetrics>>('/api/v1/cost');
    return handleResponse(response);
  },
};

export const healthApi = {
  getDetailed: async (): Promise<HealthInfo> => {
    const response = await api.get<ApiResponse<HealthInfo>>('/api/v1/health/detailed');
    return handleResponse(response);
  },
  getMetrics: async (): Promise<PerformanceMetrics> => {
    const response = await api.get<ApiResponse<PerformanceMetrics>>('/api/v1/metrics');
    return handleResponse(response);
  },
};

export const reportApi = {
  getReports: async (): Promise<{ reports: Report[] }> => {
    const response = await api.get<ApiResponse<{ reports: Report[] }>>('/api/v1/reports');
    return handleResponse(response);
  },
  generateReport: async (): Promise<void> => {
    const response = await api.post<ApiResponse<void>>('/api/v1/reports/generate');
    return handleResponse(response);
  },
};

// 评估配置API
export interface EvalConfig {
  id?: string;
  name: string;
  evaluator_type: string;
  config: Record<string, any>;
  enabled: boolean;
}

export const evalConfigApi = {
  getAll: async (): Promise<EvalConfig[]> => {
    const response = await api.get<ApiResponse<EvalConfig[]>>('/api/v1/eval-configs');
    return handleResponse(response);
  },
  save: async (config: Partial<EvalConfig>): Promise<EvalConfig> => {
    const response = await api.post<ApiResponse<EvalConfig>>('/api/v1/eval-configs', config);
    return handleResponse(response);
  },
  delete: async (configId: string): Promise<void> => {
    const response = await api.delete<ApiResponse<void>>(`/api/v1/eval-configs/${configId}`);
    return handleResponse(response);
  },
};

// 批量评估API
export interface BatchEvaluateRequest {
  cases: EvaluateRequest[];
}

export interface BatchEvaluateResult {
  total: number;
  passed: number;
  failed: number;
  results: Array<{
    case_id: string;
    status: string;
    score?: number;
    latency_ms?: number;
    message?: string;
  }>;
}

export const batchEvaluateApi = {
  syncBatch: async (data: BatchEvaluateRequest): Promise<BatchEvaluateResult> => {
    const response = await api.post<ApiResponse<BatchEvaluateResult>>('/api/v1/evaluate/sync-batch', data);
    return handleResponse(response);
  },
};

// 批量重新评估API
export interface BatchReevaluateRequest {
  record_ids: number[];
}

export interface BatchReevaluateResult {
  total: number;
  success_count: number;
  failed_count: number;
  results: Array<{
    record_id: number;
    case_id?: string;
    status: string;
    score?: number;
    latency_ms?: number;
    message?: string;
  }>;
}

export const recordsApi = {
  batchReevaluate: async (data: BatchReevaluateRequest): Promise<BatchReevaluateResult> => {
    const response = await api.post<ApiResponse<BatchReevaluateResult>>('/api/v1/records/batch/reevaluate', data);
    return handleResponse(response);
  },
  batchDelete: async (ids: number[]): Promise<{ deleted_count: number }> => {
    const response = await api.post<ApiResponse<{ deleted_count: number }>>('/api/v1/records/batch/delete', { ids });
    return handleResponse(response);
  },
  batchUpdate: async (ids: number[], data: Record<string, any>): Promise<{ updated_count: number }> => {
    const response = await api.post<ApiResponse<{ updated_count: number }>>('/api/v1/records/batch/update', { ids, data });
    return handleResponse(response);
  },
};

export default api;
