/**
 * History - Historial de reportes de performance - v2.1
 * Light theme, separate client/project columns, client + project filters
 */
import { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Eye,
  FileCode,
  FileDown,
  Trash2,
  Search,
  ClipboardList,
  AlertCircle,
} from 'lucide-react';
import { testAPI } from '../../services/api';
import { useAuth } from '../../context/AuthContext';

interface Execution {
  id: string;
  name: string;
  description: string | null;
  client: string | null;
  project: string | null;
  test_type: string;
  jtl_filename: string;
  jtl_filenames: string[] | null;
  total_requests: number;
  error_rate: number;
  avg_response_time: number;
  throughput: number;
  total_redirects: number;
  created_at: string;
}

const TEST_TYPE_BADGE: Record<string, { label: string; className: string }> = {
  load: { label: 'Load', className: 'bg-blue-100 text-blue-700 border-blue-300' },
  stress: { label: 'Stress', className: 'bg-red-100 text-red-700 border-red-300' },
  endurance: { label: 'Endurance', className: 'bg-emerald-100 text-emerald-700 border-emerald-300' },
  scalability: { label: 'Scalability', className: 'bg-purple-100 text-purple-700 border-purple-300' },
  spike: { label: 'Spike', className: 'bg-orange-100 text-orange-700 border-orange-300' },
  smoke: { label: 'Smoke', className: 'bg-gray-100 text-gray-700 border-gray-300' },
};

export default function History() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState<string>('all');
  const [filterClient, setFilterClient] = useState<string>('all');
  const [filterProject, setFilterProject] = useState<string>('all');
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const fetchExecutions = async () => {
    try {
      const data = await testAPI.getExecutions();
      // Fetch attachment counts for each execution
      const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';
      const withCounts = await Promise.all(
        (data as any[]).map(async (exec: any) => {
          try {
            const res = await fetch(`${apiBase}/executions/${exec.id}/attachment-counts`, { credentials: 'include' });
            if (res.ok) {
              const counts = await res.json();
              return { ...exec, monitoring_count: counts.monitoring || 0, evidence_count: counts.evidence || 0 };
            }
          } catch { /* ignore */ }
          return { ...exec, monitoring_count: 0, evidence_count: 0 };
        })
      );
      setExecutions(withCounts);
    } catch {
      setError('Error al cargar historial');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchExecutions();
  }, []);

  // Derive unique client and project lists for filters
  const uniqueClients = useMemo(() => {
    const set = new Set<string>();
    executions.forEach((e) => { if (e.client) set.add(e.client); });
    return Array.from(set).sort();
  }, [executions]);

  const uniqueProjects = useMemo(() => {
    const set = new Set<string>();
    const filtered = filterClient === 'all'
      ? executions
      : executions.filter((e) => e.client === filterClient);
    filtered.forEach((e) => { if (e.project) set.add(e.project); });
    return Array.from(set).sort();
  }, [executions, filterClient]);

  const handleDelete = async (id: string) => {
    try {
      await testAPI.deleteExecution(id);
      setDeleteConfirm(null);
      await fetchExecutions();
    } catch {
      setError('Error al eliminar ejecucion');
    }
  };

  const handleExportHTML = async (id: string) => {
    try {
      const blob = await testAPI.exportHTML(id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report_${id}.html`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      setError('Error al exportar HTML');
    }
  };

  const handleExportPDF = async (id: string) => {
    try {
      const blob = await testAPI.exportPDF(id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report_${id}.pdf`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      setError('Error al exportar PDF');
    }
  };

  const filteredExecutions = executions.filter((e) => {
    const matchesSearch =
      e.name.toLowerCase().includes(search.toLowerCase()) ||
      (e.description || '').toLowerCase().includes(search.toLowerCase()) ||
      (e.client || '').toLowerCase().includes(search.toLowerCase()) ||
      (e.project || '').toLowerCase().includes(search.toLowerCase()) ||
      e.jtl_filename.toLowerCase().includes(search.toLowerCase());

    const matchesType = filterType === 'all' || e.test_type === filterType;
    const matchesClient = filterClient === 'all' || e.client === filterClient;
    const matchesProject = filterProject === 'all' || e.project === filterProject;

    return matchesSearch && matchesType && matchesClient && matchesProject;
  });

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('es-ES', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-sqa-gold" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-sqa-navy to-sqa-navy-light rounded-2xl p-6 shadow-lg">
        <h1 className="text-4xl font-bold text-white">Historial de Reportes</h1>
        <p className="text-slate-300 mt-1 text-xl">{executions.length} reportes en total</p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
          <AlertCircle className="w-6 h-6 text-red-500" />
          <span className="text-red-700 text-lg">{error}</span>
          <button onClick={() => setError('')} className="ml-auto text-red-400 hover:text-red-600">
            x
          </button>
        </div>
      )}

      {/* Search + Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-6 h-6 text-gray-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por nombre, cliente, proyecto o archivo JTL..."
            className="w-full pl-12 pr-4 h-12 bg-white border border-gray-300 rounded-xl text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-sqa-gold focus:ring-2 focus:ring-sqa-gold/20 text-base"
          />
        </div>
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="px-4 h-12 bg-white border border-gray-300 rounded-xl text-gray-700 text-base focus:outline-none focus:border-sqa-gold"
        >
          <option value="all">Todos los tipos</option>
          <option value="load">Load Test</option>
          <option value="stress">Stress Test</option>
          <option value="endurance">Endurance Test</option>
          <option value="scalability">Scalability Test</option>
          <option value="spike">Spike Test</option>
          <option value="smoke">Smoke Test</option>
        </select>
        <select
          value={filterClient}
          onChange={(e) => {
            setFilterClient(e.target.value);
            setFilterProject('all');
          }}
          className="px-4 h-12 bg-white border border-gray-300 rounded-xl text-gray-700 text-base focus:outline-none focus:border-sqa-gold"
        >
          <option value="all">Todos los clientes</option>
          {uniqueClients.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <select
          value={filterProject}
          onChange={(e) => setFilterProject(e.target.value)}
          className="px-4 h-12 bg-white border border-gray-300 rounded-xl text-gray-700 text-base focus:outline-none focus:border-sqa-gold"
        >
          <option value="all">Todos los proyectos</option>
          {uniqueProjects.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden shadow-lg">
        <table className="w-full">
          <thead>
            <tr className="bg-[#0a1628] text-left">
              <th className="px-4 py-3 text-sm font-bold text-white uppercase tracking-wider">Fecha</th>
              <th className="px-4 py-3 text-sm font-bold text-white uppercase tracking-wider">Tipo</th>
              <th className="px-4 py-3 text-sm font-bold text-white uppercase tracking-wider">Cliente</th>
              <th className="px-4 py-3 text-sm font-bold text-white uppercase tracking-wider">Proyecto</th>
              <th className="px-4 py-3 text-sm font-bold text-white uppercase tracking-wider">Archivo JTL</th>
              <th className="px-4 py-3 text-sm font-bold text-white uppercase tracking-wider text-right">Muestras</th>
              <th className="px-4 py-3 text-sm font-bold text-white uppercase tracking-wider text-right">Error %</th>
              <th className="px-4 py-3 text-sm font-bold text-white uppercase tracking-wider text-right">Avg RT</th>
              <th className="px-4 py-3 text-sm font-bold text-white uppercase tracking-wider text-right">TPS</th>
              <th className="px-4 py-3 text-sm font-bold text-white uppercase tracking-wider text-center">Contenido</th>
              <th className="px-4 py-3 text-sm font-bold text-white uppercase tracking-wider text-right">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {filteredExecutions.map((exec, idx) => {
              const badge = TEST_TYPE_BADGE[exec.test_type] || TEST_TYPE_BADGE['load'];
              return (
                <tr
                  key={exec.id}
                  className={`${idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'} hover:bg-gray-100 transition-colors border-b border-gray-100`}
                >
                  <td className="px-4 py-3 text-base text-gray-700">
                    {formatDate(exec.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-block px-3 py-1 rounded-full text-xs font-bold uppercase border ${badge.className}`}>
                      {badge.label}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <p className="text-base font-semibold text-gray-800">{exec.client || '-'}</p>
                  </td>
                  <td className="px-4 py-3">
                    <p className="text-base text-gray-700">{exec.project || exec.name}</p>
                  </td>
                  <td className="px-4 py-3">
                    <p className="text-sm text-gray-500 font-mono">{exec.jtl_filename}</p>
                    {exec.jtl_filenames && exec.jtl_filenames.length > 1 && (
                      <p className="text-xs text-sqa-gold">+{exec.jtl_filenames.length - 1} archivos</p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-base text-gray-700 text-right">
                    {exec.total_requests.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span
                      className={`text-base font-semibold ${
                        exec.error_rate > 5
                          ? 'text-red-600'
                          : exec.error_rate > 1
                          ? 'text-amber-600'
                          : 'text-emerald-600'
                      }`}
                    >
                      {exec.error_rate.toFixed(2)}%
                    </span>
                  </td>
                  <td className="px-4 py-3 text-base text-gray-700 text-right">
                    {exec.avg_response_time.toFixed(0)}ms
                  </td>
                  <td className="px-4 py-3 text-base text-gray-700 text-right">
                    {exec.throughput.toFixed(2)}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex gap-1 justify-center">
                      <span className="text-xs px-1.5 py-0.5 rounded bg-blue-50 text-blue-600" title="Reporte de Performance">📄</span>
                      {(exec as any).monitoring_count > 0 && (
                        <span className="text-xs px-1.5 py-0.5 rounded bg-green-50 text-green-600" title={`${(exec as any).monitoring_count} metricas`}>📊 {(exec as any).monitoring_count}</span>
                      )}
                      {(exec as any).evidence_count > 0 && (
                        <span className="text-xs px-1.5 py-0.5 rounded bg-yellow-50 text-yellow-600" title={`${(exec as any).evidence_count} evidencias`}>🔍 {(exec as any).evidence_count}</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => navigate(`/performance/report/${exec.id}`)}
                        className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                        title="Ver reporte"
                      >
                        <Eye className="w-5 h-5" />
                      </button>
                      <button
                        onClick={() => handleExportHTML(exec.id)}
                        className="p-2 text-gray-400 hover:text-emerald-600 hover:bg-emerald-50 rounded transition-colors"
                        title="Exportar HTML"
                      >
                        <FileCode className="w-5 h-5" />
                      </button>
                      <button
                        onClick={() => handleExportPDF(exec.id)}
                        className="p-2 text-gray-400 hover:text-purple-600 hover:bg-purple-50 rounded transition-colors"
                        title="Exportar PDF"
                      >
                        <FileDown className="w-5 h-5" />
                      </button>
                      {user?.role === 'admin' && (
                        <button
                          onClick={() => setDeleteConfirm(exec.id)}
                          className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                          title="Eliminar"
                        >
                          <Trash2 className="w-5 h-5" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
            {filteredExecutions.length === 0 && (
              <tr>
                <td colSpan={11} className="px-6 py-12 text-center bg-white">
                  <ClipboardList className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                  <p className="text-gray-500 text-xl">No hay reportes en el historial</p>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-white border border-gray-200 rounded-xl p-6 w-full max-w-md shadow-2xl">
            <h3 className="text-2xl font-semibold text-gray-800 mb-2">Confirmar Eliminacion</h3>
            <p className="text-lg text-gray-500 mb-6">
              Esta accion no se puede deshacer. Se eliminara el reporte y todos sus datos asociados.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="px-5 py-3 text-xl text-gray-500 hover:text-gray-700 transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={() => handleDelete(deleteConfirm)}
                className="px-5 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 text-xl font-medium transition-colors"
              >
                Eliminar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
