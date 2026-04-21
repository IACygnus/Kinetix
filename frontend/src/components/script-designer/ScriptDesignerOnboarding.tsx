// frontend/src/components/script-designer/ScriptDesignerOnboarding.tsx
/**
 * Sprint 6 — Modal de onboarding del Script Designer.
 * Flujo: Continuar draft / Cargar existente / Nuevo (cliente → tipo → nombre)
 */
import { useState, useEffect, useRef } from 'react';
import {
  FolderOpen, Plus, Search, ChevronRight, ChevronLeft,
  Plug, Globe, Layers, Clock, Building2, X, Check, Loader2,
  ArrowRight, Edit3
} from 'lucide-react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  if (config.method && config.method !== 'get') {
    const csrfToken = document.cookie
      .split('; ')
      .find((row) => row.startsWith('csrf_token='))
      ?.split('=')[1];
    if (csrfToken) config.headers['X-CSRF-Token'] = csrfToken;
  }
  return config;
});

// ─── Types ──────────────────────────────────────────────────────────────────

type Step = 'start' | 'load-existing' | 'select-client' | 'select-type' | 'name-script';
export type ScriptType = 'api' | 'web' | 'both';

export interface Draft {
  scriptId?: number;
  scriptName: string;
  clientName?: string;
  savedAt: string;
  requestCount: number;
}

interface Client {
  id: string;
  name: string;
}

interface ScriptSummary {
  id: number;
  name: string;
  client_name?: string;
  updated_at: string;
  request_count: number;
  script_type?: string;
}

interface Props {
  onContinueDraft: (draft: Draft) => void;
  onLoadScript: (scriptId: number) => void;
  onNewScript: (params: { clientId?: string; clientName?: string; scriptType: ScriptType; scriptName: string }) => void;
  onClose?: () => void;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

export const DRAFT_KEY = 'kinetix_script_draft';

export function getDraft(): Draft | null {
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'ahora mismo';
  if (mins < 60) return `hace ${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `hace ${hours}h`;
  const days = Math.floor(hours / 24);
  return `hace ${days}d`;
}

// ─── Component ──────────────────────────────────────────────────────────────

export default function ScriptDesignerOnboarding({ onContinueDraft, onLoadScript, onNewScript, onClose }: Props) {
  const [step, setStep] = useState<Step>('start');
  const [draft] = useState<Draft | null>(getDraft);

  // Load existing
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<ScriptSummary[]>([]);
  const [selectedClientFilter, setSelectedClientFilter] = useState('');
  const [loadingSearch, setLoadingSearch] = useState(false);

  // New script
  const [clients, setClients] = useState<Client[]>([]);
  const [selectedClientId, setSelectedClientId] = useState('');
  const [selectedClientName, setSelectedClientName] = useState('');
  const [clientSearch, setClientSearch] = useState('');
  const [scriptType, setScriptType] = useState<ScriptType | null>(null);
  const [scriptName, setScriptName] = useState('');
  const [loadingClients, setLoadingClients] = useState(false);

  const searchRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Load clients on mount
  useEffect(() => {
    const fetchClients = async () => {
      setLoadingClients(true);
      try {
        const { data } = await api.get('/clients/');
        setClients(data.items || data || []);
      } catch {
        setClients([]);
      } finally {
        setLoadingClients(false);
      }
    };
    fetchClients();
  }, []);

  // Debounced search
  useEffect(() => {
    if (step !== 'load-existing') return;
    if (searchRef.current) clearTimeout(searchRef.current);
    searchRef.current = setTimeout(async () => {
      setLoadingSearch(true);
      try {
        const params: Record<string, string> = {};
        if (searchQuery) params.search = searchQuery;
        if (selectedClientFilter) params.client_id = selectedClientFilter;
        const { data } = await api.get('/scripts/', { params });
        setSearchResults(Array.isArray(data) ? data : data.items || []);
      } catch {
        setSearchResults([]);
      } finally {
        setLoadingSearch(false);
      }
    }, 300);
    return () => { if (searchRef.current) clearTimeout(searchRef.current); };
  }, [searchQuery, selectedClientFilter, step]);

  const filteredClients = clients.filter(c =>
    c.name.toLowerCase().includes(clientSearch.toLowerCase())
  );

  const canStartScript = scriptType !== null && scriptName.trim().length > 0;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden">

        {/* Header */}
        <div className="bg-[#0a1628] px-8 py-5 flex items-center justify-between">
          <div>
            <div className="text-white font-bold text-lg">
              sqa<span className="text-[#f5a623]">_</span>
              <span className="font-normal text-gray-400 text-base ml-2">Script Designer</span>
            </div>
            <p className="text-gray-400 text-sm mt-0.5">
              {step === 'start' && '¿Qué deseas hacer?'}
              {step === 'load-existing' && 'Cargar proyecto guardado'}
              {step === 'select-client' && 'Paso 1 de 3 — Seleccionar cliente'}
              {step === 'select-type' && 'Paso 2 de 3 — Tipo de prueba'}
              {step === 'name-script' && 'Paso 3 de 3 — Nombre del diseño'}
            </p>
          </div>
          {onClose && (
            <button onClick={onClose} className="text-gray-500 hover:text-white p-1 rounded-md">
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Step: START */}
        {step === 'start' && (
          <div className="p-8 space-y-3">
            {draft && (
              <button
                onClick={() => onContinueDraft(draft)}
                className="w-full flex items-start gap-4 p-5 rounded-xl border-2 border-[#f5a623] bg-amber-50 hover:bg-amber-100 transition-colors text-left group"
              >
                <div className="w-10 h-10 rounded-full bg-[#f5a623] flex items-center justify-center flex-shrink-0 mt-0.5">
                  <Clock className="w-5 h-5 text-[#0a1628]" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-gray-900 text-sm">Continuar donde lo dejé</p>
                  <p className="text-sm text-gray-600 mt-0.5 truncate">
                    <span className="font-medium">{draft.scriptName}</span>
                    {draft.clientName && <span className="text-gray-400"> · {draft.clientName}</span>}
                  </p>
                  <p className="text-sm text-gray-400 mt-1">
                    {draft.requestCount} requests · {formatRelativeTime(draft.savedAt)}
                  </p>
                </div>
                <ChevronRight className="w-5 h-5 text-[#f5a623] mt-1 group-hover:translate-x-1 transition-transform" />
              </button>
            )}

            <button
              onClick={() => setStep('load-existing')}
              className="w-full flex items-start gap-4 p-5 rounded-xl border border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition-colors text-left group"
            >
              <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                <FolderOpen className="w-5 h-5 text-gray-600" />
              </div>
              <div className="flex-1">
                <p className="font-semibold text-gray-900 text-sm">Cargar proyecto guardado</p>
                <p className="text-sm text-gray-500 mt-0.5">Busca por nombre o filtra por cliente</p>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-300 mt-1 group-hover:translate-x-1 group-hover:text-gray-500 transition-all" />
            </button>

            <button
              onClick={() => setStep('select-client')}
              className="w-full flex items-start gap-4 p-5 rounded-xl border border-gray-200 hover:border-[#0a1628] hover:bg-[#0a1628]/5 transition-colors text-left group"
            >
              <div className="w-10 h-10 rounded-full bg-[#0a1628] flex items-center justify-center flex-shrink-0 mt-0.5">
                <Plus className="w-5 h-5 text-white" />
              </div>
              <div className="flex-1">
                <p className="font-semibold text-gray-900 text-sm">Nuevo diseño</p>
                <p className="text-sm text-gray-500 mt-0.5">Empezar desde cero para un cliente</p>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-300 mt-1 group-hover:translate-x-1 group-hover:text-[#0a1628] transition-all" />
            </button>
          </div>
        )}

        {/* Step: LOAD EXISTING */}
        {step === 'load-existing' && (
          <div className="p-8 space-y-4">
            <div className="flex gap-3">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  placeholder="Buscar scripts..."
                  className="w-full pl-9 pr-4 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0a1628]/20 focus:border-[#0a1628]"
                  autoFocus
                />
                {loadingSearch && (
                  <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 animate-spin" />
                )}
              </div>
              <select
                value={selectedClientFilter}
                onChange={e => setSelectedClientFilter(e.target.value)}
                className="pl-3 pr-8 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0a1628]/20 focus:border-[#0a1628] bg-white"
              >
                <option value="">Todos los clientes</option>
                {clients.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>

            <div className="border border-gray-200 rounded-xl overflow-hidden min-h-[200px] max-h-[320px] overflow-y-auto">
              {searchResults.length === 0 && !loadingSearch && (
                <div className="flex flex-col items-center justify-center h-48 text-gray-400">
                  <Search className="w-8 h-8 mb-2 text-gray-200" />
                  <p className="text-sm">
                    {searchQuery || selectedClientFilter ? 'No se encontraron resultados' : 'Escribe para buscar scripts guardados'}
                  </p>
                </div>
              )}
              {searchResults.map((script, i) => (
                <button
                  key={script.id}
                  onClick={() => onLoadScript(script.id)}
                  className={`w-full flex items-center gap-4 px-5 py-3.5 text-left hover:bg-blue-50 transition-colors ${
                    i > 0 ? 'border-t border-gray-100' : ''
                  }`}
                >
                  <div className="w-8 h-8 rounded-lg bg-gray-100 flex items-center justify-center flex-shrink-0">
                    {script.script_type === 'web' ? (
                      <Globe className="w-4 h-4 text-gray-500" />
                    ) : script.script_type === 'both' ? (
                      <Layers className="w-4 h-4 text-gray-500" />
                    ) : (
                      <Plug className="w-4 h-4 text-gray-500" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 text-sm truncate">{script.name}</p>
                    <p className="text-sm text-gray-500 mt-0.5">
                      {script.client_name && <span className="text-blue-600">{script.client_name} · </span>}
                      {script.request_count} requests · {formatRelativeTime(script.updated_at)}
                    </p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-gray-300 flex-shrink-0" />
                </button>
              ))}
            </div>

            <button
              onClick={() => setStep('start')}
              className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700"
            >
              <ChevronLeft className="w-4 h-4" /> Volver
            </button>
          </div>
        )}

        {/* Step: SELECT CLIENT */}
        {step === 'select-client' && (
          <div className="p-8 space-y-5">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-3">
                ¿Para qué cliente es este diseño?
              </label>
              <div className="relative mb-3">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  value={clientSearch}
                  onChange={e => setClientSearch(e.target.value)}
                  placeholder="Buscar cliente..."
                  className="w-full pl-9 pr-4 py-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0a1628]/20 focus:border-[#0a1628]"
                  autoFocus
                />
              </div>
              <div className="border border-gray-200 rounded-xl overflow-hidden max-h-52 overflow-y-auto">
                <button
                  onClick={() => { setSelectedClientId(''); setSelectedClientName(''); }}
                  className={`w-full flex items-center gap-3 px-4 py-3 text-left text-sm border-b border-gray-100 hover:bg-gray-50 ${
                    selectedClientId === '' ? 'bg-blue-50' : ''
                  }`}
                >
                  <div className="w-7 h-7 rounded-full bg-gray-200 flex items-center justify-center flex-shrink-0">
                    <span className="text-sm text-gray-500">–</span>
                  </div>
                  <span className="text-sm text-gray-500">Sin cliente asignado</span>
                  {selectedClientId === '' && <Check className="w-4 h-4 text-blue-600 ml-auto" />}
                </button>
                {loadingClients ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
                  </div>
                ) : (
                  filteredClients.map((client, i) => (
                    <button
                      key={client.id}
                      onClick={() => { setSelectedClientId(client.id); setSelectedClientName(client.name); }}
                      className={`w-full flex items-center gap-3 px-4 py-3 text-left text-sm hover:bg-gray-50 ${
                        i > 0 ? 'border-t border-gray-100' : ''
                      } ${selectedClientId === client.id ? 'bg-blue-50' : ''}`}
                    >
                      <div className="w-7 h-7 rounded-full bg-[#0a1628] flex items-center justify-center flex-shrink-0">
                        <span className="text-sm font-bold text-white">{client.name[0]?.toUpperCase()}</span>
                      </div>
                      <span className="text-sm text-gray-800 font-medium">{client.name}</span>
                      {selectedClientId === client.id && <Check className="w-4 h-4 text-blue-600 ml-auto" />}
                    </button>
                  ))
                )}
              </div>
            </div>
            <div className="flex justify-between items-center">
              <button onClick={() => setStep('start')} className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700">
                <ChevronLeft className="w-4 h-4" /> Volver
              </button>
              <button
                onClick={() => setStep('select-type')}
                className="flex items-center gap-2 px-5 py-2.5 bg-[#0a1628] text-white text-sm font-medium rounded-lg hover:bg-[#1a2a48]"
              >
                Siguiente <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Step: SELECT TYPE */}
        {step === 'select-type' && (
          <div className="p-8 space-y-5">
            {selectedClientName && (
              <div className="flex items-center gap-2 text-sm text-gray-500 bg-gray-50 px-3 py-2 rounded-lg">
                <Building2 className="w-4 h-4" />
                <span>Cliente: <strong className="text-gray-800">{selectedClientName}</strong></span>
              </div>
            )}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-3">
                ¿Qué tipo de prueba vas a diseñar?
              </label>
              <div className="grid grid-cols-3 gap-3">
                {([
                  { type: 'api' as ScriptType, icon: <Plug className="w-6 h-6" />, label: 'API / Servicios', sub: 'REST · SOAP · GraphQL\nPostman · Swagger · WSDL', color: 'blue' },
                  { type: 'web' as ScriptType, icon: <Globe className="w-6 h-6" />, label: 'Flujo Web', sub: 'Navegación browser\nGrabación Chrome · HAR', color: 'green' },
                  { type: 'both' as ScriptType, icon: <Layers className="w-6 h-6" />, label: 'Ambos', sub: 'APIs + interacción\nweb simultáneos', color: 'purple' },
                ] as const).map(({ type, icon, label, sub, color }) => (
                  <button
                    key={type}
                    onClick={() => setScriptType(type)}
                    className={`relative flex flex-col items-center text-center gap-3 p-5 rounded-xl border-2 transition-all ${
                      scriptType === type
                        ? color === 'blue' ? 'border-blue-500 bg-blue-50' :
                          color === 'green' ? 'border-green-500 bg-green-50' :
                          'border-purple-500 bg-purple-50'
                        : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                      scriptType === type
                        ? color === 'blue' ? 'bg-blue-500 text-white' :
                          color === 'green' ? 'bg-green-500 text-white' :
                          'bg-purple-500 text-white'
                        : 'bg-gray-100 text-gray-500'
                    }`}>
                      {icon}
                    </div>
                    <div>
                      <p className={`font-semibold text-sm ${scriptType === type ? 'text-gray-900' : 'text-gray-700'}`}>{label}</p>
                      <p className="text-sm text-gray-400 mt-1 whitespace-pre-line leading-relaxed">{sub}</p>
                    </div>
                    {scriptType === type && (
                      <div className={`absolute top-2 right-2 w-5 h-5 rounded-full flex items-center justify-center ${
                        color === 'blue' ? 'bg-blue-500' : color === 'green' ? 'bg-green-500' : 'bg-purple-500'
                      }`}>
                        <Check className="w-3 h-3 text-white" />
                      </div>
                    )}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex justify-between items-center">
              <button onClick={() => setStep('select-client')} className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700">
                <ChevronLeft className="w-4 h-4" /> Volver
              </button>
              <button
                onClick={() => setStep('name-script')}
                disabled={!scriptType}
                className="flex items-center gap-2 px-5 py-2.5 bg-[#0a1628] text-white text-sm font-medium rounded-lg hover:bg-[#1a2a48] disabled:opacity-40"
              >
                Siguiente <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Step: NAME SCRIPT */}
        {step === 'name-script' && (
          <div className="p-8 space-y-5">
            <div className="flex gap-2 flex-wrap">
              {selectedClientName && (
                <span className="text-sm bg-gray-100 text-gray-600 px-2.5 py-1 rounded-full flex items-center gap-1">
                  <Building2 className="w-3 h-3" /> {selectedClientName}
                </span>
              )}
              {scriptType && (
                <span className="text-sm bg-gray-100 text-gray-600 px-2.5 py-1 rounded-full flex items-center gap-1">
                  {scriptType === 'api' ? <Plug className="w-3 h-3" /> : scriptType === 'web' ? <Globe className="w-3 h-3" /> : <Layers className="w-3 h-3" />}
                  {scriptType === 'api' ? 'API / Servicios' : scriptType === 'web' ? 'Flujo Web' : 'API + Web'}
                </span>
              )}
            </div>
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                Nombre del diseño
              </label>
              <input
                type="text"
                value={scriptName}
                onChange={e => setScriptName(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && canStartScript && onNewScript({ clientId: selectedClientId || undefined, clientName: selectedClientName || undefined, scriptType: scriptType!, scriptName })}
                placeholder="ej: Login Flow, Checkout Test, API de Pagos..."
                className="w-full px-4 py-3.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0a1628]/20 focus:border-[#0a1628]"
                autoFocus
                maxLength={100}
              />
              <p className="text-sm text-gray-400 mt-1.5">Presiona Enter para comenzar</p>
            </div>
            <div className="flex justify-between items-center">
              <button onClick={() => setStep('select-type')} className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700">
                <ChevronLeft className="w-4 h-4" /> Volver
              </button>
              <button
                onClick={() => canStartScript && onNewScript({
                  clientId: selectedClientId || undefined,
                  clientName: selectedClientName || undefined,
                  scriptType: scriptType!,
                  scriptName,
                })}
                disabled={!canStartScript}
                className="flex items-center gap-2 px-6 py-2.5 bg-[#f5a623] text-[#0a1628] text-sm font-bold rounded-lg hover:bg-[#e09520] disabled:opacity-40 transition-colors"
              >
                <Edit3 className="w-4 h-4" /> Comenzar diseño
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
