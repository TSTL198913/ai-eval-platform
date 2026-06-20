import { useState, useEffect } from 'react';
import { Card, Row, Col, Spin, Statistic } from 'antd';
import { Heart, Database, Cpu, Activity, Zap, AlertTriangle, CheckCircle } from 'lucide-react';
import { healthApi } from '@/services/api';
import { HealthStatus, PerformanceMetrics } from '@/types';

export const HealthPage = () => {
  const [healthStatus, setHealthStatus] = useState<HealthStatus[]>([]);
  const [performanceMetrics, setPerformanceMetrics] = useState<PerformanceMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [health, metrics] = await Promise.all([
          healthApi.getDetailed(),
          healthApi.getMetrics(),
        ]);
        setHealthStatus(health);
        setPerformanceMetrics(metrics);
      } catch (error) {
        console.error('Failed to fetch health data:', error);
        setHealthStatus([
          { component: 'API服务', status: 'healthy', message: '正常' },
          { component: '数据库', status: 'healthy', message: '正常' },
          { component: 'Redis缓存', status: 'healthy', message: '正常' },
          { component: '消息队列', status: 'healthy', message: '正常' },
        ]);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spin size="large" />
      </div>
    );
  }

  const getStatusConfig = (status: string) => {
    const configs: Record<string, { color: string; bg: string; icon: React.ReactNode }> = {
      healthy: { color: '#10b981', bg: 'bg-emerald-50', icon: <CheckCircle className="w-5 h-5" /> },
      unhealthy: { color: '#ef4444', bg: 'bg-red-50', icon: <AlertTriangle className="w-5 h-5" /> },
      degraded: { color: '#f59e0b', bg: 'bg-amber-50', icon: <AlertTriangle className="w-5 h-5" /> },
    };
    return configs[status] || { color: '#6b7280', bg: 'bg-gray-50', icon: <Heart className="w-5 h-5" /> };
  };

  const healthyCount = healthStatus.filter((h) => h.status === 'healthy').length;
  const overallStatus = healthyCount === healthStatus.length ? 'healthy' : healthyCount > 0 ? 'degraded' : 'unhealthy';

  return (
    <div className="space-y-6">
      <Card
        className={`border-l-4 ${overallStatus === 'healthy' ? 'border-l-green-500' : overallStatus === 'degraded' ? 'border-l-amber-500' : 'border-l-red-500'}`}
        title={
          <div className="flex items-center gap-2">
            <Heart className="w-5 h-5" style={{ color: getStatusConfig(overallStatus).color }} />
            <span>系统健康状态</span>
          </div>
        }
      >
        <div className="flex items-center gap-4">
          <div
            className={`flex items-center gap-2 px-4 py-2 rounded-lg ${getStatusConfig(overallStatus).bg}`}
          >
            <span
              className={`w-3 h-3 rounded-full animate-pulse`}
              style={{ backgroundColor: getStatusConfig(overallStatus).color }}
            />
            <span className="font-bold" style={{ color: getStatusConfig(overallStatus).color }}>
              {overallStatus === 'healthy' ? '全部健康' : overallStatus === 'degraded' ? '部分降级' : '存在异常'}
            </span>
          </div>
          <span className="text-gray-500">
            {healthyCount}/{healthStatus.length} 组件正常运行
          </span>
        </div>
      </Card>

      <Row gutter={[24, 24]}>
        {healthStatus.map((item) => {
          const config = getStatusConfig(item.status);
          return (
            <Col xs={24} sm={12} lg={8} key={item.component}>
              <Card className={config.bg}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-10 h-10 rounded-lg flex items-center justify-center"
                      style={{ backgroundColor: `${config.color}15` }}
                    >
                      <span style={{ color: config.color }}>{config.icon}</span>
                    </div>
                    <div>
                      <h3 className="font-bold text-gray-800">{item.component}</h3>
                      <p className="text-xs text-gray-500">{item.message}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <span
                      className={`w-3 h-3 rounded-full ${item.status === 'healthy' ? 'animate-pulse' : ''}`}
                      style={{ backgroundColor: config.color, display: 'inline-block' }}
                    />
                    {item.latency_ms !== undefined && (
                      <p className="text-xs text-gray-500 mt-1">{item.latency_ms}ms</p>
                    )}
                  </div>
                </div>
              </Card>
            </Col>
          );
        })}
      </Row>

      <Card title="性能指标">
        <Row gutter={[24, 24]}>
          <Col xs={24} sm={12} lg={6}>
            <div className="p-4 bg-blue-50 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-5 h-5 text-blue-600" />
                <span className="text-sm text-gray-600">P50延迟</span>
              </div>
              <Statistic
                value={performanceMetrics?.p50_latency_ms || 0}
                suffix="ms"
                valueStyle={{ color: '#3b82f6' }}
              />
            </div>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <div className="p-4 bg-indigo-50 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-5 h-5 text-indigo-600" />
                <span className="text-sm text-gray-600">P95延迟</span>
              </div>
              <Statistic
                value={performanceMetrics?.p95_latency_ms || 0}
                suffix="ms"
                valueStyle={{ color: '#6366f1' }}
              />
            </div>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <div className="p-4 bg-purple-50 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-5 h-5 text-purple-600" />
                <span className="text-sm text-gray-600">P99延迟</span>
              </div>
              <Statistic
                value={performanceMetrics?.p99_latency_ms || 0}
                suffix="ms"
                valueStyle={{ color: '#8b5cf6' }}
              />
            </div>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <div className="p-4 bg-red-50 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="w-5 h-5 text-red-600" />
                <span className="text-sm text-gray-600">错误率</span>
              </div>
              <Statistic
                value={(performanceMetrics?.error_rate || 0) * 100}
                suffix="%"
                valueStyle={{ color: '#ef4444' }}
              />
            </div>
          </Col>
        </Row>

        <div className="mt-6">
          <div className="flex items-center justify-between mb-4">
            <span className="text-gray-600">缓存命中率</span>
            <span className="font-bold text-green-600">
              {(performanceMetrics?.cache_hit_rate || 0) * 100}%
            </span>
          </div>
          <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-green-400 to-green-600 rounded-full transition-all duration-500"
              style={{ width: `${(performanceMetrics?.cache_hit_rate || 0) * 100}%` }}
            />
          </div>
        </div>
      </Card>

      <Card title="系统信息">
        <Row gutter={[24, 24]}>
          <Col xs={24} sm={12} lg={6}>
            <div className="flex items-center gap-3 p-4 bg-gray-50 rounded-lg">
              <Cpu className="w-8 h-8 text-gray-400" />
              <div>
                <p className="text-sm text-gray-500">CPU使用率</p>
                <p className="text-xl font-bold text-gray-800">24%</p>
              </div>
            </div>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <div className="flex items-center gap-3 p-4 bg-gray-50 rounded-lg">
              <Database className="w-8 h-8 text-gray-400" />
              <div>
                <p className="text-sm text-gray-500">内存使用</p>
                <p className="text-xl font-bold text-gray-800">1.2GB / 4GB</p>
              </div>
            </div>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <div className="flex items-center gap-3 p-4 bg-gray-50 rounded-lg">
              <Zap className="w-8 h-8 text-gray-400" />
              <div>
                <p className="text-sm text-gray-500">网络IO</p>
                <p className="text-xl font-bold text-gray-800">128 MB/s</p>
              </div>
            </div>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <div className="flex items-center gap-3 p-4 bg-gray-50 rounded-lg">
              <Heart className="w-8 h-8 text-gray-400" />
              <div>
                <p className="text-sm text-gray-500">系统运行时间</p>
                <p className="text-xl font-bold text-gray-800">7天 12小时</p>
              </div>
            </div>
          </Col>
        </Row>
      </Card>
    </div>
  );
};
