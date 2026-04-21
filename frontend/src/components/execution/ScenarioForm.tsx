// frontend/src/components/execution/ScenarioForm.tsx
import { useState, useEffect } from 'react';
import { Loader2, Play } from 'lucide-react';
import { scenarioApi, fullExecutionApi } from '../../api/executionApi';
import { scriptApi, Script } from '../../api/scriptDesignerApi';

interface Props {
  onStarted: (executionId: number) => void;
}

const TEST_TYPE_LABELS: Record<string, string> = {
  load: 'Load Test',
  stress: 'Stress Test',
  spike: 'Spike Test',
  soak: 'Soak Test',
};

const FIELD_LABELS: Record<string, string> = {
  initial_users: 'Initial VUs',
  step_users: 'Step VUs',
  step_duration_sec: 'Step Delay (sec)',
  hold_duration_sec: 'Hold Duration (sec)',
  max_users: 'Max VUs',
  ramp_down_sec: 'Ramp Down (sec)',
  total_duration_sec: 'Total Duration (sec)',
  think_time_ms: 'Think Time (ms)',
};

// Only show the key fields for the form
const EDITABLE_FIELDS = ['initial_users', 'step_users', 'step_duration_sec', 'max_users', 'hold_duration_sec'];

export default function ScenarioForm({ onStarted }: Props) {
  const [templates, setTemplates] = useState<Record<string, Record<string, number>>>({});
  const [scripts, setScripts] = useState<Script[]>([]);
  const [selectedType, setSelectedType] = useState<string>('load');
  const [scenarioName, setScenarioName] = useState('');
  const [selectedScriptId, setSelectedScriptId] = useState<number | null>(null);
  const [config, setConfig] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const [tRes, sRes] = await Promise.all([
          scenarioApi.templates(),
          scriptApi.list(),
        ]);
        setTemplates(tRes.data);
        setScripts(sRes.data);
        // Set defaults
        const firstType = Object.keys(tRes.data)[0] || 'load';
        setSelectedType(firstType);
        setConfig(tRes.data[firstType] || {});
        setScenarioName(`${TEST_TYPE_LABELS[firstType] || firstType} — ${new Date().toLocaleDateString('es-CO')}`);
        if (sRes.data.length > 0) {
          setSelectedScriptId(sRes.data[0].id);
        }
      } catch {
        setError('Error loading data');
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const handleTypeChange = (testType: string) => {
    setSelectedType(testType);
    const tpl = templates[testType];
    if (tpl) {
      setConfig({ ...tpl });
      setScenarioName(`${TEST_TYPE_LABELS[testType] || testType} — ${new Date().toLocaleDateString('es-CO')}`);
    }
  };

  const handleStart = async () => {
    if (!selectedScriptId) return setError('Select a script');
    if (!scenarioName.trim()) return setError('Enter a scenario name');

    setCreating(true);
    setError('');
    try {
      const { data: scenario } = await scenarioApi.create({
        name: scenarioName,
        test_type: selectedType,
        thread_group_config: config,
        script_id: selectedScriptId,
      });
      const { data: exec } = await fullExecutionApi.start(scenario.id, selectedScriptId);
      onStarted(exec.execution_id);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error starting execution');
    } finally {
      setCreating(false);
    }
  };

  const estimatedDuration = () => {
    const maxUsers = config.max_users || 50;
    const initialUsers = config.initial_users || 1;
    const stepUsers = config.step_users || 5;
    const stepDelay = config.step_duration_sec || 30;
    const hold = config.hold_duration_sec || 300;
    const rampSteps = Math.ceil((maxUsers - initialUsers) / stepUsers);
    const rampTime = rampSteps * stepDelay;
    const total = (rampTime + hold) / 60;
    return `~${Math.round(total)} min`;
  };

  if (loading) return (
    <div className="flex items-center justify-center py-12 text-gray-400 text-sm">
      <Loader2 className="w-4 h-4 animate-spin mr-2" /> Loading...
    </div>
  );

  return (
    <div className="space-y-5">
      {/* Test type selector */}
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-2">Test Type</label>
        <div className="grid grid-cols-4 gap-2">
          {Object.keys(templates).map(type => (
            <button
              key={type}
              onClick={() => handleTypeChange(type)}
              className={`py-2 px-3 rounded-md border text-sm font-medium transition-colors capitalize ${
                selectedType === type
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white text-gray-700 border-gray-300 hover:border-blue-300'
              }`}
            >
              {TEST_TYPE_LABELS[type] || type}
            </button>
          ))}
        </div>
      </div>

      {/* Script selector */}
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Script</label>
        <select
          value={selectedScriptId || ''}
          onChange={e => setSelectedScriptId(parseInt(e.target.value))}
          className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
        >
          <option value="">— Select a script —</option>
          {scripts.map(s => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
      </div>

      {/* Scenario name */}
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Scenario Name</label>
        <input
          type="text"
          value={scenarioName}
          onChange={e => setScenarioName(e.target.value)}
          className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
        />
      </div>

      {/* Thread group config */}
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-2">Load Profile</label>
        <div className="grid grid-cols-2 gap-3">
          {EDITABLE_FIELDS.filter(key => key in config).map(key => (
            <div key={key}>
              <label className="block text-xs text-gray-500 mb-1">{FIELD_LABELS[key] || key}</label>
              <input
                type="number"
                min={1}
                value={config[key] || 0}
                onChange={e => setConfig(prev => ({ ...prev, [key]: parseInt(e.target.value) || 1 }))}
                className="w-full border border-gray-300 rounded-md px-2 py-1.5 text-sm focus:outline-none focus:border-blue-500"
              />
            </div>
          ))}
        </div>
        {Object.keys(config).length > 0 && (
          <p className="text-xs text-gray-400 mt-2">
            Estimated duration: <strong>{estimatedDuration()}</strong> &middot;
            Peak VUs: <strong>{config.max_users || 50}</strong>
          </p>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-3 text-sm text-red-700">{error}</div>
      )}

      <button
        onClick={handleStart}
        disabled={creating || !selectedScriptId}
        className="w-full py-2.5 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2"
      >
        {creating ? (
          <><Loader2 className="w-4 h-4 animate-spin" /> Starting...</>
        ) : (
          <><Play className="w-4 h-4" /> Start Load Test</>
        )}
      </button>
    </div>
  );
}
