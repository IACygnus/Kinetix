/**
 * Monitoreo en vivo — ETAPA O1.6 (O-D5 y O-D6).
 *
 * Eliges cliente y proyecto, y la pantalla te da los valores exactos del
 * Backend Listener de JMeter para esa corrida, con un botón de copiar en cada
 * uno. Nadie tiene que recordar una URL ni inventarse un nombre de prueba.
 *
 * El nombre de la corrida lo pone Kinetix (O-D4) y es **la misma etiqueta** con
 * la que se filtra el tablero de abajo: lo que copias y lo que miras no pueden
 * discrepar.
 */
import { useCallback, useEffect, useState } from 'react';
import {
  Activity, AlertTriangle, Check, Copy, Download, Eye, EyeOff, Loader2, RefreshCw,
} from 'lucide-react';
import { clientsAPI, monitoringAPI } from '../services/api';
import type { ClientInfo, ConfiguracionJMeter, MonitoringHealth } from '../types';

/** Los rangos que ofrece el tablero embebido. */
const RANGOS: [string, string][] = [
  ['now-5m', 'Últimos 5 minutos'],
  ['now-15m', 'Últimos 15 minutos'],
  ['now-1h', 'Última hora'],
  ['now-6h', 'Últimas 6 horas'],
  ['now-24h', 'Últimas 24 horas'],
];

const REFRESCOS: [string, string][] = [
  ['5s', 'cada 5 s'],
  ['10s', 'cada 10 s'],
  ['30s', 'cada 30 s'],
  ['', 'no refrescar'],
];

/** 44 px de alto mínimo en todo lo que se pulsa. */
const BOTON = 'min-h-[44px] inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition';

export default function MonitoreoVivoPage() {
  const [clientes, setClientes] = useState<ClientInfo[]>([]);
  const [cliente, setCliente] = useState('');
  const [proyecto, setProyecto] = useState('');
  const [sugerencias, setSugerencias] = useState<string[]>([]);
  const [salud, setSalud] = useState<MonitoringHealth | null>(null);

  const [cfg, setCfg] = useState<ConfiguracionJMeter | null>(null);
  const [generando, setGenerando] = useState(false);
  const [error, setError] = useState('');
  const [copiado, setCopiado] = useState('');
  const [verSecretos, setVerSecretos] = useState(false);

  const [rango, setRango] = useState('now-15m');
  const [refresco, setRefresco] = useState('10s');
  const [recarga, setRecarga] = useState(0);

  useEffect(() => {
    clientsAPI.list().then(setClientes).catch(() => setClientes([]));
    monitoringAPI.getHealth().then(setSalud).catch(() => setSalud(null));
  }, []);

  // Las sugerencias de proyecto son del cliente elegido; al cambiarlo, se piden
  // otra vez y se limpia lo que hubiera generado, que ya no corresponde.
  useEffect(() => {
    setCfg(null);
    if (!cliente) { setSugerencias([]); return; }
    monitoringAPI.proyectosDelCliente(cliente).then(setSugerencias).catch(() => setSugerencias([]));
  }, [cliente]);

  const generar = useCallback(async () => {
    if (!cliente || !proyecto.trim()) return;
    setGenerando(true); setError(''); setVerSecretos(false);
    try {
      setCfg(await monitoringAPI.configuracionJMeter(cliente, proyecto.trim()));
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'No se pudo generar la configuración.');
      setCfg(null);
    }
    setGenerando(false);
  }, [cliente, proyecto]);

  const copiar = async (clave: string, texto: string) => {
    try {
      await navigator.clipboard.writeText(texto);
      setCopiado(clave);
      setTimeout(() => setCopiado((c) => (c === clave ? '' : c)), 1600);
    } catch {
      setError('El navegador no dejó copiar. Selecciona el texto a mano.');
    }
  };

  const urlTablero = () => {
    if (!cfg) return '';
    const p = new URLSearchParams({ orgId: '1', kiosk: 'tv', from: rango, to: 'now',
      theme: 'light', 'var-application': cfg.application });
    if (refresco) p.set('refresh', refresco);
    const sinParams = cfg.url_tablero.split('?')[0];
    return `${sinParams}?${p.toString()}`;
  };

  const listo = Boolean(cliente && proyecto.trim());

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* ---------- Cabecera ---------- */}
      <div className="flex items-start justify-between gap-4 mb-6 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-gray-800 flex items-center gap-3">
            <Activity className="w-8 h-8 text-[#f5a623]" /> Monitoreo en vivo
          </h1>
          <p className="text-lg text-gray-500 mt-1">
            Configura tu JMeter con estos valores y mira la prueba mientras corre.
          </p>
        </div>
        {salud && (
          <div className="text-base text-gray-600" data-testid="mon-salud">
            <span className={salud.influxdb_status === 'ok' ? 'text-emerald-700' : 'text-amber-700'}>
              InfluxDB: {salud.influxdb_status === 'ok' ? 'conectado' : 'sin conexión'}
            </span>
            {' · '}
            <span className={salud.grafana_status === 'ok' ? 'text-emerald-700' : 'text-amber-700'}>
              Grafana: {salud.grafana_status === 'ok' ? 'conectado' : 'sin conexión'}
            </span>
          </div>
        )}
      </div>

      {/* ---------- Elegir la corrida ---------- */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-[1fr_1fr_auto] gap-4 items-end">
          <label className="block">
            <span className="block text-base font-semibold text-gray-700 mb-1">Cliente</span>
            <select value={cliente} onChange={(e) => setCliente(e.target.value)}
              data-testid="mon-cliente"
              className="w-full min-h-[44px] px-3 text-lg border border-gray-300 rounded-xl">
              <option value="">Elige un cliente…</option>
              {clientes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>

          <label className="block">
            <span className="block text-base font-semibold text-gray-700 mb-1">Proyecto</span>
            <input list="mon-proyectos" value={proyecto} onChange={(e) => setProyecto(e.target.value)}
              placeholder="Prueba de carga Q3" data-testid="mon-proyecto"
              className="w-full min-h-[44px] px-3 text-lg border border-gray-300 rounded-xl" />
            <datalist id="mon-proyectos">
              {sugerencias.map((s) => <option key={s} value={s} />)}
            </datalist>
          </label>

          <button onClick={generar} disabled={!listo || generando} data-testid="mon-generar"
            className={`${BOTON} px-6 bg-[#f5a623] text-[#0a1628] text-lg hover:bg-[#f7b84a] disabled:opacity-40 disabled:cursor-not-allowed`}>
            {generando ? <Loader2 className="w-5 h-5 animate-spin" /> : <RefreshCw className="w-5 h-5" />}
            Generar configuración
          </button>
        </div>
        {error && (
          <p className="mt-3 text-base text-red-700" data-testid="mon-error">{error}</p>
        )}
      </div>

      {!cfg ? (
        <div className="py-16 text-center text-gray-400 text-lg" data-testid="mon-sin-corrida">
          Elige un cliente y un proyecto para generar la configuración.
        </div>
      ) : (
        <>
          {cfg.aviso && (
            <div className="flex items-start gap-3 mb-6 p-4 rounded-xl bg-amber-50 border border-amber-300"
              data-testid="mon-aviso">
              <AlertTriangle className="w-6 h-6 text-amber-700 shrink-0" />
              <p className="text-base text-amber-900">{cfg.aviso}</p>
            </div>
          )}

          {/* ---------- El nombre de la corrida ---------- */}
          <div className="flex flex-wrap items-center justify-between gap-4 mb-6 p-5 rounded-2xl bg-[#0a1628] text-white">
            <div>
              <p className="text-sm uppercase tracking-wide text-gray-300">Nombre de esta corrida</p>
              <p className="text-2xl font-bold tabular-nums mt-1" data-testid="mon-application">
                {cfg.application}
              </p>
            </div>
            <div className="flex gap-3 flex-wrap">
              <button onClick={() => copiar('application', cfg.application)}
                data-testid="mon-copiar-application"
                className={`${BOTON} px-5 text-lg bg-[#f5a623] text-[#0a1628] hover:bg-[#f7b84a]`}>
                {copiado === 'application' ? <Check className="w-5 h-5" /> : <Copy className="w-5 h-5" />}
                {copiado === 'application' ? 'Copiado' : 'Copiar'}
              </button>
              <a href={monitoringAPI.urlFragmentoJMeter(cliente, proyecto.trim())}
                data-testid="mon-descargar-jmx"
                className={`${BOTON} px-5 text-lg border-2 border-[#f5a623] text-white hover:bg-white/10`}>
                <Download className="w-5 h-5" /> Descargar el componente .jmx
              </a>
            </div>
          </div>

          {/* ---------- Los parámetros ---------- */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden mb-6">
            <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 border-b border-gray-200">
              <div>
                <h2 className="text-xl font-bold text-gray-800">Backend Listener de JMeter</h2>
                <p className="text-base text-gray-500 mt-0.5">
                  Clase: <code className="text-sm">{cfg.clase_listener}</code>
                </p>
              </div>
              <button onClick={() => setVerSecretos((v) => !v)} data-testid="mon-ver-token"
                className={`${BOTON} px-5 text-base border border-gray-300 text-gray-700 hover:bg-gray-50`}>
                {verSecretos ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                {verSecretos ? 'Ocultar el token' : 'Ver el token'}
              </button>
            </div>

            <table className="w-full" data-testid="mon-tabla-parametros">
              <thead>
                <tr className="text-left text-sm uppercase text-gray-500 bg-gray-50">
                  <th className="px-5 py-3">Parámetro</th>
                  <th className="px-5 py-3">Valor</th>
                  <th className="px-5 py-3">Qué es</th>
                  <th className="px-5 py-3 w-px" />
                </tr>
              </thead>
              <tbody>
                {cfg.argumentos.map((a) => {
                  const tapado = a.secreto && !verSecretos && a.valor;
                  return (
                    <tr key={a.nombre} data-testid="mon-parametro" data-nombre={a.nombre}
                      className="border-t border-gray-100 align-top">
                      <td className="px-5 py-3 font-semibold text-gray-800 whitespace-nowrap">
                        {a.nombre}
                      </td>
                      <td className="px-5 py-3">
                        <code className="text-sm break-all text-gray-800" data-testid="mon-valor">
                          {tapado ? '•'.repeat(28) : (a.valor || <span className="text-gray-400">(vacío)</span>)}
                        </code>
                      </td>
                      <td className="px-5 py-3 text-base text-gray-600">{a.explicacion}</td>
                      <td className="px-5 py-3">
                        <button onClick={() => copiar(a.nombre, a.valor)}
                          disabled={!a.valor} aria-label={`Copiar ${a.nombre}`}
                          data-testid="mon-copiar"
                          className={`${BOTON} w-11 border border-gray-300 text-gray-600 hover:bg-gray-50 disabled:opacity-30`}>
                          {copiado === a.nombre ? <Check className="w-5 h-5 text-emerald-600" />
                            : <Copy className="w-5 h-5" />}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* ---------- El tablero, filtrado por esta corrida ---------- */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5">
            <div className="flex flex-wrap items-center gap-3 mb-4">
              <h2 className="text-xl font-bold text-gray-800 mr-auto">
                La prueba, en vivo
              </h2>
              <select value={rango} onChange={(e) => setRango(e.target.value)}
                data-testid="mon-rango"
                className="min-h-[44px] px-3 text-base border border-gray-300 rounded-xl">
                {RANGOS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
              </select>
              <select value={refresco} onChange={(e) => setRefresco(e.target.value)}
                data-testid="mon-refresco"
                className="min-h-[44px] px-3 text-base border border-gray-300 rounded-xl">
                {REFRESCOS.map(([v, t]) => <option key={v || 'off'} value={v}>{t}</option>)}
              </select>
              <button onClick={() => setRecarga((n) => n + 1)} data-testid="mon-recargar"
                className={`${BOTON} px-5 text-base border border-gray-300 text-gray-700 hover:bg-gray-50`}>
                <RefreshCw className="w-5 h-5" /> Recargar
              </button>
            </div>
            <p className="text-base text-gray-500 mb-3">
              Solo se ve la corrida <strong>{cfg.application}</strong>. Mientras JMeter no
              empiece a enviar, los paneles salen vacíos.
            </p>
            <iframe key={`${urlTablero()}-${recarga}`} src={urlTablero()}
              title="Tablero de Grafana de esta corrida" data-testid="mon-tablero"
              className="w-full h-[70vh] border border-gray-200 rounded-xl bg-white" />
          </div>
        </>
      )}
    </div>
  );
}
