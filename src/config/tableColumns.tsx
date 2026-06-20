import StatusTag from '../components/StatusTag';
import { Checkbox, Button } from 'antd';

/**
 * 表格列配置 - 统一评估记录表格列定义
 * 用于Dashboard、Records等页面
 */
export const getEvaluationRecordColumns = (options: {
  showCheckbox?: boolean;
  showActions?: boolean;
  onCheckboxChange?: (id: number, checked: boolean) => void;
  onActionClick?: (record: any) => void;
} = {}) => {
  const baseColumns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
    { title: 'Case ID', dataIndex: 'case_id', key: 'case_id' },
    { title: '评估器', dataIndex: 'adapter_name', key: 'adapter_name' },
    { title: '模型', dataIndex: 'model_name', key: 'model_name' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => <StatusTag status={status} />
    },
    {
      title: '分数',
      dataIndex: 'score',
      key: 'score',
      render: (s: number) => s?.toFixed(2) || '-'
    },
    {
      title: '延迟(ms)',
      dataIndex: 'latency_ms',
      key: 'latency_ms',
      render: (l: number) => l?.toFixed(1) || '-'
    },
    { title: '时间', dataIndex: 'created_at', key: 'created_at' },
  ];

  // 可选添加checkbox列
  if (options.showCheckbox) {
    baseColumns.unshift({
      title: '选择',
      render: (record: any) => (
        <Checkbox
          onChange={(e) => options.onCheckboxChange?.(record.id, e.target.checked)}
        />
      ),
      width: 60,
    });
  }

  // 可选添加操作列
  if (options.showActions) {
    baseColumns.push({
      title: '操作',
      render: (record: any) => (
        <Button
          type='link'
          onClick={() => options.onActionClick?.(record)}
        >
          重新评估
        </Button>
      ),
      width: 100,
    });
  }

  return baseColumns;
};