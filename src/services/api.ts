
import axios, { AxiosInstance, AxiosResponse } from 'axios';
import { ApiResponse, LoginRequest, LoginResponse, DashboardStats, Evaluator, Model, ModelCompareRequest, ModelCompareResponse, CostMetrics, HealthInfo, PerformanceMetrics, EvaluationRecord, EvaluateRequest, EvaluateResponse, AsyncEvaluateResponse, TaskStatus } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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
    return handleResponse(response);
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

export default api;
