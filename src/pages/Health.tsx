
import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Spin, Tag, Statistic } from 'antd';
import { Server, Database, Rabbit, Activity, AlertCircle, CheckCircle } from 'lucide-react';
import { healthApi } from '../services/api';
import { HealthInfo, PerformanceMetrics } from '../types';

const Health: React.FC = () => {
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [metrics, setMetrics] = useState<PerformanceMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [healthData, metricsData] = await Promise.all([
          healthApi.getDetailed(),
          healthApi.getMetrics(),
        ]);
        setHealth(healthData);
        setMetrics(metricsData);
      } catch (error) {
        console.error('Failed to fetch health data:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className='flex items-center justify-center h-96'>
        <Spin size='large' />
      </div>
    );
  }

  const getStatusIcon = (status: string) => {
    const isHealthy = status === 'healthy';
    return isHealthy ? (
      <CheckCircle className='w-8 h-8 text-green-500' />
    ) : (
      <AlertCircle className='w-8 h-8 text-red-500' />
    );
  };

  const getStatusColor = (status: string) => {
    return status === 'healthy' ? 'green' : status === 'unhealthy' ? 'red' : 'orange';
  };

  const components = health?.components || {};

  return (
    <div>
      <Card title='服务信息' className='mb-6'>
        <div className='flex items-center gap-4'>
          <Server className='w-10 h-10 text-blue-500' />
          <div>
            <h3 className='font-semibold text-gray-800'>{health?.service.name || 'AI Eval Platform'}</h3>
            <p className='text-gray-500'>版本: {health?.service.version || '2.0.0'}</p>
          </div>
        </div>
      </Card>

      <Row gutter={[16, 16]} className='mb-6'>
        <Col xs={24} sm={8}>
          <Card title='Redis'>
            <div className='flex items-center justify-between'>
              {getStatusIcon(components.redis?.status || 'unknown')}
              <Tag color={getStatusColor(components.redis?.status || 'unknown')}>
                {components.redis?.status}
              </Tag>
            </div>
            {components.redis?.version && (
              <p className='text-gray-500 text-sm mt-2'>版本: {components.redis.version}</p>
            )}
            {components.redis?.error && (
              <p className='text-red-500 text-sm mt-2'>错误: {components.redis.error}</p>
            )}
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card title='数据库'>
            <div className='flex items-center justify-between'>
              {getStatusIcon(components.database?.status || 'unknown')}
              <Tag color={getStatusColor(components.database?.status || 'unknown')}>
                {components.database?.status}
              </Tag>
            </div>
            {components.database?.error && (
              <p className='text-red-500 text-sm mt-2'>错误: {components.database.error}</p>
            )}
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card title='RabbitMQ'>
            <div className='flex items-center justify-between'>
              {getStatusIcon(components.rabbitmq?.status || 'unknown')}
              <Tag color={getStatusColor(components.rabbitmq?.status || 'unknown')}>
                {components.rabbitmq?.status}
              </Tag>
            </div>
            {components.rabbitmq?.error && (
              <p className='text-red-500 text-sm mt-2'>错误: {components.rabbitmq.error}</p>
            )}
          </Card>
        </Col>
      </Row>

      <Card title='性能指标'>
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={6}>
            <div className='text-center'>
              <p className='text-gray-500 text-sm mb-1'>请求/分钟</p>
              <Statistic value={metrics?.requests_per_minute || 0} />
            </div>
          </Col>
          <Col xs={24} sm={6}>
            <div className='text-center'>
              <p className='text-gray-500 text-sm mb-1'>P50延迟(ms)</p>
              <Statistic value={metrics?.p50_latency_ms || 0} />
            </div>
          </Col>
          <Col xs={24} sm={6}>
            <div className='text-center'>
              <p className='text-gray-500 text-sm mb-1'>P95延迟(ms)</p>
              <Statistic value={metrics?.p95_latency_ms || 0} />
            </div>
          </Col>
          <Col xs={24} sm={6}>
            <div className='text-center'>
              <p className='text-gray-500 text-sm mb-1'>P99延迟(ms)</p>
              <Statistic value={metrics?.p99_latency_ms || 0} />
            </div>
          </Col>
          <Col xs={24} sm={6}>
            <div className='text-center'>
              <p className='text-gray-500 text-sm mb-1'>错误率</p>
              <Statistic value={(metrics?.error_rate || 0) * 100} suffix='%' precision={2} />
            </div>
          </Col>
          <Col xs={24} sm={6}>
            <div className='text-center'>
              <p className='text-gray-500 text-sm mb-1'>缓存命中率</p>
              <Statistic value={(metrics?.cache_hit_rate || 0) * 100} suffix='%' precision={1} />
            </div>
          </Col>
          <Col xs={24} sm={6}>
            <div className='text-center'>
              <p className='text-gray-500 text-sm mb-1'>平均Token数</p>
              <Statistic value={metrics?.avg_tokens_per_request || 0} />
            </div>
          </Col>
          <Col xs={24} sm={6}>
            <div className='text-center'>
              <p className='text-gray-500 text-sm mb-1'>日成本($)</p>
              <Statistic value={metrics?.daily_cost_usd || 0} prefix='$' precision={2} />
            </div>
          </Col>
        </Row>
      </Card>
    </div>
  );
};

export default Health;
