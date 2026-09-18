/**
 * Consulta de proyectos (ETAPA H3.3, especificación de horas v1.1 §5).
 *
 * *«Por proyecto: quién ha registrado y cuántas horas… Al ampliar la consulta, la
 * tabla cambia y muestra los días en que se registraron esas horas.»*
 *
 * Son dos despliegues encadenados, y esa es la forma que pidió Fredy:
 *
 *     proyecto  →  la gente que registró en él  →  los días de esa persona
 *
 * El primero ya viene en la respuesta; el segundo se pide al desplegarlo, porque
 * casi nunca se abren todos. **La pantalla no calcula nada**: los totales, el
 * porcentaje y el estado de desfase vienen resueltos de `/time/consulta`.
 *
 * Regla 16: todos los hooks antes de cualquier return.
 */
import { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle, ChevronDown, ChevronRight, Loader2, Search, Zap,
} from 'lucide-react';
import {
  Consulta, ConsultaPersona, ConsultaProyecto, Proyecto, Registro,
  fechaLarga, horas, horasApi, hoyISO,
} from '../../api/horasApi';
import AvisoDesfase, { AvisoDesfasados, BarraConsumo } from '../../components/horas/AvisoDesfase';
import { clientsAPI, usersAPI } from '../../services/api';

interface Simple { id: string; name: string; is_active?: boolean }

/** El primer y el último día del mes en curso, sin pasar por UTC. */
const mesEnCurso = (): [string, string] => {
  const hoy = hoyISO();
  const [a, m] = hoy.split('-').map(Number);
  const ultimo = new Date(a, m, 0).getDate();
  return [`${hoy.slice(0, 7)}-01`, `${hoy.slice(0, 7)}-${String(ultimo).padStart(2, '0')}`];
};

export default function ConsultaPage() {
  const [inicio, fin] = mesEnCurso();
  const [desde, setDesde] = useState(inicio);
  const [hasta, setHasta] = useState(fin);
  const [fCliente, setFCliente] = useState('');
  const [fProyecto, setFProyecto] = useState('');
  const [fUsuario, setFUsuario] = useState('');
  const [soloDesfasados, setSoloDesfasados] = useState(false);

  const [clientes, setClientes] = useState<Simple[]>([]);
  const [proyectos, setProyectos] = useState<Proyecto[]>([]);
  const [usuarios, setUsuarios] = useState<{ id: string; nombre: string }[]>([]);

  const [datos, setDatos] = useState<Consulta | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');

  // Qué proyectos están desplegados, y los días ya pedidos por (proyecto|persona).
  const [abiertos, setAbiertos] = useState<Set<string>>(new Set());
  const [dias, setDias] = useState<Record<string, Registro[] | 'cargando'>>({});

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      setDatos(await horasApi.consulta({
        desde, hasta,
        client_id: fCliente || undefined,
        project_id: fProyecto || undefined,
        user_id: fUsuario || undefined,
        solo_desfasados: soloDesfasados || undefined,
      }));
      setError('');
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'No se pudo hacer la consulta.');
      setDatos(null);
    }
    setCargando(false);
  }, [desde, hasta, fCliente, fProyecto, fUsuario, soloDesfasados]);

  useEffect(() => { cargar(); }, [cargar]);

  useEffect(() => {
    clientsAPI.list()
      .then((c: Simple[]) => setClientes((c || []).filter((x) => x.is_active !== false)))
      .catch(() => { /* el filtro se queda vacío; la consulta sigue funcionando */ });
    usersAPI.list()
      .then((us: any[]) => setUsuarios((us || []).map((u) => ({
        id: u.id, nombre: u.full_name || u.username,
      }))))
      .catch(() => { /* solo el admin puede listar usuarios (§8) */ });
  }, []);

  // El selector de proyecto se acota al cliente elegido, como en el popup de registro.
  useEffect(() => {
    horasApi.listarProyectos(fCliente ? { client_id: fCliente } : undefined)
      .then(setProyectos).catch(() => setProyectos([]));
    setFProyecto('');
  }, [fCliente]);

  const alternar = (pid: string) => {
    setAbiertos((prev) => {
      const s = new Set(prev);
      if (s.has(pid)) s.delete(pid); else s.add(pid);
      return s;
    });
  };

  /** H-D33: los días de esa persona en ese proyecto, pedidos al desplegarla. */
  const verDias = async (pid: string, uid: string) => {
    const clave = `${pid}|${uid}`;
    if (dias[clave]) {
      setDias((d) => { const c = { ...d }; delete c[clave]; return c; });
      return;
    }
    setDias((d) => ({ ...d, [clave]: 'cargando' }));
    try {
      const filas = await horasApi.diasDeConsulta(pid, desde, hasta, uid);
      setDias((d) => ({ ...d, [clave]: filas }));
    } catch {
      setDias((d) => { const c = { ...d }; delete c[clave]; return c; });
      setError('No se pudieron cargar los días de esa persona.');
    }
  };

  const campo = 'px-4 py-3 border-2 border-gray-300 rounded-xl text-lg';
  const rotulo = 'block text-base text-gray-600 mb-1';
  const proyectosVisibles = datos?.projects || [];

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-4xl font-bold text-gray-800">Consulta de proyectos</h1>
        <p className="text-lg text-gray-500 mt-1">
          Quién ha registrado y cuántas horas, con lo consumido frente a lo estimado.
        </p>
      </div>

      {/* ---------- Filtros ---------- */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 mb-6">
        <div className="flex flex-wrap gap-4 items-end">
          <label className="block">
            <span className={rotulo}>Desde</span>
            <input type="date" value={desde} onChange={(e) => e.target.value && setDesde(e.target.value)}
              data-testid="filtro-desde" className={campo} />
          </label>
          <label className="block">
            <span className={rotulo}>Hasta</span>
            <input type="date" value={hasta} onChange={(e) => e.target.value && setHasta(e.target.value)}
              data-testid="filtro-hasta" className={campo} />
          </label>
          <label className="block">
            <span className={rotulo}>Cliente</span>
            <select value={fCliente} onChange={(e) => setFCliente(e.target.value)}
              data-testid="filtro-cliente" className={campo}>
              <option value="">Todos</option>
              {clientes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label className="block">
            <span className={rotulo}>Proyecto</span>
            <select value={fProyecto} onChange={(e) => setFProyecto(e.target.value)}
              data-testid="filtro-proyecto" className={campo}>
              <option value="">Todos</option>
              {proyectos.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <label className="block">
            <span className={rotulo}>Persona</span>
            <select value={fUsuario} onChange={(e) => setFUsuario(e.target.value)}
              data-testid="filtro-persona" className={campo}>
              <option value="">Todas</option>
              {usuarios.map((u) => <option key={u.id} value={u.id}>{u.nombre}</option>)}
            </select>
          </label>
        </div>
      </div>

      {error && (
        <div className="mb-4 flex items-start gap-2 p-4 rounded-xl bg-red-50 border border-red-200 text-red-800">
          <AlertTriangle className="w-5 h-5 mt-0.5 flex-shrink-0" />
          <span className="text-base" data-testid="error-consulta">{error}</span>
        </div>
      )}

      {/* §5.1: el aviso de arriba con su filtro. */}
      {datos && (
        <AvisoDesfasados cuantos={datos.overrun_count} activo={soloDesfasados}
          onAlternar={() => setSoloDesfasados((v) => !v)} />
      )}

      {/* ---------- Totales del rango ---------- */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        {([
          ['Horas del rango', horas(datos?.total_hours ?? 0), 'border-emerald-500'],
          ['De ellas, extra', horas(datos?.total_overtime ?? 0), 'border-indigo-500'],
          ['Proyectos', String(datos?.projects_count ?? 0), 'border-gray-300'],
          ['Personas', String(datos?.people_count ?? 0), 'border-gray-300'],
        ] as [string, string, string][]).map(([etiqueta, valor, borde]) => (
          <div key={etiqueta}
            className={`bg-white rounded-xl p-4 border-l-4 ${borde} border border-gray-200 shadow-sm`}>
            <p className="text-sm text-gray-500 uppercase">{etiqueta}</p>
            <p className="text-2xl font-bold text-gray-800 mt-1 tabular-nums"
              data-testid={`total-${etiqueta}`}>{valor}</p>
          </div>
        ))}
      </div>

      {/* ---------- La tabla ---------- */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
        {cargando ? (
          <div className="py-12 text-center text-gray-400 text-lg">Consultando…</div>
        ) : proyectosVisibles.length === 0 ? (
          <div className="py-12 text-center text-gray-400 text-lg" data-testid="consulta-vacia">
            <Search className="w-8 h-8 mx-auto mb-2 opacity-40" />
            No hay horas registradas con estos filtros.
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr className="text-sm uppercase text-gray-500">
                <th className="py-3 px-4 text-left w-10"></th>
                <th className="py-3 px-4 text-left">Cliente y proyecto</th>
                <th className="py-3 px-4 text-right w-32">En el rango</th>
                <th className="py-3 px-4 text-right w-32">Estimadas</th>
                <th className="py-3 px-4 text-right w-32">Consumidas</th>
                <th className="py-3 px-4 text-right w-32">Restantes</th>
                <th className="py-3 px-4 text-left w-64">Consumo</th>
              </tr>
            </thead>
            <tbody data-testid="tabla-consulta">
              {proyectosVisibles.map((p) => (
                <FilaProyecto key={p.project_id} p={p}
                  abierto={abiertos.has(p.project_id)}
                  onAlternar={() => alternar(p.project_id)}
                  dias={dias} onVerDias={verDias} />
              ))}
            </tbody>
          </table>
        )}
      </div>

      {datos && proyectosVisibles.length > 0 && (
        <p className="mt-3 text-base text-gray-500">
          Del {fechaLarga(datos.desde)} al {fechaLarga(datos.hasta)}.
          Las horas <strong>consumidas</strong> y el estado de desfase son de todo el
          proyecto, no solo del rango consultado.
        </p>
      )}
    </div>
  );
}

/** Una fila de proyecto y, si está desplegada, su gente y sus días. */
function FilaProyecto({ p, abierto, onAlternar, dias, onVerDias }: {
  p: ConsultaProyecto;
  abierto: boolean;
  onAlternar: () => void;
  dias: Record<string, Registro[] | 'cargando'>;
  onVerDias: (pid: string, uid: string) => void;
}) {
  const desfasado = p.overrun_status === 'desfasado';
  return (
    <>
      <tr data-testid="fila-proyecto" data-proyecto={p.project_name}
        data-desfase={p.overrun_status} data-abierto={abierto ? 'si' : 'no'}
        onClick={onAlternar}
        className={`border-b border-gray-100 cursor-pointer hover:bg-amber-50/50 ${
          desfasado ? 'bg-red-50/60' : ''}`}>
        <td className="py-3 px-4">
          <button onClick={(e) => { e.stopPropagation(); onAlternar(); }}
            aria-label={abierto ? `Plegar ${p.project_name}` : `Ampliar ${p.project_name}`}
            data-testid="ampliar-proyecto"
            className="p-3 -m-1 text-gray-500 hover:text-gray-900 rounded-lg">
            {abierto ? <ChevronDown className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
          </button>
        </td>
        <td className="py-3 px-4">
          <div className="text-lg font-semibold text-gray-800">{p.project_name}</div>
          <div className="text-base text-gray-500">
            {p.client_name}
            {p.status === 'cerrado' && (
              <span className="ml-2 px-2 py-0.5 text-xs rounded bg-gray-200 text-gray-600">cerrado</span>
            )}
          </div>
        </td>
        <td className="py-3 px-4 text-right">
          <div className="text-lg font-bold tabular-nums text-gray-800" data-testid="horas-rango">
            {horas(p.hours_in_range)}
          </div>
          {parseFloat(String(p.overtime_in_range)) > 0 && (
            <div className="flex items-center justify-end gap-1 text-sm text-indigo-700">
              <Zap className="w-3.5 h-3.5" />{horas(p.overtime_in_range)} extra
            </div>
          )}
        </td>
        <td className="py-3 px-4 text-right text-lg tabular-nums text-gray-600">
          {horas(p.estimated_hours)}
        </td>
        <td className="py-3 px-4 text-right text-lg tabular-nums text-gray-600">
          {horas(p.consumed_hours)}
        </td>
        <td className={`py-3 px-4 text-right text-lg tabular-nums font-semibold ${
          desfasado ? 'text-red-600' : 'text-gray-700'}`}>
          {horas(p.remaining_hours)}
        </td>
        <td className="py-3 px-4">
          <BarraConsumo dato={p} />
          <div className="mt-1"><AvisoDesfase dato={p} /></div>
        </td>
      </tr>

      {abierto && p.people.map((persona) => (
        <FilaPersona key={persona.user_id} p={p} persona={persona}
          dias={dias[`${p.project_id}|${persona.user_id}`]}
          onVerDias={() => onVerDias(p.project_id, persona.user_id)} />
      ))}
    </>
  );
}

/** Una persona dentro del proyecto y, desplegada, sus días (H-D33). */
function FilaPersona({ p, persona, dias, onVerDias }: {
  p: ConsultaProyecto;
  persona: ConsultaPersona;
  dias: Registro[] | 'cargando' | undefined;
  onVerDias: () => void;
}) {
  const abierta = dias !== undefined;
  return (
    <>
      <tr data-testid="fila-persona" data-persona={persona.user_name}
        onClick={onVerDias}
        className="border-b border-gray-100 bg-gray-50/70 cursor-pointer hover:bg-gray-100">
        <td></td>
        <td className="py-2.5 px-4 pl-10">
          <div className="flex items-center gap-2">
            {abierta ? <ChevronDown className="w-4 h-4 text-gray-400" />
              : <ChevronRight className="w-4 h-4 text-gray-400" />}
            <span className="text-base text-gray-700">{persona.user_name}</span>
            <span className="text-sm text-gray-400">
              {persona.entries_count} registro{persona.entries_count === 1 ? '' : 's'}
            </span>
          </div>
        </td>
        <td className="py-2.5 px-4 text-right text-base tabular-nums font-semibold text-gray-700"
          data-testid="horas-persona">
          {horas(persona.hours)}
        </td>
        <td colSpan={4} className="py-2.5 px-4 text-base text-gray-500">
          {horas(persona.billable_hours)} h facturables
          {parseFloat(String(persona.overtime_hours)) > 0
            && ` · ${horas(persona.overtime_hours)} h extra`}
        </td>
      </tr>

      {dias === 'cargando' && (
        <tr><td colSpan={7} className="py-4 text-center text-gray-400 text-base">
          <Loader2 className="w-5 h-5 animate-spin inline" /> Cargando los días…
        </td></tr>
      )}

      {Array.isArray(dias) && (
        <tr data-testid="dias-persona" data-clave={`${p.project_id}|${persona.user_id}`}>
          <td></td>
          <td colSpan={6} className="py-3 px-4 pl-10 pb-5">
            <table className="w-full bg-white border border-gray-200 rounded-xl overflow-hidden">
              <thead className="bg-gray-100">
                <tr className="text-xs uppercase text-gray-500 text-left">
                  <th className="py-2 px-3 w-56">Día</th>
                  <th className="py-2 px-3">Actividad</th>
                  <th className="py-2 px-3 text-right w-24">Horas</th>
                  <th className="py-2 px-3 w-44">Cobro</th>
                  <th className="py-2 px-3">Observaciones</th>
                </tr>
              </thead>
              <tbody>
                {dias.length === 0 && (
                  <tr><td colSpan={5} className="py-4 px-3 text-gray-400 text-base">
                    Sin registros en el rango.
                  </td></tr>
                )}
                {dias.map((d) => (
                  <tr key={d.id} data-testid="dia-de-consulta"
                    className={`border-t border-gray-100 ${d.over_estimate ? 'bg-amber-50/70' : ''}`}>
                    <td className="py-2 px-3 text-base text-gray-700 capitalize">{fechaLarga(d.date)}</td>
                    <td className="py-2 px-3 text-base text-gray-700">{d.activity_name}</td>
                    <td className="py-2 px-3 text-right text-base font-semibold tabular-nums text-gray-800">
                      {horas(d.hours)}
                    </td>
                    <td className="py-2 px-3">
                      <div className="flex gap-1.5 flex-wrap">
                        <span className={`px-2 py-0.5 text-xs rounded ${d.billable
                          ? 'bg-emerald-100 text-emerald-800' : 'bg-gray-100 text-gray-600'}`}>
                          {d.billable ? 'facturable' : 'no facturable'}
                        </span>
                        {d.overtime && <span className="px-2 py-0.5 text-xs rounded bg-indigo-100 text-indigo-800">extra</span>}
                        {d.over_estimate && (
                          <span className="px-2 py-0.5 text-xs rounded bg-amber-200 text-amber-900"
                            data-testid="marca-desfase">desfase</span>
                        )}
                      </div>
                    </td>
                    <td className="py-2 px-3 text-base text-gray-500">{d.notes || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </td>
        </tr>
      )}
    </>
  );
}
