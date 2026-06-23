import { createBrowserRouter, RouterProvider, Navigate } from "react-router-dom";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Evaluators from "@/pages/Evaluators";
import Models from "@/pages/Models";
import Records from "@/pages/Records";
import Reports from "@/pages/Reports";
import Cost from "@/pages/Cost";
import Health from "@/pages/Health";
import SecurityTest from "@/pages/SecurityTest";
import Docs from "@/pages/Docs";
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

const router = createBrowserRouter(
  [
    {
      path: "/login",
      element: <Login />,
    },
    {
      path: "/",
      element: <ProtectedRoute><Dashboard /></ProtectedRoute>,
    },
    {
      path: "/evaluators",
      element: <ProtectedRoute><Evaluators /></ProtectedRoute>,
    },
    {
      path: "/models",
      element: <ProtectedRoute><Models /></ProtectedRoute>,
    },
    {
      path: "/records",
      element: <ProtectedRoute><Records /></ProtectedRoute>,
    },
    {
      path: "/reports",
      element: <ProtectedRoute><Reports /></ProtectedRoute>,
    },
    {
      path: "/cost",
      element: <ProtectedRoute><Cost /></ProtectedRoute>,
    },
    {
      path: "/health",
      element: <ProtectedRoute><Health /></ProtectedRoute>,
    },
    {
      path: "/security",
      element: <ProtectedRoute><SecurityTest /></ProtectedRoute>,
    },
    {
      path: "/docs",
      element: <ProtectedRoute><Docs /></ProtectedRoute>,
    },
  ],
  {
    future: {
      v7_startTransition: true,
      v7_relativeSplatPath: true,
    },
  }
);

export default function App() {
  return (
    <ErrorBoundary>
      <RouterProvider router={router} />
    </ErrorBoundary>
  );
}
