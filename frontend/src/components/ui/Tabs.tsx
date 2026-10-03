/**
 * Pestañas (mockup Índigo: .tabs como píldora sobre surface-2).
 *
 * Patrón WAI-ARIA de pestañas con activación automática:
 *   role="tablist" / "tab" / "tabpanel", aria-selected, aria-controls,
 *   un solo tabindex=0 (el de la activa) y flechas, Inicio y Fin para moverse.
 * La auditoría 153 encontró 11 implementaciones y ninguna con role="tab".
 */
import { KeyboardEvent, ReactNode, useRef } from 'react';
import { cx } from './cx';

export interface Pestana {
  id: string;
  etiqueta: ReactNode;
  /** Cifra opcional junto a la etiqueta (mockup: .count). */
  cuenta?: number;
}

export interface TabsProps {
  /** Prefijo único para los ids de pestañas y paneles. */
  idBase: string;
  etiqueta: string;
  pestanas: Pestana[];
  activa: string;
  onCambiar: (id: string) => void;
  className?: string;
}

export const idPestana = (idBase: string, id: string) => `${idBase}-tab-${id}`;
export const idPanel = (idBase: string, id: string) => `${idBase}-panel-${id}`;

export function Tabs({ idBase, etiqueta, pestanas, activa, onCambiar, className }: TabsProps) {
  const refs = useRef<Array<HTMLButtonElement | null>>([]);

  const alTeclear = (e: KeyboardEvent<HTMLButtonElement>, i: number) => {
    const n = pestanas.length;
    const destino =
      e.key === 'ArrowRight' ? (i + 1) % n
      : e.key === 'ArrowLeft' ? (i - 1 + n) % n
      : e.key === 'Home' ? 0
      : e.key === 'End' ? n - 1
      : -1;
    if (destino < 0) return;
    e.preventDefault();
    onCambiar(pestanas[destino].id);
    refs.current[destino]?.focus();
  };

  return (
    <div
      role="tablist"
      aria-label={etiqueta}
      className={cx('flex w-fit max-w-full flex-wrap gap-1 rounded-control bg-surface-2 p-1', className)}
    >
      {pestanas.map((p, i) => {
        const sel = p.id === activa;
        return (
          <button
            key={p.id}
            ref={(el) => (refs.current[i] = el)}
            type="button"
            role="tab"
            id={idPestana(idBase, p.id)}
            aria-selected={sel}
            aria-controls={idPanel(idBase, p.id)}
            tabIndex={sel ? 0 : -1}
            onClick={() => onCambiar(p.id)}
            onKeyDown={(e) => alTeclear(e, i)}
            className={cx(
              'inline-flex min-h-9 items-center gap-2 rounded-chico px-4 font-semibold cursor-pointer',
              sel ? 'bg-surface text-ink shadow-seg' : 'text-ink-muted hover:text-ink',
            )}
          >
            {p.etiqueta}
            {p.cuenta !== undefined && (
              <span className="rounded-pill bg-surface-2 px-1.5 py-px font-num text-xs font-bold tabular-nums text-ink">
                {p.cuenta}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

export interface TabPanelProps {
  idBase: string;
  id: string;
  activa: string;
  children: ReactNode;
  className?: string;
}

/** El contenido de una pestaña. Oculto (no desmontado) si no es la activa. */
export function TabPanel({ idBase, id, activa, children, className }: TabPanelProps) {
  return (
    <div
      role="tabpanel"
      id={idPanel(idBase, id)}
      aria-labelledby={idPestana(idBase, id)}
      hidden={id !== activa}
      tabIndex={0}
      className={className}
    >
      {children}
    </div>
  );
}
