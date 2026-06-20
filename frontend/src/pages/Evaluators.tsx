import { useState, useEffect } from 'react';
import { Card, Input, Row, Col, Tag, Button, Modal, Spin, Empty, Descriptions } from 'antd';
import { Search, Cpu, ChevronRight } from 'lucide-react';
import { evaluatorApi } from '@/services/api';
import { Evaluator } from '@/types';

export const EvaluatorsPage = () => {
  const [evaluators, setEvaluators] = useState<Evaluator[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [selectedEvaluator, setSelectedEvaluator] = useState<Evaluator | null>(null);
  const [modalVisible, setModalVisible] = useState(false);

  useEffect(() => {
    const fetchEvaluators = async () => {
      try {
        const data = await evaluatorApi.list();
        setEvaluators(data);
      } catch (error) {
        console.error('Failed to fetch evaluators:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchEvaluators();
  }, []);

  const filteredEvaluators = evaluators.filter((e) =>
    e.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    e.display_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    e.description?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleViewDetail = (evaluator: Evaluator) => {
    setSelectedEvaluator(evaluator);
    setModalVisible(true);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Row justify="space-between" align="middle">
        <Col>
          <h2 className="text-xl font-bold text-gray-800">评估器管理</h2>
          <p className="text-gray-500 mt-1">管理和配置系统中的评估器</p>
        </Col>
        <Col>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <Input
              placeholder="搜索评估器..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-64 pl-10"
            />
          </div>
        </Col>
      </Row>

      {filteredEvaluators.length > 0 ? (
        <Row gutter={[24, 24]}>
          {filteredEvaluators.map((evaluator) => (
            <Col xs={24} sm={12} lg={8} key={evaluator.name}>
              <Card
                className="hover:shadow-lg transition-shadow cursor-pointer"
                onClick={() => handleViewDetail(evaluator)}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <div className="w-10 h-10 rounded-lg bg-[#667eea]/10 flex items-center justify-center">
                      <Cpu className="w-5 h-5 text-[#667eea]" />
                    </div>
                    <div>
                      <h3 className="font-bold text-gray-800">
                        {evaluator.display_name || evaluator.name}
                      </h3>
                      <p className="text-xs text-gray-500">{evaluator.module_name}</p>
                    </div>
                  </div>
                  <Tag color={evaluator.enabled ? 'green' : 'gray'}>
                    {evaluator.enabled ? '启用' : '禁用'}
                  </Tag>
                </div>

                <p className="text-sm text-gray-600 mb-4 line-clamp-2">
                  {evaluator.description || '暂无描述'}
                </p>

                <div className="flex flex-wrap gap-1 mb-4">
                  {evaluator.supported_types?.map((type) => (
                    <Tag key={type} color="blue">
                      {type}
                    </Tag>
                  ))}
                </div>

                <div className="flex items-center justify-between text-xs text-gray-400">
                  <span>版本: {evaluator.version}</span>
                  <Button type="text" icon={<ChevronRight className="w-4 h-4" />}>
                    查看详情
                  </Button>
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      ) : (
        <Card>
          <Empty description="暂无评估器" />
        </Card>
      )}

      <Modal
        title="评估器详情"
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setModalVisible(false)}>
            关闭
          </Button>,
        ]}
      >
        {selectedEvaluator && (
          <Descriptions column={1} bordered>
            <Descriptions.Item label="名称">
              {selectedEvaluator.display_name || selectedEvaluator.name}
            </Descriptions.Item>
            <Descriptions.Item label="模块">
              {selectedEvaluator.module_name}
            </Descriptions.Item>
            <Descriptions.Item label="类名">
              {selectedEvaluator.class_name}
            </Descriptions.Item>
            <Descriptions.Item label="版本">
              {selectedEvaluator.version}
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={selectedEvaluator.enabled ? 'green' : 'gray'}>
                {selectedEvaluator.enabled ? '启用' : '禁用'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="描述">
              {selectedEvaluator.description || '暂无描述'}
            </Descriptions.Item>
            <Descriptions.Item label="支持类型">
              {selectedEvaluator.supported_types?.map((type) => (
                <Tag key={type} color="blue" className="mr-1">
                  {type}
                </Tag>
              ))}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  );
};
