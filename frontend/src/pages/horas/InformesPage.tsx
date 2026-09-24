/**
 * El informe de horas (ETAPA H5.5, especificación v1.2 §7).
 *
 * Cuatro pestañas, un solo juego de filtros. Las tres pestañas de tablas leen
 * `/time/informe` —los mismos datos que el documento— y la de **vista previa
 * enseña el documento real** (H-D57): en modo HTML, el HTML que genera el
 * servidor; en modo PDF, el PDF. Aquí no se maqueta nada del informe, porque una
 * previa maquetada aparte acaba mintiendo en cuanto una de las dos cambia.
 *
 * Los archivos se piden con axios y se enseñan desde un blob, no con un
 * `<iframe src=…>`: así la cookie de sesión viaja siempre, sin depender de cómo
 * trate el navegador un marco de otro origen.
 *
 * Regla 16: todos los hooks antes de cualquier return.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle, FileSpreadsheet, FileText, Loader2, Printer, RefreshCw,
} from 'lucide-react';
import {
  Descarga, FiltrosInforme, Informe, SECCIONES_INFORME,
  fechaLarga, horas, horasApi, hoyISO, mensajeDeError,
} from '../../api/horasApi';
// ETAPA H8 (H-D103): el estado, con su color, tambien en la previa.
import ChipEstado from '../../components/horas/EstadoProyecto';
import { clientsAPI, usersAPI } from '../../services/api';

interface Simple { id: string; name: string; is_active?: boolean }

const PESTANAS = [
  { clave: 'previa', titulo: 'Vista previa' },
  { clave: 'proyectos', titulo: 'Actividades por proyecto' },
  { clave: 'mensual', titulo: 'Mensual por persona' },
  { clave: 'ocupacion', titulo: 'Ocupación y facturación' },
] as const;

/** El primer y el último día del mes en curso, sin pasar por UTC. */
const mesEnCurso = (): [string, string] => {
  const hoy = hoyISO();
  const [a, m] = hoy.split('-').map(Number);
  const ultimo = new Date(a, m, 0).getDate();
  return [`${hoy.slice(0, 7)}-01`, `${hoy.slice(0, 7)}-${String(ultimo).padStart(2, '0')}`];
};

const pctNum = (v: string | number) => Math.round(parseFloat(String(v)) || 0);

export default function InformesPage() {
  const [inicio, fin] = mesEnCurso();
  const [desde, setDesde] = useState(inicio);
  const [hasta, setHasta] = useState(fin);
  const [personas, setPersonas] = useState<string[]>([]);
  const [fCliente, setFCliente] = useState('');
  const [fProyecto, setFProyecto] = useState('');
  const [soloFacturables, setSoloFacturables] = useState(false);
  // H-D74: a quien va dirigido. Vacio = el que trae el backend por defecto.
  const [dirigidoA, setDirigidoA] = useState('');
  const [secciones, setSecciones] = useState<string[]>(
    SECCIONES_INFORME.map((s) => s.clave));

  const [clientes, setClientes] = useState<Simple[]>([]);
  const [usuarios, setUsuarios] = useState<{ id: string; nombre: string }[]>([]);
  const [proyectos, setProyectos] = useState<{ id: string; name: string }[]>([]);

  const [datos, setDatos] = useState<Informe | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');

  const [pestana, setPestana] = useState<string>('previa');
  const [modo, setModo] = useState<'html' | 'pdf'>('html');
  const [previa, setPrevia] = useState<{ url: string; paginas?: number } | null>(null);
  const [generando, setGenerando] = useState(false);
  const [pagina, setPagina] = useState(1);
  const [bajando, setBajando] = useState('');
  const urlAnterior = useRef<string>('');

  const filtros: FiltrosInforme = useMemo(() => ({
    desde, hasta,
    user_id: personas.length ? personas : undefined,
    client_id: fCliente || undefined,
    project_id: fProyecto || undefined,
    solo_facturables: soloFacturables || undefined,
    // H-D74: si se deja vacío, el backend pone el destinatario por defecto.
    dirigido_a: dirigidoA.trim() || undefined,
  }), [desde, hasta, personas, fCliente, fProyecto, soloFacturables, dirigidoA]);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      setDatos(await horasApi.informe(filtros));
      setError('');
    } catch (e: any) {
      setError(mensajeDeError(e, 'No se pudo generar el informe.'));
      setDatos(null);
    }
    setCargando(false);
  }, [filtros]);

  useEffect(() => { cargar(); }, [cargar]);

  useEffect(() => {
    clientsAPI.list()
      .then((c: Simple[]) => setClientes((c || []).filter((x) => x.is_active !== false)))
      .catch(() => { /* el informe sigue saliendo sin el filtro */ });
    usersAPI.list()
      .then((us: any[]) => setUsuarios((us || []).map((u) => ({
        id: u.id, nombre: u.full_name || u.username,
      }))))
      .catch(() => { /* solo el admin lista usuarios (§8) */ });
  }, []);

  useEffect(() => {
    horasApi.listarProyectos(fCliente ? { client_id: fCliente } : undefined)
      .then((ps) => setProyectos(ps.map((p) => ({ id: p.id, name: p.name }))))
      .catch(() => setProyectos([]));
    setFProyecto('');
  }, [fCliente]);

  /** La previa se rehace cuando cambia algo que el documento enseña (H-D57). */
  const generarPrevia = useCallback(async () => {
    if (pestana !== 'previa') return;
    setGenerando(true); setError('');
    try {
      const d = await horasApi.documentoInforme(modo, filtros, { seccion: secciones });
      if (urlAnterior.current) URL.revokeObjectURL(urlAnterior.current);
      const url = URL.createObjectURL(d.blob);
      urlAnterior.current = url;
      setPrevia({ url, paginas: d.paginas });
      setPagina(1);
    } catch (e: any) {
      setError(mensajeDeError(e, 'No se pudo generar la vista previa.'));
      setPrevia(null);
    }
    setGenerando(false);
  }, [pestana, modo, filtros, secciones]);

  useEffect(() => { generarPrevia(); }, [generarPrevia]);
  useEffect(() => () => {
    if (urlAnterior.current) URL.revokeObjectURL(urlAnterior.current);
  }, []);

  const descargar = async (formato: 'html' | 'pdf' | 'csv') => {
    setBajando(formato); setError('');
    try {
      const d: Descarga = await horasApi.documentoInforme(formato, filtros, {
        seccion: formato === 'csv' ? undefined : secciones,
        descargar: true,
      });
      const url = URL.createObjectURL(d.blob);
      const a = document.createElement('a');
      a.href = url; a.download = d.nombre;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setError(mensajeDeError(e, 'No se pudo descargar el archivo.'));
    }
    setBajando('');
  };

  const alternarSeccion = (clave: string) => {
    setSecciones((prev) => (prev.includes(clave)
      ? prev.filter((x) => x !== clave) : [...prev, clave]));
  };

  const alternarPersona = (id: string) => {
    setPersonas((prev) => (prev.includes(id)
      ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const campo = 'px-4 py-3 border-2 border-gray-300 rounded-xl text-lg';
  const rotulo = 'block text-base text-gray-600 mb-1';

  return (
    <div className="p-8 max-w-[1400px] mx-auto">
      <div className="mb-6">
        <h1 className="text-4xl font-bold text-gray-800">Informe de horas</h1>
        <p className="text-lg text-gray-500 mt-1">
          {datos ? `${datos.filtros.alcance} · ${datos.filtros.periodo}`
            : 'Elige el periodo y las personas.'}
        </p>
      </div>

      {error && (
        <div className="mb-4 flex items-start gap-2 p-4 rounded-xl bg-red-50 border border-red-200 text-red-800">
          <AlertTriangle className="w-5 h-5 mt-0.5 flex-shrink-0" />
          <span className="text-base" data-testid="error-informe">{error}</span>
        </div>
      )}

      {/* ---------- Filtros ---------- */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 mb-5">
        <div className="flex flex-wrap gap-4 items-end mb-4">
          <label className="block">
            <span className={rotulo}>Desde</span>
            <input type="date" value={desde} onChange={(e) => e.target.value && setDesde(e.target.value)}
              data-testid="inf-desde" className={campo} />
          </label>
          <label className="block">
            <span className={rotulo}>Hasta</span>
            <input type="date" value={hasta} onChange={(e) => e.target.value && setHasta(e.target.value)}
              data-testid="inf-hasta" className={campo} />
          </label>
          <label className="block">
            <span className={rotulo}>Cliente</span>
            <select value={fCliente} onChange={(e) => setFCliente(e.target.value)}
              data-testid="inf-cliente" className={campo}>
              <option value="">Todos</option>
              {clientes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label className="block">
            <span className={rotulo}>Proyecto</span>
            <select value={fProyecto} onChange={(e) => setFProyecto(e.target.value)}
              data-testid="inf-proyecto" className={campo}>
              <option value="">Todos</option>
              {proyectos.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <label className="flex items-center gap-2 py-3">
            <input type="checkbox" checked={soloFacturables} data-testid="inf-facturables"
              onChange={(e) => setSoloFacturables(e.target.checked)}
              className="w-5 h-5 accent-[#f5a623]" />
            <span className="text-lg text-gray-700">Solo facturables</span>
          </label>
          {/* H-D74: el destinatario de la portada. Vacío = el de siempre. */}
          <label className="block flex-1 min-w-[280px]">
            <span className={rotulo}>Dirigido a</span>
            <input type="text" value={dirigidoA} data-testid="inf-dirigido-a"
              onChange={(e) => setDirigidoA(e.target.value)}
              placeholder={datos?.filtros.dirigido_a || 'José Javier Rodríguez Santos · Delivery Manager'}
              className={`${campo} w-full`} />
          </label>
        </div>

        {/* H-D53: personas — una, varias o todas */}
        <fieldset className="mb-4">
          <legend className={rotulo}>Personas <span className="text-gray-400">
            (ninguna marcada = todo el equipo)</span></legend>
          <div className="flex flex-wrap gap-2" data-testid="inf-personas">
            {usuarios.map((u) => (
              <label key={u.id}
                className={`flex items-center gap-2 px-3 py-2.5 rounded-xl border-2 cursor-pointer text-base ${
                  personas.includes(u.id)
                    ? 'border-[#f5a623] bg-[#f5a623]/10 font-semibold'
                    : 'border-gray-300 text-gray-600 hover:bg-gray-50'}`}>
                <input type="checkbox" className="w-4 h-4 accent-[#f5a623]"
                  checked={personas.includes(u.id)}
                  onChange={() => alternarPersona(u.id)}
                  data-testid="inf-persona" data-nombre={u.nombre} />
                {u.nombre}
              </label>
            ))}
          </div>
        </fieldset>

        {/* H-D53: qué secciones entran */}
        <fieldset>
          <legend className={rotulo}>Secciones del documento</legend>
          <div className="flex flex-wrap gap-2" data-testid="inf-secciones">
            {SECCIONES_INFORME.map((s, i) => (
              <label key={s.clave}
                className={`flex items-center gap-2 px-3 py-2.5 rounded-xl border-2 cursor-pointer text-base ${
                  secciones.includes(s.clave)
                    ? 'border-indigo-400 bg-indigo-50 font-semibold'
                    : 'border-gray-300 text-gray-500 hover:bg-gray-50'}`}>
                <input type="checkbox" className="w-4 h-4 accent-indigo-500"
                  checked={secciones.includes(s.clave)}
                  onChange={() => alternarSeccion(s.clave)}
                  data-testid="inf-seccion" data-seccion={s.clave} />
                <span className="text-gray-400">{i + 1}</span> {s.titulo}
              </label>
            ))}
          </div>
        </fieldset>
      </div>

      {/* ---------- Descargas ---------- */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 mb-5
                      flex flex-wrap gap-4 items-end">
        {/* H-D69: ya no hay selector de orientación. La única sección que
            giraba la hoja salió del informe, así que el PDF va todo vertical. */}
        <div className="flex flex-wrap gap-3">
          {([
            ['html', 'HTML', <FileText key="h" className="w-5 h-5" />],
            ['pdf', 'PDF', <Printer key="p" className="w-5 h-5" />],
            ['csv', 'CSV', <FileSpreadsheet key="c" className="w-5 h-5" />],
          ] as [('html' | 'pdf' | 'csv'), string, JSX.Element][]).map(([f, t, icono]) => (
            <button key={f} onClick={() => descargar(f)} disabled={Boolean(bajando)}
              data-testid={`bajar-${f}`}
              className="flex items-center gap-2 px-6 py-3 bg-[#f5a623] text-[#0a1628] text-lg font-bold rounded-xl hover:bg-[#f7b84a] disabled:opacity-40">
              {bajando === f ? <Loader2 className="w-5 h-5 animate-spin" /> : icono}
              {t}
            </button>
          ))}
        </div>
        <p className="text-base text-gray-500 flex-1 min-w-[240px]">
          El PDF no lleva el detalle de registros salvo que marques su casilla.
        </p>
      </div>

      {/* ---------- Pestañas ---------- */}
      <div className="flex flex-wrap gap-1 mb-0" data-testid="inf-pestanas">
        {PESTANAS.map((p) => (
          <button key={p.clave} onClick={() => setPestana(p.clave)}
            data-testid="inf-pestana" data-pestana={p.clave}
            aria-pressed={pestana === p.clave}
            className={`px-5 py-3 text-lg font-semibold rounded-t-xl border-2 border-b-0 ${
              pestana === p.clave
                ? 'bg-white border-gray-200 text-gray-900'
                : 'bg-gray-100 border-transparent text-gray-500 hover:bg-gray-50'}`}>
            {p.titulo}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-b-2xl rounded-tr-2xl border border-gray-200 shadow-sm p-5">
        {cargando && !datos ? (
          <div className="py-12 text-center text-gray-400 text-lg">Generando el informe…</div>
        ) : !datos ? (
          <div className="py-12 text-center text-gray-400 text-lg">Sin datos.</div>
        ) : pestana === 'previa' ? (
          <Previa modo={modo} setModo={setModo} previa={previa} generando={generando}
            pagina={pagina} setPagina={setPagina} onRehacer={generarPrevia} />
        ) : pestana === 'proyectos' ? (
          <TablaProyectos d={datos} />
        ) : pestana === 'mensual' ? (
          <TablaMensual d={datos} />
        ) : (
          <TablaOcupacion d={datos} />
        )}
      </div>
    </div>
  );
}

/** H-D57: aquí NO se maqueta el informe; se enseña el documento tal cual. */
function Previa({ modo, setModo, previa, generando, pagina, setPagina, onRehacer }: {
  modo: 'html' | 'pdf';
  setModo: (m: 'html' | 'pdf') => void;
  previa: { url: string; paginas?: number } | null;
  generando: boolean;
  pagina: number;
  setPagina: (n: number) => void;
  onRehacer: () => void;
}) {
  const paginas = previa?.paginas || 0;
  const src = modo === 'pdf' && previa
    ? `${previa.url}#page=${pagina}&toolbar=1`
    : previa?.url;
  return (
    <div>
      <div className="flex flex-wrap gap-3 items-center mb-4">
        {(['html', 'pdf'] as const).map((m) => (
          <button key={m} onClick={() => setModo(m)} data-testid={`modo-${m}`}
            aria-pressed={modo === m}
            className={`px-5 py-3 text-lg font-semibold rounded-xl border-2 ${
              modo === m ? 'bg-[#0a1628] text-white border-[#0a1628]'
                : 'border-gray-300 text-gray-600 hover:bg-gray-50'}`}>
            {m.toUpperCase()}
          </button>
        ))}
        <button onClick={onRehacer} disabled={generando} data-testid="rehacer-previa"
          className="flex items-center gap-2 px-5 py-3 text-lg font-semibold rounded-xl border-2 border-gray-300 hover:bg-gray-50 disabled:opacity-40">
          {generando ? <Loader2 className="w-5 h-5 animate-spin" />
            : <RefreshCw className="w-5 h-5" />}
          Rehacer
        </button>
        {modo === 'pdf' && paginas > 0 && (
          <div className="flex items-center gap-2" data-testid="nav-paginas">
            <button onClick={() => setPagina(Math.max(1, pagina - 1))}
              disabled={pagina <= 1} data-testid="pag-anterior"
              className="px-4 py-3 rounded-xl border-2 border-gray-300 disabled:opacity-40">‹</button>
            <span className="text-lg text-gray-700 tabular-nums" data-testid="pag-actual">
              Página {pagina} de {paginas}
            </span>
            <button onClick={() => setPagina(Math.min(paginas, pagina + 1))}
              disabled={pagina >= paginas} data-testid="pag-siguiente"
              className="px-4 py-3 rounded-xl border-2 border-gray-300 disabled:opacity-40">›</button>
          </div>
        )}
        <span className="text-base text-gray-500">
          Esto es el documento que se descarga, no una maqueta aparte.
        </span>
      </div>

      {generando && !previa ? (
        <div className="py-16 text-center text-gray-400 text-lg">Generando el documento…</div>
      ) : previa ? (
        <iframe key={src} src={src} title="Vista previa del informe"
          data-testid="previa-marco"
          className="w-full h-[78vh] border border-gray-200 rounded-xl bg-white" />
      ) : (
        <div className="py-16 text-center text-gray-400 text-lg">Sin vista previa.</div>
      )}
    </div>
  );
}

function Cabecera({ cols }: { cols: (string | JSX.Element)[] }) {
  return (
    <thead className="bg-gray-50 border-b border-gray-200">
      <tr className="text-sm uppercase text-gray-500">
        {cols.map((c, i) => (
          <th key={i} className={`py-3 px-4 ${i === 0 ? 'text-left' : 'text-right'}`}>{c}</th>
        ))}
      </tr>
    </thead>
  );
}

function TablaProyectos({ d }: { d: Informe }) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-gray-800 mb-3">Consumido frente a estimado</h2>
        <table className="w-full" data-testid="tabla-inf-proyectos">
          {/* H-D102: en el INFORME queda una sola columna de estado, la última.
              El consumo sale de aquí. En las pantallas de Proyectos y Consulta
              siguen las dos (H-D105): el informe se lee de un vistazo y sin
              poder preguntar. */}
          <Cabecera cols={['Cliente y proyecto', 'En el periodo', 'Estimadas',
                           'Consumidas', 'Restantes', 'Estado']} />
          <tbody>
            {d.proyectos.map((p) => (
              <tr key={p.project_id} className="border-b border-gray-100"
                data-proyecto={p.project_name}>
                <td className="py-3 px-4">
                  <div className="text-lg font-semibold text-gray-800">{p.project_name}</div>
                  <div className="text-base text-gray-500">{p.client_name}</div>
                </td>
                <td className="py-3 px-4 text-right text-lg tabular-nums">{horas(p.hours_in_range)}</td>
                <td className="py-3 px-4 text-right text-lg tabular-nums text-gray-600">{horas(p.estimated_hours)}</td>
                <td className="py-3 px-4 text-right text-lg tabular-nums text-gray-600">{horas(p.consumed_hours)}</td>
                {/* H-D106: sin la columna de consumo, el desfase se ve aquí. */}
                <td className={`py-3 px-4 text-right text-lg tabular-nums ${
                  parseFloat(String(p.remaining_hours)) < 0
                    ? 'font-bold text-red-700' : ''}`}>
                  {horas(p.remaining_hours)}
                </td>
                {/* H-D103: el estado, con su color, y el último. */}
                <td className="py-3 px-4 text-right" data-proyecto-estado={p.status}>
                  <ChipEstado estado={p.status} etiqueta={p.status_label} />
                </td>
              </tr>
            ))}
            {d.proyectos.length === 0 && (
              <tr><td colSpan={6} className="py-8 text-center text-gray-400 text-lg">
                Sin proyectos en el periodo.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div>
        <h2 className="text-xl font-bold text-gray-800 mb-3">En qué se fue el tiempo</h2>
        <table className="w-full" data-testid="tabla-inf-actividades">
          <Cabecera cols={['Actividad', 'Horas', '%']} />
          <tbody>
            {d.por_actividad.map((a) => (
              <tr key={a.name} className="border-b border-gray-100">
                <td className="py-3 px-4 text-lg text-gray-800">{a.name}</td>
                <td className="py-3 px-4 text-right text-lg tabular-nums">{horas(a.hours)}</td>
                <td className="py-3 px-4 text-right text-lg tabular-nums text-gray-600">
                  {pctNum(a.pct)} %
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const COLOR_ESTADO: Record<string, string> = {
  trabajado: 'bg-emerald-100', incompleto: 'bg-amber-100', festivo: 'bg-indigo-100',
  ausencia: 'bg-purple-100', finde: 'bg-gray-100', vacio: 'bg-white',
};

// ETAPA H8 (H-D85): los mismos hexadecimales del documento, para la casilla
// partida. Se usan solo ahí: una casilla entera sigue con su clase de Tailwind,
// y la diferencia entre `bg-emerald-100` y `#dcfce7` no se aprecia al lado.
const FONDO_MAPA: Record<string, string> = {
  trabajado: '#dcfce7', incompleto: '#fef3c7', festivo: '#e0e7ff',
  ausencia: '#f3e8ff', finde: '#f3f4f6', vacio: '#ffffff',
};
const FONDO_EXTRA = '#bfdbfe';

function TablaMensual({ d }: { d: Informe }) {
  return (
    <div>
      <h2 className="text-xl font-bold text-gray-800 mb-3">Mapa del mes</h2>
      <div className="overflow-x-auto">
        <table className="w-full" data-testid="tabla-inf-mapa">
          <thead className="bg-gray-50">
            <tr>
              <th className="py-2 px-3 text-left text-sm uppercase text-gray-500">Persona</th>
              {d.dias.map((f) => (
                <th key={f} className="py-2 px-0.5 text-center text-xs text-gray-500">
                  {Number(f.slice(8))}
                </th>
              ))}
              <th className="py-2 px-3 text-right text-sm uppercase text-gray-500">Total</th>
            </tr>
          </thead>
          <tbody>
            {d.mapa.map((p) => (
              <tr key={p.user_id} data-persona={p.user_name}>
                <td className="py-2 px-3 text-base text-gray-800 whitespace-nowrap">{p.user_name}</td>
                {p.estados.map((e, i) => {
                  // ETAPA H8 (H-D85): un día con horas extra se pinta partido,
                  // abajo las ordinarias y arriba las extra, en proporción. Los
                  // colores son los mismos hexadecimales del documento
                  // (`docs/diseno-informe-horas.md`), no una aproximación.
                  const total = parseFloat(String(p.por_dia[i])) || 0;
                  const extra = parseFloat(String(p.extra_por_dia?.[i] ?? 0)) || 0;
                  const parte = extra > 0 && total > 0
                    ? Math.round(((total - extra) / total) * 1000) / 10 : null;
                  return (
                    <td key={i} data-estado={e}
                      data-extra={extra > 0 ? String(extra) : undefined}
                      style={parte === null ? undefined : {
                        // La forma clásica, el mismo porcentaje repetido: es la
                        // que entiende WeasyPrint (la de doble posición la tira
                        // sin avisar), y así pantalla y papel comparten sintaxis.
                        background: `linear-gradient(to top,${FONDO_MAPA[e] || FONDO_MAPA.trabajado}`
                          + ` ${parte}%,${FONDO_EXTRA} ${parte}%)`,
                      }}
                      className={`py-2 px-0.5 text-center text-xs tabular-nums border border-white ${
                        parte === null ? (COLOR_ESTADO[e] || '') : ''}`}>
                      {total > 0 ? horas(p.por_dia[i]).replace(' h', '') : ''}
                    </td>
                  );
                })}
                <td className="py-2 px-3 text-right text-base font-semibold tabular-nums">
                  {horas(p.total_hours)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 className="text-xl font-bold text-gray-800 mt-6 mb-3">
        Días sin registrar ({d.pendientes.length})
      </h2>
      {d.pendientes.length === 0 ? (
        <p className="text-lg text-gray-400 py-4">No hay días sin registrar en el periodo.</p>
      ) : (
        <table className="w-full" data-testid="tabla-inf-pendientes">
          <Cabecera cols={['Persona', 'Día', 'Jornada', 'Registradas', 'Faltan']} />
          <tbody>
            {d.pendientes.map((p, i) => (
              <tr key={i} className="border-b border-gray-100" data-persona={p.user_name}>
                <td className="py-2.5 px-4 text-base text-gray-800">{p.user_name}</td>
                <td className="py-2.5 px-4 text-right text-base capitalize">{fechaLarga(p.date)}</td>
                <td className="py-2.5 px-4 text-right text-base tabular-nums">{horas(p.expected_hours)}</td>
                <td className="py-2.5 px-4 text-right text-base tabular-nums">{horas(p.ordinary_hours)}</td>
                <td className="py-2.5 px-4 text-right text-base tabular-nums font-semibold text-red-700">
                  {horas(p.missing_hours)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function TablaOcupacion({ d }: { d: Informe }) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-gray-800 mb-3">Ocupación por persona</h2>
        <table className="w-full" data-testid="tabla-inf-personas">
          <Cabecera cols={['Persona', 'Jornada', 'Ordinarias', 'Extra', 'Facturables',
                           'Ocupación', 'Sin registrar']} />
          <tbody>
            {d.personas.map((p) => (
              <tr key={p.user_id} className="border-b border-gray-100" data-persona={p.user_name}>
                <td className="py-3 px-4 text-lg text-gray-800">{p.user_name}</td>
                <td className="py-3 px-4 text-right text-lg tabular-nums text-gray-600">{horas(p.expected_hours)}</td>
                <td className="py-3 px-4 text-right text-lg tabular-nums">{horas(p.ordinary_hours)}</td>
                <td className="py-3 px-4 text-right text-lg tabular-nums text-indigo-700">{horas(p.overtime_hours)}</td>
                <td className="py-3 px-4 text-right text-lg tabular-nums">{horas(p.billable_hours)}</td>
                <td className="py-3 px-4 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <div className="w-24 h-2.5 bg-gray-200 rounded-full overflow-hidden">
                      <div className="h-full bg-indigo-500 rounded-full"
                        style={{ width: `${Math.min(pctNum(p.occupancy_pct), 100)}%` }} />
                    </div>
                    <span className="tabular-nums font-semibold">{pctNum(p.occupancy_pct)} %</span>
                  </div>
                </td>
                <td className="py-3 px-4 text-right text-lg tabular-nums">{p.pending_days}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div>
        <h2 className="text-xl font-bold text-gray-800 mb-3">
          Facturable frente a no facturable
        </h2>
        <table className="w-full" data-testid="tabla-inf-facturacion">
          <Cabecera cols={['Cliente', 'Facturable', 'No facturable', 'Total', '% facturable']} />
          <tbody>
            {d.facturacion.map((f) => (
              <tr key={f.client_name} className="border-b border-gray-100" data-cliente={f.client_name}>
                <td className="py-3 px-4 text-lg text-gray-800">{f.client_name}</td>
                <td className="py-3 px-4 text-right text-lg tabular-nums text-emerald-700">{horas(f.billable_hours)}</td>
                <td className="py-3 px-4 text-right text-lg tabular-nums text-gray-500">{horas(f.non_billable_hours)}</td>
                <td className="py-3 px-4 text-right text-lg tabular-nums">{horas(f.total_hours)}</td>
                <td className="py-3 px-4 text-right text-lg tabular-nums font-semibold">{pctNum(f.billable_pct)} %</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
