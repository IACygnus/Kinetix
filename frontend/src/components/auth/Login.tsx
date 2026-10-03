/**
 * Login — inicio de sesión (rediseño, Etapa 0; mockup: V.login y AFTER.login).
 *
 * A la izquierda, una prueba de carga simulada en <canvas> (LoadFx) con sus
 * cifras en vivo; a la derecha, el formulario. Bajo 900 px, una columna.
 *
 * La autenticación es la de siempre: `login()` de AuthContext, el mensaje de
 * sesión expirada con su cierre, el 429 del límite de intentos y el `detail`
 * del servidor tal cual. Lo único nuevo del formulario es que avisa en la
 * propia página si falta el usuario o la contraseña, en vez de con la burbuja
 * del navegador (`required`).
 *
 * Movimiento: el botón «Pausar animación» es la MISMA pausa de la cabecera
 * (se recuerda); con prefers-reduced-motion el lienzo es una imagen quieta y
 * el botón no aparece.
 */
import { FormEvent, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { X } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { usePreferencias } from '../../context/PreferenciasContext';
import { LoadFx, LecturaCarga } from '../ui/LoadFx';
import { Button } from '../ui/Button';
import { Field } from '../ui/Field';
import { Input } from '../ui/Input';
import { cx } from '../ui/cx';
import logo from '../../assets/logo-sqa.png';

const nf = (n: number, d = 0) =>
  Number(n).toLocaleString('es-CO', { minimumFractionDigits: d, maximumFractionDigits: d });

export default function Login() {
  const navigate = useNavigate();
  const { login, isAuthenticated, sessionExpiredMessage, clearSessionMessage } = useAuth();
  const { pausado, alternarPausa, reducido } = usePreferencias();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [faltan, setFaltan] = useState<{ usuario: boolean; clave: boolean }>({ usuario: false, clave: false });
  const [loading, setLoading] = useState(false);
  const [lectura, setLectura] = useState<LecturaCarga | null>(null);

  // Si ya está autenticado, redirigir (después de todos los hooks: regla 16).
  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const sinUsuario = !username.trim();
    const sinClave = !password;
    setFaltan({ usuario: sinUsuario, clave: sinClave });
    if (sinUsuario || sinClave) {
      setError('');
      document.getElementById(sinUsuario ? 'login-usuario' : 'login-clave')?.focus();
      return;
    }

    setLoading(true);
    setError('');

    try {
      await login(username, password);
      navigate('/dashboard');
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      if (status === 429) {
        setError(detail || 'Demasiados intentos. Intenta en 15 minutos.');
      } else {
        setError(detail || 'Credenciales inválidas. Verifica tu usuario y contraseña.');
      }
    } finally {
      setLoading(false);
    }
  };

  const faltaAlgo = faltan.usuario || faltan.clave;

  return (
    <div className="relative isolate grid min-h-screen grid-cols-1 content-start items-start gap-login-gap overflow-hidden bg-lg-bg px-login-x py-login-y text-lg-text cabecera:grid-cols-login cabecera:content-center">
      <LoadFx escena="login" onLectura={setLectura} className="-z-20" />
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10 bg-velo-login opacity-90" />

      {/* La historia: marca, titular, cifras en vivo de la prueba simulada. */}
      <div className="kx-escalonado kx-sobre-lienzo grid min-w-0 content-center gap-login-copia">
        <div className="flex items-center gap-3.5 motion-safe:animate-sube">
          <img src={logo} alt="SQA" className="block h-11 w-auto" />
          <span>
            <b className="block font-titular text-xl font-semibold tracking-display">Kinetix</b>
            <small className="block text-nota text-lg-muted">Performance</small>
          </span>
        </div>
        <p className="max-w-none font-titular text-titular font-semibold tracking-titular text-lg-text motion-safe:animate-sube cabecera:max-w-titular">
          Cada milisegundo cuenta.
        </p>
        <p className="max-w-lema text-lema text-lg-muted motion-safe:animate-sube">
          Diseña, ejecuta y analiza pruebas de carga. Kinetix convierte cada JTL en un veredicto por servicio.
        </p>
        <div aria-hidden="true" className="flex flex-wrap gap-x-10 gap-y-3 motion-safe:animate-sube">
          <div>
            <span className="block text-nota text-lg-muted">Usuarios activos</span>
            <b className="block min-w-cifra font-code text-cifra-login font-medium tabular-nums tracking-tight">
              {nf(lectura?.usuarios ?? 0)}
            </b>
          </div>
          <div>
            <span className="block text-nota text-lg-muted">Peticiones por segundo</span>
            <b className="block min-w-cifra font-code text-cifra-login font-medium tabular-nums tracking-tight">
              {nf(lectura?.tps ?? 0, 1)}
            </b>
          </div>
          <div>
            <span className="block text-nota text-lg-muted">Percentil 90</span>
            <b
              className={cx(
                'block min-w-cifra font-code text-cifra-login font-medium tabular-nums tracking-tight',
                lectura?.excedido && 'text-lg-hot',
              )}
            >
              {nf(lectura?.p90 ?? 0)} ms
            </b>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2.5 text-sm text-lg-muted motion-safe:animate-sube">
          <i aria-hidden="true" className="h-2.5 w-2.5 flex-none rounded-pill bg-lg-hot motion-safe:animate-parpadeo" />
          <span>
            <strong className="font-semibold text-lg-text">{lectura?.fase ?? 'Rampa de subida'}</strong> · prueba simulada
          </span>
          {!reducido && (
            <button
              type="button"
              onClick={alternarPausa}
              aria-pressed={pausado}
              className="min-h-8 rounded-pill border border-lg-muted bg-lg-bg/70 px-3 text-nota font-semibold text-lg-text cursor-pointer hover:bg-lg-bg focus-visible:outline-focus-hero"
            >
              {pausado ? 'Reanudar animación' : 'Pausar animación'}
            </button>
          )}
        </div>
      </div>

      {/* El formulario. */}
      <form
        noValidate
        onSubmit={handleSubmit}
        className="grid w-full max-w-tarjeta-login gap-4 rounded-tarjeta-login bg-surface p-tarjeta-login text-ink shadow-login ring-1 ring-line motion-safe:animate-tarjeta cabecera:max-w-none cabecera:justify-self-end"
      >
        <div>
          <h1 className="font-display text-tarjeta font-extrabold leading-tight tracking-display">Iniciar sesión</h1>
          <p className="text-ink-muted">Entra con tu usuario de SQA.</p>
        </div>

        <Field id="login-usuario" etiqueta="Usuario o correo">
          <Input
            id="login-usuario"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            invalido={faltan.usuario}
            aria-describedby={faltaAlgo ? 'login-faltan' : undefined}
          />
        </Field>

        <Field id="login-clave" etiqueta="Contraseña">
          <Input
            id="login-clave"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            invalido={faltan.clave}
            aria-describedby={faltaAlgo ? 'login-faltan' : undefined}
          />
        </Field>

        {faltaAlgo && (
          <p id="login-faltan" role="alert" className="text-sm font-semibold text-err">
            Escribe tu usuario y tu contraseña.
          </p>
        )}

        {sessionExpiredMessage && (
          <div role="status" className="flex items-start gap-2 rounded-control bg-warn-bg px-4 py-3 text-warn">
            <p className="flex-1 text-ink">{sessionExpiredMessage}</p>
            <button
              type="button"
              onClick={clearSessionMessage}
              aria-label="Cerrar el aviso"
              title="Cerrar el aviso"
              className="-my-1 inline-grid h-8 w-8 flex-none place-items-center rounded-chico cursor-pointer hover:bg-surface/60"
            >
              <X aria-hidden="true" strokeWidth={1.8} className="h-5 w-5" />
            </button>
          </div>
        )}

        {error && (
          <p role="alert" className="rounded-control bg-err-bg px-4 py-3 font-semibold text-err">
            {error}
          </p>
        )}

        <Button type="submit" variant="cta" size="lg" bloque cargando={loading}>
          {loading ? 'Ingresando…' : 'Ingresar'}
        </Button>

        <p className="text-sm text-ink-muted">Contacta al administrador si no tienes cuenta.</p>
      </form>
    </div>
  );
}
