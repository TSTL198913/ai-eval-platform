import axios, { AxiosInstance, AxiosResponse } from 'axios';
import {
  ApiResponse,
  LoginRequest,
  LoginResponse,
  DashboardStats,
  Evaluator,
  Model,
  EvaluationRecord,
  EvaluateRequest,
  EvaluateResponse,
  ModelComparisonResult,
  CostMetrics,
  HealthStatus,
  PerformanceMetrics,
} from '@/types';

const api: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
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

const extractData = <T>(response: AxiosResponse<ApiResponse<T>>): T => {
  return response.data.data;
};

export const authApi = {
  login: async (data: LoginRequest): Promise<LoginResponse> => {
    const response = await api.post<ApiResponse<LoginResponse>>('/auth/login', data);
    return extractData(response);
  },
  refresh: async (refreshToken: string): Promise<LoginResponse> => {
    const response = await api.post<ApiResponse<LoginResponse>>('/auth/refresh', {
      refresh_token: refreshToken,
    });
    return extractData(response);
  },
  logout: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  },
};

export const dashboardApi = {
  getStats: async (): Promise<DashboardStats> => {
    const response = await api.get<ApiResponse<DashboardStats>>('/dashboard/stats');
    return extractData(response);
  },
  getOverview: async (): Promise<unknown> => {
    const response = await api.get<ApiResponse<unknown>>('/dashboard/overview');
    return extractData(response);
  },
  getTrustScore: async (): Promise<unknown> => {
    const response = await api.get<ApiResponse<unknown>>('/dashboard/trust');
    return extractData(response);
  },
};

export const evaluatorApi = {
  list: async (): Promise<Evaluator[]> => {
    const response = await api.get<ApiResponse<Evaluator[]>>('/evaluators');
    return extractData(response);
  },
  get: async (name: string): Promise<Evaluator> => {
    const response = await api.get<ApiResponse<Evaluator>>(`/evaluators/${name}`);
    return extractData(response);
  },
};

export const modelApi = {
  list: async (): Promise<Model[]> => {
    const response = await api.get<ApiResponse<Model[]>>('/models');
    return extractData(response);
  },
  compare: async (models: string[], dataset: string): Promise<ModelComparisonResult[]> => {
    const response = await api.post<ApiResponse<ModelComparisonResult[]>>('/models/compare', {
      models,
      dataset,
    });
    return extractData(response);
  },
  getPerformance: async (): Promise<unknown> => {
    const response = await api.get<ApiResponse<unknown>>('/models/performance');
    return extractData(response);
  },
};

export const evaluationApi = {
  evaluate: async (data: EvaluateRequest): Promise<EvaluateResponse> => {
    const response = await api.post<ApiResponse<EvaluateResponse>>('/evaluate', data);
    return extractData(response);
  },
  evaluateAsync: async (data: EvaluateRequest): Promise<unknown> => {
    const response = await api.post<ApiResponse<unknown>>('/evaluate/async', data);
    return extractData(response);
  },
  getRecords: async (params?: {
    page?: number;
    page_size?: number;
    evaluator_type?: string;
    status?: string;
    search?: string;
  }): Promise<{ records: EvaluationRecord[]; total: number }> => {
    const response = await api.get<ApiResponse<{ records: EvaluationRecord[]; total: number }>>(
      '/records',
      { params }
    );
    return extractData(response);
  },
  getRecord: async (id: number): Promise<EvaluationRecord> => {
    const response = await api.get<ApiResponse<EvaluationRecord>>(`/records/${id}`);
    return extractData(response);
  },
  deleteRecord: async (id: number): Promise<void> => {
    await api.delete(`/records/${id}`);
  },
  batchDelete: async (ids: number[]): Promise<void> => {
    await api.post('/records/batch/delete', { ids });
  },
};

export const costApi = {
  getMetrics: async (): Promise<CostMetrics> => {
    const response = await api.get<ApiResponse<CostMetrics>>('/cost');
    return extractData(response);
  },
};

export const healthApi = {
  getDetailed: async (): Promise<HealthStatus[]> => {
    const response = await api.get<ApiResponse<HealthStatus[]>>('/health/detailed');
    return extractData(response);
  },
  getMetrics: async (): Promise<PerformanceMetrics> => {
    const response = await api.get<ApiResponse<PerformanceMetrics>>('/metrics');
    return extractData(response);
  },
};

export default api;
