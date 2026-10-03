/**
 * Confirmación (mockup: confirmBox). Sustituye a los `confirm()` nativos: la
 * auditoría 153 contó 38 entre `alert` y `confirm`, que no se pueden leer con el
 * estilo de la app, bloquean el navegador y en algunos sistemas no se ven.
 *
 * - El botón de confirmar dice LO QUE HACE («Eliminar reporte»), no «Aceptar».
 * - Con `peligro`, el botón es rojo y lleva papelera; `aviso` explica qué no
 *   se puede deshacer.
 * - Al abrir, el foco va a «Cancelar»: la opción segura.
 */
import { ReactNode, useRef } from 'react';
import { Trash2 } from 'lucide-react';
import { Alert } from './Alert';
import { Button } from './Button';
import { Modal } from './Modal';

export interface ConfirmDialogProps {
  abierto: boolean;
  titulo: ReactNode;
  texto: ReactNode;
  textoConfirmar: string;
  peligro?: boolean;
  aviso?: ReactNode;
  /** Mientras la acción se ejecuta: deshabilita y no deja cerrar. */
  ejecutando?: boolean;
  onConfirmar: () => void;
  onCancelar: () => void;
}

export function ConfirmDialog({
  abierto, titulo, texto, textoConfirmar, peligro, aviso, ejecutando, onConfirmar, onCancelar,
}: ConfirmDialogProps) {
  const cancelar = useRef<HTMLButtonElement>(null);
  return (
    <Modal
      abierto={abierto}
      onCerrar={onCancelar}
      titulo={titulo}
      bloqueado={ejecutando}
      focoInicial={cancelar}
      pie={
        <>
          <Button ref={cancelar} onClick={onCancelar} disabled={ejecutando}>
            Cancelar
          </Button>
          <Button
            variant={peligro ? 'danger' : 'primary'}
            icon={peligro ? Trash2 : undefined}
            onClick={onConfirmar}
            cargando={ejecutando}
          >
            {textoConfirmar}
          </Button>
        </>
      }
    >
      <p>{texto}</p>
      {aviso && <Alert tono={peligro ? 'err' : 'warn'}>{aviso}</Alert>}
    </Modal>
  );
}
