/**
 * Informe por transaccion: 5 graficas (N4.4) + 6 textos.
 *
 * ETAPA 2: eran 8 textos; conclusiones y recomendaciones por transaccion salieron
 * (D20, v1.2 §1.1). Los bloques se muestran ABIERTOS al abrir el informe y sus
 * datos se piden solos: antes era un acordeon con carga bajo demanda, y eso
 * contradecia "el mismo informe general, filtrado" de §1.
 *
 * Vive aparte de Dashboard.tsx (protegido), que solo lo monta. Todo el estado
 * —series, textos, generacion, sondeo y autoguardado— es de este componente.
 *
 * Regla 16: TODOS los hooks se declaran antes de cualquier return.
 */
import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Sparkles, AlertTriangle, Loader2 } from 'lucide-react';
import api from '../../services/api';
import { MAX_SUFFIX, CHART_LAYOUT } from '../../config/chartConfig';
import ReportBody, { ReportBodyCtx } from './ReportBody';
import SummaryTable, { SummaryRow } from './SummaryTable';

// ETAPA 2 (D20): SEIS secciones, no ocho. Las conclusiones y recomendaciones por
// transaccion se retiraron (v1.2 §1.1): van una sola vez al final del informe.
// Esta lista duplicaba la del backend (SECTIONS_GENERADAS); se mantiene el duplicado
// porque el frontend no importa constantes del backend, pero ahora coinciden.
const SECTIONS = ['summary', 'chart_response_times', 'chart_latency', 'chart_error_rate',
  'chart_codes', 'chart_tps'] as const;

const TITULOS: Record<string, string> = {
  summary: 'Resumen de la transacción',
  chart_response_times: 'Análisis — Tiempos de respuesta',
  chart_latency: 'Análisis — Latencia',
  chart_error_rate: 'Análisis — Tasa de error',
  chart_codes: 'Análisis — Códigos de respuesta',
  chart_tps: 'Análisis — Transacciones por segundo',
  conclusions: 'Conclusiones de la transacción',
  recommendations: 'Recomendaciones de la transacción',
};

// ETAPA 2 (D21 · C2): el campo que ReportBody usa para cada caja de analisis, y la
// seccion de transaction_chart_analyses donde se guarda ese mismo texto cuando el
// alcance es una transaccion. Este mapa ES el cableado: con el, editar dentro del
// bloque de una transaccion escribe en su canal y no en el del informe general.
const SECCION_DE_CAMPO: Record<string, string> = {
  ai_analysis_response_times: 'chart_response_times',
  ai_analysis_latency: 'chart_latency',
  ai_analysis_error_rate: 'chart_error_rate',
  ai_analysis_codes_per_second: 'chart_codes',
  ai_analysis_transactions_per_second: 'chart_tps',
};

const AUTOSAVE_MS = 1800;   // mismo debounce que F3/R1/R2
const POLL_MS = 4000;
const MAX_FALLOS_SONDEO = 3;

type Seccion = { section: string; ai_analysis: string | null; is_edited: boolean; generated_at: string | null };
type Progreso = { done: number; total: number; persisted: number; pending: string[] };
type Estado = { series?: any; secciones: Seccion[]; progreso?: Progreso; error?: string };

// N4.10: avance de la generacion automatica. El backend lo deriva de las filas
// ya guardadas, no de memoria de proceso (en produccion son --workers 2).
type EstadoAuto = {
  label: string;
  state: 'pendiente' | 'generando' | 'completo' | 'parcial';
  done: number; total: number; failed_sections: string[];
};
type Auto = { status: 'idle' | 'in_progress' | 'completed'; labels: EstadoAuto[];
              done_labels: number; total_labels: number; requested: string[] };

const hora = (iso: string | null) => (iso ? new Date(iso + 'Z').toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' }) : '');

const hhmmss = (iso: string) => String(iso).slice(11, 19);

/** Traduce las 5 series de /transaction-charts a las estructuras que ReportBody
 *  espera. No dibuja nada: solo adapta la forma del dato.
 *
 *  ETAPA 2 (D21): aqui muere la plantilla paralela. Antes este archivo tenia su
 *  propia grafica (GraficaTx, 260 px, ejes y tooltip propios) y por eso el informe
 *  por transaccion no se parecia al general. Ahora pinta el MISMO componente, que
 *  es lo que hace cierta por construccion la frase de v1.2 §1: "el informe por
 *  transaccion es el informe general con el mismo diseño, filtrado". */
function seriesParaReportBody(label: string, series: any) {
  const rt: any[] = series?.response_times || [];
  const hayMax = rt.some((p: any) => p.value_max != null);
  const simple = (arr: any[] | undefined) =>
    (arr || []).map((p: any) => ({ displayTime: hhmmss(p.timestamp), value: p.value }));

  // Los codigos llegan como filas (timestamp, code, value) y se pivotan a una
  // columna por codigo, igual que prepareMultiLineData hace en el general.
  const porTs = new Map<string, any>();
  const codigos: string[] = [];
  (series?.codes || []).forEach((p: any) => {
    const c = String(p.code);
    if (!codigos.includes(c)) codigos.push(c);
    if (!porTs.has(p.timestamp)) porTs.set(p.timestamp, { displayTime: hhmmss(p.timestamp) });
    porTs.get(p.timestamp)[c] = p.value;
  });

  return {
    responseTimesByLabel: {
      labels: [label],
      data: rt.map((p: any) => {
        const fila: any = { displayTime: hhmmss(p.timestamp), [label]: p.value };
        if (p.value_max != null) fila[`${label}${MAX_SUFFIX}`] = p.value_max;
        return fila;
      }),
    },
    rtMaxLabels: hayMax ? [label] : [],
    rtMaxKeys: hayMax ? [`${label}${MAX_SUFFIX}`] : [],
    latencyData: simple(series?.latency),
    errorRateData: simple(series?.error_rate),
    codesPerSecond: { labels: codigos, data: Array.from(porTs.values()) },
    tpsByLabel: {
      labels: [label],
      data: (series?.tps || []).map((p: any) => ({ displayTime: hhmmss(p.timestamp), [label]: p.value })),
    },
  };
}

/** Las graficas de UNA transaccion, pintadas por ReportBody.
 *
 *  Es un componente propio porque cada bloque necesita su estado (leyendas
 *  plegadas y zoom de eje Y) y los hooks no pueden vivir dentro de un .map.
 *  Regla 16: todos los hooks, antes de cualquier return. */
function BloqueGraficasTx({ label, series, secciones, guardarSeccion }: {
  label: string;
  series: any;
  secciones: Seccion[];
  guardarSeccion: (label: string, section: string, texto: string) => Promise<void>;
}) {
  const [hiddenRT, setHiddenRT] = useState<Set<string>>(new Set());
  const [hiddenTPS, setHiddenTPS] = useState<Set<string>>(new Set());
  const [hiddenCodes, setHiddenCodes] = useState<Set<string>>(new Set());
  const [rangos, setRangos] = useState<Record<string, { min: number | 'auto'; max: number | 'auto' }>>({});

  const handleYRange = useCallback((key: string, mn: number | 'auto', mx: number | 'auto') => {
    setRangos((p) => ({ ...p, [key]: { min: mn, max: mx } }));
  }, []);
  const getYDomain = useCallback((key: string): [number | string, number | string] => {
    const r = rangos[key];
    return r ? [r.min, r.max] : ['auto', 'auto'];
  }, [rangos]);
  const extractY = useCallback((data: any[], keys: string[]): number[] => {
    if (!data) return [];
    const vals: number[] = [];
    data.forEach((p) => keys.forEach((k) => { const v = p[k]; if (typeof v === 'number') vals.push(v); }));
    return vals;
  }, []);
  const handleLegendClick = useCallback((dataKey: string, ocultas: Set<string>,
    setOcultas: React.Dispatch<React.SetStateAction<Set<string>>>) => {
    const nuevo = new Set(ocultas);
    if (nuevo.has(dataKey)) nuevo.delete(dataKey); else nuevo.add(dataKey);
    setOcultas(nuevo);
  }, []);

  // Identidad estable (deps vacias): si cambiara en cada render, React
  // desmontaria el textarea y se perderia el foco al escribir.
  const AnalysisBox = useCallback(({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <div className="mt-4 bg-white rounded-xl p-5 border-l-4 border-orange-500 border border-gray-200">
      <div className="flex items-center justify-between mb-2">
        <h4 className="font-bold text-orange-600 text-xl">Análisis</h4>
        <span className="text-xs text-gray-400 italic">Click para editar</span>
      </div>
      <TextoEditable valor={value} editado={false} onGuardar={async (v) => onChange(v)} />
    </div>
  ), []);

  // C2: la edicion y el autoguardado de este alcance van al canal de la
  // transaccion. El setter de ReportBody se respeta en la firma pero no guarda
  // estado aqui: el texto vive en `secciones`, que se refresca al guardar.
  const emitEdit = useCallback((campo: string, setter: (v: string) => void) => (valor: string) => {
    setter(valor);
    const sec = SECCION_DE_CAMPO[campo];
    if (!sec) return;   // active_threads no existe por transaccion (D18)
    guardarSeccion(label, sec, valor);
  }, [label, guardarSeccion]);

  const datos = useMemo(() => seriesParaReportBody(label, series), [label, series]);
  const texto = (sec: string) => secciones.find((s) => s.section === sec)?.ai_analysis || '';
  const nada = () => {};

  const ctx: ReportBodyCtx = {
    ...datos,
    activeThreadsData: [],     // D18: solo en el alcance general
    analysisResponseTimes: texto('chart_response_times'), setAnalysisResponseTimes: nada,
    analysisLatency: texto('chart_latency'), setAnalysisLatency: nada,
    analysisErrorRate: texto('chart_error_rate'), setAnalysisErrorRate: nada,
    analysisCodesPerSecond: texto('chart_codes'), setAnalysisCodesPerSecond: nada,
    analysisTransactionsPerSecond: texto('chart_tps'), setAnalysisTransactionsPerSecond: nada,
    analysisActiveThreads: '', setAnalysisActiveThreads: nada,
    hiddenLinesResponseTimes: hiddenRT, setHiddenLinesResponseTimes: setHiddenRT,
    hiddenLinesTPS: hiddenTPS, setHiddenLinesTPS: setHiddenTPS,
    hiddenLinesCodes: hiddenCodes, setHiddenLinesCodes: setHiddenCodes,
    minH: Math.max(CHART_LAYOUT.minHeight, 700),   // el mismo alto que el general
    emitEdit, getYDomain, extractY, handleYRange, AnalysisBox, handleLegendClick,
  };

  return <ReportBody scope={{ kind: 'transaction', label }} ctx={ctx} />;
}

/** Texto editable con autoguardado (patron F3/R1/R2: debounce + indicador). */
function TextoEditable({ valor, editado, onGuardar }: { valor: string; editado: boolean; onGuardar: (v: string) => Promise<void> }) {
  const [local, setLocal] = useState(valor);
  const [estado, setEstado] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const timer = useRef<number | null>(null);
  const ultimo = useRef(valor);

  useEffect(() => { setLocal(valor); ultimo.current = valor; }, [valor]);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const guardar = useCallback(async (v: string) => {
    if (v === ultimo.current) return;
    setEstado('saving');
    try { await onGuardar(v); ultimo.current = v; setEstado('saved'); }
    catch { setEstado('error'); }
  }, [onGuardar]);

  return (
    <div>
      <textarea
        value={local}
        onChange={(e) => {
          const v = e.target.value;
          setLocal(v);
          if (timer.current) clearTimeout(timer.current);
          timer.current = window.setTimeout(() => { timer.current = null; guardar(v); }, AUTOSAVE_MS);
        }}
        onBlur={() => { if (timer.current) clearTimeout(timer.current); guardar(local); }}
        placeholder="Sin texto todavia. Genera el analisis o escribelo a mano."
        className="w-full p-4 border-2 border-gray-300 rounded-xl text-lg text-gray-800 focus:ring-2 focus:ring-indigo-400/50 focus:border-indigo-500 resize-y hover:border-indigo-300 transition-colors"
        style={{ minHeight: '150px' }}
      />
      <div className="flex items-center gap-3 mt-1 text-sm">
        <span className={estado === 'error' ? 'text-red-600' : estado === 'saving' ? 'text-gray-500' : estado === 'saved' ? 'text-emerald-700' : 'text-gray-400'}>
          {estado === 'saving' ? 'Guardando...' : estado === 'saved' ? 'Guardado' : estado === 'error' ? 'Error al guardar' : 'Autoguardado activo'}
        </span>
        {estado === 'error' && (
          <button onClick={() => guardar(local)} className="px-2 py-0.5 bg-red-600 text-white text-xs font-semibold rounded-lg hover:bg-red-700">Reintentar</button>
        )}
        {editado && estado !== 'saving' && <span className="text-xs text-indigo-600 font-medium">editado a mano</span>}
      </div>
    </div>
  );
}

export default function TransactionReportSection({ executionId, byLabel = [], durationSeconds = 0 }: {
  executionId: string;
  /** ETAPA 2 (D15): las filas de by_label que Dashboard ya pidio a /charts. Se pasan
   *  en vez de volver a pedir el endpoint entero (850 KB) solo para una fila. */
  byLabel?: SummaryRow[];
  durationSeconds?: number;
}) {
  const [labels, setLabels] = useState<string[]>([]);
  const [abierta, setAbierta] = useState<string | null>(null);
  const [datos, setDatos] = useState<Record<string, Estado>>({});
  const [generando, setGenerando] = useState<string | null>(null);
  const [cola, setCola] = useState<string[]>([]);
  const [segundos, setSegundos] = useState(0);
  const [avisoSondeo, setAvisoSondeo] = useState('');
  const [auto, setAuto] = useState<Auto | null>(null);     // N4.10
  const generandoRef = useRef<string | null>(null);

  // 1. Transacciones marcadas como criticas (N3.4). Sin ninguna, el bloque no existe.
  useEffect(() => {
    if (!executionId) return;
    api.get(`/executions/${executionId}/transaction-analyses`)
      .then((r) => {
        // Criticas marcadas en el upload + las que ya tienen mini-informe (N4.7):
        // una transaccion con textos generados debe verse aunque nadie la marcara.
        const criticas: string[] = (r.data?.transaction_analyses || []).map((t: any) => t.label);
        const conInforme: string[] = r.data?.report_labels || [];
        setLabels(Array.from(new Set([...criticas, ...conInforme])));
      })
      .catch(() => setLabels([]));
  }, [executionId]);

  const cargarRef = useRef<((l: string) => Promise<void>) | null>(null);

  // 1b. N4.10: la generacion automatica que lanzo el upload. Se sondea el estado
  // hasta que termina y entonces se recarga lo que quedo guardado, sin que el
  // usuario tenga que pulsar nada. Si no hay ninguna en curso, un solo GET y ya.
  useEffect(() => {
    if (!executionId) return;
    let vivo = true;
    let sonda = 0;
    const mirar = async () => {
      try {
        const r = await api.get(`/executions/${executionId}/transaction-reports/status`);
        if (!vivo) return;
        const est: Auto = r.data;
        setAuto(est);
        // Las marcadas entran en la lista aunque aun no tengan ni una fila.
        if (est.requested?.length) {
          setLabels((prev) => Array.from(new Set([...prev, ...est.requested])));
        }
        if (est.status !== 'in_progress') {
          window.clearInterval(sonda);
          // Al cerrarse, se recarga lo que este abierto para ver el texto nuevo.
          if (est.done_labels > 0 && abierta) cargarRef.current?.(abierta);
        }
      } catch {
        // El estado es informativo: si falla, la pantalla sigue usable con el
        // boton manual. No se deja un spinner eterno.
        if (vivo) { window.clearInterval(sonda); setAuto(null); }
      }
    };
    mirar();
    sonda = window.setInterval(mirar, POLL_MS);
    return () => { vivo = false; window.clearInterval(sonda); };
  }, [executionId, abierta]);

  // 2. Carga de una transaccion: series + textos ya guardados.
  const cargar = useCallback(async (label: string) => {
    const enc = encodeURIComponent(label);
    const [ser, rep] = await Promise.allSettled([
      api.get(`/executions/${executionId}/transaction-charts?label=${enc}`),
      api.get(`/executions/${executionId}/transaction-report?label=${enc}`),
    ]);
    setDatos((d) => ({
      ...d,
      [label]: {
        series: ser.status === 'fulfilled' ? ser.value.data : d[label]?.series,
        secciones: rep.status === 'fulfilled' ? rep.value.data.sections : (d[label]?.secciones || []),
        progreso: rep.status === 'fulfilled' ? rep.value.data.progress : d[label]?.progreso,
        error: ser.status === 'rejected' ? 'No se pudieron calcular las graficas de esta transaccion (el JTL original puede haberse borrado).' : undefined,
      },
    }));
  }, [executionId]);

  useEffect(() => { cargarRef.current = cargar; }, [cargar]);

  // ETAPA 2: los bloques salen ABIERTOS, asi que sus datos se piden solos al abrir
  // el informe, no al desplegar. Antes esto cargaba unicamente la transaccion que
  // el usuario abria, y por eso la pagina no pintaba ninguna grafica por
  // transaccion hasta que alguien pulsaba.
  //
  // EN SERIE, una transaccion tras otra. Cada peticion parsea el JTL entero en el
  // servidor; lanzarlas a la vez multiplicaba ese trabajo por el numero de
  // transacciones y dejaba al backend sin atender nada mas. El Set de intentados
  // se marca ANTES del await, que es lo que impide que un re-render dispare la
  // misma carga dos veces.
  const intentadosRef = useRef<Set<string>>(new Set());
  useEffect(() => { intentadosRef.current = new Set(); }, [executionId]);
  useEffect(() => {
    if (!labels.length) return;
    let vivo = true;
    (async () => {
      for (const l of labels) {
        if (!vivo) return;
        if (intentadosRef.current.has(l)) continue;
        intentadosRef.current.add(l);
        await cargar(l);
      }
    })();
    return () => { vivo = false; };
  }, [labels, cargar]);

  // 3. Sondeo del progreso mientras se genera. Si el GET falla varias veces
  // seguidas se avisa y se deja de sondear: el usuario ve las secciones reales
  // ya guardadas, nunca un spinner eterno.
  useEffect(() => {
    if (!generando) return;
    setSegundos(0);
    setAvisoSondeo('');
    let fallos = 0;
    const label = generando;
    const reloj = window.setInterval(() => setSegundos((s) => s + 1), 1000);
    const sonda = window.setInterval(async () => {
      try {
        const r = await api.get(`/executions/${executionId}/transaction-report?label=${encodeURIComponent(label)}`);
        fallos = 0;
        setDatos((d) => ({ ...d, [label]: { ...(d[label] || { secciones: [] }), secciones: r.data.sections, progreso: r.data.progress } }));
      } catch {
        fallos += 1;
        if (fallos >= MAX_FALLOS_SONDEO) {
          setAvisoSondeo('No se pudo consultar el progreso. Lo que se ve abajo es lo ultimo que quedo guardado; la generacion puede seguir en el servidor.');
          clearInterval(sonda);
        }
      }
    }, POLL_MS);
    return () => { clearInterval(sonda); clearInterval(reloj); };
  }, [generando, executionId]);

  // 4. Generacion. La cola es EN SERIE: una transaccion por llamada.
  const generar = useCallback(async (label: string) => {
    if (generandoRef.current) return;
    generandoRef.current = label;
    setGenerando(label);
    setAbierta(label);
    try {
      await api.post(`/executions/${executionId}/transaction-report?label=${encodeURIComponent(label)}`);
      setDatos((d) => ({ ...d, [label]: { ...(d[label] || { secciones: [] }), error: undefined } }));
    } catch (e: any) {
      const detalle = e?.response?.data?.detail || 'La generacion fallo. Las secciones que alcanzaron a guardarse se muestran abajo.';
      setDatos((d) => ({ ...d, [label]: { ...(d[label] || { secciones: [] }), error: String(detalle) } }));
    } finally {
      generandoRef.current = null;
      setGenerando(null);
      await cargar(label);            // refresco sin recargar la pagina
      setCola((c) => c.slice(1));     // la siguiente de la cola arranca sola
    }
  }, [executionId, cargar]);

  useEffect(() => {
    if (cola.length && !generandoRef.current) generar(cola[0]);
  }, [cola, generar]);

  const guardarSeccion = useCallback(async (label: string, section: string, texto: string) => {
    await api.put(`/executions/${executionId}/transaction-report/${section}?label=${encodeURIComponent(label)}`, { ai_analysis: texto });
    setDatos((d) => {
      const est = d[label];
      if (!est) return d;
      const yaEsta = est.secciones.some((s) => s.section === section);
      const secciones = yaEsta
        ? est.secciones.map((s) => (s.section === section ? { ...s, ai_analysis: texto, is_edited: true } : s))
        : [...est.secciones, { section, ai_analysis: texto, is_edited: true, generated_at: null }];
      return { ...d, [label]: { ...est, secciones } };
    });
  }, [executionId]);

  if (!labels.length) return null;   // regla 16: despues de TODOS los hooks

  // ETAPA 2 (v1.2 §0 y §1): NO hay encabezado de grupo. Tras el informe general,
  // cada bloque empieza directamente con el nombre de la transaccion como titulo.
  // Se va tambien la tarjeta que los envolvia a todos: era la que pedia ese titulo.
  // Lo unico que sobrevive de aquella barra es el boton de generar todas, que es
  // funcion y no encabezado.
  return (
    <div className="mb-8">
      <div>
        <div className="flex justify-end mb-4">
          <button
            onClick={() => setCola(labels.filter((l) => l !== generandoRef.current))}
            disabled={!!generando || !!cola.length}
            className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white text-base font-bold rounded-xl hover:bg-indigo-700 transition-colors disabled:opacity-50"
          >
            <Sparkles className="w-5 h-5" />
            Generar todas ({labels.length})
          </button>
        </div>

        <div className="space-y-4">
          {/* N4.10: la generacion que arranco sola al generar el reporte. */}
          {auto?.status === 'in_progress' && (
            <div className="rounded-2xl border-2 border-indigo-200 bg-indigo-50 px-5 py-4">
              <div className="flex items-center gap-3 text-indigo-800 font-semibold text-lg">
                <Loader2 className="w-5 h-5 animate-spin" />
                {(() => {
                  const act = auto.labels.find((l) => l.state === 'generando')
                    || auto.labels.find((l) => l.state === 'pendiente');
                  return act
                    ? `Generando ${act.label} — ${Math.min(act.done + 1, act.total)} de ${act.total}`
                    : 'Generando los analisis por transaccion...';
                })()}
                <span className="text-indigo-600 font-normal">
                  ({auto.done_labels} de {auto.total_labels} transacciones)
                </span>
              </div>
              <div className="text-sm text-indigo-700 mt-1">
                Arrancaron solas al generar el reporte. Puedes seguir usando la pagina; se completan aqui mismo.
              </div>
            </div>
          )}
          {auto?.labels?.some((l) => l.state === 'parcial') && (
            <div className="rounded-2xl border-2 border-amber-200 bg-amber-50 px-5 py-3 text-base text-amber-800">
              <AlertTriangle className="w-5 h-5 inline mr-2 -mt-1" />
              Quedaron secciones sin texto en{' '}
              {auto.labels.filter((l) => l.state === 'parcial').map((l) => l.label).join(', ')}.
              Se puede rehacer con el boton de esa transaccion.
            </div>
          )}

          {cola.length > 0 && (
            <div className="text-base text-indigo-700">En cola: {cola.join(', ')} — se generan de una en una.</div>
          )}

          {labels.map((label) => {
            const est = datos[label];
            const secciones = est?.secciones || [];
            // Solo las secciones que hoy se generan (D20). Sin este filtro, una
            // transaccion antigua con conclusiones y recomendaciones guardadas
            // mostraba "8 de 6 secciones".
            const conTexto = secciones.filter(
              (s) => s.ai_analysis && (SECTIONS as readonly string[]).includes(s.section)).length;
            const enCurso = generando === label;
            const prog = est?.progreso;
            const total = prog?.total ?? SECTIONS.length;
            // ETAPA 2: sin acordeon. Todos los bloques se ven, igual que el general.
            const abierto = true;

            return (
              <div key={label} className="border-2 border-gray-200 rounded-2xl overflow-hidden">
                <div className="flex items-center justify-between gap-4 px-5 py-4 bg-gray-50">
                  {/* ETAPA 2 (D16): el titulo es el nombre EXACTO de la transaccion,
                      sin prefijos ni subtitulos. Ya no es un boton: no hay acordeon. */}
                  <div className="flex items-center gap-3 text-left flex-1">
                    <span className="text-2xl font-bold text-gray-800">{label}</span>
                    <span className="text-base text-gray-500">{conTexto} de {total} secciones</span>
                    {/* N4.10: la que esta esperando o corriendo por su cuenta. */}
                    {(() => {
                      const a = auto?.labels.find((l) => l.label === label);
                      if (!a || enCurso) return null;
                      if (a.state === 'generando')
                        return <span className="text-base text-indigo-700 font-semibold">generandose sola...</span>;
                      if (a.state === 'pendiente')
                        return <span className="text-base text-gray-500">en cola</span>;
                      return null;
                    })()}
                  </div>
                  <button
                    onClick={() => generar(label)}
                    disabled={!!generando || !!cola.length}
                    className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-base font-semibold rounded-xl hover:bg-indigo-700 transition-colors disabled:opacity-50"
                  >
                    {enCurso ? <Loader2 className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
                    {conTexto ? 'Regenerar' : 'Generar analisis'}
                  </button>
                </div>

                {enCurso && (
                  <div className="px-5 py-3 bg-indigo-50 border-t border-indigo-100">
                    <div className="flex items-center gap-3 text-indigo-800 font-semibold text-lg">
                      <Loader2 className="w-5 h-5 animate-spin" />
                      {/* ETAPA 2 (D20): el total sale del progreso real, no de un 8
                          escrito a mano que dejo de ser cierto al pasar a 6. */}
                      Generando {Math.min((prog?.done || 0) + 1, total)} de {total} — {label} · {segundos} s
                    </div>
                    <div className="w-full bg-indigo-200 rounded-full h-2 overflow-hidden mt-2">
                      <div className="bg-indigo-600 h-2 rounded-full transition-all duration-500" style={{ width: `${((prog?.done || 0) / total) * 100}%` }} />
                    </div>
                    {prog?.pending?.length ? <div className="text-sm text-indigo-700 mt-1">Faltan: {prog.pending.map((p) => TITULOS[p] || p).join(', ')}</div> : null}
                    {avisoSondeo && (
                      <div className="flex items-start gap-2 text-sm text-amber-700 mt-2">
                        <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />{avisoSondeo}
                      </div>
                    )}
                  </div>
                )}

                {est?.error && (
                  <div className="flex items-start gap-2 px-5 py-3 bg-red-50 border-t border-red-100 text-red-700 text-base">
                    <AlertTriangle className="w-5 h-5 mt-0.5 shrink-0" />{est.error}
                  </div>
                )}

                {abierto && (
                  <div className="p-5 space-y-6">
                    {!est && <div className="text-gray-500 text-lg">Cargando gráficas y textos...</div>}

                    {/* ETAPA 2 (D15, v1.2 §1): la MISMA tabla resumen del informe
                        general, filtrada a esta transaccion, y debajo su analisis.
                        Sin fila TOTAL: con una sola transaccion seria la misma cifra
                        repetida. */}
                    {(() => {
                      const fila = secciones.find((s) => s.section === 'summary');
                      const filaTabla = byLabel.filter((r) => r.label === label);
                      return (
                        <>
                          {filaTabla.length > 0 && (
                            <SummaryTable rows={filaTabla} durationSeconds={durationSeconds} />
                          )}
                          <div>
                            <h4 className="text-xl font-bold text-gray-800 mb-2 border-l-4 border-indigo-500 pl-3">
                              {TITULOS.summary}
                              {fila?.generated_at && !fila?.is_edited && <span className="ml-3 text-sm font-normal text-gray-400">IA {hora(fila.generated_at)}</span>}
                            </h4>
                            <TextoEditable
                              valor={fila?.ai_analysis || ''}
                              editado={!!fila?.is_edited}
                              onGuardar={(v) => guardarSeccion(label, 'summary', v)}
                            />
                          </div>
                        </>
                      );
                    })()}

                    {/* Las 5 graficas con sus analisis, pintadas por el MISMO
                        componente que el informe general (D21). */}
                    {est && (
                      <BloqueGraficasTx
                        label={label}
                        series={est.series}
                        secciones={secciones}
                        guardarSeccion={guardarSeccion}
                      />
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
