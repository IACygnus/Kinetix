/**
 * Una sesión de monitoreo — ETAPA O2d (O-D38, O-D39, O-D40, O-D41).
 *
 * **Ésta es la pantalla que faltaba.** Hasta aquí, todo lo que O1 a O2c
 * construyó se veía solo en Grafana, y solo si alguien acertaba la corrida.
 *
 *   Arriba   «Métricas de la prueba»          — lo que tardó
 *   Abajo    «Métricas de la infraestructura» — lo que costó, por servidor
 *
 * Las dos con **el mismo eje de tiempo** (O-D39): ver la causa y el efecto
 * juntos es la idea entera del módulo. Y a todo el ancho (O-D41), porque una
 * gráfica de 300 píxeles no dice nada.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip,
  XAxis, YAxis,
} from 'recharts';
import {
  Activity, AlertTriangle, ArrowLeft, Check, Database, Loader2, Pause,
  RefreshCw, Server,
} from 'lucide-react';
import { sesionesAPI } from '../services/api';
import type { GraficaServidor, MetricasDeSesion, SesionMonitoreo } from '../types';

const BOTON = 'min-h-[44px] inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition';

/** Paleta estable: la misma serie sale del mismo color en todas las gráficas. */
const COLORES = ['#4f46e5', '#f5a623', '#059669', '#dc2626', '#0891b2',
  '#7c3aed', '#ca8a04', '#be185d'];

const RANGOS: [number, string][] = [
  [15, 'Últimos 15 minutos'],
  [60, 'Última hora'],
  [180, 'Últimas 3 horas'],
  [720, 'Últimas 12 horas'],
];

function hora(ms: number): string {
  return new Date(ms).toLocaleTimeString('es-CO',
    { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function abreviar(valor: number, unidad: string): string {
  if (unidad === 'B/s') {
    if (valor > 1048576) return `${(valor / 1048576).toFixed(1)} MB/s`;
    if (valor > 1024) return `${(valor / 1024).toFixed(0)} kB/s`;
    return `${valor.toFixed(0)} B/s`;
  }
  const redondeado = Math.abs(valor) >= 100 ? valor.toFixed(0) : valor.toFixed(1);
  return unidad ? `${redondeado} ${unidad}` : redondeado;
}

/**
 * Una gráfica. Las series vienen como [[ms, valor], ...] y recharts quiere
 * filas: se fusionan por marca de tiempo para que compartan el eje X.
 */
function Grafica({ grafica, alto = 260 }: { grafica: GraficaServidor; alto?: number }) {
  const porTiempo = new Map<number, Record<string, number>>();
  grafica.series.forEach((serie) => {
    serie.puntos.forEach(([t, v]) => {
      const fila = porTiempo.get(t) || { t };
      fila[serie.etiqueta] = v;
      porTiempo.set(t, fila);
    });
  });
  const filas = [...porTiempo.values()].sort((a, b) => a.t - b.t);

  if (filas.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-200 p-5">
        <p className="text-lg font-bold text-gray-800">{grafica.titulo}</p>
        <p className="text-base text-gray-400 py-8 text-center">Sin datos en este rango.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5">
      <p className="text-lg font-bold text-gray-800">{grafica.titulo}</p>
      {grafica.explicacion && (
        <p className="text-base text-gray-500 mt-1 mb-3">{grafica.explicacion}</p>
      )}
      <ResponsiveContainer width="100%" height={alto}>
        <LineChart data={filas} margin={{ top: 8, right: 16, bottom: 4, left: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="t" tickFormatter={hora} tick={{ fontSize: 13 }}
            minTickGap={50} stroke="#9ca3af" />
          <YAxis tick={{ fontSize: 13 }} stroke="#9ca3af"
            tickFormatter={(v: number) => abreviar(v, grafica.unidad)} width={80} />
          <Tooltip
            labelFormatter={(t: number) => hora(t)}
            formatter={(v: number, nombre: string) => [abreviar(v, grafica.unidad), nombre]}
            contentStyle={{ fontSize: 14, borderRadius: 12 }} />
          {grafica.series.length > 1 && <Legend wrapperStyle={{ fontSize: 14 }} />}
          {grafica.series.map((serie, i) => (
            <Line key={serie.etiqueta} type="monotone" dataKey={serie.etiqueta}
              stroke={COLORES[i % COLORES.length]} strokeWidth={2}
              dot={false} isAnimationActive={false} connectNulls />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function SesionPage() {
  const { sesionId } = useParams<{ sesionId: string }>();
  const navegar = useNavigate();

  const [sesion, setSesion] = useState<SesionMonitoreo | null>(null);
  const [metricas, setMetricas] = useState<MetricasDeSesion | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [minutos, setMinutos] = useState(60);
  const [enVivo, setEnVivo] = useState(true);
  const [cerrando, setCerrando] = useState(false);
  const temporizador = useRef<number | null>(null);

  const cargar = useCallback(async (conSpinner = false) => {
    if (!sesionId) return;
    if (conSpinner) setCargando(true);
    try {
      const [s, m] = await Promise.all([
        sesionesAPI.ver(sesionId),
        sesionesAPI.metricas(sesionId, minutos),
      ]);
      setSesion(s);
      setMetricas(m);
      setError('');
    } catch {
      setError('No se pudo cargar la sesión.');
    } finally {
      setCargando(false);
    }
  }, [sesionId, minutos]);

  useEffect(() => { void cargar(true); }, [cargar]);

  // O-D40: una sesión terminada no se refresca sola. Ya no va a cambiar, y
  // refrescarla cada diez segundos sería pedirle lo mismo a la base sin motivo.
  useEffect(() => {
    if (temporizador.current) window.clearInterval(temporizador.current);
    const terminada = sesion?.estado === 'terminada';
    if (!enVivo || terminada) return;
    temporizador.current = window.setInterval(() => { void cargar(); }, 10000);
    return () => {
      if (temporizador.current) window.clearInterval(temporizador.current);
    };
  }, [enVivo, sesion?.estado, cargar]);

  const cerrar = async () => {
    if (!sesionId) return;
    setCerrando(true);
    try {
      await sesionesAPI.actualizar(sesionId, { estado: 'terminada' });
      await cargar();
    } catch {
      setError('No se pudo cerrar la sesión.');
    } finally {
      setCerrando(false);
    }
  };

  if (cargando) {
    return (
      <div className="p-8 text-center text-gray-400">
        <Loader2 className="w-8 h-8 animate-spin mx-auto" />
      </div>
    );
  }

  if (!sesion) {
    return (
      <div className="p-8 max-w-[1600px] mx-auto">
        <p className="text-lg text-red-700">{error || 'No existe esa sesión.'}</p>
      </div>
    );
  }

  const terminada = sesion.estado === 'terminada';

  return (
    <div className="p-6 max-w-[1800px] mx-auto">
      {/* ---------- Cabecera ---------- */}
      <button onClick={() => navegar('/observabilidad/sesiones')}
        className={`${BOTON} px-3 mb-3 text-gray-600 hover:bg-gray-100`}>
        <ArrowLeft className="w-5 h-5" /> Volver a las sesiones
      </button>

      <div className="flex items-start justify-between gap-4 mb-5 flex-wrap">
        <div className="min-w-0">
          <h1 className="text-3xl font-bold text-gray-800">{sesion.nombre}</h1>
          <p className="text-lg text-gray-500 mt-1">
            {sesion.cliente_nombre} · {sesion.proyecto} ·{' '}
            <code className="text-base bg-gray-100 px-2 py-1 rounded"
              data-testid="ses-ver-corrida">{sesion.corrida}</code>
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <label className="block">
            <span className="sr-only">Rango de tiempo</span>
            <select value={minutos} data-testid="ses-rango"
              onChange={(e) => setMinutos(Number(e.target.value))}
              className="min-h-[44px] px-3 text-base border border-gray-300 rounded-xl">
              {RANGOS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
            </select>
          </label>

          {!terminada && (
            <>
              <button onClick={() => setEnVivo((v) => !v)} data-testid="ses-vivo"
                className={`${BOTON} px-4 border ${enVivo
                  ? 'border-emerald-300 bg-emerald-50 text-emerald-800'
                  : 'border-gray-300 text-gray-600'}`}>
                {enVivo ? <Activity className="w-5 h-5" /> : <Pause className="w-5 h-5" />}
                {enVivo ? 'En vivo' : 'Pausado'}
              </button>
              <button onClick={cerrar} disabled={cerrando} data-testid="ses-cerrar"
                className={`${BOTON} px-4 border border-gray-300 hover:bg-gray-50`}>
                {cerrando ? <Loader2 className="w-5 h-5 animate-spin" />
                  : <Check className="w-5 h-5" />}
                Terminar sesión
              </button>
            </>
          )}
          <button onClick={() => cargar()} data-testid="ses-refrescar"
            className={`${BOTON} px-4 border border-gray-300 hover:bg-gray-50`}
            aria-label="Actualizar ahora">
            <RefreshCw className="w-5 h-5" />
          </button>
        </div>
      </div>

      {error && (
        <p className="mb-4 p-4 rounded-xl bg-red-50 border border-red-300 text-base text-red-800">
          {error}
        </p>
      )}

      {/* ---------- El motivo, cuando no hay nada que pintar ---------- */}
      {metricas?.aviso && (
        <div className="mb-5 p-4 rounded-xl bg-amber-50 border border-amber-300 flex items-start gap-3"
          data-testid="ses-aviso">
          <AlertTriangle className="w-6 h-6 text-amber-700 shrink-0" />
          <p className="text-base text-amber-900">{metricas.aviso}</p>
        </div>
      )}

      {/* ================= ARRIBA: la prueba (O-D39) ================= */}
      <section className="mb-8" data-testid="ses-prueba">
        <h2 className="text-2xl font-bold text-gray-800 mb-3 flex items-center gap-2">
          <Activity className="w-6 h-6 text-[#4f46e5]" /> Métricas de la prueba
        </h2>
        {metricas && metricas.prueba.length > 0 ? (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {metricas.prueba.map((g) => (
              <Grafica key={g.titulo} grafica={g} alto={280} />
            ))}
          </div>
        ) : (
          <p className="text-base text-gray-400 py-6 px-5 bg-white rounded-2xl border border-gray-200">
            Todavía no hay métricas de la prueba. Aparecerán en cuanto lances tu
            JMeter con el archivo que descargaste.
          </p>
        )}
      </section>

      {/* ================= ABAJO: la infraestructura (O-D39) ================= */}
      <section data-testid="ses-infraestructura">
        <h2 className="text-2xl font-bold text-gray-800 mb-3 flex items-center gap-2">
          <Server className="w-6 h-6 text-[#f5a623]" /> Métricas de la infraestructura
        </h2>

        {sesion.servidores.length === 0 ? (
          <p className="text-base text-gray-500 py-6 px-5 bg-white rounded-2xl border border-gray-200">
            Esta sesión no tiene ningún servidor marcado.
          </p>
        ) : (
          (metricas?.infraestructura || []).map((servidor) => (
            <div key={servidor.servidor} className="mb-6"
              data-testid={`ses-srv-${servidor.servidor}`}>
              <h3 className="text-xl font-bold text-gray-700 mb-3 flex items-center gap-2">
                {servidor.tipo === 'postgresql'
                  ? <Database className="w-5 h-5 text-gray-400" />
                  : <Server className="w-5 h-5 text-gray-400" />}
                {servidor.servidor}
                <span className="text-base font-normal text-gray-400">
                  ({servidor.tipo})
                </span>
              </h3>
              {servidor.graficas.length === 0 ? (
                <p className="text-base text-gray-400 py-5 px-5 bg-white rounded-2xl border border-gray-200">
                  Sin métricas de este servidor en el rango elegido.
                </p>
              ) : (
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                  {servidor.graficas.map((g) => (
                    <Grafica key={g.titulo} grafica={g} />
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </section>
    </div>
  );
}
