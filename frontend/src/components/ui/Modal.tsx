/**
 * Ventana modal (mockup: .ovl + .dlg).
 *
 * - role="dialog", aria-modal y aria-labelledby al título (la auditoría 153
 *   encontró 1 modal con role="dialog" de 37).
 * - El foco entra al abrir (primer campo, o el botón de cerrar), queda atrapado
 *   con Tab / Mayús+Tab y vuelve al botón que la abrió al cerrar.
 * - Escape y la pulsación en el velo la cierran, salvo `bloqueado` (p. ej.
 *   mientras se guarda).
 * - Se monta en <body> por portal: ningún `overflow:hidden` de la pantalla la
 *   recorta.
 */
import { KeyboardEvent, ReactNode, RefObject, useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { cx } from './cx';
import { IconButton } from './IconButton';

const ENFOCABLES =
  'button:not([disabled]), [href], input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export interface ModalProps {
  abierto: boolean;
  onCerrar: () => void;
  titulo: ReactNode;
  children: ReactNode;
  pie?: ReactNode;
  ancho?: boolean;
  /** Impide cerrar con Escape, con el velo y con la X. */
  bloqueado?: boolean;
  /** Elemento que recibe el foco al abrir (por defecto, el primer campo). */
  focoInicial?: RefObject<HTMLElement>;
}

export function Modal({ abierto, onCerrar, titulo, children, pie, ancho, bloqueado, focoInicial }: ModalProps) {
  const idTitulo = useId();
  const caja = useRef<HTMLDivElement>(null);
  const previo = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!abierto) return;
    previo.current = document.activeElement as HTMLElement | null;
    const raiz = caja.current;
    const destino =
      focoInicial?.current ??
      raiz?.querySelector<HTMLElement>('[data-cuerpo] input, [data-cuerpo] select, [data-cuerpo] textarea') ??
      raiz?.querySelector<HTMLElement>('[data-pie] button') ??
      raiz?.querySelector<HTMLElement>(ENFOCABLES);
    destino?.focus();
    const desplazamiento = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = desplazamiento;
      if (previo.current && document.contains(previo.current)) previo.current.focus();
    };
    // focoInicial es un ref: no cambia entre renders.
  }, [abierto]);

  if (!abierto) return null;

  const alTeclear = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Escape' && !bloqueado) {
      e.stopPropagation();
      onCerrar();
      return;
    }
    if (e.key !== 'Tab' || !caja.current) return;
    const lista = Array.from(caja.current.querySelectorAll<HTMLElement>(ENFOCABLES)).filter((x) => x.offsetParent !== null);
    if (lista.length === 0) return;
    const primero = lista[0];
    const ultimo = lista[lista.length - 1];
    if (e.shiftKey && document.activeElement === primero) {
      e.preventDefault();
      ultimo.focus();
    } else if (!e.shiftKey && document.activeElement === ultimo) {
      e.preventDefault();
      primero.focus();
    }
  };

  return createPortal(
    <div
      className="fixed inset-0 z-modal grid place-items-center bg-scrim/60 p-4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !bloqueado) onCerrar();
      }}
    >
      <div
        ref={caja}
        role="dialog"
        aria-modal="true"
        aria-labelledby={idTitulo}
        onKeyDown={alTeclear}
        className={cx(
          'max-h-full w-full overflow-auto rounded-panel bg-surface text-ink shadow-pop motion-safe:animate-pop',
          ancho ? 'max-w-dialogo-ancho' : 'max-w-dialogo',
        )}
      >
        <div className="flex items-center justify-between gap-4 border-b border-line px-5 py-4">
          <h2 id={idTitulo} className="font-display text-h2 font-extrabold leading-tight tracking-display">
            {titulo}
          </h2>
          <IconButton icon={X} etiqueta="Cerrar" onClick={onCerrar} disabled={bloqueado} />
        </div>
        <div data-cuerpo className="grid gap-4 p-5">
          {children}
        </div>
        {pie && (
          <div data-pie className="flex flex-wrap justify-end gap-2 border-t border-line px-5 py-4">
            {pie}
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}
