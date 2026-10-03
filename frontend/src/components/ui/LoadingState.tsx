/**
 * Cargando (mockup: .skel). Esqueleto de líneas, no un giro suelto: deja ver
 * la forma de lo que viene. La auditoría 153 no encontró ningún esqueleto y la
 * mitad de las pantallas cargaban en blanco.
 *
 * role="status" con el nombre de lo que carga; con movimiento reducido o
 * pausado, las líneas quedan quietas.
 */
import { cx } from './cx';

const ANCHOS = ['w-3/5', 'w-11/12', 'w-2/5'];

export interface LoadingStateProps {
  /** Qué se está cargando, en minúscula: «los reportes». */
  que: string;
  lineas?: number;
  className?: string;
}

export function LoadingState({ que, lineas = 7, className }: LoadingStateProps) {
  return (
    <div role="status" aria-label={`Cargando ${que}`} className={cx('grid gap-3 p-5', className)}>
      {Array.from({ length: lineas }, (_, i) => (
        <i
          key={i}
          aria-hidden="true"
          className={cx('block h-4 rounded-chico bg-surface-2 motion-safe:animate-pulso', ANCHOS[i % 3])}
        />
      ))}
      <span className="sr-only">Cargando {que}…</span>
    </div>
  );
}
