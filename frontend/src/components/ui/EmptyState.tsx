/**
 * Estado vacío (mockup: .empty). Solo cuando la petición SALIÓ BIEN y no hay
 * nada: si falló, va ErrorState; si está en curso, LoadingState.
 */
import { ReactNode } from 'react';
import { Inbox } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { cx } from './cx';

export interface EmptyStateProps {
  icon?: LucideIcon;
  titulo: ReactNode;
  texto?: ReactNode;
  accion?: ReactNode;
  className?: string;
}

export function EmptyState({ icon: Icono = Inbox, titulo, texto, accion, className }: EmptyStateProps) {
  return (
    <div className={cx('grid justify-items-center gap-3 px-4 py-12 text-center', className)}>
      <Icono aria-hidden="true" strokeWidth={1.8} className="h-11 w-11 text-ink-muted" />
      <p className="font-display text-destacado font-extrabold text-ink">{titulo}</p>
      {texto && <p className="max-w-md text-ink-muted">{texto}</p>}
      {accion}
    </div>
  );
}
