// frontend/src/pages/ExecutionDashboard.tsx
import { useState } from 'react';
import { Gauge, Plus, History as HistoryIcon } from 'lucide-react';
import ScenarioForm from '../components/execution/ScenarioForm';
import LiveMetricsChart from '../components/execution/LiveMetricsChart';
import ExecutionHistory from '../components/execution/ExecutionHistory';
import { MetricsSnapshot } from '../api/executionApi';

type Tab = 'new' | 'history';

export default function ExecutionDashboard() {
  const [tab, setTab] = useState<Tab>('new');
  const [activeExecutionId, setActiveExecutionId] = useState<number | null>(null);
  const [historyRefresh, setHistoryRefresh] = useState(0);
  const [, setExecutionStatus] = useState<string>('');

  const handleStarted = (executionId: number) => {
    setActiveExecutionId(executionId);
    setExecutionStatus('running');
  };

  const handleStatusChange = (status: string) => {
    setExecutionStatus(status);
  };

  const handleFinal = (_snapshot: MetricsSnapshot) => {
    setExecutionStatus('completed');
    setHistoryRefresh(prev => prev + 1);
  };

  const handleSelectHistory = (id: number) => {
    setActiveExecutionId(id);
  };

  const tabClasses = (t: Tab) =>
    `px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
      tab === t
        ? 'bg-white text-blue-600 border border-b-0 border-gray-200'
        : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
    }`;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Gauge className="w-6 h-6 text-blue-600" />
        <div>
          <h1 className="text-xl font-bold text-gray-800">Execution Dashboard</h1>
          <p className="text-sm text-gray-500">Configure and run load tests in real time</p>
        </div>
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Left panel — form / history */}
        <div className="flex-1 min-w-0">
          {/* Tabs */}
          <div className="flex gap-1 mb-0">
            <button onClick={() => setTab('new')} className={tabClasses('new')}>
              <span className="flex items-center gap-1.5"><Plus className="w-4 h-4" /> New Test</span>
            </button>
            <button onClick={() => setTab('history')} className={tabClasses('history')}>
              <span className="flex items-center gap-1.5"><HistoryIcon className="w-4 h-4" /> History</span>
            </button>
          </div>

          <div className="bg-white border border-gray-200 rounded-b-lg rounded-tr-lg p-5">
            {tab === 'new' ? (
              <ScenarioForm onStarted={handleStarted} />
            ) : (
              <ExecutionHistory
                onSelect={handleSelectHistory}
                refreshTrigger={historyRefresh}
              />
            )}
          </div>
        </div>

        {/* Right panel — live metrics */}
        <div className="w-full lg:w-[480px] flex-shrink-0">
          <div className="bg-white border border-gray-200 rounded-lg p-5 sticky top-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">Live Metrics</h3>
            {activeExecutionId ? (
              <LiveMetricsChart
                key={activeExecutionId}
                executionId={activeExecutionId}
                onStatusChange={handleStatusChange}
                onFinal={handleFinal}
              />
            ) : (
              <div className="flex flex-col items-center justify-center py-16 text-gray-400">
                <Gauge className="w-10 h-10 mb-3 opacity-40" />
                <p className="text-sm">No active execution</p>
                <p className="text-xs mt-1">Start a test or select one from history</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
