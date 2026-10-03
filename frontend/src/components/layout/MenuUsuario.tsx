/**
 * La cuenta (mockup: ACT.user): nombre, rol y usuario, con «Mi perfil» y
 * «Cerrar sesión». Sustituye al pie del menú lateral viejo, con las mismas
 * dos acciones.
 */
import { useNavigate } from 'react-router-dom';
import { LogOut, UserCircle } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { nombreRol } from '../../config/roles';
import { Button } from '../ui/Button';
import { Modal } from '../ui/Modal';

export function MenuUsuario({ abierto, onCerrar }: { abierto: boolean; onCerrar: () => void }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <Modal
      abierto={abierto}
      onCerrar={onCerrar}
      titulo={user?.full_name || 'Usuario'}
      pie={
        <>
          <Button
            icon={UserCircle}
            onClick={() => {
              onCerrar();
              navigate('/profile');
            }}
          >
            Mi perfil
          </Button>
          <Button
            variant="primary"
            icon={LogOut}
            onClick={() => {
              onCerrar();
              logout();
            }}
          >
            Cerrar sesión
          </Button>
        </>
      }
    >
      <p className="text-ink-muted">
        {nombreRol(user?.role)}
        {user?.username && <> · @{user.username}</>}
      </p>
    </Modal>
  );
}
