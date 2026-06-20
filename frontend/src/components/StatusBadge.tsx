interface StatusBadgeProps {
  status: string;
  size?: 'small' | 'medium';
}

export const StatusBadge = ({ status, size = 'medium' }: StatusBadgeProps) => {
  const statusMap: Record<string, { color: string; bg: string; text: string }> = {
    healthy: { color: '#10b981', bg: 'bg-emerald-100', text: '健康' },
    unhealthy: { color: '#ef4444', bg: 'bg-red-100', text: '异常' },
    degraded: { color: '#f59e0b', bg: 'bg-amber-100', text: '降级' },
    pending: { color: '#f59e0b', bg: 'bg-amber-100', text: '待处理' },
    running: { color: '#3b82f6', bg: 'bg-blue-100', text: '运行中' },
    completed: { color: '#10b981', bg: 'bg-emerald-100', text: '已完成' },
    failed: { color: '#ef4444', bg: 'bg-red-100', text: '失败' },
    active: { color: '#10b981', bg: 'bg-emerald-100', text: '活跃' },
    inactive: { color: '#9ca3af', bg: 'bg-gray-100', text: '停用' },
  };

  const config = statusMap[status] || { color: '#6b7280', bg: 'bg-gray-100', text: status };

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${config.bg}`}
      style={{ color: config.color }}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${size === 'small' ? '' : 'animate-pulse'}`}
        style={{ backgroundColor: config.color }}
      />
      {config.text}
    </span>
  );
};
