
import React, { useState, useEffect } from 'react';
import { Card, Input, Select, Button, Table, Tag, Spin, Checkbox, message } from 'antd';
import { Search, RefreshCw, Download, Play } from 'lucide-react';
import { evaluationApi, evaluatorApi } from '../services/api';
import { EvaluationRecord, Evaluator } from '../types';

const { Option } = Select;

const Records: React.FC = () => {
  const [records, setRecords] = useState<EvaluationRecord[]>([]);
  const [evaluators, setEvaluators] = useState<Evaluator[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ evaluator: '', status: '' });
  const [selectedRecords, setSelectedRecords] = useState<number[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [recordsData, evaluatorsData] = await Promise.all([
          evaluationApi.getRecords({ limit: 50 }),
          evaluatorApi.getAll(),
        ]);
        setRecords(recordsData.records);
        setEvaluators(evaluatorsData);
      } catch (err: any) {
        // 架构规范：核心数据加载失败必须抛出
        console.error('Failed to fetch data:', err);
        message.error('数据加载失败');
        throw err;
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleSearch = async () => {
    setLoading(true);
    try {
      const data = await evaluationApi.searchRecords({
        evaluator: filters.evaluator || undefined,
        status: filters.status || undefined,
        limit: 50,
      });
      setRecords(data.records);
    } catch (err: any) {
      // 架构规范：搜索失败必须抛出让用户感知
      console.error('Search failed:', err);
      message.error(`搜索失败: ${err?.message || '未知错误'}`);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = () => {
    handleSearch();
  };

  const handleExport = () => {
    const data = selectedRecords.length > 0
      ? records.filter(r => selectedRecords.includes(r.id))
      : records;
    const csv = [['ID', 'Case ID', '评估器', '模型', '状态', '分数', '延迟(ms)', '时间']]
      .concat(data.map(r => [String(r.id), r.case_id, r.adapter_name, r.model_name, r.status, String(r.score), String(r.latency_ms), r.created_at]))
      .map(row => row.join(','))
      .join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'records.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleSelectAll = (e: { target: { checked: boolean } }) => {
    setSelectedRecords(e.target.checked ? records.map(r => r.id) : []);
  };

  const handleSelectRecord = (id: number, checked: boolean) => {
    setSelectedRecords(prev =>
      checked ? [...prev, id] : prev.filter(i => i !== id)
    );
  };

  const columns = [
    {
      title: (
        <Checkbox checked={selectedRecords.length === records.length} onChange={handleSelectAll} />
      ),
      render: (_: any, record: EvaluationRecord) => (
        <Checkbox checked={selectedRecords.includes(record.id)} onChange={(e) => handleSelectRecord(record.id, e.target.checked)} />
      ),
      width: 60,
    },
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
    {
      title: '操作',
      render: () => (
        <Button type='link' icon={<Play className='w-4 h-4' />}>重新评估</Button>
      ),
      width: 100,
    },
  ];

  return (
    <div>
      <Card className='mb-6'>
        <div className='flex items-center justify-between flex-wrap gap-4'>
          <div className='flex items-center gap-4 flex-wrap'>
            <Select
              placeholder='选择评估器'
              value={filters.evaluator}
              onChange={(value) => setFilters(prev => ({ ...prev, evaluator: value }))}
              style={{ width: 150 }}
            >
              <Option value=''>全部</Option>
              {evaluators.map((e) => (
                <Option key={e.name} value={e.name}>{e.name}</Option>
              ))}
            </Select>
            <Select
              placeholder='选择状态'
              value={filters.status}
              onChange={(value) => setFilters(prev => ({ ...prev, status: value }))}
              style={{ width: 120 }}
            >
              <Option value=''>全部</Option>
              <Option value='passed'>通过</Option>
              <Option value='failed'>失败</Option>
              <Option value='pending'>待处理</Option>
            </Select>
            <Button type='primary' onClick={handleSearch}>搜索</Button>
            <Button onClick={handleRefresh} icon={<RefreshCw className='w-4 h-4' />}>刷新</Button>
          </div>
          <Button icon={<Download className='w-4 h-4' />} onClick={handleExport}>
            导出{selectedRecords.length > 0 ? `(${selectedRecords.length})` : ''}
          </Button>
        </div>
      </Card>

      {loading ? (
        <div className='flex items-center justify-center h-96'>
          <Spin size='large' />
        </div>
      ) : (
        <Card>
          <Table
            dataSource={records}
            columns={columns}
            rowKey='id'
            pagination={{ pageSize: 20 }}
          />
        </Card>
      )}
    </div>
  );
};

export default Records;
