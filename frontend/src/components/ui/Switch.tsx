/**
 * Interruptor (mockup: .switch). Es una casilla con role="switch": el lector de
 * pantalla dice «activado/desactivado» y la barra espaciadora lo cambia. El
 * dibujo está en ui.css (.kx-switch).
 */
import { forwardRef, InputHTMLAttributes, ReactNode } from 'react';
import { cx } from './cx';

export interface SwitchProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'role'> {
  etiqueta: ReactNode;
}

export const Switch = forwardRef<HTMLInputElement, SwitchProps>(function Switch(
  { etiqueta, disabled, className, ...resto },
  ref,
) {
  return (
    <label
      className={cx(
        'inline-flex min-h-10 items-center gap-2.5 text-ink',
        disabled ? 'cursor-not-allowed' : 'cursor-pointer',
        className,
      )}
    >
      <input ref={ref} type="checkbox" role="switch" disabled={disabled} className="kx-switch" {...resto} />
      <span className={cx(disabled && 'opacity-50')}>{etiqueta}</span>
    </label>
  );
});
