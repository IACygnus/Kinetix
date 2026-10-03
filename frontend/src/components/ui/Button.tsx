/**
 * Botón (mockup: .btn). Un solo primario por pantalla.
 *
 * - `type` explícito, por defecto "button": la auditoría 153 encontró 401 de 477
 *   botones sin `type`, que dentro de un formulario lo envían sin querer.
 * - `cargando` lo deshabilita, marca aria-busy y pone el giro delante del texto.
 * - Altura mínima 42 px (sm: 32 px): por encima de los 24 px de WCAG 2.5.8.
 */
import { forwardRef, ButtonHTMLAttributes } from 'react';
import type { LucideIcon } from 'lucide-react';
import { cx } from './cx';
import { Spinner } from './Spinner';

export type VarianteBoton = 'primary' | 'cta' | 'secondary' | 'ghost' | 'danger' | 'hero' | 'hero-outline';
export type TamanoBoton = 'sm' | 'md' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: VarianteBoton;
  size?: TamanoBoton;
  icon?: LucideIcon;
  cargando?: boolean;
  /** Ocupa todo el ancho de su contenedor. */
  bloque?: boolean;
}

// El color del borde lo pone SIEMPRE la variante: con un `border-transparent`
// común, el orden del CSS generado decidía y el secundario perdía el suyo.
const VARIANTES: Record<VarianteBoton, string> = {
  primary: 'border-transparent bg-primary text-on-primary shadow-boton hover:bg-primary-hover',
  cta: 'border-transparent bg-cta text-on-cta shadow-boton hover:bg-cta-hover',
  secondary: 'border-line-strong bg-surface text-ink hover:bg-surface-2',
  ghost: 'border-transparent text-link hover:bg-surface-2',
  danger: 'border-transparent bg-danger text-on-danger hover:bg-danger/90',
  // Sobre el degradado del Hero: el foco cambia a su color propio (blanco).
  hero: 'border-transparent bg-hero-text text-hero-bg hover:bg-hero-text/90 focus-visible:outline-focus-hero',
  'hero-outline': 'border-hero-muted text-hero-text hover:bg-hero-text/10 focus-visible:outline-focus-hero',
};

const TAMANOS: Record<TamanoBoton, string> = {
  sm: 'min-h-control-sm px-3 py-0.5 text-sm',
  md: 'min-h-control px-4.5 py-1 text-control',
  lg: 'min-h-control-lg px-6 py-2 text-base',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'secondary', size = 'md', icon: Icono, cargando = false, bloque = false, type = 'button',
    disabled, className, children, ...resto },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || cargando}
      aria-busy={cargando || undefined}
      className={cx(
        'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-control border',
        'font-body font-bold cursor-pointer',
        'motion-safe:transition-colors motion-safe:active:translate-y-px',
        // Cargando no es «inactivo»: el texto («Guardando…») tiene que leerse,
        // así que no se atenúa; solo cambia el cursor.
        cargando ? 'disabled:cursor-wait' : 'disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none',
        VARIANTES[variant],
        TAMANOS[size],
        bloque && 'w-full',
        className,
      )}
      {...resto}
    >
      {cargando ? <Spinner /> : Icono && <Icono aria-hidden="true" strokeWidth={1.8} className="h-5 w-5 flex-none" />}
      {children}
    </button>
  );
});
