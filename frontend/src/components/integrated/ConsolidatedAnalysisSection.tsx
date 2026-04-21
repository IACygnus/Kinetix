/**
 * HF9 — Consolidated Analysis Section for Integrated Report.
 * Supports dual Load/Stress blocks. Editable textareas with onBlur persistence.
 */
import { useState } from 'react';

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
}: Props) {
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');

  const hasAnalysis = Object.keys(consolidatedAnalysis || {}).length > 0;

  const getCsrfToken = () => document.cookie.match(/csrf_token=([^;]+)/)?.[1] || '';
  const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';

  const handleGenerate = async () => {
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
          onClick={handleGenerate}
          disabled={generating}
          className="px-4 py-2 bg-slate-200 text-slate-800 rounded-lg hover:bg-slate-300 disabled:opacity-50 text-sm font-medium transition-colors"
        >
          {generating ? 'Regenerando...' : 'Regenerar'}
        </button>
      </div>

      {Object.entries(consolidatedAnalysis).map(([testType, data]) => (
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
                  defaultValue={data.conclusions}
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
                  defaultValue={data.recommendations}
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
