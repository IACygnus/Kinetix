/**
 * ReportView — Redirects to the most recently generated report.
 * Uses Navigate to the same route that History uses (/performance/report/:id).
 */
import { useState, useEffect } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { testAPI } from '../services/api';

export default function ReportView() {
  const [lastExecId, setLastExecId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const loadLatest = async () => {
      try {
        const executions = await testAPI.getExecutions();
        const list = Array.isArray(executions) ? executions : [];
        if (list.length > 0) {
          setLastExecId(list[0].id);
        }
      } catch (err) {
        console.error('Error fetching executions:', err);
        setError(true);
      }
      setLoading(false);
    };
    loadLatest();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-[#f5a623] mx-auto mb-4"></div>
          <p className="text-lg text-gray-500">Cargando ultimo reporte...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <p className="text-xl text-red-500">Error al cargar reportes</p>
        <button onClick={() => window.location.reload()}
          className="px-6 py-2 bg-gray-200 text-gray-700 rounded-xl text-lg hover:bg-gray-300 transition-colors">
          Reintentar
        </button>
      </div>
    );
  }

  if (!lastExecId) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <p className="text-xl text-gray-500">No hay reportes generados aun</p>
        <button onClick={() => navigate('/performance/new')}
          className="px-8 py-3 bg-[#f5a623] text-[#0a1628] rounded-xl font-bold text-lg hover:bg-[#f5a623]/90 transition-colors">
          Crear Nuevo Reporte
        </button>
      </div>
    );
  }

  // Redirect to the working report route (same one History uses)
  return <Navigate to={`/performance/report/${lastExecId}`} replace />;
}
