import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Evaluators from "@/pages/Evaluators";
import Models from "@/pages/Models";
import Records from "@/pages/Records";
import Reports from "@/pages/Reports";
import Cost from "@/pages/Cost";
import Health from "@/pages/Health";
import SecurityTest from "@/pages/SecurityTest";
import AppLayout from "@/components/Layout/AppLayout";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import useAuthStore from "@/stores/authStore";

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  if (!isAuthenticated) {
    return <Navigate to="/login" />;
  }
  return (
    <ErrorBoundary>
      <AppLayout>{children}</AppLayout>
    </ErrorBoundary>
  );
};

export default function App() {
  return (
    <ErrorBoundary>
      <Router>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/evaluators" element={<ProtectedRoute><Evaluators /></ProtectedRoute>} />
          <Route path="/models" element={<ProtectedRoute><Models /></ProtectedRoute>} />
          <Route path="/records" element={<ProtectedRoute><Records /></ProtectedRoute>} />
          <Route path="/reports" element={<ProtectedRoute><Reports /></ProtectedRoute>} />
          <Route path="/cost" element={<ProtectedRoute><Cost /></ProtectedRoute>} />
          <Route path="/health" element={<ProtectedRoute><Health /></ProtectedRoute>} />
          <Route path="/security" element={<ProtectedRoute><SecurityTest /></ProtectedRoute>} />
        </Routes>
      </Router>
    </ErrorBoundary>
  );
}
