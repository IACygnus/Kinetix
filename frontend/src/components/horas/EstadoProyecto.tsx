/**
 * El ESTADO del proyecto (ETAPA H8, §3.1 de la especificación v1.5).
 *
 * Un solo sitio, como `services/horas/estados.py` en el backend: lo pintan el
 * listado de Proyectos, el detalle, la Consulta y la vista previa del informe.
 * Sin esto, cuatro pantallas acabarían pintando el mismo estado de cuatro
 * formas distintas.
 *
 * **Esto es la otra columna de §5.1** (H-D82). El consumo lo pinta
 * `AvisoDesfase`, y no se mezclan: uno dice en qué punto está el trabajo y el
 * otro cuántas horas lleva gastadas de las estimadas. Las dos importan.
 *
 * Lo que se puede hacer en cada estado **no se decide aquí**: llega del backend
 * en `can_log_hours` y `can_edit_estimates`. Si esa tabla se copiara en
 * TypeScript, el día que cambiara una de las dos tendríamos una pantalla que
 * permite lo que el backend rechaza.
 */
import { EstadoProyecto } from '../../api/horasApi';

/** Los cinco de §3.1, en el orden en que se enseñan. */
export const ESTADOS: EstadoProyecto[] = [
  'pendiente', 'en_ejecucion', 'detenido', 'no_viable', 'finalizado',
];

/** El rótulo llega del backend en `status_label`; este mapa es solo para el
 *  selector, que tiene que ofrecer estados que el proyecto todavía no tiene. */
export const ROTULOS: Record<EstadoProyecto, string> = {
  pendiente: 'Pendiente',
  en_ejecucion: 'En ejecución',
  detenido: 'Detenido',
  no_viable: 'No viable',
  finalizado: 'Finalizado',
};

// En marcha en verde; parado en ámbar; lo que no se va a hacer, apagado. Son
// colores distintos de los del consumo a propósito: si los dos juegos se
// parecieran, las dos columnas volverían a leerse como una sola.
const COLOR: Record<EstadoProyecto, string> = {
  pendiente: 'bg-sky-100 text-sky-800 border border-sky-300',
  en_ejecucion: 'bg-emerald-100 text-emerald-800 border border-emerald-300',
  detenido: 'bg-amber-100 text-amber-900 border border-amber-300',
  no_viable: 'bg-gray-200 text-gray-600 border border-gray-300',
  finalizado: 'bg-slate-200 text-slate-700 border border-slate-300',
};

/** §8: los dos que cierran el proyecto son del administrador (H-D90). */
export const SOLO_ADMIN: EstadoProyecto[] = ['no_viable', 'finalizado'];

interface ChipProps {
  estado: EstadoProyecto;
  /** El texto del backend. Si falta, el del mapa. */
  etiqueta?: string;
  tamano?: 'normal' | 'grande';
}

export default function ChipEstado({ estado, etiqueta, tamano = 'normal' }: ChipProps) {
  const medida = tamano === 'grande' ? 'px-4 py-1.5 text-base' : 'px-3 py-1 text-sm';
  return (
    <span data-testid="chip-estado" data-estado={estado}
      className={`inline-flex items-center rounded-full font-semibold ${medida} ${COLOR[estado]}`}>
      {etiqueta || ROTULOS[estado]}
    </span>
  );
}

interface SelectorProps {
  estado: EstadoProyecto;
  /** Quien no es admin no puede poner `no_viable` ni `finalizado` (§8). El
   *  backend lo rechaza con un 403; aquí solo se evita ofrecer lo que no se
   *  puede hacer. */
  esAdmin: boolean;
  onCambiar: (nuevo: EstadoProyecto) => void;
  disabled?: boolean;
  /** Para distinguir el del listado del del detalle en las pruebas. */
  testid?: string;
}

/** El selector de §3.1 (H-D83). Se usa en el detalle y en el listado. */
export function SelectorEstado({
  estado, esAdmin, onCambiar, disabled = false, testid = 'selector-estado',
}: SelectorProps) {
  return (
    <select value={estado} disabled={disabled} data-testid={testid}
      onChange={(e) => onCambiar(e.target.value as EstadoProyecto)}
      onClick={(e) => e.stopPropagation()}
      className="px-3 py-2 border-2 border-gray-300 rounded-xl text-base font-semibold
                 text-gray-700 bg-white disabled:opacity-40">
      {ESTADOS.map((e) => (
        <option key={e} value={e}
          // Un estado que no se puede poner sale deshabilitado, no escondido:
          // esconderlo haría creer que no existe.
          disabled={!esAdmin && SOLO_ADMIN.includes(e) && e !== estado}>
          {ROTULOS[e]}
        </option>
      ))}
    </select>
  );
}
