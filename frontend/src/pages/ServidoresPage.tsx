/**
 * Servidores observados — ETAPA O2c (O-D24, O-D25, O-D26, O-D28).
 *
 * Aquí se dan de alta los servidores que se miran mientras corre una prueba.
 * Tres cosas se pueden hacer con cada uno:
 *
 *   1. Editarlo o darlo de baja.
 *   2. **Probar la conexión**: si se llega, qué se puede leer, y el error de
 *      verdad cuando falla — no un «no se pudo conectar» que obliga a adivinar.
 *   3. **Generar la configuración**: si es sin agente, los parámetros del
 *      recolector; si es con agente, la orden de instalación, ya rellena.
 *
 * O-D26: la credencial se escribe UNA vez y no vuelve a salir. Ni aquí, ni en
 * ninguna respuesta de la API. Al editar, el campo aparece vacío y en blanco
 * significa «déjala como está».
 *
 * O-D28: Kinetix **no ejecuta** nada en el servidor de nadie. Genera lo que hay
 * que poner; quien lo aplica es una persona con acceso a ese servidor.
 */
import { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle, Check, Copy, Eye, EyeOff, Loader2, Pencil, Plus,
  PlugZap, Server, Settings2, Trash2, X,
} from 'lucide-react';
import { clientsAPI, servidoresAPI } from '../services/api';
import type {
  ClientInfo, ConfiguracionServidor, ResultadoPrueba, ServidorObservado,
  ModoServidor, TipoServidor,
} from '../types';

/** 44 px de alto mínimo en todo lo que se pulsa. */
const BOTON = 'min-h-[44px] inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition';
const CAMPO = 'w-full min-h-[44px] px-3 text-lg border border-gray-300 rounded-xl';

const TIPOS: [TipoServidor, string][] = [
  ['linux', 'Linux'],
  ['postgresql', 'PostgreSQL'],
  ['windows', 'Windows'],
  ['otro', 'Otro'],
];

const MODOS: [ModoServidor, string][] = [
  ['sin_agente', 'Sin agente — se mira desde fuera, cada 10 s'],
  ['agente', 'Con agente — instalado dentro, cada segundo'],
];

/** El puerto de siempre de cada tipo, para que nadie tenga que acordarse. */
const PUERTO_POR_TIPO: Record<TipoServidor, number> = {
  linux: 22, postgresql: 5432, windows: 5985, otro: 22,
};

/** Qué es la credencial según el tipo. No es lo mismo una llave que una clave. */
const CREDENCIAL_POR_TIPO: Record<TipoServidor, string> = {
  linux: 'Llave privada SSH del usuario de solo lectura',
  postgresql: 'Contraseña del rol con pg_monitor',
  windows: 'Contraseña del usuario de solo lectura',
  otro: 'Credencial de acceso',
};

interface Formulario {
  id?: string;
  client_id: string;
  name: string;
  tipo: TipoServidor;
  modo: ModoServidor;
  direccion: string;
  puerto: number;
  usuario: string;
  credencial: string;
  activo: boolean;
  notas: string;
}

const VACIO: Formulario = {
  client_id: '', name: '', tipo: 'linux', modo: 'sin_agente',
  direccion: '', puerto: 22, usuario: '', credencial: '',
  activo: true, notas: '',
};

export default function ServidoresPage() {
  const [clientes, setClientes] = useState<ClientInfo[]>([]);
  const [filtroCliente, setFiltroCliente] = useState('');
  const [servidores, setServidores] = useState<ServidorObservado[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');

  const [form, setForm] = useState<Formulario | null>(null);
  const [guardando, setGuardando] = useState(false);
  const [verCredencial, setVerCredencial] = useState(false);

  const [probando, setProbando] = useState('');
  const [prueba, setPrueba] = useState<Record<string, ResultadoPrueba>>({});
  const [config, setConfig] = useState<ConfiguracionServidor | null>(null);
  const [copiado, setCopiado] = useState('');

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      setServidores(await servidoresAPI.listar(filtroCliente || undefined));
      setError('');
    } catch {
      setError('No se pudo cargar la lista de servidores.');
    } finally {
      setCargando(false);
    }
  }, [filtroCliente]);

  useEffect(() => {
    clientsAPI.list().then(setClientes).catch(() => setClientes([]));
  }, []);

  useEffect(() => { void cargar(); }, [cargar]);

  const copiar = (clave: string, texto: string) => {
    void navigator.clipboard.writeText(texto);
    setCopiado(clave);
    setTimeout(() => setCopiado(''), 1800);
  };

  const abrirNuevo = () => {
    setVerCredencial(false);
    setForm({ ...VACIO, client_id: filtroCliente || clientes[0]?.id || '' });
  };

  const abrirEdicion = (s: ServidorObservado) => {
    setVerCredencial(false);
    setForm({
      id: s.id, client_id: s.client_id, name: s.name, tipo: s.tipo,
      modo: s.modo, direccion: s.direccion, puerto: s.puerto,
      usuario: s.usuario || '',
      // O-D26: en blanco SIEMPRE. No es que no la tengamos: es que no sale.
      credencial: '',
      activo: s.activo, notas: s.notas || '',
    });
  };

  const guardar = async () => {
    if (!form) return;
    setGuardando(true);
    setError('');
    try {
      const datos: Record<string, unknown> = {
        name: form.name, tipo: form.tipo, modo: form.modo,
        direccion: form.direccion, puerto: form.puerto,
        usuario: form.usuario || null, activo: form.activo,
        notas: form.notas || null,
      };
      if (form.id) {
        // En blanco = no la toques. Solo viaja si el usuario escribió algo.
        if (form.credencial) datos.credencial = form.credencial;
        await servidoresAPI.actualizar(form.id, datos);
      } else {
        datos.client_id = form.client_id;
        if (form.credencial) datos.credencial = form.credencial;
        await servidoresAPI.crear(datos);
      }
      setForm(null);
      await cargar();
    } catch (e: unknown) {
      const r = e as { response?: { data?: { detail?: string } } };
      setError(r.response?.data?.detail || 'No se pudo guardar.');
    } finally {
      setGuardando(false);
    }
  };

  const borrar = async (s: ServidorObservado) => {
    if (!window.confirm(
      `¿Dar de baja «${s.name}»?\n\nDeja de mirarse en las próximas pruebas. ` +
      `No se borra ninguna métrica ya recogida.`)) return;
    try {
      await servidoresAPI.borrar(s.id);
      await cargar();
    } catch {
      setError('No se pudo dar de baja.');
    }
  };

  const probar = async (s: ServidorObservado) => {
    setProbando(s.id);
    try {
      // El `await` va fuera del `setPrueba`: la función que se le pasa a un
      // `useState` es síncrona y no puede esperar a nada.
      const resultado = await servidoresAPI.probar(s.id);
      setPrueba((p) => ({ ...p, [s.id]: resultado }));
    } catch {
      setPrueba((p) => ({
        ...p,
        [s.id]: {
          ok: false, resumen: 'La prueba no llegó a ejecutarse',
          error: 'Kinetix no respondió. Mira el registro del backend.',
          lecturas: [], duracion_ms: 0,
        },
      }));
    } finally {
      setProbando('');
    }
  };

  const generar = async (s: ServidorObservado) => {
    try {
      setConfig(await servidoresAPI.configuracion(s.id));
    } catch {
      setError('No se pudo generar la configuración.');
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* ---------- Cabecera ---------- */}
      <div className="flex items-start justify-between gap-4 mb-6 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-gray-800 flex items-center gap-3">
            <Server className="w-8 h-8 text-[#f5a623]" /> Servidores
          </h1>
          <p className="text-lg text-gray-500 mt-1">
            Los servidores que se miran mientras corre una prueba. Al lanzarla,
            los activos del cliente quedan ligados a esa corrida.
          </p>
        </div>
        <button onClick={abrirNuevo} data-testid="srv-nuevo"
          className={`${BOTON} px-6 text-lg bg-[#f5a623] text-[#0a1628] hover:bg-[#f7b84a]`}>
          <Plus className="w-5 h-5" /> Añadir servidor
        </button>
      </div>

      {/* ---------- Filtro ---------- */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 mb-6">
        <label className="block max-w-md">
          <span className="block text-base font-semibold text-gray-700 mb-1">Cliente</span>
          <select value={filtroCliente} onChange={(e) => setFiltroCliente(e.target.value)}
            data-testid="srv-filtro-cliente" className={CAMPO}>
            <option value="">Todos los clientes</option>
            {clientes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
      </div>

      {error && (
        <p className="mb-4 p-4 rounded-xl bg-red-50 border border-red-300 text-base text-red-800"
          data-testid="srv-error">{error}</p>
      )}

      {/* ---------- La lista ---------- */}
      {cargando ? (
        <div className="py-16 text-center text-gray-400 text-lg">
          <Loader2 className="w-8 h-8 animate-spin mx-auto" />
        </div>
      ) : servidores.length === 0 ? (
        <div className="py-16 text-center text-gray-400 text-lg" data-testid="srv-vacio">
          No hay servidores dados de alta todavía.
        </div>
      ) : (
        <div className="space-y-4" data-testid="srv-lista">
          {servidores.map((s) => {
            const r = prueba[s.id];
            return (
              <div key={s.id} data-testid={`srv-fila-${s.name}`}
                className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5">
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div className="min-w-0">
                    <p className="text-xl font-bold text-gray-800 flex items-center gap-2 flex-wrap">
                      {s.name}
                      {!s.activo && (
                        <span className="text-sm font-semibold px-2 py-1 rounded-lg bg-gray-200 text-gray-600">
                          inactivo
                        </span>
                      )}
                      <span className="text-sm font-semibold px-2 py-1 rounded-lg bg-indigo-100 text-indigo-800">
                        {s.modo === 'agente' ? 'con agente' : 'sin agente'}
                      </span>
                    </p>
                    <p className="text-base text-gray-600 mt-1">
                      {TIPOS.find(([t]) => t === s.tipo)?.[1]} ·{' '}
                      <span className="tabular-nums">{s.direccion}:{s.puerto}</span>
                      {s.usuario && <> · usuario <strong>{s.usuario}</strong></>}
                      {s.cliente_nombre && <> · {s.cliente_nombre}</>}
                    </p>
                    <p className="text-base mt-1">
                      {s.tiene_credencial ? (
                        <span className="text-emerald-700">Credencial guardada</span>
                      ) : (
                        <span className="text-amber-700">Sin credencial</span>
                      )}
                      {s.notas && <span className="text-gray-500"> · {s.notas}</span>}
                    </p>
                  </div>

                  <div className="flex gap-2 flex-wrap">
                    <button onClick={() => probar(s)} disabled={probando === s.id}
                      data-testid={`srv-probar-${s.name}`}
                      className={`${BOTON} px-4 bg-[#0a1628] text-white hover:bg-[#16243c] disabled:opacity-40`}>
                      {probando === s.id
                        ? <Loader2 className="w-5 h-5 animate-spin" />
                        : <PlugZap className="w-5 h-5" />}
                      Probar conexión
                    </button>
                    <button onClick={() => generar(s)} data-testid={`srv-config-${s.name}`}
                      className={`${BOTON} px-4 border border-gray-300 hover:bg-gray-50`}>
                      <Settings2 className="w-5 h-5" /> Configuración
                    </button>
                    <button onClick={() => abrirEdicion(s)} data-testid={`srv-editar-${s.name}`}
                      className={`${BOTON} px-4 border border-gray-300 hover:bg-gray-50`}
                      aria-label={`Editar ${s.name}`}>
                      <Pencil className="w-5 h-5" />
                    </button>
                    <button onClick={() => borrar(s)} data-testid={`srv-borrar-${s.name}`}
                      className={`${BOTON} px-4 border border-red-300 text-red-700 hover:bg-red-50`}
                      aria-label={`Dar de baja ${s.name}`}>
                      <Trash2 className="w-5 h-5" />
                    </button>
                  </div>
                </div>

                {/* ---------- El resultado de la prueba (O-D24) ---------- */}
                {r && (
                  <div data-testid={`srv-resultado-${s.name}`}
                    className={`mt-4 p-4 rounded-xl border ${
                      r.ok ? 'bg-emerald-50 border-emerald-300' : 'bg-amber-50 border-amber-300'}`}>
                    <p className="text-lg font-semibold text-gray-800">
                      {r.resumen}{' '}
                      <span className="text-base font-normal text-gray-500 tabular-nums">
                        ({r.duracion_ms} ms)
                      </span>
                    </p>
                    <ul className="mt-2 space-y-1">
                      {r.lecturas.map((l, i) => (
                        <li key={i} className="text-base text-gray-700 flex gap-2">
                          <span className={l.ok ? 'text-emerald-700' : 'text-red-700'}>
                            {l.ok ? '✓' : '✗'}
                          </span>
                          <span><strong>{l.que}</strong>: {l.detalle}</span>
                        </li>
                      ))}
                    </ul>
                    {r.error && (
                      <p className="mt-2 text-base text-red-800 font-mono break-all">
                        {r.error}
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ================= El formulario ================= */}
      {form && (
        <div className="fixed inset-0 bg-black/40 flex items-start justify-center p-4 overflow-auto z-50">
          <div className="bg-white rounded-2xl shadow-xl max-w-2xl w-full my-8 p-6"
            data-testid="srv-formulario">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-2xl font-bold text-gray-800">
                {form.id ? `Editar «${form.name}»` : 'Añadir un servidor'}
              </h2>
              <button onClick={() => setForm(null)} data-testid="srv-cerrar"
                className={`${BOTON} px-3`} aria-label="Cerrar">
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {!form.id && (
                <label className="block md:col-span-2">
                  <span className="block text-base font-semibold text-gray-700 mb-1">Cliente</span>
                  <select value={form.client_id} data-testid="srv-f-cliente"
                    onChange={(e) => setForm({ ...form, client_id: e.target.value })}
                    className={CAMPO}>
                    <option value="">Elige un cliente…</option>
                    {clientes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </label>
              )}

              <label className="block md:col-span-2">
                <span className="block text-base font-semibold text-gray-700 mb-1">Nombre</span>
                <input value={form.name} data-testid="srv-f-nombre"
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="web-01" className={CAMPO} />
                <span className="block text-sm text-gray-500 mt-1">
                  Es la etiqueta con la que sus métricas aparecen en el tablero.
                </span>
              </label>

              <label className="block">
                <span className="block text-base font-semibold text-gray-700 mb-1">Tipo</span>
                <select value={form.tipo} data-testid="srv-f-tipo"
                  onChange={(e) => {
                    const tipo = e.target.value as TipoServidor;
                    // Al cambiar de tipo se propone su puerto de siempre, pero
                    // solo si el que hay era el propuesto del tipo anterior:
                    // si alguien tecleó uno a mano, no se le pisa.
                    const eraElDeSiempre = Object.values(PUERTO_POR_TIPO).includes(form.puerto);
                    setForm({
                      ...form, tipo,
                      puerto: eraElDeSiempre ? PUERTO_POR_TIPO[tipo] : form.puerto,
                    });
                  }}
                  className={CAMPO}>
                  {TIPOS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
                </select>
              </label>

              <label className="block">
                <span className="block text-base font-semibold text-gray-700 mb-1">Modo</span>
                <select value={form.modo} data-testid="srv-f-modo"
                  onChange={(e) => setForm({ ...form, modo: e.target.value as ModoServidor })}
                  className={CAMPO}>
                  {MODOS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
                </select>
              </label>

              <label className="block">
                <span className="block text-base font-semibold text-gray-700 mb-1">Dirección</span>
                <input value={form.direccion} data-testid="srv-f-direccion"
                  onChange={(e) => setForm({ ...form, direccion: e.target.value })}
                  placeholder="10.0.0.15 o servidor.cliente.com" className={CAMPO} />
              </label>

              <label className="block">
                <span className="block text-base font-semibold text-gray-700 mb-1">Puerto</span>
                <input type="number" value={form.puerto} data-testid="srv-f-puerto"
                  onChange={(e) => setForm({ ...form, puerto: Number(e.target.value) })}
                  className={CAMPO} />
              </label>

              <label className="block">
                <span className="block text-base font-semibold text-gray-700 mb-1">Usuario</span>
                <input value={form.usuario} data-testid="srv-f-usuario"
                  onChange={(e) => setForm({ ...form, usuario: e.target.value })}
                  placeholder="kinetix_lector" className={CAMPO} />
              </label>

              <label className="block">
                <span className="block text-base font-semibold text-gray-700 mb-1">
                  {form.tipo === 'postgresql' ? 'Base de datos' : 'Notas'}
                </span>
                <input value={form.notas} data-testid="srv-f-notas"
                  onChange={(e) => setForm({ ...form, notas: e.target.value })}
                  placeholder={form.tipo === 'postgresql' ? 'nombre de la base' : 'opcional'}
                  className={CAMPO} />
              </label>

              {/* ---------- La credencial (O-D26) ---------- */}
              <label className="block md:col-span-2">
                <span className="block text-base font-semibold text-gray-700 mb-1">
                  {CREDENCIAL_POR_TIPO[form.tipo]}
                </span>
                <div className="relative">
                  <textarea value={form.credencial} data-testid="srv-f-credencial"
                    onChange={(e) => setForm({ ...form, credencial: e.target.value })}
                    rows={form.tipo === 'linux' ? 5 : 2}
                    placeholder={form.id
                      ? 'Déjalo en blanco para no cambiarla'
                      : form.tipo === 'linux'
                        ? '-----BEGIN OPENSSH PRIVATE KEY-----'
                        : ''}
                    className={`w-full px-3 py-2 text-base border border-gray-300 rounded-xl font-mono ${
                      verCredencial ? '' : 'text-transparent [caret-color:black] selection:text-transparent'}`}
                    style={verCredencial ? undefined : { textShadow: '0 0 8px rgba(0,0,0,.55)' }} />
                  <button type="button" onClick={() => setVerCredencial((v) => !v)}
                    data-testid="srv-f-ver-credencial"
                    className="absolute right-2 top-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-lg hover:bg-gray-100"
                    aria-label={verCredencial ? 'Ocultar' : 'Ver lo que estoy escribiendo'}>
                    {verCredencial ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
                <span className="block text-sm text-gray-500 mt-1">
                  Se guarda cifrada y <strong>no vuelve a mostrarse nunca</strong>.
                  {form.id && ' Para cambiarla, escribe la nueva; en blanco se queda la que hay.'}
                </span>
              </label>

              <label className="flex items-center gap-3 md:col-span-2 min-h-[44px]">
                <input type="checkbox" checked={form.activo} data-testid="srv-f-activo"
                  onChange={(e) => setForm({ ...form, activo: e.target.checked })}
                  className="w-6 h-6" />
                <span className="text-base text-gray-700">
                  Activo — se mira en las próximas pruebas de este cliente
                </span>
              </label>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setForm(null)}
                className={`${BOTON} px-6 border border-gray-300 hover:bg-gray-50`}>
                Cancelar
              </button>
              <button onClick={guardar} data-testid="srv-f-guardar"
                disabled={guardando || !form.name || !form.direccion || (!form.id && !form.client_id)}
                className={`${BOTON} px-6 bg-[#f5a623] text-[#0a1628] hover:bg-[#f7b84a] disabled:opacity-40`}>
                {guardando ? <Loader2 className="w-5 h-5 animate-spin" /> : <Check className="w-5 h-5" />}
                Guardar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ================= La configuración generada (O-D25) ================= */}
      {config && (
        <div className="fixed inset-0 bg-black/40 flex items-start justify-center p-4 overflow-auto z-50">
          <div className="bg-white rounded-2xl shadow-xl max-w-3xl w-full my-8 p-6"
            data-testid="srv-configuracion">
            <div className="flex items-start justify-between gap-4 mb-4">
              <div>
                <h2 className="text-2xl font-bold text-gray-800">{config.titulo}</h2>
                <p className="text-base text-gray-600 mt-1">{config.explicacion}</p>
              </div>
              <button onClick={() => setConfig(null)} data-testid="srv-config-cerrar"
                className={`${BOTON} px-3`} aria-label="Cerrar">
                <X className="w-6 h-6" />
              </button>
            </div>

            {/* O-D28, bien visible */}
            <div className="flex items-start gap-3 mb-5 p-4 rounded-xl bg-amber-50 border border-amber-300"
              data-testid="srv-config-aviso">
              <AlertTriangle className="w-6 h-6 text-amber-700 shrink-0" />
              <p className="text-base text-amber-900">{config.aviso}</p>
            </div>

            {config.orden ? (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-base font-semibold text-gray-700">
                    Ejecuta esto en el servidor
                  </span>
                  <button onClick={() => copiar('orden', config.orden || '')}
                    data-testid="srv-config-copiar-orden"
                    className={`${BOTON} px-4 bg-[#0a1628] text-white hover:bg-[#16243c]`}>
                    {copiado === 'orden' ? <Check className="w-5 h-5" /> : <Copy className="w-5 h-5" />}
                    {copiado === 'orden' ? 'Copiado' : 'Copiar'}
                  </button>
                </div>
                <pre className="p-4 rounded-xl bg-[#0a1628] text-gray-100 text-sm overflow-auto whitespace-pre-wrap">
                  {config.orden}
                </pre>
              </div>
            ) : (
              <div className="space-y-3" data-testid="srv-config-parametros">
                {config.parametros.map((p) => (
                  <div key={p.nombre} className="border border-gray-200 rounded-xl p-4">
                    <div className="flex items-start justify-between gap-3 flex-wrap">
                      <div className="min-w-0">
                        <p className="text-base font-bold text-gray-800">{p.nombre}</p>
                        <p className="text-base text-gray-700 font-mono break-all mt-1">
                          {p.valor || <span className="text-gray-400">(vacío)</span>}
                        </p>
                        <p className="text-sm text-gray-500 mt-1">{p.explicacion}</p>
                      </div>
                      <button onClick={() => copiar(p.nombre, p.valor)}
                        data-testid={`srv-copiar-${p.nombre}`}
                        className={`${BOTON} px-4 border border-gray-300 hover:bg-gray-50`}>
                        {copiado === p.nombre ? <Check className="w-5 h-5" /> : <Copy className="w-5 h-5" />}
                        {copiado === p.nombre ? 'Copiado' : 'Copiar'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
