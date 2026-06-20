import { useEffect, useState } from 'react';
import { Card, Row, Col, Button, Spin, Empty, Tag } from 'antd';
import {
  Activity,
  Cpu,
  Database,
  CheckCircle,
  Clock,
  DollarSign,
  BarChart3,
  Zap,
} from 'lucide-react';
import { StatCard } from '@/components/StatCard';
import { dashboardApi, evaluatorApi } from '@/services/api';
import { DashboardStats, Evaluator } from '@/types';
import { useNavigate } from 'react-router-dom';

export const DashboardPage = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [evaluators, setEvaluators] = useState<Evaluator[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsData, evaluatorsData] = await Promise.all([
          dashboardApi.getStats(),
          evaluatorApi.list(),
        ]);
        setStats(statsData);
        setEvaluators(evaluatorsData.slice(0, 6));
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error);
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

  return (
    <div className="space-y-6">
      <Row gutter={[24, 24]}>
        <Col xs={24} sm={12} lg={8}>
          <StatCard
            title="总评测次数"
            value={stats?.total_evaluations || 0}
            icon={<Activity className="w-6 h-6" />}
            color="#667eea"
            trend={{ value: 12.5, isUp: true }}
          />
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <StatCard
            title="活跃模型数"
            value={stats?.active_models || 0}
            icon={<Database className="w-6 h-6" />}
            color="#10b981"
            trend={{ value: 5.2, isUp: true }}
          />
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <StatCard
            title="评估器数量"
            value={stats?.evaluator_count || 0}
            icon={<Cpu className="w-6 h-6" />}
            color="#f59e0b"
          />
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <StatCard
            title="成功率"
            value={`${(stats?.success_rate || 0) * 100}`}
            icon={<CheckCircle className="w-6 h-6" />}
            color="#3b82f6"
            suffix="%"
            trend={{ value: 2.1, isUp: true }}
          />
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <StatCard
            title="平均延迟"
            value={stats?.avg_latency_ms || 0}
            icon={<Clock className="w-6 h-6" />}
            color="#8b5cf6"
            suffix="ms"
            trend={{ value: 8.3, isUp: false }}
          />
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <StatCard
            title="月度成本"
            value={(stats?.monthly_cost || 0).toFixed(2)}
            icon={<DollarSign className="w-6 h-6" />}
            color="#ef4444"
            suffix="元"
            trend={{ value: 3.2, isUp: true }}
          />
        </Col>
      </Row>

      <Row gutter={[24, 24]}>
        <Col xs={24} lg={16}>
          <Card
            title="快速评估"
            extra={
              <Button type="primary" onClick={() => navigate('/evaluators')}>
                查看全部评估器
              </Button>
            }
          >
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {evaluators.length > 0 ? (
                evaluators.map((evaluator) => (
                  <button
                    key={evaluator.name}
                    className="p-4 bg-gray-50 rounded-lg border border-gray-100 hover:border-[#667eea] hover:bg-[#667eea]/5 transition-all text-left"
                    onClick={() => navigate('/evaluators')}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <Zap className="w-4 h-4 text-[#667eea]" />
                      <span className="font-medium text-gray-800">
                        {evaluator.display_name || evaluator.name}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 line-clamp-2">
                      {evaluator.description || '暂无描述'}
                    </p>
                    <div className="flex flex-wrap gap-1 mt-2">
                      {evaluator.supported_types?.slice(0, 2).map((type) => (
                        <Tag key={type} color="blue">
                          {type}
                        </Tag>
                      ))}
                    </div>
                  </button>
                ))
              ) : (
                <Empty description="暂无评估器" />
              )}
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card title="系统状态">
            <div className="space-y-4">
              {[
                { name: 'API服务', status: 'healthy', latency: 23 },
                { name: '数据库', status: 'healthy', latency: 5 },
                { name: 'Redis缓存', status: 'healthy', latency: 1 },
                { name: '消息队列', status: 'healthy', latency: 2 },
                { name: '评估引擎', status: 'degraded', latency: 156 },
              ].map((item) => (
                <div
                  key={item.name}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`w-3 h-3 rounded-full ${
                        item.status === 'healthy'
                          ? 'bg-green-500 animate-pulse'
                          : item.status === 'degraded'
                          ? 'bg-amber-500'
                          : 'bg-red-500'
                      }`}
                    />
                    <span className="font-medium text-gray-700">{item.name}</span>
                  </div>
                  <span className="text-sm text-gray-500">{item.latency}ms</span>
                </div>
              ))}
            </div>
          </Card>

          <Card title="最新动态" className="mt-6">
            <div className="space-y-3">
              {[
                { action: '评估任务完成', time: '2分钟前', status: 'success' },
                { action: '新模型注册成功', time: '15分钟前', status: 'success' },
                { action: '评估器配置更新', time: '1小时前', status: 'info' },
                { action: '系统健康检查通过', time: '2小时前', status: 'success' },
              ].map((item, index) => (
                <div
                  key={index}
                  className="flex items-start gap-3 p-2 hover:bg-gray-50 rounded-lg transition-colors"
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full mt-1.5 ${
                      item.status === 'success' ? 'bg-green-500' : 'bg-blue-500'
                    }`}
                  />
                  <div className="flex-1">
                    <p className="text-sm text-gray-700">{item.action}</p>
                    <p className="text-xs text-gray-400">{item.time}</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </Col>
      </Row>

      <Card title="评估趋势">
        <div className="h-64 flex items-center justify-center">
          <BarChart3 className="w-16 h-16 text-gray-300" />
        </div>
      </Card>
    </div>
  );
};
