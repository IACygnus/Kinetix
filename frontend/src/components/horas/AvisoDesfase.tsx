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

const COLOR = {
  en_rango: 'bg-gray-100 text-gray-600',
  por_agotarse: 'bg-amber-100 text-amber-900 border border-amber-300',
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
    : dato.overrun_status === 'por_agotarse' ? 'text-amber-700' : 'text-gray-600';
  return (
    <span className={`tabular-nums font-semibold ${color}`} data-testid="porcentaje-consumido">
      {horas(pct)} %
    </span>
  );
}
