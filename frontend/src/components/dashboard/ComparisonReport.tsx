/**
 * KNX-12: Comparison Report — Load vs Stress test side-by-side.
 */
import { useState, useEffect } from 'react';
import { ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react';

interface ExecutionSummary {
  id: string;
  name: string;
  test_type: string;
  total_requests: number;
  error_rate: number;
  avg_response_time: number;
  p90_response_time: number;
  p95_response_time: number;
  p99_response_time: number;
  throughput: number;
  duration_seconds: number;
}

interface ComparisonData {
  load: ExecutionSummary;
  stress: ExecutionSummary;
  comparison: Record<string, number | null>;
  ai_comparison_analysis: string;
}

interface Props {
  executionId?: string; // not used directly — this component fetches its own data
}

export default function ComparisonReport(_props: Props) {
  const [executions, setExecutions] = useState<any[]>([]);
  const [loadId, setLoadId] = useState('');
  const [stressId, setStressId] = useState('');
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<ComparisonData | null>(null);
  const [analysis, setAnalysis] = useState('');
  const [listLoading, setListLoading] = useState(true);

  useEffect(() => {
    const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';
    fetch(`${apiBase}/executions`, { credentials: 'include' })
      .then(r => r.json())
      .then(d => { setExecutions(d); setListLoading(false); })
      .catch(() => setListLoading(false));
  }, []);

  const handleCompare = async () => {
    if (!loadId || !stressId) return;
    setLoading(true);
    try {
      const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';
      const csrfToken = document.cookie.match(/csrf_token=([^;]+)/)?.[1] || '';
      const res = await fetch(
        `${apiBase}/reports/compare?load_execution_id=${loadId}&stress_execution_id=${stressId}`,
        { method: 'POST', credentials: 'include', headers: { 'X-CSRF-Token': csrfToken } },
      );
      if (res.ok) {
        const result = await res.json();
        setData(result);
        setAnalysis(result.ai_comparison_analysis || '');
      } else {
        alert('Error generando comparacion');
      }
    } catch (err) {
      console.error(err);
      alert('Error de conexion');
    } finally {
      setLoading(false);
    }
  };

  const loadExecs = executions.filter(e => e.test_type === 'load');
  const stressExecs = executions.filter(e => ['stress', 'spike', 'scalability'].includes(e.test_type));

  const ChangeIndicator = ({ value, invert = false }: { value: number | null; invert?: boolean }) => {
    if (value == null) return <span className="text-gray-400">--</span>;
    const isBad = invert ? value > 0 : value > 0;
    const color = isBad ? 'text-red-600' : 'text-green-600';
    const Icon = value > 0 ? ArrowUpRight : value < 0 ? ArrowDownRight : Minus;
    return (
      <span className={`flex items-center gap-1 font-bold ${color}`}>
        <Icon className="w-4 h-4" />
        {value > 0 ? '+' : ''}{value.toFixed(1)}%
      </span>
    );
  };

  return (
    <div className="mb-8">
      <div className="bg-white rounded-2xl shadow-lg overflow-hidden border border-gray-200">
        <div className="bg-[#0a1628] px-6 py-4">
          <h2 className="text-3xl font-bold text-white">Informe Integrado: Carga vs Estres</h2>
        </div>
        <div className="p-6">
          <p className="text-lg text-gray-500 mb-4">
            Seleccione dos ejecuciones del mismo servicio para generar un analisis comparativo.
          </p>

          {/* Selection form */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            <div>
              <label className="text-base font-medium text-gray-600 block mb-1">Prueba de Carga (baseline)</label>
              <select
                value={loadId}
                onChange={(e) => setLoadId(e.target.value)}
                disabled={listLoading}
                className="w-full bg-white text-gray-800 rounded-xl px-4 py-3 text-lg border border-gray-300 focus:border-[#f5a623] focus:ring-2 focus:ring-[#f5a623]/20"
              >
                <option value="">Seleccionar ejecucion de carga...</option>
                {loadExecs.map(e => (
                  <option key={e.id} value={e.id}>
                    {e.name} — {e.client || 'N/A'} — {e.total_requests?.toLocaleString()} req
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-base font-medium text-gray-600 block mb-1">Prueba de Estres</label>
              <select
                value={stressId}
                onChange={(e) => setStressId(e.target.value)}
                disabled={listLoading}
                className="w-full bg-white text-gray-800 rounded-xl px-4 py-3 text-lg border border-gray-300 focus:border-[#f5a623] focus:ring-2 focus:ring-[#f5a623]/20"
              >
                <option value="">Seleccionar ejecucion de estres...</option>
                {stressExecs.map(e => (
                  <option key={e.id} value={e.id}>
                    {e.name} — {e.client || 'N/A'} — {e.total_requests?.toLocaleString()} req
                  </option>
                ))}
              </select>
            </div>
          </div>

          <button
            onClick={handleCompare}
            disabled={!loadId || !stressId || loading}
            className="px-8 py-3 bg-[#f5a623] text-[#0a1628] rounded-xl font-bold text-lg hover:bg-[#f5a623]/90 disabled:opacity-40 transition-colors"
          >
            {loading ? 'Generando...' : 'Generar Informe Comparativo'}
          </button>

          {/* Comparison results */}
          {data && (
            <div className="mt-8 space-y-6">
              {/* Metrics comparison table */}
              <div className="overflow-x-auto rounded-xl border border-gray-200">
                <table className="w-full text-lg">
                  <thead className="bg-[#0a1628]">
                    <tr>
                      <th className="px-4 py-3 text-left text-base font-bold text-white uppercase">Metrica</th>
                      <th className="px-4 py-3 text-center text-base font-bold text-blue-300 uppercase">Carga</th>
                      <th className="px-4 py-3 text-center text-base font-bold text-red-300 uppercase">Estres</th>
                      <th className="px-4 py-3 text-center text-base font-bold text-white uppercase">Cambio</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 bg-white">
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium text-gray-800">Avg Response Time</td>
                      <td className="px-4 py-3 text-center text-gray-700">{data.load.avg_response_time.toFixed(0)} ms</td>
                      <td className="px-4 py-3 text-center text-gray-700">{data.stress.avg_response_time.toFixed(0)} ms</td>
                      <td className="px-4 py-3 text-center"><ChangeIndicator value={data.comparison.response_time_change_pct} /></td>
                    </tr>
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium text-gray-800">P90</td>
                      <td className="px-4 py-3 text-center text-gray-700">{data.load.p90_response_time.toFixed(0)} ms</td>
                      <td className="px-4 py-3 text-center text-gray-700">{data.stress.p90_response_time.toFixed(0)} ms</td>
                      <td className="px-4 py-3 text-center"><ChangeIndicator value={data.comparison.p90_change_pct} /></td>
                    </tr>
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium text-gray-800">P95</td>
                      <td className="px-4 py-3 text-center text-gray-700">{data.load.p95_response_time.toFixed(0)} ms</td>
                      <td className="px-4 py-3 text-center text-gray-700">{data.stress.p95_response_time.toFixed(0)} ms</td>
                      <td className="px-4 py-3 text-center"><ChangeIndicator value={data.comparison.p95_change_pct} /></td>
                    </tr>
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium text-gray-800">Error Rate</td>
                      <td className="px-4 py-3 text-center text-gray-700">{data.load.error_rate.toFixed(2)}%</td>
                      <td className="px-4 py-3 text-center text-gray-700">{data.stress.error_rate.toFixed(2)}%</td>
                      <td className="px-4 py-3 text-center"><ChangeIndicator value={data.comparison.error_rate_change_pct} /></td>
                    </tr>
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium text-gray-800">Throughput</td>
                      <td className="px-4 py-3 text-center text-gray-700">{data.load.throughput.toFixed(2)} req/s</td>
                      <td className="px-4 py-3 text-center text-gray-700">{data.stress.throughput.toFixed(2)} req/s</td>
                      <td className="px-4 py-3 text-center"><ChangeIndicator value={data.comparison.throughput_change_pct} invert /></td>
                    </tr>
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium text-gray-800">Total Requests</td>
                      <td className="px-4 py-3 text-center text-gray-700">{data.load.total_requests.toLocaleString()}</td>
                      <td className="px-4 py-3 text-center text-gray-700">{data.stress.total_requests.toLocaleString()}</td>
                      <td className="px-4 py-3 text-center text-gray-400">--</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* AI Comparison Analysis */}
              <div className="bg-white rounded-2xl shadow-lg p-6 border-l-4 border-orange-500 border border-gray-200">
                <h3 className="text-3xl font-bold text-orange-600 mb-3">Analisis Comparativo</h3>
                <span className="text-xs text-gray-400 italic mb-1 block">Click para editar</span>
                <textarea
                  value={analysis}
                  onChange={(e) => setAnalysis(e.target.value)}
                  className="w-full min-h-[200px] p-4 border-2 border-gray-300 rounded-xl text-xl text-gray-800 focus:ring-2 focus:ring-orange-400/50 focus:border-orange-500 resize-y cursor-text hover:border-orange-300 transition-colors"
                  placeholder="Analisis comparativo..."
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
