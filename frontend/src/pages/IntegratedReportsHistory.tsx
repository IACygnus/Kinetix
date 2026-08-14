import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText,
  Search,
  Eye,
  Pencil,
  Trash2,
  Check,
  X,
  AlertCircle,
  CheckCircle2,
  Loader2,
} from 'lucide-react';
import {
  integratedReportsAPI,
  IntegratedReportSummary,
} from '../services/api';
import { useAuth } from '../context/AuthContext';

type SortKey = 'name' | 'created_at' | 'updated_at' | 'section_count';
type SortDir = 'asc' | 'desc';

export default function IntegratedReportsHistory() {
  // SEC-2: borrar es exclusivo de admin (el backend responde 403 al resto).
  const { user } = useAuth();
  const navigate = useNavigate();
  const [reports, setReports] = useState<IntegratedReportSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filtros
  const [search, setSearch] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'consolidated' | 'draft'>('all');

  // Ordenamiento
  const [sortKey, setSortKey] = useState<SortKey>('updated_at');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  // Rename inline
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState('');
  const [savingRename, setSavingRename] = useState(false);

  // Delete modal
  const [deleteTarget, setDeleteTarget] = useState<IntegratedReportSummary | null>(null);
  const [deleting, setDeleting] = useState(false);

  const loadReports = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await integratedReportsAPI.list();
      setReports(data);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Error al cargar el historial de informes integrados');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReports();
  }, []);

  const filteredReports = useMemo(() => {
    let result = [...reports];

    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter((r) => r.name.toLowerCase().includes(q));
    }

    if (dateFrom) {
      const fromTs = new Date(dateFrom).getTime();
      result = result.filter((r) => new Date(r.updated_at).getTime() >= fromTs);
    }

    if (dateTo) {
      const toTs = new Date(dateTo).getTime() + 86400000; // incluye el día completo
      result = result.filter((r) => new Date(r.updated_at).getTime() < toTs);
    }

    if (statusFilter !== 'all') {
      result = result.filter((r) =>
        statusFilter === 'consolidated' ? r.has_consolidated : !r.has_consolidated
      );
    }

    result.sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'name') {
        cmp = a.name.localeCompare(b.name);
      } else if (sortKey === 'section_count') {
        cmp = a.section_count - b.section_count;
      } else {
        cmp = new Date(a[sortKey]).getTime() - new Date(b[sortKey]).getTime();
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });

    return result;
  }, [reports, search, dateFrom, dateTo, statusFilter, sortKey, sortDir]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const startRename = (report: IntegratedReportSummary) => {
    setEditingId(report.id);
    setEditingName(report.name);
  };

  const cancelRename = () => {
    setEditingId(null);
    setEditingName('');
  };

  const saveRename = async (id: string) => {
    const newName = editingName.trim();
    if (!newName) {
      cancelRename();
      return;
    }
    setSavingRename(true);
    try {
      await integratedReportsAPI.update(id, { name: newName });
      setReports((prev) =>
        prev.map((r) => (r.id === id ? { ...r, name: newName, updated_at: new Date().toISOString() } : r))
      );
      cancelRename();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'No se pudo renombrar el informe');
    } finally {
      setSavingRename(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await integratedReportsAPI.remove(deleteTarget.id);
      setReports((prev) => prev.filter((r) => r.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'No se pudo eliminar el informe');
    } finally {
      setDeleting(false);
    }
  };

  const clearFilters = () => {
    setSearch('');
    setDateFrom('');
    setDateTo('');
    setStatusFilter('all');
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleString('es-CO', {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <FileText className="w-8 h-8 text-indigo-600" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Historial de Informes Integrados</h1>
            <p className="text-sm text-gray-500">
              {filteredReports.length} de {reports.length} informe{reports.length !== 1 ? 's' : ''}
            </p>
          </div>
        </div>
        <button
          onClick={() => navigate('/performance/integrated')}
          className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 transition"
        >
          + Nuevo Informe Integrado
        </button>
      </div>

      {/* Filtros */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 mb-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Buscar por nombre..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>
          <div>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
              placeholder="Desde"
            />
          </div>
          <div>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
              placeholder="Hasta"
            />
          </div>
          <div className="flex gap-2">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as any)}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              <option value="all">Todos</option>
              <option value="consolidated">Consolidados</option>
              <option value="draft">Sin consolidar</option>
            </select>
            <button
              onClick={clearFilters}
              className="px-3 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50"
              title="Limpiar filtros"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md flex items-start gap-2">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Tabla */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 text-indigo-600 animate-spin" />
            <span className="ml-2 text-sm text-gray-600">Cargando informes...</span>
          </div>
        ) : filteredReports.length === 0 ? (
          <div className="text-center py-12">
            <FileText className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 text-sm">
              {reports.length === 0
                ? 'Aún no hay informes integrados guardados.'
                : 'No hay informes que coincidan con los filtros aplicados.'}
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th
                  className="text-left px-4 py-3 font-medium text-gray-700 cursor-pointer hover:bg-gray-100"
                  onClick={() => toggleSort('name')}
                >
                  Nombre {sortKey === 'name' && (sortDir === 'asc' ? '↑' : '↓')}
                </th>
                <th
                  className="text-left px-4 py-3 font-medium text-gray-700 cursor-pointer hover:bg-gray-100"
                  onClick={() => toggleSort('section_count')}
                >
                  Secciones {sortKey === 'section_count' && (sortDir === 'asc' ? '↑' : '↓')}
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-700">Estado</th>
                <th
                  className="text-left px-4 py-3 font-medium text-gray-700 cursor-pointer hover:bg-gray-100"
                  onClick={() => toggleSort('created_at')}
                >
                  Creado {sortKey === 'created_at' && (sortDir === 'asc' ? '↑' : '↓')}
                </th>
                <th
                  className="text-left px-4 py-3 font-medium text-gray-700 cursor-pointer hover:bg-gray-100"
                  onClick={() => toggleSort('updated_at')}
                >
                  Modificado {sortKey === 'updated_at' && (sortDir === 'asc' ? '↑' : '↓')}
                </th>
                <th className="text-right px-4 py-3 font-medium text-gray-700">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filteredReports.map((report) => (
                <tr key={report.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-3">
                    {editingId === report.id ? (
                      <div className="flex items-center gap-2">
                        <input
                          type="text"
                          value={editingName}
                          onChange={(e) => setEditingName(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') saveRename(report.id);
                            if (e.key === 'Escape') cancelRename();
                          }}
                          autoFocus
                          className="flex-1 px-2 py-1 border border-indigo-300 rounded text-sm focus:ring-2 focus:ring-indigo-500"
                        />
                        <button
                          onClick={() => saveRename(report.id)}
                          disabled={savingRename}
                          className="p-1 text-green-600 hover:bg-green-50 rounded"
                        >
                          <Check className="w-4 h-4" />
                        </button>
                        <button
                          onClick={cancelRename}
                          className="p-1 text-gray-500 hover:bg-gray-100 rounded"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    ) : (
                      <span className="font-medium text-gray-900">{report.name}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-600">{report.section_count}</td>
                  <td className="px-4 py-3">
                    {report.has_consolidated ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full">
                        <CheckCircle2 className="w-3 h-3" />
                        Consolidado
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full">
                        Borrador
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-600 text-xs">{formatDate(report.created_at)}</td>
                  <td className="px-4 py-3 text-gray-600 text-xs">{formatDate(report.updated_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => navigate(`/performance/integrated/${report.id}`)}
                        className="p-1.5 text-indigo-600 hover:bg-indigo-50 rounded"
                        title="Ver informe"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => startRename(report)}
                        disabled={editingId !== null}
                        className="p-1.5 text-gray-600 hover:bg-gray-100 rounded disabled:opacity-40"
                        title="Renombrar"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                      {user?.role === 'admin' && (
                        <button
                          onClick={() => setDeleteTarget(report)}
                          className="p-1.5 text-red-600 hover:bg-red-50 rounded"
                          title="Eliminar"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modal eliminar */}
      {deleteTarget && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <div className="flex items-start gap-3 mb-4">
              <div className="flex-shrink-0 w-10 h-10 bg-red-100 rounded-full flex items-center justify-center">
                <Trash2 className="w-5 h-5 text-red-600" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Eliminar informe integrado</h3>
                <p className="text-sm text-gray-600 mt-1">
                  ¿Seguro que quieres eliminar <strong>{deleteTarget.name}</strong>? Esta acción no
                  se puede deshacer.
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setDeleteTarget(null)}
                disabled={deleting}
                className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
              >
                Cancelar
              </button>
              <button
                onClick={confirmDelete}
                disabled={deleting}
                className="px-4 py-2 text-sm bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50 flex items-center gap-2"
              >
                {deleting && <Loader2 className="w-4 h-4 animate-spin" />}
                Eliminar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
