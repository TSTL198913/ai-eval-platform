import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Evaluators from "@/pages/Evaluators";
import Models from "@/pages/Models";
import Records from "@/pages/Records";
import Cost from "@/pages/Cost";
import Health from "@/pages/Health";
import AppLayout from "@/components/Layout/AppLayout";
import useAuthStore from "@/stores/authStore";

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  if (!isAuthenticated) {
    return <Navigate to="/login" />;
  }
  return <AppLayout>{children}</AppLayout>;
};

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
        <Route path="/evaluators" element={<ProtectedRoute><Evaluators /></ProtectedRoute>} />
        <Route path="/models" element={<ProtectedRoute><Models /></ProtectedRoute>} />
        <Route path="/records" element={<ProtectedRoute><Records /></ProtectedRoute>} />
        <Route path="/cost" element={<ProtectedRoute><Cost /></ProtectedRoute>} />
        <Route path="/health" element={<ProtectedRoute><Health /></ProtectedRoute>} />
      </Routes>
    </Router>
  );
}
