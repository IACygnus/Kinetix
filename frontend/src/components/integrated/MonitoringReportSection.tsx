/**
 * MonitoringReportSection — Images + per-image AI analysis for integrated report.
 * Reusable for both monitoring and evidence attachment types.
 */
import { useState, useEffect } from 'react';

interface Attachment {
  id: string;
  title: string;
  category: string;
  filename: string;
  filepath: string;
  file_type: string;
  ai_analysis: string | null;
  ai_analysis_updated_at: string | null;
}

interface Props {
  executionId: string;
  attachmentType: 'monitoring' | 'evidence';
  sectionTitle: string;
  onImageAnalysisEdit?: (attachmentId: string, value: string) => void;
}

export default function MonitoringReportSection({ executionId, attachmentType, sectionTitle, onImageAnalysisEdit }: Props) {
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [loading, setLoading] = useState(true);
  const [editedAnalyses, setEditedAnalyses] = useState<Record<string, string>>({});

  const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';
  const mediaBase = apiBase.replace('/api/v1', '');

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${apiBase}/executions/${executionId}/image-analyses?attachment_type=${attachmentType}`, { credentials: 'include' });
        if (res.ok) setAttachments(await res.json());
      } catch { /* ignore */ }
      setLoading(false);
    };
    load();
  }, [executionId, attachmentType, apiBase]);

  if (loading) return null;
  if (attachments.length === 0) return null;

  const handleEdit = (attId: string, value: string) => {
    setEditedAnalyses(prev => ({ ...prev, [attId]: value }));
    onImageAnalysisEdit?.(attId, value);
  };

  return (
    <div className="mt-6">
      <h3 className="text-3xl font-bold text-gray-800 mb-4 border-l-4 border-[#0a1628] pl-4">{sectionTitle}</h3>
      <div className="space-y-4">
        {attachments.map(att => (
          <div key={att.id} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-6">
            <div className="border-l-4 border-[#0a1628] pl-4 mb-4">
              <h4 className="text-2xl font-bold text-gray-800">{att.title || att.filename}</h4>
            </div>
            {att.file_type?.startsWith('image/') && (
              <img
                src={`${mediaBase}${att.filepath}`}
                alt={att.title || att.filename}
                className="w-full max-h-[800px] rounded-xl object-contain bg-white mb-4"
              />
            )}
            {(att.ai_analysis || editedAnalyses[att.id]) && (
              <div className="mt-4 bg-white rounded-xl p-5 border-l-4 border-orange-500 border border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-bold text-orange-600 text-xl">Analisis</h4>
                  <span className="text-xs text-gray-400 italic">Click para editar</span>
                </div>
                <textarea
                  value={editedAnalyses[att.id] ?? att.ai_analysis ?? ''}
                  onChange={(e) => handleEdit(att.id, e.target.value)}
                  className="w-full p-4 border-2 border-gray-300 rounded-xl text-xl text-gray-800 resize-y cursor-text hover:border-orange-300 focus:ring-2 focus:ring-orange-400/50 focus:border-orange-500 transition-colors"
                  style={{ minHeight: '176px' }}
                />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
