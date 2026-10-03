/**
 * Clases comunes de Input, Select y Textarea (mockup: .in): una altura (42 px) y
 * un foco. La auditoría 153 contó 8 alturas y 9 colores de foco distintos.
 * El error se pinta con aria-invalid, que además lo anuncia.
 */
export const CLASE_CAMPO =
  'w-full min-h-control rounded-control border border-line-strong bg-surface px-3.5 py-1 text-ink ' +
  'placeholder:text-ink-muted ' +
  'disabled:cursor-not-allowed disabled:bg-surface-2 disabled:text-ink-muted ' +
  'aria-invalid:border-err aria-invalid:ring-1 aria-invalid:ring-err';
