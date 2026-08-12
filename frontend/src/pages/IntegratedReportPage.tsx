/**
 * IntegratedReportPage — Drag-and-drop report builder.
 * Select executions, monitoring, evidence from history.
 * Reorder sections via drag. Generate unified report with AI conclusions.
 */
import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  DndContext, closestCenter, KeyboardSensor, PointerSensor,
  useSensor, useSensors, DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove, SortableContext, sortableKeyboardCoordinates,
  verticalListSortingStrategy, useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { FileDown, GripVertical, X, Plus, Layers, Pencil } from 'lucide-react';
import { testAPI } from '../services/api';
import DashboardEmbed from '../components/integrated/DashboardEmbed';
import MonitoringReportSection from '../components/integrated/MonitoringReportSection';
import ConsolidatedAnalysisSection from '../components/integrated/ConsolidatedAnalysisSection';

// ─── Types ────────────────────────────────────────────────────────────────────
interface ReportSection {
  id: string;
  type: 'load_test' | 'stress_test' | 'monitoring' | 'evidence';
  sourceId: string;
  sourceName: string;
  sourceDate: string;
}

// F3: retardo del autosave tras la ultima tecla.
const SAVE_DEBOUNCE_MS = 1800;

// F3: aplana el consolidado al texto plano que consumen los exports.
function flattenConsolidated(data: Record<string, any>): string {
  return Object.entries(data || {})
    .filter(([k]) => !k.startsWith('_'))
    .map(([tt, d]: [string, any]) => {
      const label = tt === 'load' ? 'PRUEBA DE CARGA' : 'PRUEBA DE ESTRES';
      return `${label}\n\nConclusiones:\n${d?.conclusions || ''}\n\nRecomendaciones:\n${d?.recommendations || ''}`;
    }).join('\n\n---\n\n');
}

// ─── Sortable Item ────────────────────────────────────────────────────────────
function SortableItem({ section, onRemove }: { section: ReportSection; onRemove: () => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: section.id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 };

  const icons: Record<string, string> = { load_test: '🔵', stress_test: '🔴', monitoring: '📊', evidence: '🔍' };
  const labels: Record<string, string> = { load_test: 'Carga', stress_test: 'Estres', monitoring: 'Monitoreo', evidence: 'Evidencias' };

  return (
    <div ref={setNodeRef} style={style}
      className={`flex items-center gap-3 p-4 rounded-xl border-2 ${isDragging ? 'border-[#f5a623] bg-gray-100' : 'border-gray-200 bg-white'} hover:border-gray-300 transition-colors shadow-sm`}>
      <div {...attributes} {...listeners} className="cursor-grab active:cursor-grabbing text-gray-400 hover:text-gray-600 p-1" title="Arrastrar">
        <GripVertical className="w-5 h-5" />
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2 mb-1">
          <span>{icons[section.type]}</span>
          <span className="text-sm px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 font-semibold">{labels[section.type]}</span>
        </div>
        <div className="text-lg font-medium text-gray-800">{section.sourceName}</div>
        <div className="text-sm text-gray-400">{section.sourceDate}</div>
      </div>
      <button onClick={onRemove} className="text-red-400 hover:text-red-600 p-1 transition-colors" title="Quitar"><X className="w-5 h-5" /></button>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function IntegratedReportPage() {
  const { reportId: urlReportId } = useParams<{ reportId?: string }>();
  const navigate = useNavigate();

  const [executions, setExecutions] = useState<any[]>([]);
  const [sections, setSections] = useState<ReportSection[]>([]);
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState('');
  const [reportHtml, setReportHtml] = useState('');
  const [conclusions, setConclusions] = useState('');
  const [consolidatedAnalysis, setConsolidatedAnalysis] = useState<Record<string, any>>({});
  const [attCounts, setAttCounts] = useState<Record<string, { monitoring: number; evidence: number }>>({});

  // HF9.1: Persistence state
  const [persistedId, setPersistedId] = useState<string | null>(null);
  const [reportName, setReportName] = useState('');
  const [renameOpen, setRenameOpen] = useState(false);
  const [hydrating, setHydrating] = useState(!!urlReportId);

  // F3: estado del indicador de guardado (solo cambia cuando se guarda de verdad)
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [savedAt, setSavedAt] = useState('');

  // F3: todo lo que cambia por tecla vive en refs — nunca provoca re-render
  const saveTimerRef = useRef<number | null>(null);
  const pendingEditsRef = useRef<Record<string, Record<string, string>>>({});
  const dirtyRef = useRef(false);
  const consolidatedRef = useRef<Record<string, any>>({});
  const persistedIdRef = useRef<string | null>(null);
  const reportNameRef = useRef('');
  const sectionsRef = useRef<ReportSection[]>([]);   // F4: para armar el payload de sections

  const getCsrfToken = () => document.cookie.match(/csrf_token=([^;]+)/)?.[1] || '';
  const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';

  // F3: espejo en refs del estado que los callbacks necesitan sin closures viejos
  useEffect(() => {
    consolidatedRef.current = consolidatedAnalysis;
    persistedIdRef.current = persistedId;
    reportNameRef.current = reportName;
    sectionsRef.current = sections;
  }, [consolidatedAnalysis, persistedId, reportName, sections]);

  // F2: ediciones de las cajas de SECCION (dashboards e imagenes). Viven en un
  // ref para no re-renderizar nada por tecla. Forma — contrato para F4:
  //   { [executionId]: { analysis: { <campo_db>: texto }, images: { [attachmentId]: texto } } }
  // que en F4 se persiste dentro de cada entrada de `sections` como `overrides`.
  type SectionOverride = { analysis: Record<string, string>; images: Record<string, string> };
  const sectionOverridesRef = useRef<Record<string, SectionOverride>>({});
  // F4: copia en estado SOLO para hidratar los hijos al abrir (nunca por tecla)
  const [sectionOverrides, setSectionOverrides] = useState<Record<string, SectionOverride>>({});

  const touchSection = useCallback((execId: string) => {
    if (!sectionOverridesRef.current[execId]) {
      sectionOverridesRef.current[execId] = { analysis: {}, images: {} };
    }
    return sectionOverridesRef.current[execId];
  }, []);

  // F4: sections con sus overrides, listo para el PATCH
  const buildSectionsPayload = useCallback(() => {
    const ov = sectionOverridesRef.current;
    return sectionsRef.current.map((s, idx) => {
      const base: Record<string, any> = { order: idx, type: s.type, source_id: s.sourceId, source_name: s.sourceName };
      const o = ov[s.sourceId];
      if (o && (Object.keys(o.analysis).length || Object.keys(o.images).length)) {
        base.overrides = { analysis: o.analysis, images: o.images };
      }
      return base;
    });
  }, []);

  // F3: base (estado de la pagina) + ediciones pendientes por tecla
  const buildMergedConsolidated = useCallback((): Record<string, any> => {
    const base = consolidatedRef.current || {};
    const pend = pendingEditsRef.current;
    if (!Object.keys(pend).length) return base;
    const merged: Record<string, any> = { ...base };
    Object.entries(pend).forEach(([tt, fields]) => {
      merged[tt] = { ...(base[tt] || {}), ...fields, edited: true };
    });
    return merged;
  }, []);

  // HF9.1 / F3: Persist edits to DB — ahora con indicador de estado
  const persistEdit = useCallback(async (updates: Record<string, any>) => {
    if (!persistedIdRef.current) return false;
    setSaveState('saving');
    try {
      const res = await fetch(`${apiBase}/reports/integrated-reports/${persistedIdRef.current}`, {
        method: 'PATCH', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
        body: JSON.stringify(updates),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      dirtyRef.current = false;
      setSaveState('saved');
      setSavedAt(new Date().toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' }));
      return true;
    } catch (e) {
      console.error('Error persisting edit:', e);
      setSaveState('error');
      return false;
    }
  }, [apiBase]);

  // F3 + F4: guardado efectivo — consolidado Y overrides de seccion en el mismo
  // PATCH (cancela cualquier debounce en vuelo)
  const saveNow = useCallback(async (includeName = false) => {
    if (saveTimerRef.current) { clearTimeout(saveTimerRef.current); saveTimerRef.current = null; }
    const merged = buildMergedConsolidated();
    const payload: Record<string, any> = { consolidated_analysis: merged };
    // Guarda: nunca mandar una lista vacia — borraria las secciones guardadas.
    const secs = buildSectionsPayload();
    if (secs.length) payload.sections = secs;
    if (includeName) payload.name = reportNameRef.current;
    const ok = await persistEdit(payload);
    // El texto plano de los exports se sincroniza con lo que quedo guardado.
    if (ok) setConclusions(flattenConsolidated(merged));
    return ok;
  }, [buildMergedConsolidated, buildSectionsPayload, persistEdit]);

  // F3 + F4: rearma el debounce. Lo comparten el consolidado y las secciones.
  const scheduleSave = useCallback(() => {
    dirtyRef.current = true;
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = window.setTimeout(() => {
      saveTimerRef.current = null;
      if (dirtyRef.current) saveNow();
    }, SAVE_DEBOUNCE_MS);
  }, [saveNow]);

  // F3: una tecla — solo refs y rearme del timer, CERO setState
  const handleDraftChange = useCallback((testType: string, field: string, value: string) => {
    const pend = pendingEditsRef.current;
    pend[testType] = { ...(pend[testType] || {}), [field]: value };
    scheduleSave();
  }, [scheduleSave]);

  // F2 + F4: caja de analisis del dashboard embebido (se emite en el blur)
  const handleSectionAnalysisEdit = useCallback((execId: string, field: string, value: string) => {
    touchSection(execId).analysis[field] = value;
    scheduleSave();
  }, [touchSection, scheduleSave]);

  // F2 + F4: analisis de imagen (se emite por tecla — solo refs)
  const handleSectionImageEdit = useCallback((execId: string, attachmentId: string, value: string) => {
    touchSection(execId).images[attachmentId] = value;
    scheduleSave();
  }, [touchSection, scheduleSave]);

  // F3: vacia el debounce pendiente antes de acciones que leen lo guardado
  const flushPending = useCallback(async () => {
    if (saveTimerRef.current) { clearTimeout(saveTimerRef.current); saveTimerRef.current = null; }
    if (dirtyRef.current) await saveNow();
  }, [saveNow]);

  // F3: descarga de la pagina — intento best-effort con keepalive + limpieza del timer
  useEffect(() => {
    const onBeforeUnload = () => {
      if (!dirtyRef.current || !persistedIdRef.current) return;
      fetch(`${apiBase}/reports/integrated-reports/${persistedIdRef.current}`, {
        method: 'PATCH', credentials: 'include', keepalive: true,
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
        body: JSON.stringify({ consolidated_analysis: buildMergedConsolidated() }),
      }).catch(() => {});
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => {
      window.removeEventListener('beforeunload', onBeforeUnload);
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, [apiBase, buildMergedConsolidated]);

  // HF9.1: Hydrate from DB when URL has reportId
  useEffect(() => {
    if (urlReportId) {
      setHydrating(true);
      fetch(`${apiBase}/reports/integrated-reports/${urlReportId}`, { credentials: 'include' })
        .then(res => res.ok ? res.json() : Promise.reject('not found'))
        .then(data => {
          setPersistedId(data.id);
          setReportName(data.name || '');
          setConsolidatedAnalysis(data.consolidated_analysis || {});
          // Rebuild sections from saved data
          const savedSections: ReportSection[] = (data.sections || []).map((s: any, idx: number) => ({
            id: `${s.type}-${idx}-${Date.now()}`,
            type: s.type,
            sourceId: s.source_id,
            sourceName: s.source_name,
            sourceDate: '',
          }));
          setSections(savedSections);
          // F4: recuperar los overrides guardados. Los informes anteriores a F4
          // no traen `overrides`: se toleran con defaults y quedan vacios.
          const savedOverrides: Record<string, SectionOverride> = {};
          (data.sections || []).forEach((s: any) => {
            const ov = s?.overrides;
            if (ov && (ov.analysis || ov.images)) {
              savedOverrides[s.source_id] = { analysis: ov.analysis || {}, images: ov.images || {} };
            }
          });
          sectionOverridesRef.current = savedOverrides;
          setSectionOverrides(savedOverrides);
          // Set reportHtml to trigger the report view
          if (savedSections.length > 0) setReportHtml('hydrated');
          // Flatten consolidated for exports
          if (data.consolidated_analysis && Object.keys(data.consolidated_analysis).length > 0) {
            const allText = Object.entries(data.consolidated_analysis).map(([tt, d]: [string, any]) => {
              const label = tt === 'load' ? 'PRUEBA DE CARGA' : 'PRUEBA DE ESTRES';
              return `${label}\n\nConclusiones:\n${d.conclusions}\n\nRecomendaciones:\n${d.recommendations}`;
            }).join('\n\n---\n\n');
            setConclusions(allText);
          }
        })
        .catch(e => console.error('Error hydrating integrated report:', e))
        .finally(() => setHydrating(false));
    }
  }, [urlReportId, apiBase]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  useEffect(() => {
    testAPI.getExecutions().then(async (d) => {
      const list = Array.isArray(d) ? d : [];
      setExecutions(list);
      // Load attachment counts per execution
      const counts: Record<string, { monitoring: number; evidence: number }> = {};
      await Promise.all(list.map(async (e: any) => {
        try {
          const res = await fetch(`${apiBase}/executions/${e.id}/attachment-counts`, { credentials: 'include' });
          if (res.ok) counts[e.id] = await res.json();
        } catch { counts[e.id] = { monitoring: 0, evidence: 0 }; }
      }));
      setAttCounts(counts);
    }).catch(() => {});
  }, [apiBase]);

  // HF9.3-B: Auto-validation of footer DOM structure
  useEffect(() => {
    if (hydrating || !reportHtml) return;
    const timer = setTimeout(() => {
      let footerCount = 0;
      document.querySelectorAll('p').forEach(p => {
        if (p.textContent?.includes('Del pasado aprendimos')) footerCount++;
      });
      if (footerCount === 0) console.error('[HF9.3-B AUTO-CHECK] Footer SQA NO encontrado en el DOM');
      else if (footerCount > 1) console.error(`[HF9.3-B AUTO-CHECK] Hay ${footerCount} footers SQA en el DOM (esperaba 1)`);
      else console.log('[HF9.3-B AUTO-CHECK] Footer SQA unico encontrado');
    }, 500);
    return () => clearTimeout(timer);
  }, [hydrating, reportHtml, sections]);

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      setSections(items => {
        const oldIdx = items.findIndex(i => i.id === active.id);
        const newIdx = items.findIndex(i => i.id === over.id);
        return arrayMove(items, oldIdx, newIdx);
      });
    }
  };

  const addSection = (exec: any, type: ReportSection['type']) => {
    setSections(prev => [...prev, {
      id: `${type}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      type,
      sourceId: exec.id,
      sourceName: type === 'monitoring' ? `Monitoreo: ${exec.name}` : type === 'evidence' ? `Evidencias: ${exec.name}` : exec.name,
      sourceDate: new Date(exec.start_time || exec.created_at).toLocaleString('es-CO'),
    }]);
  };

  const handleGenerate = async () => {
    if (sections.length === 0) return;
    setGenerating(true);
    setGenerateError('');
    try {
      const res = await fetch(`${apiBase}/reports/integrated`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
        body: JSON.stringify({
          sections: sections.map((s, idx) => ({ order: idx, type: s.type, source_id: s.sourceId, source_name: s.sourceName })),
          // F1: si el informe se reabrio del historial ya tiene id — no crear duplicado
          report_id: persistedId,
          name: reportName || null,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setReportHtml(data.report_html || '');
        setConclusions(data.unified_conclusions || '');
        // F1: guardar el id del registro para que persistEdit deje de ser no-op
        if (data.report_id) {
          if (!persistedId) {
            setPersistedId(data.report_id);
            persistedIdRef.current = data.report_id;
            // F3: URL persistente sin navegar. replaceState nativo no cambia el
            // useParams de react-router, asi que NO dispara la hidratacion ni
            // remonta los dashboards; pero un F5 recarga ya este informe.
            window.history.replaceState(null, '', `/performance/integrated/${data.report_id}`);
          }
          if (data.report_name && !reportName) setReportName(data.report_name);
        } else {
          setGenerateError('El informe se genero, pero no se pudo crear su registro en el historial. Los cambios que edite NO se guardaran.');
        }
      } else {
        setGenerateError('Error al generar el informe integrado. Intente de nuevo.');
      }
    } catch (err) {
      console.error(err);
      setGenerateError('Error de conexion al generar el informe integrado.');
    }
    setGenerating(false);
  };

  const handleExportPDF = async () => {
    await flushPending();  // F3: no exportar con ediciones sin guardar
    try {
      const res = await fetch(`${apiBase}/reports/integrated/export-pdf`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
        body: JSON.stringify({
          sections: sections.map((s, idx) => ({ order: idx, type: s.type, source_id: s.sourceId, source_name: s.sourceName })),
          unified_conclusions: conclusions,
          report_id: persistedId,   // F6: el backend lee los overrides de este registro
        }),
      });
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `informe_integrado_${new Date().toISOString().slice(0, 10)}.pdf`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch (err) { console.error(err); }
  };

  const handleExportHTML = async () => {
    await flushPending();  // F3: no exportar con ediciones sin guardar
    try {
      const res = await fetch(`${apiBase}/reports/integrated/export-html`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
        body: JSON.stringify({
          sections: sections.map((s, idx) => ({ order: idx, type: s.type, source_id: s.sourceId, source_name: s.sourceName })),
          unified_conclusions: conclusions,
          report_id: persistedId,   // F6: el backend lee los overrides de este registro
        }),
      });
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `informe_integrado_${new Date().toISOString().slice(0, 10)}.html`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch (err) { console.error(err); }
  };

  // F3: el arbol de secciones se memoiza sobre `sections`. Al cambiar solo el
  // indicador de guardado, React reusa estos elementos identicos y NO vuelve a
  // renderizar los dashboards embebidos ni las imagenes.
  const sectionsTree = useMemo(() => sections.map((s, idx) => {
    if (s.type === 'monitoring' || s.type === 'evidence') {
      return (
        <MonitoringReportSection
          key={s.id}
          executionId={s.sourceId}
          attachmentType={s.type === 'monitoring' ? 'monitoring' : 'evidence'}
          sectionTitle={s.type === 'monitoring' ? 'Metricas de Monitoreo' : 'Evidencias y Hallazgos'}
          onImageAnalysisEdit={(attId, value) => handleSectionImageEdit(s.sourceId, attId, value)}
          imageOverrides={sectionOverrides[s.sourceId]?.images}
        />
      );
    }
    // For load_test/stress_test: only render monitoring/evidence if NOT already added as standalone sections
    const hasMonitoring = sections.some(x => x.type === 'monitoring' && x.sourceId === s.sourceId);
    const hasEvidence = sections.some(x => x.type === 'evidence' && x.sourceId === s.sourceId);
    return (
      <div key={s.id}>
        {idx > 0 && <hr className="my-6 border-2 border-[#0a1628]" />}
        <DashboardEmbed executionId={s.sourceId} onAnalysisEdit={handleSectionAnalysisEdit}
          analysisOverrides={sectionOverrides[s.sourceId]?.analysis} />
        {!hasMonitoring && <MonitoringReportSection executionId={s.sourceId} attachmentType="monitoring" sectionTitle="Metricas de Monitoreo"
          onImageAnalysisEdit={(attId, value) => handleSectionImageEdit(s.sourceId, attId, value)}
          imageOverrides={sectionOverrides[s.sourceId]?.images} />}
        {!hasEvidence && <MonitoringReportSection executionId={s.sourceId} attachmentType="evidence" sectionTitle="Evidencias y Hallazgos"
          onImageAnalysisEdit={(attId, value) => handleSectionImageEdit(s.sourceId, attId, value)}
          imageOverrides={sectionOverrides[s.sourceId]?.images} />}
      </div>
    );
  }), [sections, sectionOverrides, handleSectionAnalysisEdit, handleSectionImageEdit]);

  const typeMap: Record<string, ReportSection['type']> = { load: 'load_test', stress: 'stress_test', spike: 'stress_test', endurance: 'load_test', scalability: 'load_test', smoke: 'load_test' };

  // HF9.2: Block render during hydration — show spinner instead
  if (hydrating) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] p-8">
        <div className="animate-spin rounded-full h-16 w-16 border-4 border-slate-200 border-t-[#f5a623] mb-4"></div>
        <p className="text-slate-600 text-lg font-medium">Cargando informe integrado...</p>
        <p className="text-slate-400 text-sm mt-2">Recuperando analisis consolidado, metricas y evidencias</p>
      </div>
    );
  }

  return (
    <div className="w-full p-6">
      <div className="flex items-center gap-3 mb-2">
        <Layers className="w-8 h-8 text-[#f5a623]" />
        <h1 className="text-4xl font-bold text-gray-800">
          {persistedId && reportName ? reportName : 'Informe Integrado'}
        </h1>
        {persistedId && (
          <button onClick={() => setRenameOpen(true)} className="p-1 text-gray-400 hover:text-[#f5a623] transition-colors" title="Renombrar">
            <Pencil className="w-5 h-5" />
          </button>
        )}
      </div>
      <p className="text-lg text-gray-500 mb-6">
        {hydrating ? 'Cargando informe...' : 'Seleccione las ejecuciones, metricas de monitoreo y evidencias que desea integrar. Arrastre para reordenar.'}
      </p>

      {/* HF9.1: Rename modal */}
      {renameOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white p-6 rounded-xl shadow-xl w-96">
            <h3 className="text-lg font-bold text-[#0a1628] mb-3">Renombrar Informe</h3>
            <input type="text" defaultValue={reportName} autoFocus id="rename-input"
              className="w-full p-3 border border-gray-300 rounded-lg text-lg focus:outline-none focus:border-[#f5a623]" />
            <div className="flex justify-end gap-2 mt-4">
              <button onClick={() => setRenameOpen(false)} className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg">Cancelar</button>
              <button onClick={async () => {
                const input = document.getElementById('rename-input') as HTMLInputElement;
                const newName = input?.value?.trim();
                if (newName) {
                  setReportName(newName);
                  await persistEdit({ name: newName });
                }
                setRenameOpen(false);
              }} className="px-4 py-2 bg-[#0a1628] text-white rounded-lg hover:bg-[#1a2638]">Guardar</button>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: History */}
        <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-200">
          <h2 className="text-2xl font-bold text-gray-800 mb-4">Historial Disponible</h2>
          <div className="space-y-2 max-h-[500px] overflow-y-auto">
            {executions.map(exec => (
              <div key={exec.id} className="flex items-center justify-between p-3 rounded-xl border border-gray-200 bg-gray-50 hover:bg-gray-100 transition-colors">
                <div>
                  <div className="text-lg font-medium text-gray-800">{exec.name}</div>
                  <div className="text-sm text-gray-400">
                    {(exec.test_type || 'load').toUpperCase()} — {exec.client || 'N/A'} — {new Date(exec.start_time || exec.created_at).toLocaleDateString()}
                  </div>
                </div>
                <div className="flex gap-1">
                  <button onClick={() => addSection(exec, typeMap[exec.test_type] || 'load_test')}
                    className="px-2 py-1 text-sm bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 flex items-center gap-1 transition-colors">
                    <Plus className="w-3 h-3" /> Reporte
                  </button>
                  {(attCounts[exec.id]?.monitoring || 0) > 0 && (
                    <button onClick={() => addSection(exec, 'monitoring')}
                      className="px-2 py-1 text-sm bg-green-50 text-green-700 rounded-lg hover:bg-green-100 flex items-center gap-1 transition-colors">
                      <Plus className="w-3 h-3" /> Monitor ({attCounts[exec.id].monitoring})
                    </button>
                  )}
                  {(attCounts[exec.id]?.evidence || 0) > 0 && (
                    <button onClick={() => addSection(exec, 'evidence')}
                      className="px-2 py-1 text-sm bg-yellow-50 text-yellow-700 rounded-lg hover:bg-yellow-100 flex items-center gap-1 transition-colors">
                      <Plus className="w-3 h-3" /> Evidencia ({attCounts[exec.id].evidence})
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Selected sections with DnD */}
        <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-200">
          <h2 className="text-2xl font-bold text-gray-800 mb-2">Secciones del Informe ({sections.length})</h2>
          <p className="text-sm text-gray-400 mb-4">Arrastre para reordenar. El informe se genera en este orden.</p>

          {sections.length === 0 ? (
            <div className="text-lg text-gray-400 text-center py-16 border-2 border-dashed border-gray-300 rounded-xl">
              Seleccione items del historial para agregarlos
            </div>
          ) : (
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
              <SortableContext items={sections.map(s => s.id)} strategy={verticalListSortingStrategy}>
                <div className="space-y-2">
                  {sections.map(s => (
                    <SortableItem key={s.id} section={s} onRemove={() => setSections(prev => prev.filter(x => x.id !== s.id))} />
                  ))}
                </div>
              </SortableContext>
            </DndContext>
          )}

          {sections.length > 0 && (
            <div className="mt-6 flex flex-col items-center gap-3">
              <button onClick={handleGenerate} disabled={generating}
                className="px-8 py-3 bg-[#f5a623] text-[#0a1628] rounded-xl font-bold text-lg hover:bg-[#f5a623]/90 disabled:opacity-50 transition-colors">
                {generating ? 'Generando...' : 'Generar Informe Integrado'}
              </button>
              {/* F1: error de creacion del registro — visible, no solo en consola */}
              {generateError && (
                <p className="text-red-600 text-base text-center max-w-xl">{generateError}</p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Generated report — full content */}
      {reportHtml && (
        <div className="mt-8 space-y-6">
          {/* Title */}
          <div className="text-center border-b-2 border-[#f5a623] pb-4">
            <h1 className="text-3xl font-bold text-[#0a1628]">Informe Integrado de Performance</h1>
            <p className="text-sm text-gray-500 mt-1">Generado: {new Date().toLocaleString('es-CO')}</p>
          </div>

          {/* Full report per execution — each section renders once, no duplicates */}
          {sectionsTree}

          {/* HF9: Consolidated Analysis — dual Load/Stress support */}
          <ConsolidatedAnalysisSection
            consolidatedAnalysis={consolidatedAnalysis}
            sections={[
              ...sections.map(s => ({ type: s.type, source_id: s.sourceId, source_name: s.sourceName })),
              ...(persistedId ? [{ type: '__meta', source_id: persistedId, source_name: reportName || '' }] : []),
            ]}
            onGenerated={(rawData) => {
              // F3: el consolidado nuevo sustituye al anterior en la DB. Hay que
              // descartar el debounce en vuelo y las ediciones pendientes, o al
              // dispararse pisarian el texto recien regenerado con el viejo.
              if (saveTimerRef.current) { clearTimeout(saveTimerRef.current); saveTimerRef.current = null; }
              pendingEditsRef.current = {};
              dirtyRef.current = false;
              // HF9.1: Extract embedded __report_id and __report_name from response
              const rid = (rawData as any).__report_id;
              const rname = (rawData as any).__report_name;
              const cleanData = { ...rawData };
              delete (cleanData as any).__report_id;
              delete (cleanData as any).__report_name;

              setConsolidatedAnalysis(cleanData);
              if (rid && !persistedId) {
                setPersistedId(rid);
                if (rname) setReportName(rname);
                navigate(`/performance/integrated/${rid}`, { replace: true });
              } else if (rid && persistedId) {
                // Regeneration — just update analysis, keep same ID
              }
              // Flatten for exports
              const allText = Object.entries(cleanData)
                .filter(([k]) => !k.startsWith('_'))
                .map(([tt, d]) => {
                  const label = tt === 'load' ? 'PRUEBA DE CARGA' : 'PRUEBA DE ESTRES';
                  return `${label}\n\nConclusiones:\n${d.conclusions}\n\nRecomendaciones:\n${d.recommendations}`;
                }).join('\n\n---\n\n');
              setConclusions(allText);
            }}
            // F3: cada tecla solo rearma el debounce (refs, sin re-render)
            onDraftChange={handleDraftChange}
            onEdit={(testType, field, value) => {
              // F3: el blur sigue siendo un guardado inmediato. El payload se
              // arma sobre las ediciones pendientes, asi un blur en una caja no
              // pisa lo que el autosave ya guardo de la otra.
              const pend = pendingEditsRef.current;
              pend[testType] = { ...(pend[testType] || {}), [field]: value };
              dirtyRef.current = true;
              setConsolidatedAnalysis(buildMergedConsolidated());
              saveNow();
            }}
          />

          {/* Export buttons */}
          <div className="flex gap-4 justify-center">
            <button onClick={handleExportHTML}
              className="px-8 py-3 bg-[#f5a623] text-[#0a1628] rounded-xl font-bold text-lg hover:bg-[#f5a623]/90 transition-colors">
              Exportar HTML
            </button>
            <button onClick={handleExportPDF}
              className="px-8 py-3 bg-red-600 text-white rounded-xl font-bold text-lg hover:bg-red-700 flex items-center gap-2 transition-colors">
              <FileDown className="w-5 h-5" /> Exportar PDF
            </button>
          </div>

          {/* F3: barra fija de guardado — visible con cualquier scroll */}
          <div className="fixed bottom-6 right-6 z-40 flex items-center gap-3 bg-white/95 backdrop-blur border border-gray-200 shadow-xl rounded-2xl px-4 py-3">
            <span className={`text-sm font-medium ${
              saveState === 'error' ? 'text-red-600'
              : saveState === 'saving' ? 'text-gray-500'
              : saveState === 'saved' ? 'text-emerald-700'
              : 'text-gray-400'}`}>
              {!persistedId ? 'Sin registro — genere el informe'
                : saveState === 'saving' ? 'Guardando...'
                : saveState === 'saved' ? `Guardado ${savedAt}`
                : saveState === 'error' ? 'Error al guardar'
                : 'Autoguardado activo'}
            </span>
            <button
              onClick={() => saveNow(true)}
              disabled={!persistedId || saveState === 'saving'}
              className={`px-5 py-2 rounded-xl font-bold text-white transition-colors disabled:opacity-50 ${
                saveState === 'error' ? 'bg-red-600 hover:bg-red-700' : 'bg-emerald-700 hover:bg-emerald-800'}`}>
              {saveState === 'error' ? 'Reintentar' : 'Guardar cambios'}
            </button>
          </div>

          {/* HF9.2: Footer SQA — LAST element of the report */}
          <div className="text-center text-gray-500 text-xl py-8 mt-8 border-t border-gray-200">
            <p className="font-semibold text-2xl">sqa<span className="text-[#f5a623]">_</span> Software Quality Assurance</p>
            <p className="text-lg mt-2 italic">Del pasado aprendimos, En el presente construimos, Para el futuro nos preparamos</p>
          </div>
        </div>
      )}
    </div>
  );
}
