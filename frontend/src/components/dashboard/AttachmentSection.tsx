/**
 * AttachmentSection — Generic component for file attachments in reports.
 * Used by MonitoringSection (KNX-13) and EvidenceSection (KNX-14).
 */
import { useState, useEffect, useCallback } from 'react';
import { Upload, Trash2, FileText } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

interface Attachment {
  id: string;
  title: string;
  description: string;
  category: string;
  filename: string;
  filepath: string;
  file_type: string;
  file_size: number;
  sort_order: number;
}

interface CategoryOption {
  value: string;
  label: string;
}

interface AttachmentSectionProps {
  executionId: string;
  attachmentType: 'monitoring' | 'evidence';
  title: string;
  icon: string;
  description: string;
  categories: CategoryOption[];
  textareaPlaceholder: string;
}

export default function AttachmentSection({
  executionId,
  attachmentType,
  title,
  icon,
  description,
  categories,
  textareaPlaceholder,
}: AttachmentSectionProps) {
  // SEC-2: borrar es exclusivo de admin (el backend responde 403 al resto).
  const { user } = useAuth();
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [uploading, setUploading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState(categories[0]?.value || '');
  const [attachTitle, setAttachTitle] = useState('');

  const getCsrfToken = () => document.cookie.match(/csrf_token=([^;]+)/)?.[1] || '';

  const loadAttachments = useCallback(async () => {
    try {
      const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';
      const res = await fetch(
        `${apiBase}/executions/${executionId}/attachments?attachment_type=${attachmentType}`,
        { credentials: 'include' },
      );
      if (res.ok) {
        setAttachments(await res.json());
      }
    } catch (err) {
      console.error('Error loading attachments:', err);
    }
  }, [executionId, attachmentType]);

  useEffect(() => {
    loadAttachments();
  }, [loadAttachments]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';
    const csrfToken = getCsrfToken();

    for (const file of Array.from(files)) {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('attachment_type', attachmentType);
      formData.append('title', attachTitle || file.name);
      formData.append('category', selectedCategory);
      formData.append('sort_order', String(attachments.length));

      await fetch(`${apiBase}/executions/${executionId}/attachments`, {
        method: 'POST',
        body: formData,
        credentials: 'include',
        headers: { 'X-CSRF-Token': csrfToken },
      });
    }
    setUploading(false);
    setAttachTitle('');
    e.target.value = '';
    loadAttachments();
  };

  const handleDelete = async (attachmentId: string) => {
    if (!confirm('Eliminar este adjunto?')) return;
    const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';
    await fetch(`${apiBase}/executions/${executionId}/attachments/${attachmentId}`, {
      method: 'DELETE',
      credentials: 'include',
      headers: { 'X-CSRF-Token': getCsrfToken() },
    });
    loadAttachments();
  };

  const handleUpdateDescription = async (attachmentId: string, newDescription: string) => {
    const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';
    const formData = new FormData();
    formData.append('description', newDescription);
    await fetch(`${apiBase}/executions/${executionId}/attachments/${attachmentId}`, {
      method: 'PUT',
      body: formData,
      credentials: 'include',
      headers: { 'X-CSRF-Token': getCsrfToken() },
    });
  };

  const mediaBase = import.meta.env.VITE_API_BASE_URL
    ? import.meta.env.VITE_API_BASE_URL.replace('/api/v1', '')
    : 'http://localhost:8001';

  return (
    <div className="mb-8">
      <div className="bg-white rounded-2xl shadow-lg overflow-hidden border border-gray-200">
        <div className="bg-[#0a1628] px-6 py-4">
          <h2 className="text-3xl font-bold text-white flex items-center gap-2">
            {icon} {title}
            <span className="ml-2 text-xl bg-white/20 rounded-full px-3 py-0.5">
              {attachments.length} adjuntos
            </span>
          </h2>
        </div>

        <div className="p-6">
          <p className="text-lg text-gray-500 mb-4">{description}</p>

          {/* Upload form */}
          <div className="bg-gray-50 rounded-xl p-4 mb-6 border border-gray-200">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="text-base font-medium text-gray-600 block mb-1">Categoria</label>
                <select
                  value={selectedCategory}
                  onChange={(e) => setSelectedCategory(e.target.value)}
                  className="w-full bg-white text-gray-800 rounded-xl px-4 py-3 text-lg border border-gray-300 focus:border-[#f5a623] focus:ring-2 focus:ring-[#f5a623]/20"
                >
                  {categories.map((c) => (
                    <option key={c.value} value={c.value}>{c.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-base font-medium text-gray-600 block mb-1">Titulo (opcional)</label>
                <input
                  type="text"
                  value={attachTitle}
                  onChange={(e) => setAttachTitle(e.target.value)}
                  placeholder="Ej: CPU durante prueba"
                  className="w-full bg-white text-gray-800 rounded-xl px-4 py-3 text-lg border border-gray-300 focus:border-[#f5a623] focus:ring-2 focus:ring-[#f5a623]/20"
                />
              </div>
              <div className="flex items-end">
                <label className="flex items-center gap-2 px-6 py-3 bg-[#f5a623] text-[#0a1628] rounded-xl cursor-pointer hover:bg-[#f5a623]/90 text-lg font-bold transition-colors">
                  <Upload className="w-5 h-5" />
                  {uploading ? 'Subiendo...' : 'Adjuntar'}
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/gif,image/webp,.csv"
                    multiple
                    onChange={handleUpload}
                    disabled={uploading}
                    className="hidden"
                  />
                </label>
              </div>
            </div>
          </div>

          {/* Attachments list */}
          {attachments.length === 0 ? (
            <p className="text-lg text-gray-400 text-center py-8">
              No hay adjuntos. Use el boton de arriba para agregar.
            </p>
          ) : (
            <div className="space-y-4">
              {attachments.map((att) => (
                <div key={att.id} className="border border-gray-200 rounded-xl p-4 bg-white shadow-sm">
                  <div className="flex justify-between items-start mb-3">
                    <div className="flex items-center gap-2">
                      <span className="text-sm px-2 py-1 rounded-full bg-blue-50 text-blue-700 font-semibold uppercase">
                        {att.category}
                      </span>
                      <h3 className="text-xl font-medium text-gray-800">{att.title}</h3>
                    </div>
                    {user?.role === 'admin' && <button
                      onClick={() => handleDelete(att.id)}
                      className="text-red-400 hover:text-red-600 transition-colors p-1"
                      title="Eliminar"
                    >
                      <Trash2 className="w-5 h-5" />
                    </button>}
                  </div>

                  {/* Image preview */}
                  {att.file_type.startsWith('image/') && (
                    <img
                      src={`${mediaBase}${att.filepath}`}
                      alt={att.title}
                      className="max-w-full max-h-[500px] rounded-xl border border-gray-200 mb-3 object-contain bg-gray-50"
                    />
                  )}

                  {/* CSV indicator */}
                  {(att.file_type === 'text/csv' || att.file_type === 'application/vnd.ms-excel') && (
                    <div className="bg-gray-50 rounded-xl p-4 mb-3 flex items-center gap-2 text-lg text-gray-600 border border-gray-200">
                      <FileText className="w-5 h-5" />
                      Archivo CSV: {att.filename}
                    </div>
                  )}

                  {/* Editable analysis text */}
                  <span className="text-xs text-gray-400 italic mb-1 block">Click para editar</span>
                  <textarea
                    defaultValue={att.description || ''}
                    onBlur={(e) => handleUpdateDescription(att.id, e.target.value)}
                    placeholder={textareaPlaceholder}
                    className="w-full min-h-[100px] p-4 border-2 border-gray-300 rounded-xl text-xl text-gray-800 focus:ring-2 focus:ring-orange-400/50 focus:border-orange-500 resize-y cursor-text hover:border-orange-300 transition-colors"
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
