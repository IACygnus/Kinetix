// frontend/src/components/script-designer/HARImportModal.tsx
import { useState, useRef } from 'react';
import { X, Upload, CheckCircle, Loader2 } from 'lucide-react';
import { harApi, ScriptModel, HARImportStats } from '../../api/scriptDesignerApi';

interface Props {
  onImport: (scriptModel: ScriptModel) => void;
  onClose: () => void;
}

export default function HARImportModal({ onImport, onClose }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [baseUrlFilter, setBaseUrlFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [preview, setPreview] = useState<{ scriptModel: ScriptModel; stats: HARImportStats } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) {
      setFile(f);
      setError('');
      setPreview(null);
    }
  };

  const handlePreview = async () => {
    if (!file) return;
    setLoading(true);
    setError('');
    try {
      const { data } = await harApi.preview(file, baseUrlFilter || undefined);
      setPreview({ scriptModel: data.script_model, stats: data.stats });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error parsing the HAR file');
    } finally {
      setLoading(false);
    }
  };

  const handleImport = () => {
    if (preview) onImport(preview.scriptModel);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-800">Import HAR File</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          {/* Instructions */}
          <div className="bg-blue-50 rounded-md p-3 text-xs text-blue-700">
            <strong>How to export a HAR file:</strong><br/>
            Chrome: DevTools &rarr; Network &rarr; right-click &rarr; "Save all as HAR with content"<br/>
            Firefox: DevTools &rarr; Network &rarr; gear icon &rarr; "Save All as HAR"
          </div>

          {/* File input */}
          <div>
            <label className="text-sm text-gray-700 font-medium mb-1.5 block">HAR file (.har)</label>
            <div
              onClick={() => fileRef.current?.click()}
              className="border-2 border-dashed border-gray-300 rounded-md p-6 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-colors"
            >
              {file ? (
                <p className="text-sm text-gray-700 flex items-center justify-center gap-2">
                  <Upload className="w-4 h-4" />
                  {file.name} <span className="text-gray-400">({(file.size / 1024).toFixed(0)} KB)</span>
                </p>
              ) : (
                <p className="text-sm text-gray-400">Click to select .har file</p>
              )}
              <input ref={fileRef} type="file" accept=".har" onChange={handleFileChange} className="hidden" />
            </div>
          </div>

          {/* URL filter */}
          <div>
            <label className="text-sm text-gray-700 font-medium mb-1.5 block">
              Base URL filter <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <input
              type="text"
              value={baseUrlFilter}
              onChange={e => setBaseUrlFilter(e.target.value)}
              placeholder="https://api.myapp.com"
              className="w-full text-sm font-mono border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-400 mt-1">Only import requests starting with this URL</p>
          </div>

          {/* Error */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Preview stats */}
          {preview && (
            <div className="bg-green-50 border border-green-200 rounded-md p-4">
              <p className="text-sm font-medium text-green-800 mb-2 flex items-center gap-1.5">
                <CheckCircle className="w-4 h-4" /> Ready to import
              </p>
              <div className="grid grid-cols-2 gap-2 text-xs text-green-700">
                <span>Total HAR entries: <strong>{preview.stats.total_entries}</strong></span>
                <span>To import: <strong>{preview.stats.imported}</strong></span>
                <span>Filtered (static): <strong>{preview.stats.filtered_static}</strong></span>
                <span>Filtered (trackers): <strong>{preview.stats.filtered_tracker}</strong></span>
              </div>
              <div className="mt-3 max-h-40 overflow-y-auto">
                {preview.scriptModel.requests.slice(0, 5).map((r, i) => (
                  <div key={i} className="text-xs text-green-700 py-0.5 truncate">
                    &bull; {r.method} {r.name}
                  </div>
                ))}
                {preview.scriptModel.requests.length > 5 && (
                  <div className="text-xs text-green-500">... and {preview.scriptModel.requests.length - 5} more</div>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">
            Cancel
          </button>
          {!preview ? (
            <button
              onClick={handlePreview}
              disabled={!file || loading}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 flex items-center gap-1.5"
            >
              {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              {loading ? 'Parsing...' : 'Parse HAR'}
            </button>
          ) : (
            <button
              onClick={handleImport}
              className="px-4 py-2 text-sm bg-green-600 text-white rounded-md hover:bg-green-700"
            >
              Import {preview.scriptModel.requests.length} requests
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
