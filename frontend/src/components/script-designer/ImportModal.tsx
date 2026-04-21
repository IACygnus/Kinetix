// frontend/src/components/script-designer/ImportModal.tsx
/**
 * Sprint 5 — Unified Import Modal
 * Supports: Postman, OpenAPI/Swagger, WSDL/SOAP, HAR, Chrome Extension
 */
import { useState, useRef, useEffect } from 'react';
import { X, Upload, CheckCircle, Loader2, FileJson, FileCode, Globe, Radio } from 'lucide-react';
import { ScriptModel } from '../../api/scriptDesignerApi';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000,
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  if (config.method && config.method !== 'get') {
    const csrfToken = document.cookie
      .split('; ')
      .find((row) => row.startsWith('csrf_token='))
      ?.split('=')[1];
    if (csrfToken) config.headers['X-CSRF-Token'] = csrfToken;
  }
  return config;
});

type ImportFormat = 'postman' | 'openapi' | 'wsdl' | 'har' | 'chrome';

interface FormatConfig {
  label: string;
  icon: typeof FileJson;
  accept: string;
  description: string;
  color: string;
}

const FORMATS: Record<Exclude<ImportFormat, 'chrome'>, FormatConfig> = {
  postman: {
    label: 'Postman Collection',
    icon: FileJson,
    accept: '.json',
    description: 'Import from Postman Collection v2.0/v2.1 JSON export',
    color: 'text-orange-600 bg-orange-50 border-orange-200',
  },
  openapi: {
    label: 'OpenAPI / Swagger',
    icon: FileCode,
    accept: '.json,.yaml,.yml',
    description: 'Import from OpenAPI 3.x or Swagger 2.0 spec (JSON or YAML)',
    color: 'text-green-600 bg-green-50 border-green-200',
  },
  wsdl: {
    label: 'SOAP / WSDL',
    icon: Globe,
    accept: '.wsdl,.xml',
    description: 'Import from WSDL XML service definition',
    color: 'text-blue-600 bg-blue-50 border-blue-200',
  },
  har: {
    label: 'HAR File',
    icon: Globe,
    accept: '.har',
    description: 'Import from HTTP Archive recorded in browser DevTools',
    color: 'text-purple-600 bg-purple-50 border-purple-200',
  },
};

interface Props {
  onImport: (scriptModel: ScriptModel, source: string) => void;
  onClose: () => void;
}

export default function ImportModal({ onImport, onClose }: Props) {
  const [format, setFormat] = useState<ImportFormat | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<{ scriptModel: ScriptModel; stats: Record<string, number>; source: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // Chrome recording state
  const [chromeSessionId, setChromeSessionId] = useState('');
  const [chromePending, setChromePending] = useState<number>(0);
  const [chromePolling, setChromePolling] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) {
      setFile(f);
      setError('');
      setResult(null);
    }
  };

  const handleParse = async () => {
    if (!file || !format || format === 'chrome') return;
    setLoading(true);
    setError('');

    const formData = new FormData();
    formData.append('file', file);

    let endpoint = '';
    if (format === 'postman') endpoint = '/import/postman';
    else if (format === 'openapi') endpoint = '/import/openapi';
    else if (format === 'wsdl') endpoint = '/import/wsdl';
    else if (format === 'har') {
      // HAR uses the existing har-import/preview endpoint
      endpoint = '/har-import/preview';
    }

    try {
      const { data } = await api.post(endpoint, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult({
        scriptModel: data.script_model,
        stats: data.stats,
        source: data.source || format,
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || `Error parsing ${format} file`);
    } finally {
      setLoading(false);
    }
  };

  const handleImport = () => {
    if (result) onImport(result.scriptModel, result.source);
  };

  // Chrome polling
  useEffect(() => {
    if (!chromePolling || !chromeSessionId) return;
    const interval = setInterval(async () => {
      try {
        const { data } = await api.get(`/import/chrome/pending/${chromeSessionId}`);
        setChromePending(data.total_requests);
      } catch {
        // ignore polling errors
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [chromePolling, chromeSessionId]);

  const handleChromeConvert = async () => {
    if (!chromeSessionId) return;
    setLoading(true);
    setError('');
    setChromePolling(false);
    try {
      const { data } = await api.post(`/import/chrome/convert/${chromeSessionId}`);
      setResult({
        scriptModel: data.script_model,
        stats: data.stats,
        source: 'chrome',
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error converting Chrome recording');
    } finally {
      setLoading(false);
    }
  };

  // Format selection screen
  if (!format) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl">
          <div className="px-6 py-5 border-b border-gray-200 flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-gray-800">Import Script</h2>
              <p className="text-sm text-gray-500 mt-0.5">Choose an import source</p>
            </div>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="p-6 grid grid-cols-1 sm:grid-cols-2 gap-3">
            {(Object.entries(FORMATS) as [Exclude<ImportFormat, 'chrome'>, FormatConfig][]).map(([key, cfg]) => {
              const Icon = cfg.icon;
              return (
                <button
                  key={key}
                  onClick={() => setFormat(key)}
                  className={`flex items-start gap-3 p-4 rounded-lg border-2 border-gray-200 hover:border-[#f5a623] hover:bg-[#f5a623]/5 transition-all text-left group`}
                >
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${cfg.color.split(' ').slice(1).join(' ')} border`}>
                    <Icon className={`w-5 h-5 ${cfg.color.split(' ')[0]}`} />
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-semibold text-gray-800 group-hover:text-[#f5a623]">{cfg.label}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{cfg.description}</p>
                  </div>
                </button>
              );
            })}

            {/* Chrome Extension option */}
            <button
              onClick={() => setFormat('chrome')}
              className="flex items-start gap-3 p-4 rounded-lg border-2 border-gray-200 hover:border-[#f5a623] hover:bg-[#f5a623]/5 transition-all text-left group sm:col-span-2"
            >
              <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-red-50 border border-red-200">
                <Radio className="w-5 h-5 text-red-600" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-semibold text-gray-800 group-hover:text-[#f5a623]">Chrome Extension Recording</p>
                <p className="text-xs text-gray-500 mt-0.5">Import requests recorded by the SQA Kinetix Pro Chrome Extension</p>
              </div>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Chrome recording screen
  if (format === 'chrome') {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg">
          <div className="px-6 py-5 border-b border-gray-200 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <button onClick={() => { setFormat(null); setChromePolling(false); }} className="text-gray-400 hover:text-gray-600 text-sm">&larr;</button>
              <h2 className="text-lg font-bold text-gray-800">Chrome Extension</h2>
            </div>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="p-6 space-y-4">
            <div className="bg-red-50 rounded-lg p-3 text-xs text-red-700">
              <strong>How it works:</strong><br />
              1. Open the SQA Kinetix Pro Chrome Extension<br />
              2. Enter the session ID below and start recording<br />
              3. Navigate the target application<br />
              4. Stop recording and click "Convert" here
            </div>

            <div>
              <label className="text-sm text-gray-700 font-medium mb-1.5 block">Session ID</label>
              <input
                type="text"
                value={chromeSessionId}
                onChange={e => setChromeSessionId(e.target.value)}
                placeholder="Paste the session ID from the extension"
                className="w-full text-sm font-mono border border-gray-300 rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#f5a623]/50 focus:border-[#f5a623]"
              />
            </div>

            {!chromePolling ? (
              <button
                onClick={() => setChromePolling(true)}
                disabled={!chromeSessionId}
                className="w-full px-4 py-2.5 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 font-medium"
              >
                Start Polling
              </button>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center gap-3 bg-red-50 border border-red-200 rounded-lg p-3">
                  <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
                  <span className="text-sm text-red-700 font-medium">
                    Waiting for requests... ({chromePending} captured)
                  </span>
                </div>
                <button
                  onClick={handleChromeConvert}
                  disabled={chromePending === 0 || loading}
                  className="w-full px-4 py-2.5 text-sm bg-[#f5a623] text-[#0a1628] rounded-lg hover:bg-[#e6951e] disabled:opacity-50 font-bold flex items-center justify-center gap-2"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                  {loading ? 'Converting...' : `Convert ${chromePending} Requests`}
                </button>
              </div>
            )}

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">{error}</div>
            )}

            {result && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <p className="text-sm font-medium text-green-800 mb-2 flex items-center gap-1.5">
                  <CheckCircle className="w-4 h-4" /> Ready to import
                </p>
                <p className="text-xs text-green-700">
                  {result.scriptModel.requests.length} requests ready
                  {result.stats.filtered ? ` (${result.stats.filtered} filtered)` : ''}
                </p>
              </div>
            )}
          </div>

          {result && (
            <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-2">
              <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">Cancel</button>
              <button
                onClick={handleImport}
                className="px-4 py-2.5 text-sm bg-[#f5a623] text-[#0a1628] font-bold rounded-lg hover:bg-[#e6951e]"
              >
                Import {result.scriptModel.requests.length} requests
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  // File import screen (Postman, OpenAPI, WSDL, HAR)
  const cfg = FORMATS[format as Exclude<ImportFormat, 'chrome'>];
  const Icon = cfg.icon;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg">
        <div className="px-6 py-5 border-b border-gray-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button onClick={() => { setFormat(null); setFile(null); setResult(null); setError(''); }} className="text-gray-400 hover:text-gray-600 text-sm">&larr;</button>
            <div className="flex items-center gap-2">
              <Icon className={`w-5 h-5 ${cfg.color.split(' ')[0]}`} />
              <h2 className="text-lg font-bold text-gray-800">{cfg.label}</h2>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          {/* Drop zone */}
          <div
            onClick={() => fileRef.current?.click()}
            onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add('border-[#f5a623]', 'bg-[#f5a623]/5'); }}
            onDragLeave={e => { e.currentTarget.classList.remove('border-[#f5a623]', 'bg-[#f5a623]/5'); }}
            onDrop={e => {
              e.preventDefault();
              e.currentTarget.classList.remove('border-[#f5a623]', 'bg-[#f5a623]/5');
              const f = e.dataTransfer.files[0];
              if (f) { setFile(f); setError(''); setResult(null); }
            }}
            className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center cursor-pointer hover:border-[#f5a623] hover:bg-[#f5a623]/5 transition-all"
          >
            {file ? (
              <div className="flex items-center justify-center gap-2 text-sm text-gray-700">
                <Upload className="w-5 h-5 text-[#f5a623]" />
                <span className="font-medium">{file.name}</span>
                <span className="text-gray-400">({(file.size / 1024).toFixed(0)} KB)</span>
              </div>
            ) : (
              <div>
                <Upload className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                <p className="text-sm text-gray-500">Drop your file here or click to browse</p>
                <p className="text-xs text-gray-400 mt-1">Accepted: {cfg.accept}</p>
              </div>
            )}
            <input ref={fileRef} type="file" accept={cfg.accept} onChange={handleFileChange} className="hidden" />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">{error}</div>
          )}

          {/* Preview stats */}
          {result && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <p className="text-sm font-medium text-green-800 mb-2 flex items-center gap-1.5">
                <CheckCircle className="w-4 h-4" /> Ready to import
              </p>
              <div className="grid grid-cols-2 gap-2 text-xs text-green-700">
                {Object.entries(result.stats).map(([key, value]) => (
                  <span key={key}>
                    {key.replace(/_/g, ' ')}: <strong>{value}</strong>
                  </span>
                ))}
              </div>
              {result.scriptModel.requests.length > 0 && (
                <div className="mt-3 max-h-40 overflow-y-auto border-t border-green-200 pt-2">
                  {result.scriptModel.requests.slice(0, 8).map((r, i) => (
                    <div key={i} className="text-xs text-green-700 py-0.5 truncate flex items-center gap-1">
                      <span className="font-mono font-bold text-green-800">{r.method}</span>
                      <span className="truncate">{r.name}</span>
                    </div>
                  ))}
                  {result.scriptModel.requests.length > 8 && (
                    <div className="text-xs text-green-500 mt-1">... and {result.scriptModel.requests.length - 8} more</div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">Cancel</button>
          {!result ? (
            <button
              onClick={handleParse}
              disabled={!file || loading}
              className="px-4 py-2.5 text-sm bg-[#f5a623] text-[#0a1628] font-bold rounded-lg hover:bg-[#e6951e] disabled:opacity-50 flex items-center gap-2"
            >
              {loading && <Loader2 className="w-4 h-4 animate-spin" />}
              {loading ? 'Parsing...' : 'Parse File'}
            </button>
          ) : (
            <button
              onClick={handleImport}
              className="px-4 py-2.5 text-sm bg-[#f5a623] text-[#0a1628] font-bold rounded-lg hover:bg-[#e6951e]"
            >
              Import {result.scriptModel.requests.length} requests
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
