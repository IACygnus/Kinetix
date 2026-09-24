/**
 * Proyectos del MÓDULO DE HORAS (ETAPA H1.5).
 *
 * Especificación de horas v1.0 §3:
 *   - listado con cliente, nombre, estado, estimado y consumido;
 *   - crear con cliente, nombre y la tabla de actividades con sus horas;
 *   - ampliar o reducir estimaciones, con el historial visible (H-D11);
 *   - añadir o quitar actividades según H-D12.
 *
 * El consumido es 0 en toda la etapa: el registro de horas llega en H2. La
 * columna está desde ahora porque el backend ya la devuelve y así la pantalla no
 * cambia de forma cuando haya datos.
 *
 * Regla 16: todos los hooks antes de cualquier return.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Plus, Trash2, History, Loader2, AlertTriangle, ChevronLeft, Pencil,
} from 'lucide-react';
import {
  Actividad, CambioDeEstado, CambioDeEstimacion, EstadoProyecto, Proyecto, ProyectoDetalle,
  esPasoValido, horas, horasApi,
} from '../../api/horasApi';
import AvisoDesfase, {
  AvisoDesfasados, BarraConsumo, PorcentajeConsumido,
} from '../../components/horas/AvisoDesfase';
// ETAPA H8 (§3.1): el estado, en un solo sitio.
import ChipEstado, { SelectorEstado } from '../../components/horas/EstadoProyecto';
import { clientsAPI } from '../../services/api';
import { useAuth } from '../../context/AuthContext';

interface ClienteMin { id: string; name: string; is_active?: boolean }

export default function ProyectosPage() {
  const { user } = useAuth();
  const esAdmin = user?.role === 'admin';

  const [proyectos, setProyectos] = useState<Proyecto[]>([]);
  const [clientes, setClientes] = useState<ClienteMin[]>([]);
  const [actividades, setActividades] = useState<Actividad[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [filtroCliente, setFiltroCliente] = useState('');
  // H-D84: por defecto se esconden los finalizados y los no viables.
  const [incluirFinalizados, setIncluirFinalizados] = useState(false);
  const [texto, setTexto] = useState('');
  // §5.1: ver solo los que se pasaron. Se filtra aquí y no en el backend porque
  // el listado ya viene entero y el estado viaja en cada fila.
  const [soloDesfasados, setSoloDesfasados] = useState(false);

  // null = listado · 'nuevo' = formulario de alta · id = detalle
  const [vista, setVista] = useState<string | null>(null);
  const [detalle, setDetalle] = useState<ProyectoDetalle | null>(null);
  const [cambios, setCambios] = useState<CambioDeEstimacion[]>([]);
  // ETAPA H8 (H-D83): el historial de estados, que viene de su propio endpoint
  // y se enseña junto al de estimaciones.
  const [cambiosEstado, setCambiosEstado] = useState<CambioDeEstado[]>([]);
  const [verHistorial, setVerHistorial] = useState(false);
  // H-D63: el nombre se puede cambiar después de crear el proyecto.
  const [editandoNombre, setEditandoNombre] = useState(false);
  const [nombreEditado, setNombreEditado] = useState('');

  // Formulario de alta
  const [nuevoCliente, setNuevoCliente] = useState('');
  const [nuevoNombre, setNuevoNombre] = useState('');
  const [nuevasLineas, setNuevasLineas] = useState<{ activity_id: string; horas: string }[]>([
    { activity_id: '', horas: '' },
  ]);
  const [guardando, setGuardando] = useState(false);

  const fallo = (e: any, porDefecto: string) =>
    setError(e?.response?.data?.detail || porDefecto);

  const cargarListado = useCallback(async () => {
    try {
      setProyectos(await horasApi.listarProyectos({
        client_id: filtroCliente || undefined,
        incluir_finalizados: incluirFinalizados || undefined,
        texto: texto.trim() || undefined,
      }));
      setError('');
    } catch (e) { fallo(e, 'No se pudieron cargar los proyectos.'); }
    setCargando(false);
  }, [filtroCliente, incluirFinalizados, texto]);

  useEffect(() => {
    (async () => {
      try {
        const [cli, act] = await Promise.all([
          clientsAPI.list(),
          horasApi.listarActividades(true),
        ]);
        setClientes((cli || []).filter((c: ClienteMin) => c.is_active !== false));
        setActividades(act);
      } catch { /* el listado de abajo ya avisa si algo falla */ }
    })();
  }, []);

  useEffect(() => { if (vista === null) cargarListado(); }, [vista, cargarListado]);

  const abrir = async (id: string) => {
    try {
      const d = await horasApi.verProyecto(id);
      setDetalle(d);
      const [est, edo] = await Promise.all([
        horasApi.historial(id), horasApi.historialEstado(id),
      ]);
      setCambios(est);
      setCambiosEstado(edo);
      setVista(id);
      setVerHistorial(false);
      setError('');
    } catch (e) { fallo(e, 'No se pudo abrir el proyecto.'); }
  };

  const refrescarDetalle = async (d: ProyectoDetalle) => {
    setDetalle(d);
    const [est, edo] = await Promise.all([
      horasApi.historial(d.id), horasApi.historialEstado(d.id),
    ]);
    setCambios(est);
    setCambiosEstado(edo);
  };

  // ---------- Alta ----------
  const lineasValidas = useMemo(
    () => nuevasLineas.filter((l) => l.activity_id && esPasoValido(parseFloat(l.horas))),
    [nuevasLineas],
  );
  const puedeCrear = Boolean(nuevoCliente && nuevoNombre.trim() && lineasValidas.length > 0);

  const crear = async () => {
    setGuardando(true);
    try {
      const d = await horasApi.crearProyecto({
        client_id: nuevoCliente,
        name: nuevoNombre.trim(),
        activities: lineasValidas.map((l) => ({
          activity_id: l.activity_id, estimated_hours: parseFloat(l.horas),
        })),
      });
      setNuevoCliente(''); setNuevoNombre('');
      setNuevasLineas([{ activity_id: '', horas: '' }]);
      setError('');
      await refrescarDetalle(d);
      setVista(d.id);
    } catch (e) { fallo(e, 'No se pudo crear el proyecto.'); }
    setGuardando(false);
  };

  // ---------- Acciones sobre el detalle ----------
  const cambiarEstimacion = async (activityId: string, valor: string) => {
    const n = parseFloat(valor);
    if (!detalle || !esPasoValido(n)) {
      setError('Las horas van en pasos de 0,25 y tienen que ser mayores que cero.');
      return;
    }
    try {
      await refrescarDetalle(await horasApi.guardarActividadDeProyecto(detalle.id, activityId, n));
      setError('');
    } catch (e) { fallo(e, 'No se pudo cambiar la estimación.'); }
  };

  const quitar = async (activityId: string, nombre: string) => {
    if (!detalle) return;
    if (!window.confirm(`¿Quitar «${nombre}» de este proyecto?`)) return;
    try {
      await refrescarDetalle(await horasApi.quitarActividadDeProyecto(detalle.id, activityId));
      setError('');
    } catch (e) { fallo(e, 'No se pudo quitar la actividad.'); }
  };

  // ---------- H-D63: renombrar el proyecto ----------
  const guardarNombre = async () => {
    if (!detalle) return;
    const limpio = nombreEditado.trim();
    if (!limpio || limpio === detalle.name) { setEditandoNombre(false); return; }
    try {
      await refrescarDetalle(await horasApi.editarProyecto(detalle.id, { name: limpio }));
      setEditandoNombre(false);
      setError('');
    } catch (e) {
      // El backend ya comprueba que el nombre sea único por cliente, comparado
      // normalizado: aquí solo se enseña lo que responde.
      fallo(e, 'No se pudo cambiar el nombre del proyecto.');
    }
  };

  // ---------- ETAPA H8 (H-D83): el estado del proyecto ----------
  const cambiarEstado = async (id: string, nuevo: EstadoProyecto) => {
    try {
      const d = await horasApi.cambiarEstadoProyecto(id, nuevo);
      if (detalle && detalle.id === id) await refrescarDetalle(d);
      else await cargarListado();
      setError('');
    } catch (e) { fallo(e, 'No se pudo cambiar el estado del proyecto.'); }
  };

  const disponibles = actividades.filter(
    (a) => !detalle?.activities.some((x) => x.activity_id === a.id));

  const bloqueError = error && (
    <div className="mb-4 flex items-start gap-2 p-4 rounded-xl bg-red-50 border border-red-200 text-red-800">
      <AlertTriangle className="w-5 h-5 mt-0.5 flex-shrink-0" />
      <span className="text-base" data-testid="error-proyectos">{error}</span>
    </div>
  );

  // ==================== FORMULARIO DE ALTA ====================
  if (vista === 'nuevo') {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <button onClick={() => { setVista(null); setError(''); }}
          className="flex items-center gap-1 text-gray-500 hover:text-gray-800 mb-4 text-lg">
          <ChevronLeft className="w-5 h-5" /> Volver
        </button>
        <h1 className="text-4xl font-bold text-gray-800 mb-6">Proyecto nuevo</h1>
        {bloqueError}

        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 space-y-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            <label className="block">
              <span className="block text-base font-semibold text-gray-700 mb-1">Cliente</span>
              <select value={nuevoCliente} onChange={(e) => setNuevoCliente(e.target.value)}
                data-testid="nuevo-cliente"
                className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl text-lg">
                <option value="">Elige un cliente…</option>
                {clientes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="block text-base font-semibold text-gray-700 mb-1">Nombre del proyecto</span>
              <input value={nuevoNombre} onChange={(e) => setNuevoNombre(e.target.value)}
                data-testid="nuevo-nombre"
                className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl text-lg" />
            </label>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-base font-semibold text-gray-700">
                Horas estimadas por actividad
              </span>
              <button onClick={() => setNuevasLineas((l) => [...l, { activity_id: '', horas: '' }])}
                data-testid="anadir-linea"
                className="flex items-center gap-1 px-3 py-1.5 text-sm font-semibold rounded-lg border border-gray-300 hover:bg-gray-50">
                <Plus className="w-4 h-4" /> Añadir actividad
              </button>
            </div>
            <p className="text-sm text-gray-500 mb-3">
              Hace falta al menos una. Las horas van en pasos de 0,25.
            </p>
            <div className="space-y-2" data-testid="lineas-nuevas">
              {nuevasLineas.map((l, i) => {
                const usadas = nuevasLineas.filter((_, j) => j !== i).map((x) => x.activity_id);
                const malas = l.horas !== '' && !esPasoValido(parseFloat(l.horas));
                return (
                  <div key={i} className="flex gap-2 items-start">
                    <select value={l.activity_id}
                      onChange={(e) => setNuevasLineas((ls) =>
                        ls.map((x, j) => j === i ? { ...x, activity_id: e.target.value } : x))}
                      className="flex-1 px-3 py-2.5 border-2 border-gray-300 rounded-xl text-lg">
                      <option value="">Actividad…</option>
                      {actividades.filter((a) => !usadas.includes(a.id)).map((a) => (
                        <option key={a.id} value={a.id}>{a.name}</option>
                      ))}
                    </select>
                    <div className="w-40">
                      <input type="number" step="0.25" min="0.25" value={l.horas}
                        placeholder="Horas"
                        onChange={(e) => setNuevasLineas((ls) =>
                          ls.map((x, j) => j === i ? { ...x, horas: e.target.value } : x))}
                        className={`w-full px-3 py-2.5 border-2 rounded-xl text-lg tabular-nums ${
                          malas ? 'border-red-400' : 'border-gray-300'}`} />
                      {malas && <span className="text-xs text-red-600">pasos de 0,25</span>}
                    </div>
                    {nuevasLineas.length > 1 && (
                      <button onClick={() => setNuevasLineas((ls) => ls.filter((_, j) => j !== i))}
                        aria-label="Quitar" className="p-2.5 text-gray-400 hover:text-red-600">
                        <Trash2 className="w-5 h-5" />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2 border-t border-gray-200">
            <button onClick={() => { setVista(null); setError(''); }}
              className="px-6 py-3 text-lg font-semibold rounded-xl border border-gray-300 text-gray-600 hover:bg-gray-50">
              Cancelar
            </button>
            <button onClick={crear} disabled={!puedeCrear || guardando}
              data-testid="guardar-proyecto"
              className="flex items-center gap-2 px-6 py-3 bg-[#f5a623] text-[#0a1628] text-lg font-bold rounded-xl hover:bg-[#f7b84a] disabled:opacity-40 disabled:cursor-not-allowed">
              {guardando && <Loader2 className="w-5 h-5 animate-spin" />}
              Crear proyecto
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ==================== DETALLE ====================
  if (vista && detalle) {
    // ETAPA H8 (§3.1): **la regla viene del backend**, no se escribe aquí. Si
    // se escribiera, el día que cambiara una de las dos copias la pantalla
    // permitiría lo que el backend rechaza.
    const bloqueado = !detalle.can_edit_estimates;
    return (
      <div className="p-8 max-w-5xl mx-auto">
        <button onClick={() => { setVista(null); setDetalle(null); setError(''); }}
          className="flex items-center gap-1 text-gray-500 hover:text-gray-800 mb-4 text-lg">
          <ChevronLeft className="w-5 h-5" /> Volver a proyectos
        </button>

        <div className="flex items-start justify-between mb-6 gap-4">
          <div>
            {editandoNombre ? (
              <div className="flex flex-wrap items-center gap-2">
                <input value={nombreEditado} onChange={(e) => setNombreEditado(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') guardarNombre(); }}
                  data-testid="editar-nombre-proyecto" autoFocus
                  className="px-4 py-3 border-2 border-[#f5a623] rounded-xl text-3xl font-bold text-gray-800 min-w-[320px]" />
                <button onClick={guardarNombre} data-testid="guardar-nombre-proyecto"
                  className="px-5 py-3 bg-[#f5a623] text-[#0a1628] text-lg font-bold rounded-xl hover:bg-[#f7b84a]">
                  Guardar
                </button>
                <button onClick={() => setEditandoNombre(false)}
                  className="px-5 py-3 text-lg font-semibold rounded-xl border border-gray-300 text-gray-600 hover:bg-gray-50">
                  Cancelar
                </button>
              </div>
            ) : (
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-4xl font-bold text-gray-800" data-testid="nombre-proyecto">{detalle.name}</h1>
                <button data-testid="renombrar-proyecto"
                  onClick={() => { setNombreEditado(detalle.name); setEditandoNombre(true); }}
                  className="flex items-center gap-2 px-4 py-3 text-base font-semibold rounded-xl border-2 border-gray-300 text-gray-600 hover:bg-gray-50">
                  <Pencil className="w-5 h-5" /> Renombrar
                </button>
              </div>
            )}
            <p className="text-lg text-gray-500 mt-1">{detalle.client_name}</p>
            {/* §5.1: cómo va de horas, junto al nombre. */}
            <div className="flex items-center gap-3 mt-3">
              <PorcentajeConsumido dato={detalle} />
              <span className="text-base text-gray-500">
                {horas(detalle.total_consumed_hours)} de {horas(detalle.total_estimated_hours)} h
              </span>
              <AvisoDesfase dato={detalle} siempre />
            </div>
          </div>
          {/* ETAPA H8 (H-D83): el estado se cambia desde el detalle, con un
              selector. Es la columna «Estado» de §5.1, la otra es el consumo
              que está a la izquierda, junto al nombre. */}
          <div className="flex flex-col items-end gap-2" data-testid="estado-proyecto"
            data-estado={detalle.status}>
            <span className="text-sm uppercase text-gray-500 font-semibold">Estado</span>
            <SelectorEstado estado={detalle.status} esAdmin={esAdmin}
              onCambiar={(e) => cambiarEstado(detalle.id, e)} />
            {bloqueado && (
              <span className="text-sm text-gray-500 max-w-[220px] text-right">
                Un proyecto «{detalle.status_label}» no admite cambios en sus estimaciones.
              </span>
            )}
          </div>
        </div>

        {bloqueError}

        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden mb-6">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr className="text-sm uppercase text-gray-500">
                <th className="py-3 px-4 text-left">Actividad</th>
                <th className="py-3 px-4 text-right w-40">Estimadas</th>
                <th className="py-3 px-4 text-right w-40">Consumidas</th>
                <th className="py-3 px-4 text-right w-40">Restantes</th>
                {/* §5.1: cuál es la actividad que tira del proyecto. */}
                <th className="py-3 px-4 text-right w-48">Consumo</th>
                <th className="py-3 px-4 text-right w-20"></th>
              </tr>
            </thead>
            <tbody data-testid="tabla-actividades-proyecto">
              {detalle.activities.map((a) => (
                <tr key={a.activity_id} className="border-b border-gray-100 last:border-0"
                  data-actividad={a.activity_name}>
                  <td className="py-3 px-4 text-lg text-gray-800">{a.activity_name}</td>
                  <td className="py-3 px-4 text-right">
                    <input type="number" step="0.25" min="0.25" disabled={bloqueado}
                      defaultValue={String(a.estimated_hours)}
                      data-testid="estimacion"
                      onBlur={(e) => {
                        if (e.target.value !== String(a.estimated_hours)) {
                          cambiarEstimacion(a.activity_id, e.target.value);
                        }
                      }}
                      className="w-28 px-3 py-1.5 border-2 border-gray-300 rounded-lg text-lg text-right tabular-nums disabled:bg-gray-100" />
                  </td>
                  <td className="py-3 px-4 text-right text-lg tabular-nums text-gray-600">
                    {horas(a.consumed_hours)}
                  </td>
                  <td className={`py-3 px-4 text-right text-lg tabular-nums font-semibold ${
                    a.over_estimate ? 'text-red-600' : 'text-gray-700'}`}>
                    {horas(a.remaining_hours)}
                  </td>
                  <td className="py-3 px-4 text-right" data-actividad-desfase={a.overrun_status}>
                    <div className="flex items-center justify-end gap-2 flex-wrap">
                      <PorcentajeConsumido dato={a} />
                      <AvisoDesfase dato={a} />
                    </div>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <button onClick={() => quitar(a.activity_id, a.activity_name)}
                      disabled={bloqueado} data-testid="quitar-actividad"
                      aria-label={`Quitar ${a.activity_name}`}
                      className="p-2 text-red-600 hover:bg-red-50 rounded-lg disabled:opacity-30">
                      <Trash2 className="w-5 h-5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot className="bg-gray-50 border-t border-gray-200">
              <tr className="text-lg font-bold text-gray-800">
                <td className="py-3 px-4">Total</td>
                <td className="py-3 px-4 text-right tabular-nums" data-testid="total-estimado">
                  {horas(detalle.total_estimated_hours)}
                </td>
                <td className="py-3 px-4 text-right tabular-nums">{horas(detalle.total_consumed_hours)}</td>
                <td colSpan={3}></td>
              </tr>
            </tfoot>
          </table>
        </div>

        {/* Añadir actividad */}
        {!bloqueado && disponibles.length > 0 && (
          <AnadirActividad actividades={disponibles}
            onAnadir={(id, h) => cambiarEstimacion(id, String(h))} />
        )}

        {/* Historial (H-D11) */}
        <div className="mt-6">
          <button onClick={() => setVerHistorial((v) => !v)} data-testid="ver-historial"
            className="flex items-center gap-2 text-lg font-semibold text-gray-600 hover:text-gray-900">
            <History className="w-5 h-5" />
            {verHistorial ? 'Ocultar historial'
              : `Ver historial (${cambios.length + cambiosEstado.length})`}
          </button>

          {/* ETAPA H8 (H-D83): el historial de ESTADOS, encima del de
              estimaciones. Son dos tablas y no una: una va por actividad y la
              otra no tiene ninguna. */}
          {verHistorial && cambiosEstado.length > 0 && (
            <div className="mt-3 bg-white rounded-2xl border border-gray-200 overflow-hidden">
              <div className="px-4 py-2 bg-gray-50 border-b border-gray-200 text-sm uppercase
                              text-gray-500 font-semibold">
                Cambios de estado
              </div>
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr className="text-sm uppercase text-gray-500">
                    <th className="py-2 px-4 text-left">De</th>
                    <th className="py-2 px-4 text-left">A</th>
                    <th className="py-2 px-4 text-left w-52">Quién</th>
                    <th className="py-2 px-4 text-left w-44">Cuándo</th>
                  </tr>
                </thead>
                <tbody data-testid="tabla-historial-estado">
                  {cambiosEstado.map((c) => (
                    <tr key={c.id} className="border-b border-gray-100 last:border-0">
                      <td className="py-2 px-4">
                        {c.previous_status
                          ? <ChipEstado estado={c.previous_status} etiqueta={c.previous_label} />
                          : <span className="text-base text-gray-400">—</span>}
                      </td>
                      <td className="py-2 px-4">
                        <ChipEstado estado={c.new_status} etiqueta={c.new_label} />
                      </td>
                      <td className="py-2 px-4 text-base text-gray-600">{c.changed_by_name}</td>
                      <td className="py-2 px-4 text-base text-gray-500">
                        {new Date(c.changed_at + 'Z').toLocaleString('es-CO')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {verHistorial && (
            <div className="mt-3 bg-white rounded-2xl border border-gray-200 overflow-hidden">
              <div className="px-4 py-2 bg-gray-50 border-b border-gray-200 text-sm uppercase
                              text-gray-500 font-semibold">
                Cambios de estimación
              </div>
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr className="text-sm uppercase text-gray-500">
                    <th className="py-2 px-4 text-left">Actividad</th>
                    <th className="py-2 px-4 text-center w-28">Cambio</th>
                    <th className="py-2 px-4 text-right w-28">Antes</th>
                    <th className="py-2 px-4 text-right w-28">Después</th>
                    <th className="py-2 px-4 text-left w-52">Quién</th>
                    <th className="py-2 px-4 text-left w-44">Cuándo</th>
                  </tr>
                </thead>
                <tbody data-testid="tabla-historial">
                  {cambios.map((c) => (
                    <tr key={c.id} className="border-b border-gray-100 last:border-0">
                      <td className="py-2 px-4 text-base text-gray-800">{c.activity_name}</td>
                      <td className="py-2 px-4 text-center">
                        <span className={`px-2 py-0.5 text-xs font-semibold rounded ${
                          c.change_type === 'alta' ? 'bg-emerald-100 text-emerald-800'
                            : c.change_type === 'baja' ? 'bg-red-100 text-red-800'
                            : 'bg-indigo-100 text-indigo-800'}`}>
                          {c.change_type}
                        </span>
                      </td>
                      <td className="py-2 px-4 text-right tabular-nums text-gray-600">{horas(c.previous_hours)}</td>
                      <td className="py-2 px-4 text-right tabular-nums text-gray-800 font-semibold">{horas(c.new_hours)}</td>
                      <td className="py-2 px-4 text-base text-gray-600">{c.changed_by_name}</td>
                      <td className="py-2 px-4 text-base text-gray-500">
                        {new Date(c.changed_at + 'Z').toLocaleString('es-CO')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    );
  }

  // ==================== LISTADO ====================
  // §5.1: el aviso de arriba y la tabla miran la misma lista.
  const desfasados = proyectos.filter((p) => p.overrun_status === 'desfasado').length;
  const visibles = soloDesfasados
    ? proyectos.filter((p) => p.overrun_status === 'desfasado')
    : proyectos;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex items-start justify-between mb-6 gap-4">
        <div>
          <h1 className="text-4xl font-bold text-gray-800">Proyectos</h1>
          <p className="text-lg text-gray-500 mt-1">
            Cada proyecto pertenece a un cliente y tiene horas estimadas por actividad.
          </p>
        </div>
        <button onClick={() => { setVista('nuevo'); setError(''); }} data-testid="nuevo-proyecto"
          className="flex items-center gap-2 px-6 py-3 bg-[#f5a623] text-[#0a1628] text-lg font-bold rounded-xl hover:bg-[#f7b84a]">
          <Plus className="w-5 h-5" /> Proyecto nuevo
        </button>
      </div>

      {bloqueError}

      {/* §5.1: «Arriba, un aviso dice cuántos proyectos están desfasados». */}
      <AvisoDesfasados cuantos={desfasados} activo={soloDesfasados}
        onAlternar={() => setSoloDesfasados((v) => !v)} />

      <div className="flex flex-wrap gap-3 mb-5">
        <select value={filtroCliente} onChange={(e) => setFiltroCliente(e.target.value)}
          className="px-4 py-2.5 border-2 border-gray-300 rounded-xl text-lg">
          <option value="">Todos los clientes</option>
          {clientes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        {/* H-D84: por defecto se esconden los finalizados y los no viables, que
            se siguen consultando pero no estorban el día a día. */}
        <label className="flex items-center gap-2 px-4 py-2.5">
          <input type="checkbox" checked={incluirFinalizados} data-testid="incluir-finalizados"
            onChange={(e) => setIncluirFinalizados(e.target.checked)}
            className="w-5 h-5 accent-[#f5a623]" />
          <span className="text-lg text-gray-700">Incluir finalizados y no viables</span>
        </label>
        <input value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Buscar por nombre…"
          className="flex-1 min-w-[200px] px-4 py-2.5 border-2 border-gray-300 rounded-xl text-lg" />
      </div>

      {cargando ? (
        <div className="py-12 text-center text-gray-400 text-lg">Cargando proyectos…</div>
      ) : (
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr className="text-sm uppercase text-gray-500">
                <th className="py-3 px-4 text-left">Cliente</th>
                <th className="py-3 px-4 text-left">Proyecto</th>
                {/* §5.1 (H-D82): «Estado» y «Consumo» son DOS columnas, con dos
                    títulos. Nunca en la misma celda: dicen cosas distintas y
                    las dos importan. */}
                <th className="py-3 px-4 text-center w-44">Estado</th>
                <th className="py-3 px-4 text-right w-36">Estimadas</th>
                <th className="py-3 px-4 text-right w-36">Consumidas</th>
                <th className="py-3 px-4 text-right w-56">Consumo</th>
              </tr>
            </thead>
            <tbody data-testid="tabla-proyectos">
 {visibles.map((p) => (
                <tr key={p.id} onClick={() => abrir(p.id)} data-proyecto={p.name}
                  className="border-b border-gray-100 last:border-0 hover:bg-amber-50/50 cursor-pointer">
                  <td className="py-3 px-4 text-lg text-gray-600">{p.client_name}</td>
                  <td className="py-3 px-4 text-lg font-semibold text-gray-800">
                    {p.name}
                    <span className="ml-2 text-sm text-gray-400">
                      {p.activities_count} actividad{p.activities_count === 1 ? '' : 'es'}
                    </span>
                  </td>
                  {/* H-D83: también se cambia desde el listado, sin abrirlo. El
                      `stopPropagation` del selector evita que elegir un estado
                      abra el proyecto. */}
                  <td className="py-3 px-4 text-center" data-proyecto-estado={p.status}>
                    <SelectorEstado estado={p.status} esAdmin={esAdmin}
                      testid="selector-estado-fila"
                      onCambiar={(e) => cambiarEstado(p.id, e)} />
                  </td>
                  <td className="py-3 px-4 text-right text-lg tabular-nums text-gray-700">
                    {horas(p.total_estimated_hours)}
                  </td>
                  <td className="py-3 px-4 text-right text-lg tabular-nums text-gray-600">
                    {horas(p.total_consumed_hours)}
                  </td>
                  <td className="py-3 px-4 text-right" data-proyecto-desfase={p.overrun_status}>
                    {/* §5.1: la barra de consumido frente a estimado. */}
                    <BarraConsumo dato={p} />
                    <div className="flex items-center justify-end gap-2 flex-wrap mt-1">
                      <AvisoDesfase dato={p} />
                    </div>
                  </td>
                </tr>
              ))}
 {visibles.length === 0 && (
                <tr><td colSpan={6} className="py-10 text-center text-gray-400 text-lg">
                  No hay proyectos que coincidan.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/** Fila para añadir una actividad al proyecto. Componente propio porque necesita
 *  su propio estado y los hooks no pueden vivir dentro de un condicional. */
function AnadirActividad({ actividades, onAnadir }: {
  actividades: Actividad[];
  onAnadir: (activityId: string, horas: number) => void;
}) {
  const [id, setId] = useState('');
  const [h, setH] = useState('');
  const valido = Boolean(id) && esPasoValido(parseFloat(h));
  return (
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-4 flex flex-wrap gap-3 items-center">
      <span className="text-base font-semibold text-gray-700">Añadir actividad:</span>
      <select value={id} onChange={(e) => setId(e.target.value)} data-testid="add-actividad-select"
        className="flex-1 min-w-[200px] px-3 py-2.5 border-2 border-gray-300 rounded-xl text-lg">
        <option value="">Elige una…</option>
        {actividades.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
      </select>
      <input type="number" step="0.25" min="0.25" value={h} onChange={(e) => setH(e.target.value)}
        placeholder="Horas" data-testid="add-actividad-horas"
        className="w-32 px-3 py-2.5 border-2 border-gray-300 rounded-xl text-lg tabular-nums" />
      <button onClick={() => { onAnadir(id, parseFloat(h)); setId(''); setH(''); }}
        disabled={!valido} data-testid="add-actividad-boton"
        className="flex items-center gap-2 px-5 py-2.5 bg-[#f5a623] text-[#0a1628] text-lg font-bold rounded-xl hover:bg-[#f7b84a] disabled:opacity-40 disabled:cursor-not-allowed">
        <Plus className="w-5 h-5" /> Añadir
      </button>
    </div>
  );
}
