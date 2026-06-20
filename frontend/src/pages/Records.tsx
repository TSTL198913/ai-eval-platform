import { useState, useEffect } from 'react';
import { Card, Table, Tag, Button, Input, Select, Pagination, Spin, Empty, Tooltip } from 'antd';
import { Search, Download, RefreshCw, Eye } from 'lucide-react';
import { evaluationApi } from '@/services/api';
import { EvaluationRecord } from '@/types';
import { formatDate, formatLatency } from '@/utils';
import { StatusBadge } from '@/components/StatusBadge';

export const RecordsPage = () => {
  const [records, setRecords] = useState<EvaluationRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  useEffect(() => {
    const fetchRecords = async () => {
      try {
        const params: Record<string, unknown> = {
          page,
          page_size: pageSize,
        };
        if (searchTerm) params.search = searchTerm;
        if (statusFilter) params.status = statusFilter;

        const result = await evaluationApi.getRecords(params);
        setRecords(result.records);
        setTotal(result.total);
      } catch (error) {
        console.error('Failed to fetch records:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchRecords();
  }, [page, pageSize, searchTerm, statusFilter]);

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 80,
      render: (id: number) => <span className="text-gray-600">{id}</span>,
    },
    {
      title: '任务ID',
      dataIndex: 'case_id',
      key: 'case_id',
      width: 150,
      render: (caseId: string) => (
        <Tooltip title={caseId}>
          <span className="truncate">{caseId}</span>
        </Tooltip>
      ),
    },
    {
      title: '评估器',
      dataIndex: 'adapter_name',
      key: 'adapter_name',
      width: 120,
      render: (name: string) => (
        <Tag color="blue">{name}</Tag>
      ),
    },
    {
      title: '模型',
      dataIndex: 'model_name',
      key: 'model_name',
      width: 120,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => <StatusBadge status={status} />,
    },
    {
      title: '分数',
      dataIndex: 'score',
      key: 'score',
      width: 100,
      render: (score: number) => (
        <span className={`font-medium ${score >= 0.8 ? 'text-green-600' : score >= 0.6 ? 'text-amber-600' : 'text-red-600'}`}>
          {score.toFixed(2)}
        </span>
      ),
    },
    {
      title: '延迟',
      dataIndex: 'latency_ms',
      key: 'latency_ms',
      width: 100,
      render: (latency: number) => (
        <span className="text-gray-600">{formatLatency(latency)}</span>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (time: string) => (
        <span className="text-gray-600">{formatDate(time)}</span>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: () => (
        <div className="flex items-center gap-2">
          <Button type="text" icon={<Eye className="w-4 h-4" />} size="small">
            查看
          </Button>
        </div>
      ),
    },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card
        title="评估记录"
        extra={
          <div className="flex items-center gap-2">
            <Button type="primary" icon={<Download className="w-4 h-4" />}>
              导出
            </Button>
            <Button icon={<RefreshCw className="w-4 h-4" />}>
              刷新
            </Button>
          </div>
        }
      >
        <div className="flex flex-wrap items-center gap-4 mb-6">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <Input
              placeholder="搜索任务ID..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setPage(1);
              }}
              className="w-64 pl-10"
            />
          </div>
          <Select
            placeholder="状态筛选"
            value={statusFilter}
            onChange={(value) => {
              setStatusFilter(value);
              setPage(1);
            }}
            options={[
              { value: '', label: '全部' },
              { value: 'pending', label: '待处理' },
              { value: 'running', label: '运行中' },
              { value: 'completed', label: '已完成' },
              { value: 'failed', label: '失败' },
            ]}
            style={{ width: 150 }}
          />
        </div>

        {records.length > 0 ? (
          <div>
            <Table
              dataSource={records}
              columns={columns}
              rowKey="id"
              pagination={false}
              scroll={{ x: 1000 }}
            />
            <div className="flex justify-end mt-4">
              <Pagination
                current={page}
                pageSize={pageSize}
                total={total}
                onChange={(page, pageSize) => {
                  setPage(page);
                  setPageSize(pageSize);
                }}
                showSizeChanger
                showTotal={(total) => `共 ${total} 条记录`}
              />
            </div>
          </div>
        ) : (
          <Empty description="暂无评估记录" />
        )}
      </Card>
    </div>
  );
};
