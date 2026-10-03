/**
 * Indicador de actividad dentro de un botón o de un estado de carga. Con
 * movimiento reducido o pausado queda quieto (ui.css), y el texto que lo
 * acompaña es lo que informa: el giro es decoración.
 */
import { Loader2 } from 'lucide-react';
import { cx } from './cx';

export function Spinner({ className }: { className?: string }) {
  return <Loader2 aria-hidden="true" className={cx('h-5 w-5 flex-none motion-safe:animate-spin', className)} />;
}
