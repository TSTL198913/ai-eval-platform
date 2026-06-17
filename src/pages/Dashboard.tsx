
import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Table, Spin, Tag } from 'antd';
import { 
  FileText, 
  Brain, 
  CheckCircle, 
  Clock, 
  DollarSign,
  TrendingUp,
  ArrowUp,
  ArrowDown
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { dashboardApi } from '../services/api';
import { DashboardStats } from '../types';

const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const data = await dashboardApi.getStats();
        setStats(data);
      } catch (error) {
        console.error('Failed to fetch stats:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
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

  const statusData = stats?.status_distribution ? Object.entries(stats.status_distribution).map(([name, value]) => ({ name, value })) : [];

  const statCards = stats ? [
    { title: '总评测次数', value: stats.total_records.toLocaleString(), icon: <FileText className='w-6 h-6' />, color: 'blue', suffix: <TrendingUp className='w-4 h-4 text-green-500' /> },
    { title: '评估器类型', value: stats.evaluator_types, icon: <Brain className='w-6 h-6' />, color: 'purple' },
    { title: '通过记录', value: stats.status_distribution?.passed?.toLocaleString() || '0', icon: <CheckCircle className='w-6 h-6' />, color: 'green', suffix: <ArrowUp className='w-4 h-4 text-green-500' /> },
    { title: '平均延迟', value: '245ms', icon: <Clock className='w-6 h-6' />, color: 'orange', suffix: <ArrowDown className='w-4 h-4 text-red-500' /> },
    { title: '成功率', value: '98.5%', icon: <TrendingUp className='w-6 h-6' />, color: 'cyan', suffix: <ArrowUp className='w-4 h-4 text-green-500' /> },
    { title: '月度成本', value: ',560', icon: <DollarSign className='w-6 h-6' />, color: 'pink', suffix: <span className='text-xs text-gray-400'>预算内</span> },
  ] : [];

  return (
    <div>
      {loading ? (
        <div className='flex items-center justify-center h-96'>
          <Spin size='large' />
        </div>
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
                    <div className={w-12 h-12 rounded-lg bg--100 flex items-center justify-center text--600}>
                      {card.icon}
                    </div>
                  </div>
                </Card>
              </Col>
            ))}
          </Row>

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
              <Card title='最近评估记录'>
                <Table
                  dataSource={stats?.recent_records}
                  columns={columns}
                  pagination={false}
                  scroll={{ y: 200 }}
                  rowKey='id'
                />
              </Card>
            </Col>
          </Row>
        </>
      )}
    </div>
  );
};

export default Dashboard;
