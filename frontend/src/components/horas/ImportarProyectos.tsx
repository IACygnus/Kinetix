/**
 * Importar proyectos, estados y estimaciones (ETAPA H8.5b, H-D94 a H-D101).
 *
 * Es la segunda pestaña de la pantalla de Importar. **La de registros no se
 * toca** (H-D94): esto es un componente aparte con su propio flujo, el mismo de
 * siempre y sin atajos:
 *
 *     elegir archivo  →  VISTA PREVIA  →  confirmar  →  resumen
 *
 * **Nada se escribe hasta confirmar** (H-D99), y la previa la calcula el backend
 * con el mismo código que después escribe.
 *
 * La previa enseña **un bloque por proyecto** con sus actividades juntas y
 * **cuánto suma el proyecto entero**, que es la cifra con la que se ve de un
 * vistazo si el Excel está bien.
 *
 * Regla 16: todos los hooks antes de cualquier return.
 */
import { useRef, useState } from 'react';
import {
  AlertTriangle, Check, Download, FileSpreadsheet, Loader2, Upload,
} from 'lucide-react';
import {
  ActividadNueva, ProyectoImportado, ResumenProyectos, VistaPreviaProyectos,
  horas, horasApi, mensajeDeError,
} from '../../api/horasApi';
import ChipEstado from './EstadoProyecto';

export default function ImportarProyectos() {
  const [archivo, setArchivo] = useState<File | null>(null);
  const [previa, setPrevia] = useState<VistaPreviaProyectos | null>(null);
  const [resumen, setResumen] = useState<ResumenProyectos | null>(null);
  const [analizando, setAnalizando] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [bajando, setBajando] = useState(false);
  const [error, setError] = useState('');
  const entrada = useRef<HTMLInputElement>(null);

  const elegir = (f: File | null) => {
    setArchivo(f); setPrevia(null); setResumen(null); setError('');
  };

  const empezar = () => {
    elegir(null);
    if (entrada.current) entrada.current.value = '';
  };

  const descargarPlantilla = async () => {
    setBajando(true); setError('');
    try {
      const blob = await horasApi.plantillaProyectos();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'plantilla-proyectos-y-estimaciones.xlsx';
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setError(mensajeDeError(e, 'No se pudo descargar la plantilla.'));
    }
    setBajando(false);
  };

  const analizar = async () => {
    if (!archivo) return;
    setAnalizando(true); setError(''); setResumen(null);
    try {
      setPrevia(await horasApi.vistaPreviaProyectos(archivo));
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
      setResumen(await horasApi.confirmarProyectos(archivo));
      setPrevia(null);
    } catch (e: any) {
      setError(mensajeDeError(e, 'No se pudo completar la importación.'));
    }
    setConfirmando(false);
  };

  return (
    <div data-testid="importar-proyectos">
      <p className="text-lg text-gray-500 mb-5">
        Una fila por actividad. El proyecto se repite en cada una de sus
        actividades, y volver a subir el mismo archivo no duplica nada:
        actualiza las horas estimadas al valor del archivo.
      </p>

      {error && (
        <div className="mb-4 flex items-start gap-2 p-4 rounded-xl bg-red-50 border border-red-200 text-red-800">
          <AlertTriangle className="w-5 h-5 mt-0.5 flex-shrink-0" />
          <span className="text-base" data-testid="error-proyectos">{error}</span>
        </div>
      )}

      {/* ---------- 1. El archivo ---------- */}
      {!resumen && (
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 mb-6">
          <div className="flex flex-wrap gap-5 items-end">
            <label className="block">
              <span className="block text-base font-semibold text-gray-700 mb-1">
                Archivo (.xlsx)
              </span>
              <input ref={entrada} type="file" accept=".xlsx"
                onChange={(e) => elegir(e.target.files?.[0] || null)}
                data-testid="archivo-proyectos"
                className="block text-lg file:mr-4 file:py-3 file:px-5 file:rounded-xl
                  file:border-0 file:text-lg file:font-bold file:bg-[#f5a623]
                  file:text-[#0a1628] hover:file:bg-[#f7b84a] file:cursor-pointer" />
            </label>

            <button onClick={analizar} disabled={!archivo || analizando}
              data-testid="analizar-proyectos"
              className="flex items-center gap-2 px-6 py-3 bg-[#0a1628] text-white text-lg
                         font-bold rounded-xl hover:bg-[#16243d] disabled:opacity-40
                         disabled:cursor-not-allowed">
              {analizando ? <Loader2 className="w-5 h-5 animate-spin" />
                : <Upload className="w-5 h-5" />}
              Ver qué va a pasar
            </button>

            {/* H-D101: para no adivinar el formato. */}
            <button onClick={descargarPlantilla} disabled={bajando}
              data-testid="descargar-plantilla"
              className="flex items-center gap-2 px-5 py-3 text-lg font-semibold rounded-xl
                         border-2 border-gray-300 text-gray-700 hover:bg-gray-50
                         disabled:opacity-40">
              {bajando ? <Loader2 className="w-5 h-5 animate-spin" />
                : <Download className="w-5 h-5" />}
              Descargar plantilla
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
        <div data-testid="previa-proyectos">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
            {([
              ['Proyectos nuevos', String(previa.proyectos_nuevos), 'border-emerald-500'],
              ['Ya existían', String(previa.proyectos_actualizados), 'border-indigo-500'],
              ['No se importan', String(previa.invalidas.length),
                previa.invalidas.length ? 'border-red-500' : 'border-gray-300'],
              ['Horas estimadas', `${horas(previa.total_horas)} h`, 'border-gray-300'],
            ] as [string, string, string][]).map(([etiqueta, valor, borde]) => (
              <div key={etiqueta}
                className={`bg-white rounded-xl p-4 border-l-4 ${borde} border border-gray-200 shadow-sm`}>
                <p className="text-sm text-gray-500 uppercase">{etiqueta}</p>
                <p className="text-2xl font-bold text-gray-800 mt-1 tabular-nums"
                  data-testid={`previa-proy-${etiqueta}`}>{valor}</p>
              </div>
            ))}
          </div>

          <p className="text-base text-gray-500 mb-5">
            Hoja «{previa.sheet}» · {previa.total_filas} filas ·{' '}
            {previa.estimaciones_nuevas} estimaciones nuevas,{' '}
            {previa.estimaciones_actualizadas} que cambian y{' '}
            {previa.estimaciones_iguales} que se quedan igual
            {previa.clientes_a_crear.length > 0
              && ` · se crean los clientes: ${previa.clientes_a_crear.join(', ')}`}
            {previa.actividades_a_crear.length > 0
              && ` · y las actividades: ${previa.actividades_a_crear.join(', ')}`}
          </p>

          {/* §4 (carga real): las actividades que el catálogo no tenía. El mismo
              aviso que en la importación de registros, porque las dos preguntan
              a la misma tabla de sinónimos. */}
          <ActividadesNuevasProyectos actividades={previa.actividades_nuevas} />

          {/* Las filas que no entran, primero: es lo que hay que mirar (H-D100). */}
          {previa.invalidas.length > 0 && (
            <div className="rounded-2xl border border-red-200 bg-red-50 p-5 mb-5"
              data-testid="filas-invalidas">
              <p className="text-lg font-bold text-red-800 mb-2">
                {previa.invalidas.length} fila
                {previa.invalidas.length === 1 ? '' : 's'} que no se importa
                {previa.invalidas.length === 1 ? '' : 'n'}
              </p>
              <ul className="space-y-1">
                {previa.invalidas.map((f) => (
                  <li key={f.numero} className="text-base text-red-900">
                    <strong>Fila {f.numero}</strong> · {f.project_name || '—'}
                    {f.activity_name ? ` · ${f.activity_name}` : ''} — {f.motivo}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {previa.proyectos.map((p) => <BloqueProyecto key={`${p.client_name}|${p.project_name}`} p={p} />)}

          <div className="flex flex-wrap justify-end gap-3 mt-6">
            <button onClick={empezar} data-testid="cancelar-proyectos"
              className="px-6 py-3 text-lg font-semibold rounded-xl border-2 border-gray-300 hover:bg-gray-50">
              Cancelar
            </button>
            <button onClick={confirmar} disabled={confirmando || previa.proyectos.length === 0}
              data-testid="confirmar-proyectos"
              className="flex items-center gap-2 px-6 py-3 bg-[#f5a623] text-[#0a1628] text-lg
                         font-bold rounded-xl hover:bg-[#f7b84a] disabled:opacity-40">
              {confirmando && <Loader2 className="w-5 h-5 animate-spin" />}
              Importar {previa.proyectos.length} proyecto
              {previa.proyectos.length === 1 ? '' : 's'}
            </button>
          </div>
        </div>
      )}

      {/* ---------- 3. El resumen ---------- */}
      {resumen && (
        <div className="bg-white rounded-2xl border border-emerald-300 p-5"
          data-testid="resumen-proyectos">
          <p className="text-xl font-bold text-emerald-800 mb-3 flex items-center gap-2">
            <Check className="w-6 h-6" /> Importación terminada
          </p>
          <ul className="text-lg text-gray-800 space-y-1">
            <li>{resumen.proyectos_creados.length} proyectos creados</li>
            <li>{resumen.proyectos_actualizados} proyectos que ya existían</li>
            <li>
              {resumen.estimaciones_creadas} estimaciones nuevas ·{' '}
              {resumen.estimaciones_actualizadas} actualizadas ·{' '}
              {resumen.estimaciones_iguales} sin cambio
            </li>
            {resumen.estados_cambiados > 0 && (
              <li>{resumen.estados_cambiados} cambios de estado</li>
            )}
            {resumen.omitidas > 0 && (
              <li className="text-red-800">{resumen.omitidas} filas no se importaron</li>
            )}
            <li className="font-semibold">{horas(resumen.total_horas)} h estimadas en total</li>
          </ul>

          {/* §4: el mismo bloque de la previa, repetido para que siga a la
              vista después de confirmar. */}
          <div className="mt-5">
            <ActividadesNuevasProyectos actividades={resumen.actividades_nuevas} yaCreadas />
          </div>

          <button onClick={empezar} data-testid="importar-otros-proyectos"
            className="mt-4 px-6 py-3 bg-[#f5a623] text-[#0a1628] text-lg font-bold rounded-xl hover:bg-[#f7b84a]">
            Importar otro archivo
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * §4 (carga real): las actividades del archivo que no estaban en el catálogo.
 *
 * Aquí las horas son **estimadas**, no trabajadas; por lo demás es el mismo
 * aviso que en la importación de registros y sirve para lo mismo: decidir si lo
 * que falta es un sinónimo antes de crear una actividad duplicada.
 */
function ActividadesNuevasProyectos({ actividades, yaCreadas }: {
  actividades: ActividadNueva[]; yaCreadas?: boolean;
}) {
  if (actividades.length === 0) return null;
  return (
    <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 mb-5"
      data-testid="actividades-nuevas">
      <p className="text-lg font-bold text-gray-800 mb-2">
        Actividades nuevas que no estaban en el catálogo ({actividades.length})
      </p>
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
            {' — '}{horas(a.horas)} h estimadas en {a.filas.length}{' '}
            {a.filas.length === 1 ? 'fila' : 'filas'}
            {a.filas.length > 0 && (
              <span className="text-gray-500"> ({a.filas.join(', ')})</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Un proyecto del archivo, con sus actividades juntas (H-D96, H-D99). */
function BloqueProyecto({ p }: { p: ProyectoImportado }) {
  const ACCION: Record<string, string> = {
    crea: 'bg-emerald-100 text-emerald-800',
    actualiza: 'bg-indigo-100 text-indigo-800',
    igual: 'bg-gray-100 text-gray-600',
  };
  return (
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 mb-4"
      data-testid="bloque-proyecto" data-proyecto={p.project_name}>
      <div className="flex flex-wrap items-center gap-3 mb-3">
        <span className="text-xl font-bold text-gray-800">{p.project_name}</span>
        <span className="text-base text-gray-500">{p.client_name}</span>
        <ChipEstado estado={p.status} etiqueta={p.status_label} />
        {p.es_nuevo
          ? <span className="px-3 py-1 text-sm font-semibold rounded-full bg-emerald-100 text-emerald-800">nuevo</span>
          : <span className="px-3 py-1 text-sm font-semibold rounded-full bg-indigo-100 text-indigo-800">ya existe</span>}
        {p.cambia_de_estado && (
          <span className="text-base text-amber-800">
            cambia de «{p.status_anterior_label}» a «{p.status_label}»
          </span>
        )}
        <span className="ml-auto text-xl font-bold text-gray-800 tabular-nums"
          data-testid="total-proyecto">
          {horas(p.total_hours)} h
        </span>
      </div>
      <table className="w-full">
        <tbody>
          {p.filas.map((f) => (
            <tr key={f.numero} className="border-t border-gray-100">
              <td className="py-2 pr-3 text-base text-gray-400 w-16">Fila {f.numero}</td>
              <td className="py-2 pr-3 text-lg text-gray-800">
                {f.activity_name}
                {f.crea_actividad && (
                  <span className="ml-2 text-sm text-emerald-700">actividad nueva</span>
                )}
              </td>
              <td className="py-2 pr-3 text-right text-lg tabular-nums text-gray-800 w-28">
                {horas(f.estimated_hours)} h
              </td>
              <td className="py-2 text-right w-40">
                <span className={`px-3 py-1 text-sm font-semibold rounded-full ${ACCION[f.accion] || ''}`}>
                  {f.accion === 'crea' ? 'se añade'
                    : f.accion === 'actualiza' ? `de ${horas(f.previous_hours)} h`
                    : 'sin cambio'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
