/**
 * UserList - Tabla CRUD de usuarios - Admin only - SQA Light Theme
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Plus,
  Edit2,
  ToggleLeft,
  ToggleRight,
  KeyRound,
  AlertCircle,
  Users,
  Search,
  X,
} from 'lucide-react';
import { usersAPI } from '../../services/api';
import type { UserInfo } from '../../types';

const ROLE_BADGES: Record<string, { label: string; classes: string }> = {
  admin: { label: 'Admin', classes: 'bg-purple-100 text-purple-700 border-purple-300' },
  analyst: { label: 'Analyst', classes: 'bg-blue-100 text-blue-700 border-blue-300' },
  viewer: { label: 'Viewer', classes: 'bg-gray-100 text-gray-700 border-gray-300' },
};

export default function UserList() {
  const navigate = useNavigate();
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [resetModal, setResetModal] = useState<{ userId: string; username: string } | null>(null);
  const [newPassword, setNewPassword] = useState('');
  const [actionLoading, setActionLoading] = useState('');

  const fetchUsers = async () => {
    try {
      const data = await usersAPI.list();
      setUsers(data);
    } catch {
      setError('Error al cargar usuarios');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleToggle = async (userId: string) => {
    setActionLoading(userId);
    try {
      await usersAPI.toggle(userId);
      await fetchUsers();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al cambiar estado';
      setError(msg);
    } finally {
      setActionLoading('');
    }
  };

  const handleResetPassword = async () => {
    if (!resetModal || !newPassword) return;
    setActionLoading(resetModal.userId);
    try {
      await usersAPI.resetPassword(resetModal.userId, newPassword);
      setResetModal(null);
      setNewPassword('');
    } catch {
      setError('Error al resetear contrasena');
    } finally {
      setActionLoading('');
    }
  };

  const filteredUsers = users.filter(
    (u) =>
      u.full_name.toLowerCase().includes(search.toLowerCase()) ||
      u.username.toLowerCase().includes(search.toLowerCase()) ||
      u.email.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#f5a623]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-[#0a1628] to-[#162040] rounded-2xl p-6 shadow-lg">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold text-white">Gestion de Usuarios</h1>
            <p className="text-slate-300 mt-1 text-xl">{users.length} usuarios registrados</p>
          </div>
          <button
            onClick={() => navigate('/users/new')}
            className="flex items-center gap-2 px-5 py-3 bg-gradient-to-r from-[#f5a623] to-[#e6951e] text-[#0a1628] font-bold rounded-xl hover:from-[#e6951e] hover:to-[#d4850f] transition-all text-xl shadow-lg"
          >
            <Plus className="w-6 h-6" />
            Nuevo Usuario
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
          <AlertCircle className="w-6 h-6 text-red-500" />
          <span className="text-red-700 text-lg">{error}</span>
          <button onClick={() => setError('')} className="ml-auto text-red-400 hover:text-red-600">
            <X className="w-5 h-5" />
          </button>
        </div>
      )}

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-6 h-6 text-gray-400" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar por nombre, username o email..."
          className="w-full pl-12 pr-4 h-12 bg-white border border-gray-300 rounded-xl text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-[#f5a623] focus:ring-2 focus:ring-[#f5a623]/20 text-base"
        />
      </div>

      {/* Table */}
      <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden shadow-lg">
        <table className="w-full">
          <thead>
            <tr className="bg-[#0a1628] text-left">
              <th className="px-5 py-3 text-sm font-bold text-white uppercase tracking-wider">Usuario</th>
              <th className="px-5 py-3 text-sm font-bold text-white uppercase tracking-wider">Email</th>
              <th className="px-5 py-3 text-sm font-bold text-white uppercase tracking-wider">Rol</th>
              <th className="px-5 py-3 text-sm font-bold text-white uppercase tracking-wider text-center">Estado</th>
              <th className="px-5 py-3 text-sm font-bold text-white uppercase tracking-wider">Creado</th>
              <th className="px-5 py-3 text-sm font-bold text-white uppercase tracking-wider text-right">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {filteredUsers.map((u, idx) => {
              const badge = ROLE_BADGES[u.role] || ROLE_BADGES.viewer;
              return (
                <tr
                  key={u.id}
                  className={`${idx % 2 === 0 ? 'bg-white' : 'bg-[#f8fafc]'} hover:bg-gray-100 transition-colors border-b border-gray-100`}
                >
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-[#f5a623]/20 rounded-full flex items-center justify-center flex-shrink-0">
                        <span className="text-base font-bold text-[#f5a623]">
                          {u.full_name.charAt(0).toUpperCase()}
                        </span>
                      </div>
                      <div>
                        <p className="text-base font-semibold text-gray-800">{u.full_name}</p>
                        <p className="text-sm text-gray-500">@{u.username}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-3 text-base text-gray-600">{u.email}</td>
                  <td className="px-5 py-3">
                    <span className={`inline-flex px-3 py-1 text-xs font-bold uppercase rounded-full border ${badge.classes}`}>
                      {badge.label}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-center">
                    <span
                      className={`inline-flex items-center gap-1.5 text-sm font-medium ${
                        u.is_active ? 'text-emerald-600' : 'text-gray-400'
                      }`}
                    >
                      <span
                        className={`w-2 h-2 rounded-full ${
                          u.is_active ? 'bg-emerald-500' : 'bg-gray-400'
                        }`}
                      />
                      {u.is_active ? 'Activo' : 'Inactivo'}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-base text-gray-500">
                    {new Date(u.created_at).toLocaleDateString('es-ES')}
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => navigate(`/users/${u.id}`)}
                        className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                        title="Editar"
                      >
                        <Edit2 className="w-5 h-5" />
                      </button>
                      <button
                        onClick={() => handleToggle(u.id)}
                        disabled={actionLoading === u.id}
                        className="p-2 text-gray-400 hover:text-amber-600 hover:bg-amber-50 rounded transition-colors"
                        title={u.is_active ? 'Desactivar' : 'Activar'}
                      >
                        {u.is_active ? (
                          <ToggleRight className="w-5 h-5" />
                        ) : (
                          <ToggleLeft className="w-5 h-5" />
                        )}
                      </button>
                      <button
                        onClick={() =>
                          setResetModal({ userId: u.id, username: u.username })
                        }
                        className="p-2 text-gray-400 hover:text-orange-600 hover:bg-orange-50 rounded transition-colors"
                        title="Resetear contrasena"
                      >
                        <KeyRound className="w-5 h-5" />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
            {filteredUsers.length === 0 && (
              <tr>
                <td colSpan={6} className="px-6 py-12 text-center bg-white">
                  <Users className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                  <p className="text-gray-500 text-xl">No se encontraron usuarios</p>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Reset Password Modal */}
      {resetModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-white border border-gray-200 rounded-xl p-6 w-full max-w-md shadow-2xl">
            <h3 className="text-2xl font-semibold text-gray-800 mb-4">
              Resetear Contrasena
            </h3>
            <p className="text-lg text-gray-500 mb-4">
              Nueva contrasena para <strong className="text-gray-800">@{resetModal.username}</strong>
            </p>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Nueva contrasena"
              className="w-full px-4 h-12 bg-white border border-gray-300 rounded-lg text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-[#f5a623] mb-4 text-base"
            />
            <div className="flex justify-end gap-3">
              <button
                onClick={() => {
                  setResetModal(null);
                  setNewPassword('');
                }}
                className="px-5 py-3 text-base text-gray-500 hover:text-gray-700 transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleResetPassword}
                disabled={!newPassword || actionLoading === resetModal.userId}
                className="px-5 py-3 bg-gradient-to-r from-[#f5a623] to-[#e6951e] text-[#0a1628] rounded-lg font-bold disabled:opacity-50 text-base transition-all"
              >
                Resetear
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
