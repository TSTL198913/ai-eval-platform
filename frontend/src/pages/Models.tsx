import { useState, useEffect } from 'react';
import { Card, Select, Button, Row, Col, Spin, Statistic } from 'antd';
import { Database, BarChart2 } from 'lucide-react';
import { modelApi } from '@/services/api';
import { Model, ModelComparisonResult } from '@/types';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

export const ModelsPage = () => {
  const [models, setModels] = useState<Model[]>([]);
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [comparisonResult, setComparisonResult] = useState<ModelComparisonResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [modelLoading, setModelLoading] = useState(true);

  useEffect(() => {
    const fetchModels = async () => {
      try {
        const data = await modelApi.list();
        setModels(data);
      } catch (error) {
        console.error('Failed to fetch models:', error);
      } finally {
        setModelLoading(false);
      }
    };
    fetchModels();
  }, []);

  const handleCompare = async () => {
    if (selectedModels.length < 2) return;
    setLoading(true);
    try {
      const result = await modelApi.compare(selectedModels, 'gsm8k');
      setComparisonResult(result);
    } catch (error) {
      console.error('Failed to compare models:', error);
    } finally {
      setLoading(false);
    }
  };

  if (modelLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card title="模型对比">
        <div className="flex flex-wrap items-center gap-4 mb-6">
          <Select
            mode="multiple"
            placeholder="选择要对比的模型（至少2个）"
            value={selectedModels}
            onChange={setSelectedModels}
            style={{ width: '60%' }}
            options={models.map((model) => ({
              value: model.name,
              label: model.display_name || model.name,
            }))}
          />
          <Button
            type="primary"
            onClick={handleCompare}
            disabled={selectedModels.length < 2}
            loading={loading}
          >
            开始对比
          </Button>
        </div>

        {comparisonResult.length > 0 ? (
          <div className="space-y-6">
            <Row gutter={[24, 24]}>
              {comparisonResult.map((result) => (
                <Col xs={24} sm={12} lg={8} key={result.model_name}>
                  <Card className="text-center">
                    <div className="w-16 h-16 rounded-full bg-gradient-to-br from-[#667eea] to-[#764ba2] flex items-center justify-center mx-auto mb-4">
                      <Database className="w-8 h-8 text-white" />
                    </div>
                    <h3 className="text-lg font-bold text-gray-800 mb-2">
                      {result.model_name}
                    </h3>
                    <div className="space-y-3">
                      <Statistic
                        title="准确率"
                        value={result.accuracy}
                        suffix="%"
                        valueStyle={{ color: '#10b981' }}
                      />
                      <Statistic
                        title="延迟"
                        value={result.latency_ms}
                        suffix="ms"
                        valueStyle={{ color: '#3b82f6' }}
                      />
                      <Statistic
                        title="成本"
                        value={result.cost}
                        suffix="元"
                        valueStyle={{ color: '#ef4444' }}
                      />
                    </div>
                  </Card>
                </Col>
              ))}
            </Row>

            <Card title="对比图表">
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={comparisonResult}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="model_name" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="accuracy" name="准确率%" fill="#10b981" />
                    <Bar dataKey="latency_ms" name="延迟ms" fill="#3b82f6" />
                    <Bar dataKey="cost" name="成本" fill="#ef4444" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-12">
            <BarChart2 className="w-16 h-16 text-gray-300 mb-4" />
            <p className="text-gray-500">选择模型并点击开始对比</p>
          </div>
        )}
      </Card>

      <Card title="可用模型">
        <Row gutter={[24, 24]}>
          {models.map((model) => (
            <Col xs={24} sm={12} lg={8} key={model.name}>
              <Card
                className={`border-l-4 ${model.status === 'active' ? 'border-l-green-500' : 'border-l-gray-300'}`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <div className="w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center">
                      <Database className="w-5 h-5 text-gray-600" />
                    </div>
                    <div>
                      <h3 className="font-bold text-gray-800">
                        {model.display_name || model.name}
                      </h3>
                      <p className="text-xs text-gray-500">{model.provider}</p>
                    </div>
                  </div>
                  <span
                    className={`px-2 py-1 rounded-full text-xs font-medium ${
                      model.status === 'active'
                        ? 'bg-green-100 text-green-600'
                        : 'bg-gray-100 text-gray-600'
                    }`}
                  >
                    {model.status === 'active' ? '活跃' : '停用'}
                  </span>
                </div>

                <p className="text-sm text-gray-600 mb-3">
                  {model.description || '暂无描述'}
                </p>

                <div className="flex flex-wrap gap-1">
                  {model.capabilities?.map((cap) => (
                    <span
                      key={cap}
                      className="px-2 py-0.5 bg-blue-50 text-blue-600 rounded text-xs"
                    >
                      {cap}
                    </span>
                  ))}
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      </Card>
    </div>
  );
};
