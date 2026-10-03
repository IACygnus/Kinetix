/**
 * El lienzo animado: una prueba de carga simulada, en <canvas> propio y sin
 * dependencias. Dos escenas, portadas del mockup:
 *
 *   'login' (AFTER.login): las peticiones cruzan la pantalla; cuando el sistema
 *     se satura van más lentas, fallan en ámbar y el trazo del percentil 90
 *     supera el criterio. Informa sus cifras por `onLectura` cada 0,2 s.
 *   'hero' (zz-motion → fxHero): peticiones que cruzan y, con `rampa`, la
 *     escalera de usuarios que sube escalón por escalón.
 *
 * Movimiento (WCAG 2.2.2 y 2.3.3): con `quieto` (pausa del usuario o
 * prefers-reduced-motion, ver PreferenciasContext) NO se anima: se simula un
 * tramo de prueba y se pinta UNA imagen fija, que es la que queda. Al reanudar,
 * sigue desde ahí. Es decorativo: aria-hidden; las cifras que importan van en
 * texto aparte.
 *
 * Los colores salen de los tokens (--lg-*, --hero-*) y se releen al cambiar de
 * tema.
 */
import { useEffect, useRef } from 'react';
import { usePreferencias } from '../../context/PreferenciasContext';
import { cx } from './cx';

export interface LecturaCarga {
  usuarios: number;
  tps: number;
  p90: number;
  fase: string;
  /** El percentil 90 supera el criterio (5 s). */
  excedido: boolean;
}

export interface LoadFxProps {
  escena: 'login' | 'hero';
  /** Solo 'hero': dibuja la escalera de usuarios. */
  rampa?: boolean;
  /** Pausa local además de la global (el botón propio del login). */
  pausado?: boolean;
  onLectura?: (l: LecturaCarga) => void;
  className?: string;
}

type Particula = { x: number; y: number; k: number; hot: boolean; w: number; z: number };
type Colores = Record<'fondo' | 'fondo2' | 'linea' | 'caliente' | 'apagado' | 'punto', string>;

/** Un token de color («79 70 229») como color de canvas. */
function colorDe(estilo: CSSStyleDeclaration, nombre: string): string {
  const v = estilo.getPropertyValue(nombre).trim().split(/\s+/);
  return v.length === 3 ? `rgb(${v[0]}, ${v[1]}, ${v[2]})` : 'transparent';
}

// ---- Escena del inicio de sesión (constantes del mockup) ----
const CICLO = 26;
const MAXU = 350;
const LIMITE = 5000;
const TECHO = 7200;
const objetivo = (s: number) => {
  s %= CICLO;
  return s < 8 ? (MAXU * Math.min(5, Math.floor(s / 1.6) + 1)) / 5
    : s < 15 ? MAXU
    : s < 18.5 ? MAXU * 1.7
    : s < 24 ? MAXU * (1 - (s - 18.5) / 5.5)
    : 0;
};
const fase = (s: number) => {
  s %= CICLO;
  return s < 8 ? 'Rampa de subida' : s < 15 ? 'Carga sostenida' : s < 18.5 ? 'Pico de usuarios' : s < 24 ? 'Enfriamiento' : 'Preparando la siguiente';
};
const p90De = (u: number) => (120 + 0.9 * u + (u > MAXU ? (u - MAXU) * 9.4 : 0)) * 1.8;

export function LoadFx({ escena, rampa = false, pausado = false, onLectura, className }: LoadFxProps) {
  const lienzo = useRef<HTMLCanvasElement>(null);
  const { quieto: quietoGlobal, tema } = usePreferencias();
  const quieto = quietoGlobal || pausado;
  const quietoRef = useRef(quieto);
  const lecturaRef = useRef(onLectura);
  lecturaRef.current = onLectura;
  // El motor vive en un ref: sobrevive a los cambios de tema y de pausa.
  const motor = useRef<{ arrancar: () => void; recolorear: () => void } | null>(null);

  useEffect(() => {
    const cv = lienzo.current;
    if (!cv) return;
    const cx2 = cv.getContext('2d');
    if (!cx2) return;
    const ctx = cx2;

    let W = 0;
    let H = 0;
    let t = 0;
    let ultimo = 0;
    let brote = 0;
    let muestra = 0;
    let hud = 0;
    let uMostrado = 0;
    let gx = 0;
    let parts: Particula[] = [];
    const traza: number[] = [];
    let raf = 0;
    let C: Colores = { fondo: '', fondo2: '', linea: '', caliente: '', apagado: '', punto: '' };
    let fuente = 'system-ui';

    const recolorear = () => {
      const e = getComputedStyle(cv);
      C = escena === 'login'
        ? {
            fondo: colorDe(e, '--lg-bg'), fondo2: colorDe(e, '--lg-2'), linea: colorDe(e, '--lg-line'),
            caliente: colorDe(e, '--lg-hot'), apagado: colorDe(e, '--lg-muted'), punto: colorDe(e, '--lg-text'),
          }
        : {
            fondo: '', fondo2: '', linea: colorDe(e, '--hero-line'), caliente: colorDe(e, '--lg-hot'),
            apagado: colorDe(e, '--hero-muted'), punto: colorDe(e, '--hero-text'),
          };
      fuente = e.getPropertyValue('--font-body').trim() || 'system-ui';
    };

    const medir = () => {
      const d = Math.min(2, window.devicePixelRatio || 1);
      W = cv.clientWidth;
      H = cv.clientHeight;
      cv.width = Math.round(W * d);
      cv.height = Math.round(H * d);
      ctx.setTransform(d, 0, 0, d, 0, 0);
    };

    // ---------- login ----------
    let velocidad = 0;
    const pasoLogin = (dt: number) => {
      t += dt;
      uMostrado += (objetivo(t) - uMostrado) * Math.min(1, dt * 3.2);
      const p90 = p90De(uMostrado) * (1 + Math.sin(t * 7.3) * 0.035 + Math.sin(t * 2.1) * 0.03);
      gx = (gx + dt * 26) % 64;
      brote += dt * (6 + uMostrado * 0.34);
      while (brote >= 1) {
        brote--;
        if (parts.length < 460) {
          const carril = Math.floor(Math.random() * 30);
          const z = Math.random();
          parts.push({ x: -60, y: H * (0.05 + (carril / 30) * 0.6), k: 0.45 + z * 0.9, hot: Math.random() < (p90 > 4300 ? 0.32 : 0.006), w: 0.8 + z * 2.6, z });
        }
      }
      velocidad = W * (0.52 - Math.min(0.36, p90 / 15000));
      for (const p of parts) p.x += velocidad * p.k * dt;
      parts = parts.filter((p) => p.x < W + 60);
      muestra += dt;
      while (muestra >= 0.05) {
        muestra -= 0.05;
        traza.push(p90);
        if (traza.length > Math.ceil(W / 3) + 2) traza.shift();
      }
      hud += dt;
      if (hud >= 0.2) {
        hud = 0;
        lecturaRef.current?.({
          usuarios: uMostrado,
          tps: uMostrado * 0.078 * (uMostrado > MAXU * 1.1 ? 0.8 : 1),
          p90,
          fase: fase(t),
          excedido: p90 > LIMITE,
        });
      }
    };

    const dibujarLogin = () => {
      const v = velocidad || W * 0.3;
      const g = ctx.createLinearGradient(0, 0, W, H);
      g.addColorStop(0, C.fondo);
      g.addColorStop(1, C.fondo2);
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, W, H);
      const r = ctx.createRadialGradient(W * 0.78, H * 0.12, 0, W * 0.78, H * 0.12, Math.max(W, H) * 0.7);
      r.addColorStop(0, C.fondo2);
      r.addColorStop(1, 'transparent');
      ctx.globalAlpha = 0.55;
      ctx.fillStyle = r;
      ctx.fillRect(0, 0, W, H);
      // Rejilla que se desplaza.
      ctx.globalAlpha = 0.08;
      ctx.strokeStyle = C.linea;
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let x = -gx; x < W; x += 64) { ctx.moveTo(x, 0); ctx.lineTo(x, H); }
      for (let y = 0; y < H; y += 64) { ctx.moveTo(0, y); ctx.lineTo(W, y); }
      ctx.stroke();
      // Peticiones.
      ctx.lineCap = 'round';
      for (const p of parts) {
        const len = Math.max(24, v * p.k * 0.24);
        const a = Math.min(1, (p.x + 60) / 160) * Math.min(1, (W + 60 - p.x) / 200) * (0.35 + p.z * 0.65);
        const lg = ctx.createLinearGradient(p.x - len, 0, p.x, 0);
        lg.addColorStop(0, 'transparent');
        lg.addColorStop(1, p.hot ? C.caliente : C.linea);
        ctx.globalAlpha = a * (p.hot ? 1 : 0.75);
        ctx.strokeStyle = lg;
        ctx.lineWidth = p.w;
        ctx.beginPath();
        ctx.moveTo(p.x - len, p.y);
        ctx.lineTo(p.x, p.y);
        ctx.stroke();
        ctx.globalAlpha = a;
        ctx.fillStyle = p.hot ? C.caliente : C.punto;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.w * 0.9, 0, 6.3);
        ctx.fill();
      }
      // Trazo del percentil 90 frente al criterio.
      const y0 = H * 0.5;
      const y1 = H * 0.985;
      const py = (q: number) => y1 - Math.sqrt(Math.min(q, TECHO) / TECHO) * (y1 - y0);
      const n = traza.length;
      const x0 = W - (n - 1) * 3;
      const ly = py(LIMITE);
      if (n > 1) {
        const camino = () => {
          ctx.beginPath();
          traza.forEach((q, i) => (i ? ctx.lineTo(x0 + i * 3, py(q)) : ctx.moveTo(x0, py(q))));
        };
        ctx.globalAlpha = 0.42;
        camino();
        ctx.lineTo(W, y1);
        ctx.lineTo(x0, y1);
        ctx.closePath();
        const fg = ctx.createLinearGradient(0, y0, 0, y1);
        fg.addColorStop(0, C.linea);
        fg.addColorStop(1, 'transparent');
        ctx.fillStyle = fg;
        ctx.fill();
        ctx.globalAlpha = 1;
        ctx.lineWidth = 3;
        ctx.lineJoin = 'round';
        ctx.shadowBlur = 24;
        ctx.save();
        ctx.beginPath();
        ctx.rect(0, ly, W, H);
        ctx.clip();
        ctx.shadowColor = C.linea;
        ctx.strokeStyle = C.linea;
        camino();
        ctx.stroke();
        ctx.restore();
        ctx.save();
        ctx.beginPath();
        ctx.rect(0, 0, W, ly);
        ctx.clip();
        ctx.shadowColor = C.caliente;
        ctx.strokeStyle = C.caliente;
        camino();
        ctx.stroke();
        ctx.restore();
        const q = traza[n - 1];
        const pulso = 6 + Math.abs(Math.sin(t * 3)) * 9;
        ctx.shadowBlur = 0;
        ctx.globalAlpha = 0.35;
        ctx.fillStyle = q > LIMITE ? C.caliente : C.linea;
        ctx.beginPath();
        ctx.arc(W - 6, py(q), pulso, 0, 6.3);
        ctx.fill();
        ctx.globalAlpha = 1;
        ctx.fillStyle = C.punto;
        ctx.beginPath();
        ctx.arc(W - 6, py(q), 4, 0, 6.3);
        ctx.fill();
      }
      ctx.shadowBlur = 0;
      ctx.globalAlpha = 0.8;
      ctx.setLineDash([6, 6]);
      const dg = ctx.createLinearGradient(W * 0.4, 0, W * 0.62, 0);
      dg.addColorStop(0, 'transparent');
      dg.addColorStop(1, C.caliente);
      ctx.strokeStyle = dg;
      ctx.lineWidth = 1.25;
      ctx.beginPath();
      ctx.moveTo(W * 0.4, ly);
      ctx.lineTo(W, ly);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.globalAlpha = 0.95;
      ctx.fillStyle = C.apagado;
      ctx.font = `500 12px ${fuente}`;
      ctx.fillText('criterio: percentil 90 ≤ 5 s', W * 0.47, ly - 9);
      ctx.globalAlpha = 1;
    };

    // ---------- hero ----------
    const CICLO_H = 13;
    const ESCALONES = 5;
    const pasoHero = (dt: number) => {
      t += dt;
      const s = t % CICLO_H;
      const carga = Math.min(1, s / 5.5) * (s > 11 ? 1 - (s - 11) / 2 : 1);
      brote += dt * (6 + carga * 52);
      while (brote >= 1) {
        brote--;
        if (parts.length < 190) {
          const z = Math.random();
          parts.push({ x: W * 0.42, y: 0.05 + Math.random() * 0.66, k: 0.5 + z * 0.9, w: 0.8 + z * 2.2, z, hot: Math.random() < 0.035 });
        }
      }
      for (const p of parts) p.x += W * 0.3 * p.k * dt;
      parts = parts.filter((p) => p.x <= W + 60);
    };

    const dibujarHero = () => {
      ctx.clearRect(0, 0, W, H);
      const s = t % CICLO_H;
      const prog = Math.min(1, s / 5.5);
      const desvanece = s > 11 ? Math.max(0, 1 - (s - 11) / 2) : 1;
      ctx.lineCap = 'round';
      for (const p of parts) {
        const len = Math.max(22, W * 0.3 * p.k * 0.2);
        const fx = Math.max(0, Math.min(1, (p.x - W * 0.5) / (W * 0.22)));
        const a = fx * Math.min(1, (W + 60 - p.x) / 160) * (0.28 + p.z * 0.6);
        if (a <= 0.01) continue;
        const y = p.y * H;
        const g = ctx.createLinearGradient(p.x - len, 0, p.x, 0);
        g.addColorStop(0, 'transparent');
        g.addColorStop(1, p.hot ? C.caliente : C.linea);
        ctx.globalAlpha = a;
        ctx.strokeStyle = g;
        ctx.lineWidth = p.w;
        ctx.beginPath();
        ctx.moveTo(p.x - len, y);
        ctx.lineTo(p.x, y);
        ctx.stroke();
        ctx.fillStyle = p.hot ? C.caliente : C.punto;
        ctx.beginPath();
        ctx.arc(p.x, y, p.w * 0.85, 0, 6.3);
        ctx.fill();
      }
      if (!rampa) {
        ctx.globalAlpha = 1;
        return;
      }
      const xa = W * (W < 900 ? 0.5 : 0.69);
      const xb = W * 0.965;
      const yb = H * 0.82;
      const yt = Math.max(36, H * 0.2);
      const seg = (xb - xa) / ESCALONES;
      const a: Array<[number, number]> = [[xa, yb]];
      for (let i = 0; i < ESCALONES; i++) {
        const y = yb - ((yb - yt) * i) / ESCALONES;
        const y2 = yb - ((yb - yt) * (i + 1)) / ESCALONES;
        a.push([xa + (i + 0.55) * seg, y], [xa + (i + 1) * seg, y2]);
      }
      let total = 0;
      const L = [0];
      for (let i = 1; i < a.length; i++) {
        total += Math.hypot(a[i][0] - a[i - 1][0], a[i][1] - a[i - 1][1]);
        L.push(total);
      }
      const corte = total * prog;
      let hx = a[0][0];
      let hy = a[0][1];
      ctx.beginPath();
      ctx.moveTo(hx, hy);
      for (let i = 1; i < a.length; i++) {
        if (L[i] <= corte) {
          ctx.lineTo(a[i][0], a[i][1]);
          hx = a[i][0];
          hy = a[i][1];
        } else {
          const f = (corte - L[i - 1]) / (L[i] - L[i - 1]);
          hx = a[i - 1][0] + (a[i][0] - a[i - 1][0]) * f;
          hy = a[i - 1][1] + (a[i][1] - a[i - 1][1]) * f;
          ctx.lineTo(hx, hy);
          break;
        }
      }
      ctx.globalAlpha = 0.95 * desvanece;
      ctx.strokeStyle = C.linea;
      ctx.lineWidth = 3;
      ctx.lineJoin = 'round';
      ctx.shadowColor = C.linea;
      ctx.shadowBlur = 18;
      ctx.stroke();
      ctx.shadowBlur = 0;
      ctx.lineTo(hx, yb);
      ctx.lineTo(a[0][0], yb);
      ctx.closePath();
      const fg = ctx.createLinearGradient(0, H * 0.1, 0, yb);
      fg.addColorStop(0, C.linea);
      fg.addColorStop(1, 'transparent');
      ctx.globalAlpha = 0.22 * desvanece;
      ctx.fillStyle = fg;
      ctx.fill();
      const pulso = 6 + Math.abs(Math.sin(t * 3.2)) * 10;
      ctx.globalAlpha = 0.35 * desvanece;
      ctx.fillStyle = C.linea;
      ctx.beginPath();
      ctx.arc(hx, hy, pulso, 0, 6.3);
      ctx.fill();
      ctx.globalAlpha = desvanece;
      ctx.fillStyle = C.punto;
      ctx.beginPath();
      ctx.arc(hx, hy, 4.5, 0, 6.3);
      ctx.fill();
      ctx.globalAlpha = 1;
    };

    const paso = escena === 'login' ? pasoLogin : pasoHero;
    const dibujar = escena === 'login' ? dibujarLogin : dibujarHero;

    const bucle = (ahora: number) => {
      const dt = Math.min(0.05, (ahora - (ultimo || ahora)) / 1000);
      ultimo = ahora;
      paso(dt);
      dibujar();
      raf = requestAnimationFrame(bucle);
    };

    const arrancar = () => {
      cancelAnimationFrame(raf);
      ultimo = 0;
      if (quietoRef.current) {
        // Imagen fija: un tramo de prueba ya simulado (17 s en el login, en
        // plena carga; 7,5 s en el bloque, con la rampa arriba).
        if (t === 0) {
          const pasos = escena === 'login' ? 345 : 150;
          for (let i = 0; i < pasos; i++) paso(0.05);
        }
        dibujar();
        return;
      }
      raf = requestAnimationFrame(bucle);
    };

    recolorear();
    medir();
    const ro = new ResizeObserver(() => {
      medir();
      if (quietoRef.current) dibujar();
    });
    ro.observe(cv);
    motor.current = {
      arrancar,
      recolorear: () => {
        recolorear();
        if (quietoRef.current) dibujar();
      },
    };
    arrancar();

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      motor.current = null;
    };
  }, [escena, rampa]);

  // Pausar / reanudar sin perder el estado de la simulación.
  useEffect(() => {
    quietoRef.current = quieto;
    motor.current?.arrancar();
  }, [quieto]);

  // El tema cambió: releer los colores de los tokens. Un fotograma después,
  // porque <html data-theme> lo cambia el efecto del proveedor, que corre
  // DESPUÉS de los de sus hijos.
  useEffect(() => {
    const id = requestAnimationFrame(() => motor.current?.recolorear());
    return () => cancelAnimationFrame(id);
  }, [tema]);

  return (
    <canvas
      ref={lienzo}
      aria-hidden="true"
      className={cx('pointer-events-none absolute inset-0 block h-full w-full', className)}
    />
  );
}
