/**
 * Barra de progreso (mockup: .prog). role="progressbar" con su valor y su
 * nombre; el tono dice el estado (ok, aviso, error), pero el texto que la
 * acompaña es lo que lo cuenta. Sin `valor`, es indeterminada.
 */
import { cx } from './cx';

export type TonoProgreso = 'primary' | 'ok' | 'warn' | 'err';

const TONOS: Record<TonoProgreso, string> = {
  primary: 'bg-primary',
  ok: 'bg-ok',
  warn: 'bg-warn',
  err: 'bg-err',
};

export interface ProgressProps {
  etiqueta: string;
  valor?: number;
  max?: number;
  tono?: TonoProgreso;
  /** Texto que lee el lector de pantalla en lugar del porcentaje («3 de 5 archivos»). */
  textoValor?: string;
  className?: string;
}

export function Progress({ etiqueta, valor, max = 100, tono = 'primary', textoValor, className }: ProgressProps) {
  const indeterminada = valor === undefined;
  const pct = indeterminada ? 40 : Math.max(0, Math.min(100, (valor / max) * 100));
  return (
    <div
      role="progressbar"
      aria-label={etiqueta}
      aria-valuemin={indeterminada ? undefined : 0}
      aria-valuemax={indeterminada ? undefined : max}
      aria-valuenow={indeterminada ? undefined : valor}
      aria-valuetext={textoValor}
      className={cx('h-2 min-w-20 overflow-hidden rounded-pill bg-surface-2', className)}
    >
      <i
        className={cx(
          'block h-full origin-left rounded-pill',
          TONOS[tono],
          indeterminada ? 'motion-safe:animate-pulso' : 'motion-safe:transition-all',
        )}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
