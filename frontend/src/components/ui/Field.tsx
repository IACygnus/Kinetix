/**
 * Campo de formulario (mockup: .field): etiqueta, control, ayuda y error.
 *
 * El control se pasa como hijo con el mismo `id`, y su `aria-describedby` se
 * obtiene con `describedBy(id, ayuda, error)`: así un lector de pantalla lee la
 * ayuda y el error al llegar al control.
 */
import { ReactNode } from 'react';
import { cx } from './cx';

export const idsDeCampo = (id: string) => ({ ayuda: `${id}-ayuda`, error: `${id}-error` });

/** El valor de aria-describedby para un control con ayuda y/o error. */
export const describedBy = (id: string, ayuda?: ReactNode, error?: ReactNode): string | undefined => {
  const ids = idsDeCampo(id);
  const partes = [ayuda ? ids.ayuda : '', error ? ids.error : ''].filter(Boolean);
  return partes.length ? partes.join(' ') : undefined;
};

export interface FieldProps {
  id: string;
  etiqueta: ReactNode;
  obligatorio?: boolean;
  ayuda?: ReactNode;
  error?: ReactNode;
  className?: string;
  children: ReactNode;
}

export function Field({ id, etiqueta, obligatorio, ayuda, error, className, children }: FieldProps) {
  const ids = idsDeCampo(id);
  return (
    <div className={cx('grid min-w-0 content-start gap-1.5', className)}>
      <label htmlFor={id} className="text-sm font-bold text-ink">
        {etiqueta}
        {obligatorio && (
          <>
            <span className="text-err" aria-hidden="true"> *</span>
            <span className="sr-only"> (obligatorio)</span>
          </>
        )}
      </label>
      {children}
      {ayuda && (
        <p id={ids.ayuda} className="text-sm text-ink-muted">
          {ayuda}
        </p>
      )}
      {error && (
        <p id={ids.error} className="text-sm font-semibold text-err">
          {error}
        </p>
      )}
    </div>
  );
}
