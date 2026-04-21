// frontend/src/pages/ScriptDesigner.tsx
/**
 * Sprint 6 — Script Designer with Onboarding, Draft persistence, Clear, refined UI
 */
import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { v4 as uuidv4 } from 'uuid';
import {
  ArrowLeft, FileDown, Save, Plus, FolderOpen, Loader2, Check,
  AlertCircle, FlaskConical, Brain, Bug, FileUp, Layers, Trash2, Brackets
} from 'lucide-react';
import {
  scriptApi, Script, ScriptModel, ScriptRequest, ScriptVariableModel,
  executionApi, AICorrelateResult, AIDebugResult,
  dataFileApi, DataFile,
} from '../api/scriptDesignerApi';
import RequestTable from '../components/script-designer/RequestTable';
import RequestEditor from '../components/script-designer/RequestEditor';
import ImportModal from '../components/script-designer/ImportModal';
import DataFileManager from '../components/script-designer/DataFileManager';
import VariableManager, { scanVariablesFromModel } from '../components/script-designer/VariableManager';
import type { ScriptVariable } from '../components/script-designer/VariableManager';
// SmokeResultModal removed — results now go to ExecutionHistoryPanel
import ExecutionHistoryPanel, { useExecutionHistory } from '../components/script-designer/ExecutionHistoryPanel';
import type { RequestDetail } from '../components/script-designer/JMeterResultDetail';
import ScriptDesignerOnboarding, { DRAFT_KEY } from '../components/script-designer/ScriptDesignerOnboarding';
import type { ScriptType } from '../components/script-designer/ScriptDesignerOnboarding';

const EMPTY_SCRIPT_MODEL: ScriptModel = {
  requests: [],
  variables: [],
  data_files: [],
  protocol: 'http',
};

const EMPTY_REQUEST: Omit<ScriptRequest, 'id' | 'order'> = {
  name: 'New Request',
  protocol: 'http',
  method: 'GET',
  url: '',
  headers: {},
  body: '',
  body_type: 'json',
  params: {},
  assertions: [],
  think_time_ms: 0,
  extractors: [],
};

export default function ScriptDesigner() {
  const { scriptId } = useParams<{ scriptId?: string }>();
  const navigate = useNavigate();

  const [script, setScript] = useState<Script | null>(null);
  const [scriptModel, setScriptModel] = useState<ScriptModel>(EMPTY_SCRIPT_MODEL);
  const [scriptName, setScriptName] = useState('New Script');
  const [scriptClientId, setScriptClientId] = useState('');
  const [scriptClientName, setScriptClientName] = useState('');
  const [, setScriptTypeVal] = useState<ScriptType>('api');
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null);
  const [showImportModal, setShowImportModal] = useState(false);
  const [showDataFiles, setShowDataFiles] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saved' | 'error'>('idle');
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  // Onboarding
  const [showOnboarding, setShowOnboarding] = useState(false);

  // Sprint 7 — Variable Manager
  const [leftTab, setLeftTab] = useState<'requests' | 'variables'>('requests');
  const [dataFilesList, setDataFilesList] = useState<DataFile[]>([]);

  // Sprint 2 — Smoke Test + AI states
  const [runningSmoke, setRunningSmoke] = useState(false);

  const [aiCorrelateResult, setAICorrelateResult] = useState<AICorrelateResult | null>(null);
  const [showAICorrelate, setShowAICorrelate] = useState(false);
  const [runningAICorrelate, setRunningAICorrelate] = useState(false);

  const [aiDebugResult, setAIDebugResult] = useState<AIDebugResult | null>(null);
  const [showAIDebug, setShowAIDebug] = useState(false);
  const [runningAIDebug, setRunningAIDebug] = useState(false);

  // Sprint 7.2 — Run single request result (shown in right panel)
  const [runResult, setRunResult] = useState<any>(null);
  const [runResultRequestId, setRunResultRequestId] = useState<string | null>(null);
  const [runningRequestId, setRunningRequestId] = useState<string | null>(null);
  // Sprint 7.8 — Map of all run results per request (for extractor preview)
  const [runResults, setRunResults] = useState<Record<string, any>>({});

  // Sprint 7.5 — Execution history panel
  const { entries: historyEntries, addEntry: addHistoryEntry, clearHistory } = useExecutionHistory();

  // Load script or show onboarding
  useEffect(() => {
    if (scriptId && scriptId !== 'new') {
      setLoading(true);
      scriptApi.get(parseInt(scriptId))
        .then(({ data }) => {
          setScript(data);
          setScriptModel(data.script_model || EMPTY_SCRIPT_MODEL);
          setScriptName(data.name);
          if (data.script_model?.requests?.length > 0) {
            setSelectedRequestId(data.script_model.requests[0].id);
          }
        })
        .catch(() => navigate('/script-designer'))
        .finally(() => setLoading(false));
    } else {
      setShowOnboarding(true);
    }
  }, [scriptId]);

  // ─── Draft persistence (Task 3) ──────────────────────────────────────────
  useEffect(() => {
    if (scriptModel.requests.length === 0) return;

    const draft = {
      scriptId: script?.id,
      scriptName: scriptName || 'Sin nombre',
      clientId: scriptClientId,
      clientName: scriptClientName,
      savedAt: new Date().toISOString(),
      requestCount: Math.min(scriptModel.requests.length, 100),
      scriptModel: scriptModel.requests.length > 100
        ? { ...scriptModel, requests: scriptModel.requests.slice(0, 100), _truncated: true }
        : scriptModel,
    };
    localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
  }, [scriptModel, scriptName, script?.id, scriptClientId, scriptClientName]);

  // ─── Sprint 7: load data files for Variable Manager ──────────────────────
  useEffect(() => {
    if (script?.id) {
      dataFileApi.listByScript(script.id)
        .then(({ data }) => setDataFilesList(data))
        .catch(() => setDataFilesList([]));
    }
  }, [script?.id, showDataFiles]);

  // ─── Onboarding handlers ─────────────────────────────────────────────────
  const handleContinueDraft = useCallback((draft: any) => {
    setShowOnboarding(false);
    if (draft.scriptModel) setScriptModel(draft.scriptModel);
    if (draft.scriptName) setScriptName(draft.scriptName);
    if (draft.clientName) setScriptClientName(draft.clientName);
    if (draft.clientId) setScriptClientId(draft.clientId);
    if (draft.scriptId) {
      navigate(`/script-designer/${draft.scriptId}`, { replace: true });
    }
    if (draft.scriptModel?.requests?.length > 0) {
      setSelectedRequestId(draft.scriptModel.requests[0].id);
    }
  }, [navigate]);

  const handleLoadScript = useCallback((id: number) => {
    setShowOnboarding(false);
    navigate(`/script-designer/${id}`, { replace: true });
  }, [navigate]);

  const handleNewScript = useCallback((params: { clientId?: string; clientName?: string; scriptType: ScriptType; scriptName: string }) => {
    setShowOnboarding(false);
    setScriptName(params.scriptName);
    setScriptClientId(params.clientId || '');
    setScriptClientName(params.clientName || '');
    setScriptTypeVal(params.scriptType);
    setScriptModel(EMPTY_SCRIPT_MODEL);
    setScript(null);
    setSelectedRequestId(null);
  }, []);

  const selectedRequest = scriptModel.requests.find(r => r.id === selectedRequestId) || null;

  const addRequest = useCallback(() => {
    const newReq: ScriptRequest = {
      ...EMPTY_REQUEST,
      id: uuidv4(),
      order: scriptModel.requests.length,
    };
    setScriptModel(prev => ({
      ...prev,
      requests: [...prev.requests, newReq],
    }));
    setSelectedRequestId(newReq.id);
  }, [scriptModel.requests.length]);

  const updateRequest = useCallback((updatedReq: ScriptRequest) => {
    setScriptModel(prev => {
      const newRequests = prev.requests.map(r => r.id === updatedReq.id ? updatedReq : r);
      return { ...prev, requests: newRequests };
    });
    // Sync extractor variables when a request is updated
    setScriptModel(prev => {
      const extractorVars: string[] = [];
      prev.requests.forEach(req => {
        (req.extractors || []).forEach(ext => {
          if (ext.variable_name) extractorVars.push(ext.variable_name);
        });
      });
      const currentVars: ScriptVariableModel[] = prev.variables || [];
      const existingNames = currentVars.map(v => v.name);
      const newExtVars: ScriptVariableModel[] = extractorVars
        .filter(name => !existingNames.includes(name))
        .map(name => ({ name, value: '', type: 'extractor' as const, source_hint: 'Definida en Extractors', default_value: '' }));
      const updatedVars = currentVars.map(v =>
        v.type === 'extractor' && !extractorVars.includes(v.name) ? { ...v, type: 'manual' as const } : v
      );
      if (newExtVars.length === 0 && updatedVars.every((v, i) => v === currentVars[i])) return prev;
      return { ...prev, variables: [...updatedVars, ...newExtVars] };
    });
  }, []);

  const deleteRequest = useCallback((requestId: string) => {
    setScriptModel(prev => {
      const newRequests = prev.requests
        .filter(r => r.id !== requestId)
        .map((r, idx) => ({ ...r, order: idx }));
      return { ...prev, requests: newRequests };
    });
    setSelectedRequestId(prev => prev === requestId ? null : prev);
  }, []);

  const reorderRequests = useCallback((newOrder: ScriptRequest[]) => {
    setScriptModel(prev => ({
      ...prev,
      requests: newOrder.map((r, idx) => ({ ...r, order: idx })),
    }));
  }, []);

  const handleImport = useCallback((importedModel: ScriptModel, _source: string) => {
    // Ensure imported variables have proper type
    let importedVars = importedModel.variables || [];
    importedVars = importedVars.map(v => ({
      ...v,
      type: v.type || 'imported',
      source_hint: v.source_hint || (v.source ? `Importada de: ${v.source}` : 'Detectada al importar'),
    }));

    // If no variables defined, scan the imported model for them
    if (importedVars.length === 0) {
      const scanned = scanVariablesFromModel(importedModel);
      importedVars = scanned.map(name => ({
        name,
        value: '',
        type: 'imported' as const,
        source_hint: 'Detectada al importar',
      }));
    }

    setScriptModel(prev => {
      // Merge variables: keep existing, add new from import
      const existingNames = (prev.variables || []).map(v => v.name);
      const newVars = importedVars.filter(v => !existingNames.includes(v.name));
      return {
        ...importedModel,
        variables: [...(prev.variables || []), ...newVars],
        requests: [
          ...prev.requests,
          ...importedModel.requests.map((r, idx) => ({
            ...r,
            order: prev.requests.length + idx,
          })),
        ],
      };
    });
    setShowImportModal(false);
    if (importedModel.requests.length > 0) {
      setSelectedRequestId(importedModel.requests[0].id);
    }
  }, []);

  const handleClearAll = useCallback(() => {
    setScriptModel(prev => ({ ...prev, requests: [] }));
    setSelectedRequestId(null);
    setShowClearConfirm(false);
    localStorage.removeItem(DRAFT_KEY);
  }, []);

  const saveScript = useCallback(async () => {
    setSaving(true);
    setSaveStatus('idle');
    try {
      if (script) {
        const { data } = await scriptApi.update(script.id, {
          name: scriptName,
          script_model: scriptModel,
        });
        setScript(data);
      } else {
        const { data } = await scriptApi.create({
          name: scriptName,
          script_model: scriptModel,
          origin: 'manual',
        });
        setScript(data);
        navigate(`/script-designer/${data.id}`, { replace: true });
      }
      setSaveStatus('saved');
      localStorage.removeItem(DRAFT_KEY);
      setTimeout(() => setSaveStatus('idle'), 3000);
    } catch {
      setSaveStatus('error');
    } finally {
      setSaving(false);
    }
  }, [script, scriptName, scriptModel, navigate]);

  const exportJMX = useCallback(async () => {
    if (!script) return;
    try {
      const { data } = await scriptApi.exportJMX(script.id);
      const url = window.URL.createObjectURL(new Blob([data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${scriptName.replace(/\s+/g, '_')}.jmx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      alert('Error exporting JMX');
    }
  }, [script, scriptName]);

  // ─── Sprint 7.2 — Run single request ────────────────────────────────────────
  const handleRunSingle = useCallback(async (requestId: string) => {
    const req = scriptModel.requests.find(r => r.id === requestId);
    if (!req) return;

    // Validate URL before executing
    const url = req.url || '';
    if (!url) {
      setRunResult({ success: false, status_code: null, duration_ms: 0, error: 'La URL esta vacia' });
      setRunResultRequestId(requestId);
      setSelectedRequestId(requestId);
      return;
    }

    setRunningRequestId(requestId);
    setSelectedRequestId(requestId);
    try {
      const csrfToken = document.cookie.match(/csrf_token=([^;]+)/)?.[1] || '';
      // Send FULL variables array (same format VariableEngine expects)
      const variablesArray = (scriptModel.variables || []).map(v => ({
        name: v.name,
        value: v.value || '',
        source: v.type || 'manual',
      }));
      // Inject extracted variables from previous run results (for chaining requests)
      Object.values(runResults).forEach((prevResult: any) => {
        const extracted = prevResult?.extracted_variables;
        if (extracted && typeof extracted === 'object') {
          Object.entries(extracted).forEach(([name, value]) => {
            if (name && value) {
              variablesArray.push({ name, value: String(value), source: 'extractor' });
            }
          });
        }
      });
      const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';
      const res = await fetch(`${apiBase}/executions/run-single`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
        body: JSON.stringify({
          request: req,
          variables: variablesArray,
          data_files: scriptModel.data_files || [],
        }),
      });

      // Handle non-JSON responses (e.g. HTML error pages)
      const contentType = res.headers.get('content-type') || '';
      if (!contentType.includes('application/json')) {
        const text = await res.text();
        setRunResult({
          success: false,
          status_code: null,
          duration_ms: 0,
          resolved_url: url,
          response_headers: {},
          response_body: '',
          error: `Error del servidor (${res.status}): El endpoint /executions/run-single no respondio JSON. Verifica que el backend este corriendo. Respuesta: ${text.slice(0, 200)}`,
        });
        setRunResultRequestId(requestId);
        return;
      }

      const data = await res.json();
      setRunResult(data);
      setRunResultRequestId(requestId);
      setRunResults(prev => ({ ...prev, [requestId]: data }));
      // Add to execution history panel (include request name for tree display)
      addHistoryEntry({
        type: 'single',
        duration_ms: data.duration_ms || 0,
        success: data.success ?? false,
        result: { ...data, name: data.name || req.name } as RequestDetail,
      });
    } catch (err: any) {
      setRunResult({
        success: false,
        status_code: null,
        duration_ms: 0,
        resolved_url: url,
        response_headers: {},
        response_body: '',
        error: `Error de red: ${err.message}. Verifica que el backend este corriendo en http://localhost:8001`,
      });
      setRunResultRequestId(requestId);
    } finally {
      setRunningRequestId(null);
    }
  }, [scriptModel, addHistoryEntry]);

  // ─── Sprint 2 Handlers ──────────────────────────────────────────────────────

  const handleSmokeTest = useCallback(async () => {
    if (scriptModel.requests.length === 0) { alert('No hay requests para ejecutar'); return; }
    setRunningSmoke(true);
    try {
      // Enviar el script_model actual del editor (tiene prioridad sobre el guardado en BD)
      const { data } = await executionApi.smokeTest(script?.id, undefined, scriptModel);

      // Adaptar resultados para el historial
      const smokeResults: RequestDetail[] = (data.request_details || []).map((d: any) => ({
        name: d.name,
        resolved_url: d.resolved_url || d.url || '',
        method: d.method || '',
        status_code: d.status_code,
        duration_ms: d.duration_ms || d.elapsed_ms || 0,
        elapsed_ms: d.elapsed_ms,
        success: d.success,
        failure_message: d.failure_message,
        bytes: d.bytes,
        error: d.success ? null : d.failure_message,
        petition_text: d.petition_text || '',
        sent_headers: d.sent_headers || '',
        sent_body: d.sent_body || '',
        response_body: d.response_body || '',
        response_headers: d.response_headers || {},
        response_headers_raw: d.response_headers_raw || '',
        assertion_failures: d.assertion_failures || [],
      }));

      // Add to execution history panel (no modal — results go to panel only)
      addHistoryEntry({
        type: 'smoke',
        duration_ms: data.duration_ms || 0,
        success: data.failed_requests === 0,
        results: smokeResults,
        total: data.total_requests,
        passed: data.passed_requests,
        failed: data.failed_requests,
      });
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error running smoke test');
    } finally { setRunningSmoke(false); }
  }, [script, scriptModel, addHistoryEntry]);

  const handleAICorrelate = useCallback(async () => {
    if (!script) { alert('Save the script first'); return; }
    setRunningAICorrelate(true);
    try {
      const { data } = await executionApi.aiCorrelate(script.id);
      setAICorrelateResult(data);
      setShowAICorrelate(true);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error during AI analysis');
    } finally { setRunningAICorrelate(false); }
  }, [script]);

  const handleAIDebug = useCallback(async () => {
    if (!script) { alert('Save the script first'); return; }
    setRunningAIDebug(true);
    try {
      const { data } = await executionApi.aiDebug(script.id);
      setAIDebugResult(data);
      setShowAIDebug(true);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error during AI debug');
    } finally { setRunningAIDebug(false); }
  }, [script]);

  const applyAICorrelations = useCallback((correlations: AICorrelateResult['correlations']) => {
    setScriptModel(prev => {
      const newRequests = [...prev.requests];
      correlations.forEach(corr => {
        const reqIndex = corr.extract_from_request;
        if (reqIndex >= 0 && reqIndex < newRequests.length) {
          const req = { ...newRequests[reqIndex] };
          const alreadyExists = req.extractors.some(e => e.variable_name === corr.variable_name);
          if (!alreadyExists) {
            req.extractors = [...req.extractors, {
              variable_name: corr.variable_name,
              extract_from: corr.extract_from,
              regex: corr.regex,
              match_no: corr.match_no,
              default_value: corr.default_value,
              header_name: corr.header_name || '',
            }];
            newRequests[reqIndex] = req;
          }
        }
      });
      return { ...prev, requests: newRequests };
    });
    setShowAICorrelate(false);
  }, []);

  const applyAIDebug = useCallback((ordersToRemove: number[]) => {
    setScriptModel(prev => {
      const newRequests = prev.requests
        .filter(r => !ordersToRemove.includes(r.order))
        .map((r, idx) => ({ ...r, order: idx }));
      return { ...prev, requests: newRequests };
    });
    setShowAIDebug(false);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-8 h-8 animate-spin text-[#f5a623]" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-2rem)]">

      {/* ─── Onboarding overlay ──────────────────────────────────────── */}
      {showOnboarding && (
        <ScriptDesignerOnboarding
          onContinueDraft={handleContinueDraft}
          onLoadScript={handleLoadScript}
          onNewScript={handleNewScript}
          onClose={() => setShowOnboarding(false)}
        />
      )}

      {/* ─── Header Bar ──────────────────────────────────────────────── */}
      <div className="bg-gradient-to-r from-[#0a1628] to-[#162040] px-5 h-14 flex items-center justify-between rounded-t-xl shadow-lg flex-shrink-0">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate(-1)}
            className="text-slate-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <input
            type="text"
            value={scriptName}
            onChange={e => setScriptName(e.target.value)}
            className="text-lg font-bold text-white bg-transparent border-0 border-b-2 border-transparent hover:border-slate-500 focus:border-[#f5a623] focus:outline-none px-1 py-1 min-w-[18rem] placeholder-slate-500"
            placeholder="Script name..."
          />
          {saveStatus === 'saved' && (
            <span className="text-green-400 text-sm flex items-center gap-1 font-medium">
              <Check className="w-4 h-4" /> Saved
            </span>
          )}
          {saveStatus === 'error' && (
            <span className="text-red-400 text-sm flex items-center gap-1 font-medium">
              <AlertCircle className="w-4 h-4" /> Error
            </span>
          )}
        </div>
      </div>

      {/* ─── Toolbar ─────────────────────────────────────────────────── */}
      <div className="bg-white border-b border-gray-200 px-5 h-14 flex items-center justify-between flex-shrink-0">
        {/* Left: Import + AI groups */}
        <div className="flex items-center gap-2">
          {/* Load + Import group */}
          <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
            <button
              onClick={() => setShowOnboarding(true)}
              className="px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-white hover:shadow-sm rounded-md transition-all flex items-center gap-1.5"
            >
              <Layers className="w-4 h-4 text-[#f5a623]" /> Scripts Guardados
            </button>
            <button
              onClick={() => setShowImportModal(true)}
              className="px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-white hover:shadow-sm rounded-md transition-all flex items-center gap-1.5"
            >
              <FileUp className="w-4 h-4 text-[#f5a623]" /> Import
            </button>
            <button
              onClick={() => setShowDataFiles(v => !v)}
              className={`px-3 py-1.5 text-sm font-medium rounded-md flex items-center gap-1.5 transition-all ${
                showDataFiles ? 'bg-white shadow-sm text-blue-700' : 'text-gray-700 hover:bg-white hover:shadow-sm'
              }`}
            >
              <FolderOpen className="w-4 h-4" /> Data Files
            </button>
          </div>

          {/* Separator */}
          <div className="w-px h-5 bg-gray-300" />

          {/* AI & Test group */}
          <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
            <button
              onClick={handleSmokeTest}
              disabled={runningSmoke || scriptModel.requests.length === 0}
              className="px-3 py-1.5 text-sm font-medium text-emerald-700 hover:bg-white hover:shadow-sm rounded-md flex items-center gap-1.5 disabled:opacity-40 transition-all"
            >
              {runningSmoke ? <Loader2 className="w-4 h-4 animate-spin" /> : <FlaskConical className="w-4 h-4" />}
              Smoke
            </button>
            <button
              onClick={handleAICorrelate}
              disabled={runningAICorrelate || !script}
              className="px-3 py-1.5 text-sm font-medium text-purple-700 hover:bg-white hover:shadow-sm rounded-md flex items-center gap-1.5 disabled:opacity-40 transition-all"
            >
              {runningAICorrelate ? <Loader2 className="w-4 h-4 animate-spin" /> : <Brain className="w-4 h-4" />}
              Correlate
            </button>
            <button
              onClick={handleAIDebug}
              disabled={runningAIDebug || !script}
              className="px-3 py-1.5 text-sm font-medium text-orange-700 hover:bg-white hover:shadow-sm rounded-md flex items-center gap-1.5 disabled:opacity-40 transition-all"
            >
              {runningAIDebug ? <Loader2 className="w-4 h-4 animate-spin" /> : <Bug className="w-4 h-4" />}
              Debug
            </button>
          </div>
        </div>

        {/* Right: Clear + Export + Save */}
        <div className="flex items-center gap-2">
          {/* Clear button (Task 4) */}
          {scriptModel.requests.length > 0 && !showClearConfirm && (
            <button
              onClick={() => setShowClearConfirm(true)}
              className="px-3 py-1.5 text-sm font-medium border border-red-200 text-red-500 rounded-lg hover:bg-red-50 flex items-center gap-1.5 transition-colors"
            >
              <Trash2 className="w-4 h-4" /> Limpiar
            </button>
          )}
          {showClearConfirm && (
            <div className="flex items-center gap-2 bg-red-50 border border-red-200 rounded-lg px-3 py-1.5">
              <span className="text-sm text-red-700">¿Eliminar {scriptModel.requests.length} requests?</span>
              <button
                onClick={handleClearAll}
                className="px-2.5 py-1 text-sm font-semibold bg-red-500 text-white rounded hover:bg-red-600"
              >
                Sí, limpiar
              </button>
              <button
                onClick={() => setShowClearConfirm(false)}
                className="px-2.5 py-1 text-sm text-gray-600 hover:text-gray-900"
              >
                Cancelar
              </button>
            </div>
          )}

          {script && (
            <button
              onClick={exportJMX}
              className="px-3 py-1.5 text-sm font-medium border border-gray-300 rounded-lg hover:bg-gray-50 flex items-center gap-1.5 text-gray-700 transition-colors"
            >
              <FileDown className="w-4 h-4" /> JMX
            </button>
          )}
          <button
            onClick={saveScript}
            disabled={saving}
            className="px-5 py-1.5 text-sm font-semibold bg-[#0a1628] text-white rounded-lg hover:bg-[#1a2a48] disabled:opacity-50 flex items-center gap-2 shadow-sm transition-all"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            {saving ? 'Saving...' : 'Guardar'}
          </button>
        </div>
      </div>

      {/* Data Files Panel */}
      {showDataFiles && script && (
        <div className="border-b border-gray-200 bg-white px-6 py-4 flex-shrink-0">
          <DataFileManager scriptId={script.id} />
        </div>
      )}

      {/* ─── Main Layout ─────────────────────────────────────────────── */}
      <div className="flex flex-col flex-1 overflow-hidden bg-white rounded-b-xl">
        <div className="flex flex-1 overflow-hidden">
        {/* Left: Request list / Variables tabs */}
        <div className="w-80 flex-shrink-0 border-r border-gray-200 flex flex-col bg-gray-50/50">
          {/* Tab switcher */}
          <div className="flex border-b border-gray-200 bg-white">
            <button
              onClick={() => setLeftTab('requests')}
              className={`flex-1 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors flex items-center justify-center gap-1.5 ${
                leftTab === 'requests'
                  ? 'border-[#0a1628] text-[#0a1628]'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <Layers className="w-4 h-4 text-[#f5a623]" />
              Requests ({scriptModel.requests.length})
            </button>
            <button
              onClick={() => setLeftTab('variables')}
              className={`flex-1 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors flex items-center justify-center gap-1.5 ${
                leftTab === 'variables'
                  ? 'border-[#0a1628] text-[#0a1628]'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <Brackets className="w-4 h-4 text-purple-500" />
              Variables ({(scriptModel.variables || []).filter(v => v.type !== 'builtin').length})
            </button>
          </div>

          {leftTab === 'requests' && (
            <>
              <div className="px-4 py-2 border-b border-gray-200 flex items-center justify-end bg-white">
                <button
                  onClick={addRequest}
                  className="text-[#f5a623] hover:text-[#e6951e] text-sm font-semibold flex items-center gap-1 transition-colors"
                >
                  <Plus className="w-4 h-4" /> Add
                </button>
              </div>
              <div className="flex-1 overflow-y-auto">
                <RequestTable
                  requests={scriptModel.requests}
                  selectedId={selectedRequestId}
                  onSelect={setSelectedRequestId}
                  onDelete={deleteRequest}
                  onReorder={reorderRequests}
                  variables={(scriptModel.variables || []).map(v => ({
                    name: v.name,
                    value: v.value,
                    type: v.type || 'manual',
                    source_hint: v.source_hint,
                    default_value: v.default_value,
                    datafile_name: v.datafile_name,
                    datafile_column: v.datafile_column,
                  })) as ScriptVariable[]}
                  onRunSingle={handleRunSingle}
                  runningRequestId={runningRequestId}
                />
              </div>
            </>
          )}

          {leftTab === 'variables' && (
            <div className="flex-1 overflow-hidden">
              <VariableManager
                variables={(scriptModel.variables || []).map(v => ({
                  name: v.name,
                  value: v.value,
                  type: v.type || 'manual',
                  source_hint: v.source_hint,
                  default_value: v.default_value,
                  datafile_name: v.datafile_name,
                  datafile_column: v.datafile_column,
                })) as ScriptVariable[]}
                dataFiles={dataFilesList.map(df => ({
                  id: df.id,
                  filename: df.original_filename,
                  columns: df.columns,
                }))}
                scriptModel={scriptModel}
                onChange={(newVars) => setScriptModel(prev => ({ ...prev, variables: newVars }))}
              />
            </div>
          )}
        </div>

        {/* Right: Editor or Empty State */}
        <div className="flex-1 overflow-y-auto">
          {selectedRequest ? (
            <RequestEditor
              request={selectedRequest}
              onChange={updateRequest}
              variables={(scriptModel.variables || []).map(v => ({
                name: v.name,
                value: v.value,
                type: v.type || 'manual',
                source_hint: v.source_hint,
                default_value: v.default_value,
                datafile_name: v.datafile_name,
                datafile_column: v.datafile_column,
              })) as ScriptVariable[]}
              runResult={runResultRequestId === selectedRequestId ? runResult : null}
              runResults={runResults}
              dataFiles={dataFilesList.map(df => ({
                id: df.id,
                filename: df.original_filename,
                columns: df.columns,
              }))}
              onVariableChange={(updated) => {
                setScriptModel(prev => {
                  const vars = [...(prev.variables || [])];
                  const idx = vars.findIndex(v => v.name === updated.name);
                  if (idx >= 0) {
                    vars[idx] = { ...vars[idx], ...updated };
                  } else {
                    vars.push(updated as any);
                  }
                  return { ...prev, variables: vars };
                });
              }}
              onVariableCreate={(newVar) => {
                setScriptModel(prev => {
                  const vars = [...(prev.variables || [])];
                  if (!vars.find(v => v.name === newVar.name)) {
                    vars.push(newVar as any);
                  }
                  return { ...prev, variables: vars };
                });
              }}
            />
          ) : scriptModel.requests.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center px-8">
              <div className="w-20 h-20 bg-[#f5a623]/10 rounded-2xl flex items-center justify-center mb-5">
                <Layers className="w-10 h-10 text-[#f5a623]" />
              </div>
              <h3 className="text-lg font-bold text-gray-800 mb-2">Comienza tu diseño</h3>
              <p className="text-sm text-gray-500 mb-6 max-w-md">
                Agrega requests manualmente o importa desde Postman, OpenAPI, WSDL, HAR o la extensión Chrome.
              </p>
              <div className="flex items-center gap-3">
                <button
                  onClick={addRequest}
                  className="px-5 py-2.5 text-sm bg-[#0a1628] text-white font-semibold rounded-lg hover:bg-[#162040] flex items-center gap-2 shadow-sm"
                >
                  <Plus className="w-4 h-4" /> Add Request
                </button>
                <button
                  onClick={() => setShowImportModal(true)}
                  className="px-5 py-2.5 text-sm bg-[#f5a623] text-[#0a1628] font-bold rounded-lg hover:bg-[#e6951e] flex items-center gap-2 shadow-sm"
                >
                  <FileUp className="w-4 h-4" /> Import
                </button>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
              <FileDown className="w-12 h-12 text-gray-300 mb-3" />
              <p className="text-sm font-medium">Selecciona un request para editar</p>
              <p className="text-sm mt-1">o haz clic en "+ Add" para crear uno</p>
            </div>
          )}
        </div>
        </div>

        {/* ─── Panel inferior - historial de ejecuciones ──────────────── */}
        <ExecutionHistoryPanel
          entries={historyEntries}
          onClear={clearHistory}
        />
      </div>

      {/* ─── Import Modal ────────────────────────────────────────────── */}
      {showImportModal && (
        <ImportModal onImport={handleImport} onClose={() => setShowImportModal(false)} />
      )}

      {/* ─── AI Correlate Modal ──────────────────────────────────────── */}
      {showAICorrelate && aiCorrelateResult && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
            <div className="px-6 py-4 border-b bg-purple-50 flex items-center justify-between">
              <h2 className="text-base font-bold text-purple-800 flex items-center gap-2">
                <Brain className="w-5 h-5" /> AI Correlation Suggestions
              </h2>
              <button onClick={() => setShowAICorrelate(false)} className="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
            </div>
            <div className="p-6 overflow-y-auto flex-1">
              <p className="text-sm text-gray-600 mb-4">{aiCorrelateResult.analysis_summary}</p>
              {aiCorrelateResult.error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 text-sm text-red-700">{aiCorrelateResult.error}</div>
              )}
              {aiCorrelateResult.correlations.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-8">No correlations detected</p>
              ) : (
                <div className="space-y-3">
                  {aiCorrelateResult.correlations.map((c, i) => (
                    <div key={i} className="border border-purple-200 rounded-lg p-3 bg-purple-50/50">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-semibold text-purple-800">{`\${${c.variable_name}}`}</span>
                        <span className="text-sm text-gray-500">Request #{c.extract_from_request}</span>
                      </div>
                      <p className="text-sm text-gray-600 mb-1">{c.description}</p>
                      <code className="text-sm bg-white px-2 py-1 rounded border border-purple-200 block font-mono">{c.regex}</code>
                    </div>
                  ))}
                </div>
              )}
            </div>
            {aiCorrelateResult.correlations.length > 0 && (
              <div className="px-6 py-4 border-t flex justify-end gap-2">
                <button onClick={() => setShowAICorrelate(false)} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">Cancel</button>
                <button
                  onClick={() => applyAICorrelations(aiCorrelateResult.correlations)}
                  className="px-4 py-2.5 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700 font-semibold"
                >
                  Apply {aiCorrelateResult.correlations.length} correlations
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─── AI Debug Modal ──────────────────────────────────────────── */}
      {showAIDebug && aiDebugResult && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg max-h-[80vh] overflow-hidden flex flex-col">
            <div className="px-6 py-4 border-b bg-orange-50 flex items-center justify-between">
              <h2 className="text-base font-bold text-orange-800 flex items-center gap-2">
                <Bug className="w-5 h-5" /> AI Debug Results
              </h2>
              <button onClick={() => setShowAIDebug(false)} className="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
            </div>
            <div className="p-6 overflow-y-auto flex-1">
              <p className="text-sm text-gray-600 mb-4">{aiDebugResult.analysis_summary}</p>
              {aiDebugResult.error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 text-sm text-red-700">{aiDebugResult.error}</div>
              )}
              {aiDebugResult.requests_to_remove.length === 0 ? (
                <div className="text-sm text-gray-400 text-center py-8">
                  <Check className="w-6 h-6 mx-auto mb-2 text-green-500" />
                  Script looks clean — no issues detected
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="text-sm font-semibold text-gray-700 mb-2">Requests to remove:</p>
                  {aiDebugResult.requests_to_remove.map((order) => (
                    <div key={order} className="flex items-start gap-2 bg-orange-50 border border-orange-200 rounded-lg p-3">
                      <AlertCircle className="w-4 h-4 text-orange-600 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="text-sm font-semibold text-orange-800">
                          Request #{order}
                          {scriptModel.requests[order] && ` — ${scriptModel.requests[order].name}`}
                        </p>
                        <p className="text-sm text-orange-700">{aiDebugResult.reasons[String(order)]}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            {aiDebugResult.requests_to_remove.length > 0 && (
              <div className="px-6 py-4 border-t flex justify-end gap-2">
                <button onClick={() => setShowAIDebug(false)} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">Cancel</button>
                <button
                  onClick={() => applyAIDebug(aiDebugResult.requests_to_remove)}
                  className="px-4 py-2.5 text-sm bg-orange-600 text-white rounded-lg hover:bg-orange-700 font-semibold"
                >
                  Remove {aiDebugResult.requests_to_remove.length} requests
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
