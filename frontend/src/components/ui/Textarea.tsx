/** Área de texto (mockup: textarea.in). Redimensionable solo en vertical. */
import { forwardRef, TextareaHTMLAttributes } from 'react';
import { cx } from './cx';
import { CLASE_CAMPO } from './campo';

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalido?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { invalido, className, rows = 4, ...resto },
  ref,
) {
  return (
    <textarea
      ref={ref}
      rows={rows}
      aria-invalid={invalido || undefined}
      className={cx(CLASE_CAMPO, 'resize-y py-2.5 leading-normal', className)}
      {...resto}
    />
  );
});
