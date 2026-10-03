/**
 * La marca: el logo de SQA sobre su chip y «Kinetix / Performance» (mockup:
 * brandHtml). El logo es el PNG del mockup (`<img id="logo-src">`), con fondo
 * transparente, sobre el chip --brand-bg.
 */
import { Link } from 'react-router-dom';
import logo from '../../assets/logo-sqa.png';
import { cx } from '../ui/cx';

export function Marca({ soloLogo, className }: { soloLogo?: boolean; className?: string }) {
  return (
    <Link
      to="/dashboard"
      className={cx(
        'flex flex-none items-center gap-2.5 rounded-control text-brand-text no-underline focus-visible:outline-focus-hdr',
        className,
      )}
    >
      <span className="grid place-items-center rounded-control bg-brand-bg px-2.5 py-1.5">
        <img src={logo} alt="SQA" className="block h-5.5 w-auto" />
      </span>
      {!soloLogo && (
        <span className="grid leading-tight">
          <b className="font-display text-destacado font-extrabold tracking-display">Kinetix</b>
          <small className="block text-xs font-medium text-brand-muted">Performance</small>
        </span>
      )}
    </Link>
  );
}
