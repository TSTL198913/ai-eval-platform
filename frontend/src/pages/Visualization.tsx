/**
 * 📊 src/pages/Visualization.tsx
 * 可视化分析页面
 */

import React from 'react';
import EvaluationDashboard from '../components/EvaluationDashboard';

const Visualization: React.FC = () => {
  return (
    <div>
      <EvaluationDashboard title="AI 评测可视化分析" />
    </div>
  );
};

export default Visualization;
