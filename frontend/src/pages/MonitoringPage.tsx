/**
 * MonitoringPage — Standalone page for infrastructure monitoring metrics.
 * Upload images/CSV, per-image AI analysis with Gemini Vision, global analysis.
 */
import { useState, useEffect, useCallback } from 'react';
import { Upload, Trash2, FileText, Cpu, Sparkles } from 'lucide-react';
import { testAPI } from '../services/api';
import ImageAnalysisCard from '../components/analysis/ImageAnalysisCard';
import type { ImageSaveState } from '../components/analysis/ImageAnalysisCard';   // R2
import EditableAttachmentTitle from '../components/analysis/EditableAttachmentTitle';
import { useAuth } from '../context/AuthContext';

interface Attachment {
  id: string;
  title: string;
  description: string;
  category: string;
  filename: string;
  filepath: string;
  file_type: string;
  ai_analysis?: string | null;
  ai_analysis_updated_at?: string | null;
}

const CATEGORIES = [
  { value: 'cpu', label: 'CPU' },
  { value: 'memory', label: 'Memoria' },
  { value: 'database', label: 'Base de Datos' },
  { value: 'apm', label: 'APM / Application Performance' },
  { value: 'network', label: 'Red / I/O' },
  { value: 'logs', label: 'Logs' },
  { value: 'other', label: 'Otro' },
];

export default function MonitoringPage() {
  // SEC-2: borrar es exclusivo de admin (el backend responde 403 al resto).
  const { user } = useAuth();

  // R2: autoguardado del analisis de cada imagen (patron F3/R1). El indicador
  // es uno solo para toda la pagina; cada tarjeta reporta su estado aqui.
  const AUTOSAVE_MS = 1800;
  const [saveState, setSaveState] = useState<ImageSaveState>('idle');
  const [savedAt, setSavedAt] = useState('');
  const [retrySave, setRetrySave] = useState<{ fn: () => void }>({ fn: () => {} });
  const handleSaveState = useCallback((s: ImageSaveState, at: string, retry: () => void) => {
    setSaveState(s);
    if (at) setSavedAt(at);
    setRetrySave({ fn: retry });
  }, []);
  const [executions, setExecutions] = useState<any[]>([]);
  const [selectedExecId, setSelectedExecId] = useState('');
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [uploading, setUploading] = useState(false);
  const [generatingAI, setGeneratingAI] = useState(false);
  const [aiAnalysis, setAiAnalysis] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('cpu');
  const [title, setTitle] = useState('');
  const [listLoading, setListLoading] = useState(true);
  const [analyzingAll, setAnalyzingAll] = useState(false);

  const getCsrfToken = () => document.cookie.match(/csrf_token=([^;]+)/)?.[1] || '';
  const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';
  const mediaBase = apiBase.replace('/api/v1', '');

  useEffect(() => {
    testAPI.getExecutions()
      .then(d => setExecutions(Array.isArray(d) ? d : []))
      .catch(() => {})
      .finally(() => setListLoading(false));
  }, []);

  const loadAttachments = useCallback(async () => {
    if (!selectedExecId) { setAttachments([]); return; }
    try {
      // Load attachments + their AI analyses in one call
      const res = await fetch(`${apiBase}/executions/${selectedExecId}/image-analyses?attachment_type=monitoring`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setAttachments(data);
      } else {
        // Fallback to basic attachments list
        const res2 = await fetch(`${apiBase}/executions/${selectedExecId}/attachments?attachment_type=monitoring`, { credentials: 'include' });
        if (res2.ok) setAttachments(await res2.json());
      }
    } catch { /* ignore */ }
  }, [selectedExecId, apiBase]);

  useEffect(() => { loadAttachments(); }, [loadAttachments]);

  useEffect(() => {
    if (!selectedExecId) { setAiAnalysis(''); return; }
    fetch(`${apiBase}/executions/${selectedExecId}/monitoring-analysis`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setAiAnalysis(d.analysis || ''); })
      .catch(() => {});
  }, [selectedExecId, apiBase]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || !selectedExecId) return;
    setUploading(true);
    for (const file of Array.from(files)) {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('attachment_type', 'monitoring');
      formData.append('title', title || file.name);
      formData.append('category', selectedCategory);
      formData.append('sort_order', String(attachments.length));
      await fetch(`${apiBase}/executions/${selectedExecId}/attachments`, {
        method: 'POST', body: formData, credentials: 'include',
        headers: { 'X-CSRF-Token': getCsrfToken() },
      });
    }
    setUploading(false);
    setTitle('');
    e.target.value = '';
    loadAttachments();
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Eliminar este adjunto?')) return;
    await fetch(`${apiBase}/executions/${selectedExecId}/attachments/${id}`, {
      method: 'DELETE', credentials: 'include', headers: { 'X-CSRF-Token': getCsrfToken() },
    });
    loadAttachments();
  };

  const handleGenerateAI = async () => {
    if (!selectedExecId || attachments.length === 0) return;
    setGeneratingAI(true);
    try {
      const res = await fetch(`${apiBase}/executions/${selectedExecId}/monitoring-analysis`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
        body: JSON.stringify({ attachments: attachments.map(a => ({ category: a.category, title: a.title, description: a.description, file_type: a.file_type })) }),
      });
      if (res.ok) { const d = await res.json(); setAiAnalysis(d.analysis || ''); }
    } catch (err) { console.error(err); }
    setGeneratingAI(false);
  };

  const handleAnalyzeAll = async () => {
    if (!selectedExecId) return;
    setAnalyzingAll(true);
    try {
      const res = await fetch(`${apiBase}/executions/${selectedExecId}/analyze-all-images?attachment_type=monitoring`, {
        method: 'POST', credentials: 'include', headers: { 'X-CSRF-Token': getCsrfToken() },
      });
      if (res.ok) {
        const data = await res.json();
        alert(`Analisis completado: ${data.analyzed_count} imagenes analizadas, ${data.failed_count} errores`);
        loadAttachments();
      }
    } catch (err) { console.error(err); }
    setAnalyzingAll(false);
  };

  const imageCount = attachments.filter(a => a.file_type?.startsWith('image/')).length;
  const analyzedCount = attachments.filter(a => a.file_type?.startsWith('image/') && a.ai_analysis).length;

  return (
    <div className="w-full p-6">
      <div className="flex items-center gap-3 mb-2">
        <Cpu className="w-8 h-8 text-[#f5a623]" />
        <h1 className="text-4xl font-bold text-gray-800">Metricas de Monitoreo</h1>
      </div>
      <p className="text-lg text-gray-500 mb-6">
        Adjunte capturas de dashboards APM, graficas de infraestructura o archivos CSV. Genere analisis AI por imagen.
      </p>

      {/* Step 1: Execution selector */}
      <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-200 mb-6">
        <label className="text-base font-medium text-gray-600 block mb-2">1. Seleccionar ejecucion / proyecto</label>
        <select value={selectedExecId} onChange={(e) => setSelectedExecId(e.target.value)}
          disabled={listLoading}
          className="w-full bg-white text-gray-800 rounded-xl px-4 py-3 text-lg border border-gray-300 focus:border-[#f5a623] focus:ring-2 focus:ring-[#f5a623]/20">
          <option value="">{listLoading ? 'Cargando ejecuciones...' : 'Seleccionar ejecucion...'}</option>
          {executions.map(e => (
            <option key={e.id} value={e.id}>{e.name} — {e.client || 'N/A'} — {new Date(e.start_time || e.created_at).toLocaleDateString()}</option>
          ))}
        </select>
      </div>

      {!selectedExecId && !listLoading && (
        <div className="bg-amber-50 border-2 border-amber-200 rounded-2xl p-8 text-center">
          <p className="text-xl text-amber-700 font-medium mb-2">Seleccione una ejecucion del listado de arriba para comenzar</p>
          <p className="text-lg text-amber-600">Al seleccionar, apareceran los controles para adjuntar metricas y generar analisis AI.</p>
        </div>
      )}

      {selectedExecId && (
        <>
          {/* Step 2: Upload */}
          <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-200 mb-6">
            <h2 className="text-2xl font-bold text-gray-800 mb-4">2. Adjuntar Metricas</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="text-base font-medium text-gray-600 block mb-1">Categoria</label>
                <select value={selectedCategory} onChange={(e) => setSelectedCategory(e.target.value)}
                  className="w-full bg-white text-gray-800 rounded-xl px-4 py-3 text-lg border border-gray-300 focus:border-[#f5a623]">
                  {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>
              </div>
              <div>
                <label className="text-base font-medium text-gray-600 block mb-1">Titulo (opcional)</label>
                <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Ej: CPU durante carga"
                  className="w-full bg-white text-gray-800 rounded-xl px-4 py-3 text-lg border border-gray-300 focus:border-[#f5a623]" />
              </div>
              <div className="flex items-end">
                <label className="flex items-center gap-2 px-6 py-3 bg-[#f5a623] text-[#0a1628] rounded-xl cursor-pointer hover:bg-[#f5a623]/90 text-lg font-bold transition-colors">
                  <Upload className="w-5 h-5" />
                  {uploading ? 'Subiendo...' : 'Adjuntar archivo'}
                  <input type="file" accept="image/png,image/jpeg,image/gif,image/webp,.csv" multiple onChange={handleUpload} disabled={uploading} className="hidden" />
                </label>
              </div>
            </div>
          </div>

          {/* Step 3: Attachments list with per-image AI */}
          {attachments.length > 0 && (
            <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-200 mb-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-2xl font-bold text-gray-800">Metricas Adjuntas ({attachments.length})</h2>
                {imageCount > 0 && (
                  <button onClick={handleAnalyzeAll} disabled={analyzingAll}
                    className="px-4 py-2 bg-[#f5a623] text-[#0a1628] rounded-xl font-bold text-sm hover:bg-[#f5a623]/90 disabled:opacity-50 transition-colors flex items-center gap-2">
                    <Sparkles className="w-4 h-4" />
                    {analyzingAll ? 'Analizando...' : `Analizar Todas (${analyzedCount}/${imageCount})`}
                  </button>
                )}
              </div>
              <div className="space-y-4">
                {attachments.map(att => (
                  <div key={att.id} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-6">
                    <div className="flex justify-between items-start mb-4">
                      <div className="border-l-4 border-[#0a1628] pl-4">
                        <EditableAttachmentTitle attachmentId={att.id} executionId={selectedExecId} currentTitle={att.title || att.filename}
                          onTitleSaved={(attId, newTitle) => setAttachments(prev => prev.map(a => a.id === attId ? { ...a, title: newTitle } : a))} />
                      </div>
                      {user?.role === 'admin' && <button onClick={() => handleDelete(att.id)} className="text-red-400 hover:text-red-600 transition-colors p-1"><Trash2 className="w-5 h-5" /></button>}
                    </div>
                    {att.file_type?.startsWith('image/') && (
                      <>
                        <img src={`${mediaBase}${att.filepath}`} alt={att.title} className="w-full max-h-[800px] rounded-xl object-contain bg-white mb-4" />
                        <ImageAnalysisCard
                          executionId={selectedExecId}
                          attachmentId={att.id}
                          aiAnalysis={att.ai_analysis || null}
                          aiAnalysisUpdatedAt={att.ai_analysis_updated_at || null}
                          onAnalysisUpdated={(attId, analysis) => {
                            setAttachments(prev => prev.map(a => a.id === attId ? { ...a, ai_analysis: analysis } : a));
                          }}
                          autoSaveMs={AUTOSAVE_MS}
                          onSaveStateChange={handleSaveState}
                        />
                      </>
                    )}
                    {(att.file_type === 'text/csv' || att.file_type === 'application/vnd.ms-excel') && (
                      <div className="bg-gray-100 rounded-xl p-4 flex items-center gap-2 text-lg text-gray-600"><FileText className="w-5 h-5" /> CSV: {att.filename}</div>
                    )}
                  </div>
                ))}
              </div>

              {/* Global analysis button (existing) */}
              <div className="mt-6 flex justify-center">
                <button onClick={handleGenerateAI} disabled={generatingAI}
                  className="px-8 py-3 bg-gray-200 text-gray-700 rounded-xl font-bold text-lg hover:bg-gray-300 disabled:opacity-50 transition-colors flex items-center gap-2">
                  {generatingAI ? 'Generando...' : 'Generar Analisis Global'}
                </button>
              </div>
            </div>
          )}

          {attachments.length === 0 && (
            <div className="bg-gray-50 border-2 border-dashed border-gray-300 rounded-2xl p-8 text-center">
              <p className="text-lg text-gray-400">No hay metricas adjuntas aun. Use el formulario de arriba para adjuntar imagenes o CSV.</p>
            </div>
          )}

          {aiAnalysis && (
            <div className="mt-6 bg-white rounded-2xl shadow-lg p-6 border-l-4 border-orange-500 border border-gray-200">
              <h2 className="text-2xl font-bold text-orange-600 mb-3">Analisis Global de Metricas</h2>
              <div className="text-xl text-gray-800 whitespace-pre-wrap leading-relaxed">{aiAnalysis}</div>
            </div>
          )}
        </>
      )}

      {/* R2: indicador fijo de autoguardado — mismo patron que F3/R1 */}
      <div className="fixed bottom-6 right-6 z-40 flex items-center gap-3 bg-white/95 backdrop-blur border border-gray-200 shadow-xl rounded-2xl px-4 py-3">
        <span className={`text-sm font-medium ${saveState === 'error' ? 'text-red-600' : saveState === 'saving' ? 'text-gray-500' : saveState === 'saved' ? 'text-emerald-700' : 'text-gray-400'}`}>
          {saveState === 'saving' ? 'Guardando...' : saveState === 'saved' ? `Guardado ${savedAt}` : saveState === 'error' ? 'Error al guardar' : 'Autoguardado activo'}
        </span>
        {saveState === 'error' && (
          <button onClick={() => retrySave.fn()}
            className="px-3 py-1.5 bg-red-600 text-white text-sm font-semibold rounded-lg hover:bg-red-700 transition-colors">
            Reintentar
          </button>
        )}
      </div>
    </div>
  );
}
