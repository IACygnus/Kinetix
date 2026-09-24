/**
 * El popup de registro (ETAPA H2b.3, especificación de horas v1.1 §4.1).
 *
 * Se abre al pulsar un día del calendario o el botón de registrar, y sirve
 * también para editar un registro que ya existe: son el mismo formulario porque
 * son los mismos campos, y mantener dos habría dejado uno de los dos atrás.
 *
 * Lo que la especificación pide y aquí se cumple al pie de la letra:
 *
 *   - una franja con la jornada de ese día y lo que falta por registrar;
 *   - **la fecha es editable dentro del popup**, por si uno se equivocó de día;
 *   - cliente → proyecto → actividad encadenados, con las horas que quedan a la vista;
 *   - **Facturable / No facturable como dos opciones explícitas**: hay que elegir;
 *   - Guardar, **Guardar y añadir otra** y Cancelar.
 *
 * Regla 16: todos los hooks antes de cualquier return.
 */
import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Loader2, X } from 'lucide-react';
import {
  Disponibilidad, Proyecto, Registro,
  esPasoValido, fechaLarga, horas, horasApi, hoyISO,
} from '../../api/horasApi';
import { clientsAPI } from '../../services/api';

interface ClienteSimple { id: string; name: string; is_active?: boolean }

/** Lo que el calendario ya sabe del día, para la franja de arriba. */
export interface JornadaDelDia {
  jornada: number;
  registradas: number;
  faltan: number;
  motivoNoLaborable: string;
}

interface Props {
  fecha: string;
  /** El día que se está mirando, resuelto por el backend. `null` si la fecha
   *  elegida cae fuera del mes cargado: entonces la franja no se inventa nada. */
  datosDelDia: (iso: string) => JornadaDelDia | null;
  /** Si viene, el popup edita ese registro en vez de crear uno nuevo. */
  registro?: Registro | null;
  /** A quién se le registran las horas (H-D13). Vacío = a uno mismo. */
  userId?: string;
  onCerrar: () => void;
  onGuardado: () => void | Promise<void>;
}

export default function PopupRegistro({
  fecha, datosDelDia, registro, userId, onCerrar, onGuardado,
}: Props) {
  const edicion = Boolean(registro);

  const [fFecha, setFFecha] = useState(registro?.date || fecha);
  const [clientes, setClientes] = useState<ClienteSimple[]>([]);
  const [proyectos, setProyectos] = useState<Proyecto[]>([]);
  const [disp, setDisp] = useState<Disponibilidad[]>([]);
  const [fCliente, setFCliente] = useState(registro?.client_id || '');
  const [fProyecto, setFProyecto] = useState(registro?.project_id || '');
  const [fActividad, setFActividad] = useState(registro?.activity_id || '');
  const [fHoras, setFHoras] = useState(registro ? String(registro.hours) : '');
  // §4.1: sin valor por defecto. Facturable o no es una decisión, no una inercia.
  const [fFacturable, setFFacturable] = useState<boolean | null>(
    registro ? registro.billable : null,
  );
  const [fExtra, setFExtra] = useState(registro?.overtime || false);
  const [fNotas, setFNotas] = useState(registro?.notes || '');
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');

  useEffect(() => {
    clientsAPI.list()
      .then((c: ClienteSimple[]) => setClientes((c || []).filter((x) => x.is_active !== false)))
      .catch(() => setError('No se pudo cargar la lista de clientes.'));
  }, []);

  // Cliente → los proyectos de ese cliente **en los que se puede registrar**.
  // ETAPA H8 (§3.1): ese es exactamente uno, `en_ejecucion`. Ofrecer un
  // proyecto detenido solo serviría para que el guardado devolviera un 409
  // después de haber rellenado el formulario entero.
  useEffect(() => {
    if (!fCliente) { setProyectos([]); return; }
    horasApi.listarProyectos({ client_id: fCliente, estado: 'en_ejecucion' })
      .then(setProyectos).catch(() => setProyectos([]));
  }, [fCliente]);

  // Proyecto → actividades con lo que queda de cada una (H-D16).
  useEffect(() => {
    if (!fProyecto) { setDisp([]); return; }
    horasApi.disponibilidad(fProyecto).then(setDisp).catch(() => setDisp([]));
  }, [fProyecto]);

  const dia = datosDelDia(fFecha);
  const restante = useMemo(
    () => disp.find((d) => d.activity_id === fActividad),
    [disp, fActividad],
  );
  const horasNum = parseFloat(fHoras);
  const horasValidas = esPasoValido(horasNum);
  // §4.2.4: se avisa, **se permite guardar** y el registro queda marcado.
  const seDesfasa = Boolean(restante && horasValidas
    && horasNum > parseFloat(String(restante.remaining_hours)));

  const completo = Boolean(fProyecto && fActividad && horasValidas && fFacturable !== null);

  const cambiarCliente = (v: string) => {
    setFCliente(v); setFProyecto(''); setFActividad(''); setDisp([]);
  };
  const cambiarProyecto = (v: string) => { setFProyecto(v); setFActividad(''); };

  const enviar = async (otra: boolean) => {
    if (!completo) return;
    setGuardando(true); setError(''); setAviso('');
    try {
      const datos = {
        date: fFecha, project_id: fProyecto, activity_id: fActividad,
        hours: horasNum, billable: fFacturable as boolean, overtime: fExtra,
        notes: fNotas.trim() || undefined,
      };
      if (registro) {
        await horasApi.editarRegistro(registro.id, datos);
      } else {
        await horasApi.crearRegistro({ ...datos, user_id: userId || undefined });
      }
      await onGuardado();
      if (otra) {
        // Se queda el día, el cliente y el proyecto: un día suele tener varios
        // renglones del mismo sitio. Lo que cambia es la actividad y las horas.
        setFActividad(''); setFHoras(''); setFNotas(''); setFExtra(false);
        setAviso('Registro guardado. Puedes añadir otro.');
      } else {
        onCerrar();
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'No se pudo guardar el registro.');
    }
    setGuardando(false);
  };

  const campo = 'w-full px-4 py-3 border-2 border-gray-300 rounded-xl text-lg disabled:bg-gray-100 disabled:text-gray-400';
  const rotulo = 'block text-base font-semibold text-gray-700 mb-1';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onCerrar}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto"
        data-testid="popup-registro" onClick={(e) => e.stopPropagation()}>

        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h3 className="text-2xl font-bold text-gray-800">
            {edicion ? 'Editar registro' : 'Registrar horas'}
          </h3>
          <button onClick={onCerrar} aria-label="Cerrar"
            className="p-2.5 rounded-lg text-gray-400 hover:bg-gray-100">
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* La franja del día: jornada y lo que falta (§4.1). */}
        <div className="px-6 py-3 bg-gray-50 border-b border-gray-200" data-testid="franja-dia">
          <span className="text-lg text-gray-800 capitalize">{fechaLarga(fFecha)}</span>
          {dia && (
            <span className="text-lg text-gray-600 ml-3 tabular-nums">
              {dia.motivoNoLaborable
                ? `· ${dia.motivoNoLaborable}: no se reclaman horas`
                : dia.jornada === 0
                  ? '· no laborable'
                  : `· jornada de ${horas(dia.jornada)} h · registradas ${horas(dia.registradas)} h`}
              {dia.faltan > 0 && (
                <strong className="text-amber-700"> · faltan {horas(dia.faltan)} h</strong>
              )}
            </span>
          )}
        </div>

        <div className="p-6 space-y-4">
          {error && (
            <div className="flex items-start gap-2 p-4 rounded-xl bg-red-50 border border-red-200 text-red-800"
              data-testid="popup-error">
              <AlertTriangle className="w-5 h-5 mt-0.5 flex-shrink-0" />
              <span className="text-base">{error}</span>
            </div>
          )}
          {aviso && (
            <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-base"
              data-testid="popup-aviso">{aviso}</div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* §4.1: la fecha se puede corregir sin cerrar el popup. */}
            <label className="block">
              <span className={rotulo}>Fecha</span>
              <input type="date" value={fFecha} max={hoyISO()}
                onChange={(e) => e.target.value && setFFecha(e.target.value)}
                data-testid="popup-fecha" className={campo} />
            </label>
            <label className="block">
              <span className={rotulo}>Cliente</span>
              <select value={fCliente} onChange={(e) => cambiarCliente(e.target.value)}
                data-testid="popup-cliente" className={campo}>
                <option value="">Elige…</option>
                {clientes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <label className="block">
              <span className={rotulo}>Proyecto</span>
              <select value={fProyecto} onChange={(e) => cambiarProyecto(e.target.value)}
                disabled={!fCliente} data-testid="popup-proyecto" className={campo}>
                <option value="">{fCliente ? 'Elige…' : 'Elige un cliente primero'}</option>
                {proyectos.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </label>
            <label className="block">
              <span className={rotulo}>Actividad</span>
              <select value={fActividad} onChange={(e) => setFActividad(e.target.value)}
                disabled={!fProyecto} data-testid="popup-actividad" className={campo}>
                <option value="">{fProyecto ? 'Elige…' : 'Elige un proyecto primero'}</option>
                {disp.map((d) => (
                  <option key={d.activity_id} value={d.activity_id}>
                    {d.activity_name} — quedan {horas(d.remaining_hours)} h
                  </option>
                ))}
              </select>
            </label>
          </div>

          {/* Las horas que quedan de esa actividad, a la vista (§4.1). */}
          {restante && (
            <div className="text-base text-gray-600" data-testid="popup-restantes">
              De <strong>{horas(restante.estimated_hours)} h</strong> estimadas se han
              registrado <strong>{horas(restante.consumed_hours)} h</strong>:
              quedan <strong>{horas(restante.remaining_hours)} h</strong>.
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <label className="block">
              <span className={rotulo}>Horas</span>
              <input type="number" step="0.25" min="0.25" value={fHoras}
                onChange={(e) => setFHoras(e.target.value)}
                data-testid="popup-horas" className={`${campo} tabular-nums`} />
              <span className="block text-sm text-gray-400 mt-1">En pasos de 0,25.</span>
            </label>

            {/* §4.1: dos opciones explícitas, no un interruptor. */}
            <fieldset className="block">
              <legend className={rotulo}>¿Se cobra?</legend>
              <div className="flex gap-2">
                {[['Facturable', true], ['No facturable', false]].map(([texto, valor]) => (
                  <label key={String(valor)}
                    className={`flex-1 flex items-center justify-center gap-2 px-3 py-3 rounded-xl border-2 cursor-pointer text-lg ${
                      fFacturable === valor
                        ? 'border-[#f5a623] bg-[#f5a623]/10 font-bold text-gray-800'
                        : 'border-gray-300 text-gray-600 hover:bg-gray-50'}`}>
                    <input type="radio" name="facturable" className="w-5 h-5 accent-[#f5a623]"
                      checked={fFacturable === valor}
                      onChange={() => setFFacturable(valor as boolean)}
                      data-testid={valor ? 'popup-facturable' : 'popup-no-facturable'} />
                    {texto as string}
                  </label>
                ))}
              </div>
            </fieldset>
          </div>

          <label className="flex items-center gap-2">
            <input type="checkbox" checked={fExtra} onChange={(e) => setFExtra(e.target.checked)}
              data-testid="popup-extra" className="w-5 h-5 accent-indigo-500" />
            <span className="text-lg text-gray-700">Son horas extra</span>
          </label>

          {/* §4.2.4: se avisa con la cifra y se puede guardar igual. */}
          {seDesfasa && (
            <div className="flex items-start gap-2 p-4 rounded-xl bg-amber-50 border border-amber-300 text-amber-900"
              data-testid="aviso-desfase">
              <AlertTriangle className="w-5 h-5 mt-0.5 flex-shrink-0" />
              <span className="text-base">
                Vas a registrar <strong>{horas(fHoras)} h</strong> y solo
                quedan <strong>{horas(restante!.remaining_hours)} h</strong> en esta
                actividad. Se puede guardar igual: el registro quedará marcado como desfase.
              </span>
            </div>
          )}

          <label className="block">
            <span className={rotulo}>
              Observaciones <span className="font-normal text-gray-400">(opcional)</span>
            </span>
            <textarea value={fNotas} onChange={(e) => setFNotas(e.target.value)} rows={2}
              data-testid="popup-notas" className={`${campo} resize-y`} />
          </label>
        </div>

        <div className="flex flex-wrap justify-end gap-3 px-6 py-4 border-t border-gray-200">
          <button onClick={onCerrar} data-testid="popup-cancelar"
            className="px-6 py-3 text-lg font-semibold rounded-xl border border-gray-300 text-gray-600 hover:bg-gray-50">
            Cancelar
          </button>
          {!edicion && (
            <button onClick={() => enviar(true)} disabled={guardando || !completo}
              data-testid="popup-guardar-otra"
              className="px-6 py-3 text-lg font-semibold rounded-xl border-2 border-[#f5a623] text-[#0a1628] hover:bg-[#f5a623]/10 disabled:opacity-40 disabled:cursor-not-allowed">
              Guardar y añadir otra
            </button>
          )}
          <button onClick={() => enviar(false)} disabled={guardando || !completo}
            data-testid="popup-guardar"
            className="flex items-center gap-2 px-6 py-3 bg-[#f5a623] text-[#0a1628] text-lg font-bold rounded-xl hover:bg-[#f7b84a] disabled:opacity-40 disabled:cursor-not-allowed">
            {guardando && <Loader2 className="w-5 h-5 animate-spin" />}
            {edicion ? 'Guardar cambios' : 'Guardar'}
          </button>
        </div>
      </div>
    </div>
  );
}
