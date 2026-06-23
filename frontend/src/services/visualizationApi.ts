/**
 * 📡 src/services/visualizationApi.ts
 * 可视化数据 API 客户端
 */

import axios from 'axios';
import type { DashboardData } from '../types/visualization';

const API_BASE = '/api/v1/visualization';

export const visualizationApi = {
  /**
   * 获取综合仪表盘数据
   */
  async getDashboard(evaluatorTypes?: string, days: number = 30): Promise<DashboardData> {
    const params: Record<string, any> = { days };
    if (evaluatorTypes) params.evaluator_types = evaluatorTypes;
    const response = await axios.get(`${API_BASE}/dashboard`, { params });
    return response.data.data;
  },

  /**
   * 获取雷达图数据
   */
  async getRadar(evaluatorTypes?: string): Promise<any> {
    const params: Record<string, any> = {};
    if (evaluatorTypes) params.evaluator_types = evaluatorTypes;
    const response = await axios.get(`${API_BASE}/radar`, { params });
    return response.data.data;
  },

  /**
   * 获取趋势图数据
   */
  async getTrend(bucket: 'day' | 'hour' | 'minute' = 'day', days: number = 30): Promise<any> {
    const response = await axios.get(`${API_BASE}/trend`, {
      params: { bucket, days },
    });
    return response.data.data;
  },

  /**
   * 获取分布图数据
   */
  async getDistribution(binCount: number = 10): Promise<any> {
    const response = await axios.get(`${API_BASE}/distribution`, {
      params: { bin_count: binCount },
    });
    return response.data.data;
  },

  /**
   * 获取箱线图数据
   */
  async getBoxplot(): Promise<any> {
    const response = await axios.get(`${API_BASE}/boxplot`);
    return response.data.data;
  },

  /**
   * 获取热力图数据
   */
  async getHeatmap(): Promise<any> {
    const response = await axios.get(`${API_BASE}/heatmap`);
    return response.data.data;
  },

  /**
   * HTML 报告 URL
   */
  getHtmlReportUrl(title: string = 'AI 评测报告', days: number = 30): string {
    return `${API_BASE}/report/html?title=${encodeURIComponent(title)}&days=${days}`;
  },

  /**
   * Markdown 报告
   */
  async getMarkdownReport(title: string = 'AI 评测报告', days: number = 30): Promise<any> {
    const response = await axios.get(`${API_BASE}/report/markdown`, {
      params: { title, days },
    });
    return response.data;
  },
};

export default visualizationApi;
