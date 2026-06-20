import React from 'react';
import { Tag } from 'antd';

interface StatusTagProps {
  status: string;
}

/**
 * 状态标签组件 - 统一状态渲染逻辑
 * 用于评估记录、任务状态等场景
 */
const StatusTag: React.FC<StatusTagProps> = ({ status }) => {
  const getStatusColor = (status: string): string => {
    const colorMap: Record<string, string> = {
      passed: 'green',
      failed: 'red',
      pending: 'orange',
      running: 'blue',
      success: 'green',
      error: 'red',
    };
    return colorMap[status] || 'default';
  };

  const getStatusText = (status: string): string => {
    const textMap: Record<string, string> = {
      passed: '通过',
      failed: '失败',
      pending: '待处理',
      running: '运行中',
      success: '成功',
      error: '错误',
    };
    return textMap[status] || status;
  };

  return <Tag color={getStatusColor(status)}>{getStatusText(status)}</Tag>;
};

export default StatusTag;