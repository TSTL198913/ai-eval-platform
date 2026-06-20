export const formatDate = (dateString: string): string => {
  const date = new Date(dateString);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
};

export const formatNumber = (num: number, decimals: number = 2): string => {
  return num.toLocaleString('zh-CN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
};

export const formatLatency = (ms: number): string => {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(2)}s`;
  return `${(ms / 60000).toFixed(2)}min`;
};

export const formatCurrency = (amount: number): string => {
  return `¥${amount.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
};

export const getStatusColor = (status: string): string => {
  const colorMap: Record<string, string> = {
    healthy: '#10b981',
    unhealthy: '#ef4444',
    degraded: '#f59e0b',
    pending: '#f59e0b',
    running: '#3b82f6',
    completed: '#10b981',
    failed: '#ef4444',
    active: '#10b981',
    inactive: '#9ca3af',
  };
  return colorMap[status] || '#6b7280';
};

export const getStatusText = (status: string): string => {
  const textMap: Record<string, string> = {
    healthy: '健康',
    unhealthy: '异常',
    degraded: '降级',
    pending: '待处理',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    active: '活跃',
    inactive: '停用',
  };
  return textMap[status] || status;
};

export const getScoreLevel = (score: number): { level: string; color: string } => {
  if (score >= 0.9) return { level: '优秀', color: '#10b981' };
  if (score >= 0.8) return { level: '良好', color: '#3b82f6' };
  if (score >= 0.7) return { level: '合格', color: '#f59e0b' };
  if (score >= 0.6) return { level: '较差', color: '#f97316' };
  return { level: '不合格', color: '#ef4444' };
};

export const debounce = <T extends (...args: unknown[]) => void>(
  func: T,
  wait: number
): ((...args: Parameters<T>) => void) => {
  let timeout: ReturnType<typeof setTimeout> | null = null;
  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
};
