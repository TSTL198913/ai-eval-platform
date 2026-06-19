import React, { useState, useEffect } from 'react';
import { Card, Select, Button, Spin, Table, Tag, message, Progress, Descriptions } from 'antd';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line } from 'recharts';
import { modelApi, evaluationApi } from '../services/api';
import { Model, ModelCompareRequest, ModelCompareResult, EvaluateRequest } from '../types';
import { TrendingUp, Clock, DollarSign, Award, Play, RefreshCw } from 'lucide-react';

const { Option } = Select;

const Models: React.FC = () => {
  const [models, setModels] = useState<Model[]>([]);
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [dataset, setDataset] = useState('mmlu');
  const [comparisonResults, setComparisonResults] = useState<ModelCompareResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<{ timestamp: number; results: ModelCompareResult[] }[]>([]);

  useEffect(() => {
    const fetchModels = async () => {
      try {
        const data = await modelApi.getAll();
        setModels(data);
      } catch (err: any) {
        // 架构规范：模型列表加载失败必须抛出，不允许静默
        console.error('Failed to fetch models:', err);
        message.error('模型列表加载失败，请检查后端服务');
        throw err;
      }
    };
    fetchModels();
  }, []);

  const handleCompare = async () => {
    if (selectedModels.length < 2) {
      message.warning('请至少选择2个模型进行对比');
      return;
    }
    setLoading(true);
    try {
      const modelObjects = selectedModels.map(modelId => {
        const model = models.find(m => m.id === modelId);
        return model ? { provider: model.provider, name: model.name } : { provider: 'unknown', name: modelId };
      });
      const response = await modelApi.compare({
        models: modelObjects,
        datasets: [dataset],
        sample_count: 10,
      });
      setComparisonResults(response.models);
      setHistory(prev => [...prev.slice(-4), { timestamp: Date.now(), results: response.models }]);
      message.success('模型对比完成');
    } catch (err: any) {
      // 架构规范：业务操作失败必须抛出让用户感知
      console.error('Failed to compare models:', err);
      message.error(`模型对比失败: ${err?.message || '未知错误'}`);
      throw err; // 抛出给ErrorBoundary
    } finally {
      setLoading(false);
    }
  };

  const handleEvaluate = async () => {
    if (selectedModels.length === 0) {
      message.warning('请先选择模型');
      return;
    }
    setLoading(true);
    try {
      const modelObjects = selectedModels.map(modelId => {
        const model = models.find(m => m.id === modelId);
        return model ? model : null;
      }).filter(Boolean);

      for (const model of modelObjects) {
        const testPayload: EvaluateRequest = {
          id: `model_test_${model.name}_${Date.now()}`,
          type: 'general',
          payload: {
            user_input: "What is the capital of France?",
            expected_output: "Paris",
            model_name: model.name,
            provider: model.provider,
          },
        };
        await evaluationApi.evaluate(testPayload);
      }
      message.success(`已完成 ${modelObjects.length} 个模型的评测`);
    } catch (error) {
      console.error('Evaluation failed:', error);
      message.error('评测失败');
    } finally {
      setLoading(false);
    }
  };

  const colors = ['#667eea', '#764ba2', '#f59e0b', '#10b981', '#ef4444'];

  const columns = [
    { 
      title: '模型', 
      dataIndex: 'model', 
      key: 'model',
      render: (text: string) => <span className='font-semibold'>{text}</span>
    },
    { 
      title: '提供商', 
      dataIndex: 'provider', 
      key: 'provider',
      render: (text: string) => <Tag color='blue'>{text}</Tag>
    },
    { 
      title: '准确率', 
      dataIndex: 'avg_accuracy', 
      key: 'avg_accuracy', 
      render: (a: number) => (
        <div>
          <span className='font-semibold'>{(a * 100).toFixed(1)}%</span>
          <Progress percent={a * 100} size='small' strokeColor='#10b981' />
        </div>
      )
    },
    { 
      title: '延迟(ms)', 
      dataIndex: 'avg_latency_ms', 
      key: 'avg_latency_ms', 
      render: (l: number) => <span>{l.toFixed(0)} ms</span>
    },
    { 
      title: '成本($)', 
      dataIndex: 'total_cost_usd', 
      key: 'total_cost_usd', 
      render: (c: number) => <span>${c.toFixed(4)}</span>
    },
    {
      title: '排名',
      key: 'rank',
      render: (_, record, index) => (
        <Tag color={index === 0 ? 'gold' : 'default'}>
          {index + 1}
        </Tag>
      )
    },
  ];

  const sortedResults = [...comparisonResults].sort((a, b) => b.avg_accuracy - a.avg_accuracy);

  const getBestModel = () => {
    if (sortedResults.length === 0) return null;
    return sortedResults[0];
  };

  const bestModel = getBestModel();

  const avgData = history.map(h => ({
    time: new Date(h.timestamp).toLocaleTimeString(),
    avg_accuracy: h.results.reduce((sum, r) => sum + r.avg_accuracy, 0) / h.results.length,
  }));

  return (
    <div>
      <Card className='mb-6'>
        <div className='flex items-center gap-4 flex-wrap'>
          <div>
            <label className='text-gray-500 text-sm mr-2'>选择模型（至少2个进行对比）</label>
            <Select
              mode='multiple'
              value={selectedModels}
              onChange={setSelectedModels}
              style={{ width: 400 }}
              placeholder='选择要对比的模型'
            >
              {models.map((model) => (
                <Option key={model.id} value={model.id}>
                  {model.name} ({model.provider})
                </Option>
              ))}
            </Select>
          </div>
          <div>
            <label className='text-gray-500 text-sm mr-2'>选择数据集</label>
            <Select value={dataset} onChange={setDataset} style={{ width: 150 }}>
              <Option value='mmlu'>MMLU（知识理解）</Option>
              <Option value='gsm8k'>GSM8K（数学推理）</Option>
              <Option value='humaneval'>HumanEval（代码生成）</Option>
            </Select>
          </div>
          <Button 
            type='primary' 
            onClick={handleCompare} 
            loading={loading}
            icon={<Play />}
            disabled={selectedModels.length < 2}
          >
            开始对比
          </Button>
          <Button 
            type='default' 
            onClick={handleEvaluate} 
            loading={loading}
            icon={<RefreshCw />}
            disabled={selectedModels.length === 0}
          >
            执行评测
          </Button>
        </div>
      </Card>

      {bestModel && (
        <Card className='mb-6 shadow-lg' bordered={false}>
          <div className='flex items-center gap-6'>
            <div className='w-16 h-16 bg-gradient-to-br from-yellow-400 to-orange-500 rounded-full flex items-center justify-center'>
              <Award className='w-8 h-8 text-white' />
            </div>
            <div>
              <h3 className='text-xl font-bold'>最佳推荐模型: {bestModel.model}</h3>
              <p className='text-gray-500'>提供商: {bestModel.provider}</p>
            </div>
            <div className='ml-auto flex gap-8'>
              <div className='text-center'>
                <p className='text-2xl font-bold text-green-600'>{(bestModel.avg_accuracy * 100).toFixed(1)}%</p>
                <p className='text-sm text-gray-500'>准确率</p>
              </div>
              <div className='text-center'>
                <p className='text-2xl font-bold text-blue-600'>{bestModel.avg_latency_ms.toFixed(0)}ms</p>
                <p className='text-sm text-gray-500'>延迟</p>
              </div>
              <div className='text-center'>
                <p className='text-2xl font-bold text-orange-600'>${bestModel.total_cost_usd.toFixed(4)}</p>
                <p className='text-sm text-gray-500'>成本</p>
              </div>
            </div>
          </div>
        </Card>
      )}

      {comparisonResults.length > 0 ? (
        <>
          <Card title='对比图表' className='mb-6'>
            <ResponsiveContainer width='100%' height={350}>
              <BarChart data={sortedResults}>
                <CartesianGrid strokeDasharray='3 3' />
                <XAxis dataKey='model' />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey='avg_accuracy' name='准确率' fill={colors[0]} />
                <Bar dataKey='avg_latency_ms' name='延迟(ms)' fill={colors[1]} />
                <Bar dataKey='total_cost_usd' name='成本' fill={colors[2]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <Card title='详细数据'>
            <Table
              dataSource={sortedResults}
              columns={columns}
              rowKey='model'
            />
          </Card>

          {history.length > 1 && (
            <Card title='历史趋势' className='mt-6'>
              <ResponsiveContainer width='100%' height={250}>
                <LineChart data={avgData}>
                  <CartesianGrid strokeDasharray='3 3' />
                  <XAxis dataKey='time' />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line type='monotone' dataKey='avg_accuracy' name='平均准确率' stroke='#667eea' />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          )}

          <Card title='数据集详情' className='mt-6'>
            <Descriptions bordered column={3}>
              <Descriptions.Item label='数据集'>{dataset.toUpperCase()}</Descriptions.Item>
              <Descriptions.Item label='样本数量'>10</Descriptions.Item>
              <Descriptions.Item label='评测类型'>{
                dataset === 'mmlu' ? '多学科知识理解' : 
                dataset === 'gsm8k' ? '小学数学推理' : '代码生成能力'
              }</Descriptions.Item>
            </Descriptions>
          </Card>
        </>
      ) : (
        <div className='flex items-center justify-center h-96'>
          <Spin size='large' spinning={loading} />
          {!loading && (
            <div className='text-center'>
              <TrendingUp className='w-16 h-16 text-gray-300 mx-auto mb-4' />
              <p className='text-gray-400 text-lg'>选择模型并点击开始对比</p>
              <p className='text-gray-400 text-sm mt-2'>支持 MMLU、GSM8K、HumanEval 数据集</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Models;
