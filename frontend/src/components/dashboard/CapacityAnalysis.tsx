/**
 * KNX-17: Capacity Analysis — infrastructure resource evaluation (CPU, RAM, DB, etc.)
 */
import { useState, useEffect, useCallback } from 'react';
import { Plus, Trash2, Save, CheckCircle, XCircle } from 'lucide-react';

interface Resource {
  id: string;
  name: string;
  category: string;
  observed_value: string;
  unit: string;
  threshold: string;
  status: 'PASS' | 'FAIL' | '';
  analysis: string;
}

interface Props {
  executionId: string;
}

const DEFAULT_RESOURCES: () => Resource[] = () => [
  { id: crypto.randomUUID(), name: 'CPU', category: 'compute', observed_value: '', unit: '%', threshold: '80', status: '', analysis: '' },
  { id: crypto.randomUUID(), name: 'Memoria RAM', category: 'memory', observed_value: '', unit: '%', threshold: '85', status: '', analysis: '' },
  { id: crypto.randomUUID(), name: 'Base de Datos (query time)', category: 'database', observed_value: '', unit: 'ms', threshold: '500', status: '', analysis: '' },
  { id: crypto.randomUUID(), name: 'Disco I/O', category: 'storage', observed_value: '', unit: '%', threshold: '70', status: '', analysis: '' },
  { id: crypto.randomUUID(), name: 'Red (bandwidth)', category: 'network', observed_value: '', unit: 'Mbps', threshold: '', status: '', analysis: '' },
];

export default function CapacityAnalysis({ executionId }: Props) {
  const [enabled, setEnabled] = useState(false);
  const [resources, setResources] = useState<Resource[]>(DEFAULT_RESOURCES());
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const getCsrfToken = () => document.cookie.match(/csrf_token=([^;]+)/)?.[1] || '';
  const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';

  const loadData = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/executions/${executionId}/capacity`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        if (data.enabled) {
          setEnabled(true);
          if (data.resources && data.resources.length > 0) {
            setResources(data.resources);
          }
        }
      }
    } catch (err) {
      console.error('Error loading capacity data:', err);
    } finally {
      setLoaded(true);
    }
  }, [executionId, apiBase]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await fetch(`${apiBase}/executions/${executionId}/capacity`, {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
        body: JSON.stringify({ enabled, resources }),
      });
    } catch (err) {
      console.error('Error saving capacity:', err);
      alert('Error guardando analisis de capacidades');
    } finally {
      setSaving(false);
    }
  };

  const updateResource = (id: string, field: keyof Resource, value: string) => {
    setResources(prev => prev.map(r => {
      if (r.id !== id) return r;
      const updated = { ...r, [field]: value };
      // Auto-evaluate PASS/FAIL
      const obs = parseFloat(updated.observed_value);
      const thr = parseFloat(updated.threshold);
      if (!isNaN(obs) && !isNaN(thr) && thr > 0) {
        updated.status = obs <= thr ? 'PASS' : 'FAIL';
      } else {
        updated.status = '';
      }
      return updated;
    }));
  };

  const addResource = () => {
    setResources(prev => [...prev, {
      id: crypto.randomUUID(),
      name: '',
      category: 'other',
      observed_value: '',
      unit: '%',
      threshold: '',
      status: '',
      analysis: '',
    }]);
  };

  const removeResource = (id: string) => {
    setResources(prev => prev.filter(r => r.id !== id));
  };

  if (!loaded) return null;

  return (
    <div className="mb-8">
      <div className="bg-white rounded-2xl shadow-lg overflow-hidden border border-gray-200">
        <div className="bg-[#0a1628] px-6 py-4 flex items-center justify-between">
          <h2 className="text-3xl font-bold text-white">Analisis de Capacidades del Sistema</h2>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              className="w-5 h-5 rounded text-[#f5a623] focus:ring-[#f5a623]"
            />
            <span className="text-lg text-white/80">Incluir en reporte</span>
          </label>
        </div>

        {enabled && (
          <div className="p-6">
            <p className="text-lg text-gray-500 mb-4">
              Registre los valores observados de infraestructura y compare contra los umbrales del cliente.
            </p>

            <div className="overflow-x-auto rounded-xl border border-gray-200 mb-4">
              <table className="w-full text-lg">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left text-base font-bold text-gray-500 uppercase">Recurso</th>
                    <th className="px-3 py-2 text-center text-base font-bold text-gray-500 uppercase">Valor</th>
                    <th className="px-3 py-2 text-center text-base font-bold text-gray-500 uppercase">Unidad</th>
                    <th className="px-3 py-2 text-center text-base font-bold text-gray-500 uppercase">Umbral</th>
                    <th className="px-3 py-2 text-center text-base font-bold text-gray-500 uppercase">Estado</th>
                    <th className="px-3 py-2 text-center text-base font-bold text-gray-500 uppercase">Analisis</th>
                    <th className="px-3 py-2 text-center text-base font-bold text-gray-500 uppercase w-12"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 bg-white">
                  {resources.map((r) => (
                    <tr key={r.id}>
                      <td className="px-3 py-2">
                        <input
                          type="text"
                          value={r.name}
                          onChange={(e) => updateResource(r.id, 'name', e.target.value)}
                          className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-lg text-gray-800 focus:border-[#f5a623] focus:ring-1 focus:ring-[#f5a623]/20"
                          placeholder="Nombre"
                        />
                      </td>
                      <td className="px-3 py-2">
                        <input
                          type="text"
                          value={r.observed_value}
                          onChange={(e) => updateResource(r.id, 'observed_value', e.target.value)}
                          className="w-24 text-center bg-white border border-gray-200 rounded-lg px-2 py-2 text-lg text-gray-800 focus:border-[#f5a623]"
                          placeholder="0"
                        />
                      </td>
                      <td className="px-3 py-2">
                        <select
                          value={r.unit}
                          onChange={(e) => updateResource(r.id, 'unit', e.target.value)}
                          className="bg-white border border-gray-200 rounded-lg px-2 py-2 text-lg text-gray-800 focus:border-[#f5a623]"
                        >
                          <option value="%">%</option>
                          <option value="ms">ms</option>
                          <option value="Mbps">Mbps</option>
                          <option value="GB">GB</option>
                          <option value="IOPS">IOPS</option>
                          <option value="count">count</option>
                        </select>
                      </td>
                      <td className="px-3 py-2">
                        <input
                          type="text"
                          value={r.threshold}
                          onChange={(e) => updateResource(r.id, 'threshold', e.target.value)}
                          className="w-24 text-center bg-white border border-gray-200 rounded-lg px-2 py-2 text-lg text-gray-800 focus:border-[#f5a623]"
                          placeholder="Umbral"
                        />
                      </td>
                      <td className="px-3 py-2 text-center">
                        {r.status === 'PASS' && (
                          <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-green-100 text-green-700 text-base font-bold">
                            <CheckCircle className="w-4 h-4" /> PASS
                          </span>
                        )}
                        {r.status === 'FAIL' && (
                          <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-red-100 text-red-700 text-base font-bold">
                            <XCircle className="w-4 h-4" /> FAIL
                          </span>
                        )}
                        {r.status === '' && <span className="text-gray-400 text-base">--</span>}
                      </td>
                      <td className="px-3 py-2">
                        <input
                          type="text"
                          value={r.analysis}
                          onChange={(e) => updateResource(r.id, 'analysis', e.target.value)}
                          className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-lg text-gray-800 focus:border-[#f5a623]"
                          placeholder="Interpretacion..."
                        />
                      </td>
                      <td className="px-3 py-2 text-center">
                        <button onClick={() => removeResource(r.id)} className="text-red-400 hover:text-red-600 transition-colors">
                          <Trash2 className="w-5 h-5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex items-center gap-4">
              <button
                onClick={addResource}
                className="flex items-center gap-2 px-4 py-2 text-lg text-[#f5a623] hover:bg-[#f5a623]/10 rounded-lg transition-colors border border-[#f5a623]/30"
              >
                <Plus className="w-5 h-5" /> Agregar recurso
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-2 px-6 py-2 bg-green-600 text-white text-lg font-bold rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
              >
                <Save className="w-5 h-5" /> {saving ? 'Guardando...' : 'Guardar Capacidades'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
