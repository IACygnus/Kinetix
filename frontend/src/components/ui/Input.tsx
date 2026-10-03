/**
 * Campo de texto (mockup: .in). `invalido` marca aria-invalid y pinta el error.
 * Va dentro de un <Field> con el mismo id.
 */
import { forwardRef, InputHTMLAttributes } from 'react';
import { cx } from './cx';
import { CLASE_CAMPO } from './campo';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalido?: boolean;
  /** Para nombres de archivo, rutas, URL: JetBrains Mono. */
  codigo?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { invalido, codigo, className, ...resto },
  ref,
) {
  return (
    <input
      ref={ref}
      aria-invalid={invalido || undefined}
      className={cx(CLASE_CAMPO, codigo && 'font-code text-sm', className)}
      {...resto}
    />
  );
});
