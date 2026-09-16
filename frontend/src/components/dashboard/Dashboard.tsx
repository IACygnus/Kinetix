import React, { useEffect, useState, useCallback, useRef, memo } from 'react';
import {
  Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell
} from 'recharts';
import { ArrowLeft, Save, FileDown, FileCode, X, CheckCircle, AlertTriangle } from 'lucide-react';
import type { AIStatus } from '../../types';
import { testAPI } from '../../services/api';
// LoadingSpinner replaced with inline loading indicator for better UX
// Monitoring, Evidence, Capacity, and Comparison moved to standalone pages (R3-A)
import ReportBody from './ReportBody';   // ETAPA 2 (D21): el cuerpo del informe
import TransactionReportSection from './TransactionReportSection';   // N4.7
import {
  CHART_LAYOUT,
  getCodeColor,
  MAX_SUFFIX,
} from '../../config/chartConfig';

interface DashboardProps {
  executionId: string;
  onLogout: () => void;
  onBack: () => void;
  embedded?: boolean;
  // F2: canal OPCIONAL hacia el informe integrado. Sin esta prop el
  // comportamiento es identico al de siempre (reporte individual).
  onAnalysisEdit?: (executionId: string, field: string, value: string) => void;
  // F4: texto editado guardado en el informe integrado. Se aplica encima de lo
  // que trae la DB. El reporte individual no la pasa y no se ve afectado.
  analysisOverrides?: Record<string, string>;
}

// GRAF1-B: sufijo de la serie de maximos (solo Response Times por Transaccion)

// ===== CUSTOM TOOLTIP COMPONENT =====

// ===== EDITABLE TEXTAREA — defined OUTSIDE Dashboard to prevent re-creation on re-render =====
const EditableTextArea = memo(function EditableTextArea({
  initialValue,
  onSave,
  placeholder,
  className,
  minHeight = '176px',
  debounceMs,
}: {
  initialValue: string;
  onSave: (value: string) => void;
  placeholder?: string;
  className?: string;
  minHeight?: string;
  debounceMs?: number;
}) {
  const [localValue, setLocalValue] = useState(initialValue);
  // R1: sin `debounceMs` el componente se comporta EXACTAMENTE como antes
  // (solo confirma en blur). Con el, una pausa al escribir tambien confirma,
  // que es lo que despierta al autoguardado sin necesidad de hacer clic fuera.
  const draftTimer = useRef<number | null>(null);
  const clearDraft = () => { if (draftTimer.current) { clearTimeout(draftTimer.current); draftTimer.current = null; } };
  useEffect(() => { setLocalValue(initialValue); }, [initialValue]);
  useEffect(() => clearDraft, []);
  return (
    <textarea
      value={localValue}
      onChange={(e) => {
        const v = e.target.value;
        setLocalValue(v);
        if (debounceMs) { clearDraft(); draftTimer.current = window.setTimeout(() => { draftTimer.current = null; onSave(v); }, debounceMs); }
      }}
      onBlur={() => { clearDraft(); onSave(localValue); }}
      placeholder={placeholder || 'Click para editar el analisis...'}
      className={className || 'w-full p-4 border-2 border-gray-300 rounded-xl text-xl text-gray-800 focus:ring-2 focus:ring-orange-400/50 focus:border-orange-500 resize-y cursor-text hover:border-orange-300 transition-colors'}
      style={{ minHeight }}
    />
  );
});

export default function Dashboard({ executionId, onLogout: _onLogout, onBack, embedded = false, onAnalysisEdit, analysisOverrides }: DashboardProps) {
  const [execution, setExecution] = useState<any>(null);
  const [charts, setCharts] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [saving, setSaving] = useState(false);
  const [timeMode, setTimeMode] = useState<'elapsed' | 'real'>('elapsed');

  const [isExportingPDF, setIsExportingPDF] = useState(false);
  const [pdfProgress, setPdfProgress] = useState(0);

  const [analysisSummary, setAnalysisSummary] = useState('');
  const [analysisErrors, setAnalysisErrors] = useState('');
  const [analysisResponseTimes, setAnalysisResponseTimes] = useState('');
  const [analysisResponseTimeOverTime, setAnalysisResponseTimeOverTime] = useState('');
  const [analysisThroughput, setAnalysisThroughput] = useState('');
  const [analysisLatency, setAnalysisLatency] = useState('');
  const [analysisErrorRate, setAnalysisErrorRate] = useState('');
  const [analysisCodesPerSecond, setAnalysisCodesPerSecond] = useState('');
  const [analysisTransactionsPerSecond, setAnalysisTransactionsPerSecond] = useState('');
  const [analysisActiveThreads, setAnalysisActiveThreads] = useState('');
  const [analysisRedirects, setAnalysisRedirects] = useState('');
  const [conclusions, setConclusions] = useState('');
  const [recommendations, setRecommendations] = useState('');

  const [hiddenLinesResponseTimes, setHiddenLinesResponseTimes] = useState<Set<string>>(new Set());
  const [hiddenLinesCodes, setHiddenLinesCodes] = useState<Set<string>>(new Set());
  const [hiddenLinesTPS, setHiddenLinesTPS] = useState<Set<string>>(new Set());

  // KNX-10: Collapsible charts
  const [chartsExpanded, setChartsExpanded] = useState(true);

  // P3: Y-axis zoom per chart
  const [yAxisRanges, setYAxisRanges] = useState<Record<string, { min: number | 'auto'; max: number | 'auto' }>>({});

  // AI Status toast
  const [aiToast, setAiToast] = useState<AIStatus | null>(null);

  // Read AI status from sessionStorage (set by UploadJTL after upload)
  useEffect(() => {
    const stored = sessionStorage.getItem('ai_status');
    if (stored) {
      try {
        setAiToast(JSON.parse(stored));
      } catch { /* ignore */ }
      sessionStorage.removeItem('ai_status');
    }
  }, []);

  // Auto-close toast after 5 seconds
  useEffect(() => {
    if (!aiToast) return;
    const timer = setTimeout(() => setAiToast(null), 5000);
    return () => clearTimeout(timer);
  }, [aiToast]);

  // ===== R1: AUTOGUARDADO DEL REPORTE INDIVIDUAL (patron F3) =====
  // Escribe en test_executions por el MISMO PUT que el boton manual. Solo en la
  // vista individual: embebido en el informe integrado guarda la pagina padre
  // por el canal de overrides (Opcion B), y guardar aqui seria doble escritura.
  const AUTOSAVE_MS = 1800;
  const autoSaveMs = embedded ? undefined : AUTOSAVE_MS;
  const saveTimerRef = useRef<number | null>(null);
  const pendingRef = useRef<Record<string, string>>({});
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [savedAt, setSavedAt] = useState('');

  const flushSave = useCallback(async () => {
    if (saveTimerRef.current) { clearTimeout(saveTimerRef.current); saveTimerRef.current = null; }
    const pend = pendingRef.current;
    if (!Object.keys(pend).length) return;
    pendingRef.current = {};
    setSaveState('saving');
    try {
      await testAPI.updateAnalysis(executionId!, pend);
      setSaveState('saved');
      setSavedAt(new Date().toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' }));
    } catch {
      // Lo no guardado vuelve a la cola (sin pisar lo que se haya escrito despues).
      pendingRef.current = { ...pend, ...pendingRef.current };
      setSaveState('error');
    }
  }, [executionId]);

  // Canal unico: cada campo confirmado entra a la cola y rearma el debounce.
  const queueSave = useCallback((field: string, value: string) => {
    if (embedded) return;
    pendingRef.current[field] = value;
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = window.setTimeout(() => { saveTimerRef.current = null; flushSave(); }, AUTOSAVE_MS);
  }, [embedded, flushSave]);

  // Descarga de la pagina: best-effort con keepalive, igual que F3.
  useEffect(() => {
    const onUnload = () => {
      const pend = pendingRef.current;
      if (embedded || !Object.keys(pend).length) return;
      const base = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';
      fetch(`${base}/executions/${executionId}/analysis`, {
        method: 'PUT', credentials: 'include', keepalive: true,
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': document.cookie.match(/csrf_token=([^;]+)/)?.[1] || '' },
        body: JSON.stringify(pend),
      }).catch(() => {});
    };
    window.addEventListener('beforeunload', onUnload);
    return () => { window.removeEventListener('beforeunload', onUnload); if (saveTimerRef.current) clearTimeout(saveTimerRef.current); };
  }, [embedded, executionId]);

  useEffect(() => {
    if (executionId) {
      setYAxisRanges({});  // Reset zoom when changing report
      loadData();
    }
  }, [executionId]);

  const loadData = async () => {
    try {
      const [execData, chartsData] = await Promise.all([
        testAPI.getExecution(executionId!),
        testAPI.getCharts(executionId!),
      ]);

      setExecution(execData);
      setCharts(chartsData);

      setAnalysisSummary(execData.ai_analysis_summary || '');
      setAnalysisErrors(execData.ai_analysis_errors || '');
      setAnalysisResponseTimes(execData.ai_analysis_response_times || '');
      setAnalysisResponseTimeOverTime(execData.ai_analysis_response_time_over_time || '');
      setAnalysisThroughput(execData.ai_analysis_throughput || '');
      setAnalysisLatency(execData.ai_analysis_latency || '');
      setAnalysisErrorRate(execData.ai_analysis_error_rate || '');
      setAnalysisCodesPerSecond(execData.ai_analysis_codes_per_second || '');
      setAnalysisTransactionsPerSecond(execData.ai_analysis_transactions_per_second || '');
      setAnalysisActiveThreads(execData.ai_analysis_active_threads || '');
      setAnalysisRedirects(execData.ai_analysis_redirects || '');
      setConclusions(execData.ai_conclusions || '');
      setRecommendations(execData.ai_recommendations || '');

      // F4: overrides del informe integrado — se aplican ENCIMA del texto de la
      // DB. Solo afectan a esta vista embebida; la ejecucion no se modifica.
      if (analysisOverrides) {
        const setters: Record<string, (v: string) => void> = {
          ai_analysis_summary: setAnalysisSummary, ai_analysis_errors: setAnalysisErrors,
          ai_analysis_response_times: setAnalysisResponseTimes, ai_analysis_response_time_over_time: setAnalysisResponseTimeOverTime,
          ai_analysis_throughput: setAnalysisThroughput, ai_analysis_latency: setAnalysisLatency,
          ai_analysis_error_rate: setAnalysisErrorRate, ai_analysis_codes_per_second: setAnalysisCodesPerSecond,
          ai_analysis_transactions_per_second: setAnalysisTransactionsPerSecond, ai_analysis_active_threads: setAnalysisActiveThreads,
          ai_analysis_redirects: setAnalysisRedirects,
        };
        Object.entries(analysisOverrides).forEach(([k, v]) => setters[k]?.(v));
      }
    } catch (error: any) {
      console.error('Error loading data:', error);
      setLoadError(error?.response?.status === 401
        ? 'Sesion expirada. Por favor inicie sesion nuevamente.'
        : 'Error al cargar el reporte. Verifique la conexion e intente de nuevo.');
    } finally {
      setLoading(false);
    }
  };

  // F2: guarda en el estado local (como siempre) y ademas avisa al padre si hay canal.
  const emitEdit = (field: string, setter: (v: string) => void) => (value: string) => {
    setter(value);
    onAnalysisEdit?.(executionId!, field, value);
    queueSave(field, value);   // R1: no hace nada en modo embebido
  };

  const handleSaveChanges = async () => {
    // R1: el boton sigue siendo el guardado completo. Descarta el debounce en
    // vuelo y la cola: este PUT manda los 13 campos y los deja al dia.
    if (saveTimerRef.current) { clearTimeout(saveTimerRef.current); saveTimerRef.current = null; }
    pendingRef.current = {};
    setSaving(true);
    try {
      await testAPI.updateAnalysis(executionId!, {
        ai_analysis_summary: analysisSummary,
        ai_analysis_errors: analysisErrors,
        ai_analysis_response_times: analysisResponseTimes,
        ai_analysis_response_time_over_time: analysisResponseTimeOverTime,
        ai_analysis_throughput: analysisThroughput,
        ai_analysis_latency: analysisLatency,
        ai_analysis_error_rate: analysisErrorRate,
        ai_analysis_codes_per_second: analysisCodesPerSecond,
        ai_analysis_transactions_per_second: analysisTransactionsPerSecond,
        ai_analysis_active_threads: analysisActiveThreads,
        ai_analysis_redirects: analysisRedirects,
        ai_recommendations: recommendations,
        ai_conclusions: conclusions,
      });
      setSaveState('saved');
      setSavedAt(new Date().toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' }));
      alert('Cambios guardados exitosamente');
    } catch (error) {
      alert('Error al guardar cambios');
    } finally {
      setSaving(false);
    }
  };

  const handleExportHTML = async () => {
    try {
      const blob = await testAPI.exportHTML(executionId!);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `reporte_${execution.name.replace(/\s+/g, '_')}_${new Date().toISOString().split('T')[0]}.html`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
    } catch (error) {
      console.error('Error exportando HTML:', error);
      alert('Error al exportar HTML. Por favor, intenta de nuevo.');
    }
  };

  const handleExportPDF = async () => {
    setIsExportingPDF(true);
    setPdfProgress(10);

    try {
      setPdfProgress(30);
      const blob = await testAPI.exportPDF(executionId!);
      setPdfProgress(90);

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `reporte_${execution.name.replace(/\s+/g, '_')}_${new Date().toISOString().split('T')[0]}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();

      setPdfProgress(100);
      setTimeout(() => {
        setIsExportingPDF(false);
        setPdfProgress(0);
      }, 1000);
    } catch (error) {
      console.error('Error:', error);
      alert('Error al generar el PDF. Por favor, intenta de nuevo.');
      setIsExportingPDF(false);
      setPdfProgress(0);
    }
  };

  const prepareChartData = (timelineData: any[]) => {
    if (!timelineData || timelineData.length === 0) return [];
    const startTime = new Date(timelineData[0].timestamp);

    return timelineData.map((item: any) => {
      const timestamp = new Date(item.timestamp);
      let displayTime;
      if (timeMode === 'elapsed') {
        const elapsedSeconds = Math.floor((timestamp.getTime() - startTime.getTime()) / 1000);
        const hours = Math.floor(elapsedSeconds / 3600);
        const minutes = Math.floor((elapsedSeconds % 3600) / 60);
        const seconds = elapsedSeconds % 60;
        displayTime = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
      } else {
        displayTime = timestamp.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
      }
      return { ...item, displayTime };
    });
  };

  // GRAF1-B: withMax solo lo activa Response Times por Transaccion (serie dual del backend).
  // Las demas graficas llaman sin el flag y se construyen exactamente igual que antes.
  const prepareMultiLineData = (data: any[], withMax = false) => {
    if (!data || data.length === 0) return { labels: [], data: [] };
    const labels = [...new Set(data.map((d: any) => d.label || d.code))];
    const timeMap = new Map();
    data.forEach((item: any) => {
      const key = item.label || item.code;
      if (!timeMap.has(item.timestamp)) {
        timeMap.set(item.timestamp, { timestamp: item.timestamp });
      }
      timeMap.get(item.timestamp)[key] = item.value;
      // Tolerante a datos sin value_max (ejecuciones previas a GRAF1-A): no crea la clave.
      if (withMax && item.value_max != null) {
        timeMap.get(item.timestamp)[`${key}${MAX_SUFFIX}`] = item.value_max;
      }
    });
    const chartData = Array.from(timeMap.values()).sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
    const startTime = chartData.length > 0 ? new Date(chartData[0].timestamp) : new Date();
    const processedData = chartData.map((item: any) => {
      const timestamp = new Date(item.timestamp);
      let displayTime;
      if (timeMode === 'elapsed') {
        const elapsedSeconds = Math.floor((timestamp.getTime() - startTime.getTime()) / 1000);
        const hours = Math.floor(elapsedSeconds / 3600);
        const minutes = Math.floor((elapsedSeconds % 3600) / 60);
        const seconds = elapsedSeconds % 60;
        displayTime = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
      } else {
        displayTime = timestamp.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
      }
      return { ...item, displayTime };
    });
    return { labels, data: processedData };
  };

  const handleLegendClick = useCallback((dataKey: string, hiddenLines: Set<string>, setHiddenLines: React.Dispatch<React.SetStateAction<Set<string>>>) => {
    const newHiddenLines = new Set(hiddenLines);
    if (newHiddenLines.has(dataKey)) { newHiddenLines.delete(dataKey); } else { newHiddenLines.add(dataKey); }
    setHiddenLines(newHiddenLines);
  }, []);

  // Helper for chart analysis sections — MUST be before early returns (Rules of Hooks)
  const AnalysisBox = useCallback(({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <div className="mt-4 bg-white rounded-xl p-5 border-l-4 border-orange-500 border border-gray-200">
      <div className="flex items-center justify-between mb-2">
        <h4 className="font-bold text-orange-600 text-xl">Analisis</h4>
        <span className="text-xs text-gray-400 italic">Click para editar</span>
      </div>
      <EditableTextArea initialValue={value} onSave={onChange} placeholder="Analisis..." debounceMs={autoSaveMs} />
    </div>
  ), []);

  // P3: Y-axis zoom helpers
  const handleYRange = useCallback((key: string, yMin: number | 'auto', yMax: number | 'auto') => {
    setYAxisRanges(prev => ({ ...prev, [key]: { min: yMin, max: yMax } }));
  }, []);

  const getYDomain = useCallback((key: string): [number | string, number | string] => {
    const r = yAxisRanges[key];
    if (!r) return ['auto', 'auto'];
    return [r.min, r.max];
  }, [yAxisRanges]);

  const extractY = useCallback((data: any[], keys: string[]): number[] => {
    if (!data) return [];
    const vals: number[] = [];
    data.forEach(p => keys.forEach(k => { const v = p[k]; if (v != null && typeof v === 'number') vals.push(v); }));
    return vals;
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-64 bg-white">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#f5a623] mx-auto mb-4"></div>
        <p className="text-xl text-gray-500">Cargando reporte...</p>
      </div>
    </div>
  );
  if (loadError) return (
    <div className="flex flex-col items-center justify-center h-64 bg-white gap-4">
      <p className="text-2xl text-red-500 font-semibold">{loadError}</p>
      <button onClick={() => { setLoadError(''); setLoading(true); loadData(); }}
        className="px-6 py-2 bg-[#f5a623] text-[#0a1628] rounded-xl font-bold text-lg hover:bg-[#f5a623]/90 transition-colors">
        Reintentar
      </button>
    </div>
  );
  if (!execution || !charts) return (
    <div className="flex flex-col items-center justify-center h-64 bg-white gap-4">
      <p className="text-2xl text-gray-500">No se encontraron datos para este reporte</p>
      {!embedded && (
        <button onClick={onBack} className="px-6 py-2 bg-gray-200 text-gray-700 rounded-xl text-lg hover:bg-gray-300 transition-colors">
          Volver al historial
        </button>
      )}
    </div>
  );

  // ===== DATA PROCESSING =====
  const throughputData = prepareChartData(charts.throughput_timeline || []);
  const latencyData = prepareChartData(charts.latency_timeline || []);
  const errorRateData = prepareChartData(charts.error_rate_timeline || []);
  const activeThreadsData = prepareChartData(charts.active_threads_timeline || []);
  const responseTimesByLabel = prepareMultiLineData(charts.response_times_by_label || [], true);
  const tpsByLabel = prepareMultiLineData(charts.tps_by_label || []);
  const codesPerSecond = prepareMultiLineData(charts.codes_per_second || []);
  // GRAF1-B: solo las transacciones que realmente traen maximos pintan la 2a linea.
  const rtMaxLabels = responseTimesByLabel.labels.filter((l: string) =>
    responseTimesByLabel.data.some((p: any) => p[`${l}${MAX_SUFFIX}`] != null));
  const rtMaxKeys = rtMaxLabels.map((l: string) => `${l}${MAX_SUFFIX}`);

  // KNX-02: Use real error codes from error_detail (no more hardcoded "404/405")
  const errorData = (charts.error_detail || []).map((row: any) => ({
    name: row.label,
    code: String(row.code),
    value: row.count,
    percentage: execution.total_requests > 0
      ? ((row.count / execution.total_requests) * 100).toFixed(2)
      : '0.00',
  }));

  const minH = Math.max(CHART_LAYOUT.minHeight, 700);

  return (
    <>
    {/* AI Status Toast */}
    {aiToast && (
      <div
        className={`fixed top-6 right-6 z-50 max-w-sm rounded-xl border shadow-2xl p-5 animate-slide-in-right ${
          aiToast.success
            ? 'bg-green-900/90 border-green-500 text-green-100'
            : 'bg-amber-900/90 border-amber-500 text-amber-100'
        }`}
      >
        <button
          onClick={() => setAiToast(null)}
          className="absolute top-2 right-2 opacity-60 hover:opacity-100 transition-opacity"
        >
          <X className="w-4 h-4" />
        </button>
        <div className="flex items-start gap-3">
          {aiToast.success ? (
            <CheckCircle className="w-6 h-6 text-green-400 flex-shrink-0 mt-0.5" />
          ) : (
            <AlertTriangle className="w-6 h-6 text-amber-400 flex-shrink-0 mt-0.5" />
          )}
          <div>
            <p className="font-semibold text-lg">
              {aiToast.success
                ? `Analisis generado con ${aiToast.provider === 'gemini' ? 'Gemini AI' : aiToast.provider}`
                : 'Analisis generado localmente'}
            </p>
            <p className="text-sm opacity-80 mt-1">
              {/* B6.3: el aviso nombra el provider y el modelo REALES y el motivo
                  real. Antes decia siempre "Gemini no disponible", aunque el
                  provider fuera OpenAI y el motivo fuera otro. */}
              {aiToast.success
                ? `Modelo: ${aiToast.model}`
                : aiToast.error
                  || `${aiToast.provider || 'El proveedor de IA'} ${aiToast.model || ''} no devolvio analisis: se uso el analizador de respaldo`}
            </p>
            <p className="text-sm opacity-70 mt-0.5">
              {aiToast.success
                ? 'El informe incluye analisis inteligente de rendimiento'
                : 'El informe fue generado con el analizador estadistico de respaldo'}
            </p>
          </div>
        </div>
      </div>
    )}

    {/* R1: salir de cualquier caja guarda ya, sin esperar al debounce (blur burbujea) */}
    <div className="w-full overflow-hidden bg-gray-50" id="dashboard-content"
      onBlur={!embedded ? () => { if (Object.keys(pendingRef.current).length) flushSave(); } : undefined}>
      {/* HEADER — Dark gradient card */}
      <div className="w-full px-4 py-6">
        <div className="bg-gradient-to-r from-[#0a1628] to-[#162040] rounded-2xl p-8 text-white shadow-xl mb-8">
          {/* Top row: SQA logo left, metadata right */}
          <div className="flex flex-col sm:flex-row justify-between items-start mb-6">
            <div className="flex items-center gap-4">
              {!embedded && (
                <button onClick={onBack} className="text-white/70 hover:text-white transition-colors">
                  <ArrowLeft className="w-8 h-8" />
                </button>
              )}
              <div>
                <h1 className="text-4xl font-bold">
                  sqa<span className="text-[#f5a623]">_</span>
                </h1>
                <p className="text-white/60 text-lg">Software Quality Assurance</p>
              </div>
            </div>
            <div className="text-right mt-4 sm:mt-0">
              <p className="text-white/60 text-lg">Realizado por:</p>
              <p className="text-xl font-bold">Celula de performance SQA</p>
              <p className="text-white/60 text-lg">Generado: {new Date(execution.created_at).toLocaleString('es-ES')}</p>
            </div>
          </div>

          {/* Project info grid */}
          <div className={`bg-white/10 backdrop-blur rounded-xl p-6 grid grid-cols-1 sm:grid-cols-2 gap-6 ${execution.acceptance_criteria_json?.verdict ? 'lg:grid-cols-5' : 'lg:grid-cols-4'}`}>
            <div>
              <p className="text-white/50 text-base uppercase tracking-wider">Cliente</p>
              <p className="text-2xl font-bold mt-1">{execution.client || execution.project || 'N/A'}</p>
            </div>
            <div>
              <p className="text-white/50 text-base uppercase tracking-wider">Nombre del Proyecto</p>
              <p className="text-2xl font-bold mt-1">{execution.name}</p>
            </div>
            <div>
              <p className="text-white/50 text-base uppercase tracking-wider">Duracion</p>
              <p className="text-2xl font-bold mt-1">{execution.duration_seconds ? `${Math.floor(execution.duration_seconds / 60)}m ${Math.floor(execution.duration_seconds % 60)}s` : '--'}</p>
            </div>
            <div>
              <p className="text-white/50 text-base uppercase tracking-wider">Tipo de Prueba</p>
              <span className={`inline-block mt-2 px-4 py-1 rounded-full text-lg font-bold uppercase ${
                execution.test_type === 'stress' ? 'bg-red-500/20 text-red-300' :
                execution.test_type === 'load' ? 'bg-green-500/20 text-green-300' :
                execution.test_type === 'endurance' ? 'bg-blue-500/20 text-blue-300' :
                execution.test_type === 'spike' ? 'bg-yellow-500/20 text-yellow-300' :
                execution.test_type === 'scalability' ? 'bg-purple-500/20 text-purple-300' :
                'bg-gray-500/20 text-gray-300'
              }`}>
                {execution.test_type?.toUpperCase() || 'LOAD'}
              </span>
            </div>
            {/* Verdict badge */}
            {execution.acceptance_criteria_json?.verdict && (
              <div>
                <p className="text-white/50 text-base uppercase tracking-wider">Veredicto</p>
                <span className={`inline-block mt-2 px-4 py-1.5 rounded-full text-lg font-bold uppercase tracking-wide ${
                  execution.acceptance_criteria_json.verdict === 'APTO' ? 'bg-green-500/20 text-green-300 border border-green-500/40' :
                  execution.acceptance_criteria_json.verdict === 'NO APTO' ? 'bg-red-500/20 text-red-300 border border-red-500/40' :
                  'bg-yellow-500/20 text-yellow-300 border border-yellow-500/40'
                }`}>
                  {execution.acceptance_criteria_json.verdict}
                </span>
              </div>
            )}
          </div>

          {/* File and dates row */}
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-6 text-lg">
            <div>
              <p className="text-white/50 text-base">Archivo</p>
              <p className="font-mono text-white/90 truncate">{execution.jtl_filename}</p>
            </div>
            <div>
              <p className="text-white/50 text-base">Inicio</p>
              <p className="text-white/90">{execution.start_time ? new Date(execution.start_time).toLocaleString('es-ES') : '--'}</p>
            </div>
            <div>
              <p className="text-white/50 text-base">Fin</p>
              <p className="text-white/90">{execution.end_time ? new Date(execution.end_time).toLocaleString('es-ES') : '--'}</p>
            </div>
          </div>
        </div>

        {/* RESUMEN EJECUTIVO — KNX-10: Extended KPI Dashboard */}
        <div className="mb-8">
          <h2 className="text-4xl font-bold text-gray-800 mb-5">Dashboard de KPIs</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="bg-white rounded-2xl shadow-lg p-5 border-l-4 border-l-blue-500 border border-gray-200">
              <p className="text-base text-gray-500 uppercase tracking-wide">Total Requests</p>
              <p className="text-4xl font-bold text-gray-800 mt-1">{execution.total_requests.toLocaleString()}</p>
              <p className="text-sm text-gray-400 mt-1">samples</p>
            </div>
            <div className="bg-white rounded-2xl shadow-lg p-5 border-l-4 border-l-green-500 border border-gray-200">
              <p className="text-base text-gray-500 uppercase tracking-wide">Avg Response Time</p>
              <p className="text-4xl font-bold text-green-600 mt-1">{execution.avg_response_time.toFixed(0)} <span className="text-xl">ms</span></p>
            </div>
            <div className={`bg-white rounded-2xl shadow-lg p-5 border-l-4 border border-gray-200 ${execution.error_rate < 1 ? 'border-l-green-500' : execution.error_rate < 5 ? 'border-l-orange-500' : 'border-l-red-500'}`}>
              <p className="text-base text-gray-500 uppercase tracking-wide">Error Rate</p>
              <p className={`text-4xl font-bold mt-1 ${execution.error_rate < 1 ? 'text-green-600' : execution.error_rate < 5 ? 'text-orange-600' : 'text-red-600'}`}>{execution.error_rate.toFixed(2)} <span className="text-xl">%</span></p>
            </div>
            <div className="bg-white rounded-2xl shadow-lg p-5 border-l-4 border-l-purple-500 border border-gray-200">
              <p className="text-base text-gray-500 uppercase tracking-wide">Throughput</p>
              <p className="text-4xl font-bold text-purple-600 mt-1">{execution.throughput.toFixed(2)} <span className="text-xl">req/s</span></p>
            </div>
            {/* Percentile cards */}
            <div className="bg-white rounded-2xl shadow-lg p-5 border-l-4 border-l-cyan-500 border border-gray-200">
              <p className="text-base text-gray-500 uppercase tracking-wide">Percentil 50</p>
              <p className="text-4xl font-bold text-cyan-600 mt-1">{execution.p50_response_time?.toFixed(0) || '--'} <span className="text-xl">ms</span></p>
            </div>
            <div className="bg-white rounded-2xl shadow-lg p-5 border-l-4 border-l-amber-500 border border-gray-200">
              <p className="text-base text-gray-500 uppercase tracking-wide">Percentil 90</p>
              <p className="text-4xl font-bold text-amber-600 mt-1">{execution.p90_response_time.toFixed(0)} <span className="text-xl">ms</span></p>
            </div>
            <div className="bg-white rounded-2xl shadow-lg p-5 border-l-4 border-l-orange-500 border border-gray-200">
              <p className="text-base text-gray-500 uppercase tracking-wide">Percentil 95</p>
              <p className="text-4xl font-bold text-orange-600 mt-1">{execution.p95_response_time.toFixed(0)} <span className="text-xl">ms</span></p>
            </div>
            <div className="bg-white rounded-2xl shadow-lg p-5 border-l-4 border-l-red-500 border border-gray-200">
              <p className="text-base text-gray-500 uppercase tracking-wide">Percentil 99</p>
              <p className="text-4xl font-bold text-red-600 mt-1">{execution.p99_response_time.toFixed(0)} <span className="text-xl">ms</span></p>
            </div>
          </div>
        </div>

        {/* KNX-09: Per-Transaction Verdicts */}
        {execution.acceptance_criteria_json?.verdicts_per_transaction && Object.keys(execution.acceptance_criteria_json.verdicts_per_transaction).length > 0 && (
          <div className="mb-8">
            <div className="bg-white rounded-2xl shadow-lg overflow-hidden border border-gray-200">
              <div className="bg-[#0a1628] px-6 py-4">
                <h2 className="text-3xl font-bold text-white">Veredicto por Transaccion</h2>
              </div>
              <div className="p-6">
                <table className="w-full text-lg">
                  <thead>
                    <tr className="border-b-2 border-gray-200">
                      <th className="text-left py-3 px-4 text-base font-bold text-gray-500 uppercase">Transaccion</th>
                      <th className="text-center py-3 px-4 text-base font-bold text-gray-500 uppercase">P90 (ms)</th>
                      <th className="text-center py-3 px-4 text-base font-bold text-gray-500 uppercase">Umbral RT (ms)</th>
                      <th className="text-center py-3 px-4 text-base font-bold text-gray-500 uppercase">% Error</th>
                      <th className="text-center py-3 px-4 text-base font-bold text-gray-500 uppercase">Veredicto</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {Object.entries(execution.acceptance_criteria_json.verdicts_per_transaction).map(([txn, verdict]: [string, any]) => {
                      const txnData = (charts.by_label || []).find((r: any) => r.label === txn);
                      const rtThreshold = execution.acceptance_criteria_json?.per_transaction?.[txn]?.response_time || execution.acceptance_criteria_json?.response_time || 2000;
                      return (
                        <tr key={txn} className="hover:bg-gray-50">
                          <td className="py-3 px-4 text-xl text-gray-900 font-medium">{txn}</td>
                          <td className="py-3 px-4 text-xl text-center text-gray-700">{txnData?.p90?.toFixed(0) || '--'}</td>
                          <td className="py-3 px-4 text-xl text-center text-gray-400">{rtThreshold}</td>
                          <td className="py-3 px-4 text-xl text-center text-gray-700">{txnData?.error_rate?.toFixed(2) || '0.00'}%</td>
                          <td className="py-3 px-4 text-center">
                            <span className={`px-3 py-1 rounded-full text-base font-bold uppercase ${
                              verdict === 'APTO' ? 'bg-green-100 text-green-700' :
                              verdict === 'NO APTO' ? 'bg-red-100 text-red-700' :
                              'bg-yellow-100 text-yellow-700'
                            }`}>
                              {verdict as string}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* REPORTE RESUMEN TABLE */}
        <div className="mb-8">
          <div className="w-full overflow-x-auto rounded-2xl shadow-lg border border-gray-200">
            <div className="bg-[#0a1628] px-6 py-4">
              <h2 className="text-3xl font-bold text-white">Reporte Resumen</h2>
            </div>
            <table className="w-full table-auto text-lg">
              <thead className="bg-[#0a1628]">
                <tr>
                  <th className="px-3 py-2 text-left text-base font-bold text-white uppercase">Transaccion</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">Muestras</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">Errores</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">% Error</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">Promedio</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">Mediana</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">90%</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">95%</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">99%</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">Min</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">Max</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">TPS</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">KB/s Rec</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">KB/s Env</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-100">
                {(charts.by_label || []).map((row: any, idx: number) => (
                  <tr key={idx} className="hover:bg-blue-50/50 transition-colors">
                    <td className="px-3 py-2 text-base font-medium text-gray-900 max-w-[250px] truncate" title={row.label}>{row.label}</td>
                    <td className="px-3 py-2 text-base text-right text-gray-700">{row.count.toLocaleString()}</td>
                    <td className="px-3 py-2 text-base text-right text-red-600 font-semibold">{(row.error_count ?? (row.count - row.success_count)).toLocaleString()}</td>
                    <td className={`px-3 py-2 text-base text-right font-semibold ${(row.error_rate ?? 0) === 0 ? 'text-green-600' : (row.error_rate ?? 0) < 5 ? 'text-orange-600 bg-orange-50' : 'text-red-600 bg-red-50'}`}>
                      {(row.error_rate ?? ((row.count - row.success_count) / row.count * 100)).toFixed(2)}%
                    </td>
                    <td className="px-3 py-2 text-base text-right text-gray-700">{row.avg_time >= 1000 ? Math.round(row.avg_time).toLocaleString() : row.avg_time.toFixed(2)}</td>
                    <td className="px-3 py-2 text-base text-right text-gray-700">{row.avg_time >= 1000 ? Math.round(row.avg_time).toLocaleString() : row.avg_time.toFixed(2)}</td>
                    <td className="px-3 py-2 text-base text-right text-gray-700">{(row.p90 ?? row.avg_time * 1.5) >= 1000 ? Math.round(row.p90 ?? row.avg_time * 1.5).toLocaleString() : (row.p90 ?? row.avg_time * 1.5).toFixed(2)}</td>
                    <td className="px-3 py-2 text-base text-right text-gray-700">{(row.p95 ?? row.avg_time * 2) >= 1000 ? Math.round(row.p95 ?? row.avg_time * 2).toLocaleString() : (row.p95 ?? row.avg_time * 2).toFixed(2)}</td>
                    <td className="px-3 py-2 text-base text-right text-gray-700">{(row.p99 ?? row.avg_time * 3) >= 1000 ? Math.round(row.p99 ?? row.avg_time * 3).toLocaleString() : (row.p99 ?? row.avg_time * 3).toFixed(2)}</td>
                    <td className="px-3 py-2 text-base text-right text-gray-700">{row.min_time >= 1000 ? Math.round(row.min_time).toLocaleString() : row.min_time.toFixed(2)}</td>
                    <td className="px-3 py-2 text-base text-right text-gray-700">{row.max_time >= 1000 ? Math.round(row.max_time).toLocaleString() : row.max_time.toFixed(2)}</td>
                    <td className="px-3 py-2 text-base text-right text-blue-700 font-semibold">{(row.throughput ?? (row.count / (execution.duration_seconds || 1))).toFixed(2)}</td>
                    <td className="px-3 py-2 text-base text-right text-gray-700">{row.kb_received?.toFixed(2) || '--'}</td>
                    <td className="px-3 py-2 text-base text-right text-gray-700">{row.kb_sent?.toFixed(2) || '--'}</td>
                  </tr>
                ))}
                <tr className="bg-[#0a1628] text-white font-bold">
                  <td className="px-3 py-2 text-base">TOTAL PRINCIPALES</td>
                  <td className="px-3 py-2 text-base text-right">{execution.total_requests.toLocaleString()}</td>
                  <td className="px-3 py-2 text-base text-right">{execution.total_errors.toLocaleString()}</td>
                  <td className="px-3 py-2 text-base text-right">{execution.error_rate.toFixed(2)}%</td>
                  <td className="px-3 py-2 text-base text-right">{execution.avg_response_time.toFixed(2)}</td>
                  <td className="px-3 py-2 text-base text-right">{execution.median_response_time?.toFixed(2) || '--'}</td>
                  <td className="px-3 py-2 text-base text-right">{execution.p90_response_time.toFixed(2)}</td>
                  <td className="px-3 py-2 text-base text-right">{execution.p95_response_time.toFixed(2)}</td>
                  <td className="px-3 py-2 text-base text-right">{execution.p99_response_time.toFixed(2)}</td>
                  <td className="px-3 py-2 text-base text-right">{execution.min_response_time.toFixed(2)}</td>
                  <td className="px-3 py-2 text-base text-right">{execution.max_response_time.toFixed(2)}</td>
                  <td className="px-3 py-2 text-base text-right">{execution.throughput.toFixed(2)}</td>
                  <td className="px-3 py-2 text-base text-right">{execution.kb_per_sec_received?.toFixed(2) || '--'}</td>
                  <td className="px-3 py-2 text-base text-right">{execution.kb_per_sec_sent?.toFixed(2) || '--'}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div className="mt-4 bg-white rounded-2xl shadow-lg p-6 border-l-4 border-orange-500 border border-gray-200">
            <h3 className="text-3xl font-bold text-orange-600 mb-3">Analisis del Reporte Resumen</h3>
            <span className="text-xs text-gray-400 italic mb-1 block">Click para editar</span>
            <EditableTextArea initialValue={analysisSummary} onSave={emitEdit('ai_analysis_summary', setAnalysisSummary)} placeholder="El analisis aparecera aqui..." debounceMs={autoSaveMs} />
          </div>

          {/* TABLA DE REDIRECCIONES */}
          {charts.has_redirects && charts.by_label_redirects && charts.by_label_redirects.length > 0 && (
            <div className="mt-6">
              <div className="bg-white rounded-2xl shadow-lg overflow-hidden border border-gray-200">
                <div className="bg-[#0a1628] px-6 py-4">
                  <h2 className="text-3xl font-bold text-white flex items-center gap-2">
                    Reporte de Redirecciones
                    <span className="ml-2 text-xl bg-white/20 rounded-full px-3 py-0.5">{charts.by_label_redirects.length} labels</span>
                  </h2>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-[#0a1628]">
                      <tr>
                        <th className="px-4 py-3 text-left text-xl font-bold text-white uppercase">Redireccion</th>
                        <th className="px-4 py-3 text-center text-xl font-bold text-white uppercase">Muestras</th>
                        <th className="px-4 py-3 text-center text-xl font-bold text-white uppercase">Errores</th>
                        <th className="px-4 py-3 text-center text-xl font-bold text-white uppercase">% Error</th>
                        <th className="px-4 py-3 text-center text-xl font-bold text-white uppercase">Promedio</th>
                        <th className="px-4 py-3 text-center text-xl font-bold text-white uppercase">P90</th>
                        <th className="px-4 py-3 text-center text-xl font-bold text-white uppercase">P95</th>
                        <th className="px-4 py-3 text-center text-xl font-bold text-white uppercase">P99</th>
                        <th className="px-4 py-3 text-center text-xl font-bold text-white uppercase">Min</th>
                        <th className="px-4 py-3 text-center text-xl font-bold text-white uppercase">Max</th>
                        <th className="px-4 py-3 text-center text-xl font-bold text-white uppercase">TPS</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-100">
                      {charts.by_label_redirects.map((row: any, idx: number) => (
                        <tr key={idx} className="hover:bg-orange-50/50 transition-colors">
                          <td className="px-4 py-3 text-xl font-medium text-gray-900">{row.label}</td>
                          <td className="px-4 py-3 text-xl text-center text-gray-700">{row.count.toLocaleString()}</td>
                          <td className="px-4 py-3 text-xl text-center text-red-600 font-semibold">{(row.error_count ?? 0).toLocaleString()}</td>
                          <td className="px-4 py-3 text-xl text-center font-semibold text-gray-700">{(row.error_rate ?? 0).toFixed(2)}%</td>
                          <td className="px-4 py-3 text-xl text-center text-gray-700">{row.avg_time.toFixed(2)}</td>
                          <td className="px-4 py-3 text-xl text-center text-gray-700">{(row.p90 ?? 0).toFixed(2)}</td>
                          <td className="px-4 py-3 text-xl text-center text-gray-700">{(row.p95 ?? 0).toFixed(2)}</td>
                          <td className="px-4 py-3 text-xl text-center text-gray-700">{(row.p99 ?? 0).toFixed(2)}</td>
                          <td className="px-4 py-3 text-xl text-center text-gray-700">{row.min_time.toFixed(2)}</td>
                          <td className="px-4 py-3 text-xl text-center text-gray-700">{row.max_time.toFixed(2)}</td>
                          <td className="px-4 py-3 text-xl text-center text-blue-700 font-semibold">{(row.throughput ?? 0).toFixed(2)}</td>
                        </tr>
                      ))}
                      <tr className="bg-[#0a1628] text-white font-bold">
                        <td className="px-4 py-3 text-xl">TOTAL REDIRECCIONES</td>
                        <td className="px-4 py-3 text-xl text-center">{(charts.total_all_samples - charts.total_main_samples).toLocaleString()}</td>
                        <td colSpan={9} className="px-4 py-3 text-xl text-center text-orange-200">Total con redirecciones: {charts.total_all_samples?.toLocaleString() || '--'}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
              <div className="mt-4 bg-white rounded-2xl shadow-lg p-6 border-l-4 border-orange-500 border border-gray-200">
                <h3 className="text-3xl font-bold text-orange-600 mb-3">Analisis de Redirecciones</h3>
                <span className="text-xs text-gray-400 italic mb-1 block">Click para editar</span>
                <EditableTextArea initialValue={analysisRedirects} onSave={emitEdit('ai_analysis_redirects', setAnalysisRedirects)} placeholder="Analisis de redirecciones..." debounceMs={autoSaveMs} />
              </div>
            </div>
          )}
        </div>

        {/* ANALISIS DE ERRORES */}
        {errorData.length > 0 && (
          <div className="mb-8">
            <div className="bg-[#0a1628] rounded-t-2xl px-6 py-4">
              <h2 className="text-3xl font-bold text-white">Analisis de Errores</h2>
            </div>
            <div className="bg-white rounded-b-2xl shadow-lg p-6 border border-gray-200 border-t-0">
              <div className="mb-6 bg-red-50 border-2 border-red-200 rounded-xl p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-2xl text-red-700 font-semibold">Total de Errores Detectados</p>
                    <p className="text-6xl font-bold text-red-900 mt-1">{execution.total_errors.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-2xl text-red-700 font-semibold">Tasa de Error General</p>
                    <p className="text-6xl font-bold text-red-900 mt-1">{execution.error_rate.toFixed(2)}%</p>
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div>
                  <h3 className="text-3xl font-bold text-gray-800 mb-4">Distribucion de Codigos de Error</h3>
                  <ResponsiveContainer width="100%" height={500}>
                    <PieChart>
                      <Pie
                        data={Object.entries(charts.response_codes || {}).map(([code, count]) => ({ name: code, value: count as number }))}
                        cx="50%"
                        cy="45%"
                        outerRadius="65%"
                        dataKey="value"
                        label={({ name, percent, x, y, midAngle }) => {
                          if (percent < 0.03) return null;
                          const RADIAN = Math.PI / 180;
                          const radius = 20;
                          const cx2 = x + Math.cos(-midAngle * RADIAN) * radius;
                          const cy2 = y + Math.sin(-midAngle * RADIAN) * radius;
                          return (
                            <text x={cx2} y={cy2} textAnchor={cx2 > 200 ? 'start' : 'end'} dominantBaseline="central" fontSize={14} fill="#374151">
                              {`${name}: ${(percent * 100).toFixed(1)}%`}
                            </text>
                          );
                        }}
                        labelLine
                      >
                        {Object.keys(charts.response_codes || {}).map((code, index) => (<Cell key={`cell-${index}`} fill={getCodeColor(code)} />))}
                      </Pie>
                      <Tooltip formatter={(value: number) => value.toLocaleString()} />
                      <Legend
                        layout="horizontal"
                        verticalAlign="bottom"
                        align="center"
                        formatter={(value: string) => {
                          const total = Object.values(charts.response_codes || {}).reduce((sum: number, v: any) => sum + (v as number), 0);
                          const count = (charts.response_codes || {})[value] || 0;
                          const pct = total > 0 ? ((count as number) / (total as number) * 100).toFixed(1) : '0';
                          return `${value}: ${pct}%`;
                        }}
                        wrapperStyle={{ fontSize: '14px', paddingTop: '10px' }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div>
                  <h3 className="text-3xl font-bold text-gray-800 mb-4">Detalle de Errores por Transaccion</h3>
                  <div className="overflow-auto max-h-[400px]">
                    <table className="w-full">
                      <thead className="bg-[#0a1628] sticky top-0">
                        <tr>
                          <th className="px-4 py-3 text-left text-xl font-bold text-white">Transaccion</th>
                          <th className="px-4 py-3 text-left text-xl font-bold text-white">Codigo</th>
                          <th className="px-4 py-3 text-left text-xl font-bold text-white">Errores</th>
                          <th className="px-4 py-3 text-left text-xl font-bold text-white">%</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {errorData.map((error: any, idx: number) => (
                          <tr key={idx} className="hover:bg-red-50">
                            <td className="px-4 py-3 text-xl text-gray-900">{error.name}</td>
                            <td className="px-4 py-3 text-xl font-mono text-red-600">{error.code}</td>
                            <td className="px-4 py-3 text-xl font-semibold text-red-600">{error.value.toLocaleString()}</td>
                            <td className="px-4 py-3 text-xl font-bold text-red-600">{error.percentage}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
            <div className="mt-4 bg-white rounded-2xl shadow-lg p-6 border-l-4 border-orange-500 border border-gray-200">
              <h3 className="text-3xl font-bold text-orange-600 mb-3">Analisis de Errores</h3>
              <span className="text-xs text-gray-400 italic mb-1 block">Click para editar</span>
              <EditableTextArea initialValue={analysisErrors} onSave={emitEdit('ai_analysis_errors', setAnalysisErrors)} placeholder="Analisis de errores..." debounceMs={autoSaveMs} />
            </div>
          </div>
        )}

        {/* GRAFICOS DE PERFORMANCE — KNX-10: Collapsible */}
        <div className="mb-8">
          <div className="bg-[#0a1628] rounded-t-2xl px-6 py-4 flex items-center justify-between">
            <button onClick={() => setChartsExpanded(!chartsExpanded)} className="flex items-center gap-3 text-white hover:text-[#f5a623] transition-colors">
              <span className={`transform transition-transform text-2xl ${chartsExpanded ? 'rotate-90' : ''}`}>&#9654;</span>
              <h2 className="text-3xl font-bold">Graficos de Performance</h2>
              <span className="text-lg text-white/50">(7 graficas)</span>
            </button>
            {chartsExpanded && (
              <div className="flex gap-2">
                <button onClick={() => setTimeMode('elapsed')} className={`px-5 py-2.5 rounded-xl font-bold text-xl transition-all ${timeMode === 'elapsed' ? 'bg-sqa-gold text-sqa-navy shadow-lg' : 'bg-white/10 text-white hover:bg-white/20'}`}>
                  Tiempo Transcurrido
                </button>
                <button onClick={() => setTimeMode('real')} className={`px-5 py-2.5 rounded-xl font-bold text-xl transition-all ${timeMode === 'real' ? 'bg-sqa-gold text-sqa-navy shadow-lg' : 'bg-white/10 text-white hover:bg-white/20'}`}>
                  Hora Real
                </button>
              </div>
            )}
          </div>

          {chartsExpanded && (
            <ReportBody scope={{ kind: 'general' }} ctx={{
              responseTimesByLabel, rtMaxKeys, rtMaxLabels, throughputData, latencyData,
              errorRateData, codesPerSecond, tpsByLabel, activeThreadsData,
              analysisResponseTimes, setAnalysisResponseTimes,
              analysisThroughput, setAnalysisThroughput,
              analysisLatency, setAnalysisLatency,
              analysisErrorRate, setAnalysisErrorRate,
              analysisCodesPerSecond, setAnalysisCodesPerSecond,
              analysisTransactionsPerSecond, setAnalysisTransactionsPerSecond,
              analysisActiveThreads, setAnalysisActiveThreads,
              hiddenLinesResponseTimes, setHiddenLinesResponseTimes,
              hiddenLinesTPS, setHiddenLinesTPS,
              hiddenLinesCodes, setHiddenLinesCodes,
              minH, emitEdit, getYDomain, extractY, handleYRange, AnalysisBox, handleLegendClick,
            }} />
          )}
        </div>

        {/* N4.7: el informe de cada transaccion critica. ETAPA 2 (D17): va AQUI,
            entre el informe general y las conclusiones — v1.2 §1 pone las
            conclusiones una sola vez y al final, sobre toda la prueba. Antes se
            montaba despues de ellas. El componente decide si hay algo que mostrar. */}
        {!embedded && <TransactionReportSection executionId={executionId} />}

        {/* CONCLUSIONES Y RECOMENDACIONES — hidden when embedded in integrated report */}
        {!embedded && (
        <div className="mb-8">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-2xl shadow-lg overflow-hidden border border-gray-200">
              <div className="bg-[#0a1628] px-6 py-4">
                <h2 className="text-3xl font-bold text-white">Conclusiones</h2>
              </div>
              <div className="p-6">
                <span className="text-xs text-gray-400 italic mb-1 block">Click para editar</span>
                <EditableTextArea initialValue={conclusions} onSave={(v) => { setConclusions(v); queueSave('ai_conclusions', v); }} debounceMs={autoSaveMs} placeholder="Escribe las conclusiones generales de la prueba de performance..." minHeight="320px" className="w-full p-4 border-2 border-gray-300 rounded-xl text-xl text-gray-800 focus:ring-2 focus:ring-sqa-gold/50 focus:border-sqa-gold resize-y cursor-text hover:border-yellow-300 transition-colors" />
              </div>
            </div>
            <div className="bg-white rounded-2xl shadow-lg overflow-hidden border border-gray-200">
              <div className="bg-gradient-to-r from-green-600 to-teal-600 px-6 py-4">
                <h2 className="text-3xl font-bold text-white">Recomendaciones</h2>
              </div>
              <div className="p-6">
                <span className="text-xs text-gray-400 italic mb-1 block">Click para editar</span>
                <EditableTextArea initialValue={recommendations} onSave={(v) => { setRecommendations(v); queueSave('ai_recommendations', v); }} debounceMs={autoSaveMs} placeholder="Escribe las recomendaciones para mejorar el performance del sistema..." minHeight="320px" className="w-full p-4 border-2 border-gray-300 rounded-xl text-xl text-gray-800 focus:ring-2 focus:ring-green-400/50 focus:border-green-400 resize-y cursor-text hover:border-green-300 transition-colors" />
              </div>
            </div>
          </div>
        </div>
        )}

        {/* PDF PROGRESS */}
        {isExportingPDF && (
          <div className="mb-6 p-5 bg-blue-50 border-2 border-blue-200 rounded-2xl">
            <div className="flex items-center gap-3 mb-2">
              <div className="animate-spin rounded-full h-7 w-7 border-b-2 border-blue-600"></div>
              <span className="text-blue-800 font-bold text-3xl">Generando PDF completo... {pdfProgress}%</span>
            </div>
            <div className="w-full bg-blue-200 rounded-full h-3 overflow-hidden">
              <div className="bg-blue-600 h-3 rounded-full transition-all duration-300" style={{ width: `${pdfProgress}%` }}></div>
            </div>
            <div className="mt-2 text-xl text-blue-700">
              {pdfProgress < 30 && 'Preparando contenido...'}
              {pdfProgress >= 30 && pdfProgress < 60 && 'Capturando graficas...'}
              {pdfProgress >= 60 && pdfProgress < 90 && 'Generando documento...'}
              {pdfProgress >= 90 && 'Finalizando...'}
            </div>
          </div>
        )}

        {/* R1: indicador fijo de autoguardado — mismo patron que el integrado (F3) */}
        {!embedded && (
          <div className="fixed bottom-6 right-6 z-40 flex items-center gap-3 bg-white/95 backdrop-blur border border-gray-200 shadow-xl rounded-2xl px-4 py-3">
            <span className={`text-sm font-medium ${saveState === 'error' ? 'text-red-600' : saveState === 'saving' ? 'text-gray-500' : saveState === 'saved' ? 'text-emerald-700' : 'text-gray-400'}`}>
              {saveState === 'saving' ? 'Guardando...' : saveState === 'saved' ? `Guardado ${savedAt}` : saveState === 'error' ? 'Error al guardar' : 'Autoguardado activo'}
            </span>
            {saveState === 'error' && (
              <button onClick={flushSave}
                className="px-3 py-1.5 bg-red-600 text-white text-sm font-semibold rounded-lg hover:bg-red-700 transition-colors">
                Reintentar
              </button>
            )}
          </div>
        )}

        {/* ACTION BUTTONS — hidden when embedded in integrated report */}
        {!embedded && <div className="export-buttons flex justify-center gap-5 mb-8">
          <button onClick={handleSaveChanges} disabled={saving || isExportingPDF} className="flex items-center gap-3 px-10 py-4 bg-gradient-to-r from-green-600 to-green-700 text-white text-xl font-bold rounded-2xl shadow-lg hover:from-green-700 hover:to-green-800 transition-all disabled:opacity-50">
            <Save className="w-7 h-7" />
            {saving ? 'Guardando...' : 'Guardar Todos los Cambios'}
          </button>
          <button onClick={handleExportHTML} disabled={isExportingPDF} className="flex items-center gap-3 px-10 py-4 bg-sqa-gold text-sqa-navy text-xl font-bold rounded-2xl shadow-lg hover:bg-sqa-gold-light transition-all disabled:opacity-50">
            <FileCode className="w-7 h-7" />
            Exportar HTML
          </button>
          <button onClick={handleExportPDF} disabled={isExportingPDF} className="flex items-center gap-3 px-10 py-4 bg-sqa-gold text-sqa-navy text-xl font-bold rounded-2xl shadow-lg hover:bg-sqa-gold-light transition-all disabled:opacity-50 relative overflow-hidden">
            {isExportingPDF ? (
              <><div className="animate-spin rounded-full h-7 w-7 border-b-2 border-sqa-navy"></div><span>Generando... {pdfProgress}%</span></>
            ) : (
              <><FileDown className="w-7 h-7" /><span>Exportar PDF</span></>
            )}
          </button>
        </div>}

        {!embedded && (
        <div className="text-center text-gray-500 text-xl py-8 border-t border-gray-200">
          <p className="font-semibold text-2xl">sqa<span className="text-sqa-gold">_</span> Software Quality Assurance</p>
          <p className="text-lg mt-2 italic">Del pasado aprendimos, En el presente construimos, Para el futuro nos preparamos</p>
        </div>
        )}
      </div>
    </div>
    </>
  );
}
