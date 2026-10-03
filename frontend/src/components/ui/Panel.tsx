/**
 * Tarjeta de contenido (mockup: .panel, .panel-h, .panel-b). En Índigo claro
 * no lleva borde, solo sombra; en oscuro, borde (la sombra no se ve).
 *
 * `titulo` se pinta como h2 por defecto; `nivel` lo cambia para respetar la
 * jerarquía de la pantalla.
 */
import { ReactNode } from 'react';
import { cx } from './cx';

export interface PanelProps {
  titulo?: ReactNode;
  descripcion?: ReactNode;
  acciones?: ReactNode;
  nivel?: 2 | 3;
  /** Sin relleno interior: para tablas y listas que llegan al borde. */
  sinRelleno?: boolean;
  className?: string;
  children?: ReactNode;
  id?: string;
}

export function Panel({ titulo, descripcion, acciones, nivel = 2, sinRelleno, className, children, id }: PanelProps) {
  const Titulo = nivel === 2 ? 'h2' : 'h3';
  return (
    <section
      id={id}
      className={cx(
        'min-w-0 rounded-panel border border-transparent bg-surface text-ink shadow-card',
        'dark:border-line',
        className,
      )}
    >
      {(titulo || acciones) && (
        <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-6 pb-1 pt-5">
          <div className="min-w-0">
            {titulo && (
              <Titulo className="font-display text-h2 font-extrabold leading-tight tracking-display">{titulo}</Titulo>
            )}
            {descripcion && <p className="mt-0.5 text-sm text-ink-muted">{descripcion}</p>}
          </div>
          {acciones && <div className="flex flex-wrap items-center gap-2">{acciones}</div>}
        </header>
      )}
      {children !== undefined && <div className={cx(!sinRelleno && 'px-6 pb-6 pt-5')}>{children}</div>}
    </section>
  );
}
