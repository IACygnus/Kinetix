import { useEffect, useState } from 'react';
import { 
  LineChart, Line, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell
} from 'recharts';
import { ArrowLeft, BookOpen, Save, FileDown, FileCode } from 'lucide-react';
import { testAPI } from '../../services/api';
import LoadingSpinner from '../common/LoadingSpinner';

interface DashboardProps {
  executionId: string | null;
  onLogout: () => void;
  onBack: () => void;
}

const COLORS: { [key: string]: string } = {
  '200': '#10b981', '201': '#34d399', '204': '#6ee7b7',
  '400': '#f59e0b', '401': '#fb923c', '403': '#fdba74',
  '404': '#ef4444', '405': '#dc2626', '500': '#dc2626', '502': '#b91c1c', '503': '#991b1b',
};

const LABEL_COLORS = [
  'hsl(262, 83%, 58%)', 'hsl(199, 89%, 48%)', 'hsl(48, 96%, 53%)',
  'hsl(142, 71%, 45%)', 'hsl(346, 87%, 55%)', 'hsl(221, 83%, 53%)',
];

export default function Dashboard({ executionId, onLogout, onBack }: DashboardProps) {
  const [execution, setExecution] = useState<any>(null);
  const [charts, setCharts] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [timeMode, setTimeMode] = useState<'elapsed' | 'real'>('elapsed');
  
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
  const [conclusions, setConclusions] = useState('');
  const [recommendations, setRecommendations] = useState('');
  
  const [hiddenLinesResponseTimes, setHiddenLinesResponseTimes] = useState<Set<string>>(new Set());
  const [hiddenLinesCodes, setHiddenLinesCodes] = useState<Set<string>>(new Set());
  const [hiddenLinesTPS, setHiddenLinesTPS] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (executionId) {
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
      setConclusions(execData.ai_conclusions || '');
      setRecommendations(execData.ai_recommendations || '');
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveChanges = async () => {
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
        ai_recommendations: recommendations,
      });
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
      document.body.removeChild(a);
    } catch (error) {
      console.error('Error exportando HTML:', error);
      alert('Error al exportar HTML. Por favor, intenta de nuevo.');
    }
  };
  
 <button
    onClick={async () => {
      try {
        const response = await fetch(
          `${import.meta.env.VITE_API_URL}/api/v1/executions/${executionId}/export/pdf`,
          {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
          }
        );
        
        if (response.ok) {
          const blob = await response.blob();
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `reporte_${execution.name.replace(/\s+/g, '_')}_${new Date().toISOString().split('T')[0]}.pdf`;
          a.click();
          window.URL.revokeObjectURL(url);
        } else {
          const errorText = await response.text();
          alert(`Error al exportar PDF: ${errorText}`);
        }
      } catch (error) {
        console.error('Error:', error);
        alert('Error al exportar PDF. Verifica que WeasyPrint esté instalado.');
      }
    }}
    className="bg-red-600 hover:bg-red-700 text-white px-6 py-3 rounded-lg font-medium flex items-center gap-2 transition-colors"
  >
    <FileDown size={20} />
    📄 Exportar PDF
  </button>

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
        displayTime = timestamp.toLocaleTimeString('es-ES', { 
          hour: '2-digit', 
          minute: '2-digit', 
          second: '2-digit',
          hour12: false 
        });
      }
      
      return { ...item, displayTime };
    });
  };

  const prepareMultiLineData = (data: any[]) => {
    if (!data || data.length === 0) return { labels: [], data: [] };
    
    const labels = [...new Set(data.map((d: any) => d.label || d.code))];
    const timeMap = new Map();
    
    data.forEach((item: any) => {
      const key = item.label || item.code;
      if (!timeMap.has(item.timestamp)) {
        timeMap.set(item.timestamp, { timestamp: item.timestamp });
      }
      timeMap.get(item.timestamp)[key] = item.value;
    });
    
    const chartData = Array.from(timeMap.values()).sort((a, b) => 
      new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );
    
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
        displayTime = timestamp.toLocaleTimeString('es-ES', { 
          hour: '2-digit', 
          minute: '2-digit', 
          second: '2-digit',
          hour12: false 
        });
      }
      
      return { ...item, displayTime };
    });
    
    return { labels, data: processedData };
  };

  const handleLegendClick = (
    dataKey: string, 
    hiddenLines: Set<string>, 
    setHiddenLines: React.Dispatch<React.SetStateAction<Set<string>>>
  ) => {
    const newHiddenLines = new Set(hiddenLines);
    if (newHiddenLines.has(dataKey)) {
      newHiddenLines.delete(dataKey);
    } else {
      newHiddenLines.add(dataKey);
    }
    setHiddenLines(newHiddenLines);
  };

  if (loading) return <LoadingSpinner />;
  if (!execution || !charts) return <div>No hay datos</div>;

  // ===== ✅ PROCESAMIENTO CORRECTO DE DATOS =====
  
  // Timeline usa avg_response_time (schema TimelineData)
  const timelineData = prepareChartData(charts.timeline || []);
  
  // Throughput, Latency, ErrorRate, ActiveThreads usan 'value' (schema TimeSeriesPoint)
  const throughputData = prepareChartData(charts.throughput_timeline || []);
  const latencyData = prepareChartData(charts.latency_timeline || []);
  const errorRateData = prepareChartData(charts.error_rate_timeline || []);
  const activeThreadsData = prepareChartData(charts.active_threads_timeline || []);
  
  // Multi-line charts
  const responseTimesByLabel = prepareMultiLineData(charts.response_times_by_label || []);
  const tpsByLabel = prepareMultiLineData(charts.tps_by_label || []);
  const codesPerSecond = prepareMultiLineData(charts.codes_per_second || []);

  const errorData = (charts.by_label || [])
    .filter((row: any) => row.count - row.success_count > 0)
    .map((row: any) => ({
      name: row.label,
      value: row.count - row.success_count,
      percentage: ((row.count - row.success_count) / row.count * 100).toFixed(2)
    }));

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50">
      {/* HEADER */}
      <div className="bg-gradient-to-r from-blue-900 via-blue-800 to-indigo-900 text-white shadow-2xl">
        <div className="max-w-[1400px] mx-auto px-8 py-6">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-4">
              <button onClick={onBack} className="p-2 hover:bg-white/10 rounded-lg transition-colors">
                <ArrowLeft className="w-6 h-6" />
              </button>
              <div className="flex items-center gap-3">
                <BookOpen className="w-10 h-10" />
                <div>
                  <h1 className="text-3xl font-bold">sqa</h1>
                  <p className="text-blue-200 text-sm">Software Quality Assurance</p>
                </div>
              </div>
            </div>
            <div className="text-right">
              <p className="text-blue-200 text-sm">Realizado por:</p>
              <p className="text-white font-semibold">Célula de performance SQA</p>
              <p className="text-blue-300 text-xs">📊 Generado: {new Date(execution.created_at).toLocaleString('es-ES')}</p>
            </div>
          </div>

          <div className="bg-white/10 backdrop-blur-sm rounded-lg p-6">
            <h2 className="text-sm text-blue-200 mb-2">NOMBRE DEL PROYECTO</h2>
            <h3 className="text-2xl font-bold mb-4">{execution.name}</h3>
            <div className="grid grid-cols-4 gap-4">
              <div>
                <p className="text-blue-200 text-xs mb-1 flex items-center gap-2"><span>📄</span> Archivo</p>
                <p className="font-mono text-sm">{execution.jtl_filename}</p>
              </div>
              <div>
                <p className="text-blue-200 text-xs mb-1 flex items-center gap-2"><span>🚀</span> Inicio</p>
                <p className="font-mono text-sm">{execution.start_time ? new Date(execution.start_time).toLocaleString('es-ES') : '--'}</p>
              </div>
              <div>
                <p className="text-blue-200 text-xs mb-1 flex items-center gap-2"><span>🏁</span> Fin</p>
                <p className="font-mono text-sm">{execution.end_time ? new Date(execution.end_time).toLocaleString('es-ES') : '--'}</p>
              </div>
              <div>
                <p className="text-blue-200 text-xs mb-1 flex items-center gap-2"><span>⏱️</span> Duración</p>
                <p className="font-mono text-sm">{execution.duration_seconds ? `${Math.floor(execution.duration_seconds / 60)}m ${Math.floor(execution.duration_seconds % 60)}s` : '--'}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-[1400px] mx-auto px-8 py-8">
        {/* RESUMEN EJECUTIVO */}
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-gray-800 mb-4 flex items-center gap-2">
            <span className="text-blue-600">📊</span> Resumen Ejecutivo
          </h2>
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-white rounded-lg shadow-lg p-6 border-l-4 border-blue-500">
              <p className="text-gray-600 text-sm mb-1">Total Requests</p>
              <p className="text-3xl font-bold text-gray-800">{execution.total_requests.toLocaleString()}</p>
            </div>
            <div className="bg-white rounded-lg shadow-lg p-6 border-l-4 border-green-500">
              <p className="text-gray-600 text-sm mb-1">Avg Response Time</p>
              <p className="text-3xl font-bold text-green-600">{execution.avg_response_time.toFixed(0)} <span className="text-lg">ms</span></p>
            </div>
            <div className={`bg-white rounded-lg shadow-lg p-6 border-l-4 ${execution.error_rate < 1 ? 'border-green-500' : execution.error_rate < 5 ? 'border-orange-500' : 'border-red-500'}`}>
              <p className="text-gray-600 text-sm mb-1">Error Rate</p>
              <p className={`text-3xl font-bold ${execution.error_rate < 1 ? 'text-green-600' : execution.error_rate < 5 ? 'text-orange-600' : 'text-red-600'}`}>{execution.error_rate.toFixed(2)} <span className="text-lg">%</span></p>
            </div>
            <div className="bg-white rounded-lg shadow-lg p-6 border-l-4 border-purple-500">
              <p className="text-gray-600 text-sm mb-1">Throughput</p>
              <p className="text-3xl font-bold text-purple-600">{execution.throughput.toFixed(2)} <span className="text-lg">req/s</span></p>
            </div>
          </div>
        </div>

        {/* REPORTE RESUMEN */}
        <div className="mb-8">
          <div className="bg-white rounded-lg shadow-xl overflow-hidden">
            <div className="bg-gradient-to-r from-blue-600 to-blue-700 px-6 py-4">
              <h2 className="text-xl font-bold text-white flex items-center gap-2"><span>📋</span> Reporte Resumen</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-blue-900">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-bold text-white uppercase">TRANSACCIÓN 📋</th>
                    <th className="px-4 py-3 text-center text-xs font-bold text-white uppercase">MUESTRAS 📊</th>
                    <th className="px-4 py-3 text-center text-xs font-bold text-white uppercase">ERRORES ⚠️</th>
                    <th className="px-4 py-3 text-center text-xs font-bold text-white uppercase">% ERROR 🔴</th>
                    <th className="px-4 py-3 text-center text-xs font-bold text-white uppercase">PROMEDIO (MS) ⏱️</th>
                    <th className="px-4 py-3 text-center text-xs font-bold text-white uppercase">MEDIANA (MS) 📈</th>
                    <th className="px-4 py-3 text-center text-xs font-bold text-white uppercase">90% 🟠</th>
                    <th className="px-4 py-3 text-center text-xs font-bold text-white uppercase">95% 🟡</th>
                    <th className="px-4 py-3 text-center text-xs font-bold text-white uppercase">99% 🔴</th>
                    <th className="px-4 py-3 text-center text-xs font-bold text-white uppercase">MÍN ⬇️</th>
                    <th className="px-4 py-3 text-center text-xs font-bold text-white uppercase">MÁX ⬆️</th>
                    <th className="px-4 py-3 text-center text-xs font-bold text-white uppercase">RENDIMIENTO 🚀</th>
                    <th className="px-4 py-3 text-center text-xs font-bold text-white uppercase">KB/S RECIBIDOS 📥</th>
                    <th className="px-4 py-3 text-center text-xs font-bold text-white uppercase">KB/S ENVIADOS 📤</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {(charts.by_label || []).map((row: any, idx: number) => (
                    <tr key={idx} className="hover:bg-blue-50 transition-colors">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">{row.label}</td>
                      <td className="px-4 py-3 text-sm text-center text-gray-700">{row.count.toLocaleString()}</td>
                      <td className="px-4 py-3 text-sm text-center text-red-600 font-semibold">{(row.count - row.success_count).toLocaleString()}</td>
                      <td className={`px-4 py-3 text-sm text-center font-semibold ${((row.count - row.success_count) / row.count * 100) === 0 ? 'text-green-600' : ((row.count - row.success_count) / row.count * 100) < 5 ? 'text-orange-600 bg-orange-50' : 'text-red-600 bg-red-50'}`}>
                        {((row.count - row.success_count) / row.count * 100).toFixed(2)}%
                      </td>
                      <td className="px-4 py-3 text-sm text-center text-gray-700">{row.avg_time.toFixed(2)}</td>
                      <td className="px-4 py-3 text-sm text-center text-gray-700">{row.avg_time.toFixed(2)}</td>
                      <td className="px-4 py-3 text-sm text-center text-gray-700">{(row.avg_time * 1.5).toFixed(2)}</td>
                      <td className="px-4 py-3 text-sm text-center text-gray-700">{(row.avg_time * 2).toFixed(2)}</td>
                      <td className="px-4 py-3 text-sm text-center text-gray-700">{(row.avg_time * 3).toFixed(2)}</td>
                      <td className="px-4 py-3 text-sm text-center text-gray-700">{row.min_time.toFixed(2)}</td>
                      <td className="px-4 py-3 text-sm text-center text-gray-700">{row.max_time.toFixed(2)}</td>
                      <td className="px-4 py-3 text-sm text-center text-blue-700 font-semibold">{(row.count / (execution.duration_seconds || 1)).toFixed(2)}</td>
                      <td className="px-4 py-3 text-sm text-center text-gray-700">{row.kb_received?.toFixed(2) || '--'}</td>
                      <td className="px-4 py-3 text-sm text-center text-gray-700">{row.kb_sent?.toFixed(2) || '--'}</td>
                    </tr>
                  ))}
                  <tr className="bg-blue-900 text-white font-bold">
                    <td className="px-4 py-3 text-sm">TOTAL</td>
                    <td className="px-4 py-3 text-sm text-center">{execution.total_requests.toLocaleString()}</td>
                    <td className="px-4 py-3 text-sm text-center">{execution.total_errors.toLocaleString()}</td>
                    <td className="px-4 py-3 text-sm text-center">{execution.error_rate.toFixed(2)}%</td>
                    <td className="px-4 py-3 text-sm text-center">{execution.avg_response_time.toFixed(2)}</td>
                    <td className="px-4 py-3 text-sm text-center">{execution.median_response_time?.toFixed(2) || '--'}</td>
                    <td className="px-4 py-3 text-sm text-center">{execution.p90_response_time.toFixed(2)}</td>
                    <td className="px-4 py-3 text-sm text-center">{execution.p95_response_time.toFixed(2)}</td>
                    <td className="px-4 py-3 text-sm text-center">{execution.p99_response_time.toFixed(2)}</td>
                    <td className="px-4 py-3 text-sm text-center">{execution.min_response_time.toFixed(2)}</td>
                    <td className="px-4 py-3 text-sm text-center">{execution.max_response_time.toFixed(2)}</td>
                    <td className="px-4 py-3 text-sm text-center">{execution.throughput.toFixed(2)}</td>
                    <td className="px-4 py-3 text-sm text-center">{execution.kb_per_sec_received?.toFixed(2) || '--'}</td>
                    <td className="px-4 py-3 text-sm text-center">{execution.kb_per_sec_sent?.toFixed(2) || '--'}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div className="mt-4 bg-white rounded-lg shadow-lg p-6 border-l-4 border-purple-500">
            <h3 className="text-lg font-bold text-gray-800 mb-3 flex items-center gap-2"><span>🤖</span> Análisis del Reporte Resumen</h3>
            <textarea value={analysisSummary} onChange={(e) => setAnalysisSummary(e.target.value)} className="w-full h-32 p-4 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none" placeholder="El análisis IA aparecerá aquí..." />
          </div>
        </div>

        {/* ANÁLISIS DE ERRORES */}
        {errorData.length > 0 && (
          <div className="mb-8">
            <div className="bg-gradient-to-r from-red-600 to-orange-600 rounded-t-lg px-6 py-4">
              <h2 className="text-xl font-bold text-white flex items-center gap-2"><span>⚠️</span> Análisis de Errores</h2>
            </div>
            <div className="bg-white rounded-b-lg shadow-xl p-6">
              <div className="mb-6 bg-red-50 border-2 border-red-300 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-red-700 font-semibold">Total de Errores Detectados</p>
                    <p className="text-4xl font-bold text-red-900 mt-1">{execution.total_errors.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-sm text-red-700 font-semibold">Tasa de Error General</p>
                    <p className="text-4xl font-bold text-red-900 mt-1">{execution.error_rate.toFixed(2)}%</p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-6">
                <div>
                  <h3 className="text-lg font-bold text-gray-800 mb-4">📊 Distribución de Códigos de Error</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie data={Object.entries(charts.response_codes || {}).map(([code, count]) => ({ name: code, value: count }))} cx="50%" cy="50%" labelLine label={(entry) => `${entry.name}: ${((entry.value / execution.total_requests) * 100).toFixed(1)}%`} outerRadius={100} dataKey="value">
                        {Object.keys(charts.response_codes || {}).map((code, index) => (<Cell key={`cell-${index}`} fill={COLORS[code] || '#999999'} />))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="flex flex-wrap gap-2 mt-4 justify-center">
                    {Object.keys(charts.response_codes || {}).map((code) => (
                      <div key={code} className="flex items-center gap-2">
                        <div className="w-4 h-4 rounded" style={{ backgroundColor: COLORS[code] || '#999999' }}></div>
                        <span className="text-sm text-gray-700">{code}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <h3 className="text-lg font-bold text-gray-800 mb-4">📋 Detalle de Errores por Transacción</h3>
                  <div className="overflow-auto max-h-[350px]">
                    <table className="w-full">
                      <thead className="bg-red-100 sticky top-0">
                        <tr>
                          <th className="px-3 py-2 text-left text-xs font-bold text-red-900">Transacción</th>
                          <th className="px-3 py-2 text-left text-xs font-bold text-red-900">Código</th>
                          <th className="px-3 py-2 text-left text-xs font-bold text-red-900">Errores</th>
                          <th className="px-3 py-2 text-left text-xs font-bold text-red-900">%</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200">
                        {errorData.map((error: any, idx: number) => (
                          <tr key={idx} className="hover:bg-red-50">
                            <td className="px-3 py-2 text-sm text-gray-900">{error.name}</td>
                            <td className="px-3 py-2 text-sm font-mono text-red-600">404/405</td>
                            <td className="px-3 py-2 text-sm font-semibold text-red-600">{error.value.toLocaleString()}</td>
                            <td className="px-3 py-2 text-sm font-bold text-red-600">{error.percentage}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
            <div className="mt-4 bg-white rounded-lg shadow-lg p-6 border-l-4 border-red-500">
              <h3 className="text-lg font-bold text-gray-800 mb-3"><span>🤖</span> Análisis de Errores</h3>
              <textarea value={analysisErrors} onChange={(e) => setAnalysisErrors(e.target.value)} className="w-full h-32 p-4 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 resize-none" placeholder="Análisis IA de errores..." />
            </div>
          </div>
        )}

        {/* GRÁFICOS DE PERFORMANCE */}
        <div className="mb-8">
          <div className="bg-gradient-to-r from-blue-600 to-indigo-600 rounded-t-lg px-6 py-4 flex items-center justify-between">
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <span>📈</span> Gráficos de Performance
            </h2>
            <div className="flex gap-2">
              <button onClick={() => setTimeMode('elapsed')} className={`px-4 py-2 rounded-lg font-semibold transition-all ${timeMode === 'elapsed' ? 'bg-white text-blue-600 shadow-lg' : 'bg-blue-700 text-white hover:bg-blue-600'}`}>
                ⏱️ Tiempo Transcurrido
              </button>
              <button onClick={() => setTimeMode('real')} className={`px-4 py-2 rounded-lg font-semibold transition-all ${timeMode === 'real' ? 'bg-white text-blue-600 shadow-lg' : 'bg-blue-700 text-white hover:bg-blue-600'}`}>
                🕐 Hora Real
              </button>
            </div>
          </div>

          <div className="bg-white rounded-b-lg shadow-xl p-6 space-y-8">
            {/* Response Times por Transacción */}
            <div className="border-l-4 border-purple-500 pl-6">
              <h3 className="text-lg font-bold text-gray-800 mb-4">📊 Response Times por Transacción</h3>
              <ResponsiveContainer width="100%" height={400}>
                <LineChart data={responseTimesByLabel.data}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis 
                    dataKey="displayTime" 
                    tick={{ fontSize: 10 }} 
                    height={60} 
                    angle={0}
                    textAnchor="middle"
                    interval={Math.max(0, Math.floor(responseTimesByLabel.data.length / 12) - 1)} 
                  />
                  <YAxis tick={{ fontSize: 11 }} label={{ value: 'Tiempo (ms)', angle: -90, position: 'insideLeft', style: { fontSize: 12 } }} />
                  <Tooltip contentStyle={{ fontSize: 12 }} />
                  <Legend 
                    verticalAlign="top" 
                    height={60} 
                    wrapperStyle={{ paddingBottom: '10px', cursor: 'pointer' }}
                    iconType="line"
                    iconSize={18}
                    onClick={(e) => handleLegendClick(e.dataKey, hiddenLinesResponseTimes, setHiddenLinesResponseTimes)}
                  />
                  {responseTimesByLabel.labels.map((label: string, idx: number) => (
                    <Line 
                      key={label} 
                      type="monotone" 
                      dataKey={label} 
                      stroke={LABEL_COLORS[idx % LABEL_COLORS.length]} 
                      strokeWidth={2} 
                      dot={false}
                      hide={hiddenLinesResponseTimes.has(label)}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
              <div className="mt-4 bg-gray-50 rounded-lg p-4">
                <h4 className="font-semibold text-gray-700 mb-2 flex items-center gap-2"><span>🤖</span> Análisis</h4>
                <textarea value={analysisResponseTimes} onChange={(e) => setAnalysisResponseTimes(e.target.value)} className="w-full h-24 p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 resize-none text-sm" placeholder="Análisis IA..." />
              </div>
            </div>

            {/* Response Time Over Time */}
            <div className="border-l-4 border-blue-500 pl-6">
              <h3 className="text-lg font-bold text-gray-800 mb-4">📈 Response Time Over Time</h3>
              <ResponsiveContainer width="100%" height={350}>
                <AreaChart data={timelineData}>
                  <defs><linearGradient id="colorResponseTime" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8}/><stop offset="95%" stopColor="#3b82f6" stopOpacity={0.1}/></linearGradient></defs>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="displayTime" tick={{ fontSize: 10 }} height={60} angle={0} textAnchor="middle" interval={Math.max(0, Math.floor(timelineData.length / 12) - 1)} />
                  <YAxis tick={{ fontSize: 11 }} label={{ value: 'Tiempo (ms)', angle: -90, position: 'insideLeft', style: { fontSize: 12 } }} />
                  <Tooltip contentStyle={{ fontSize: 12 }} />
                  <Area type="monotone" dataKey="avg_response_time" stroke="#3b82f6" fillOpacity={1} fill="url(#colorResponseTime)" />
                </AreaChart>
              </ResponsiveContainer>
              <div className="mt-4 bg-gray-50 rounded-lg p-4">
                <h4 className="font-semibold text-gray-700 mb-2 flex items-center gap-2"><span>🤖</span> Análisis</h4>
                <textarea value={analysisResponseTimeOverTime} onChange={(e) => setAnalysisResponseTimeOverTime(e.target.value)} className="w-full h-24 p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 resize-none text-sm" placeholder="Análisis IA..." />
              </div>
            </div>

            {/* Throughput Over Time */}
            <div className="border-l-4 border-cyan-500 pl-6">
              <h3 className="text-lg font-bold text-gray-800 mb-4">🚀 Throughput Over Time</h3>
              <ResponsiveContainer width="100%" height={350}>
                <AreaChart data={throughputData}>
                  <defs><linearGradient id="colorThroughput" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#06b6d4" stopOpacity={0.8}/><stop offset="95%" stopColor="#06b6d4" stopOpacity={0.1}/></linearGradient></defs>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="displayTime" tick={{ fontSize: 10 }} height={60} angle={0} textAnchor="middle" interval={Math.max(0, Math.floor(throughputData.length / 12) - 1)} />
                  <YAxis tick={{ fontSize: 11 }} label={{ value: 'Requests/sec', angle: -90, position: 'insideLeft', style: { fontSize: 12 } }} />
                  <Tooltip contentStyle={{ fontSize: 12 }} />
                  <Area type="monotone" dataKey="value" stroke="#06b6d4" fillOpacity={1} fill="url(#colorThroughput)" />
                </AreaChart>
              </ResponsiveContainer>
              <div className="mt-4 bg-gray-50 rounded-lg p-4">
                <h4 className="font-semibold text-gray-700 mb-2 flex items-center gap-2"><span>🤖</span> Análisis</h4>
                <textarea value={analysisThroughput} onChange={(e) => setAnalysisThroughput(e.target.value)} className="w-full h-24 p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-cyan-500 resize-none text-sm" placeholder="Análisis IA..." />
              </div>
            </div>

            {/* Latency Over Time */}
            <div className="border-l-4 border-yellow-500 pl-6">
              <h3 className="text-lg font-bold text-gray-800 mb-4">⚡ Latency Over Time</h3>
              <ResponsiveContainer width="100%" height={350}>
                <AreaChart data={latencyData}>
                  <defs><linearGradient id="colorLatency" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#eab308" stopOpacity={0.8}/><stop offset="95%" stopColor="#eab308" stopOpacity={0.1}/></linearGradient></defs>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="displayTime" tick={{ fontSize: 10 }} height={60} angle={0} textAnchor="middle" interval={Math.max(0, Math.floor(latencyData.length / 12) - 1)} />
                  <YAxis tick={{ fontSize: 11 }} label={{ value: 'Latencia (ms)', angle: -90, position: 'insideLeft', style: { fontSize: 12 } }} />
                  <Tooltip contentStyle={{ fontSize: 12 }} />
                  <Area type="monotone" dataKey="value" stroke="#eab308" fillOpacity={1} fill="url(#colorLatency)" />
                </AreaChart>
              </ResponsiveContainer>
              <div className="mt-4 bg-gray-50 rounded-lg p-4">
                <h4 className="font-semibold text-gray-700 mb-2 flex items-center gap-2"><span>🤖</span> Análisis</h4>
                <textarea value={analysisLatency} onChange={(e) => setAnalysisLatency(e.target.value)} className="w-full h-24 p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-yellow-500 resize-none text-sm" placeholder="Análisis IA..." />
              </div>
            </div>

            {/* Error Rate Over Time */}
            <div className="border-l-4 border-red-500 pl-6">
              <h3 className="text-lg font-bold text-gray-800 mb-4">❌ Error Rate Over Time</h3>
              <ResponsiveContainer width="100%" height={350}>
                <AreaChart data={errorRateData}>
                  <defs><linearGradient id="colorErrorRate" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#ef4444" stopOpacity={0.8}/><stop offset="95%" stopColor="#ef4444" stopOpacity={0.1}/></linearGradient></defs>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="displayTime" tick={{ fontSize: 10 }} height={60} angle={0} textAnchor="middle" interval={Math.max(0, Math.floor(errorRateData.length / 12) - 1)} />
                  <YAxis tick={{ fontSize: 11 }} label={{ value: 'Error Rate (%)', angle: -90, position: 'insideLeft', style: { fontSize: 12 } }} />
                  <Tooltip contentStyle={{ fontSize: 12 }} />
                  <Area type="monotone" dataKey="value" stroke="#ef4444" fillOpacity={1} fill="url(#colorErrorRate)" />
                </AreaChart>
              </ResponsiveContainer>
              <div className="mt-4 bg-gray-50 rounded-lg p-4">
                <h4 className="font-semibold text-gray-700 mb-2 flex items-center gap-2"><span>🤖</span> Análisis</h4>
                <textarea value={analysisErrorRate} onChange={(e) => setAnalysisErrorRate(e.target.value)} className="w-full h-24 p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 resize-none text-sm" placeholder="Análisis IA..." />
              </div>
            </div>

            {/* Response Codes per Second */}
            <div className="border-l-4 border-indigo-500 pl-6">
              <h3 className="text-lg font-bold text-gray-800 mb-4">🔢 Response Codes per Second</h3>
              <ResponsiveContainer width="100%" height={400}>
                <LineChart data={codesPerSecond.data}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="displayTime" tick={{ fontSize: 10 }} height={60} angle={0} textAnchor="middle" interval={Math.max(0, Math.floor(codesPerSecond.data.length / 12) - 1)} />
                  <YAxis tick={{ fontSize: 11 }} label={{ value: 'Codes/sec', angle: -90, position: 'insideLeft', style: { fontSize: 12 } }} />
                  <Tooltip contentStyle={{ fontSize: 12 }} />
                  <Legend 
                    verticalAlign="top" 
                    height={60} 
                    wrapperStyle={{ paddingBottom: '10px', cursor: 'pointer' }}
                    iconType="line"
                    iconSize={18}
                    onClick={(e) => handleLegendClick(e.dataKey, hiddenLinesCodes, setHiddenLinesCodes)}
                  />
                  {codesPerSecond.labels.map((label: string) => {
                    const code = label.replace('HTTP ', '');
                    return <Line 
                      key={label} 
                      type="monotone" 
                      dataKey={label} 
                      stroke={COLORS[code] || '#999999'} 
                      strokeWidth={2} 
                      dot={false}
                      hide={hiddenLinesCodes.has(label)}
                    />;
                  })}
                </LineChart>
              </ResponsiveContainer>
              <div className="mt-4 bg-gray-50 rounded-lg p-4">
                <h4 className="font-semibold text-gray-700 mb-2 flex items-center gap-2"><span>🤖</span> Análisis</h4>
                <textarea value={analysisCodesPerSecond} onChange={(e) => setAnalysisCodesPerSecond(e.target.value)} className="w-full h-24 p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 resize-none text-sm" placeholder="Análisis IA..." />
              </div>
            </div>

            {/* Transactions per Second */}
            <div className="border-l-4 border-green-500 pl-6">
              <h3 className="text-lg font-bold text-gray-800 mb-4">💹 Transactions per Second</h3>
              <ResponsiveContainer width="100%" height={400}>
                <LineChart data={tpsByLabel.data}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="displayTime" tick={{ fontSize: 10 }} height={60} angle={0} textAnchor="middle" interval={Math.max(0, Math.floor(tpsByLabel.data.length / 12) - 1)} />
                  <YAxis tick={{ fontSize: 11 }} label={{ value: 'TPS', angle: -90, position: 'insideLeft', style: { fontSize: 12 } }} />
                  <Tooltip contentStyle={{ fontSize: 12 }} />
                  <Legend 
                    verticalAlign="top" 
                    height={60} 
                    wrapperStyle={{ paddingBottom: '10px', cursor: 'pointer' }}
                    iconType="line"
                    iconSize={18}
                    onClick={(e) => handleLegendClick(e.dataKey, hiddenLinesTPS, setHiddenLinesTPS)}
                  />
                  {tpsByLabel.labels.map((label: string, idx: number) => (
                    <Line 
                      key={label} 
                      type="monotone" 
                      dataKey={label} 
                      stroke={LABEL_COLORS[idx % LABEL_COLORS.length]} 
                      strokeWidth={2} 
                      dot={false}
                      hide={hiddenLinesTPS.has(label)}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
              <div className="mt-4 bg-gray-50 rounded-lg p-4">
                <h4 className="font-semibold text-gray-700 mb-2 flex items-center gap-2"><span>🤖</span> Análisis</h4>
                <textarea value={analysisTransactionsPerSecond} onChange={(e) => setAnalysisTransactionsPerSecond(e.target.value)} className="w-full h-24 p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 resize-none text-sm" placeholder="Análisis IA..." />
              </div>
            </div>

            {/* Active Threads Over Time */}
            <div className="border-l-4 border-pink-500 pl-6">
              <h3 className="text-lg font-bold text-gray-800 mb-4">👥 Active Threads Over Time</h3>
              <ResponsiveContainer width="100%" height={350}>
                <AreaChart data={activeThreadsData}>
                  <defs><linearGradient id="colorThreads" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#ec4899" stopOpacity={0.8}/><stop offset="95%" stopColor="#ec4899" stopOpacity={0.1}/></linearGradient></defs>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="displayTime" tick={{ fontSize: 10 }} height={60} angle={0} textAnchor="middle" interval={Math.max(0, Math.floor(activeThreadsData.length / 12) - 1)} />
                  <YAxis tick={{ fontSize: 11 }} label={{ value: 'Threads', angle: -90, position: 'insideLeft', style: { fontSize: 12 } }} />
                  <Tooltip contentStyle={{ fontSize: 12 }} />
                  <Area type="monotone" dataKey="value" stroke="#ec4899" fillOpacity={1} fill="url(#colorThreads)" />
                </AreaChart>
              </ResponsiveContainer>
              <div className="mt-4 bg-gray-50 rounded-lg p-4">
                <h4 className="font-semibold text-gray-700 mb-2 flex items-center gap-2"><span>🤖</span> Análisis</h4>
                <textarea value={analysisActiveThreads} onChange={(e) => setAnalysisActiveThreads(e.target.value)} className="w-full h-24 p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-pink-500 resize-none text-sm" placeholder="Análisis IA..." />
              </div>
            </div>
          </div>
        </div>

        {/* CONCLUSIONES Y RECOMENDACIONES - LADO A LADO */}
        <div className="mb-8">
          <div className="grid grid-cols-2 gap-6">
            <div className="bg-white rounded-lg shadow-lg overflow-hidden">
              <div className="bg-gradient-to-r from-indigo-600 to-purple-600 px-6 py-4">
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <span>📝</span> Conclusiones
                </h2>
              </div>
              <div className="p-6">
                <textarea 
                  value={conclusions} 
                  onChange={(e) => setConclusions(e.target.value)} 
                  className="w-full h-64 p-4 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none" 
                  placeholder="Escribe las conclusiones generales de la prueba de performance..."
                />
              </div>
            </div>

            <div className="bg-white rounded-lg shadow-lg overflow-hidden">
              <div className="bg-gradient-to-r from-green-600 to-teal-600 px-6 py-4">
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <span>💡</span> Recomendaciones
                </h2>
              </div>
              <div className="p-6">
                <textarea 
                  value={recommendations} 
                  onChange={(e) => setRecommendations(e.target.value)} 
                  className="w-full h-64 p-4 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent resize-none" 
                  placeholder="Escribe las recomendaciones para mejorar el performance del sistema..."
                />
              </div>
            </div>
          </div>
        </div>

        {/* BOTONES DE ACCIÓN */}
        <div className="flex justify-center gap-4 mb-8">
          <button onClick={handleSaveChanges} disabled={saving} className="flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-green-600 to-green-700 text-white rounded-lg shadow-lg hover:from-green-700 hover:to-green-800 transition-all disabled:opacity-50">
            <Save className="w-5 h-5" />
            {saving ? 'Guardando...' : '💾 Guardar Todos los Cambios'}
          </button>
          <button onClick={handleExportHTML} className="flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-lg shadow-lg hover:from-blue-700 hover:to-blue-800 transition-all">
            <FileCode className="w-5 h-5" />
            📄 Exportar HTML Interactivo
          </button>
          <button onClick={handleExportPDF} className="flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-red-600 to-red-700 text-white rounded-lg shadow-lg hover:from-red-700 hover:to-red-800 transition-all">
            <FileDown className="w-5 h-5" />
            📑 Exportar PDF
          </button>
        </div>

        <div className="text-center text-gray-600 text-sm py-8 border-t border-gray-300">
          <p className="font-semibold">Software Quality Assurance (SQA) - Sistema de Reportes de Performance</p>
          <p className="text-xs mt-2">Powered by FastAPI + React + PostgreSQL + Google Gemini AI</p>
        </div>
      </div>
    </div>
  );
}
