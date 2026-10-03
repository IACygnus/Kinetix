/**
 * Control segmentado (mockup: .seg): elegir UNA opción que cambia la vista en
 * el sitio (Ambas · Promedio · Máximo). No es una pestaña: no hay panel, así que
 * es un grupo de botones con aria-pressed.
 */
import { ReactNode } from 'react';
import { cx } from './cx';

export interface OpcionSegmentada<V extends string> {
  valor: V;
  etiqueta: ReactNode;
}

export interface SegmentedProps<V extends string> {
  etiqueta: string;
  opciones: OpcionSegmentada<V>[];
  valor: V;
  onCambiar: (v: V) => void;
  disabled?: boolean;
  className?: string;
}

export function Segmented<V extends string>({ etiqueta, opciones, valor, onCambiar, disabled, className }: SegmentedProps<V>) {
  return (
    <div
      role="group"
      aria-label={etiqueta}
      className={cx('inline-flex flex-wrap gap-1 rounded-control bg-surface-2 p-1', className)}
    >
      {opciones.map((o) => {
        const sel = o.valor === valor;
        return (
          <button
            key={o.valor}
            type="button"
            aria-pressed={sel}
            disabled={disabled}
            onClick={() => onCambiar(o.valor)}
            className={cx(
              'min-h-8.5 rounded-chico px-3.5 font-semibold cursor-pointer disabled:cursor-not-allowed disabled:opacity-50',
              sel ? 'bg-surface text-ink shadow-seg' : 'text-ink-muted hover:text-ink',
            )}
          >
            {o.etiqueta}
          </button>
        );
      })}
    </div>
  );
}
