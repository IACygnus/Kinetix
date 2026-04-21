/**
 * ImageAnalysisCard — Per-image AI analysis display + controls.
 * Shows analysis text below each uploaded image with analyze/edit/regenerate.
 */
import { useState, useEffect } from 'react';
import { Loader2, RefreshCw, Save, Sparkles } from 'lucide-react';

interface Props {
  executionId: string;
  attachmentId: string;
  aiAnalysis: string | null;
  aiAnalysisUpdatedAt: string | null;
  onAnalysisUpdated: (attachmentId: string, analysis: string) => void;
}

export default function ImageAnalysisCard({
  executionId,
  attachmentId,
  aiAnalysis,
  aiAnalysisUpdatedAt,
  onAnalysisUpdated,
}: Props) {
  const [localAnalysis, setLocalAnalysis] = useState(aiAnalysis || '');
  const [isEdited, setIsEdited] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setLocalAnalysis(aiAnalysis || '');
    setIsEdited(false);
  }, [aiAnalysis]);

  const getCsrfToken = () => document.cookie.match(/csrf_token=([^;]+)/)?.[1] || '';
  const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';

  const analyzeImage = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(
        `${apiBase}/executions/${executionId}/attachments/${attachmentId}/analyze-image`,
        {
          method: 'POST',
          credentials: 'include',
          headers: { 'X-CSRF-Token': getCsrfToken() },
        },
      );
      if (res.ok) {
        const data = await res.json();
        setLocalAnalysis(data.ai_analysis || '');
        setIsEdited(false);
        onAnalysisUpdated(attachmentId, data.ai_analysis || '');
      } else {
        setError('Error al analizar la imagen. Intente nuevamente.');
      }
    } catch (err) {
      console.error('Error analyzing image:', err);
      setError('Error de conexion al analizar.');
    } finally {
      setLoading(false);
    }
  };

  const saveAnalysis = async () => {
    setSaving(true);
    try {
      await fetch(
        `${apiBase}/executions/${executionId}/attachments/${attachmentId}/analysis`,
        {
          method: 'PUT',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
          body: JSON.stringify({ ai_analysis: localAnalysis }),
        },
      );
      setIsEdited(false);
      onAnalysisUpdated(attachmentId, localAnalysis);
    } catch (err) {
      console.error('Error saving analysis:', err);
    } finally {
      setSaving(false);
    }
  };

  const formatDate = (iso: string | null) => {
    if (!iso) return '';
    try {
      return new Date(iso).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' });
    } catch {
      return iso;
    }
  };

  // No analysis yet
  if (!aiAnalysis && !localAnalysis && !loading) {
    return (
      <div className="mt-2 p-3 bg-gray-50 border border-dashed border-gray-300 rounded-xl text-center">
        <button
          onClick={analyzeImage}
          disabled={loading}
          className="px-4 py-2 bg-[#f5a623] text-[#0a1628] rounded-lg font-bold text-sm hover:bg-[#f5a623]/90 transition-colors flex items-center gap-2 mx-auto"
        >
          <Sparkles className="w-4 h-4" /> Analizar con AI
        </button>
        {error && <p className="text-sm text-red-500 mt-2">{error}</p>}
      </div>
    );
  }

  // Loading state
  if (loading) {
    return (
      <div className="mt-2 p-4 bg-amber-50 border border-amber-200 rounded-xl flex items-center gap-3">
        <Loader2 className="w-5 h-5 text-[#f5a623] animate-spin" />
        <span className="text-sm text-amber-700">Analizando imagen con Gemini Vision...</span>
      </div>
    );
  }

  // Has analysis
  return (
    <div className="mt-4 bg-white rounded-xl p-5 border-l-4 border-orange-500 border border-gray-200">
      <div className="flex items-center justify-between mb-2">
        <h4 className="font-bold text-orange-600 text-xl">Analisis</h4>
        <span className="text-xs text-gray-400 italic">{aiAnalysisUpdatedAt ? formatDate(aiAnalysisUpdatedAt) : 'Click para editar'}</span>
      </div>
        <textarea
          value={localAnalysis}
          onChange={(e) => { setLocalAnalysis(e.target.value); setIsEdited(true); }}
          className="w-full min-h-[100px] p-3 border border-gray-200 rounded-lg text-sm text-gray-800 resize-y focus:border-orange-400 focus:ring-1 focus:ring-orange-400/30 cursor-text hover:border-orange-300 transition-colors"
          placeholder="Analisis de la imagen..."
        />
        <div className="flex items-center justify-end gap-2 mt-2">
          {isEdited && (
            <button
              onClick={saveAnalysis}
              disabled={saving}
              className="px-3 py-1.5 bg-[#0a1628] text-white rounded-lg text-sm font-medium hover:bg-[#0a1628]/90 flex items-center gap-1.5 transition-colors disabled:opacity-50"
            >
              <Save className="w-3.5 h-3.5" />
              {saving ? 'Guardando...' : 'Guardar'}
            </button>
          )}
          <button
            onClick={analyzeImage}
            disabled={loading}
            className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 flex items-center gap-1.5 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Regenerar
          </button>
        </div>
        {error && <p className="text-sm text-red-500 mt-2">{error}</p>}
    </div>
  );
}
