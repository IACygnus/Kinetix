/**
 * ExecutionReportSection — Full report for ONE execution inside integrated report.
 * Shows KPIs, charts (collapsible), AI analysis (editable), verdicts.
 */
import { useState, useEffect } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { testAPI } from '../../services/api';

interface Props {
  executionId: string;
  onAnalysisEdit?: (execId: string, field: string, value: string) => void;
}

const AI_SECTIONS = [
  { key: 'ai_analysis_summary', label: 'Resumen General' },
  { key: 'ai_analysis_errors', label: 'Analisis de Errores' },
  { key: 'ai_analysis_response_times', label: 'Tiempos de Respuesta' },
  { key: 'ai_analysis_throughput', label: 'Throughput' },
  { key: 'ai_analysis_latency', label: 'Latencia' },
  { key: 'ai_analysis_error_rate', label: 'Tasa de Error' },
  { key: 'ai_analysis_codes_per_second', label: 'Codigos por Segundo' },
  { key: 'ai_analysis_transactions_per_second', label: 'Transacciones por Segundo' },
  { key: 'ai_analysis_active_threads', label: 'Threads Activos' },
  { key: 'ai_conclusions', label: 'Conclusiones' },
  { key: 'ai_recommendations', label: 'Recomendaciones' },
];

export default function ExecutionReportSection({ executionId, onAnalysisEdit }: Props) {
  const [execution, setExecution] = useState<any>(null);
  const [charts, setCharts] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [chartsExpanded, setChartsExpanded] = useState(false);
  const [editedFields, setEditedFields] = useState<Record<string, string>>({});

  useEffect(() => {
    const load = async () => {
      try {
        const [execRes, chartsRes] = await Promise.all([
          testAPI.getExecution(executionId),
          testAPI.getCharts(executionId),
        ]);
        setExecution(execRes);
        setCharts(chartsRes);
      } catch (err) {
        console.error('Error loading execution:', err);
      }
      setLoading(false);
    };
    load();
  }, [executionId]);

  if (loading) return <div className="text-center py-8 text-gray-400 text-lg">Cargando datos de la ejecucion...</div>;
  if (!execution) return <div className="text-center py-8 text-red-400 text-lg">Error al cargar ejecucion {executionId}</div>;

  const verdict = execution.acceptance_criteria_json?.verdict;
  const verdictColor = verdict === 'APTO' ? 'text-green-600 bg-green-50' : verdict === 'NO APTO' ? 'text-red-600 bg-red-50' : 'text-yellow-600 bg-yellow-50';

  // Prepare chart data (simplified from Dashboard)
  const prepareTimeline = (data: any[]) => {
    if (!data?.length) return [];
    const start = new Date(data[0].timestamp).getTime();
    return data.map((d: any) => {
      const elapsed = Math.floor((new Date(d.timestamp).getTime() - start) / 1000);
      const m = Math.floor(elapsed / 60);
      const s = elapsed % 60;
      return { ...d, time: `${m}:${String(s).padStart(2, '0')}` };
    });
  };

  const timeline = prepareTimeline(charts?.timeline || []);

  const handleFieldEdit = (field: string, value: string) => {
    setEditedFields(prev => ({ ...prev, [field]: value }));
    onAnalysisEdit?.(executionId, field, value);
  };

  const getFieldValue = (field: string) => editedFields[field] ?? execution[field] ?? '';

  return (
    <div className="bg-white rounded-2xl shadow-lg border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="bg-[#0a1628] px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-white">{execution.name}</h2>
            <p className="text-sm text-white/60">
              {(execution.test_type || 'load').toUpperCase()} — {execution.client || 'N/A'} — {execution.start_time ? new Date(execution.start_time).toLocaleString('es-CO') : ''}
            </p>
          </div>
          {verdict && (
            <span className={`px-4 py-1.5 rounded-full text-lg font-bold uppercase ${verdictColor}`}>{verdict}</span>
          )}
        </div>
      </div>

      <div className="p-6">
        {/* KPI Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          {[
            { label: 'Total Requests', value: execution.total_requests?.toLocaleString(), color: 'border-blue-500' },
            { label: 'Error Rate', value: `${(execution.error_rate || 0).toFixed(2)}%`, color: execution.error_rate > 1 ? 'border-red-500' : 'border-green-500' },
            { label: 'Avg Response Time', value: `${(execution.avg_response_time || 0).toFixed(0)} ms`, color: 'border-green-500' },
            { label: 'Throughput', value: `${(execution.throughput || 0).toFixed(2)} req/s`, color: 'border-purple-500' },
            { label: 'P90', value: `${(execution.p90_response_time || 0).toFixed(0)} ms`, color: 'border-amber-500' },
            { label: 'P95', value: `${(execution.p95_response_time || 0).toFixed(0)} ms`, color: 'border-orange-500' },
            { label: 'P99', value: `${(execution.p99_response_time || 0).toFixed(0)} ms`, color: 'border-red-500' },
            { label: 'Duracion', value: execution.duration_seconds ? `${Math.floor(execution.duration_seconds / 60)}m ${Math.floor(execution.duration_seconds % 60)}s` : '--', color: 'border-cyan-500' },
          ].map((kpi, i) => (
            <div key={i} className={`bg-white rounded-xl p-3 border-l-4 ${kpi.color} border border-gray-200 shadow-sm`}>
              <p className="text-xs text-gray-500 uppercase">{kpi.label}</p>
              <p className="text-xl font-bold text-gray-800 mt-1">{kpi.value}</p>
            </div>
          ))}
        </div>

        {/* Charts (collapsible) */}
        <button onClick={() => setChartsExpanded(!chartsExpanded)}
          className="flex items-center gap-2 text-sm text-[#f5a623] font-medium mb-3 hover:text-[#f5a623]/80">
          {chartsExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          {chartsExpanded ? 'Ocultar graficas' : 'Mostrar graficas'} ({timeline.length} puntos)
        </button>

        {chartsExpanded && timeline.length > 0 && (
          <div className="space-y-4 mb-6">
            {/* Response Time */}
            <div className="border border-gray-100 rounded-xl p-3">
              <h4 className="text-sm font-bold text-gray-700 mb-2">Response Time Over Time</h4>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={timeline}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis dataKey="time" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} tickCount={8} />
                  <Tooltip />
                  <Area type="monotone" dataKey="avg_response_time" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.15} strokeWidth={1.5} isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Throughput */}
            <div className="border border-gray-100 rounded-xl p-3">
              <h4 className="text-sm font-bold text-gray-700 mb-2">Throughput</h4>
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={prepareTimeline(charts?.throughput_timeline || [])}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis dataKey="time" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} tickCount={8} />
                  <Tooltip />
                  <Area type="monotone" dataKey="value" stroke="#10b981" fill="#10b981" fillOpacity={0.15} strokeWidth={1.5} isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Error Rate */}
            <div className="border border-gray-100 rounded-xl p-3">
              <h4 className="text-sm font-bold text-gray-700 mb-2">Error Rate</h4>
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={prepareTimeline(charts?.error_rate_timeline || [])}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis dataKey="time" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} tickCount={8} />
                  <Tooltip />
                  <Area type="monotone" dataKey="value" stroke="#ef4444" fill="#ef4444" fillOpacity={0.15} strokeWidth={1.5} isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* AI Analysis sections */}
        <div className="space-y-3">
          {AI_SECTIONS.map(({ key, label }) => {
            const val = getFieldValue(key);
            if (!val) return null;
            return (
              <div key={key} className="border border-gray-200 rounded-xl overflow-hidden">
                <div className="px-3 py-2 bg-orange-50 border-b border-orange-100">
                  <span className="text-sm font-semibold text-orange-700">{label}</span>
                </div>
                <textarea
                  value={val}
                  onChange={(e) => handleFieldEdit(key, e.target.value)}
                  className="w-full min-h-[80px] p-3 border-0 text-sm text-gray-800 resize-y focus:ring-1 focus:ring-orange-300"
                />
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
