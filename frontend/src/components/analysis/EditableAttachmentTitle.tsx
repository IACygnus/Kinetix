/**
 * EditableAttachmentTitle — Inline editable title for uploaded attachments.
 * Hover shows pencil icon, click activates input, Enter/blur saves.
 */
import { useState, useRef, useEffect, useCallback } from 'react';
import { Pencil } from 'lucide-react';

interface Props {
  attachmentId: string;
  executionId: string;
  currentTitle: string;
  onTitleSaved: (attachmentId: string, newTitle: string) => void;
}

export default function EditableAttachmentTitle({ attachmentId, executionId, currentTitle, onTitleSaved }: Props) {
  const [isEditing, setIsEditing] = useState(false);
  const [title, setTitle] = useState(currentTitle);
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { setTitle(currentTitle); }, [currentTitle]);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const getCsrfToken = () => document.cookie.match(/csrf_token=([^;]+)/)?.[1] || '';
  const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';

  const handleSave = useCallback(async () => {
    const trimmed = title.trim();
    if (trimmed === currentTitle || !trimmed) {
      setTitle(currentTitle);
      setIsEditing(false);
      return;
    }
    setSaving(true);
    try {
      const formData = new FormData();
      formData.append('title', trimmed);
      await fetch(`${apiBase}/executions/${executionId}/attachments/${attachmentId}`, {
        method: 'PUT', body: formData, credentials: 'include',
        headers: { 'X-CSRF-Token': getCsrfToken() },
      });
      onTitleSaved(attachmentId, trimmed);
    } catch (err) {
      console.error('Error saving title:', err);
      setTitle(currentTitle);
    }
    setSaving(false);
    setIsEditing(false);
  }, [title, currentTitle, executionId, attachmentId, onTitleSaved, apiBase]);

  if (isEditing) {
    return (
      <input
        ref={inputRef}
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        onBlur={handleSave}
        onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') { setTitle(currentTitle); setIsEditing(false); } }}
        disabled={saving}
        className="border border-[#f5a623] rounded-lg px-3 py-1 text-lg text-gray-800 min-w-[200px] focus:ring-2 focus:ring-[#f5a623]/30"
        placeholder="Titulo de la imagen"
      />
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 group">
      <span className="text-xl font-medium text-gray-800">{currentTitle || 'Sin titulo'}</span>
      <button onClick={() => setIsEditing(true)}
        className="opacity-0 group-hover:opacity-100 transition-opacity text-gray-400 hover:text-[#f5a623] p-0.5"
        title="Editar titulo">
        <Pencil className="w-4 h-4" />
      </button>
    </span>
  );
}
