// frontend/src/components/execution/ExecutionHistory.tsx
import { useState, useEffect, useCallback } from 'react';
import { Loader2, Download, BarChart3 } from 'lucide-react';
import { fullExecutionApi, ExecutionHistoryItem } from '../../api/executionApi';

interface Props {
  onSelect?: (id: number) => void;
  refreshTrigger?: number;
}

const statusBadge = (status: string, isActive: boolean) => {
  if (isActive && status === 'running') return 'bg-green-100 text-green-700';
  if (status === 'completed') return 'bg-blue-100 text-blue-700';
  if (status === 'error') return 'bg-red-100 text-red-700';
  if (status === 'paused') return 'bg-yellow-100 text-yellow-700';
  return 'bg-gray-100 text-gray-600';
};

const testTypeBadge: Record<string, string> = {
  load: 'bg-blue-50 text-blue-600',
  stress: 'bg-orange-50 text-orange-600',
  spike: 'bg-purple-50 text-purple-600',
  soak: 'bg-green-50 text-green-600',
  smoke_test: 'bg-gray-50 text-gray-600',
  smoke: 'bg-gray-50 text-gray-600',
};

export default function ExecutionHistory({ onSelect, refreshTrigger }: Props) {
  const [items, setItems] = useState<ExecutionHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await fullExecutionApi.history(20, 0);
      setItems(data.items);
    } catch (e) {
      console.error('History load error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load, refreshTrigger]);

  const [generatingId, setGeneratingId] = useState<number | null>(null);

  const generateReport = async (executionId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setGeneratingId(executionId);
    try {
      const { data } = await fullExecutionApi.generateReport(executionId);
      window.location.href = data.report_url || '/';
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error generating report');
    } finally {
      setGeneratingId(null);
    }
  };

  const downloadJTL = async (item: ExecutionHistoryItem, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const { data } = await fullExecutionApi.downloadJTL(item.id);
      const url = window.URL.createObjectURL(new Blob([data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', item.output_filename || `execution_${item.id}.jtl`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      alert('JTL file not available');
    }
  };

  if (loading) return (
    <div className="flex items-center justify-center py-8 text-gray-400 text-sm">
      <Loader2 className="w-4 h-4 animate-spin mr-2" /> Loading history...
    </div>
  );

  if (items.length === 0) return (
    <div className="flex flex-col items-center justify-center py-12 text-gray-400">
      <p className="text-sm">No executions yet</p>
      <p className="text-xs mt-1">Run your first load test to see it here</p>
    </div>
  );

  return (
    <div className="overflow-hidden">
      <div className="divide-y divide-gray-100">
        {items.map(item => (
          <div
            key={item.id}
            onClick={() => onSelect?.(item.id)}
            className="px-4 py-3 hover:bg-gray-50 cursor-pointer transition-colors"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${statusBadge(item.status, item.is_active)}`}>
                    {item.is_active && item.status === 'running' ? '● ' : ''}{item.status}
                  </span>
                  {item.test_type && (
                    <span className={`text-xs px-1.5 py-0.5 rounded ${testTypeBadge[item.test_type] || 'bg-gray-50 text-gray-600'}`}>
                      {item.test_type}
                    </span>
                  )}
                </div>
                <p className="text-sm font-medium text-gray-800 truncate">{item.scenario_name || 'Smoke Test'}</p>
                <p className="text-xs text-gray-500 truncate">{item.script_name}</p>
              </div>
              <div className="text-right flex-shrink-0">
                <p className="text-xs text-gray-500">
                  {item.started_at ? new Date(item.started_at).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' }) : '—'}
                </p>
                {item.total_requests > 0 && (
                  <p className="text-xs text-gray-600 mt-0.5">
                    {item.total_requests.toLocaleString()} reqs
                    <span className={item.error_rate_percent > 1 ? ' text-red-600' : ' text-gray-500'}>
                      {' '}&middot; {item.error_rate_percent.toFixed(1)}% err
                    </span>
                  </p>
                )}
                {item.duration_sec != null && (
                  <p className="text-xs text-gray-400">{Math.round(item.duration_sec)}s</p>
                )}
              </div>
            </div>

            {item.jtl_file_path && item.status === 'completed' && (
              <div className="mt-1.5 flex items-center gap-3">
                <button
                  onClick={(e) => downloadJTL(item, e)}
                  className="text-xs text-blue-600 hover:text-blue-800 hover:underline flex items-center gap-1"
                >
                  <Download className="w-3 h-3" /> Download JTL
                </button>
                <button
                  onClick={(e) => generateReport(item.id, e)}
                  disabled={generatingId === item.id}
                  className="text-xs text-purple-600 hover:text-purple-800 hover:underline flex items-center gap-1 disabled:opacity-50"
                >
                  {generatingId === item.id ? (
                    <><Loader2 className="w-3 h-3 animate-spin" /> Generating...</>
                  ) : (
                    <><BarChart3 className="w-3 h-3" /> Generate Report</>
                  )}
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
