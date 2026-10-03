/**
 * Aviso dentro de la página (mockup: .alert). Cuatro tonos, uno por significado:
 * la auditoría 153 contó ~50 firmas y amber/yellow y green/emerald mezclados.
 *
 * El de error se anuncia (role="alert"); los demás, con cortesía (role="status").
 * Si se puede cerrar, el botón dice qué cierra.
 */
import { ReactNode } from 'react';
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { cx } from './cx';

export type TonoAviso = 'info' | 'ok' | 'warn' | 'err';

const TONOS: Record<TonoAviso, { clase: string; icono: LucideIcon }> = {
  info: { clase: 'bg-info-bg text-info', icono: Info },
  ok: { clase: 'bg-ok-bg text-ok', icono: CheckCircle2 },
  warn: { clase: 'bg-warn-bg text-warn', icono: AlertTriangle },
  err: { clase: 'bg-err-bg text-err', icono: XCircle },
};

export interface AlertProps {
  tono?: TonoAviso;
  titulo?: ReactNode;
  children?: ReactNode;
  /** Botón o enlace a la derecha (p. ej. «Reintentar»). */
  accion?: ReactNode;
  onCerrar?: () => void;
  className?: string;
}

export function Alert({ tono = 'info', titulo, children, accion, onCerrar, className }: AlertProps) {
  const { clase, icono: Icono } = TONOS[tono];
  return (
    <div
      role={tono === 'err' ? 'alert' : 'status'}
      className={cx('flex flex-wrap items-start gap-3 rounded-control px-4 py-3.5', clase, className)}
    >
      <Icono aria-hidden="true" strokeWidth={1.8} className="mt-0.5 h-5 w-5 flex-none" />
      <div className="min-w-48 flex-1">
        {titulo && <p className="font-bold">{titulo}</p>}
        {children && <div className="text-ink">{children}</div>}
      </div>
      {accion && <div className="flex flex-wrap items-center gap-2">{accion}</div>}
      {onCerrar && (
        <button
          type="button"
          onClick={onCerrar}
          aria-label="Cerrar el aviso"
          title="Cerrar el aviso"
          className="inline-grid h-8 w-8 flex-none place-items-center rounded-chico cursor-pointer hover:bg-surface/60"
        >
          <X aria-hidden="true" strokeWidth={1.8} className="h-5 w-5" />
        </button>
      )}
    </div>
  );
}
