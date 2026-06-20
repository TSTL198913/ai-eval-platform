import { useEffect, useState } from 'react';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  trend?: { value: number; isUp: boolean };
  color: string;
  suffix?: string;
}

export const StatCard = ({ title, value, icon, trend, color, suffix }: StatCardProps) => {
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    if (typeof value === 'number') {
      const duration = 1500;
      const steps = 60;
      const increment = value / steps;
      let current = 0;
      const timer = setInterval(() => {
        current += increment;
        if (current >= value) {
          setDisplayValue(value);
          clearInterval(timer);
        } else {
          setDisplayValue(Math.floor(current));
        }
      }, duration / steps);
      return () => clearInterval(timer);
    }
    setDisplayValue(0);
  }, [value]);

  const formatValue = () => {
    if (typeof value === 'string') return value;
    return displayValue.toLocaleString('zh-CN');
  };

  return (
    <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100 hover:shadow-md transition-shadow duration-300">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm text-gray-500 mb-2">{title}</p>
          <div className="flex items-baseline gap-1">
            <span className="text-2xl font-bold text-gray-800">
              {formatValue()}
            </span>
            {suffix && <span className="text-sm text-gray-400">{suffix}</span>}
          </div>
          {trend && (
            <div className={`flex items-center gap-1 mt-2 text-sm ${trend.isUp ? 'text-green-500' : 'text-red-500'}`}>
              <span>{trend.isUp ? '↑' : '↓'}</span>
              <span>{Math.abs(trend.value)}%</span>
              <span className="text-gray-400">较上期</span>
            </div>
          )}
        </div>
        <div
          className="w-12 h-12 rounded-lg flex items-center justify-center"
          style={{ backgroundColor: `${color}15` }}
        >
          <div style={{ color }}>{icon}</div>
        </div>
      </div>
    </div>
  );
};
