/**
 * Registro de horas (ETAPA H2.3).
 *
 * Especificación de horas v1.0 §4. La pantalla **no calcula nada**: la jornada,
 * los totales, el "incompleto" y la marca de exceso vienen resueltos del backend
 * (`/time/week`), que a su vez los saca de `services/horas/calendario.py`.
 *
 * Regla 16: todos los hooks antes de cualquier return.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ChevronLeft, ChevronRight, Plus, Trash2, Pencil, AlertTriangle, Check, X,
  CalendarClock, Zap, Loader2,
} from 'lucide-react';
import {
  Dia, DiaPendiente, Disponibilidad, Proyecto, Registro, Semana,
  esPasoValido, fechaCorta, fechaLarga, horas, horasApi, hoyISO, sumarDias,
} from '../../api/horasApi';
import { clientsAPI, usersAPI } from '../../services/api';
import { useAuth } from '../../context/AuthContext';

interface Simple { id: string; name: string; is_active?: boolean }

export default function RegistroPage() {
  const { user } = useAuth();
  const esAdmin = user?.role === 'admin';

  const [usuarios, setUsuarios] = useState<{ id: string; nombre: string }[]>([]);
  const [usuarioSel, setUsuarioSel] = useState('');
  const [fecha, setFecha] = useState(hoyISO());
  const [semana, setSemana] = useState<Semana | null>(null);
  const [pendientes, setPendientes] = useState<DiaPendiente[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [enfocado, setEnfocado] = useState('');

  // Alta
  const [diaAlta, setDiaAlta] = useState('');
  const [clientes, setClientes] = useState<Simple[]>([]);
  const [proyectos, setProyectos] = useState<Proyecto[]>([]);
  const [disp, setDisp] = useState<Disponibilidad[]>([]);
  const [fCliente, setFCliente] = useState('');
  const [fProyecto, setFProyecto] = useState('');
  const [fActividad, setFActividad] = useState('');
  const [fHoras, setFHoras] = useState('');
  const [fFacturable, setFFacturable] = useState(false);
  const [fExtra, setFExtra] = useState(false);
  const [fNotas, setFNotas] = useState('');
  const [guardando, setGuardando] = useState(false);

  // Edición en línea
  const [editando, setEditando] = useState<string | null>(null);
  const [eHoras, setEHoras] = useState('');
  const [eNotas, setENotas] = useState('');

  const fallo = (e: any, porDefecto: string) =>
    setError(e?.response?.data?.detail || porDefecto);

  const objetivo = usuarioSel || user?.id || '';

  const cargar = useCallback(async () => {
    if (!objetivo) return;
    try {
      const [s, p] = await Promise.all([
        horasApi.semana(fecha, objetivo),
        horasApi.diasPendientes(objetivo),
      ]);
      setSemana(s);
      setPendientes(p);
      setError('');
    } catch (e) { fallo(e, 'No se pudo cargar la semana.'); }
    setCargando(false);
  }, [fecha, objetivo]);

  useEffect(() => { cargar(); }, [cargar]);

  useEffect(() => {
    (async () => {
      try {
        const cli = await clientsAPI.list();
        setClientes((cli || []).filter((c: Simple) => c.is_active !== false));
      } catch { /* el formulario avisa si falla */ }
      // H-D13: solo el admin puede cambiar de persona, y solo él puede listar
      // usuarios (GET /users es admin). Los demás se ven a sí mismos y no
      // necesitan la lista.
      if (esAdmin) {
        try {
          const us = await usersAPI.list();
          setUsuarios((us || []).map((u: any) => ({
            id: u.id, nombre: u.full_name || u.username,
          })));
        } catch { /* si falla, el selector se queda con el propio */ }
      }
    })();
  }, [esAdmin]);

  // Al elegir cliente se piden sus proyectos activos (§4.1 encadena los selectores).
  useEffect(() => {
    if (!fCliente) { setProyectos([]); setFProyecto(''); return; }
    horasApi.listarProyectos({ client_id: fCliente, estado: 'activo' })
      .then(setProyectos).catch(() => setProyectos([]));
    setFProyecto(''); setFActividad(''); setDisp([]);
  }, [fCliente]);

  // Al elegir proyecto se piden sus actividades con lo que queda (H-D16).
  useEffect(() => {
    if (!fProyecto) { setDisp([]); setFActividad(''); return; }
    horasApi.disponibilidad(fProyecto).then((d) => {
      setDisp(d);
      // H-D15: facturable hereda del último registro de ese proyecto en la
      // semana visible; si no hay ninguno, queda en "No".
      const previos = (semana?.days || [])
        .flatMap((x) => x.entries).filter((e) => e.project_id === fProyecto);
      setFFacturable(previos.length ? previos[previos.length - 1].billable : false);
    }).catch(() => setDisp([]));
    setFActividad('');
  }, [fProyecto]);   // eslint-disable-line react-hooks/exhaustive-deps

  const restante = useMemo(
    () => disp.find((d) => d.activity_id === fActividad),
    [disp, fActividad],
  );
  const horasNum = parseFloat(fHoras);
  const seExcede = Boolean(restante && esPasoValido(horasNum)
    && horasNum > parseFloat(String(restante.remaining_hours)));

  const abrirAlta = (dia: string) => {
    setDiaAlta(dia);
    setFCliente(''); setFProyecto(''); setFActividad('');
    setFHoras(''); setFExtra(false); setFNotas(''); setFFacturable(false);
    setError('');
  };

  const guardar = async () => {
    if (!esPasoValido(horasNum)) {
      setError('Las horas van en pasos de 0,25 y tienen que ser mayores que cero.');
      return;
    }
    setGuardando(true);
    try {
      await horasApi.crearRegistro({
        user_id: esAdmin && usuarioSel && usuarioSel !== user?.id ? usuarioSel : undefined,
        date: diaAlta, project_id: fProyecto, activity_id: fActividad,
        hours: horasNum, billable: fFacturable, overtime: fExtra,
        notes: fNotas.trim() || undefined,
      });
      setDiaAlta('');
      await cargar();
    } catch (e) { fallo(e, 'No se pudo guardar el registro.'); }
    setGuardando(false);
  };

  const guardarEdicion = async (r: Registro) => {
    const n = parseFloat(eHoras);
    if (!esPasoValido(n)) {
      setError('Las horas van en pasos de 0,25 y tienen que ser mayores que cero.');
      return;
    }
    try {
      await horasApi.editarRegistro(r.id, { hours: n, notes: eNotas });
      setEditando(null);
      await cargar();
    } catch (e) { fallo(e, 'No se pudo editar el registro.'); }
  };

  const borrar = async (r: Registro) => {
    if (!window.confirm(`¿Borrar el registro de ${horas(r.hours)} h en «${r.project_name}»?`)) return;
    try {
      await horasApi.borrarRegistro(r.id);
      await cargar();
    } catch (e) { fallo(e, 'No se pudo borrar el registro.'); }
  };

  const irA = (iso: string) => { setFecha(iso); setEnfocado(iso); };

  const puedeEditar = (r: Registro) => esAdmin || r.user_id === user?.id;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      {/* ---------- Cabecera ---------- */}
      <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-4xl font-bold text-gray-800">Registro de horas</h1>
          <p className="text-lg text-gray-500 mt-1">
            {semana ? `Semana del ${fechaLarga(semana.week_start)} al ${fechaLarga(semana.week_end)}` : '…'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {/* H-D13: solo el admin lo puede cambiar. */}
          <select value={objetivo} onChange={(e) => setUsuarioSel(e.target.value)}
            disabled={!esAdmin} data-testid="selector-usuario"
            className="px-4 py-2.5 border-2 border-gray-300 rounded-xl text-lg disabled:bg-gray-100 disabled:text-gray-500">
            {(usuarios.length ? usuarios : [{ id: user?.id || '', nombre: user?.full_name || user?.username || 'Yo' }])
              .map((u) => <option key={u.id} value={u.id}>{u.nombre}</option>)}
          </select>
          <div className="flex items-center gap-1">
            <button onClick={() => setFecha(sumarDias(fecha, -7))} aria-label="Semana anterior"
              data-testid="semana-anterior"
              className="p-2.5 border-2 border-gray-300 rounded-xl hover:bg-gray-50">
              <ChevronLeft className="w-5 h-5" />
            </button>
            <button onClick={() => irA(hoyISO())} data-testid="hoy"
              className="px-4 py-2.5 border-2 border-gray-300 rounded-xl text-lg font-semibold hover:bg-gray-50">
              Hoy
            </button>
            <button onClick={() => setFecha(sumarDias(fecha, 7))} aria-label="Semana siguiente"
              data-testid="semana-siguiente"
              className="p-2.5 border-2 border-gray-300 rounded-xl hover:bg-gray-50">
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
          <input type="date" value={fecha} onChange={(e) => e.target.value && irA(e.target.value)}
            data-testid="salto-fecha"
            className="px-4 py-2.5 border-2 border-gray-300 rounded-xl text-lg" />
        </div>
      </div>

      {error && (
        <div className="mb-4 flex items-start gap-2 p-4 rounded-xl bg-red-50 border border-red-200 text-red-800">
          <AlertTriangle className="w-5 h-5 mt-0.5 flex-shrink-0" />
          <span className="text-base" data-testid="error-registro">{error}</span>
        </div>
      )}

      {/* ---------- Totales de la semana ---------- */}
      {semana && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          {[
            ['Jornada esperada', horas(semana.total_expected), 'border-gray-300'],
            ['Registradas', horas(semana.total_ordinary), 'border-emerald-500'],
            ['Horas extra', horas(semana.total_overtime), 'border-indigo-500'],
            ['Días pendientes', String(pendientes.length), pendientes.length ? 'border-amber-500' : 'border-gray-300'],
          ].map(([etiqueta, valor, borde]) => (
            <div key={etiqueta} className={`bg-white rounded-xl p-4 border-l-4 ${borde} border border-gray-200 shadow-sm`}>
              <p className="text-sm text-gray-500 uppercase">{etiqueta}</p>
              <p className="text-2xl font-bold text-gray-800 mt-1 tabular-nums" data-testid={`total-${etiqueta}`}>
                {valor}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* ---------- Días pendientes (H-D18) ---------- */}
      {pendientes.length > 0 && (
        <div className="mb-6 bg-amber-50 border border-amber-200 rounded-2xl p-4" data-testid="panel-pendientes">
          <div className="flex items-center gap-2 mb-3">
            <CalendarClock className="w-5 h-5 text-amber-700" />
            <h2 className="text-lg font-bold text-amber-900">
              Días sin registrar o incompletos ({pendientes.length})
            </h2>
          </div>
          <div className="flex flex-wrap gap-2">
            {pendientes.map((p) => (
              <button key={p.date} onClick={() => irA(p.date)}
                data-testid="enlace-pendiente" data-fecha={p.date}
                className="px-3 py-1.5 bg-white border border-amber-300 rounded-lg text-base hover:bg-amber-100">
                <span className="font-semibold">{fechaCorta(p.date)}</span>
                <span className="text-amber-700 ml-2">faltan {horas(p.missing_hours)} h</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ---------- Los siete días ---------- */}
      {cargando ? (
        <div className="py-12 text-center text-gray-400 text-lg">Cargando la semana…</div>
      ) : (
        <div className="space-y-3" data-testid="dias">
          {(semana?.days || []).map((d) => (
            <DiaCard
              key={d.date} dia={d} enfocado={enfocado === d.date}
              onAlta={() => abrirAlta(d.date)}
              editando={editando} eHoras={eHoras} eNotas={eNotas}
              setEHoras={setEHoras} setENotas={setENotas}
              onEditar={(r) => { setEditando(r.id); setEHoras(String(r.hours)); setENotas(r.notes || ''); }}
              onCancelar={() => setEditando(null)}
              onGuardar={guardarEdicion}
              onBorrar={borrar}
              puedeEditar={puedeEditar}
              esAdmin={esAdmin}
            />
          ))}
        </div>
      )}

      {/* ---------- Formulario de alta ---------- */}
      {diaAlta && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setDiaAlta('')}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[88vh] overflow-y-auto"
            data-testid="formulario-alta" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
              <h3 className="text-2xl font-bold text-gray-800">
                Registrar horas — {fechaLarga(diaAlta)}
              </h3>
              <button onClick={() => setDiaAlta('')} aria-label="Cerrar"
                className="p-1.5 rounded-lg text-gray-400 hover:bg-gray-100">
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              {error && (
                <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-800 text-base">
                  {error}
                </div>
              )}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <label className="block">
                  <span className="block text-base font-semibold text-gray-700 mb-1">Cliente</span>
                  <select value={fCliente} onChange={(e) => setFCliente(e.target.value)}
                    data-testid="alta-cliente"
                    className="w-full px-4 py-2.5 border-2 border-gray-300 rounded-xl text-lg">
                    <option value="">Elige…</option>
                    {clientes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </label>
                <label className="block">
                  <span className="block text-base font-semibold text-gray-700 mb-1">Proyecto</span>
                  <select value={fProyecto} onChange={(e) => setFProyecto(e.target.value)}
                    disabled={!fCliente} data-testid="alta-proyecto"
                    className="w-full px-4 py-2.5 border-2 border-gray-300 rounded-xl text-lg disabled:bg-gray-100">
                    <option value="">{fCliente ? 'Elige…' : 'Elige un cliente primero'}</option>
                    {proyectos.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                </label>
              </div>

              <label className="block">
                <span className="block text-base font-semibold text-gray-700 mb-1">Actividad</span>
                <select value={fActividad} onChange={(e) => setFActividad(e.target.value)}
                  disabled={!fProyecto} data-testid="alta-actividad"
                  className="w-full px-4 py-2.5 border-2 border-gray-300 rounded-xl text-lg disabled:bg-gray-100">
                  <option value="">{fProyecto ? 'Elige…' : 'Elige un proyecto primero'}</option>
                  {disp.map((d) => (
                    <option key={d.activity_id} value={d.activity_id}>
                      {d.activity_name} — quedan {horas(d.remaining_hours)} h
                    </option>
                  ))}
                </select>
              </label>

              {/* H-D16: las horas restantes, visibles al elegir actividad. */}
              {restante && (
                <div className="text-base text-gray-600" data-testid="restantes">
                  De <strong>{horas(restante.estimated_hours)} h</strong> estimadas se han
                  registrado <strong>{horas(restante.consumed_hours)} h</strong>:
                  quedan <strong>{horas(restante.remaining_hours)} h</strong>.
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <label className="block">
                  <span className="block text-base font-semibold text-gray-700 mb-1">Horas</span>
                  <input type="number" step="0.25" min="0.25" value={fHoras}
                    onChange={(e) => setFHoras(e.target.value)} data-testid="alta-horas"
                    className="w-full px-4 py-2.5 border-2 border-gray-300 rounded-xl text-lg tabular-nums" />
                </label>
                <label className="flex items-center gap-2 pt-7">
                  <input type="checkbox" checked={fFacturable} data-testid="alta-facturable"
                    onChange={(e) => setFFacturable(e.target.checked)}
                    className="w-5 h-5 accent-[#f5a623]" />
                  <span className="text-lg text-gray-700">Facturable</span>
                </label>
                <label className="flex items-center gap-2 pt-7">
                  <input type="checkbox" checked={fExtra} data-testid="alta-extra"
                    onChange={(e) => setFExtra(e.target.checked)}
                    className="w-5 h-5 accent-indigo-500" />
                  <span className="text-lg text-gray-700">Hora extra</span>
                </label>
              </div>

              {/* H-D16: se avisa con la cifra y SE PERMITE guardar. */}
              {seExcede && (
                <div className="flex items-start gap-2 p-4 rounded-xl bg-amber-50 border border-amber-300 text-amber-900"
                  data-testid="aviso-exceso">
                  <AlertTriangle className="w-5 h-5 mt-0.5 flex-shrink-0" />
                  <span className="text-base">
                    Vas a registrar <strong>{horas(fHoras)} h</strong> y solo
                    quedan <strong>{horas(restante!.remaining_hours)} h</strong> en esta
                    actividad. Se puede guardar igual: el registro quedará marcado como exceso.
                  </span>
                </div>
              )}

              <label className="block">
                <span className="block text-base font-semibold text-gray-700 mb-1">
                  Observaciones <span className="font-normal text-gray-400">(opcional)</span>
                </span>
                <textarea value={fNotas} onChange={(e) => setFNotas(e.target.value)}
                  rows={2} data-testid="alta-notas"
                  className="w-full px-4 py-2.5 border-2 border-gray-300 rounded-xl text-lg resize-y" />
              </label>
            </div>

            <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-200">
              <button onClick={() => setDiaAlta('')}
                className="px-6 py-3 text-lg font-semibold rounded-xl border border-gray-300 text-gray-600 hover:bg-gray-50">
                Cancelar
              </button>
              <button onClick={guardar}
                disabled={guardando || !fActividad || !esPasoValido(horasNum)}
                data-testid="alta-guardar"
                className="flex items-center gap-2 px-6 py-3 bg-[#f5a623] text-[#0a1628] text-lg font-bold rounded-xl hover:bg-[#f7b84a] disabled:opacity-40 disabled:cursor-not-allowed">
                {guardando && <Loader2 className="w-5 h-5 animate-spin" />}
                Guardar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/** La tarjeta de un día. Todo lo que pinta viene resuelto del backend. */
function DiaCard({ dia, enfocado, onAlta, editando, eHoras, eNotas, setEHoras, setENotas,
                   onEditar, onCancelar, onGuardar, onBorrar, puedeEditar, esAdmin }: {
  dia: Dia; enfocado: boolean; onAlta: () => void;
  editando: string | null; eHoras: string; eNotas: string;
  setEHoras: (v: string) => void; setENotas: (v: string) => void;
  onEditar: (r: Registro) => void; onCancelar: () => void;
  onGuardar: (r: Registro) => void; onBorrar: (r: Registro) => void;
  puedeEditar: (r: Registro) => boolean; esAdmin: boolean;
}) {
  const noLaborable = dia.is_holiday || dia.is_absence || parseFloat(String(dia.expected_hours)) === 0;
  return (
    <div data-testid="dia" data-fecha={dia.date}
      data-incompleto={dia.incomplete ? 'si' : 'no'}
      className={`bg-white rounded-2xl border shadow-sm overflow-hidden ${
        enfocado ? 'border-[#f5a623] ring-2 ring-[#f5a623]/40'
          : dia.incomplete ? 'border-amber-300' : 'border-gray-200'}`}>
      <div className={`flex flex-wrap items-center justify-between gap-3 px-5 py-3 ${
        noLaborable ? 'bg-gray-50' : dia.incomplete ? 'bg-amber-50' : 'bg-white'}`}>
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-lg font-bold text-gray-800 capitalize">{fechaLarga(dia.date)}</span>
          {dia.is_holiday && (
            <span className="px-2 py-0.5 text-sm rounded bg-indigo-100 text-indigo-800">
              {dia.non_working_reason || 'Festivo'}
            </span>
          )}
          {dia.is_absence && (
            <span className="px-2 py-0.5 text-sm rounded bg-purple-100 text-purple-800">
              {dia.non_working_reason || 'Ausencia'}
            </span>
          )}
          {dia.incomplete && (
            <span className="px-2 py-0.5 text-sm rounded bg-amber-200 text-amber-900"
              data-testid="marca-incompleto">
              faltan {horas(dia.missing_hours)} h
            </span>
          )}
        </div>
        <div className="flex items-center gap-4">
          <span className="text-lg tabular-nums text-gray-700">
            <strong data-testid="total-dia">{horas(dia.ordinary_hours)}</strong>
            <span className="text-gray-400"> / {horas(dia.expected_hours)} h</span>
          </span>
          {parseFloat(String(dia.overtime_hours)) > 0 && (
            <span className="flex items-center gap-1 text-lg tabular-nums text-indigo-700"
              data-testid="total-extra">
              <Zap className="w-4 h-4" /> {horas(dia.overtime_hours)} h extra
            </span>
          )}
          <button onClick={onAlta} data-testid="anadir-registro"
            className="flex items-center gap-1 px-3 py-1.5 bg-[#f5a623] text-[#0a1628] text-base font-bold rounded-lg hover:bg-[#f7b84a]">
            <Plus className="w-4 h-4" /> Registrar
          </button>
        </div>
      </div>

      {dia.entries.length > 0 && (
        <table className="w-full border-t border-gray-100">
          <tbody data-testid="registros-dia">
            {dia.entries.map((r) => (
              <tr key={r.id} data-testid="registro" data-exceso={r.over_estimate ? 'si' : 'no'}
                className={`border-b border-gray-50 last:border-0 ${r.over_estimate ? 'bg-amber-50/70' : ''}`}>
                <td className="py-2.5 px-5">
                  <div className="text-base text-gray-800">
                    {r.client_name} · <strong>{r.project_name}</strong> · {r.activity_name}
                  </div>
                  {editando === r.id ? (
                    <input value={eNotas} onChange={(e) => setENotas(e.target.value)}
                      placeholder="Observaciones"
                      className="mt-1 w-full px-2 py-1 border border-gray-300 rounded text-sm" />
                  ) : r.notes ? (
                    <div className="text-sm text-gray-500 mt-0.5">{r.notes}</div>
                  ) : null}
                </td>
                <td className="py-2.5 px-3 text-right w-32">
                  {editando === r.id ? (
                    <input type="number" step="0.25" min="0.25" value={eHoras}
                      onChange={(e) => setEHoras(e.target.value)} data-testid="editar-horas"
                      className="w-24 px-2 py-1 border-2 border-[#f5a623] rounded text-base text-right tabular-nums" />
                  ) : (
                    <span className="text-lg font-semibold tabular-nums text-gray-800">
                      {horas(r.hours)} h
                    </span>
                  )}
                </td>
                <td className="py-2.5 px-3 w-44">
                  <div className="flex gap-1.5 flex-wrap">
                    {r.billable && <span className="px-2 py-0.5 text-xs rounded bg-emerald-100 text-emerald-800">facturable</span>}
                    {r.overtime && <span className="px-2 py-0.5 text-xs rounded bg-indigo-100 text-indigo-800">extra</span>}
                    {r.over_estimate && <span className="px-2 py-0.5 text-xs rounded bg-amber-200 text-amber-900" data-testid="marca-exceso">exceso</span>}
                  </div>
                </td>
                <td className="py-2.5 px-5 text-right w-32">
                  {editando === r.id ? (
                    <div className="flex justify-end gap-1">
                      <button onClick={() => onGuardar(r)} aria-label="Guardar" data-testid="editar-guardar"
                        className="p-1.5 text-emerald-600 hover:bg-emerald-50 rounded-lg">
                        <Check className="w-5 h-5" />
                      </button>
                      <button onClick={onCancelar} aria-label="Cancelar"
                        className="p-1.5 text-gray-400 hover:bg-gray-100 rounded-lg">
                        <X className="w-5 h-5" />
                      </button>
                    </div>
                  ) : (
                    <div className="flex justify-end gap-1">
                      {puedeEditar(r) && (
                        <button onClick={() => onEditar(r)} aria-label="Editar" data-testid="editar-registro"
                          className="p-1.5 text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded-lg">
                          <Pencil className="w-5 h-5" />
                        </button>
                      )}
                      {esAdmin && (
                        <button onClick={() => onBorrar(r)} aria-label="Borrar" data-testid="borrar-registro"
                          className="p-1.5 text-red-600 hover:bg-red-50 rounded-lg">
                          <Trash2 className="w-5 h-5" />
                        </button>
                      )}
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
