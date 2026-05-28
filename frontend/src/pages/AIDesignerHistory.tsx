import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Sparkles,
  Search,
  Eye,
  Trash2,
  AlertCircle,
  Loader2,
  FileCode,
  MessageSquare,
  CheckCircle2,
  X,
  Code,
} from 'lucide-react';
import {
  aiScriptDesignsAPI,
  AIScriptDesignSummary,
  clientsAPI,
} from '../services/api';

type SortKey = 'name' | 'updated_at' | 'created_at' | 'message_count';
type SortDir = 'asc' | 'desc';

interface ClientOption {
  id: string;
  name: string;
}

export default function AIDesignerHistory() {
  const navigate = useNavigate();
  const [designs, setDesigns] = useState<AIScriptDesignSummary[]>([]);
  const [clients, setClients] = useState<ClientOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filtros
  const [search, setSearch] = useState('');
  const [clientFilter, setClientFilter] = useState<string>('all');
  const [includeDrafts, setIncludeDrafts] = useState<boolean>(false);

  // Ordenamiento
  const [sortKey, setSortKey] = useState<SortKey>('updated_at');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  // Delete modal
  const [deleteTarget, setDeleteTarget] = useState<AIScriptDesignSummary | null>(null);
  const [deleting, setDeleting] = useState(false);

  const loadClients = async () => {
    try {
      const data = await clientsAPI.getMyClients();
      setClients(data.map((c) => ({ id: c.id, name: c.name })));
    } catch (e) {
      // No bloqueante: si falla, el filtro por cliente queda vacío
      console.error('Error cargando clientes', e);
    }
  };

  const loadDesigns = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { client_id?: string; include_drafts: boolean } = {
        include_drafts: includeDrafts,
      };
      if (clientFilter !== 'all') {
        params.client_id = clientFilter;
      }
      const data = await aiScriptDesignsAPI.list(params);
      setDesigns(data);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Error al cargar los diseños AI');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadClients();
  }, []);

  useEffect(() => {
    loadDesigns();
  }, [clientFilter, includeDrafts]);

  const clientNameById = useMemo(() => {
    const m = new Map<string, string>();
    clients.forEach((c) => m.set(c.id, c.name));
    return m;
  }, [clients]);

  const filteredDesigns = useMemo(() => {
    let result = [...designs];

    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter((d) => {
        const name = (d.name || '').toLowerCase();
        const fileName = (d.reference_file_name || '').toLowerCase();
        return name.includes(q) || fileName.includes(q);
      });
    }

    result.sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'name') {
        cmp = (a.name || '').localeCompare(b.name || '');
      } else if (sortKey === 'message_count') {
        cmp = a.message_count - b.message_count;
      } else {
        cmp = new Date(a[sortKey]).getTime() - new Date(b[sortKey]).getTime();
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });

    return result;
  }, [designs, search, sortKey, sortDir]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await aiScriptDesignsAPI.remove(deleteTarget.id);
      setDesigns((prev) => prev.filter((d) => d.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'No se pudo eliminar el diseño');
    } finally {
      setDeleting(false);
    }
  };

  const clearFilters = () => {
    setSearch('');
    setClientFilter('all');
    setIncludeDrafts(false);
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

  const fileTypeBadge = (type: string | null) => {
    if (!type) return null;
    const colorMap: Record<string, string> = {
      postman: 'bg-orange-100 text-orange-700',
      openapi: 'bg-blue-100 text-blue-700',
      swagger: 'bg-blue-100 text-blue-700',
      har: 'bg-purple-100 text-purple-700',
      jmx: 'bg-green-100 text-green-700',
      text: 'bg-gray-100 text-gray-600',
    };
    const cls = colorMap[type] || 'bg-gray-100 text-gray-600';
    return (
      <span className={`inline-flex items-center px-1.5 py-0.5 ${cls} text-xs rounded`}>
        {type}
      </span>
    );
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Sparkles className="w-8 h-8 text-indigo-600" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Mis Diseños IA</h1>
            <p className="text-sm text-gray-500">
              {filteredDesigns.length} de {designs.length} diseño{designs.length !== 1 ? 's' : ''}
              {includeDrafts ? ' (incluye borradores)' : ''}
            </p>
          </div>
        </div>
        <button
          onClick={() => navigate('/ai-script-designer')}
          className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 transition flex items-center gap-2"
        >
          <Sparkles className="w-4 h-4" />
          Nuevo Diseño con IA
        </button>
      </div>

      {/* Filtros */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 mb-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Buscar por nombre o archivo..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>
          <div>
            <select
              value={clientFilter}
              onChange={(e) => setClientFilter(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              <option value="all">Todos los clientes</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <label className="flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-md text-sm cursor-pointer hover:bg-gray-50">
            <input
              type="checkbox"
              checked={includeDrafts}
              onChange={(e) => setIncludeDrafts(e.target.checked)}
              className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
            />
            <span>Incluir borradores</span>
          </label>
          <button
            onClick={clearFilters}
            className="px-3 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 flex items-center justify-center gap-2"
            title="Limpiar filtros"
          >
            <X className="w-4 h-4" />
            Limpiar
          </button>
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
            <span className="ml-2 text-sm text-gray-600">Cargando diseños...</span>
          </div>
        ) : filteredDesigns.length === 0 ? (
          <div className="text-center py-12">
            <Sparkles className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 text-sm">
              {designs.length === 0
                ? includeDrafts
                  ? 'Aún no hay diseños AI creados.'
                  : 'No hay diseños guardados. Activa "Incluir borradores" para ver los autosaves.'
                : 'No hay diseños que coincidan con los filtros aplicados.'}
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
                <th className="text-left px-4 py-3 font-medium text-gray-700">Cliente</th>
                <th className="text-left px-4 py-3 font-medium text-gray-700">Estado</th>
                <th
                  className="text-left px-4 py-3 font-medium text-gray-700 cursor-pointer hover:bg-gray-100"
                  onClick={() => toggleSort('message_count')}
                >
                  Mensajes {sortKey === 'message_count' && (sortDir === 'asc' ? '↑' : '↓')}
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-700">JMX</th>
                <th className="text-left px-4 py-3 font-medium text-gray-700">Referencia</th>
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
              {filteredDesigns.map((d) => (
                <tr key={d.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <span className="font-medium text-gray-900">
                      {d.name || <em className="text-gray-400 font-normal">Sin nombre</em>}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    {clientNameById.get(d.client_id) || (
                      <span className="text-gray-400 text-xs">{d.client_id.substring(0, 8)}...</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {d.is_draft ? (
                      <span className="inline-flex items-center px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full">
                        Borrador
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full">
                        <CheckCircle2 className="w-3 h-3" />
                        Guardado
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    <span className="inline-flex items-center gap-1">
                      <MessageSquare className="w-3.5 h-3.5 text-gray-400" />
                      {d.message_count}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {d.has_jmx ? (
                      <span className="inline-flex items-center gap-1 text-green-600">
                        <FileCode className="w-4 h-4" />
                      </span>
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {d.reference_file_name ? (
                      <div className="flex flex-col gap-0.5">
                        <span className="text-xs text-gray-600 truncate max-w-[160px]" title={d.reference_file_name}>
                          {d.reference_file_name}
                        </span>
                        {fileTypeBadge(d.reference_file_type)}
                      </div>
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-600 text-xs">{formatDate(d.updated_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => navigate(`/ai-script-designer?designId=${d.id}`)}
                        className="p-1.5 text-indigo-600 hover:bg-indigo-50 rounded"
                        title="Abrir diseño"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => navigate(`/ai-script-designer/editor/${d.id}`)}
                        disabled={!d.has_jmx}
                        className="p-1.5 text-purple-600 hover:bg-purple-50 rounded disabled:opacity-40 disabled:cursor-not-allowed"
                        title={!d.has_jmx ? 'Sin JMX para editar' : 'Abrir en Editor IA'}
                      >
                        <Code className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => setDeleteTarget(d)}
                        className="p-1.5 text-red-600 hover:bg-red-50 rounded"
                        title="Eliminar"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
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
                <h3 className="text-lg font-semibold text-gray-900">Eliminar diseño AI</h3>
                <p className="text-sm text-gray-600 mt-1">
                  ¿Seguro que quieres eliminar{' '}
                  <strong>{deleteTarget.name || 'este borrador sin nombre'}</strong>? Se perderá la
                  conversación, el JMX generado y el archivo de referencia. Esta acción no se puede
                  deshacer.
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
