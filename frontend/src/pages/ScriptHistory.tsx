/**
 * ScriptHistory — Saved scripts browser with filters.
 * Lists all saved scripts, filterable by client/name/type.
 * Click to open in ScriptDesigner.
 */
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, PenTool, FileText, Loader2 } from 'lucide-react';
import { scriptApi } from '../api/scriptDesignerApi';
import type { Script } from '../api/scriptDesignerApi';
import { clientsAPI } from '../services/api';
import type { ClientInfo } from '../types';

export default function ScriptHistory() {
  const navigate = useNavigate();
  const [scripts, setScripts] = useState<Script[]>([]);
  const [clients, setClients] = useState<ClientInfo[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [filterClientId, setFilterClientId] = useState('');
  const [filterType, setFilterType] = useState('');

  useEffect(() => {
    Promise.all([
      scriptApi.list().then(({ data }) => setScripts(Array.isArray(data) ? data : [])),
      clientsAPI.getMyClients().then(setClients).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  const filtered = scripts.filter(s => {
    const ext = s as any;
    if (searchQuery && !s.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    if (filterClientId && s.client_id !== filterClientId) return false;
    if (filterType && (ext.script_type || '') !== filterType) return false;
    return true;
  });

  const openScript = (id: number) => {
    navigate(`/script-designer/${id}`);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-[#f5a623]" />
      </div>
    );
  }

  return (
    <div className="w-full p-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-2">
        <PenTool className="w-8 h-8 text-[#f5a623]" />
        <h1 className="text-4xl font-bold text-gray-800">Scripts Guardados</h1>
      </div>
      <p className="text-lg text-gray-500 mb-6">
        Todos los scripts de performance guardados. Haz clic en uno para abrirlo en el editor.
      </p>

      {/* Filters */}
      <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-200 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Buscar por nombre..."
              className="w-full pl-10 pr-4 h-12 bg-gray-50 border border-gray-300 rounded-xl text-lg text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-[#f5a623] focus:ring-2 focus:ring-[#f5a623]/20"
            />
          </div>
          <select
            value={filterClientId}
            onChange={e => setFilterClientId(e.target.value)}
            className="h-12 bg-gray-50 border border-gray-300 rounded-xl text-lg text-gray-800 px-4 focus:outline-none focus:border-[#f5a623] focus:ring-2 focus:ring-[#f5a623]/20 appearance-none"
          >
            <option value="">Todos los clientes</option>
            {clients.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <select
            value={filterType}
            onChange={e => setFilterType(e.target.value)}
            className="h-12 bg-gray-50 border border-gray-300 rounded-xl text-lg text-gray-800 px-4 focus:outline-none focus:border-[#f5a623] focus:ring-2 focus:ring-[#f5a623]/20 appearance-none"
          >
            <option value="">Todos los tipos</option>
            <option value="api">API</option>
            <option value="web">Web</option>
            <option value="both">API + Web</option>
          </select>
        </div>
      </div>

      {/* Scripts Table */}
      <div className="bg-white rounded-2xl shadow-lg border border-gray-200 overflow-hidden">
        {filtered.length === 0 ? (
          <div className="text-center py-16 text-lg text-gray-400">
            {scripts.length === 0
              ? 'No hay scripts guardados aun.'
              : 'No se encontraron scripts con los filtros aplicados.'}
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="bg-[#0a1628] text-white">
                <th className="text-left px-6 py-4 text-sm font-semibold uppercase tracking-wider">Nombre</th>
                <th className="text-left px-6 py-4 text-sm font-semibold uppercase tracking-wider">Cliente</th>
                <th className="text-left px-6 py-4 text-sm font-semibold uppercase tracking-wider">Tipo</th>
                <th className="text-left px-6 py-4 text-sm font-semibold uppercase tracking-wider">Origen</th>
                <th className="text-left px-6 py-4 text-sm font-semibold uppercase tracking-wider">Requests</th>
                <th className="text-left px-6 py-4 text-sm font-semibold uppercase tracking-wider">Actualizado</th>
                <th className="text-center px-6 py-4 text-sm font-semibold uppercase tracking-wider">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((script, idx) => {
                const ext = script as any;
                return (
                  <tr
                    key={script.id}
                    className={`border-b border-gray-100 hover:bg-gray-50 cursor-pointer transition-colors ${idx % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}`}
                    onClick={() => openScript(script.id)}
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <FileText className="w-5 h-5 text-[#f5a623] flex-shrink-0" />
                        <span className="text-lg font-medium text-gray-800">{script.name}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-lg text-gray-600">
                      {ext.client_name || 'Sin cliente'}
                    </td>
                    <td className="px-6 py-4">
                      <span className="px-3 py-1 rounded-full text-sm font-semibold bg-blue-50 text-blue-700 uppercase">
                        {ext.script_type || 'api'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-lg text-gray-500 capitalize">
                      {script.origin || 'manual'}
                    </td>
                    <td className="px-6 py-4 text-lg text-gray-600">
                      {script.script_model?.requests?.length || 0}
                    </td>
                    <td className="px-6 py-4 text-lg text-gray-500">
                      {new Date(script.updated_at).toLocaleDateString('es-CO', {
                        day: '2-digit', month: 'short', year: 'numeric',
                      })}
                    </td>
                    <td className="px-6 py-4 text-center">
                      <button
                        onClick={(e) => { e.stopPropagation(); openScript(script.id); }}
                        className="px-4 py-2 bg-[#f5a623] text-[#0a1628] rounded-lg text-sm font-bold hover:bg-[#f5a623]/80 transition-colors"
                      >
                        Abrir
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        <div className="px-6 py-3 bg-gray-50 border-t border-gray-200 text-sm text-gray-500">
          {filtered.length} de {scripts.length} scripts
        </div>
      </div>
    </div>
  );
}
