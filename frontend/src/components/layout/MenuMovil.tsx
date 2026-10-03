/**
 * El menú desplegable bajo 1100 px (mockup: .app.drawer .side).
 *
 * Panel a la izquierda con todos los módulos y sus pantallas (los módulos se
 * pliegan y despliegan), sobre un velo que lo cierra. Escape lo cierra y
 * devuelve el foco al botón de menú; al abrir, el foco entra en el primer
 * enlace y queda dentro mientras esté abierto.
 */
import { KeyboardEvent, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight, X } from 'lucide-react';
import { IconButton } from '../ui/IconButton';
import { cx } from '../ui/cx';
import { Marca } from './Marca';
import { Modulo, Pantalla, rutaDeModulo } from './navegacion';

interface MenuMovilProps {
  abierto: boolean;
  onCerrar: () => void;
  modulos: Modulo[];
  moduloActual: Modulo | null;
  pantallaActual: Pantalla | null;
}

const ENFOCABLES = 'a[href], button:not([disabled])';

export function MenuMovil({ abierto, onCerrar, modulos, moduloActual, pantallaActual }: MenuMovilProps) {
  const panel = useRef<HTMLDivElement>(null);
  const [desplegados, setDesplegados] = useState<Set<string>>(new Set());

  // Al abrir: el módulo actual desplegado y el foco dentro.
  useEffect(() => {
    if (!abierto) return;
    if (moduloActual) setDesplegados((d) => new Set(d).add(moduloActual.id));
    const id = requestAnimationFrame(() => panel.current?.querySelector<HTMLElement>('nav a, nav button')?.focus());
    return () => cancelAnimationFrame(id);
  }, [abierto, moduloActual]);

  if (!abierto) return null;

  const alternar = (id: string) =>
    setDesplegados((d) => {
      const n = new Set(d);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

  const alTeclear = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Escape') {
      e.stopPropagation();
      onCerrar();
      return;
    }
    if (e.key !== 'Tab' || !panel.current) return;
    const lista = Array.from(panel.current.querySelectorAll<HTMLElement>(ENFOCABLES));
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

  const clase = (actual: boolean) =>
    cx(
      'flex w-full min-h-control items-center gap-3 rounded-control px-3 py-1 text-left font-semibold no-underline cursor-pointer',
      'focus-visible:outline-focus-nav',
      actual ? 'bg-nav-active-bg text-nav-active-text' : 'text-nav-muted hover:bg-nav-hover hover:text-nav-text',
    );

  return (
    <div className="fixed inset-0 z-menu nav:hidden">
      <button
        type="button"
        tabIndex={-1}
        aria-label="Cerrar el menú"
        onClick={onCerrar}
        className="absolute inset-0 h-full w-full cursor-default bg-scrim/55"
      />
      <div
        ref={panel}
        id="menu-movil"
        role="dialog"
        aria-modal="true"
        aria-label="Menú principal"
        onKeyDown={alTeclear}
        className="absolute inset-y-0 left-0 flex w-76 max-w-full flex-col overflow-y-auto bg-nav-bg text-nav-text shadow-pop"
      >
        <div className="flex min-h-hdr items-center justify-between gap-2 px-4">
          <Marca />
          <IconButton icon={X} etiqueta="Cerrar el menú" variant="cabecera" onClick={onCerrar} />
        </div>
        <nav aria-label="Principal" className="flex-1 px-2.5 py-1.5">
          <ul className="space-y-0.5">
            {modulos.map((m) => {
              const Icono = m.icono;
              if (!m.pantallas) {
                const actual = moduloActual?.id === m.id;
                return (
                  <li key={m.id}>
                    <Link to={rutaDeModulo(m)} onClick={onCerrar} aria-current={actual ? 'page' : undefined} className={clase(actual)}>
                      <Icono aria-hidden="true" strokeWidth={1.8} className="h-5 w-5 flex-none" />
                      {m.etiqueta}
                    </Link>
                  </li>
                );
              }
              const abiertoModulo = desplegados.has(m.id);
              return (
                <li key={m.id}>
                  <button
                    type="button"
                    aria-expanded={abiertoModulo}
                    onClick={() => alternar(m.id)}
                    className={cx(clase(false), moduloActual?.id === m.id && 'text-nav-text')}
                  >
                    <Icono aria-hidden="true" strokeWidth={1.8} className="h-5 w-5 flex-none" />
                    {m.etiqueta}
                    <ChevronRight
                      aria-hidden="true"
                      strokeWidth={1.8}
                      className={cx('ml-auto h-4 w-4 motion-safe:transition-transform', abiertoModulo && 'rotate-90')}
                    />
                  </button>
                  {abiertoModulo && (
                    <ul className="mb-1.5 ml-5.5 mt-0.5 space-y-0.5 border-l border-nav-border pl-2">
                      {m.pantallas.map((p) => {
                        const actual = pantallaActual?.ruta === p.ruta;
                        return (
                          <li key={p.ruta}>
                            <Link
                              to={p.ruta}
                              onClick={onCerrar}
                              aria-current={actual ? 'page' : undefined}
                              className={cx(clase(actual), 'min-h-9 text-control font-medium')}
                            >
                              {p.etiqueta}
                            </Link>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
        </nav>
        <p className="border-t border-nav-border px-4.5 py-3.5 text-xs text-nav-label">SQA Kinetix Pro © {new Date().getFullYear()}</p>
      </div>
    </div>
  );
}
