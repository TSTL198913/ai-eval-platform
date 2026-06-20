import { useState, useEffect } from 'react';
import { Card, Row, Col, Spin, Statistic, Progress, Button } from 'antd';
import { DollarSign, TrendingUp, TrendingDown, Clock, AlertTriangle } from 'lucide-react';
import { costApi } from '@/services/api';
import { CostMetrics } from '@/types';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

export const CostPage = () => {
  const [metrics, setMetrics] = useState<CostMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const data = await costApi.getMetrics();
        setMetrics(data);
      } catch (error) {
        console.error('Failed to fetch cost metrics:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchMetrics();
  }, []);

  const mockTrendData = [
    { day: '周一', cost: 120, tokens: 50000 },
    { day: '周二', cost: 150, tokens: 65000 },
    { day: '周三', cost: 90, tokens: 40000 },
    { day: '周四', cost: 180, tokens: 75000 },
    { day: '周五', cost: 200, tokens: 85000 },
    { day: '周六', cost: 80, tokens: 35000 },
    { day: '周日', cost: 100, tokens: 45000 },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spin size="large" />
      </div>
    );
  }

  const budgetUsedPercent = metrics?.budget_used_percent || 0;
  const isOverBudget = budgetUsedPercent >= 90;

  return (
    <div className="space-y-6">
      <Row gutter={[24, 24]}>
        <Col xs={24} lg={8}>
          <Card className="bg-gradient-to-br from-blue-50 to-indigo-50">
            <div className="flex items-center gap-3 mb-4">
              <DollarSign className="w-8 h-8 text-blue-600" />
              <span className="text-gray-600">今日成本</span>
            </div>
            <Statistic
              value={(metrics?.daily_cost || 0).toFixed(2)}
              prefix="¥"
              valueStyle={{ fontSize: '32px', fontWeight: 'bold', color: '#1e3a5f' }}
            />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card className="bg-gradient-to-br from-purple-50 to-pink-50">
            <div className="flex items-center gap-3 mb-4">
              <TrendingUp className="w-8 h-8 text-purple-600" />
              <span className="text-gray-600">本周成本</span>
            </div>
            <Statistic
              value={(metrics?.weekly_cost || 0).toFixed(2)}
              prefix="¥"
              valueStyle={{ fontSize: '32px', fontWeight: 'bold', color: '#1e3a5f' }}
            />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card className="bg-gradient-to-br from-amber-50 to-orange-50">
            <div className="flex items-center gap-3 mb-4">
              <TrendingDown className="w-8 h-8 text-amber-600" />
              <span className="text-gray-600">本月成本</span>
            </div>
            <Statistic
              value={(metrics?.monthly_cost || 0).toFixed(2)}
              prefix="¥"
              valueStyle={{ fontSize: '32px', fontWeight: 'bold', color: '#1e3a5f' }}
            />
          </Card>
        </Col>
      </Row>

      <Card
        title="预算使用"
        extra={
          isOverBudget && (
            <AlertTriangle className="w-5 h-5 text-red-500" />
          )
        }
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-gray-600">本月预算</span>
            <span className="font-medium">
              ¥{(metrics?.budget_limit || 0).toLocaleString()}
            </span>
          </div>
          <Progress
            percent={budgetUsedPercent}
            strokeColor={{
              '0%': '#10b981',
              '70%': '#f59e0b',
              '90%': '#ef4444',
            }}
            strokeWidth={3}
            format={(percent) => `${percent}%`}
          />
          <div className="flex items-center justify-between">
            <span className="text-gray-600">已使用</span>
            <span className={`font-medium ${isOverBudget ? 'text-red-500' : 'text-gray-800'}`}>
              ¥{(metrics?.monthly_cost || 0).toLocaleString()}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-600">剩余</span>
            <span className="font-medium text-green-600">
              ¥{((metrics?.budget_limit || 0) - (metrics?.monthly_cost || 0)).toLocaleString()}
            </span>
          </div>
          {isOverBudget && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-red-600 font-medium">预算即将耗尽，请及时调整！</p>
              <Button type="primary" className="mt-2">
                调整预算
              </Button>
            </div>
          )}
        </div>
      </Card>

      <Row gutter={[24, 24]}>
        <Col xs={24} lg={12}>
          <Card title="成本趋势">
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={mockTrendData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="day" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="cost" name="成本(¥)" stroke="#667eea" />
                  <Line type="monotone" dataKey="tokens" name="Token数" stroke="#10b981" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="Token使用">
            <div className="space-y-6">
              <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-3">
                  <Clock className="w-6 h-6 text-gray-400" />
                  <span className="text-gray-600">本月Token消耗</span>
                </div>
                <span className="text-xl font-bold text-gray-800">
                  {(metrics?.token_usage || 0).toLocaleString()}
                </span>
              </div>
              <div className="flex flex-wrap gap-4">
                {[
                  { label: '平均每日', value: '12,500' },
                  { label: '峰值日', value: '25,800' },
                  { label: '最低日', value: '3,200' },
                  { label: '平均单次', value: '1,500' },
                ].map((item, index) => (
                  <div key={index} className="flex-1 text-center p-3 bg-gray-50 rounded-lg">
                    <p className="text-sm text-gray-500">{item.label}</p>
                    <p className="text-lg font-bold text-gray-800">{item.value}</p>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
};
