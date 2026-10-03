/**
 * Preferencias de la interfaz (rediseño, Etapa 0): el tema y la pausa de las
 * animaciones. Las dos se recuerdan por navegador y se reflejan en <html>:
 *
 *   data-theme="light" | "dark"          → src/styles/tokens.css
 *   data-movimiento="pausado" | "activo"  → src/styles/ui.css
 *
 * `index.html` aplica las dos antes del primer pintado, para que no parpadee.
 * `quieto` es lo que deben mirar los lienzos: verdadero si el usuario pausó o si
 * el sistema pide movimiento reducido.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, ReactNode } from 'react';

export type Tema = 'light' | 'dark';

const CLAVE_TEMA = 'kx-tema';
const CLAVE_MOVIMIENTO = 'kx-movimiento';
const CONSULTA_REDUCIDO = '(prefers-reduced-motion: reduce)';

interface Preferencias {
  tema: Tema;
  alternarTema: () => void;
  pausado: boolean;
  alternarPausa: () => void;
  /** El sistema operativo pide movimiento reducido. */
  reducido: boolean;
  /** Nada debe moverse: pausado o reducido. */
  quieto: boolean;
}

const PreferenciasContext = createContext<Preferencias | undefined>(undefined);

function leer(clave: string): string | null {
  try {
    return localStorage.getItem(clave);
  } catch {
    return null;
  }
}

function guardar(clave: string, valor: string) {
  try {
    localStorage.setItem(clave, valor);
  } catch {
    // Navegación privada o almacenamiento bloqueado: la preferencia dura la sesión.
  }
}

export function PreferenciasProvider({ children }: { children: ReactNode }) {
  const [tema, setTema] = useState<Tema>(() => (leer(CLAVE_TEMA) === 'dark' ? 'dark' : 'light'));
  const [pausado, setPausado] = useState<boolean>(() => leer(CLAVE_MOVIMIENTO) === 'pausado');
  const [reducido, setReducido] = useState<boolean>(
    () => typeof window !== 'undefined' && window.matchMedia(CONSULTA_REDUCIDO).matches,
  );

  useEffect(() => {
    document.documentElement.dataset.theme = tema;
    guardar(CLAVE_TEMA, tema);
  }, [tema]);

  useEffect(() => {
    document.documentElement.dataset.movimiento = pausado ? 'pausado' : 'activo';
    guardar(CLAVE_MOVIMIENTO, pausado ? 'pausado' : 'activo');
  }, [pausado]);

  useEffect(() => {
    const mq = window.matchMedia(CONSULTA_REDUCIDO);
    const alCambiar = () => setReducido(mq.matches);
    mq.addEventListener('change', alCambiar);
    return () => mq.removeEventListener('change', alCambiar);
  }, []);

  const alternarTema = useCallback(() => setTema((t) => (t === 'dark' ? 'light' : 'dark')), []);
  const alternarPausa = useCallback(() => setPausado((p) => !p), []);

  const valor = useMemo(
    () => ({ tema, alternarTema, pausado, alternarPausa, reducido, quieto: pausado || reducido }),
    [tema, alternarTema, pausado, alternarPausa, reducido],
  );

  return <PreferenciasContext.Provider value={valor}>{children}</PreferenciasContext.Provider>;
}

export function usePreferencias(): Preferencias {
  const ctx = useContext(PreferenciasContext);
  if (!ctx) throw new Error('usePreferencias debe usarse dentro de PreferenciasProvider');
  return ctx;
}
