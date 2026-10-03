/**
 * Botón de solo icono (mockup: .ib). `etiqueta` es obligatoria: es el nombre
 * accesible (aria-label) y el título al pasar el ratón. 36 × 36 px; en la
 * cabecera, 44 × 44.
 */
import { forwardRef, ButtonHTMLAttributes } from 'react';
import type { LucideIcon } from 'lucide-react';
import { cx } from './cx';
import { Spinner } from './Spinner';

export interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'aria-label'> {
  icon: LucideIcon;
  etiqueta: string;
  variant?: 'default' | 'danger' | 'cabecera';
  cargando?: boolean;
}

const VARIANTES = {
  default: 'h-9 w-9 text-ink-muted hover:bg-surface-2 hover:text-ink',
  danger: 'h-9 w-9 text-ink-muted hover:bg-err-bg hover:text-err',
  // Sobre la cabecera oscura, con su propio color de foco.
  cabecera: 'h-11 w-11 text-hdr-text hover:bg-nav-hover focus-visible:outline-focus-hdr',
};

// El icono crece con el botón: en la cabecera (76 px) uno de 20 px se ve perdido.
const ICONO = { default: 'h-5 w-5', danger: 'h-5 w-5', cabecera: 'h-5.5 w-5.5' };

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { icon: Icono, etiqueta, variant = 'default', cargando = false, type = 'button', disabled, className, title, ...resto },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      aria-label={etiqueta}
      title={title ?? etiqueta}
      disabled={disabled || cargando}
      aria-busy={cargando || undefined}
      className={cx(
        'inline-grid flex-none place-items-center rounded-control border border-transparent cursor-pointer',
        'motion-safe:transition-colors disabled:cursor-not-allowed disabled:opacity-50',
        VARIANTES[variant],
        className,
      )}
      {...resto}
    >
      {cargando ? <Spinner /> : <Icono aria-hidden="true" strokeWidth={1.8} className={ICONO[variant]} />}
    </button>
  );
});
