/**
 * Layout — el armazón de Kinetix (rediseño, Etapa 0).
 *
 * Sustituye al menú lateral fijo de 288 px (Sidebar.tsx y Footer.tsx, borrados
 * en la Etapa 1) por el del mockup:
 *
 *   ┌──────────── cabecera: marca · módulos · buscar · pausa · tema · cuenta ┐
 *   │ riel de sección │ contenido (ancho máximo común, centrado)             │
 *
 * Bajo 1100 px los módulos van al menú desplegable y el riel pasa a
 * sub-pestañas encima del contenido.
 *
 * - Rutas, filtrado por rol e ítems: los de siempre (navegacion.ts).
 * - «Saltar al contenido» es lo primero que se enfoca con Tab.
 * - `<main>` ya no lleva `overflow-x-hidden`: lo que no cabía se cortaba en
 *   silencio (auditoría 153 §2.2). Ahora, si algo no cabe, se ve.
 * - El contenido va en `.tema-claro`: las pantallas aún no migradas están
 *   pintadas con la paleta clara de Tailwind y en tema oscuro serían
 *   ilegibles. El armazón sí sigue el tema. Cada etapa que migre una pantalla
 *   la sacará de ahí.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Cabecera } from './Cabecera';
import { RielSeccion } from './RielSeccion';
import { MenuMovil } from './MenuMovil';
import { BuscadorPantallas } from './BuscadorPantallas';
import { MenuUsuario } from './MenuUsuario';
import { modulosVisibles, ubicar } from './navegacion';

export default function Layout() {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const [menu, setMenu] = useState(false);
  const [buscador, setBuscador] = useState(false);
  const [cuenta, setCuenta] = useState(false);
  const principal = useRef<HTMLElement>(null);
  const primeraRuta = useRef(true);
  const botonMenu = useRef<HTMLElement | null>(null);

  const modulos = useMemo(() => modulosVisibles(user?.role), [user?.role]);
  const { modulo, pantalla } = useMemo(() => ubicar(pathname, modulos), [pathname, modulos]);

  // Ctrl + K (o Cmd + K) abre el buscador desde cualquier pantalla.
  useEffect(() => {
    const alTeclear = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setMenu(false);
        setBuscador(true);
      }
    };
    document.addEventListener('keydown', alTeclear);
    return () => document.removeEventListener('keydown', alTeclear);
  }, []);

  // Al cambiar de pantalla, el foco va al contenido (lo anuncia el lector de
  // pantalla) sin mover el desplazamiento. No en la primera carga.
  useEffect(() => {
    setMenu(false);
    if (primeraRuta.current) {
      primeraRuta.current = false;
      return;
    }
    principal.current?.focus({ preventScroll: true });
  }, [pathname]);

  // Si la ventana crece por encima de 1100 px con el menú abierto, se cierra.
  useEffect(() => {
    const mq = window.matchMedia('(min-width: 1100px)');
    const alCambiar = () => mq.matches && setMenu(false);
    mq.addEventListener('change', alCambiar);
    return () => mq.removeEventListener('change', alCambiar);
  }, []);

  const cerrarMenu = () => {
    setMenu(false);
    botonMenu.current?.focus();
  };

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <a
        href="#contenido"
        className="sr-only z-modal rounded-control border border-line-strong bg-surface px-4 py-2 text-ink focus:not-sr-only focus:fixed focus:left-2 focus:top-2"
      >
        Saltar al contenido
      </a>

      <Cabecera
        modulos={modulos}
        moduloActual={modulo}
        menuAbierto={menu}
        onMenu={() => {
          botonMenu.current = document.activeElement as HTMLElement | null;
          setMenu(true);
        }}
        onBuscar={() => setBuscador(true)}
        onUsuario={() => setCuenta(true)}
      />

      <div className="nav:flex">
        <RielSeccion modulo={modulo} pantalla={pantalla} />
        <main
          ref={principal}
          id="contenido"
          tabIndex={-1}
          className="tema-claro min-w-0 flex-1 bg-canvas px-4 pb-16 pt-6 text-ink focus:outline-none sm:px-6 lg:px-8"
        >
          <div className="mx-auto w-full max-w-pagina">
            <Outlet />
          </div>
        </main>
      </div>

      <MenuMovil
        abierto={menu}
        onCerrar={cerrarMenu}
        modulos={modulos}
        moduloActual={modulo}
        pantallaActual={pantalla}
      />
      <BuscadorPantallas abierto={buscador} onCerrar={() => setBuscador(false)} modulos={modulos} />
      <MenuUsuario abierto={cuenta} onCerrar={() => setCuenta(false)} />
    </div>
  );
}
