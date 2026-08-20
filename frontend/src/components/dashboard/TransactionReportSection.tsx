/**
 * N4.7 — Mini-informe por transaccion critica: 5 graficas (N4.4) + 8 textos (N4.6).
 *
 * Vive aparte de Dashboard.tsx (protegido), que solo lo monta. Todo el estado del
 * mini-informe —series, textos, generacion, sondeo y autoguardado— es de este
 * componente.
 *
 * Regla 16: TODOS los hooks se declaran antes de cualquier return.
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { ChevronDown, ChevronRight, Sparkles, AlertTriangle, Loader2 } from 'lucide-react';
import api from '../../services/api';
import { getColorForIndex, getCodeColor } from '../../config/chartConfig';

const SECTIONS = ['summary', 'chart_response_times', 'chart_latency', 'chart_error_rate',
  'chart_codes', 'chart_tps', 'conclusions', 'recommendations'] as const;

const TITULOS: Record<string, string> = {
  summary: 'Resumen de la transaccion',
  chart_response_times: 'Analisis — Tiempos de respuesta',
  chart_latency: 'Analisis — Latencia',
  chart_error_rate: 'Analisis — Tasa de error',
  chart_codes: 'Analisis — Codigos de respuesta',
  chart_tps: 'Analisis — Transacciones por segundo',
  conclusions: 'Conclusiones de la transaccion',
  recommendations: 'Recomendaciones de la transaccion',
};

// Que grafica acompana a que texto. Las tres sin grafica son de ambito general.
const GRAFICA_DE: Record<string, string> = {
  chart_response_times: 'response_times', chart_latency: 'latency',
  chart_error_rate: 'error_rate', chart_codes: 'codes', chart_tps: 'tps',
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

/** Una grafica de la transaccion. `codes` llega como filas (timestamp, code, value)
 *  y se pivota a una serie por codigo. */
function GraficaTx({ tipo, series }: { tipo: string; series: any }) {
  const puntos: any[] = series?.[tipo] || [];
  if (!puntos.length) {
    return <div className="text-base text-gray-400 italic py-6 text-center">Sin datos para esta grafica.</div>;
  }
  let data = puntos;
  let lineas: { key: string; color: string; nombre: string }[] = [{ key: 'value', color: '#4f46e5', nombre: 'Valor' }];

  if (tipo === 'response_times') {
    lineas = [{ key: 'value', color: '#4f46e5', nombre: 'Promedio' }, { key: 'value_max', color: '#ef4444', nombre: 'Maximo' }];
  } else if (tipo === 'codes') {
    const porTs: Record<string, any> = {};
    const codigos = new Set<string>();
    puntos.forEach((p: any) => {
      codigos.add(p.code);
      porTs[p.timestamp] = { ...(porTs[p.timestamp] || { timestamp: p.timestamp }), [p.code]: p.value };
    });
    data = Object.values(porTs);
    lineas = Array.from(codigos).map((c, i) => ({ key: c, color: getCodeColor(c) || getColorForIndex(i), nombre: c }));
  }

  const unidad = tipo === 'error_rate' ? '%' : tipo === 'tps' || tipo === 'codes' ? '/s' : 'ms';
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ top: 8, right: 20, left: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
        <XAxis dataKey="timestamp" tick={{ fontSize: 11 }} tickFormatter={(t) => String(t).slice(11, 19)} minTickGap={40} />
        <YAxis tick={{ fontSize: 11 }} width={60} label={{ value: unidad, angle: -90, position: 'insideLeft', style: { fontSize: 11 } }} />
        <Tooltip labelFormatter={(t) => String(t).slice(11, 19)} formatter={(v: any) => [`${Number(v).toFixed(2)} ${unidad}`, '']} />
        {lineas.length > 1 && <Legend verticalAlign="bottom" height={24} wrapperStyle={{ fontSize: 12 }} />}
        {lineas.map((l) => (
          <Line key={l.key} type="monotone" dataKey={l.key} name={l.nombre} stroke={l.color}
            strokeWidth={1.5} dot={false} connectNulls isAnimationActive={false} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
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
        placeholder="Sin texto todavia. Genera el mini-informe o escribelo a mano."
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

export default function TransactionReportSection({ executionId }: { executionId: string }) {
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

  useEffect(() => {
    if (abierta && !datos[abierta]) cargar(abierta);
  }, [abierta, datos, cargar]);

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

  return (
    <div className="mb-8">
      <div className="bg-white rounded-2xl shadow-lg overflow-hidden border border-gray-200">
        <div className="bg-[#0a1628] px-6 py-4 flex items-center justify-between gap-4">
          <h2 className="text-3xl font-bold text-white">Mini-informe por Transaccion</h2>
          <button
            onClick={() => setCola(labels.filter((l) => l !== generandoRef.current))}
            disabled={!!generando || !!cola.length}
            className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white text-base font-bold rounded-xl hover:bg-indigo-700 transition-colors disabled:opacity-50"
          >
            <Sparkles className="w-5 h-5" />
            Generar todas ({labels.length})
          </button>
        </div>

        <div className="p-6 space-y-4">
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
                    : 'Generando los mini-informes...';
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
            const conTexto = secciones.filter((s) => s.ai_analysis).length;
            const enCurso = generando === label;
            const prog = est?.progreso;
            const abierto = abierta === label;

            return (
              <div key={label} className="border-2 border-gray-200 rounded-2xl overflow-hidden">
                <div className="flex items-center justify-between gap-4 px-5 py-4 bg-gray-50">
                  <button onClick={() => setAbierta(abierto ? null : label)} className="flex items-center gap-3 text-left flex-1">
                    {abierto ? <ChevronDown className="w-6 h-6 text-gray-500" /> : <ChevronRight className="w-6 h-6 text-gray-500" />}
                    <span className="text-2xl font-bold text-gray-800">{label}</span>
                    <span className="text-base text-gray-500">{conTexto} de 8 secciones</span>
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
                  </button>
                  <button
                    onClick={() => generar(label)}
                    disabled={!!generando || !!cola.length}
                    className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-base font-semibold rounded-xl hover:bg-indigo-700 transition-colors disabled:opacity-50"
                  >
                    {enCurso ? <Loader2 className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
                    {conTexto ? 'Regenerar' : 'Generar mini-informe'}
                  </button>
                </div>

                {enCurso && (
                  <div className="px-5 py-3 bg-indigo-50 border-t border-indigo-100">
                    <div className="flex items-center gap-3 text-indigo-800 font-semibold text-lg">
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Generando {Math.min((prog?.done || 0) + 1, 8)} de 8 — {label} · {segundos} s
                    </div>
                    <div className="w-full bg-indigo-200 rounded-full h-2 overflow-hidden mt-2">
                      <div className="bg-indigo-600 h-2 rounded-full transition-all duration-500" style={{ width: `${((prog?.done || 0) / 8) * 100}%` }} />
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
                    {!est && <div className="text-gray-500 text-lg">Cargando graficas y textos...</div>}
                    {SECTIONS.map((sec) => {
                      const fila = secciones.find((s) => s.section === sec);
                      const grafica = GRAFICA_DE[sec];
                      return (
                        <div key={sec}>
                          <h4 className="text-xl font-bold text-gray-800 mb-2 border-l-4 border-indigo-500 pl-3">
                            {TITULOS[sec]}
                            {fila?.generated_at && !fila?.is_edited && <span className="ml-3 text-sm font-normal text-gray-400">IA {hora(fila.generated_at)}</span>}
                          </h4>
                          {grafica && est?.series && <GraficaTx tipo={grafica} series={est.series} />}
                          <TextoEditable
                            valor={fila?.ai_analysis || ''}
                            editado={!!fila?.is_edited}
                            onGuardar={(v) => guardarSeccion(label, sec, v)}
                          />
                        </div>
                      );
                    })}
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
