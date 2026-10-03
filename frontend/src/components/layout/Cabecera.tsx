/**
 * La cabecera del armazón (mockup: «Armazón de Telemetría aplicado a Índigo»).
 *
 *   [menú*] [marca] [módulos…]          [buscar] [pausa] [tema] [usuario]
 *
 * (*) El botón de menú solo aparece bajo 1100 px, cuando los módulos se van
 * al menú desplegable. Bajo 900 px se esconden el nombre del usuario y el
 * atajo Ctrl K. Entre 1100 y 1500 px el nombre y el rol también se esconden
 * y queda solo el avatar (con el nombre en aria-label y title), para que los
 * siete módulos del admin quepan en UNA línea. Todo lo de la derecha son
 * botones de 40 px.
 */
import { Link } from 'react-router-dom';
import { Menu, Moon, Pause, Play, Search, Sun } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { usePreferencias } from '../../context/PreferenciasContext';
import { nombreRol } from '../../config/roles';
import { IconButton } from '../ui/IconButton';
import { cx } from '../ui/cx';
import { Marca } from './Marca';
import { Modulo, rutaDeModulo } from './navegacion';

interface CabeceraProps {
  modulos: Modulo[];
  moduloActual: Modulo | null;
  menuAbierto: boolean;
  onMenu: () => void;
  onBuscar: () => void;
  onUsuario: () => void;
}

export function Cabecera({ modulos, moduloActual, menuAbierto, onMenu, onBuscar, onUsuario }: CabeceraProps) {
  const { user } = useAuth();
  const { tema, alternarTema, pausado, alternarPausa } = usePreferencias();
  const oscuro = tema === 'dark';

  return (
    <header className="sticky top-0 z-cabecera flex min-h-hdr items-center gap-2 bg-hdr-bg px-4 py-2 text-hdr-text sm:px-6 lg:px-8">
      <IconButton
        icon={Menu}
        etiqueta="Abrir el menú"
        variant="cabecera"
        aria-expanded={menuAbierto}
        aria-controls="menu-movil"
        onClick={onMenu}
        className="nav:hidden"
      />
      <Marca />

      <nav aria-label="Módulos" className="hidden min-w-0 flex-1 nav:block">
        <ul className="flex flex-wrap gap-0.5">
          {modulos.map((m) => {
            const actual = moduloActual?.id === m.id;
            return (
              <li key={m.id}>
                <Link
                  to={rutaDeModulo(m)}
                  aria-current={actual ? 'true' : undefined}
                  className={cx(
                    'inline-flex min-h-11 items-center whitespace-nowrap rounded-control px-3 text-base font-semibold no-underline',
                    'motion-safe:transition-colors focus-visible:outline-focus-hdr',
                    actual ? 'bg-nav-active-bg text-nav-active-text' : 'text-nav-muted hover:bg-nav-hover hover:text-nav-text',
                  )}
                >
                  {m.etiqueta}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="ml-auto flex flex-none items-center gap-1">
        <button
          type="button"
          onClick={onBuscar}
          aria-label="Buscar una pantalla (Ctrl + K)"
          title="Buscar una pantalla (Ctrl + K)"
          aria-haspopup="dialog"
          className="flex min-h-11 items-center gap-2 rounded-control border border-nav-border bg-nav-hover px-3 text-nav-muted cursor-pointer hover:text-nav-text focus-visible:outline-focus-hdr"
        >
          <Search aria-hidden="true" strokeWidth={1.8} className="h-5.5 w-5.5" />
          <kbd className="hidden rounded border border-nav-muted px-1.5 font-code text-mini font-semibold cabecera:inline nav:hidden amplia:inline">
            Ctrl K
          </kbd>
        </button>
        <IconButton
          icon={pausado ? Play : Pause}
          etiqueta={pausado ? 'Reanudar animaciones' : 'Pausar animaciones'}
          aria-pressed={pausado}
          variant="cabecera"
          onClick={alternarPausa}
        />
        <IconButton
          icon={oscuro ? Sun : Moon}
          etiqueta={oscuro ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro'}
          variant="cabecera"
          onClick={alternarTema}
        />
        <button
          type="button"
          onClick={onUsuario}
          aria-haspopup="dialog"
          aria-label={`Cuenta de ${user?.full_name || 'usuario'}`}
          title={`${user?.full_name || 'Usuario'} · ${nombreRol(user?.role)}`}
          className="flex items-center gap-2.5 rounded-control px-1.5 py-1 text-left text-sm leading-tight cursor-pointer hover:bg-nav-hover focus-visible:outline-focus-hdr"
        >
          <span className="hidden max-w-60 cabecera:block nav:hidden amplia:block">
            <span className="block truncate font-semibold" title={user?.full_name}>
              {user?.full_name || 'Usuario'}
            </span>
            <small className="block text-hdr-muted">{nombreRol(user?.role)}</small>
          </span>
          <span
            aria-hidden="true"
            className="inline-grid h-10 w-10 flex-none place-items-center rounded-pill bg-primary font-display font-extrabold text-on-primary"
          >
            {user?.full_name?.charAt(0)?.toUpperCase() || 'U'}
          </span>
        </button>
      </div>
    </header>
  );
}
