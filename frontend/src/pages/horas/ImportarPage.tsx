/**
 * Importación del archivo de horas (ETAPA H3.5, especificación §6).
 *
 * Tres estados y en este orden, sin atajos:
 *
 *     elegir archivo  →  VISTA PREVIA  →  confirmar  →  resumen
 *
 * **Nada se escribe hasta confirmar** (§6.2.5). La vista previa la calcula el
 * backend con el mismo código que después escribe, así que lo que se ve aquí es
 * exactamente lo que va a pasar, no una aproximación.
 *
 * Regla 16: todos los hooks antes de cualquier return.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle, ArrowRight, Check, FileSpreadsheet, Loader2, Plus, Upload,
} from 'lucide-react';
import {
  ActividadNueva, FilaImportacion, ResumenImportacion, VistaPrevia,
  fechaLarga, horas, horasApi, mensajeDeError,
} from '../../api/horasApi';
import BorrarPeriodo from '../../components/horas/BorrarPeriodo';
import ImportarProyectos from '../../components/horas/ImportarProyectos';
import { usersAPI } from '../../services/api';
import { useAuth } from '../../context/AuthContext';

export default function ImportarPage() {
  const { user } = useAuth();
  const navegar = useNavigate();
  const esAdmin = user?.role === 'admin';

  const [usuarios, setUsuarios] = useState<{ id: string; nombre: string }[]>([]);
  const [usuarioSel, setUsuarioSel] = useState('');
  const [archivo, setArchivo] = useState<File | null>(null);
  const [previa, setPrevia] = useState<VistaPrevia | null>(null);
  const [resumen, setResumen] = useState<ResumenImportacion | null>(null);
  const [analizando, setAnalizando] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [error, setError] = useState('');
  // ETAPA H8.5b (H-D94): «registros» o «proyectos».
  const [pestana, setPestana] = useState<string>('registros');
  const entrada = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!esAdmin) return;
    usersAPI.list()
      .then((us: any[]) => setUsuarios((us || []).map((u) => ({
        id: u.id, nombre: u.full_name || u.username,
      }))))
      .catch(() => { /* sin lista, se importa para uno mismo */ });
  }, [esAdmin]);

  const objetivo = usuarioSel || user?.id || '';
  const paraOtro = esAdmin && usuarioSel && usuarioSel !== user?.id ? usuarioSel : undefined;

  const entran = useMemo(
    () => (previa ? previa.nuevas.length + previa.actualizadas.length : 0),
    [previa],
  );

  const elegir = (f: File | null) => {
    setArchivo(f); setPrevia(null); setResumen(null); setError('');
  };

  const analizar = async () => {
    if (!archivo) return;
    setAnalizando(true); setError(''); setResumen(null);
    try {
      setPrevia(await horasApi.vistaPreviaImportacion(archivo, paraOtro));
    } catch (e: any) {
      setError(mensajeDeError(e, 'No se pudo leer el archivo.'));
      setPrevia(null);
    }
    setAnalizando(false);
  };

  const confirmar = async () => {
    if (!archivo || !previa) return;
    setConfirmando(true); setError('');
    try {
      setResumen(await horasApi.confirmarImportacion(archivo, paraOtro));
      setPrevia(null);
    } catch (e: any) {
      setError(mensajeDeError(e, 'No se pudo completar la importación.'));
    }
    setConfirmando(false);
  };

  const empezar = () => {
    setArchivo(null); setPrevia(null); setResumen(null); setError('');
    if (entrada.current) entrada.current.value = '';
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-4xl font-bold text-gray-800">Importar</h1>
        <p className="text-lg text-gray-500 mt-1">
          Antes de guardar nada verás exactamente qué va a pasar.
        </p>
      </div>

      {/* ETAPA H8.5b (H-D94): dos importadores en la misma pantalla, cada uno en
          su pestaña. El orden es el de uso: primero los proyectos con sus
          estimaciones, y después las horas, que caen sobre ellos. */}
      <div className="flex gap-2 mb-6 border-b border-gray-200" data-testid="pestanas-importar">
        {([['registros', 'Registros de horas'],
           ['proyectos', 'Proyectos y estimaciones']] as [string, string][]).map(
          ([clave, titulo]) => (
            <button key={clave} onClick={() => setPestana(clave)}
              data-testid={`pestana-${clave}`}
              className={`px-5 py-3 text-lg font-semibold border-b-4 -mb-px ${
                pestana === clave
                  ? 'border-[#f5a623] text-gray-900'
                  : 'border-transparent text-gray-500 hover:text-gray-800'}`}>
              {titulo}
            </button>
          ))}
      </div>

      {pestana === 'proyectos' && <ImportarProyectos />}

      {pestana === 'registros' && (<>

      {error && (
        <div className="mb-4 flex items-start gap-2 p-4 rounded-xl bg-red-50 border border-red-200 text-red-800">
          <AlertTriangle className="w-5 h-5 mt-0.5 flex-shrink-0" />
          <span className="text-base" data-testid="error-importacion">{error}</span>
        </div>
      )}

      {/* ---------- 1. El archivo y la persona ---------- */}
      {!resumen && (
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 mb-6">
          <div className="flex flex-wrap gap-5 items-end">
            <label className="block">
              <span className="block text-base font-semibold text-gray-700 mb-1">
                Archivo (.xlsx)
              </span>
              <input ref={entrada} type="file" accept=".xlsx"
                onChange={(e) => elegir(e.target.files?.[0] || null)}
                data-testid="archivo"
                className="block text-lg file:mr-4 file:py-3 file:px-5 file:rounded-xl
                  file:border-0 file:text-lg file:font-bold file:bg-[#f5a623]
                  file:text-[#0a1628] hover:file:bg-[#f7b84a] file:cursor-pointer" />
            </label>

            {/* H-D39/H-D49: el archivo no trae persona; se elige aquí. */}
            <label className="block">
              <span className="block text-base font-semibold text-gray-700 mb-1">
                Las horas son de
              </span>
              <select value={objetivo} onChange={(e) => { setUsuarioSel(e.target.value); setPrevia(null); }}
                disabled={!esAdmin} data-testid="importar-persona"
                className="px-4 py-3 border-2 border-gray-300 rounded-xl text-lg disabled:bg-gray-100 disabled:text-gray-500">
                {(usuarios.length ? usuarios : [{
                  id: user?.id || '', nombre: user?.full_name || user?.username || 'Yo',
                }]).map((u) => <option key={u.id} value={u.id}>{u.nombre}</option>)}
              </select>
            </label>

            <button onClick={analizar} disabled={!archivo || analizando}
              data-testid="analizar"
              className="flex items-center gap-2 px-6 py-3 bg-[#0a1628] text-white text-lg font-bold rounded-xl hover:bg-[#16243d] disabled:opacity-40 disabled:cursor-not-allowed">
              {analizando ? <Loader2 className="w-5 h-5 animate-spin" /> : <Upload className="w-5 h-5" />}
              Ver qué va a pasar
            </button>
          </div>
          {archivo && (
            <p className="mt-3 text-base text-gray-500 flex items-center gap-2">
              <FileSpreadsheet className="w-5 h-5 text-emerald-600" />
              {archivo.name} · {Math.round(archivo.size / 1024)} KB
            </p>
          )}
        </div>
      )}

      {/* ---------- 2. La vista previa ---------- */}
      {previa && (
        <div data-testid="vista-previa">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
            {([
              ['Se crean', String(previa.nuevas.length), 'border-emerald-500'],
              ['Se actualizan', String(previa.actualizadas.length), 'border-indigo-500'],
              ['No se importan', String(previa.invalidas.length),
                previa.invalidas.length ? 'border-red-500' : 'border-gray-300'],
              ['Horas', horas(previa.total_horas), 'border-gray-300'],
            ] as [string, string, string][]).map(([etiqueta, valor, borde]) => (
              <div key={etiqueta}
                className={`bg-white rounded-xl p-4 border-l-4 ${borde} border border-gray-200 shadow-sm`}>
                <p className="text-sm text-gray-500 uppercase">{etiqueta}</p>
                <p className="text-2xl font-bold text-gray-800 mt-1 tabular-nums"
                  data-testid={`previa-${etiqueta}`}>{valor}</p>
              </div>
            ))}
          </div>

          <p className="text-base text-gray-500 mb-5">
            Hoja «{previa.sheet}»
            {previa.sheets.length > 1 && (
              <strong className="text-amber-700">
                {' '}— el libro trae {previa.sheets.length} hojas y se usa la primera
              </strong>
            )}
            {' · '}las horas se registran a nombre de <strong>{previa.user_name}</strong>.
          </p>

          {/* Lo que se va a crear (H-D36, H-D48) */}
          {(previa.clientes_a_crear.length > 0 || previa.proyectos_a_crear.length > 0
            || previa.actividades_a_crear.length > 0) && (
            <Seccion titulo="Se va a crear" testid="seccion-a-crear" color="amber">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
                <ListaNombres titulo="Clientes" nombres={previa.clientes_a_crear} testid="crear-clientes" />
                <ListaNombres titulo="Proyectos" testid="crear-proyectos"
                  nombres={previa.proyectos_a_crear.map((p) => `${p.project_name} (${p.client_name})`)} />
                <ListaNombres titulo="Actividades" nombres={previa.actividades_a_crear} testid="crear-actividades" />
              </div>
              {previa.proyectos_a_crear.length > 0 && (
                <p className="mt-4 text-base text-amber-900">
                  Los proyectos nuevos <strong>nacen sin horas estimadas</strong>. Al
                  terminar te doy el enlace de cada uno para que se las pongas.
                </p>
              )}
            </Seccion>
          )}

          {/* §4: las actividades que el catálogo no tenía */}
          <ActividadesNuevas actividades={previa.actividades_nuevas} />

          {/* Las que no entran (H-D40) */}
          {previa.invalidas.length > 0 && (
            <Seccion titulo={`No se importan (${previa.invalidas.length})`}
              testid="seccion-invalidas" color="red">
              <p className="text-base text-red-900 mb-3">
                El resto del archivo sí se importa: estas filas se quedan fuera y te
                dicen por qué.
              </p>
              <Tabla filas={previa.invalidas} conMotivo />
            </Seccion>
          )}

          {/* Las que se pasan de lo estimado (H-D38) */}
          {previa.desfasadas.length > 0 && (
            <Seccion titulo={`Quedan desfasadas (${previa.desfasadas.length})`}
              testid="seccion-desfasadas" color="amber">
              <p className="text-base text-amber-900 mb-3">
                Se importan igual: avisan, no bloquean (§4.2.4).
              </p>
              <Tabla filas={previa.desfasadas} conDesfase />
            </Seccion>
          )}

          {previa.actualizadas.length > 0 && (
            <Seccion titulo={`Se actualizan (${previa.actualizadas.length})`}
              testid="seccion-actualizadas" color="indigo">
              <p className="text-base text-gray-600 mb-3">
                Ya estaban importadas con el mismo Id: se corrigen, no se duplican.
              </p>
              <Tabla filas={previa.actualizadas} />
            </Seccion>
          )}

          {previa.nuevas.length > 0 && (
            <Seccion titulo={`Se crean (${previa.nuevas.length})`}
              testid="seccion-nuevas" color="emerald">
              <Tabla filas={previa.nuevas} />
            </Seccion>
          )}

          <div className="flex flex-wrap justify-end gap-3 mt-6">
            <button onClick={empezar} data-testid="cancelar-importacion"
              className="px-6 py-3 text-lg font-semibold rounded-xl border border-gray-300 text-gray-600 hover:bg-gray-50">
              Cancelar
            </button>
            <button onClick={confirmar} disabled={confirmando || entran === 0}
              data-testid="confirmar-importacion"
              className="flex items-center gap-2 px-6 py-3 bg-[#f5a623] text-[#0a1628] text-lg font-bold rounded-xl hover:bg-[#f7b84a] disabled:opacity-40 disabled:cursor-not-allowed">
              {confirmando ? <Loader2 className="w-5 h-5 animate-spin" /> : <Check className="w-5 h-5" />}
              Importar {entran} {entran === 1 ? 'fila' : 'filas'}
            </button>
          </div>
        </div>
      )}

      {/* ---------- 3. El resumen ---------- */}
      {resumen && (
        <div data-testid="resumen-importacion">
          <div className="flex items-center gap-2 p-5 rounded-2xl bg-emerald-50 border border-emerald-200 mb-6">
            <Check className="w-6 h-6 text-emerald-700 flex-shrink-0" />
            <span className="text-xl text-emerald-900">
              Importadas <strong>{horas(resumen.total_horas)} h</strong> a nombre
              de <strong>{resumen.user_name}</strong>:
              {' '}{resumen.creados} nuevas y {resumen.actualizados} actualizadas
              {resumen.omitidos > 0 && `, ${resumen.omitidos} sin importar`}.
            </span>
          </div>

          {resumen.proyectos_creados.length > 0 && (
            <Seccion titulo="Proyectos nuevos, sin horas estimadas"
              testid="proyectos-creados" color="amber">
              <p className="text-base text-amber-900 mb-3">
                Nacieron de la importación (§6.2.4). Ponles sus horas para que el
                aviso de desfase pueda funcionar.
              </p>
              <ul className="space-y-2">
                {resumen.proyectos_creados.map((p) => (
                  <li key={p.id}>
                    <button onClick={() => navegar('/horas/proyectos')}
                      data-testid="enlace-proyecto-creado" data-proyecto={p.name}
                      className="flex items-center gap-2 px-4 py-3 text-lg font-semibold text-[#0a1628] bg-white border-2 border-amber-300 rounded-xl hover:bg-amber-100 w-full text-left">
                      <Plus className="w-5 h-5 flex-shrink-0" />
                      <span className="flex-1">{p.name}</span>
                      <span className="text-base font-normal text-gray-500">{p.client_name}</span>
                      <ArrowRight className="w-5 h-5 flex-shrink-0" />
                    </button>
                  </li>
                ))}
              </ul>
            </Seccion>
          )}

          {(resumen.clientes_creados.length > 0 || resumen.actividades_creadas.length > 0) && (
            <Seccion titulo="También se crearon" testid="tambien-creados" color="indigo">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <ListaNombres titulo="Clientes" nombres={resumen.clientes_creados} testid="creados-clientes" />
                <ListaNombres titulo="Actividades" nombres={resumen.actividades_creadas} testid="creados-actividades" />
              </div>
            </Seccion>
          )}

          {/* §4: el mismo bloque de la previa, para que quede a la vista
              DESPUÉS de confirmar y no haya que acordarse de lo que decía. */}
          <ActividadesNuevas actividades={resumen.actividades_nuevas} yaCreadas />

          <div className="flex flex-wrap justify-end gap-3 mt-6">
            <button onClick={() => navegar('/horas/registro')} data-testid="ver-calendario"
              className="px-6 py-3 text-lg font-semibold rounded-xl border-2 border-gray-300 hover:bg-gray-50">
              Ver el calendario
            </button>
            <button onClick={empezar} data-testid="importar-otro"
              className="px-6 py-3 bg-[#f5a623] text-[#0a1628] text-lg font-bold rounded-xl hover:bg-[#f7b84a]">
              Importar otro archivo
            </button>
          </div>
        </div>
      )}

      </>)}

      {/* ETAPA H8.5 (§4.3): borrar un periodo. Va aquí porque el orden real de
          uso es borrar → cargar proyectos → cargar horas, y es donde se está.
          Fuera de las pestañas: vale para las dos. Solo admin, plegado por defecto. */}
      {esAdmin && <BorrarPeriodo />}
    </div>
  );
}

const COLORES = {
  amber: 'bg-amber-50 border-amber-200',
  red: 'bg-red-50 border-red-200',
  indigo: 'bg-indigo-50 border-indigo-200',
  emerald: 'bg-white border-gray-200',
} as const;

function Seccion({ titulo, testid, color, children }: {
  titulo: string; testid: string; color: keyof typeof COLORES; children: React.ReactNode;
}) {
  return (
    <div className={`rounded-2xl border p-5 mb-5 ${COLORES[color]}`} data-testid={testid}>
      <h2 className="text-xl font-bold text-gray-800 mb-3">{titulo}</h2>
      {children}
    </div>
  );
}

function ListaNombres({ titulo, nombres, testid }: {
  titulo: string; nombres: string[]; testid: string;
}) {
  return (
    <div data-testid={testid} data-cuantos={nombres.length}>
      <p className="text-sm text-gray-500 uppercase mb-1">{titulo} ({nombres.length})</p>
      {nombres.length === 0 ? (
        <p className="text-base text-gray-400">Ninguno</p>
      ) : (
        <ul className="space-y-1">
          {nombres.map((n) => (
            <li key={n} className="text-base text-gray-800">· {n}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

/**
 * §4 (carga real): las actividades que NO estaban en el catálogo.
 *
 * Bloque propio y no una línea más en «se va a crear», porque dice otra cosa:
 * aquello enumera nombres, esto avisa de que el archivo trae una actividad que
 * la tabla de sinónimos no conoce. Con el nombre a secas no se puede decidir;
 * con **las filas y las horas** sí: una desconocida con 40 horas repartidas en
 * 12 filas casi nunca es nueva, es una variante de escritura de una de las
 * ocho, y entonces lo que hay que hacer es añadir el sinónimo y volver a
 * importar, no confirmar.
 *
 * Se pinta igual en la vista previa y en el resumen, para que siga a la vista
 * después de confirmar.
 */
function ActividadesNuevas({ actividades, yaCreadas }: {
  actividades: ActividadNueva[]; yaCreadas?: boolean;
}) {
  if (actividades.length === 0) return null;
  return (
    <Seccion
      titulo={`Actividades nuevas que no estaban en el catálogo (${actividades.length})`}
      testid="actividades-nuevas" color="amber">
      <p className="text-base text-amber-900 mb-3">
        {yaCreadas
          ? 'Se crearon con el nombre que traía el archivo.'
          : 'Entran igual y se crean con el nombre que trae el archivo.'}{' '}
        Si alguna es en realidad una de las del catálogo escrita de otra manera,
        lo que falta es un <strong>sinónimo</strong>, no una actividad.
      </p>
      <ul className="space-y-2">
        {actividades.map((a) => (
          <li key={a.name} data-testid="actividad-nueva" data-nombre={a.name}
            data-filas={a.filas.length} data-horas={String(a.horas)}
            className="text-base text-gray-800">
            <strong>{a.name}</strong>
            {' — '}{horas(a.horas)} h en {a.filas.length}{' '}
            {a.filas.length === 1 ? 'fila' : 'filas'}
            {a.filas.length > 0 && (
              <span className="text-gray-500"> ({a.filas.join(', ')})</span>
            )}
          </li>
        ))}
      </ul>
    </Seccion>
  );
}

/** Las filas del archivo. Se enseñan enteras: es lo que hay que revisar antes de
 *  decir que sí, y esconderlas detrás de un contador no ayudaría a decidir. */
function Tabla({ filas, conMotivo = false, conDesfase = false }: {
  filas: FilaImportacion[]; conMotivo?: boolean; conDesfase?: boolean;
}) {
  return (
    <div className="overflow-x-auto bg-white rounded-xl border border-gray-200">
      <table className="w-full">
        <thead className="bg-gray-50">
          <tr className="text-xs uppercase text-gray-500 text-left">
            <th className="py-2 px-3 w-16">Fila</th>
            <th className="py-2 px-3 w-52">Día</th>
            <th className="py-2 px-3">Cliente y proyecto</th>
            <th className="py-2 px-3">Actividad</th>
            <th className="py-2 px-3 text-right w-24">Horas</th>
            {conMotivo && <th className="py-2 px-3 w-72">Por qué no entra</th>}
            {conDesfase && <th className="py-2 px-3 w-48">Desfase</th>}
            {!conMotivo && !conDesfase && <th className="py-2 px-3 w-44">Marcas</th>}
          </tr>
        </thead>
        <tbody>
          {filas.map((f) => (
            <tr key={f.numero} data-testid="fila-previa" data-fila={f.numero}
              data-accion={f.accion}
              className="border-t border-gray-100">
              <td className="py-2 px-3 text-base tabular-nums text-gray-500">{f.numero}</td>
              <td className="py-2 px-3 text-base text-gray-700 capitalize">
                {f.date ? fechaLarga(f.date) : <span className="text-red-600">sin fecha</span>}
              </td>
              <td className="py-2 px-3 text-base text-gray-800">
                {f.client_name} · <strong>{f.project_name}</strong>
                {(f.crea_cliente || f.crea_proyecto) && (
                  <span className="ml-2 px-2 py-0.5 text-xs rounded bg-amber-200 text-amber-900">
                    {f.crea_cliente && f.crea_proyecto ? 'cliente y proyecto nuevos'
                      : f.crea_cliente ? 'cliente nuevo' : 'proyecto nuevo'}
                  </span>
                )}
              </td>
              <td className="py-2 px-3 text-base text-gray-700">
                {f.activity_name}
                {f.crea_actividad && (
                  <span className="ml-2 px-2 py-0.5 text-xs rounded bg-amber-200 text-amber-900">nueva</span>
                )}
              </td>
              <td className="py-2 px-3 text-right text-base font-semibold tabular-nums text-gray-800">
                {f.hours === null || f.hours === undefined
                  ? <span className="text-red-600">—</span> : horas(f.hours)}
              </td>
              {conMotivo && (
                <td className="py-2 px-3 text-base text-red-800" data-testid="motivo">{f.motivo}</td>
              )}
              {conDesfase && (
                <td className="py-2 px-3">
                  <span className="px-3 py-1 rounded-full text-sm font-semibold bg-red-100 text-red-800"
                    data-testid="previa-desfase">{f.overrun_label}</span>
                </td>
              )}
              {!conMotivo && !conDesfase && (
                <td className="py-2 px-3">
                  <div className="flex gap-1.5 flex-wrap">
                    <span className={`px-2 py-0.5 text-xs rounded ${f.billable
                      ? 'bg-emerald-100 text-emerald-800' : 'bg-gray-100 text-gray-600'}`}>
                      {f.billable ? 'facturable' : 'no facturable'}
                    </span>
                    {f.overtime && <span className="px-2 py-0.5 text-xs rounded bg-indigo-100 text-indigo-800">extra</span>}
                    {f.cambia_de_persona && (
                      <span className="px-2 py-0.5 text-xs rounded bg-amber-200 text-amber-900"
                        data-testid="cambia-persona">cambia de persona</span>
                    )}
                  </div>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
