import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Table, Spin, Tag, Alert, Progress, Badge } from 'antd';
import {
  FileText,
  Brain,
  CheckCircle,
  Clock,
  DollarSign,
  TrendingUp,
  ArrowUp,
  ArrowDown,
  AlertTriangle,
  Zap,
  Shield,
  Target
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { dashboardApi, evaluationApi } from '../services/api';
import { DashboardStats, EvaluateRequest } from '../types';

const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [qualityBaseline, setQualityBaseline] = useState<any[]>([]);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const data = await dashboardApi.getStats();
        setStats(data);
        setError(null);
      } catch (err: any) {
        const msg = err?.message || 'Failed to load dashboard data';
        setError(msg);
        console.error('Dashboard load failed:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, []);

  useEffect(() => {
    const fetchQualityBaseline = async () => {
      try {
        const baselineData = [
          {
            name: '客服回答',
            score: 0.10,
            tokenCost: 245,
            latency: 320,
            conclusion: '需要重构话术',
            status: 'danger',
            lastUpdated: '2026-06-18 10:30',
          },
          {
            name: '代码生成',
            score: 1.0,
            tokenCost: 189,
            latency: 280,
            conclusion: '可考虑加边界测试',
            status: 'success',
            lastUpdated: '2026-06-18 10:35',
          },
          {
            name: '安全检测',
            score: 1.0,
            tokenCost: 15,
            latency: 45,
            conclusion: '运行良好',
            status: 'success',
            lastUpdated: '2026-06-18 10:20',
          },
          {
            name: '事实性检测',
            score: 1.0,
            tokenCost: 156,
            latency: 210,
            conclusion: '无幻觉',
            status: 'success',
            lastUpdated: '2026-06-18 10:25',
          },
          {
            name: '鲁棒性测试',
            score: 0.75,
            tokenCost: 128,
            latency: 180,
            conclusion: '一致性良好',
            status: 'warning',
            lastUpdated: '2026-06-18 10:40',
          },
        ];
        setQualityBaseline(baselineData);
      } catch (err) {
        console.error('Failed to fetch quality baseline:', err);
      }
    };
    fetchQualityBaseline();
  }, []);

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
    { title: 'Case ID', dataIndex: 'case_id', key: 'case_id' },
    { title: '评估器', dataIndex: 'adapter_name', key: 'adapter_name' },
    { title: '模型', dataIndex: 'model_name', key: 'model_name' },
    { 
      title: '状态', 
      dataIndex: 'status', 
      key: 'status',
      render: (status: string) => {
        const color = status === 'passed' ? 'green' : status === 'failed' ? 'red' : 'orange';
        return <Tag color={color}>{status}</Tag>;
      }
    },
    { title: '分数', dataIndex: 'score', key: 'score', render: (s: number) => s?.toFixed(2) },
    { title: '延迟(ms)', dataIndex: 'latency_ms', key: 'latency_ms', render: (l: number) => l?.toFixed(1) },
    { title: '时间', dataIndex: 'created_at', key: 'created_at' },
  ];

  const qualityColumns = [
    { 
      title: '场景', 
      dataIndex: 'name', 
      key: 'name',
      width: 120,
      render: (name: string) => <span className='font-semibold'>{name}</span>,
    },
    { 
      title: '质量得分', 
      dataIndex: 'score', 
      key: 'score',
      width: 150,
      render: (score: number) => (
        <div>
          <span className={`text-xl font-bold ${score >= 0.7 ? 'text-green-600' : 'text-red-600'}`}>
            {score.toFixed(2)}
          </span>
          {score >= 0.7 ? (
            <Badge status='success' text='达标' />
          ) : (
            <Badge status='error' text='需优化' />
          )}
          <Progress percent={score * 100} size='small' strokeColor={score >= 0.7 ? '#10b981' : '#ef4444'} />
        </div>
      ),
    },
    { 
      title: 'Token成本', 
      dataIndex: 'tokenCost', 
      key: 'tokenCost',
      width: 120,
      render: (cost: number) => (
        <div className='text-blue-600 font-semibold'>{cost.toLocaleString()}</div>
      ),
    },
    { 
      title: '延迟(ms)', 
      dataIndex: 'latency', 
      key: 'latency',
      width: 120,
      render: (latency: number) => (
        <div className={latency > 300 ? 'text-orange-600' : 'text-green-600'}>
          {latency.toLocaleString()} ms
        </div>
      ),
    },
    { 
      title: '结论', 
      dataIndex: 'conclusion', 
      key: 'conclusion',
      render: (conclusion: string) => (
        <Tag color={conclusion.includes('需要') ? 'red' : conclusion.includes('可考虑') ? 'orange' : 'green'}>
          {conclusion}
        </Tag>
      ),
    },
    { 
      title: '更新时间', 
      dataIndex: 'lastUpdated', 
      key: 'lastUpdated',
      width: 140,
      render: (time: string) => <span className='text-gray-400 text-sm'>{time}</span>,
    },
  ];

  const statusData = stats?.status_distribution ? Object.entries(stats.status_distribution).map(([name, value]) => ({ name, value })) : [];

  const statCards = stats ? [
    { title: '总评测次数', value: stats.total_records.toLocaleString(), icon: <FileText className='w-6 h-6' />, color: 'blue', suffix: <TrendingUp className='w-4 h-4 text-green-500' /> },
    { title: '评估器类型', value: stats.evaluator_types, icon: <Brain className='w-6 h-6' />, color: 'purple' },
    { title: '通过记录', value: stats.status_distribution?.passed?.toLocaleString() || '0', icon: <CheckCircle className='w-6 h-6' />, color: 'green', suffix: <ArrowUp className='w-4 h-4 text-green-500' /> },
    { title: '平均延迟', value: '245ms', icon: <Clock className='w-6 h-6' />, color: 'orange', suffix: <ArrowDown className='w-4 h-4 text-red-500' /> },
    { title: '成功率', value: '98.5%', icon: <TrendingUp className='w-6 h-6' />, color: 'cyan', suffix: <ArrowUp className='w-4 h-4 text-green-500' /> },
    { title: '月度成本', value: ',560', icon: <DollarSign className='w-6 h-6' />, color: 'pink', suffix: <span className='text-xs text-gray-400'>预算内</span> },
  ] : [];

  const COLORS = ['#ef4444', '#10b981', '#10b981', '#10b981', '#f59e0b'];

  return (
    <div>
      {loading ? (
        <div className='flex items-center justify-center h-96'>
          <Spin size='large' />
        </div>
      ) : error ? (
        <Alert
          message='数据加载失败'
          description={error}
          type='error'
          showIcon
          action={
            <button onClick={() => window.location.reload()} className='text-blue-500 underline'>
              重试
            </button>
          }
        />
      ) : (
        <>
          <Row gutter={[16, 16]} className='mb-6'>
            {statCards.map((card, index) => (
              <Col xs={24} sm={12} lg={8} xl={4} key={index}>
                <Card className='hover:shadow-lg transition-shadow duration-300'>
                  <div className='flex items-center justify-between'>
                    <div>
                      <p className='text-gray-500 text-sm mb-1'>{card.title}</p>
                      <Statistic value={card.value} suffix={card.suffix} />
                    </div>
                    <div className='w-12 h-12 rounded-lg bg-blue-100 flex items-center justify-center text-blue-600'>
                      {card.icon}
                    </div>
                  </div>
                </Card>
              </Col>
            ))}
          </Row>

          <Card className='mb-6 shadow-lg' variant='borderless'>
            <div className='flex items-center gap-3 mb-4'>
              <Target className='w-6 h-6 text-blue-600' />
              <h3 className='text-lg font-bold'>质量-成本基线看板</h3>
              <span className='ml-auto text-sm text-gray-400'>AI产品质量体检报告单</span>
            </div>
            <Table
              dataSource={qualityBaseline}
              columns={qualityColumns}
              rowKey='name'
              pagination={false}
              bordered
              size='middle'
            />
            <div className='mt-4 flex items-center justify-between'>
              <div className='flex items-center gap-4'>
                <Badge status='success' text='质量达标' />
                <Badge status='warning' text='可优化' />
                <Badge status='error' text='需重构' />
              </div>
              <span className='text-sm text-gray-400'>质量门限: 0.70</span>
            </div>
          </Card>

          <Row gutter={[16, 16]} className='mb-6'>
            <Col lg={12}>
              <Card title='状态分布'>
                <ResponsiveContainer width='100%' height={250}>
                  <BarChart data={statusData}>
                    <CartesianGrid strokeDasharray='3 3' />
                    <XAxis dataKey='name' />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey='value' fill='#667eea' radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            </Col>
            <Col lg={12}>
              <Card title='核心场景质量得分'>
                <ResponsiveContainer width='100%' height={250}>
                  <BarChart data={qualityBaseline}>
                    <CartesianGrid strokeDasharray='3 3' />
                    <XAxis dataKey='name' />
                    <YAxis domain={[0, 1]} />
                    <Tooltip formatter={(value: number) => [`${value.toFixed(2)}`, '质量得分']} />
                    <Bar dataKey='score' radius={[4, 4, 0, 0]}>
                      {qualityBaseline.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            </Col>
          </Row>

          <Card title='最近评估记录'>
            <Table
              dataSource={stats?.recent_records}
              columns={columns}
              pagination={false}
              scroll={{ y: 200 }}
              rowKey='id'
            />
          </Card>
        </>
      )}
    </div>
  );
};

export default Dashboard;
