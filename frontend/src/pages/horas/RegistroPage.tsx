/**
 * Registro de horas — el calendario (ETAPA H2b.3).
 *
 * Especificación de horas v1.1 §4.1. **Un calendario mensual es la única vista**:
 * la semanal de H2 se retira, no convive con ella. Dos formas de hacer lo mismo
 * confunden, y era lo que Fredy encontró desordenado.
 *
 * La pantalla **no calcula nada**: el estado de cada día, las horas que faltan,
 * los totales del mes y la marca de desfase vienen resueltos de `/time/month`,
 * que los saca de `services/horas/calendario.py`. El detalle del día se pide a
 * `/time/week`, que es donde vienen los registros con todos sus campos.
 *
 * Regla 16: todos los hooks antes de cualquier return.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle, CalendarClock, ChevronLeft, ChevronRight, Pencil, Plus, Trash2, Zap,
} from 'lucide-react';
import {
  Dia, Mes, Registro, Semana,
  fechaLarga, horas, horasApi, hoyISO, moverMes, nombreDelMes,
} from '../../api/horasApi';
import CalendarioMes from '../../components/horas/CalendarioMes';
import PopupRegistro, { JornadaDelDia } from '../../components/horas/PopupRegistro';
import { usersAPI } from '../../services/api';
import { useAuth } from '../../context/AuthContext';

export default function RegistroPage() {
  const { user } = useAuth();
  const esAdmin = user?.role === 'admin';
  const hoy = hoyISO();

  const [usuarios, setUsuarios] = useState<{ id: string; nombre: string }[]>([]);
  const [usuarioSel, setUsuarioSel] = useState('');
  const [anio, setAnio] = useState(Number(hoy.slice(0, 4)));
  const [mes, setMes] = useState(Number(hoy.slice(5, 7)));
  const [seleccionado, setSeleccionado] = useState(hoy);
  const [datos, setDatos] = useState<Mes | null>(null);
  const [semana, setSemana] = useState<Semana | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');

  // El popup: abierto con una fecha, y con un registro si se está editando.
  const [popup, setPopup] = useState<{ fecha: string; registro: Registro | null } | null>(null);

  const objetivo = usuarioSel || user?.id || '';

  const cargarMes = useCallback(async () => {
    if (!objetivo) return;
    try {
      setDatos(await horasApi.mes(anio, mes, objetivo));
      setError('');
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'No se pudo cargar el mes.');
    }
    setCargando(false);
  }, [anio, mes, objetivo]);

  const cargarDia = useCallback(async () => {
    if (!objetivo || !seleccionado) return;
    try {
      setSemana(await horasApi.semana(seleccionado, objetivo));
    } catch { /* el detalle se queda vacío; el error del mes ya se ve arriba */ }
  }, [seleccionado, objetivo]);

  useEffect(() => { cargarMes(); }, [cargarMes]);
  useEffect(() => { cargarDia(); }, [cargarDia]);

  useEffect(() => {
    // H-D13: solo el admin puede registrar por otra persona, y solo él puede
    // listar usuarios. Los demás se ven a sí mismos y no necesitan la lista.
    if (!esAdmin) return;
    usersAPI.list()
      .then((us: any[]) => setUsuarios((us || []).map((u) => ({
        id: u.id, nombre: u.full_name || u.username,
      }))))
      .catch(() => { /* si falla, el selector se queda con el propio */ });
  }, [esAdmin]);

  const dias = datos?.days || [];
  const diaSel: Dia | undefined = (semana?.days || []).find((d) => d.date === seleccionado);
  const registros = diaSel?.entries || [];

  /** Lo que el popup necesita saber del día que tenga elegido. Sale del mes ya
   *  cargado: si la fecha se va a otro mes, devuelve `null` y la franja calla. */
  const datosDelDia = useCallback((iso: string): JornadaDelDia | null => {
    const d = dias.find((x) => x.date === iso);
    if (!d) return null;
    return {
      jornada: parseFloat(String(d.expected_hours)),
      registradas: parseFloat(String(d.ordinary_hours)),
      faltan: d.incomplete ? parseFloat(String(d.missing_hours)) : 0,
      motivoNoLaborable: d.is_holiday || d.is_absence ? d.non_working_reason : '',
    };
  }, [dias]);

  const irAlMes = (n: number) => {
    const { anio: a, mes: m } = moverMes(anio, mes, n);
    setAnio(a); setMes(m);
    // El día elegido pasa al primero del mes nuevo, salvo que el mes nuevo sea
    // el de hoy: entonces se queda en hoy, que es lo que uno va a registrar.
    const primero = `${a}-${String(m).padStart(2, '0')}-01`;
    setSeleccionado(hoy.startsWith(primero.slice(0, 7)) ? hoy : primero);
  };

  const irAHoy = () => {
    setAnio(Number(hoy.slice(0, 4))); setMes(Number(hoy.slice(5, 7))); setSeleccionado(hoy);
  };

  const recargar = async () => { await Promise.all([cargarMes(), cargarDia()]); };

  const borrar = async (r: Registro) => {
    if (!window.confirm(`¿Borrar el registro de ${horas(r.hours)} h en «${r.project_name}»?`)) return;
    try {
      await horasApi.borrarRegistro(r.id);
      await recargar();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'No se pudo borrar el registro.');
    }
  };

  const puedeEditar = (r: Registro) => esAdmin || r.user_id === user?.id;

  const totalDia = useMemo(() => ({
    ordinarias: parseFloat(String(diaSel?.ordinary_hours || 0)),
    extra: parseFloat(String(diaSel?.overtime_hours || 0)),
    jornada: parseFloat(String(diaSel?.expected_hours || 0)),
  }), [diaSel]);

  const tarjetas: [string, string, string][] = [
    ['Jornada del mes', horas(datos?.total_expected ?? 0), 'border-gray-300'],
    ['Registradas', horas(datos?.total_ordinary ?? 0), 'border-emerald-500'],
    ['Horas extra', horas(datos?.total_overtime ?? 0), 'border-indigo-500'],
    ['Días pendientes', String(datos?.pending_days ?? 0),
      datos?.pending_days ? 'border-amber-500' : 'border-gray-300'],
  ];

  return (
    <div className="p-8 max-w-6xl mx-auto">
      {/* ---------- Cabecera ---------- */}
      <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-4xl font-bold text-gray-800">Registro de horas</h1>
          <p className="text-lg text-gray-500 mt-1 capitalize" data-testid="mes-visible">
            {nombreDelMes(anio, mes)}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2">
            <span className="text-base text-gray-600">Persona</span>
            <select value={objetivo} onChange={(e) => setUsuarioSel(e.target.value)}
              disabled={!esAdmin} data-testid="selector-usuario"
              className="px-4 py-3 border-2 border-gray-300 rounded-xl text-lg disabled:bg-gray-100 disabled:text-gray-500">
              {(usuarios.length ? usuarios : [{
                id: user?.id || '', nombre: user?.full_name || user?.username || 'Yo',
              }]).map((u) => <option key={u.id} value={u.id}>{u.nombre}</option>)}
            </select>
          </label>
          <div className="flex items-center gap-1">
            <button onClick={() => irAlMes(-1)} aria-label="Mes anterior" data-testid="mes-anterior"
              className="p-3 border-2 border-gray-300 rounded-xl hover:bg-gray-50">
              <ChevronLeft className="w-5 h-5" />
            </button>
            <button onClick={irAHoy} data-testid="hoy"
              className="px-5 py-3 border-2 border-gray-300 rounded-xl text-lg font-semibold hover:bg-gray-50">
              Hoy
            </button>
            <button onClick={() => irAlMes(1)} aria-label="Mes siguiente" data-testid="mes-siguiente"
              className="p-3 border-2 border-gray-300 rounded-xl hover:bg-gray-50">
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
          <button onClick={() => setPopup({ fecha: seleccionado, registro: null })}
            data-testid="registrar-horas"
            className="flex items-center gap-2 px-5 py-3 bg-[#f5a623] text-[#0a1628] text-lg font-bold rounded-xl hover:bg-[#f7b84a]">
            <Plus className="w-5 h-5" /> Registrar horas
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 flex items-start gap-2 p-4 rounded-xl bg-red-50 border border-red-200 text-red-800">
          <AlertTriangle className="w-5 h-5 mt-0.5 flex-shrink-0" />
          <span className="text-base" data-testid="error-registro">{error}</span>
        </div>
      )}

      {/* ---------- Resumen del mes ---------- */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        {tarjetas.map(([etiqueta, valor, borde]) => (
          <div key={etiqueta}
            className={`bg-white rounded-xl p-4 border-l-4 ${borde} border border-gray-200 shadow-sm`}>
            <p className="text-sm text-gray-500 uppercase">{etiqueta}</p>
            <p className="text-2xl font-bold text-gray-800 mt-1 tabular-nums"
              data-testid={`total-${etiqueta}`}>{valor}</p>
          </div>
        ))}
      </div>

      {/* ---------- El calendario ---------- */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 mb-6">
        {cargando ? (
          <div className="py-12 text-center text-gray-400 text-lg">Cargando el mes…</div>
        ) : (
          <CalendarioMes dias={dias} hoy={hoy} seleccionado={seleccionado}
            onElegir={(iso) => { setSeleccionado(iso); setPopup(null); }} />
        )}
      </div>

      {/* ---------- El detalle del día elegido ---------- */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden"
        data-testid="detalle-dia" data-fecha={seleccionado}>
        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 border-b border-gray-200">
          <div className="flex items-center gap-3 flex-wrap">
            <CalendarClock className="w-5 h-5 text-gray-400" />
            <h2 className="text-xl font-bold text-gray-800 capitalize">{fechaLarga(seleccionado)}</h2>
            {diaSel?.is_holiday && (
              <span className="px-2 py-0.5 text-sm rounded bg-indigo-100 text-indigo-800">
                {diaSel.non_working_reason || 'Festivo'}
              </span>
            )}
            {diaSel?.is_absence && (
              <span className="px-2 py-0.5 text-sm rounded bg-purple-100 text-purple-800">
                {diaSel.non_working_reason || 'Ausencia'}
              </span>
            )}
            {diaSel?.incomplete && (
              <span className="px-2 py-0.5 text-sm rounded bg-amber-200 text-amber-900"
                data-testid="marca-incompleto">faltan {horas(diaSel.missing_hours)} h</span>
            )}
          </div>
          <div className="flex items-center gap-4">
            <span className="text-lg tabular-nums text-gray-700">
              <strong data-testid="total-dia">{horas(totalDia.ordinarias)}</strong>
              <span className="text-gray-400"> / {horas(totalDia.jornada)} h</span>
            </span>
            {totalDia.extra > 0 && (
              <span className="flex items-center gap-1 text-lg tabular-nums text-indigo-700"
                data-testid="total-extra">
                <Zap className="w-4 h-4" /> {horas(totalDia.extra)} h extra
              </span>
            )}
            <button onClick={() => setPopup({ fecha: seleccionado, registro: null })}
              data-testid="anadir-registro"
              className="flex items-center gap-1 px-4 py-2.5 bg-[#f5a623] text-[#0a1628] text-base font-bold rounded-xl hover:bg-[#f7b84a]">
              <Plus className="w-4 h-4" /> Registrar
            </button>
          </div>
        </div>

        {registros.length === 0 ? (
          <div className="py-10 text-center text-gray-400 text-lg" data-testid="dia-sin-registros">
            Este día no tiene horas registradas.
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="text-left text-sm text-gray-500 uppercase border-b border-gray-100">
                <th className="py-2 px-5 font-semibold">Cliente y proyecto</th>
                <th className="py-2 px-3 font-semibold">Actividad</th>
                <th className="py-2 px-3 font-semibold text-right">Horas</th>
                <th className="py-2 px-3 font-semibold">Marcas</th>
                <th className="py-2 px-5 font-semibold text-right">Acciones</th>
              </tr>
            </thead>
            <tbody data-testid="registros-dia">
              {registros.map((r) => (
                <tr key={r.id} data-testid="registro" data-desfase={r.over_estimate ? 'si' : 'no'}
                  className={`border-b border-gray-50 last:border-0 ${r.over_estimate ? 'bg-amber-50/70' : ''}`}>
                  <td className="py-3 px-5">
                    <div className="text-base text-gray-800">
                      {r.client_name} · <strong>{r.project_name}</strong>
                    </div>
                    {r.notes && <div className="text-sm text-gray-500 mt-0.5">{r.notes}</div>}
                    {r.user_id !== user?.id && (
                      <div className="text-sm text-gray-400 mt-0.5">de {r.user_name}</div>
                    )}
                  </td>
                  <td className="py-3 px-3 text-base text-gray-700">{r.activity_name}</td>
                  <td className="py-3 px-3 text-right">
                    <span className="text-lg font-semibold tabular-nums text-gray-800">
                      {horas(r.hours)} h
                    </span>
                  </td>
                  <td className="py-3 px-3">
                    <div className="flex gap-1.5 flex-wrap">
                      <span className={`px-2 py-0.5 text-xs rounded ${r.billable
                        ? 'bg-emerald-100 text-emerald-800' : 'bg-gray-100 text-gray-600'}`}>
                        {r.billable ? 'facturable' : 'no facturable'}
                      </span>
                      {r.overtime && <span className="px-2 py-0.5 text-xs rounded bg-indigo-100 text-indigo-800">extra</span>}
                      {r.over_estimate && (
                        <span className="px-2 py-0.5 text-xs rounded bg-amber-200 text-amber-900"
                          data-testid="marca-desfase">desfase</span>
                      )}
                    </div>
                  </td>
                  <td className="py-3 px-5 text-right">
                    <div className="flex justify-end gap-1">
                      {puedeEditar(r) && (
                        <button onClick={() => setPopup({ fecha: r.date, registro: r })}
                          aria-label="Editar" data-testid="editar-registro"
                          className="p-3 text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded-lg">
                          <Pencil className="w-5 h-5" />
                        </button>
                      )}
                      {/* §4.2.2: borrar es exclusivo del administrador. */}
                      {esAdmin && (
                        <button onClick={() => borrar(r)} aria-label="Borrar" data-testid="borrar-registro"
                          className="p-3 text-red-600 hover:bg-red-50 rounded-lg">
                          <Trash2 className="w-5 h-5" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {popup && (
        <PopupRegistro
          fecha={popup.fecha}
          registro={popup.registro}
          datosDelDia={datosDelDia}
          userId={esAdmin && usuarioSel && usuarioSel !== user?.id ? usuarioSel : undefined}
          onCerrar={() => setPopup(null)}
          onGuardado={recargar}
        />
      )}
    </div>
  );
}
