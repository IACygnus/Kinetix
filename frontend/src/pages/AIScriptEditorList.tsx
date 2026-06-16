import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Code,
  Loader2,
  AlertCircle,
  Search as SearchIcon,
  FileCode,
  Download,
} from 'lucide-react';
import { aiScriptDesignsAPI, clientsAPI } from '../services/api';
import type { AIScriptDesignSummary } from '../services/api';
import type { ClientInfo } from '../types';

export default function AIScriptEditorList() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [designs, setDesigns] = useState<AIScriptDesignSummary[]>([]);
  const [clients, setClients] = useState<ClientInfo[]>([]);
  const [search, setSearch] = useState('');
  const [clientFilter, setClientFilter] = useState<string>('all');
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const handleDownloadDesign = useCallback(async (designId: string) => {
    setDownloadingId(designId);
    try {
      // HF14b: export-bundle (JMX o ZIP) con naming desde el backend.
      await aiScriptDesignsAPI.exportBundle(designId);
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      const msg =
        detail && typeof detail === 'object'
          ? detail.message || JSON.stringify(detail)
          : detail || e?.message || 'Error al descargar';
      alert(String(msg));
    } finally {
      setDownloadingId(null);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [allDesigns, myClients] = await Promise.all([
          aiScriptDesignsAPI.list({ include_drafts: false }),
          clientsAPI.getMyClients(),
        ]);
        if (cancelled) return;
        // Filtrar solo los que tienen JMX
        setDesigns(allDesigns.filter((d) => d.has_jmx));
        setClients(myClients);
      } catch (e: any) {
        if (!cancelled) setError(e?.response?.data?.detail || e?.message || 'Error');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = designs.filter((d) => {
    if (clientFilter !== 'all' && d.client_id !== clientFilter) return false;
    if (search && !(d.name || '').toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
        <span className="ml-2 text-gray-600">Cargando diseños...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded p-4 text-red-700 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 mt-0.5" />
          <div>{error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Code className="w-7 h-7 text-indigo-600" />
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">Editor IA</h1>
            <p className="text-sm text-gray-500">
              Selecciona un diseño con JMX para editarlo visualmente.
            </p>
          </div>
        </div>
      </div>

      {/* Filtros */}
      <div className="bg-white border border-gray-200 rounded-lg p-3 mb-4 flex items-center gap-3">
        <div className="relative flex-1">
          <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Buscar por nombre..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 text-sm border border-gray-300 rounded-md"
          />
        </div>
        <select
          value={clientFilter}
          onChange={(e) => setClientFilter(e.target.value)}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-md"
        >
          <option value="all">Todos los clientes</option>
          {clients.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      {/* Tabla */}
      {filtered.length === 0 ? (
        <div className="bg-amber-50 border border-amber-200 rounded p-6 text-center">
          <FileCode className="w-12 h-12 text-amber-400 mx-auto mb-2" />
          <p className="text-sm text-amber-800">
            {designs.length === 0
              ? 'No hay diseños con JMX. Crea uno desde el AI Script Designer.'
              : 'Sin resultados con los filtros actuales.'}
          </p>
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-2 text-xs font-semibold text-gray-700">Nombre</th>
                <th className="text-left px-4 py-2 text-xs font-semibold text-gray-700">Cliente</th>
                <th className="text-left px-4 py-2 text-xs font-semibold text-gray-700">Actualizado</th>
                <th className="text-right px-4 py-2 text-xs font-semibold text-gray-700">Acción</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((d) => (
                <tr key={d.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-2 font-medium text-gray-900">{d.name || '(sin nombre)'}</td>
                  <td className="px-4 py-2 text-gray-600">
                    {clients.find((c) => c.id === d.client_id)?.name || '—'}
                  </td>
                  <td className="px-4 py-2 text-gray-500 text-xs">
                    {new Date(d.updated_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <div className="inline-flex items-center gap-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDownloadDesign(d.id);
                        }}
                        disabled={downloadingId === d.id}
                        className="p-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded disabled:opacity-50 disabled:cursor-not-allowed"
                        title="Descargar JMX"
                      >
                        {downloadingId === d.id ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Download className="w-4 h-4" />
                        )}
                      </button>
                      <button
                        onClick={() => navigate(`/ai-script-designer/editor/${d.id}`)}
                        className="inline-flex items-center gap-1.5 px-3 py-1 bg-indigo-600 text-white text-xs font-medium rounded hover:bg-indigo-700"
                      >
                        <Code className="w-3.5 h-3.5" />
                        Editar
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
