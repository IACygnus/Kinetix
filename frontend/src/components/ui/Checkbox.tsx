/**
 * Casilla con su etiqueta (mockup: .check). Toda la fila es pulsable: 40 px de
 * alto, aunque la casilla mida 20.
 */
import { forwardRef, InputHTMLAttributes, ReactNode } from 'react';
import { cx } from './cx';

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  etiqueta: ReactNode;
  invalido?: boolean;
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox(
  { etiqueta, invalido, disabled, className, ...resto },
  ref,
) {
  return (
    <label
      className={cx(
        'inline-flex min-h-10 items-center gap-2 text-ink',
        disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer',
        className,
      )}
    >
      <input
        ref={ref}
        type="checkbox"
        disabled={disabled}
        aria-invalid={invalido || undefined}
        className="h-5 w-5 flex-none cursor-pointer accent-link disabled:cursor-not-allowed"
        {...resto}
      />
      <span>{etiqueta}</span>
    </label>
  );
});
