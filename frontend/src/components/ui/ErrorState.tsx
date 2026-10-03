/**
 * Error al cargar (mockup: guard → alertBox «No se pudieron cargar …»).
 *
 * Sustituye a los ceros: cuando la petición falla, la pantalla pinta ESTO en
 * lugar de sus indicadores y tablas, para que nadie lea «0 reportes» como un
 * dato (auditoría 153 §4.1). Con `onReintentar`, ofrece el botón.
 */
import { ReactNode } from 'react';
import { RefreshCw } from 'lucide-react';
import { Alert } from './Alert';
import { Button } from './Button';

export interface ErrorStateProps {
  /** Qué no se pudo cargar, en minúscula: «los reportes». */
  que: string;
  /** El detalle del servidor, si lo hay. */
  detalle?: ReactNode;
  onReintentar?: () => void;
  reintentando?: boolean;
  className?: string;
}

export function ErrorState({ que, detalle, onReintentar, reintentando, className }: ErrorStateProps) {
  return (
    <Alert
      tono="err"
      titulo={`No se pudieron cargar ${que}`}
      className={className}
      accion={
        onReintentar && (
          <Button size="sm" icon={RefreshCw} onClick={onReintentar} cargando={reintentando}>
            Reintentar
          </Button>
        )
      }
    >
      <p>{detalle ?? 'El servidor no respondió. No se muestra ningún dato porque no hay dato confiable que mostrar.'}</p>
    </Alert>
  );
}
