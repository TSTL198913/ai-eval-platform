
import React, { useState, useEffect } from 'react';
import { Card, Input, Spin, Modal, Tag } from 'antd';
import { Search, Info, X } from 'lucide-react';
import { evaluatorApi } from '../services/api';
import { Evaluator } from '../types';

const Evaluators: React.FC = () => {
  const [evaluators, setEvaluators] = useState<Evaluator[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedEvaluator, setSelectedEvaluator] = useState<Evaluator | null>(null);
  const [modalVisible, setModalVisible] = useState(false);

  useEffect(() => {
    const fetchEvaluators = async () => {
      try {
        const data = await evaluatorApi.getAll();
        setEvaluators(data);
      } catch (error) {
        console.error('Failed to fetch evaluators:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchEvaluators();
  }, []);

  const filteredEvaluators = evaluators.filter(e => 
    e.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    e.class_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleEvaluatorClick = (evaluator: Evaluator) => {
    setSelectedEvaluator(evaluator);
    setModalVisible(true);
  };

  return (
    <div>
      <Card className='mb-6'>
        <div className='flex items-center gap-4'>
          <Search className='w-5 h-5 text-gray-400' />
          <Input
            placeholder='搜索评估器...'
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className='w-80'
          />
        </div>
      </Card>

      {loading ? (
        <div className='flex items-center justify-center h-96'>
          <Spin size='large' />
        </div>
      ) : (
        <div className='grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4'>
          {filteredEvaluators.map((evaluator) => (
            <Card
              key={evaluator.name}
              hoverable
              className='cursor-pointer hover:shadow-lg transition-shadow duration-300'
              onClick={() => handleEvaluatorClick(evaluator)}
            >
              <div className='flex items-start justify-between mb-2'>
                <h3 className='font-semibold text-gray-800'>{evaluator.name}</h3>
                <Info className='w-4 h-4 text-gray-400' />
              </div>
              <Tag color='blue' className='mb-2'>{evaluator.class_name}</Tag>
              <p className='text-gray-500 text-sm line-clamp-2'>{evaluator.docstring || '暂无描述'}</p>
            </Card>
          ))}
        </div>
      )}

      <Modal
        title={selectedEvaluator?.name}
        visible={modalVisible}
        footer={null}
        onCancel={() => setModalVisible(false)}
        width={600}
      >
        {selectedEvaluator && (
          <div>
            <div className='flex items-center gap-2 mb-4'>
              <Tag color='blue'>{selectedEvaluator.class_name}</Tag>
            </div>
            <div className='mb-4'>
              <p className='text-gray-500 text-sm mb-1'>模块</p>
              <p className='font-mono text-sm text-gray-800'>{selectedEvaluator.module}</p>
            </div>
            <div>
              <p className='text-gray-500 text-sm mb-1'>描述</p>
              <p className='text-gray-700'>{selectedEvaluator.docstring || '暂无描述'}</p>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default Evaluators;
