/**
 * 📈 EvaluationDashboard.tsx
 * 综合评估仪表盘组件 - 2026 工业级
 * 支持雷达图、趋势图、分布图、热力图、箱线图
 */

import React, { useEffect, useState } from 'react';
import {
  Card,
  Row,
  Col,
  Spin,
  Alert,
  Statistic,
  Button,
  Space,
  Tabs,
} from 'antd';
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  BarChart,
  Bar,
} from 'recharts';
import { RefreshCw, FileText, Download } from 'lucide-react';
import { visualizationApi } from '../services/visualizationApi';
import type { DashboardData } from '../types/visualization';

interface EvaluationDashboardProps {
  title?: string;
  evaluatorTypes?: string[];
}

const EvaluationDashboard: React.FC<EvaluationDashboardProps> = ({
  title = 'AI 评测仪表盘',
  evaluatorTypes,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [activeTab, setActiveTab] = useState('overview');

  const fetchDashboard = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await visualizationApi.getDashboard(
        evaluatorTypes?.join(','),
        30,
      );
      setDashboard(data);
    } catch (err: any) {
      const msg = err?.message || '加载仪表盘数据失败';
      setError(msg);
      console.error('Dashboard load failed:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleDownloadReport = async (format: 'html' | 'markdown') => {
    try {
      if (format === 'html') {
        const url = visualizationApi.getHtmlReportUrl(title);
        window.open(url, '_blank');
      } else {
        const result = await visualizationApi.getMarkdownReport(title);
        const blob = new Blob([result.data.content], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${title}-${Date.now()}.md`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch (err) {
      console.error('Download report failed:', err);
    }
  };

  if (loading && !dashboard) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <Spin size="large" tip="加载仪表盘数据中..." />
      </div>
    );
  }

  if (error) {
    return (
      <Alert
        message="仪表盘加载失败"
        description={error}
        type="error"
        showIcon
        action={
          <Button size="small" onClick={fetchDashboard}>
            重试
          </Button>
        }
      />
    );
  }

  if (!dashboard) return null;

  const kpiCards = dashboard.kpi_cards || [];
  const radarData = dashboard.radar_chart;
  const trendData = dashboard.trend_chart;
  const distData = dashboard.distribution_chart;
  const boxData = dashboard.boxplot;

  // 适配 recharts 数据格式
  const radarChartData =
    radarData?.indicator?.map((ind, i) => {
      const point: Record<string, any> = { dimension: ind.name };
      radarData.series?.forEach((s) => {
        point[s.name] = s.value[i];
      });
      return point;
    }) || [];

  const trendChartData =
    trendData?.x_axis?.data?.map((ts: string) => {
      const point: Record<string, any> = { ts };
      trendData.series?.forEach((s) => {
        const found = s.data?.find((d: any) => (Array.isArray(d) ? d[0] === ts : d[0] === ts));
        point[s.name] = Array.isArray(found) ? found[1] : null;
      });
      return point;
    }) || [];

  const distChartData =
    distData?.bins?.map((bin: string, i: number) => ({
      bin,
      count: distData.counts?.[i] || 0,
    })) || [];

  const boxChartData =
    boxData?.categories?.map((cat: string, i: number) => ({
      name: cat,
      min: boxData.box_data?.[i]?.[0] ?? 0,
      q1: boxData.box_data?.[i]?.[1] ?? 0,
      median: boxData.box_data?.[i]?.[2] ?? 0,
      q3: boxData.box_data?.[i]?.[3] ?? 0,
      max: boxData.box_data?.[i]?.[4] ?? 0,
    })) || [];

  return (
    <div style={{ padding: 16 }}>
      {/* 标题栏 */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <h2 style={{ margin: 0 }}>{title}</h2>
        <Space>
          <Button icon={<RefreshCw size={14} />} onClick={fetchDashboard} loading={loading}>
            刷新
          </Button>
          <Button
            icon={<FileText size={14} />}
            onClick={() => handleDownloadReport('html')}
          >
            HTML 报告
          </Button>
          <Button
            icon={<Download size={14} />}
            onClick={() => handleDownloadReport('markdown')}
          >
            Markdown 报告
          </Button>
        </Space>
      </div>

      {/* KPI 卡片 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        {kpiCards.map((card, idx) => (
          <Col key={idx} xs={24} sm={12} md={6}>
            <Card>
              <Statistic
                title={card.label}
                value={card.value as any}
                precision={typeof card.value === 'number' ? 4 : 0}
                suffix={card.unit}
              />
            </Card>
          </Col>
        ))}
      </Row>

      {/* 图表区域 */}
      <Tabs activeKey={activeTab} onChange={setActiveTab}>
        <Tabs.TabPane tab="总览" key="overview">
          <Row gutter={16}>
            <Col xs={24} lg={12}>
              <Card title="多维度评估雷达图">
                <ResponsiveContainer width="100%" height={320}>
                  <RadarChart data={radarChartData}>
                    <PolarGrid />
                    <PolarAngleAxis dataKey="dimension" />
                    <PolarRadiusAxis domain={[0, 1]} />
                    {radarData?.series?.map((s) => (
                      <Radar
                        key={s.name}
                        name={s.name}
                        dataKey={s.name}
                        stroke="#8884d8"
                        fill="#8884d8"
                        fillOpacity={0.3}
                      />
                    ))}
                    <Legend />
                  </RadarChart>
                </ResponsiveContainer>
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card title="分数分布">
                <ResponsiveContainer width="100%" height={320}>
                  <BarChart data={distChartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="bin" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="count" fill="#4299e1" />
                  </BarChart>
                </ResponsiveContainer>
                {distData?.stats && (
                  <div style={{ marginTop: 8, fontSize: 12, color: '#666' }}>
                    均值: {distData.stats.mean?.toFixed(4)} | 标准差:{' '}
                    {distData.stats.stdev?.toFixed(4)} | 样本数: {distData.stats.count}
                  </div>
                )}
              </Card>
            </Col>
          </Row>
        </Tabs.TabPane>

        <Tabs.TabPane tab="趋势" key="trend">
          <Card title="历史趋势">
            <ResponsiveContainer width="100%" height={420}>
              <LineChart data={trendChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="ts" />
                <YAxis domain={[0, 1]} />
                <Tooltip />
                <Legend />
                {trendData?.series?.map((s, idx) => (
                  <Line
                    key={s.name}
                    type="monotone"
                    dataKey={s.name}
                    stroke={['#8884d8', '#82ca9d', '#ffc658', '#ff7300'][idx % 4]}
                    dot={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </Tabs.TabPane>

        <Tabs.TabPane tab="离散度" key="boxplot">
          <Card title="分数离散度（箱线图）">
            <ResponsiveContainer width="100%" height={420}>
              <BarChart data={boxChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="median" fill="#8884d8" name="中位数" />
                <Bar dataKey="q1" fill="#82ca9d" name="下四分位" />
                <Bar dataKey="q3" fill="#ffc658" name="上四分位" />
              </BarChart>
            </ResponsiveContainer>
            <div style={{ marginTop: 8, fontSize: 12, color: '#666' }}>
              数据说明: 显示各评估器分数的中位数、下四分位(q1)、上四分位(q3)
            </div>
          </Card>
        </Tabs.TabPane>

        <Tabs.TabPane tab="相关性" key="heatmap">
          <Card title="评估器相关性（热力图）">
            <Alert
              message="热力图建议使用 ECharts 渲染以获得更佳交互体验，本标签页可在 HTML 报告中查看完整效果"
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
            />
            {dashboard.heatmap?.data && (
              <div style={{ overflow: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      <th style={{ padding: 8, border: '1px solid #ddd' }}></th>
                      {dashboard.heatmap.x_labels?.map((x: string) => (
                        <th key={x} style={{ padding: 8, border: '1px solid #ddd' }}>
                          {x}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {dashboard.heatmap.y_labels?.map((y: string, i: number) => (
                      <tr key={y}>
                        <th style={{ padding: 8, border: '1px solid #ddd' }}>{y}</th>
                        {dashboard.heatmap.x_labels?.map((_x: string, j: number) => {
                          const cell = dashboard.heatmap.data?.find(
                            (d: any) => d[0] === j && d[1] === i,
                          );
                          const value = cell?.[2] ?? 0;
                          const bg = `rgba(66, 153, 225, ${Math.abs(value)})`;
                          return (
                            <td
                              key={j}
                              style={{
                                padding: 8,
                                border: '1px solid #ddd',
                                background: bg,
                                color: Math.abs(value) > 0.5 ? '#fff' : '#000',
                                textAlign: 'center',
                              }}
                            >
                              {value.toFixed(2)}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </Tabs.TabPane>
      </Tabs>
    </div>
  );
};

export default EvaluationDashboard;
