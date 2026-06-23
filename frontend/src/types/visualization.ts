/**
 * 📊 src/types/visualization.ts
 * 可视化数据 TypeScript 类型定义
 */

export interface KpiCard {
  label: string;
  value: number | string;
  unit?: string;
}

export interface RadarChartData {
  chart_type: 'radar';
  title: string;
  indicator: Array<{ name: string; max: number }>;
  series: Array<{
    name: string;
    value: number[];
    metadata?: Record<string, any>;
  }>;
  legend: string[];
  generated_at: string;
}

export interface TrendChartData {
  chart_type: 'line';
  title: string;
  x_axis: { type: string; data: string[]; name: string };
  y_axis: { type: string; name: string; min: number; max: number };
  series: Array<{
    name: string;
    type: string;
    data: any[];
    smooth: boolean;
    showSymbol: boolean;
  }>;
  time_unit: string;
  generated_at: string;
}

export interface DistributionChartData {
  chart_type: 'histogram';
  bins: string[];
  counts: number[];
  stats: {
    count: number;
    mean: number;
    median: number;
    stdev: number;
    min: number;
    max: number;
    q1?: number;
    q3?: number;
  };
  generated_at: string;
}

export interface BoxplotData {
  chart_type: 'boxplot';
  title: string;
  categories: string[];
  box_data: Array<[number, number, number, number, number]>; // [min, q1, median, q3, max]
  generated_at: string;
}

export interface HeatmapData {
  chart_type: 'heatmap';
  title: string;
  x_labels: string[];
  y_labels: string[];
  data: Array<[number, number, number]>; // [x_index, y_index, value]
  min_value: number;
  max_value: number;
  generated_at: string;
}

export interface DashboardData {
  kpi_cards: KpiCard[];
  radar_chart: RadarChartData;
  trend_chart: TrendChartData;
  distribution_chart: DistributionChartData;
  boxplot: BoxplotData;
  heatmap: HeatmapData;
  generated_at: string;
  total_evaluations: number;
}
