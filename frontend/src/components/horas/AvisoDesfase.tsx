/**
 * El aviso de desfase (ETAPA H2b.4, especificación de horas v1.1 §5.1).
 *
 * El estado, las horas de más y el texto vienen **ya resueltos** del backend
 * (`services/horas/desfase.py`): aquí solo se elige el color. Si la regla de los
 * umbrales cambia, cambia en un sitio y estas dos pantallas se enteran solas.
 *
 * Se dice «desfase», no «exceso» (H-D27).
 */
import { AlertCircle, AlertTriangle } from 'lucide-react';
import { Desfase, horas } from '../../api/horasApi';

// Los CUATRO valores del consumo (§5.1, v1.5). «En rango» y «Terminado» no son
// avisos: van en gris y en verde, sin gritar. Los que piden mirar son los otros
// dos.
//
// ETAPA H8 (H-D82): `cerrado` salió de aquí. Cerrar un proyecto es un ESTADO y
// lo pinta `EstadoProyecto.tsx`, en su propia columna; antes tapaba el consumo
// y ya no se sabía si el proyecto se había pasado de horas o no.
const COLOR = {
  en_rango: 'bg-gray-100 text-gray-600',
  por_agotarse: 'bg-amber-100 text-amber-900 border border-amber-300',
  terminado: 'bg-emerald-100 text-emerald-800 border border-emerald-300',
  desfasado: 'bg-red-100 text-red-800 border border-red-300',
} as const;

interface Props {
  dato: Desfase;
  /** En un listado, «En rango» en cada fila es ruido: solo se avisa de lo que
   *  hay que mirar. En el detalle del proyecto se enseña siempre. */
  siempre?: boolean;
}

export default function AvisoDesfase({ dato, siempre = false }: Props) {
  const estado = dato.overrun_status;
  if (estado === 'en_rango' && !siempre) return null;

  return (
    <span data-testid="chip-desfase" data-estado={estado}
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-semibold ${COLOR[estado]}`}>
      {estado === 'desfasado' && <AlertTriangle className="w-4 h-4" />}
      {estado === 'por_agotarse' && <AlertCircle className="w-4 h-4" />}
      {dato.overrun_label}
    </span>
  );
}

/** El porcentaje consumido, en formato español. */
export function PorcentajeConsumido({ dato }: { dato: Desfase }) {
  const pct = parseFloat(String(dato.consumed_pct));
  const color = dato.overrun_status === 'desfasado' ? 'text-red-700'
    : dato.overrun_status === 'por_agotarse' ? 'text-amber-700'
    : dato.overrun_status === 'terminado' ? 'text-emerald-700' : 'text-gray-600';
  return (
    <span className={`tabular-nums font-semibold ${color}`} data-testid="porcentaje-consumido">
      {horas(pct)} %
    </span>
  );
}

/** La barra de consumido frente a estimado (§5.1).
 *
 *  §5.1 pide «una barra con lo consumido frente a lo estimado»; el porcentaje en
 *  texto lo dice, pero no se ve de un vistazo en una lista larga. Va con su cifra
 *  al lado: la barra sola no se puede leer con precisión.
 */
export function BarraConsumo({ dato }: { dato: Desfase }) {
  const pct = parseFloat(String(dato.consumed_pct)) || 0;
  const relleno = dato.overrun_status === 'desfasado' ? 'bg-red-500'
    : dato.overrun_status === 'por_agotarse' ? 'bg-amber-500'
    : dato.overrun_status === 'terminado' ? 'bg-emerald-600' : 'bg-emerald-500';
  return (
    <div className="flex items-center gap-2" data-testid="barra-consumo" data-pct={pct.toFixed(2)}>
      <div className="flex-1 min-w-[60px] h-2.5 bg-gray-200 rounded-full overflow-hidden">
        {/* Por encima del 100 % la barra se queda llena: lo que sobra lo dice la
            etiqueta con su cifra, no un rectángulo que se salga de la caja. */}
        <div className={`h-full ${relleno} rounded-full`}
          style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      <PorcentajeConsumido dato={dato} />
    </div>
  );
}

/** El aviso de arriba: cuántos proyectos están desfasados, con su filtro (§5.1). */
export function AvisoDesfasados({ cuantos, activo, onAlternar }: {
  cuantos: number;
  activo: boolean;
  onAlternar: () => void;
}) {
  if (!cuantos && !activo) return null;
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3 p-4 rounded-xl bg-red-50 border border-red-200"
      data-testid="aviso-desfasados">
      <div className="flex items-center gap-2 text-red-800">
        <AlertTriangle className="w-5 h-5 flex-shrink-0" />
        <span className="text-lg">
          {cuantos === 0 ? 'Ningún proyecto desfasado con estos filtros.'
            : cuantos === 1 ? <><strong>1 proyecto</strong> se pasó de lo estimado.</>
            : <><strong>{cuantos} proyectos</strong> se pasaron de lo estimado.</>}
        </span>
      </div>
      <button onClick={onAlternar} data-testid="filtro-desfasados"
        className={`px-4 py-2.5 text-base font-semibold rounded-xl border-2 ${
          activo ? 'bg-red-600 text-white border-red-600'
            : 'bg-white text-red-700 border-red-300 hover:bg-red-100'}`}>
        {activo ? 'Ver todos' : 'Ver solo los desfasados'}
      </button>
    </div>
  );
}
