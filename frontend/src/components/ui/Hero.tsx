/**
 * Bloque destacado de la cabecera de un módulo (mockup: .hero en Índigo:
 * degradado hero-bg → hero-2 y el lienzo de carga detrás).
 *
 * Sustituye a las 7 copias del «hero» navy que encontró la auditoría 153. El
 * lienzo es decorativo y se queda quieto con la pausa o con movimiento
 * reducido. El texto va siempre por encima, con su propio contraste.
 */
import { ReactNode } from 'react';
import { cx } from './cx';
import { LoadFx } from './LoadFx';

export interface HeroProps {
  /** Línea pequeña encima del título (mockup: .hello). */
  antetitulo?: ReactNode;
  titulo: ReactNode;
  children?: ReactNode;
  acciones?: ReactNode;
  /** Con lienzo animado (por defecto sí). */
  animado?: boolean;
  /** El lienzo dibuja la escalera de usuarios. */
  rampa?: boolean;
  className?: string;
}

export function Hero({ antetitulo, titulo, children, acciones, animado = true, rampa = true, className }: HeroProps) {
  return (
    <section
      className={cx(
        'relative isolate grid gap-5 overflow-hidden rounded-panel bg-gradient-to-br from-hero-bg to-hero-2 p-6 text-hero-text sm:p-9',
        className,
      )}
    >
      {animado && <LoadFx escena="hero" rampa={rampa} className="-z-10" />}
      <div className="min-w-0">
        {antetitulo && <p className="mb-1 text-destacado font-bold text-hero-muted">{antetitulo}</p>}
        <h1 className="font-display text-3xl font-extrabold leading-tight tracking-display text-hero-text lg:text-4xl">
          {titulo}
        </h1>
        {children && <div className="mt-2 max-w-2xl text-hero-muted">{children}</div>}
      </div>
      {acciones && <div className="flex flex-wrap items-center gap-2.5">{acciones}</div>}
    </section>
  );
}
