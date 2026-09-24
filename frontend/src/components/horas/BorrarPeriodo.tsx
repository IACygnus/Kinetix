/**
 * Borrar los registros de un periodo (ETAPA H8.5, §4.3, H-D88/H-D89).
 *
 * Vive dentro de la pantalla de Importación porque es donde se usa: el orden
 * real es **borrar → cargar proyectos → cargar horas**. Y está **plegado por
 * defecto**: no es algo que se haga todos los días.
 *
 * Las tres condiciones de §4.3 están aquí por comodidad, no por seguridad —el
 * backend las vuelve a comprobar todas—, pero la pantalla hace una cosa que el
 * backend no puede hacer solo: **invalidar la previa en cuanto cambian las
 * fechas**. Si la previa siguiera en pantalla con un rango nuevo, se podría
 * confirmar un borrado distinto del que se revisó.
 *
 * Solo admin (§8). Quien no lo sea no ve este bloque, y el backend le
 * contestaría 403 hasta en la vista previa.
 *
 * Regla 16: todos los hooks antes de cualquier return.
 */
import { useEffect, useState } from 'react';
import {
  AlertTriangle, ChevronDown, ChevronRight, Check, Copy, Loader2, Trash2,
} from 'lucide-react';
import {
  BorradoPreview, BorradoResumen, horas, horasApi, hoyISO, mensajeDeError,
} from '../../api/horasApi';

/** El primer y el último día del mes pasado: es lo que se suele querer borrar. */
const mesPasado = (): [string, string] => {
  const [a, m] = hoyISO().split('-').map(Number);
  const anio = m === 1 ? a - 1 : a;
  const mes = m === 1 ? 12 : m - 1;
  const ultimo = new Date(anio, mes, 0).getDate();
  const mm = String(mes).padStart(2, '0');
  return [`${anio}-${mm}-01`, `${anio}-${mm}-${String(ultimo).padStart(2, '0')}`];
};

export default function BorrarPeriodo() {
  const [abierto, setAbierto] = useState(false);          // plegado por defecto
  const [inicio, fin] = mesPasado();
  const [desde, setDesde] = useState(inicio);
  const [hasta, setHasta] = useState(fin);

  const [previa, setPrevia] = useState<BorradoPreview | null>(null);
  const [copiaHecha, setCopiaHecha] = useState(false);
  const [tecleado, setTecleado] = useState('');
  const [resumen, setResumen] = useState<BorradoResumen | null>(null);
  const [cargando, setCargando] = useState(false);
  const [borrando, setBorrando] = useState(false);
  const [error, setError] = useState('');
  const [copiado, setCopiado] = useState(false);

  // **Cambiar el rango invalida todo lo anterior.** Es la única forma de que no
  // se pueda confirmar un rango distinto del revisado: la previa desaparece, y
  // con ella la casilla y el texto tecleado.
  useEffect(() => {
    setPrevia(null);
    setCopiaHecha(false);
    setTecleado('');
    setResumen(null);
    setError('');
  }, [desde, hasta]);

  const pedirPrevia = async () => {
    setCargando(true); setError('');
    try {
      setPrevia(await horasApi.borradoPreview(desde, hasta));
    } catch (e: any) {
      setError(mensajeDeError(e, 'No se pudo calcular la vista previa.'));
      setPrevia(null);
    }
    setCargando(false);
  };

  const borrar = async () => {
    if (!previa) return;
    setBorrando(true); setError('');
    try {
      setResumen(await horasApi.borradoConfirm({
        desde, hasta, confirmacion: tecleado, copia_hecha: copiaHecha,
      }));
      setPrevia(null);
    } catch (e: any) {
      setError(mensajeDeError(e, 'No se pudo borrar el periodo.'));
    }
    setBorrando(false);
  };

  const copiarComando = async () => {
    if (!previa) return;
    try {
      await navigator.clipboard.writeText(previa.comando_copia);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2500);
    } catch { /* si el navegador no deja, el comando está a la vista igual */ }
  };

  // La comparación de aquí es la MISMA que hace el backend: sin tildes, sin
  // mayúsculas y sin espacios de más. Si fuera más estricta, el botón se
  // quedaría apagado con un texto que el backend sí acepta.
  const comparable = (s: string) =>
    s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim().replace(/\s+/g, ' ').toLowerCase();
  const fraseOk = Boolean(previa)
    && comparable(tecleado) === comparable(previa!.frase_de_confirmacion);
  const puedeBorrar = Boolean(previa) && previa!.total_entries > 0
    && copiaHecha && fraseOk && !borrando;

  const campo = 'px-4 py-3 border-2 border-gray-300 rounded-xl text-lg';

  return (
    <div className="mt-8 rounded-2xl border-2 border-red-200 bg-red-50/40 overflow-hidden"
      data-testid="bloque-borrar-periodo">
      <button onClick={() => setAbierto((v) => !v)} data-testid="abrir-borrar-periodo"
        className="w-full flex items-center gap-3 px-5 py-4 text-left hover:bg-red-50">
        {abierto ? <ChevronDown className="w-5 h-5 text-red-700" />
          : <ChevronRight className="w-5 h-5 text-red-700" />}
        <Trash2 className="w-5 h-5 text-red-700" />
        <span className="text-xl font-bold text-red-800">Borrar los registros de un periodo</span>
        <span className="ml-auto text-base text-red-700">Solo administrador</span>
      </button>

      {abierto && (
        <div className="px-5 pb-5" data-testid="panel-borrar-periodo">
          <p className="text-base text-gray-700 mb-4">
            Para volver a cargar un periodo desde cero. <strong>Se borran solo
            registros de horas</strong>: los proyectos, sus estimaciones, las
            actividades y los clientes se quedan como están.
          </p>

          {error && (
            <div className="mb-4 flex items-start gap-2 p-4 rounded-xl bg-red-100 border border-red-300 text-red-900">
              <AlertTriangle className="w-5 h-5 mt-0.5 flex-shrink-0" />
              <span className="text-base" data-testid="error-borrado">{error}</span>
            </div>
          )}

          {/* ---------- 1. El rango ---------- */}
          <div className="flex flex-wrap gap-4 items-end mb-4">
            <label className="block">
              <span className="block text-base text-gray-600 mb-1">Desde</span>
              <input type="date" value={desde} data-testid="borrado-desde" className={campo}
                onChange={(e) => e.target.value && setDesde(e.target.value)} />
            </label>
            <label className="block">
              <span className="block text-base text-gray-600 mb-1">Hasta</span>
              <input type="date" value={hasta} data-testid="borrado-hasta" className={campo}
                onChange={(e) => e.target.value && setHasta(e.target.value)} />
            </label>
            <button onClick={pedirPrevia} disabled={cargando} data-testid="ver-que-se-borra"
              className="flex items-center gap-2 px-6 py-3 bg-white border-2 border-red-300
                         text-red-800 text-lg font-bold rounded-xl hover:bg-red-50
                         disabled:opacity-40">
              {cargando && <Loader2 className="w-5 h-5 animate-spin" />}
              Ver qué se borraría
            </button>
          </div>

          {/* ---------- 2. La vista previa ---------- */}
          {previa && (
            <div className="bg-white rounded-2xl border border-red-200 p-5"
              data-testid="previa-borrado">
              <p className="text-2xl font-bold text-gray-800 mb-1">
                {previa.periodo}
              </p>
              <p className="text-lg text-gray-700 mb-4" data-testid="borrado-totales">
                <strong>{previa.total_entries}</strong> registro
                {previa.total_entries === 1 ? '' : 's'} ·{' '}
                <strong>{horas(previa.total_hours)} h</strong> ·{' '}
                {previa.de_importacion} de importación y {previa.manuales} a mano
              </p>

              {previa.total_entries === 0 ? (
                <p className="text-lg text-gray-500">
                  No hay nada que borrar en ese rango.
                </p>
              ) : (
                <>
                  <table className="w-full mb-4" data-testid="borrado-por-persona">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr className="text-sm uppercase text-gray-500">
                        <th className="py-2 px-3 text-left">Persona</th>
                        <th className="py-2 px-3 text-right w-32">Registros</th>
                        <th className="py-2 px-3 text-right w-32">Horas</th>
                      </tr>
                    </thead>
                    <tbody>
                      {previa.por_persona.map((p) => (
                        <tr key={p.user_name} className="border-b border-gray-100 last:border-0">
                          <td className="py-2 px-3 text-lg text-gray-800">{p.user_name}</td>
                          <td className="py-2 px-3 text-right text-lg tabular-nums">{p.entries}</td>
                          <td className="py-2 px-3 text-right text-lg tabular-nums">{horas(p.hours)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  <p className="text-base text-gray-700 mb-4 p-3 rounded-xl bg-emerald-50
                                border border-emerald-200" data-testid="lo-que-no-se-borra">
                    {previa.lo_que_no_se_borra}
                  </p>

                  {/* ---------- 3. La copia, que la hace una persona ---------- */}
                  <p className="text-base font-semibold text-gray-700 mb-1">
                    Antes de borrar, haz la copia de seguridad:
                  </p>
                  <div className="flex gap-2 items-start mb-2">
                    <code className="flex-1 block p-3 rounded-xl bg-gray-900 text-gray-100
                                     text-sm break-all" data-testid="comando-copia">
                      {previa.comando_copia}
                    </code>
                    <button onClick={copiarComando} data-testid="copiar-comando"
                      className="flex items-center gap-1 px-4 py-3 text-base font-semibold
                                 rounded-xl border-2 border-gray-300 hover:bg-gray-50">
                      {copiado ? <Check className="w-5 h-5 text-emerald-600" />
                        : <Copy className="w-5 h-5" />}
                      {copiado ? 'Copiado' : 'Copiar'}
                    </button>
                  </div>
                  <label className="flex items-center gap-2 mb-4 cursor-pointer">
                    <input type="checkbox" checked={copiaHecha} data-testid="copia-hecha"
                      onChange={(e) => setCopiaHecha(e.target.checked)}
                      className="w-5 h-5 accent-red-600" />
                    <span className="text-lg text-gray-800">
                      Ya hice la copia de seguridad
                    </span>
                  </label>

                  {/* ---------- 4. La frase, tecleada ---------- */}
                  <label className="block mb-4">
                    <span className="block text-base text-gray-700 mb-1">
                      Escribe <strong>{previa.frase_de_confirmacion}</strong> para confirmar
                    </span>
                    <input value={tecleado} data-testid="frase-confirmacion"
                      onChange={(e) => setTecleado(e.target.value)}
                      placeholder={previa.frase_de_confirmacion}
                      className={`${campo} w-full max-w-md ${
                        tecleado && !fraseOk ? 'border-red-400' : ''}`} />
                  </label>

                  <button onClick={borrar} disabled={!puedeBorrar} data-testid="borrar-periodo"
                    className="flex items-center gap-2 px-6 py-3 bg-red-600 text-white text-lg
                               font-bold rounded-xl hover:bg-red-700 disabled:opacity-40
                               disabled:cursor-not-allowed">
                    {borrando && <Loader2 className="w-5 h-5 animate-spin" />}
                    <Trash2 className="w-5 h-5" />
                    Borrar los {previa.total_entries} registros de {previa.periodo}
                  </button>
                </>
              )}
            </div>
          )}

          {/* ---------- 5. Lo que pasó ---------- */}
          {resumen && (
            <div className="bg-white rounded-2xl border border-emerald-300 p-5"
              data-testid="resumen-borrado">
              <p className="text-xl font-bold text-emerald-800 mb-2">
                Borrado de {resumen.periodo}
              </p>
              <p className="text-lg text-gray-800">
                {resumen.entries_deleted} registros · {horas(resumen.hours_deleted)} h ·
                por {resumen.performed_by}
              </p>
              <p className="text-base text-gray-600 mt-2">{resumen.lo_que_no_se_borro}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
