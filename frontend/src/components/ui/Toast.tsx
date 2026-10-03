/**
 * Avisos emergentes (mockup: .toasts / .toast). Sustituyen a los `alert()`
 * nativos para lo que se confirma de pasada: «Reporte guardado».
 *
 * - Una sola región `aria-live="polite"`, montada una vez por ToastProvider.
 * - Se van solos a los 4,5 s, salvo los de error, que esperan a que se cierren:
 *   un error que desaparece antes de leerlo es un error que no se vio.
 * - Al pasar el ratón o el foco por encima, no se van.
 * - Lo que el usuario TIENE que leer (un error al cargar) no va aquí: va en un
 *   Alert dentro de la página.
 */
import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { cx } from './cx';

export type TonoToast = 'ok' | 'info' | 'warn' | 'err';

interface Toast {
  id: number;
  tono: TonoToast;
  texto: ReactNode;
}

interface ToastApi {
  avisar: (texto: ReactNode, tono?: TonoToast) => void;
}

const ToastContext = createContext<ToastApi | undefined>(undefined);
const DURACION_MS = 4500;

const ICONOS: Record<TonoToast, LucideIcon> = { ok: CheckCircle2, info: Info, warn: AlertTriangle, err: XCircle };
// Fondo de tinta y texto del fondo, como en el mockup; el icono lleva el tono.
const ACENTOS: Record<TonoToast, string> = {
  ok: 'text-ok-bg',
  info: 'text-info-bg',
  warn: 'text-warn-bg',
  err: 'text-err-bg',
};

function Aviso({ toast, onCerrar }: { toast: Toast; onCerrar: (id: number) => void }) {
  const [enPausa, setEnPausa] = useState(false);
  const Icono = ICONOS[toast.tono];
  const fijo = toast.tono === 'err';

  useEffect(() => {
    if (fijo || enPausa) return;
    const t = setTimeout(() => onCerrar(toast.id), DURACION_MS);
    return () => clearTimeout(t);
  }, [fijo, enPausa, onCerrar, toast.id]);

  return (
    <div
      onMouseEnter={() => setEnPausa(true)}
      onMouseLeave={() => setEnPausa(false)}
      onFocus={() => setEnPausa(true)}
      onBlur={() => setEnPausa(false)}
      className="flex items-start gap-2.5 rounded-control bg-ink px-4 py-3 font-semibold text-canvas shadow-pop motion-safe:animate-pop"
    >
      <Icono aria-hidden="true" strokeWidth={1.8} className={cx('mt-0.5 h-5 w-5 flex-none', ACENTOS[toast.tono])} />
      <span className="flex-1">
        {toast.tono === 'err' && <span className="sr-only">Error: </span>}
        {toast.texto}
      </span>
      <button
        type="button"
        onClick={() => onCerrar(toast.id)}
        aria-label="Cerrar el aviso"
        title="Cerrar el aviso"
        className="-my-1 -mr-2 inline-grid h-8 w-8 flex-none place-items-center rounded-chico cursor-pointer hover:bg-canvas/15 focus-visible:outline-canvas"
      >
        <X aria-hidden="true" strokeWidth={1.8} className="h-4 w-4" />
      </button>
    </div>
  );
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [lista, setLista] = useState<Toast[]>([]);
  const siguiente = useRef(1);

  const cerrar = useCallback((id: number) => setLista((l) => l.filter((t) => t.id !== id)), []);
  const avisar = useCallback((texto: ReactNode, tono: TonoToast = 'ok') => {
    const id = siguiente.current++;
    setLista((l) => [...l.slice(-3), { id, tono, texto }]);
  }, []);
  const api = useMemo(() => ({ avisar }), [avisar]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      {createPortal(
        <div
          role="status"
          aria-live="polite"
          className="fixed bottom-4 right-4 z-aviso grid w-full max-w-sm gap-2 pl-8"
        >
          {lista.map((t) => (
            <Aviso key={t.id} toast={t} onCerrar={cerrar} />
          ))}
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast debe usarse dentro de ToastProvider');
  return ctx;
}
