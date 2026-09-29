/**
 * IntegratedReportPage — Drag-and-drop report builder.
 * Select executions, monitoring, evidence from history.
 * Reorder sections via drag. Generate unified report with AI conclusions.
 */
import { useState, useEffect, useLayoutEffect, useCallback, useRef, useMemo } from 'react';
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
import SelectorContenidoSeccion from '../components/integrated/SelectorContenidoSeccion';

// ─── Types ────────────────────────────────────────────────────────────────────
// R1 (R-D5/R-D6): que entra de la seccion. `tx` en carga/estres, `adjuntos` en
// monitoreo/evidencias. null/ausente = todo (lo de siempre). Se guarda con el
// informe, dentro de su entrada de `sections`.
type Seleccion = { tx?: string[] | null; adjuntos?: string[] | null };

interface ReportSection {
  id: string;
  type: 'load_test' | 'stress_test' | 'monitoring' | 'evidence';
  sourceId: string;
  sourceName: string;
  sourceDate: string;
  seleccion?: Seleccion;
}

/** R1: una seccion tal como la reciben los endpoints. Una sola definicion para
 *  generar, exportar, guardar y el consolidado: si cada uno armara la suya, la
 *  seleccion se caeria por el camino en el que alguien se olvidara de ella. */
const seccionApi = (s: ReportSection, idx: number) => ({
  order: idx, type: s.type, source_id: s.sourceId, source_name: s.sourceName, seleccion: s.seleccion || {},
});

// F3: retardo del autosave tras la ultima tecla.
const SAVE_DEBOUNCE_MS = 1800;

type SaveState = 'idle' | 'pending' | 'saving' | 'saved' | 'error';

// R1 (R-D3): lo que se envia al salir se guarda antes en el navegador y se
// borra cuando el servidor confirma. Si al volver sigue ahi y la base no tiene
// esos textos, la pagina lo dice y ofrece recuperarlo.
type CopiaLocal = { sections?: any[]; consolidated_analysis?: Record<string, any>; ts: number };
const claveCopia = (id: string) => `kx_integrado_pendiente_${id}`;
function leerCopia(id: string): CopiaLocal | null {
  try { const t = localStorage.getItem(claveCopia(id)); return t ? JSON.parse(t) : null; } catch { return null; }
}
function escribirCopia(id: string, payload: Record<string, any>) {
  try { localStorage.setItem(claveCopia(id), JSON.stringify({ ...payload, ts: Date.now() })); } catch { /* sin almacenamiento: queda el envio */ }
}
function borrarCopia(id: string) {
  try { localStorage.removeItem(claveCopia(id)); } catch { /* idem */ }
}
/** La copia ya esta en la base si cada texto que lleva coincide con el guardado. */
function copiaYaGuardada(copia: CopiaLocal, server: any): boolean {
  const ovServer: Record<string, any> = {};
  (server.sections || []).forEach((s: any) => { if (s?.overrides) ovServer[s.source_id] = s.overrides; });
  for (const s of copia.sections || []) {
    const ov = s?.overrides;
    if (!ov) continue;
    for (const tipo of ['analysis', 'images'] as const) {
      for (const [k, v] of Object.entries(ov[tipo] || {})) {
        if ((ovServer[s.source_id]?.[tipo] || {})[k] !== v) return false;
      }
    }
  }
  const cs = server.consolidated_analysis || {};
  for (const [tt, d] of Object.entries(copia.consolidated_analysis || {})) {
    for (const campo of ['conclusions', 'recommendations']) {
      if ((d as any)?.[campo] !== undefined && cs[tt]?.[campo] !== (d as any)[campo]) return false;
    }
  }
  return true;
}

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
function SortableItem({ section, onRemove, onSeleccion }: {
  section: ReportSection; onRemove: () => void; onSeleccion: (s: Seleccion) => void;
}) {
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
        {/* R1 (R-D5): que entra de esta seccion */}
        <SelectorContenidoSeccion
          executionId={section.sourceId}
          tipo={section.type}
          seleccion={section.type === 'monitoring' || section.type === 'evidence' ? section.seleccion?.adjuntos : section.seleccion?.tx}
          onCambiar={(nueva) => onSeleccion(section.type === 'monitoring' || section.type === 'evidence'
            ? { adjuntos: nueva } : { tx: nueva })}
        />
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

  // R1 (R-D1): el indicador no miente. 'pending' = hay cambios que el servidor
  // todavia no tiene; 'saved' solo se pone cuando el PATCH respondio 200.
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [savedAt, setSavedAt] = useState('');
  const [saveError, setSaveError] = useState('');   // R-D3: el aviso visible
  // R1: copia local de una visita anterior que no llego al servidor (ver `enviarAlSalir`)
  const [recuperable, setRecuperable] = useState<CopiaLocal | null>(null);

  // F3: todo lo que cambia por tecla vive en refs — nunca provoca re-render
  const saveTimerRef = useRef<number | null>(null);
  const pendingEditsRef = useRef<Record<string, Record<string, string>>>({});
  // R1: contador de ediciones en vez de un si/no. Cada edicion suma uno; un
  // guardado solo da por guardado lo que llevaba al salir. Asi, una edicion que
  // llega mientras un PATCH esta en vuelo no queda marcada como guardada.
  const editSeqRef = useRef(0);
  const savedSeqRef = useRef(0);
  const saveStateRef = useRef<SaveState>('idle');
  const hayPendiente = () => editSeqRef.current !== savedSeqRef.current;
  const setEstado = (s: SaveState) => { saveStateRef.current = s; setSaveState(s); };
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
  // F2 (aviso de respaldo): antes de exportar, si alguna ejecucion del integrado
  // tiene secciones que no escribio la IA, se dice y se pide «igualmente». Sale
  // de `ai_origen`, que ya viene en la lista de /executions: ninguna peticion mas.
  const [confirmarExport, setConfirmarExport] = useState<'pdf' | 'html' | null>(null);

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
      const base: Record<string, any> = seccionApi(s, idx);
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

  // HF9.1 / F3: Persist edits to DB — ahora con indicador de estado.
  // R1: `seq` es la ultima edicion que lleva este PATCH; `null` = no lleva
  // ediciones (renombrar) y no cambia lo pendiente.
  const persistEdit = useCallback(async (updates: Record<string, any>, seq: number | null) => {
    const id = persistedIdRef.current;
    if (!id) return false;
    setEstado('saving');
    try {
      const res = await fetch(`${apiBase}/reports/integrated-reports/${id}`, {
        method: 'PATCH', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
        body: JSON.stringify(updates),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      if (seq !== null) savedSeqRef.current = Math.max(savedSeqRef.current, seq);
      setSaveError('');
      if (hayPendiente()) {
        // Llego otra edicion mientras este PATCH viajaba: sigue sin guardar.
        setEstado('pending');
      } else {
        borrarCopia(id);
        setEstado('saved');
        setSavedAt(new Date().toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' }));
      }
      return true;
    } catch (e) {
      console.error('Error persisting edit:', e);
      setEstado('error');
      setSaveError('No se pudieron guardar los cambios. Siguen en esta página: pulse «Reintentar» antes de salir.');
      return false;
    }
  }, [apiBase]);

  // R1: lo que se manda al servidor, en un solo sitio: el guardado normal y el
  // envio al salir no pueden armar payloads distintos.
  const buildSavePayload = useCallback((includeName = false) => {
    const payload: Record<string, any> = { consolidated_analysis: buildMergedConsolidated() };
    // Guarda: nunca mandar una lista vacia — borraria las secciones guardadas.
    const secs = buildSectionsPayload();
    if (secs.length) payload.sections = secs;
    if (includeName) payload.name = reportNameRef.current;
    return payload;
  }, [buildMergedConsolidated, buildSectionsPayload]);

  // F3 + F4: guardado efectivo — consolidado Y overrides de seccion en el mismo
  // PATCH (cancela cualquier debounce en vuelo)
  const saveNow = useCallback(async (includeName = false) => {
    if (saveTimerRef.current) { clearTimeout(saveTimerRef.current); saveTimerRef.current = null; }
    const seq = editSeqRef.current;
    const payload = buildSavePayload(includeName);
    const ok = await persistEdit(payload, seq);
    // El texto plano de los exports se sincroniza con lo que quedo guardado.
    if (ok) setConclusions(flattenConsolidated(payload.consolidated_analysis));
    return ok;
  }, [buildSavePayload, persistEdit]);

  // R1 (R-D1): una edicion. Solo cambia el estado al pasar a 'pending', no por
  // tecla: el arbol de secciones esta memoizado y no se repinta.
  const marcarEdicion = useCallback(() => {
    editSeqRef.current += 1;
    if (saveStateRef.current !== 'pending' && saveStateRef.current !== 'saving') setEstado('pending');
  }, []);

  // F3 + F4: rearma el debounce. Lo comparten el consolidado y las secciones.
  const scheduleSave = useCallback(() => {
    marcarEdicion();
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = window.setTimeout(() => {
      saveTimerRef.current = null;
      if (hayPendiente()) saveNow();
    }, SAVE_DEBOUNCE_MS);
  }, [marcarEdicion, saveNow]);

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

  // R1 (R-D5/R-D6): la seleccion es parte del informe y se guarda con el, por el
  // mismo camino que una edicion (y con el mismo indicador).
  const cambiarSeleccion = useCallback((id: string, sel: Seleccion) => {
    setSections(prev => prev.map(x => (x.id === id ? { ...x, seleccion: { ...(x.seleccion || {}), ...sel } } : x)));
    if (persistedIdRef.current) scheduleSave();
  }, [scheduleSave]);

  // F3: vacia el debounce pendiente antes de acciones que leen lo guardado
  const flushPending = useCallback(async () => {
    if (saveTimerRef.current) { clearTimeout(saveTimerRef.current); saveTimerRef.current = null; }
    if (hayPendiente()) await saveNow();
  }, [saveNow]);

  // R1 (R-D2): salir ENVIA lo pendiente en vez de cancelarlo. Vale para salir
  // por el menu (desmontaje), recargar y cerrar la pestaña (beforeunload).
  //  1. Se quita el foco de la caja activa: su onBlur vuelca el texto al ref por
  //     el camino de siempre. Sin esto, escribir y pulsar F5 perdia la caja.
  //  2. Se guarda una copia local ANTES de enviar (R-D3): si el envio no llega,
  //     la pagina lo recupera al volver.
  //  3. `keepalive` para que el navegador termine el envio aunque la pagina se
  //     cierre. Tiene un tope de 64 KB; por encima se envia sin el (sale igual
  //     al navegar por el menu, y si se cierra la pestaña queda la copia).
  const enviarAlSalir = useCallback(() => {
    const activo = document.activeElement as HTMLElement | null;
    if (activo && typeof activo.blur === 'function') activo.blur();
    const id = persistedIdRef.current;
    if (!id || !hayPendiente()) return;
    if (saveTimerRef.current) { clearTimeout(saveTimerRef.current); saveTimerRef.current = null; }
    const body = JSON.stringify(buildSavePayload());
    escribirCopia(id, JSON.parse(body));
    fetch(`${apiBase}/reports/integrated-reports/${id}`, {
      method: 'PATCH', credentials: 'include', keepalive: body.length < 60000,
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
      body,
    }).then((r) => { if (r.ok) borrarCopia(id); }).catch(() => {});
  }, [apiBase, buildSavePayload]);

  // R1 (R-D3): aplica la copia local encima de lo guardado, la guarda y recarga
  // para que cada caja se pinte con el texto recuperado.
  const recuperarCopia = useCallback(async () => {
    const copia = recuperable;
    if (!copia) return;
    (copia.sections || []).forEach((s: any) => {
      const ov = s?.overrides;
      if (!ov) return;
      const dst = touchSection(s.source_id);
      Object.assign(dst.analysis, ov.analysis || {});
      Object.assign(dst.images, ov.images || {});
    });
    Object.entries(copia.consolidated_analysis || {}).forEach(([tt, d]: [string, any]) => {
      if (d && typeof d === 'object') {
        pendingEditsRef.current[tt] = { conclusions: d.conclusions ?? '', recommendations: d.recommendations ?? '' };
      }
    });
    marcarEdicion();
    if (await saveNow()) window.location.reload();
  }, [recuperable, touchSection, marcarEdicion, saveNow]);

  const enviarAlSalirRef = useRef(enviarAlSalir);
  enviarAlSalirRef.current = enviarAlSalir;

  useEffect(() => {
    const onBeforeUnload = () => enviarAlSalirRef.current();
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, []);

  // Salir por el menu desmonta la pagina. Es un efecto de LAYOUT a proposito:
  // su limpieza corre antes de que React quite el DOM, asi que la caja con el
  // foco todavia existe y su onBlur llega a volcar el texto.
  useLayoutEffect(() => () => enviarAlSalirRef.current(), []);

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
            seleccion: s.seleccion || undefined,   // R1 (R-D6)
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
          // R1 (R-D3): ¿quedo algo de la visita anterior sin llegar al servidor?
          const copia = leerCopia(data.id);
          if (copia) {
            if (copiaYaGuardada(copia, data)) borrarCopia(data.id);
            else setRecuperable(copia);
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
          sections: sections.map(seccionApi),
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

  const ejecucionesSinIA = sections
    .filter((s) => s.type === 'load_test' || s.type === 'stress_test')
    .map((s) => ({ nombre: s.sourceName, o: executions.find((e: any) => String(e.id) === s.sourceId)?.ai_origen }))
    .filter((x) => (x.o?.afectadas || 0) > 0);

  const pedirExport = (formato: 'pdf' | 'html') => {
    if (ejecucionesSinIA.length > 0) { setConfirmarExport(formato); return; }
    if (formato === 'pdf') handleExportPDF(); else handleExportHTML();
  };

  const handleExportPDF = async () => {
    await flushPending();  // F3: no exportar con ediciones sin guardar
    try {
      const res = await fetch(`${apiBase}/reports/integrated/export-pdf`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
        body: JSON.stringify({
          sections: sections.map(seccionApi),
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
          sections: sections.map(seccionApi),
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
          soloAdjuntos={s.seleccion?.adjuntos}
        />
      );
    }
    // R1 (opcion (a) de Fredy): una seccion de carga/estres ya NO pinta dentro su
    // monitoreo ni sus evidencias. Entran solo como seccion propia, igual que en el
    // PDF y el HTML, que nunca las incluyeron ahi: la pantalla y el exportado
    // decian cosas distintas.
    return (
      <div key={s.id}>
        {idx > 0 && <hr className="my-6 border-2 border-[#0a1628]" />}
        <DashboardEmbed executionId={s.sourceId} onAnalysisEdit={handleSectionAnalysisEdit}
          analysisOverrides={sectionOverrides[s.sourceId]?.analysis}
          soloTransacciones={s.seleccion?.tx} />
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

      {/* R1 (R-D3): lo que se envio al salir y no consta en la base */}
      {recuperable && (
        <div role="alert" data-testid="aviso-recuperar"
          className="mb-6 flex flex-wrap items-center gap-4 bg-amber-50 border-2 border-amber-300 text-amber-900 rounded-2xl px-5 py-4">
          <span className="flex-1 text-base font-medium">
            Hay cambios de su última visita ({new Date(recuperable.ts).toLocaleString('es-CO')}) que no llegaron a guardarse.
          </span>
          <button onClick={recuperarCopia}
            className="px-4 py-2 bg-amber-600 text-white font-bold rounded-xl hover:bg-amber-700">Recuperar y guardar</button>
          <button onClick={() => { if (persistedId) borrarCopia(persistedId); setRecuperable(null); }}
            className="px-4 py-2 text-amber-800 font-semibold rounded-xl hover:bg-amber-100">Descartar</button>
        </div>
      )}

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
                  await persistEdit({ name: newName }, null);
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
                    <SortableItem key={s.id} section={s} onRemove={() => setSections(prev => prev.filter(x => x.id !== s.id))}
                      onSeleccion={(sel) => cambiarSeleccion(s.id, sel)} />
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
              ...sections.map(s => ({ type: s.type, source_id: s.sourceId, source_name: s.sourceName, seleccion: s.seleccion || {} })),
              ...(persistedId ? [{ type: '__meta', source_id: persistedId, source_name: reportName || '' }] : []),
            ]}
            onGenerated={(rawData) => {
              // F3: el consolidado nuevo sustituye al anterior en la DB. Hay que
              // descartar el debounce en vuelo y las ediciones pendientes, o al
              // dispararse pisarian el texto recien regenerado con el viejo.
              if (saveTimerRef.current) { clearTimeout(saveTimerRef.current); saveTimerRef.current = null; }
              pendingEditsRef.current = {};
              // HF9.1: Extract embedded __report_id and __report_name from response
              const rid = (rawData as any).__report_id;
              const rname = (rawData as any).__report_name;
              const cleanData = { ...rawData };
              delete (cleanData as any).__report_id;
              delete (cleanData as any).__report_name;

              setConsolidatedAnalysis(cleanData);
              // R1: el consolidado nuevo ya esta en la base. Si quedan ediciones
              // de SECCION sin guardar, se envian ya, con el consolidado nuevo (el
              // ref se pone a mano: el efecto espejo aun no ha corrido y mandaria
              // el viejo). Antes se daban por guardadas sin estarlo.
              consolidatedRef.current = cleanData;
              if (hayPendiente()) saveNow();
              else setEstado('saved');
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
              marcarEdicion();
              setConsolidatedAnalysis(buildMergedConsolidated());
              saveNow();
            }}
          />

          {/* Export buttons */}
          <div className="flex gap-4 justify-center">
            <button onClick={() => pedirExport('html')}
              className="px-8 py-3 bg-[#f5a623] text-[#0a1628] rounded-xl font-bold text-lg hover:bg-[#f5a623]/90 transition-colors">
              Exportar HTML
            </button>
            <button onClick={() => pedirExport('pdf')}
              className="px-8 py-3 bg-red-600 text-white rounded-xl font-bold text-lg hover:bg-red-700 flex items-center gap-2 transition-colors">
              <FileDown className="w-5 h-5" /> Exportar PDF
            </button>
          </div>

          {/* F2: exportar con secciones que no escribio la IA pide confirmacion */}
          {confirmarExport && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" data-testid="confirmar-export-integrado">
              <div className="w-full max-w-xl rounded-2xl border-2 border-red-400 bg-white p-6 shadow-2xl" role="alertdialog">
                <p className="text-2xl font-bold text-red-900">Este integrado lleva secciones que no escribió la IA</p>
                <ul className="mt-3 space-y-1 text-base text-red-900">
                  {ejecucionesSinIA.map((x) => (
                    <li key={x.nombre}>
                      <span className="font-semibold">{x.nombre}</span>: {x.o.afectadas} de {x.o.total} · {x.o.motivo_frase || 'motivo desconocido'}
                    </li>
                  ))}
                </ul>
                <p className="mt-3 text-base text-red-900">
                  El documento no lo dice en la página: quien lo reciba no lo sabrá. Lo recomendable es
                  regenerar esas ejecuciones con IA antes de enviarlo.
                </p>
                <div className="mt-5 flex justify-end gap-3 border-t border-gray-200 pt-4">
                  <button onClick={() => setConfirmarExport(null)} data-testid="export-integrado-cancelar"
                    className="rounded-xl border border-gray-300 px-6 py-3 text-lg font-semibold text-gray-600 hover:bg-gray-50">
                    Cancelar
                  </button>
                  <button data-testid="export-integrado-igualmente"
                    onClick={() => { const f = confirmarExport; setConfirmarExport(null); if (f === 'pdf') handleExportPDF(); else handleExportHTML(); }}
                    className="rounded-xl border-2 border-red-500 bg-white px-6 py-3 text-lg font-bold text-red-700 hover:bg-red-50">
                    Exportar {confirmarExport === 'pdf' ? 'PDF' : 'HTML'} igualmente
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* F3: barra fija de guardado — visible con cualquier scroll.
              R1 (R-D1/R-D3/R-D4): dice «Guardado» solo con la confirmacion del
              servidor; con cambios pendientes lo dice con esas palabras, y un
              fallo sale como mensaje, no solo como color. */}
          <div className="fixed bottom-6 right-6 z-40 flex flex-col items-end gap-2" data-testid="barra-guardado">
            {saveError && (
              <div role="alert" data-testid="aviso-guardado"
                className="max-w-md bg-red-50 border-2 border-red-300 text-red-800 text-sm font-medium rounded-xl px-4 py-3 shadow-xl">
                {saveError}
              </div>
            )}
            <div className="flex items-center gap-3 bg-white/95 backdrop-blur border border-gray-200 shadow-xl rounded-2xl px-4 py-3">
              <span data-testid="estado-guardado" className={`text-sm font-medium ${
                saveState === 'error' ? 'text-red-600'
                : saveState === 'pending' ? 'text-amber-700'
                : saveState === 'saving' ? 'text-gray-500'
                : saveState === 'saved' ? 'text-emerald-700'
                : 'text-gray-400'}`}>
                {!persistedId ? 'Sin registro — genere el informe'
                  : saveState === 'pending' ? 'Cambios sin guardar'
                  : saveState === 'saving' ? 'Guardando...'
                  : saveState === 'saved' ? `Guardado ${savedAt}`
                  : saveState === 'error' ? 'No se guardó'
                  : 'Sin cambios pendientes'}
              </span>
              <button
                onClick={() => saveNow(true)}
                disabled={!persistedId || saveState === 'saving'}
                className={`px-5 py-2 rounded-xl font-bold text-white transition-colors disabled:opacity-50 ${
                  saveState === 'error' ? 'bg-red-600 hover:bg-red-700'
                  : saveState === 'pending' ? 'bg-amber-600 hover:bg-amber-700 ring-4 ring-amber-200'
                  : 'bg-emerald-700 hover:bg-emerald-800'}`}>
                {saveState === 'error' ? 'Reintentar' : 'Guardar cambios'}
              </button>
            </div>
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
