/**
 * ClientsPage - CRUD de clientes - Admin only - SQA Light Theme
 */
import { useEffect, useState } from 'react';
import {
  Building2,
  Plus,
  Pencil,
  Trash2,
  Check,
  X,
  AlertCircle,
  Search,
} from 'lucide-react';
import { clientsAPI } from '../../services/api';
import type { ClientInfo } from '../../types';

export default function ClientsPage() {
  const [clients, setClients] = useState<ClientInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formContact, setFormContact] = useState('');
  const [formEmail, setFormEmail] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const fetchClients = async () => {
    try {
      const data = await clientsAPI.list();
      setClients(data);
    } catch {
      setError('Error al cargar clientes');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClients();
  }, []);

  const resetForm = () => {
    setFormName('');
    setFormDescription('');
    setFormContact('');
    setFormEmail('');
    setEditId(null);
    setShowModal(false);
  };

  const openCreate = () => {
    resetForm();
    setShowModal(true);
  };

  const openEdit = (client: ClientInfo) => {
    setEditId(client.id);
    setFormName(client.name);
    setFormDescription(client.description || '');
    setFormContact(client.contact_name || '');
    setFormEmail(client.contact_email || '');
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!formName.trim()) return;
    setError('');
    try {
      const payload = {
        name: formName.trim(),
        description: formDescription.trim() || undefined,
        contact_name: formContact.trim() || undefined,
        contact_email: formEmail.trim() || undefined,
      };
      if (editId) {
        await clientsAPI.update(editId, payload);
      } else {
        await clientsAPI.create(payload);
      }
      resetForm();
      await fetchClients();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setError(axiosErr.response?.data?.detail || 'Error al guardar cliente');
    }
  };

  const handleToggle = async (id: string, currentActive: boolean) => {
    setError('');
    try {
      await clientsAPI.update(id, { is_active: !currentActive });
      await fetchClients();
    } catch {
      setError('Error al cambiar estado del cliente');
    }
  };

  const handleDelete = async (id: string) => {
    setError('');
    try {
      await clientsAPI.delete(id);
      setDeleteConfirm(null);
      await fetchClients();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setError(axiosErr.response?.data?.detail || 'Error al eliminar cliente');
    }
  };

  const filteredClients = clients.filter(
    (c) =>
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      (c.description || '').toLowerCase().includes(search.toLowerCase()) ||
      (c.contact_name || '').toLowerCase().includes(search.toLowerCase()) ||
      (c.contact_email || '').toLowerCase().includes(search.toLowerCase())
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
            <h1 className="text-4xl font-bold text-white">Gestion de Clientes</h1>
            <p className="text-slate-300 mt-1 text-xl">{clients.length} clientes registrados</p>
          </div>
          <button
            onClick={openCreate}
            className="flex items-center gap-2 px-5 py-3 bg-gradient-to-r from-[#f5a623] to-[#e6951e] text-[#0a1628] font-bold rounded-xl hover:from-[#e6951e] hover:to-[#d4850f] transition-all text-xl shadow-lg"
          >
            <Plus className="w-6 h-6" />
            Nuevo Cliente
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
          placeholder="Buscar por nombre, descripcion, contacto o email..."
          className="w-full pl-12 pr-4 h-12 bg-white border border-gray-300 rounded-xl text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-[#f5a623] focus:ring-2 focus:ring-[#f5a623]/20 text-base"
        />
      </div>

      {/* Table */}
      <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden shadow-lg">
        <table className="w-full">
          <thead>
            <tr className="bg-[#0a1628] text-left">
              <th className="px-5 py-3 text-sm font-bold text-white uppercase tracking-wider">Nombre</th>
              <th className="px-5 py-3 text-sm font-bold text-white uppercase tracking-wider">Descripcion</th>
              <th className="px-5 py-3 text-sm font-bold text-white uppercase tracking-wider">Contacto</th>
              <th className="px-5 py-3 text-sm font-bold text-white uppercase tracking-wider">Email</th>
              <th className="px-5 py-3 text-sm font-bold text-white uppercase tracking-wider text-center">Estado</th>
              <th className="px-5 py-3 text-sm font-bold text-white uppercase tracking-wider text-right">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {filteredClients.map((client, idx) => (
              <tr
                key={client.id}
                className={`${idx % 2 === 0 ? 'bg-white' : 'bg-[#f8fafc]'} hover:bg-gray-100 transition-colors border-b border-gray-100`}
              >
                <td className="px-5 py-3">
                  <div className="flex items-center gap-3">
                    <Building2 className="w-5 h-5 text-[#f5a623]" />
                    <span className="text-base font-semibold text-gray-800">{client.name}</span>
                  </div>
                </td>
                <td className="px-5 py-3 text-base text-gray-600">{client.description || '-'}</td>
                <td className="px-5 py-3 text-base text-gray-700">{client.contact_name || '-'}</td>
                <td className="px-5 py-3 text-base text-gray-600">{client.contact_email || '-'}</td>
                <td className="px-5 py-3 text-center">
                  <button
                    onClick={() => handleToggle(client.id, client.is_active)}
                    className={`px-3 py-1 rounded-full text-xs font-bold uppercase border ${
                      client.is_active
                        ? 'bg-emerald-100 text-emerald-700 border-emerald-300'
                        : 'bg-red-100 text-red-700 border-red-300'
                    }`}
                  >
                    {client.is_active ? 'Activo' : 'Inactivo'}
                  </button>
                </td>
                <td className="px-5 py-3">
                  <div className="flex items-center justify-end gap-1">
                    <button
                      onClick={() => openEdit(client)}
                      className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                      title="Editar"
                    >
                      <Pencil className="w-5 h-5" />
                    </button>
                    <button
                      onClick={() => setDeleteConfirm(client.id)}
                      className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                      title="Eliminar"
                    >
                      <Trash2 className="w-5 h-5" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {filteredClients.length === 0 && (
              <tr>
                <td colSpan={6} className="px-6 py-12 text-center bg-white">
                  <Building2 className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                  <p className="text-gray-500 text-xl">No hay clientes registrados</p>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-white border border-gray-200 rounded-xl p-6 w-full max-w-lg shadow-2xl">
            <h3 className="text-2xl font-semibold text-gray-800 mb-4">
              {editId ? 'Editar Cliente' : 'Nuevo Cliente'}
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Nombre *</label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="Nombre del cliente"
                  autoFocus
                  className="w-full px-4 h-12 bg-white border border-gray-300 rounded-lg text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-[#f5a623] text-base"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Descripcion</label>
                <input
                  type="text"
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  placeholder="Descripcion breve"
                  className="w-full px-4 h-12 bg-white border border-gray-300 rounded-lg text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-[#f5a623] text-base"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Nombre de Contacto</label>
                <input
                  type="text"
                  value={formContact}
                  onChange={(e) => setFormContact(e.target.value)}
                  placeholder="Nombre del contacto"
                  className="w-full px-4 h-12 bg-white border border-gray-300 rounded-lg text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-[#f5a623] text-base"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email de Contacto</label>
                <input
                  type="email"
                  value={formEmail}
                  onChange={(e) => setFormEmail(e.target.value)}
                  placeholder="email@ejemplo.com"
                  className="w-full px-4 h-12 bg-white border border-gray-300 rounded-lg text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-[#f5a623] text-base"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={resetForm}
                className="px-5 py-3 text-base text-gray-500 hover:text-gray-700 transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleSave}
                disabled={!formName.trim()}
                className="px-5 py-3 bg-gradient-to-r from-[#f5a623] to-[#e6951e] text-[#0a1628] rounded-lg font-bold text-base hover:from-[#e6951e] hover:to-[#d4850f] disabled:opacity-50 transition-all"
              >
                <div className="flex items-center gap-2">
                  <Check className="w-5 h-5" />
                  {editId ? 'Guardar Cambios' : 'Crear Cliente'}
                </div>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-white border border-gray-200 rounded-xl p-6 w-full max-w-md shadow-2xl">
            <h3 className="text-2xl font-semibold text-gray-800 mb-2">Confirmar Eliminacion</h3>
            <p className="text-lg text-gray-500 mb-6">
              Se eliminara el cliente y todas sus asignaciones. Esta accion no se puede deshacer.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="px-5 py-3 text-base text-gray-500 hover:text-gray-700 transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={() => handleDelete(deleteConfirm)}
                className="px-5 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 text-base font-medium transition-colors"
              >
                Eliminar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
