// frontend/src/components/script-designer/RunResultPanel.tsx
/**
 * Panel completo de resultado de ejecucion individual de un request.
 * Se muestra en el panel derecho del editor, tab "Resultado".
 */
import { useState } from 'react';
import {
  CheckCircle, XCircle, Clock, Globe, Copy, Check
} from 'lucide-react';

interface RunResult {
  success: boolean;
  status_code: number | null;
  duration_ms: number;
  resolved_url?: string;
  response_headers?: Record<string, string>;
  response_body?: string;
  error?: string;
}

interface Props {
  result: RunResult;
}

export default function RunResultPanel({ result }: Props) {
  const [activeSection, setActiveSection] = useState<'body' | 'headers'>('body');
  const [copied, setCopied] = useState(false);

  const formatBody = (body: string | undefined) => {
    if (!body) return '(sin body)';
    try { return JSON.stringify(JSON.parse(body), null, 2); }
    catch { return body; }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(formatBody(result.response_body));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const formattedBody = formatBody(result.response_body);
  const headerCount = Object.keys(result.response_headers || {}).length;

  return (
    <div className="flex flex-col h-full overflow-hidden">

      {/* Status bar */}
      <div className={`flex items-center gap-4 px-4 py-3 border-b ${result.success ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
        {result.success
          ? <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0" />
          : <XCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
        }
        <span className={`text-2xl font-bold ${result.status_code && result.status_code < 400 ? 'text-green-700' : 'text-red-700'}`}>
          {result.status_code ?? 'ERR'}
        </span>
        <span className="text-sm text-gray-600">
          {result.success ? 'Solicitud exitosa' : result.error || 'Solicitud fallida'}
        </span>
        <div className="ml-auto flex items-center gap-1.5 text-sm text-gray-500">
          <Clock className="w-4 h-4" />
          <span className="font-medium">{result.duration_ms} ms</span>
        </div>
      </div>

      {/* Resolved URL */}
      {result.resolved_url && (
        <div className="px-4 py-2 bg-gray-50 border-b border-gray-200 flex items-start gap-2">
          <Globe className="w-4 h-4 text-gray-400 flex-shrink-0 mt-0.5" />
          <code className="text-sm text-blue-700 break-all leading-relaxed">{result.resolved_url}</code>
        </div>
      )}

      {/* Error message */}
      {result.error && !result.success && (
        <div className="mx-4 mt-3 p-3 bg-red-100 border border-red-300 rounded-md text-sm text-red-800">
          {result.error}
        </div>
      )}

      {/* Tabs Body / Headers */}
      <div className="flex border-b border-gray-200 bg-white flex-shrink-0">
        <button
          onClick={() => setActiveSection('body')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
            activeSection === 'body'
              ? 'border-[#0a1628] text-[#0a1628]'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          Body de respuesta
        </button>
        <button
          onClick={() => setActiveSection('headers')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
            activeSection === 'headers'
              ? 'border-[#0a1628] text-[#0a1628]'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          Headers ({headerCount})
        </button>
      </div>

      {/* Body content */}
      {activeSection === 'body' && (
        <div className="flex-1 overflow-hidden flex flex-col">
          <div className="flex items-center justify-between px-4 py-2 bg-gray-900 flex-shrink-0">
            <span className="text-sm text-gray-400">Response body</span>
            <button onClick={handleCopy}
              className="flex items-center gap-1 text-sm text-gray-400 hover:text-white transition-colors">
              {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? 'Copiado' : 'Copiar'}
            </button>
          </div>
          <pre className="flex-1 overflow-auto p-4 bg-gray-900 text-green-400 text-sm font-mono leading-relaxed whitespace-pre-wrap break-words">
            {formattedBody}
          </pre>
        </div>
      )}

      {/* Headers content */}
      {activeSection === 'headers' && (
        <div className="flex-1 overflow-auto">
          {headerCount === 0 ? (
            <p className="text-sm text-gray-400 italic text-center py-8">Sin headers de respuesta</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-sm text-gray-500 font-medium">
                  <th className="text-left px-4 py-2 w-[40%]">Header</th>
                  <th className="text-left px-4 py-2">Valor</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(result.response_headers || {}).map(([k, v]) => (
                  <tr key={k} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-4 py-2 font-mono text-sm text-gray-600 align-top">{k}</td>
                    <td className="px-4 py-2 font-mono text-sm text-gray-800 break-all">{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
