/**
 * Zona de carga de archivos (mockup: .drop con «hormigas» en el borde).
 * Una sola, para las 5 que la auditoría 153 encontró.
 *
 * - Es un <label> que envuelve un <input type="file"> visualmente oculto: se
 *   abre con clic, Intro o espacio, y el lector de pantalla lo anuncia como
 *   selector de archivos con su etiqueta.
 * - Arrastrar y soltar es un atajo, no el único camino.
 * - `aceptar` filtra en el diálogo; la validación de verdad (extensión, número,
 *   tamaño) es de la pantalla, que muestra su error en `error`.
 */
import { ChangeEvent, DragEvent, ReactNode, useId, useState } from 'react';
import { Upload } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { cx } from './cx';

export interface DropzoneProps {
  titulo: ReactNode;
  ayuda?: ReactNode;
  aceptar?: string;
  multiple?: boolean;
  disabled?: boolean;
  error?: ReactNode;
  icon?: LucideIcon;
  onArchivos: (archivos: File[]) => void;
  className?: string;
}

export function Dropzone({
  titulo, ayuda, aceptar, multiple, disabled, error, icon: Icono = Upload, onArchivos, className,
}: DropzoneProps) {
  const id = useId();
  const [sobre, setSobre] = useState(false);

  const alElegir = (e: ChangeEvent<HTMLInputElement>) => {
    const lista = Array.from(e.target.files ?? []);
    if (lista.length) onArchivos(lista);
    // Permite volver a elegir el mismo archivo.
    e.target.value = '';
  };

  const alSoltar = (e: DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    setSobre(false);
    if (disabled) return;
    const lista = Array.from(e.dataTransfer.files);
    if (lista.length) onArchivos(multiple ? lista : lista.slice(0, 1));
  };

  return (
    <div className={cx('grid gap-1.5', className)}>
      <label
        htmlFor={id}
        data-sobre={sobre}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setSobre(true);
        }}
        onDragLeave={() => setSobre(false)}
        onDrop={alSoltar}
        className={cx(
          'kx-drop relative grid justify-items-center gap-1.5 rounded-panel bg-surface px-4 py-8 text-center',
          'focus-within:outline focus-within:outline-3 focus-within:outline-offset-2 focus-within:outline-focus',
          disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer hover:bg-primary-soft',
          sobre && 'bg-primary-soft',
          error ? 'ring-2 ring-err' : undefined,
        )}
      >
        <svg className="kx-hormigas pointer-events-none absolute inset-0 h-full w-full overflow-visible" aria-hidden="true">
          <rect />
        </svg>
        <Icono aria-hidden="true" strokeWidth={1.8} className="h-9 w-9 text-link motion-safe:animate-flota" />
        <strong className="font-display text-destacado">{titulo}</strong>
        {ayuda && <span className="text-sm text-ink-muted">{ayuda}</span>}
        <input
          id={id}
          type="file"
          accept={aceptar}
          multiple={multiple}
          disabled={disabled}
          onChange={alElegir}
          aria-invalid={error ? true : undefined}
          className="sr-only"
        />
      </label>
      {error && (
        <p role="alert" className="text-sm font-semibold text-err">
          {error}
        </p>
      )}
    </div>
  );
}
