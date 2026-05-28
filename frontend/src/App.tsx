/**
 * App - Router principal con layout y rutas protegidas - v2.0
 */
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useParams } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import ProtectedRoute from './components/common/ProtectedRoute';
import Layout from './components/layout/Layout';
import Login from './components/auth/Login';
import DashboardHome from './components/dashboard/DashboardHome';
import UploadJTL from './components/dashboard/UploadJTL';
import Dashboard from './components/dashboard/Dashboard';
import History from './components/performance/History';
import MonitoringRealtime from './components/monitoring/MonitoringRealtime';
import MonitoringSettings from './components/monitoring/MonitoringSettings';
import UserList from './components/users/UserList';
import UserForm from './components/users/UserForm';
import ClientsPage from './components/clients/ClientsPage';
import AssignmentsPage from './components/clients/AssignmentsPage';
import AIConfigPage from './components/admin/AIConfigPage';
import Profile from './components/profile/Profile';
import ScriptDesigner from './pages/ScriptDesigner';
import AIScriptDesigner from './pages/AIScriptDesigner';
import AIDesignerHistory from './pages/AIDesignerHistory';
import AIScriptEditor from './pages/AIScriptEditor';
import AIScriptEditorList from './pages/AIScriptEditorList';
import ExecutionDashboard from './pages/ExecutionDashboard';
import ReportView from './pages/ReportView';
import MonitoringPage from './pages/MonitoringPage';
import EvidencePage from './pages/EvidencePage';
import IntegratedReportPage from './pages/IntegratedReportPage';
import IntegratedReportsHistory from './pages/IntegratedReportsHistory';
import ScriptHistory from './pages/ScriptHistory';

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public route */}
          <Route path="/login" element={<Login />} />

          {/* Protected routes with layout */}
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            {/* Dashboard Home */}
            <Route path="/dashboard" element={<DashboardHome />} />

            {/* Performance */}
            <Route
              path="/performance/new"
              element={
                <ProtectedRoute roles={['admin', 'analyst']}>
                  <NewReportWrapper />
                </ProtectedRoute>
              }
            />
            <Route path="/performance/report/:executionId" element={<ReportWrapper />} />
            <Route path="/performance/report-latest" element={<ReportView />} />
            <Route path="/performance/monitoring" element={<MonitoringPage />} />
            <Route path="/performance/evidence" element={<EvidencePage />} />
            <Route path="/performance/integrated" element={<IntegratedReportPage />} />
            <Route
              path="/performance/integrated/history"
              element={
                <ProtectedRoute roles={['admin', 'analyst']}>
                  <IntegratedReportsHistory />
                </ProtectedRoute>
              }
            />
            <Route path="/performance/integrated/:reportId" element={<IntegratedReportPage />} />
            <Route path="/performance/history" element={<History />} />

            {/* Monitoring */}
            <Route path="/monitoring/realtime" element={<MonitoringRealtime />} />
            <Route
              path="/monitoring/settings"
              element={
                <ProtectedRoute roles={['admin']}>
                  <MonitoringSettings />
                </ProtectedRoute>
              }
            />

            {/* Users - Admin only */}
            <Route
              path="/users"
              element={
                <ProtectedRoute roles={['admin']}>
                  <UserList />
                </ProtectedRoute>
              }
            />
            <Route
              path="/users/new"
              element={
                <ProtectedRoute roles={['admin']}>
                  <UserForm />
                </ProtectedRoute>
              }
            />
            <Route
              path="/users/:userId"
              element={
                <ProtectedRoute roles={['admin']}>
                  <UserForm />
                </ProtectedRoute>
              }
            />

            {/* Admin - Clients & Assignments */}
            <Route
              path="/admin/clients"
              element={
                <ProtectedRoute roles={['admin']}>
                  <ClientsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/assignments"
              element={
                <ProtectedRoute roles={['admin']}>
                  <AssignmentsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/ai-config"
              element={
                <ProtectedRoute roles={['admin']}>
                  <AIConfigPage />
                </ProtectedRoute>
              }
            />

            {/* Script Designer */}
            <Route
              path="/script-designer"
              element={
                <ProtectedRoute roles={['admin', 'analyst']}>
                  <ScriptDesigner />
                </ProtectedRoute>
              }
            />
            <Route
              path="/script-designer/history"
              element={
                <ProtectedRoute roles={['admin', 'analyst']}>
                  <ScriptHistory />
                </ProtectedRoute>
              }
            />
            <Route
              path="/script-designer/:scriptId"
              element={
                <ProtectedRoute roles={['admin', 'analyst']}>
                  <ScriptDesigner />
                </ProtectedRoute>
              }
            />

            {/* AI Script Designer */}
            <Route
              path="/ai-script-designer/history"
              element={
                <ProtectedRoute roles={['admin', 'analyst']}>
                  <AIDesignerHistory />
                </ProtectedRoute>
              }
            />
            <Route
              path="/ai-script-designer/editor/:designId"
              element={
                <ProtectedRoute roles={['admin', 'analyst']}>
                  <AIScriptEditor />
                </ProtectedRoute>
              }
            />
            <Route
              path="/ai-script-editor"
              element={
                <ProtectedRoute roles={['admin', 'analyst']}>
                  <AIScriptEditorList />
                </ProtectedRoute>
              }
            />
            <Route
              path="/ai-script-designer"
              element={
                <ProtectedRoute roles={['admin', 'analyst']}>
                  <AIScriptDesigner />
                </ProtectedRoute>
              }
            />

            {/* Execution Dashboard */}
            <Route
              path="/execution-dashboard"
              element={
                <ProtectedRoute roles={['admin', 'analyst']}>
                  <ExecutionDashboard />
                </ProtectedRoute>
              }
            />

            {/* Profile */}
            <Route path="/profile" element={<Profile />} />
          </Route>

          {/* Default redirect */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

/**
 * Wrapper for UploadJTL to handle navigation after upload
 */
function NewReportWrapper() {
  const navigate = useNavigate();

  const handleUploadSuccess = (id: string) => {
    navigate(`/performance/report/${id}`);
  };

  return (
    <div className="max-w-5xl mx-auto">
      <UploadJTL onUploadSuccess={handleUploadSuccess} />
    </div>
  );
}

/**
 * Wrapper for Dashboard report view to get executionId from URL
 */
function ReportWrapper() {
  const { executionId } = useParams<{ executionId: string }>();
  const navigate = useNavigate();
  const { logout } = useAuth();

  if (!executionId) {
    return <Navigate to="/performance/history" replace />;
  }

  return (
    <Dashboard
      executionId={executionId}
      onLogout={logout}
      onBack={() => navigate('/performance/history')}
    />
  );
}

export default App;
