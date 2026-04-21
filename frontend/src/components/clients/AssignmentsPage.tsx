/**
 * AssignmentsPage - Asignacion de clientes a usuarios - Admin only - SQA Light Theme
 */
import { useEffect, useState } from 'react';
import {
  Building2,
  Plus,
  X,
  AlertCircle,
  ChevronDown,
  Users,
} from 'lucide-react';
import { clientsAPI } from '../../services/api';
import type { ClientInfo, UserWithClients } from '../../types';

export default function AssignmentsPage() {
  const [assignments, setAssignments] = useState<UserWithClients[]>([]);
  const [clients, setClients] = useState<ClientInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [addingFor, setAddingFor] = useState<string | null>(null);
  const [selectedClient, setSelectedClient] = useState('');

  const fetchData = async () => {
    try {
      const [assignData, clientData] = await Promise.all([
        clientsAPI.getAssignments(),
        clientsAPI.list(),
      ]);
      setAssignments(assignData);
      setClients(clientData);
    } catch {
      setError('Error al cargar asignaciones');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleAssign = async (userId: string) => {
    if (!selectedClient) return;
    setError('');
    try {
      await clientsAPI.assign({ user_id: userId, client_id: selectedClient });
      setAddingFor(null);
      setSelectedClient('');
      await fetchData();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setError(axiosErr.response?.data?.detail || 'Error al asignar cliente');
    }
  };

  const handleUnassign = async (userId: string, clientId: string) => {
    setError('');
    try {
      await clientsAPI.unassign(userId, clientId);
      await fetchData();
    } catch {
      setError('Error al remover asignacion');
    }
  };

  const getAvailableClients = (user: UserWithClients) => {
    const assignedIds = new Set(user.clients.map((c) => c.id));
    return clients.filter((c) => c.is_active && !assignedIds.has(c.id));
  };

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
        <h1 className="text-4xl font-bold text-white">Asignaciones Usuario-Cliente</h1>
        <p className="text-slate-300 mt-1 text-xl">
          Asignar clientes a usuarios para controlar acceso a reportes
        </p>
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

      {/* Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl p-5 border border-gray-200 shadow-sm">
          <p className="text-sm text-gray-500 uppercase tracking-wider">Usuarios Activos</p>
          <p className="text-3xl font-bold text-gray-800 mt-1">{assignments.length}</p>
        </div>
        <div className="bg-white rounded-xl p-5 border border-gray-200 shadow-sm">
          <p className="text-sm text-gray-500 uppercase tracking-wider">Clientes Activos</p>
          <p className="text-3xl font-bold text-gray-800 mt-1">{clients.filter((c) => c.is_active).length}</p>
        </div>
        <div className="bg-white rounded-xl p-5 border border-gray-200 shadow-sm">
          <p className="text-sm text-gray-500 uppercase tracking-wider">Total Asignaciones</p>
          <p className="text-3xl font-bold text-[#f5a623] mt-1">
            {assignments.reduce((sum, u) => sum + u.clients.length, 0)}
          </p>
        </div>
      </div>

      {/* Users with assignments */}
      <div className="space-y-4">
        {assignments.map((user) => {
          const available = getAvailableClients(user);
          const isAdding = addingFor === user.id;

          return (
            <div
              key={user.id}
              className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm"
            >
              {/* User header */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-[#f5a623]/15 rounded-full flex items-center justify-center">
                    <span className="text-xl font-bold text-[#f5a623]">
                      {user.full_name.charAt(0).toUpperCase()}
                    </span>
                  </div>
                  <div>
                    <p className="text-base font-semibold text-gray-800">{user.full_name}</p>
                    <p className="text-sm text-gray-500">
                      @{user.username} &middot;{' '}
                      <span className={`capitalize font-medium ${
                        user.role === 'admin' ? 'text-purple-600' : 'text-blue-600'
                      }`}>{user.role}</span>
                    </p>
                  </div>
                </div>

                {user.role !== 'admin' && available.length > 0 && (
                  <button
                    onClick={() => {
                      setAddingFor(isAdding ? null : user.id);
                      setSelectedClient('');
                    }}
                    className="flex items-center gap-2 px-4 py-2 text-[#f5a623] border border-[#f5a623]/40 rounded-lg hover:bg-[#f5a623]/10 transition-colors text-sm font-medium"
                  >
                    <Plus className="w-4 h-4" />
                    Asignar Cliente
                  </button>
                )}
              </div>

              {/* Admin badge */}
              {user.role === 'admin' && (
                <p className="text-sm text-gray-400 italic mb-3">
                  Los administradores tienen acceso a todos los clientes automaticamente.
                </p>
              )}

              {/* Assigned clients chips */}
              {user.clients.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-3">
                  {user.clients.map((client) => (
                    <div
                      key={client.id}
                      className="flex items-center gap-2 px-3 py-1.5 bg-[#f5a623]/10 border border-[#f5a623]/30 rounded-lg"
                    >
                      <Building2 className="w-4 h-4 text-[#f5a623]" />
                      <span className="text-sm font-medium text-gray-700">{client.name}</span>
                      {user.role !== 'admin' && (
                        <button
                          onClick={() => handleUnassign(user.id, client.id)}
                          className="ml-1 p-0.5 text-gray-400 hover:text-red-500 transition-colors"
                          title="Remover asignacion"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {user.role !== 'admin' && user.clients.length === 0 && (
                <p className="text-sm text-gray-400 mb-3">Sin clientes asignados</p>
              )}

              {/* Add assignment inline */}
              {isAdding && (
                <div className="flex items-center gap-3 mt-3 pt-3 border-t border-gray-200">
                  <div className="relative flex-1 max-w-sm">
                    <select
                      value={selectedClient}
                      onChange={(e) => setSelectedClient(e.target.value)}
                      className="w-full px-4 h-10 bg-white border border-gray-300 rounded-lg text-gray-800 text-base appearance-none focus:outline-none focus:border-[#f5a623] pr-10"
                    >
                      <option value="">Seleccionar cliente...</option>
                      {available.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
                  </div>
                  <button
                    onClick={() => handleAssign(user.id)}
                    disabled={!selectedClient}
                    className="px-4 py-2 bg-gradient-to-r from-[#f5a623] to-[#e6951e] text-[#0a1628] font-bold rounded-lg disabled:bg-gray-200 disabled:text-gray-400 disabled:from-gray-200 disabled:to-gray-200 transition-all text-sm"
                  >
                    Asignar
                  </button>
                  <button
                    onClick={() => { setAddingFor(null); setSelectedClient(''); }}
                    className="p-2 text-gray-400 hover:text-red-500 transition-colors"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
              )}
            </div>
          );
        })}

        {assignments.length === 0 && (
          <div className="bg-white border border-gray-200 rounded-xl p-12 text-center shadow-sm">
            <Users className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 text-xl">No hay usuarios activos</p>
          </div>
        )}
      </div>
    </div>
  );
}
