/**
 * Insignia de estado (mockup: .badge). El tono nunca va solo: el texto dice lo
 * mismo que el color, y el icono es opcional.
 */
import { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { cx } from './cx';

export type TonoBadge = 'neutral' | 'ok' | 'warn' | 'err' | 'info' | 'primary';

const TONOS: Record<TonoBadge, string> = {
  neutral: 'bg-surface-2 text-ink',
  ok: 'bg-ok-bg text-ok',
  warn: 'bg-warn-bg text-warn',
  err: 'bg-err-bg text-err',
  info: 'bg-info-bg text-info',
  primary: 'bg-primary-soft text-on-primary-soft',
};

export interface BadgeProps {
  tono?: TonoBadge;
  icon?: LucideIcon;
  className?: string;
  children: ReactNode;
}

export function Badge({ tono = 'neutral', icon: Icono, className, children }: BadgeProps) {
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1 whitespace-nowrap rounded-pill px-2.5 py-0.5 text-nota font-bold',
        TONOS[tono],
        className,
      )}
    >
      {Icono && <Icono aria-hidden="true" strokeWidth={2.6} className="h-3.5 w-3.5" />}
      {children}
    </span>
  );
}
