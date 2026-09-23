/**
 * Sesiones de monitoreo — ETAPA O2d (O-D36).
 *
 * Es la entrada de la sección. Lo que se ve al llegar es **la lista de sesiones
 * con su estado y su fecha**, no un generador de configuración: una sesión es
 * algo que existe y se consulta, no un formulario que se rellena y se pierde.
 *
 * Arriba, si falta el token de lectura, un aviso que se puede resolver ahí
 * mismo — sin él no hay gráficas, y es el fallo número uno.
 */
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity, AlertTriangle, Check, Clock, Loader2, Play, Plus, Radar, Trash2,
} from 'lucide-react';
import { clientsAPI, sesionesAPI } from '../services/api';
import type { ClientInfo, EstadoSesion, SesionMonitoreo } from '../types';

const BOTON = 'min-h-[44px] inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition';
const CAMPO = 'w-full min-h-[44px] px-3 text-lg border border-gray-300 rounded-xl';

const ESTADOS: Record<EstadoSesion, { texto: string; clase: string; icono: JSX.Element }> = {
  preparada: {
    texto: 'Preparada',
    clase: 'bg-gray-100 text-gray-700',
    icono: <Clock className="w-4 h-4" />,
  },
  en_curso: {
    texto: 'En curso',
    clase: 'bg-emerald-100 text-emerald-800',
    icono: <Play className="w-4 h-4" />,
  },
  terminada: {
    texto: 'Terminada',
    clase: 'bg-indigo-100 text-indigo-800',
    icono: <Check className="w-4 h-4" />,
  },
};

function cuando(marca?: string | null): string {
  if (!marca) return '—';
  const fecha = new Date(marca.endsWith('Z') ? marca : `${marca}Z`);
  return fecha.toLocaleString('es-CO', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

export default function SesionesPage() {
  const navegar = useNavigate();
  const [clientes, setClientes] = useState<ClientInfo[]>([]);
  const [filtro, setFiltro] = useState('');
  const [sesiones, setSesiones] = useState<SesionMonitoreo[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');

  const [faltaToken, setFaltaToken] = useState(false);
  const [tokenNuevo, setTokenNuevo] = useState('');
  const [guardandoToken, setGuardandoToken] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      setSesiones(await sesionesAPI.listar(filtro || undefined));
      setError('');
    } catch {
      setError('No se pudo cargar la lista de sesiones.');
    } finally {
      setCargando(false);
    }
  }, [filtro]);

  const revisarToken = useCallback(async () => {
    try {
      const estado = await sesionesAPI.estadoTokenLectura();
      setFaltaToken(!estado.hay_token);
    } catch {
      // Si no se puede preguntar, no se molesta al usuario con un aviso más.
      setFaltaToken(false);
    }
  }, []);

  useEffect(() => {
    clientsAPI.list().then(setClientes).catch(() => setClientes([]));
    void revisarToken();
  }, [revisarToken]);

  useEffect(() => { void cargar(); }, [cargar]);

  const guardarToken = async () => {
    setGuardandoToken(true);
    try {
      await sesionesAPI.guardarTokenLectura(tokenNuevo.trim());
      setTokenNuevo('');
      await revisarToken();
      setError('');
    } catch (e: unknown) {
      const r = e as { response?: { data?: { detail?: string } } };
      setError(r.response?.data?.detail
        || 'No se pudo guardar el token. ¿Es el de lectura y no el de escritura?');
    } finally {
      setGuardandoToken(false);
    }
  };

  const borrar = async (s: SesionMonitoreo) => {
    if (!window.confirm(
      `¿Borrar la sesión «${s.nombre}»?\n\n` +
      `Se borra la sesión, no las métricas: lo que se recogió sigue en la base ` +
      `de métricas. Lo que se pierde es poder volver a verlo desde aquí.`)) return;
    try {
      await sesionesAPI.borrar(s.id);
      await cargar();
    } catch {
      setError('No se pudo borrar la sesión.');
    }
  };

  return (
    <div className="p-8 max-w-[1600px] mx-auto">
      {/* ---------- Cabecera ---------- */}
      <div className="flex items-start justify-between gap-4 mb-6 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-gray-800 flex items-center gap-3">
            <Radar className="w-8 h-8 text-[#f5a623]" /> Sesiones de monitoreo
          </h1>
          <p className="text-lg text-gray-500 mt-1">
            Cada sesión es una prueba mirada de cerca: arriba lo que tardó, abajo
            lo que le costó a tus servidores. Se guardan y se pueden volver a abrir.
          </p>
        </div>
        <button onClick={() => navegar('/observabilidad/sesiones/nueva')}
          data-testid="ses-nueva"
          className={`${BOTON} px-6 text-lg bg-[#f5a623] text-[#0a1628] hover:bg-[#f7b84a]`}>
          <Plus className="w-5 h-5" /> Nueva sesión
        </button>
      </div>

      {/* ---------- O-D33: sin token de lectura no hay gráficas ---------- */}
      {faltaToken && (
        <div className="mb-6 p-5 rounded-2xl bg-amber-50 border border-amber-300"
          data-testid="ses-falta-token">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-6 h-6 text-amber-700 shrink-0" />
            <div className="flex-1">
              <p className="text-lg font-semibold text-amber-900">
                Falta el token de lectura: las gráficas van a salir vacías
              </p>
              <p className="text-base text-amber-900 mt-1">
                Kinetix necesita un token que pueda <strong>leer</strong> las
                métricas. El que ya hay es de solo escritura a propósito —es el
                que se le da a JMeter— y no sirve para dibujar nada. El comando
                para copiarlo está en{' '}
                <code className="bg-amber-100 px-1 rounded">
                  docs/observabilidad/datos-de-prueba.md
                </code>.
              </p>
              <div className="flex gap-3 mt-3 flex-wrap">
                <label className="flex-1 min-w-[280px]">
                  <span className="sr-only">Token de lectura</span>
                  <input value={tokenNuevo} data-testid="ses-token"
                    onChange={(e) => setTokenNuevo(e.target.value)}
                    placeholder="Pega aquí el token de lectura"
                    className={`${CAMPO} font-mono text-base`} />
                </label>
                <button onClick={guardarToken} data-testid="ses-guardar-token"
                  disabled={guardandoToken || tokenNuevo.trim().length < 20}
                  className={`${BOTON} px-6 bg-[#0a1628] text-white hover:bg-[#16243c] disabled:opacity-40`}>
                  {guardandoToken ? <Loader2 className="w-5 h-5 animate-spin" />
                    : <Check className="w-5 h-5" />}
                  Guardar
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ---------- Filtro ---------- */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 mb-6">
        <label className="block max-w-md">
          <span className="block text-base font-semibold text-gray-700 mb-1">Cliente</span>
          <select value={filtro} onChange={(e) => setFiltro(e.target.value)}
            data-testid="ses-filtro-cliente" className={CAMPO}>
            <option value="">Todos los clientes</option>
            {clientes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
      </div>

      {error && (
        <p className="mb-4 p-4 rounded-xl bg-red-50 border border-red-300 text-base text-red-800"
          data-testid="ses-error">{error}</p>
      )}

      {/* ---------- La lista ---------- */}
      {cargando ? (
        <div className="py-16 text-center text-gray-400">
          <Loader2 className="w-8 h-8 animate-spin mx-auto" />
        </div>
      ) : sesiones.length === 0 ? (
        <div className="py-16 text-center" data-testid="ses-vacio">
          <Activity className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-lg text-gray-500">
            Todavía no hay ninguna sesión.
          </p>
          <p className="text-base text-gray-400 mt-1">
            Crea una, conecta tu JMeter, y verás la prueba y tus servidores juntos.
          </p>
        </div>
      ) : (
        <div className="space-y-3" data-testid="ses-lista">
          {sesiones.map((s) => {
            const estado = ESTADOS[s.estado];
            return (
              <div key={s.id} data-testid={`ses-fila-${s.nombre}`}
                className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 flex items-start justify-between gap-4 flex-wrap">
                <button onClick={() => navegar(`/observabilidad/sesiones/${s.id}`)}
                  data-testid={`ses-abrir-${s.nombre}`}
                  className="text-left flex-1 min-w-0 min-h-[44px]">
                  <p className="text-xl font-bold text-gray-800 flex items-center gap-3 flex-wrap">
                    {s.nombre}
                    <span className={`text-sm font-semibold px-2 py-1 rounded-lg inline-flex items-center gap-1 ${estado.clase}`}>
                      {estado.icono} {estado.texto}
                    </span>
                  </p>
                  <p className="text-base text-gray-600 mt-1">
                    {s.cliente_nombre} · {s.proyecto} ·{' '}
                    {s.servidores.length === 0
                      ? <span className="text-amber-700">sin servidores</span>
                      : `${s.servidores.length} servidor${s.servidores.length > 1 ? 'es' : ''}: ${s.servidores.map((v) => v.name).join(', ')}`}
                  </p>
                  <p className="text-base text-gray-400 mt-1">
                    Creada el {cuando(s.creada_en)}
                    {s.termino_en && ` · terminó el ${cuando(s.termino_en)}`}
                  </p>
                </button>
                <div className="flex gap-2">
                  <button onClick={() => navegar(`/observabilidad/sesiones/${s.id}`)}
                    className={`${BOTON} px-5 bg-[#0a1628] text-white hover:bg-[#16243c]`}>
                    Ver
                  </button>
                  <button onClick={() => borrar(s)} data-testid={`ses-borrar-${s.nombre}`}
                    className={`${BOTON} px-4 border border-red-300 text-red-700 hover:bg-red-50`}
                    aria-label={`Borrar ${s.nombre}`}>
                    <Trash2 className="w-5 h-5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
