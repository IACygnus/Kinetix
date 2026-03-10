/**
 * UserForm - Crear o editar usuario - Admin only - SQA Light Theme
 */
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Save, AlertCircle } from 'lucide-react';
import { usersAPI } from '../../services/api';
import type { UserInfo } from '../../types';

export default function UserForm() {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const isEditing = !!userId && userId !== 'new';

  const [loading, setLoading] = useState(isEditing);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('viewer');
  const [isActive, setIsActive] = useState(true);

  useEffect(() => {
    if (isEditing && userId) {
      const fetchUser = async () => {
        try {
          const user: UserInfo = await usersAPI.get(userId);
          setUsername(user.username);
          setEmail(user.email);
          setFullName(user.full_name);
          setRole(user.role);
          setIsActive(user.is_active);
        } catch {
          setError('Error al cargar usuario');
        } finally {
          setLoading(false);
        }
      };
      fetchUser();
    }
  }, [isEditing, userId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSaving(true);

    try {
      if (isEditing && userId) {
        const updateData: Record<string, unknown> = {
          username,
          email,
          full_name: fullName,
          role,
          is_active: isActive,
        };
        if (password) {
          updateData.password = password;
        }
        await usersAPI.update(userId, updateData);
      } else {
        if (!password) {
          setError('La contrasena es obligatoria');
          setSaving(false);
          return;
        }
        await usersAPI.create({
          username,
          email,
          full_name: fullName,
          password,
          role,
          is_active: isActive,
        });
      }
      navigate('/users');
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        setError(axiosErr.response?.data?.detail || 'Error al guardar usuario');
      } else {
        setError('Error al guardar usuario');
      }
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#f5a623]" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-[#0a1628] to-[#162040] rounded-2xl p-6 shadow-lg">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/users')}
            className="p-2 text-white/70 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-7 h-7" />
          </button>
          <div>
            <h1 className="text-4xl font-bold text-white">
              {isEditing ? 'Editar Usuario' : 'Nuevo Usuario'}
            </h1>
            <p className="text-slate-300 mt-1 text-xl">
              {isEditing ? 'Modificar datos del usuario' : 'Registrar un nuevo usuario en el sistema'}
            </p>
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
          <AlertCircle className="w-6 h-6 text-red-500" />
          <span className="text-red-700 text-lg">{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-white border border-gray-200 rounded-2xl p-6 space-y-5 shadow-lg">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Nombre Completo *
            </label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              className="w-full px-4 h-12 bg-white border border-gray-300 rounded-lg text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-[#f5a623] text-base"
              placeholder="Juan Perez"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Username *
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="w-full px-4 h-12 bg-white border border-gray-300 rounded-lg text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-[#f5a623] text-base"
              placeholder="jperez"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Email *
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full px-4 h-12 bg-white border border-gray-300 rounded-lg text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-[#f5a623] text-base"
            placeholder="jperez@empresa.com"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Contrasena {isEditing ? '(dejar vacio para no cambiar)' : '*'}
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required={!isEditing}
            className="w-full px-4 h-12 bg-white border border-gray-300 rounded-lg text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-[#f5a623] text-base"
            placeholder="••••••••"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Rol *
            </label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full px-4 h-12 bg-white border border-gray-300 rounded-lg text-gray-800 focus:outline-none focus:border-[#f5a623] text-base"
            >
              <option value="admin">Admin</option>
              <option value="analyst">Analyst</option>
              <option value="viewer">Viewer</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Estado
            </label>
            <div className="flex items-center gap-3 pt-2">
              <button
                type="button"
                onClick={() => setIsActive(!isActive)}
                className={`relative w-11 h-6 rounded-full transition-colors ${
                  isActive ? 'bg-emerald-500' : 'bg-gray-300'
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform shadow ${
                    isActive ? 'translate-x-5' : ''
                  }`}
                />
              </button>
              <span className={`text-base font-medium ${isActive ? 'text-emerald-600' : 'text-gray-500'}`}>
                {isActive ? 'Activo' : 'Inactivo'}
              </span>
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
          <button
            type="button"
            onClick={() => navigate('/users')}
            className="px-5 py-3 text-base text-gray-500 hover:text-gray-700 transition-colors"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={saving}
            className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-[#f5a623] to-[#e6951e] text-[#0a1628] rounded-lg font-bold disabled:opacity-50 text-base transition-all"
          >
            <Save className="w-5 h-5" />
            {saving ? 'Guardando...' : isEditing ? 'Actualizar' : 'Crear Usuario'}
          </button>
        </div>
      </form>
    </div>
  );
}
