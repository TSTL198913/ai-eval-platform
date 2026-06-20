import React from 'react';
import { Spin } from 'antd';

interface LoadingSpinnerProps {
  height?: string;
  size?: 'small' | 'default' | 'large';
}

/**
 * Loading加载组件 - 统一Loading状态处理
 * 用于页面加载、数据请求等场景
 */
const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  height = 'h-96',
  size = 'large'
}) => {
  return (
    <div className={`flex items-center justify-center ${height}`}>
      <Spin size={size} />
    </div>
  );
};

export default LoadingSpinner;