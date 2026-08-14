// frontend/src/components/script-designer/DataFileManager.tsx
import { useState, useEffect, useRef } from 'react';
import { Upload, X, FileText, Loader2 } from 'lucide-react';
import { dataFileApi, DataFile, DataFilePreview } from '../../api/scriptDesignerApi';
import { useAuth } from '../../context/AuthContext';

interface Props {
  scriptId: number;
}

export default function DataFileManager({ scriptId }: Props) {
  // SEC-2: borrar es exclusivo de admin (el backend responde 403 al resto).
  const { user } = useAuth();
  const [files, setFiles] = useState<DataFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<DataFile | null>(null);
  const [preview, setPreview] = useState<DataFilePreview | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadFiles();
  }, [scriptId]);

  const loadFiles = async () => {
    setLoading(true);
    try {
      const { data } = await dataFileApi.listByScript(scriptId);
      setFiles(data);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await dataFileApi.upload(scriptId, file);
      await loadFiles();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error uploading file');
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const handlePreview = async (file: DataFile) => {
    setSelectedFile(file);
    try {
      const { data } = await dataFileApi.preview(file.id);
      setPreview(data);
    } catch {
      setPreview(null);
    }
  };

  const handleDelete = async (fileId: number) => {
    if (!confirm('Delete this data file?')) return;
    await dataFileApi.delete(fileId);
    await loadFiles();
    if (selectedFile?.id === fileId) {
      setSelectedFile(null);
      setPreview(null);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-gray-700">
          Data Files <span className="text-gray-400 font-normal text-xs">-- CSV files for parameterization</span>
        </h3>
        <button
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
          className="text-sm text-blue-600 hover:text-blue-700 font-medium disabled:opacity-50 flex items-center gap-1"
        >
          {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
          {uploading ? 'Uploading...' : 'Upload CSV'}
        </button>
        <input ref={fileRef} type="file" accept=".csv" onChange={handleUpload} className="hidden" />
      </div>

      {loading ? (
        <p className="text-xs text-gray-400">Loading...</p>
      ) : files.length === 0 ? (
        <p className="text-xs text-gray-400">No data files. Upload a CSV to parameterize your script.</p>
      ) : (
        <div className="flex gap-4">
          {/* File list */}
          <div className="flex-1">
            <div className="space-y-1">
              {files.map(f => (
                <div
                  key={f.id}
                  className={`flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer ${
                    selectedFile?.id === f.id ? 'bg-blue-50 border border-blue-200' : 'hover:bg-gray-50 border border-transparent'
                  }`}
                  onClick={() => handlePreview(f)}
                >
                  <FileText className="w-4 h-4 text-gray-400 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-700 truncate">{f.original_filename}</p>
                    <p className="text-xs text-gray-400">
                      {f.columns.length} columns &middot; {f.row_count ?? '?'} rows
                    </p>
                  </div>
                  {user?.role === 'admin' && (
                    <button
                      onClick={e => { e.stopPropagation(); handleDelete(f.id); }}
                      className="text-gray-300 hover:text-red-500"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Preview */}
          {preview && selectedFile && (
            <div className="flex-1 bg-gray-50 rounded-md p-3 text-xs overflow-auto max-h-48">
              <p className="font-medium text-gray-700 mb-2">
                Columns:{' '}
                {preview.columns.map((c: string) => (
                  <code key={c} className="bg-blue-100 text-blue-700 px-1 rounded mr-1">{`\${${c}}`}</code>
                ))}
              </p>
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-b border-gray-200">
                    {preview.columns.map((c: string) => (
                      <th key={c} className="text-left pr-4 pb-1 font-medium text-gray-600">{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((row: Record<string, string>, i: number) => (
                    <tr key={i} className="border-b border-gray-100">
                      {preview.columns.map((c: string) => (
                        <td key={c} className="pr-4 py-1 font-mono text-gray-700 truncate max-w-24">{row[c]}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
