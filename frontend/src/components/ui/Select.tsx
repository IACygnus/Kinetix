/**
 * Lista desplegable nativa con el aspecto de los campos. Nativa a propósito:
 * teclado, lector de pantalla y móvil funcionan sin código propio.
 */
import { forwardRef, SelectHTMLAttributes } from 'react';
import { cx } from './cx';
import { CLASE_CAMPO } from './campo';

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  invalido?: boolean;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { invalido, className, children, ...resto },
  ref,
) {
  return (
    <select
      ref={ref}
      aria-invalid={invalido || undefined}
      className={cx(CLASE_CAMPO, 'cursor-pointer pr-8', className)}
      {...resto}
    >
      {children}
    </select>
  );
});
