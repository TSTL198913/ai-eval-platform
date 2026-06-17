
import React, { useState, useEffect } from 'react';
import { Card, Select, Button, Spin, Table } from 'antd';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { modelApi } from '../services/api';
import { Model, ModelCompareResult } from '../types';

const { Option } = Select;

const Models: React.FC = () => {
  const [models, setModels] = useState<Model[]>([]);
  const [selectedModels, setSelectedModels] = useState<string[]>(['gpt-4', 'claude-3']);
  const [dataset, setDataset] = useState('mmlu');
  const [comparisonResults, setComparisonResults] = useState<ModelCompareResult[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchModels = async () => {
      try {
        const data = await modelApi.getAll();
        setModels(data);
      } catch (error) {
        console.error('Failed to fetch models:', error);
      }
    };
    fetchModels();
  }, []);

  const handleCompare = async () => {
    if (selectedModels.length < 2) {
      return;
    }
    setLoading(true);
    try {
      const response = await modelApi.compare({
        models: selectedModels,
        dataset,
      });
      setComparisonResults(response.results);
    } catch (error) {
      console.error('Failed to compare models:', error);
    } finally {
      setLoading(false);
    }
  };

  const colors = ['#667eea', '#764ba2', '#f59e0b', '#10b981', '#ef4444'];

  const columns = [
    { title: '模型', dataIndex: 'model', key: 'model' },
    { title: '准确率', dataIndex: 'accuracy', key: 'accuracy', render: (a: number) => (a * 100).toFixed(1) + '%' },
    { title: '延迟(ms)', dataIndex: 'latency_ms', key: 'latency_ms', render: (l: number) => l.toFixed(0) },
    { title: '成本($)', dataIndex: 'cost', key: 'cost', render: (c: number) => c.toFixed(4) },
  ];

  return (
    <div>
      <Card className='mb-6'>
        <div className='flex items-center gap-4 flex-wrap'>
          <div>
            <label className='text-gray-500 text-sm mr-2'>选择模型（至少2个）</label>
            <Select
              mode='multiple'
              value={selectedModels}
              onChange={setSelectedModels}
              style={{ width: 400 }}
              placeholder='选择要对比的模型'
            >
              {models.map((model) => (
                <Option key={model.id} value={model.id}>{model.name}</Option>
              ))}
            </Select>
          </div>
          <div>
            <label className='text-gray-500 text-sm mr-2'>选择数据集</label>
            <Select value={dataset} onChange={setDataset} style={{ width: 150 }}>
              <Option value='mmlu'>MMLU</Option>
              <Option value='gsm8k'>GSM8K</Option>
              <Option value='humaneval'>HumanEval</Option>
            </Select>
          </div>
          <Button type='primary' onClick={handleCompare} loading={loading}>
            开始对比
          </Button>
        </div>
      </Card>

      {comparisonResults.length > 0 ? (
        <>
          <Card title='对比图表' className='mb-6'>
            <ResponsiveContainer width='100%' height={350}>
              <BarChart data={comparisonResults}>
                <CartesianGrid strokeDasharray='3 3' />
                <XAxis dataKey='model' />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey='accuracy' name='准确率' fill={colors[0]} />
                <Bar dataKey='latency_ms' name='延迟(ms)' fill={colors[1]} />
                <Bar dataKey='cost' name='成本' fill={colors[2]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <Card title='详细数据'>
            <Table
              dataSource={comparisonResults}
              columns={columns}
              rowKey='model'
            />
          </Card>
        </>
      ) : (
        <div className='flex items-center justify-center h-96'>
          <Spin size='large' spinning={loading} />
          {!loading && <p className='text-gray-400'>选择模型并点击开始对比</p>}
        </div>
      )}
    </div>
  );
};

export default Models;
