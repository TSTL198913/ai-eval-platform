
import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Spin, Progress, Tag } from 'antd';
import { DollarSign, TrendingUp, TrendingDown, AlertTriangle } from 'lucide-react';
import { costApi } from '../services/api';
import { CostMetrics } from '../types';

const Cost: React.FC = () => {
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

  if (loading) {
    return (
      <div className='flex items-center justify-center h-96'>
        <Spin size='large' />
      </div>
    );
  }

  const budgetUsage = metrics?.budget_status?.daily_usage_percent || 0;
  const budgetColor = budgetUsage > 90 ? 'red' : budgetUsage > 70 ? 'orange' : 'green';

  return (
    <div>
      <Row gutter={[16, 16]} className='mb-6'>
        <Col xs={24} sm={12} lg={8}>
          <Card>
            <div className='flex items-center gap-4'>
              <div className='w-12 h-12 rounded-lg bg-green-100 flex items-center justify-center'>
                <DollarSign className='w-6 h-6 text-green-600' />
              </div>
              <div>
                <p className='text-gray-500 text-sm mb-1'>日成本</p>
                <Statistic value={metrics?.daily_cost_usd || 0} prefix='$' precision={2} />
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card>
            <div className='flex items-center gap-4'>
              <div className='w-12 h-12 rounded-lg bg-blue-100 flex items-center justify-center'>
                <TrendingUp className='w-6 h-6 text-blue-600' />
              </div>
              <div>
                <p className='text-gray-500 text-sm mb-1'>周成本</p>
                <Statistic value={metrics?.weekly_cost_usd || 0} prefix='$' precision={2} />
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card>
            <div className='flex items-center gap-4'>
              <div className='w-12 h-12 rounded-lg bg-purple-100 flex items-center justify-center'>
                <TrendingDown className='w-6 h-6 text-purple-600' />
              </div>
              <div>
                <p className='text-gray-500 text-sm mb-1'>月成本</p>
                <Statistic value={metrics?.monthly_cost_usd || 0} prefix='$' precision={2} />
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      <Card title='预算使用情况' className='mb-6'>
        <div className='mb-4'>
          <div className='flex justify-between mb-2'>
            <span className='text-gray-500'>日预算使用</span>
            <span className='font-semibold'>
              {budgetUsage.toFixed(1)}%
            </span>
          </div>
          <Progress percent={budgetUsage} status={budgetUsage > 90 ? 'exception' : budgetUsage > 70 ? 'active' : 'success'} />
        </div>
        {
          <div className='flex items-center gap-2 text-red-500'>
            <AlertTriangle className='w-5 h-5' />
            <span className='text-sm'>预算即将耗尽，请关注成本控制</span>
          </div>
        )}
      </Card>

      <Card title='成本趋势'>
        <div className='text-center py-12'>
          <p className='text-gray-400'>图表功能开发中...</p>
          <p className='text-gray-300 text-sm mt-2'>将显示每日成本趋势和预算对比</p>
        </div>
      </Card>
    </div>
  );
};

export default Cost;
