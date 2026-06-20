import { useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';
import { AppLayout } from '@/components/Layout';
import { LoginPage } from '@/pages/Login';
import { DashboardPage } from '@/pages/Dashboard';
import { EvaluatorsPage } from '@/pages/Evaluators';
import { ModelsPage } from '@/pages/Models';
import { RecordsPage } from '@/pages/Records';
import { CostPage } from '@/pages/Cost';
import { HealthPage } from '@/pages/Health';

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, checkAuth } = useAuthStore();

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

const getPageTitle = (path: string): string => {
  const titleMap: Record<string, string> = {
    '/': '仪表盘',
    '/evaluators': '评估器管理',
    '/models': '模型对比',
    '/records': '评估记录',
    '/cost': '成本监控',
    '/health': '系统健康',
  };
  return titleMap[path] || 'AI评测平台';
};

const DashboardLayout = ({ children, currentPath }: { children: React.ReactNode; currentPath: string }) => (
  <AppLayout title={getPageTitle(currentPath)} currentPath={currentPath}>
    {children}
  </AppLayout>
);

export const App = () => {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route
        path="/"
        element={
          <ProtectedRoute>
            <DashboardLayout currentPath="/">
              <DashboardPage />
            </DashboardLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/evaluators"
        element={
          <ProtectedRoute>
            <DashboardLayout currentPath="/evaluators">
              <EvaluatorsPage />
            </DashboardLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/models"
        element={
          <ProtectedRoute>
            <DashboardLayout currentPath="/models">
              <ModelsPage />
            </DashboardLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/records"
        element={
          <ProtectedRoute>
            <DashboardLayout currentPath="/records">
              <RecordsPage />
            </DashboardLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/cost"
        element={
          <ProtectedRoute>
            <DashboardLayout currentPath="/cost">
              <CostPage />
            </DashboardLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/health"
        element={
          <ProtectedRoute>
            <DashboardLayout currentPath="/health">
              <HealthPage />
            </DashboardLayout>
          </ProtectedRoute>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};
