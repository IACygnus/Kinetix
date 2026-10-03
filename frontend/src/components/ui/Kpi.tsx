/**
 * Indicador (mockup: .kpi). Cifra grande en tabular-nums para que no baile.
 *
 * Regla del plan (auditoría 153 §4.1): un indicador SIN dato no enseña un 0.
 * Si `valor` es null o undefined se pinta «—» y un texto oculto que lo dice.
 */
import { ReactNode } from 'react';
import { cx } from './cx';

export type TonoNota = 'neutral' | 'ok' | 'warn' | 'err';

const TONOS_NOTA: Record<TonoNota, string> = {
  neutral: 'text-ink-muted',
  ok: 'text-ok',
  warn: 'text-warn',
  err: 'text-err',
};

export interface KpiProps {
  etiqueta: ReactNode;
  valor: ReactNode | null | undefined;
  unidad?: ReactNode;
  nota?: ReactNode;
  tonoNota?: TonoNota;
  compacto?: boolean;
  className?: string;
}

export function Kpi({ etiqueta, valor, unidad, nota, tonoNota = 'neutral', compacto, className }: KpiProps) {
  const sinDato = valor === null || valor === undefined;
  return (
    <div
      className={cx(
        'relative min-w-0 rounded-panel border border-transparent bg-surface px-5 py-4.5 shadow-card dark:border-line',
        className,
      )}
    >
      <p className="text-sm font-semibold text-ink-muted">{etiqueta}</p>
      <p
        className={cx(
          'font-display font-extrabold leading-tight tracking-display tabular-nums break-words',
          compacto ? 'text-2xl' : 'text-kpi',
        )}
      >
        {sinDato ? (
          <>
            <span aria-hidden="true">—</span>
            <span className="sr-only">Sin dato</span>
          </>
        ) : (
          valor
        )}
        {!sinDato && unidad && (
          <small className="ml-1 text-sm font-semibold tracking-normal text-ink-muted">{unidad}</small>
        )}
      </p>
      {nota && <p className={cx('mt-0.5 text-sm font-semibold', TONOS_NOTA[tonoNota])}>{nota}</p>}
    </div>
  );
}
