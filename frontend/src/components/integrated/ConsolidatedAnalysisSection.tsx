/**
 * HF9 — Consolidated Analysis Section for Integrated Report.
 * Supports dual Load/Stress blocks. Editable textareas with onBlur persistence.
 */
import { useState, useEffect } from 'react';

interface ConsolidatedData {
  conclusions: string;
  recommendations: string;
  generated_at: string | null;
  edited: boolean;
}

interface Props {
  consolidatedAnalysis: Record<string, ConsolidatedData>;
  sections: Array<{ type: string; source_id: string; source_name: string }>;
  onGenerated: (data: Record<string, ConsolidatedData>) => void;
  onEdit: (testType: string, field: 'conclusions' | 'recommendations', value: string) => void;
  // F3: notifica cada tecla al padre para el autosave con debounce. Opcional:
  // sin esta prop el componente se comporta exactamente igual que en F7.
  onDraftChange?: (testType: string, field: 'conclusions' | 'recommendations', value: string) => void;
}

const TEST_TYPE_LABELS: Record<string, string> = {
  load: 'Prueba de Carga',
  stress: 'Prueba de Estres',
};

export default function ConsolidatedAnalysisSection({
  consolidatedAnalysis,
  sections,
  onGenerated,
  onEdit,
  onDraftChange,
}: Props) {
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');
  // F5 (B2, Opcion D): confirmacion antes de pisar ediciones manuales.
  const [confirmOpen, setConfirmOpen] = useState(false);

  // F7: espejo controlado de lo que muestran las cajas. Se resincroniza cuando
  // el padre cambia consolidatedAnalysis (regenerar), asi la pantalla nunca
  // queda mostrando texto viejo. La persistencia sigue en onBlur (sin cambios).
  const [draft, setDraft] = useState<Record<string, ConsolidatedData>>(consolidatedAnalysis || {});
  useEffect(() => { setDraft(consolidatedAnalysis || {}); }, [consolidatedAnalysis]);

  const hasAnalysis = Object.keys(consolidatedAnalysis || {}).length > 0;

  const getCsrfToken = () => document.cookie.match(/csrf_token=([^;]+)/)?.[1] || '';
  const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';

  // F5: el flag `edited` lo escribe la pagina padre (F3/F4) en cada blur y viaja
  // a la DB, asi que sobrevive a recargar el informe desde el historial.
  const hasManualEdits = Object.values(consolidatedAnalysis || {}).some((d: any) => d?.edited);

  const handleGenerate = async () => {
    setConfirmOpen(false);
    setGenerating(true);
    setError('');
    try {
      const res = await fetch(`${apiBase}/reports/integrated/generate-consolidated`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
        body: JSON.stringify({
          sections: sections.map((s, idx) => ({ order: idx, type: s.type, source_id: s.source_id, source_name: s.source_name })),
        }),
      });
      if (res.ok) {
        const data = await res.json();
        onGenerated(data.consolidated_analysis || {});
      } else {
        const errData = await res.json().catch(() => ({}));
        setError(errData.detail || 'Error al generar analisis consolidado');
      }
    } catch (e) {
      setError('Error de conexion al generar analisis consolidado');
    } finally {
      setGenerating(false);
    }
  };

  if (!hasAnalysis) {
    return (
      <div className="border-t-4 pt-8 mt-8" style={{ borderColor: '#f5a623' }}>
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-8 text-center">
          <h3 className="text-2xl font-bold text-[#0a1628] mb-3">
            Analisis Consolidado
          </h3>
          <p className="text-lg text-gray-600 mb-5">
            Genera un analisis consolidado que correlaciona KPIs, conclusiones, monitoreo y evidencias.
            {sections.some(s => s.type === 'load_test') && sections.some(s => s.type === 'stress_test')
              ? ' Se generaran analisis separados para Carga y Estres.'
              : ''}
          </p>
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="px-8 py-3 bg-[#0a1628] text-white font-bold text-lg rounded-xl hover:bg-[#1a2638] disabled:opacity-50 transition-colors"
          >
            {generating ? 'Generando...' : 'Generar Analisis Consolidado'}
          </button>
          {error && <p className="mt-3 text-red-600">{error}</p>}
        </div>
      </div>
    );
  }

  return (
    <div className="border-t-4 pt-8 mt-8" style={{ borderColor: '#f5a623' }}>
      <div className="flex justify-between items-center mb-6">
        <h3 className="text-2xl font-bold text-[#0a1628]">Analisis Consolidado</h3>
        <button
          onClick={() => (hasManualEdits ? setConfirmOpen(true) : handleGenerate())}
          disabled={generating}
          className="px-4 py-2 bg-slate-200 text-slate-800 rounded-lg hover:bg-slate-300 disabled:opacity-50 text-sm font-medium transition-colors"
        >
          {generating ? 'Regenerando...' : 'Regenerar'}
        </button>
      </div>

      {/* F5 (B2, Opcion D): confirmacion antes de reemplazar ediciones manuales.
          Mismo patron que el modal de confirmacion de ClientsPage. */}
      {confirmOpen && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-white border border-gray-200 rounded-xl p-6 w-full max-w-md shadow-2xl">
            <h3 className="text-2xl font-semibold text-gray-800 mb-2">Regenerar Analisis Consolidado</h3>
            <p className="text-lg text-gray-500 mb-6">
              El analisis consolidado tiene ediciones manuales. Regenerar las reemplazara
              por el texto nuevo de la IA. Esta accion no se puede deshacer. &iquest;Continuar?
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setConfirmOpen(false)}
                className="px-5 py-3 text-base text-gray-500 hover:text-gray-700 transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleGenerate}
                className="px-5 py-3 bg-red-600 text-white text-base font-semibold rounded-lg hover:bg-red-700 transition-colors"
              >
                Regenerar y reemplazar
              </button>
            </div>
          </div>
        </div>
      )}

      {Object.entries(draft).map(([testType, data]) => (
        <div key={testType} className="mb-8">
          <h4 className="text-xl font-semibold text-gray-700 mb-4">
            {TEST_TYPE_LABELS[testType] || testType}
          </h4>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Conclusiones */}
            <div className="border border-slate-200 rounded-lg overflow-hidden">
              <div className="bg-[#0a1628] text-white px-5 py-3">
                <h5 className="font-bold text-lg">Conclusiones Consolidadas</h5>
              </div>
              <div className="p-4 bg-white">
                <textarea
                  className="w-full min-h-[220px] p-3 border border-slate-200 rounded text-base text-slate-800 leading-relaxed focus:outline-none focus:border-[#f5a623] resize-y"
                  value={data.conclusions ?? ''}
                  onChange={(e) => {
                    setDraft(prev => ({ ...prev, [testType]: { ...prev[testType], conclusions: e.target.value } }));
                    onDraftChange?.(testType, 'conclusions', e.target.value);
                  }}
                  onBlur={(e) => onEdit(testType, 'conclusions', e.target.value)}
                  placeholder="Click para editar conclusiones..."
                />
              </div>
            </div>

            {/* Recomendaciones */}
            <div className="border border-slate-200 rounded-lg overflow-hidden">
              <div className="bg-emerald-700 text-white px-5 py-3">
                <h5 className="font-bold text-lg">Recomendaciones Consolidadas</h5>
              </div>
              <div className="p-4 bg-white">
                <textarea
                  className="w-full min-h-[220px] p-3 border border-slate-200 rounded text-base text-slate-800 leading-relaxed focus:outline-none focus:border-[#f5a623] resize-y"
                  value={data.recommendations ?? ''}
                  onChange={(e) => {
                    setDraft(prev => ({ ...prev, [testType]: { ...prev[testType], recommendations: e.target.value } }));
                    onDraftChange?.(testType, 'recommendations', e.target.value);
                  }}
                  onBlur={(e) => onEdit(testType, 'recommendations', e.target.value)}
                  placeholder="Click para editar recomendaciones..."
                />
              </div>
            </div>
          </div>
        </div>
      ))}

      {error && <p className="mt-3 text-red-600">{error}</p>}
    </div>
  );
}
