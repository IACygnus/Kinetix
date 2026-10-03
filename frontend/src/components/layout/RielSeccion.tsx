/**
 * El riel de sección (mockup: .sub): las pantallas del módulo actual.
 *
 * - Desde 1100 px, columna a la izquierda, fija bajo la cabecera.
 * - Bajo 1100 px, fila de sub-pestañas encima del contenido, que se parte en
 *   varias líneas en vez de cortarse.
 *
 * Son ENLACES de navegación (cambian de ruta), no pestañas de WAI-ARIA: llevan
 * aria-current="page", no role="tab". Un módulo de una sola pantalla
 * (Dashboard, Ejecución) no tiene riel.
 */
import { Link } from 'react-router-dom';
import { cx } from '../ui/cx';
import { Modulo, Pantalla } from './navegacion';

interface RielProps {
  modulo: Modulo | null;
  pantalla: Pantalla | null;
}

export function RielSeccion({ modulo, pantalla }: RielProps) {
  if (!modulo?.pantallas?.length) return null;
  return (
    <nav
      aria-label={`Sección ${modulo.etiqueta}`}
      className={cx(
        // Bajo 1100 px: fila de sub-pestañas.
        'border-b border-line bg-canvas px-4 py-1.5 sm:px-6',
        // Desde 1100 px: riel vertical fijo.
        'nav:sticky nav:top-hdr nav:h-bajo-cabecera nav:w-riel nav:flex-none nav:overflow-y-auto nav:border-b-0 nav:px-3 nav:py-6',
      )}
    >
      <h2 className="hidden px-3 pb-2 font-body text-nota font-bold text-ink-muted nav:block">{modulo.etiqueta}</h2>
      <ul className="flex flex-wrap gap-0.5 nav:block nav:space-y-0.5">
        {modulo.pantallas.map((p) => {
          const actual = pantalla?.ruta === p.ruta;
          const Icono = p.icono;
          return (
            <li key={p.ruta}>
              <Link
                to={p.ruta}
                aria-current={actual ? 'page' : undefined}
                className={cx(
                  'flex min-h-10 items-center gap-2.5 rounded-control px-3 py-1 font-semibold no-underline nav:min-h-control',
                  'motion-safe:transition-colors',
                  actual
                    ? 'bg-primary text-on-primary nav:shadow-boton'
                    : 'text-ink-muted hover:bg-surface-2 hover:text-ink',
                )}
              >
                <Icono aria-hidden="true" strokeWidth={1.8} className="h-5 w-5 flex-none" />
                <span>{p.etiqueta}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
