/**
 * Profile - Editar perfil propio - v2.0
 */
import { useState } from 'react';
import { Save, AlertCircle, CheckCircle, UserCircle, Lock } from 'lucide-react';
import { profileAPI } from '../../services/api';
import { useAuth } from '../../context/AuthContext';

export default function Profile() {
  const { user, refreshUser } = useAuth();

  const [fullName, setFullName] = useState(user?.full_name || '');
  const [email, setEmail] = useState(user?.email || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Password change
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [pwSaving, setPwSaving] = useState(false);
  const [pwError, setPwError] = useState('');
  const [pwSuccess, setPwSuccess] = useState('');

  const handleProfileUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setSaving(true);

    try {
      await profileAPI.update({ full_name: fullName, email });
      await refreshUser();
      setSuccess('Perfil actualizado correctamente');
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        setError(axiosErr.response?.data?.detail || 'Error al actualizar perfil');
      } else {
        setError('Error al actualizar perfil');
      }
    } finally {
      setSaving(false);
    }
  };

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setPwError('');
    setPwSuccess('');

    if (newPassword !== confirmPassword) {
      setPwError('Las contrasenas no coinciden');
      return;
    }

    if (newPassword.length < 6) {
      setPwError('La contrasena debe tener al menos 6 caracteres');
      return;
    }

    setPwSaving(true);

    try {
      await profileAPI.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setPwSuccess('Contrasena actualizada correctamente');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        setPwError(axiosErr.response?.data?.detail || 'Error al cambiar contrasena');
      } else {
        setPwError('Error al cambiar contrasena');
      }
    } finally {
      setPwSaving(false);
    }
  };

  const ROLE_LABELS: Record<string, string> = {
    admin: 'Administrador',
    analyst: 'Analista',
    viewer: 'Visor',
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-4xl font-bold text-white">Mi Perfil</h1>
        <p className="text-gray-400 mt-1 text-xl">Administra tu informacion personal</p>
      </div>

      {/* Info Card */}
      <div className="bg-[#162040] border border-[#f5a623]/20 rounded-xl p-6">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-[#f5a623] rounded-full flex items-center justify-center">
            <span className="text-3xl font-bold text-[#0a1628]">
              {user?.full_name?.charAt(0)?.toUpperCase() || 'U'}
            </span>
          </div>
          <div>
            <p className="text-2xl font-semibold text-white">{user?.full_name}</p>
            <p className="text-lg text-gray-400">@{user?.username}</p>
            <span className="inline-flex mt-1 px-3 py-1 text-lg font-medium rounded bg-[#f5a623]/20 text-[#f5a623] border border-[#f5a623]/30">
              {ROLE_LABELS[user?.role || 'viewer']}
            </span>
          </div>
        </div>
      </div>

      {/* Profile Form */}
      <form onSubmit={handleProfileUpdate} className="bg-[#162040] border border-[#f5a623]/20 rounded-xl p-6 space-y-5">
        <div className="flex items-center gap-2 mb-2">
          <UserCircle className="w-7 h-7 text-[#f5a623]" />
          <h2 className="text-2xl font-semibold text-white">Datos Personales</h2>
        </div>

        {error && (
          <div className="bg-red-900/20 border border-red-700 rounded-lg p-3 flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-red-400" />
            <span className="text-lg text-red-300">{error}</span>
          </div>
        )}
        {success && (
          <div className="bg-emerald-900/20 border border-emerald-700 rounded-lg p-3 flex items-center gap-2">
            <CheckCircle className="w-5 h-5 text-emerald-400" />
            <span className="text-lg text-emerald-300">{success}</span>
          </div>
        )}

        <div>
          <label className="block text-lg font-medium text-gray-300 mb-1.5">
            Nombre Completo
          </label>
          <input
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="w-full px-5 h-14 bg-[#0d1f3c] border border-[#2a3f6f] rounded-lg text-white focus:outline-none focus:border-[#f5a623] text-xl"
          />
        </div>

        <div>
          <label className="block text-lg font-medium text-gray-300 mb-1.5">
            Email
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-5 h-14 bg-[#0d1f3c] border border-[#2a3f6f] rounded-lg text-white focus:outline-none focus:border-[#f5a623] text-xl"
          />
        </div>

        <div>
          <label className="block text-lg font-medium text-gray-300 mb-1.5">
            Username
          </label>
          <input
            type="text"
            value={user?.username || ''}
            disabled
            className="w-full px-5 h-14 bg-[#0d1f3c]/50 border border-[#2a3f6f] rounded-lg text-gray-500 text-xl cursor-not-allowed"
          />
          <p className="text-lg text-gray-500 mt-1">El username no se puede cambiar</p>
        </div>

        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={saving}
            className="flex items-center gap-2 px-6 py-3 bg-[#f5a623] text-[#0a1628] rounded-lg hover:bg-[#e09410] disabled:opacity-50 text-xl font-semibold transition-colors"
          >
            <Save className="w-6 h-6" />
            {saving ? 'Guardando...' : 'Guardar Cambios'}
          </button>
        </div>
      </form>

      {/* Password Form */}
      <form onSubmit={handlePasswordChange} className="bg-[#162040] border border-[#f5a623]/20 rounded-xl p-6 space-y-5">
        <div className="flex items-center gap-2 mb-2">
          <Lock className="w-7 h-7 text-[#f5a623]" />
          <h2 className="text-2xl font-semibold text-white">Cambiar Contrasena</h2>
        </div>

        {pwError && (
          <div className="bg-red-900/20 border border-red-700 rounded-lg p-3 flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-red-400" />
            <span className="text-lg text-red-300">{pwError}</span>
          </div>
        )}
        {pwSuccess && (
          <div className="bg-emerald-900/20 border border-emerald-700 rounded-lg p-3 flex items-center gap-2">
            <CheckCircle className="w-5 h-5 text-emerald-400" />
            <span className="text-lg text-emerald-300">{pwSuccess}</span>
          </div>
        )}

        <div>
          <label className="block text-lg font-medium text-gray-300 mb-1.5">
            Contrasena Actual
          </label>
          <input
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            required
            className="w-full px-5 h-14 bg-[#0d1f3c] border border-[#2a3f6f] rounded-lg text-white focus:outline-none focus:border-[#f5a623] text-xl"
            placeholder="••••••••"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div>
            <label className="block text-lg font-medium text-gray-300 mb-1.5">
              Nueva Contrasena
            </label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              className="w-full px-5 h-14 bg-[#0d1f3c] border border-[#2a3f6f] rounded-lg text-white focus:outline-none focus:border-[#f5a623] text-xl"
              placeholder="••••••••"
            />
          </div>
          <div>
            <label className="block text-lg font-medium text-gray-300 mb-1.5">
              Confirmar Contrasena
            </label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              className="w-full px-5 h-14 bg-[#0d1f3c] border border-[#2a3f6f] rounded-lg text-white focus:outline-none focus:border-[#f5a623] text-xl"
              placeholder="••••••••"
            />
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={pwSaving}
            className="flex items-center gap-2 px-6 py-3 bg-[#f5a623] text-[#0a1628] rounded-lg hover:bg-[#e09410] disabled:opacity-50 text-xl font-semibold transition-colors"
          >
            <Lock className="w-6 h-6" />
            {pwSaving ? 'Cambiando...' : 'Cambiar Contrasena'}
          </button>
        </div>
      </form>
    </div>
  );
}
