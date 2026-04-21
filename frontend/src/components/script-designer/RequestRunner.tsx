// frontend/src/components/script-designer/RequestRunner.tsx
/**
 * Ejecuta un solo request usando las variables actuales del scriptModel
 * y muestra la respuesta inline (status, headers, body, tiempo).
 */
import { useState } from 'react';
import { Play, ChevronDown, ChevronUp, Clock, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import type { ScriptVariable } from './VariableManager';

interface SingleRunResult {
  status_code: number | null;
  duration_ms: number;
  success: boolean;
  error?: string;
  response_headers?: Record<string, string>;
  response_body?: string;
  resolved_url?: string;
}

interface Props {
  request: any;
  variables: ScriptVariable[];
  onResult?: (requestId: string, result: any) => void;
}

export default function RequestRunner({ request, variables, onResult }: Props) {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<SingleRunResult | null>(null);
  const [expanded, setExpanded] = useState(true);
  const [showHeaders, setShowHeaders] = useState(false);
  const [showBody, setShowBody] = useState(true);

  const handleRun = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setRunning(true);
    setResult(null);
    try {
      const csrfToken = document.cookie.match(/csrf_token=([^;]+)/)?.[1] || '';
      const res = await fetch('/api/v1/executions/run-single', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken,
        },
        body: JSON.stringify({
          request: request,
          variables: variables.map(v => ({
            name: v.name,
            value: v.value || '',
            source: v.type || 'manual',
          })),
        }),
      });
      const data = await res.json();
      setResult(data);
      setExpanded(true);
      if (onResult) onResult(request.id, data);
    } catch (err: any) {
      setResult({ status_code: null, duration_ms: 0, success: false, error: err.message });
    } finally {
      setRunning(false);
    }
  };

  const statusColor = (code: number | null) => {
    if (!code) return 'text-red-600';
    if (code < 300) return 'text-green-600';
    if (code < 400) return 'text-yellow-600';
    return 'text-red-600';
  };

  const statusBg = (code: number | null) => {
    if (!code) return 'bg-red-50 border-red-200';
    if (code < 300) return 'bg-green-50 border-green-200';
    if (code < 400) return 'bg-yellow-50 border-yellow-200';
    return 'bg-red-50 border-red-200';
  };

  return (
    <div className="mt-1" onClick={e => e.stopPropagation()}>
      {/* Play button */}
      <button
        onClick={handleRun}
        disabled={running || !request.url}
        title="Ejecutar solo este request"
        className="flex items-center gap-1 text-xs px-2 py-0.5 rounded border border-gray-200 bg-white hover:bg-gray-50 text-gray-600 disabled:opacity-40 transition-colors"
      >
        {running
          ? <Loader2 className="w-3 h-3 animate-spin text-blue-500" />
          : <Play className="w-3 h-3 text-green-600" />
        }
        {running ? 'Run...' : 'Probar'}
      </button>

      {/* Inline result */}
      {result && (
        <div className={`mt-1.5 rounded border text-xs overflow-hidden ${statusBg(result.status_code)}`}>
          {/* Summary bar */}
          <div
            className="flex items-center justify-between px-2 py-1.5 cursor-pointer"
            onClick={() => setExpanded(!expanded)}
          >
            <div className="flex items-center gap-2">
              {result.success
                ? <CheckCircle className="w-3.5 h-3.5 text-green-600" />
                : <XCircle className="w-3.5 h-3.5 text-red-500" />
              }
              <span className={`font-bold ${statusColor(result.status_code)}`}>
                {result.status_code ?? 'ERR'}
              </span>
              <span className="flex items-center gap-0.5 text-gray-500">
                <Clock className="w-3 h-3" />{result.duration_ms}ms
              </span>
            </div>
            {expanded ? <ChevronUp className="w-3.5 h-3.5 text-gray-400" /> : <ChevronDown className="w-3.5 h-3.5 text-gray-400" />}
          </div>

          {/* Expanded detail */}
          {expanded && (
            <div className="border-t border-gray-200/50 px-2 py-1.5 space-y-1.5 bg-white/70">
              {/* Resolved URL */}
              {result.resolved_url && (
                <div>
                  <p className="font-medium text-gray-500 text-[10px] uppercase">URL:</p>
                  <code className="text-xs text-blue-700 break-all block">{result.resolved_url}</code>
                </div>
              )}

              {/* Response headers */}
              {result.response_headers && Object.keys(result.response_headers).length > 0 && (
                <div>
                  <button
                    onClick={() => setShowHeaders(!showHeaders)}
                    className="flex items-center gap-1 text-[10px] font-medium text-gray-500 hover:text-gray-700 uppercase"
                  >
                    {showHeaders ? <ChevronUp className="w-2.5 h-2.5" /> : <ChevronDown className="w-2.5 h-2.5" />}
                    Headers ({Object.keys(result.response_headers).length})
                  </button>
                  {showHeaders && (
                    <div className="mt-0.5 space-y-0 pl-1">
                      {Object.entries(result.response_headers).slice(0, 15).map(([k, v]) => (
                        <div key={k} className="flex gap-1 text-[10px]">
                          <span className="font-mono text-gray-500">{k}:</span>
                          <span className="font-mono text-gray-700 break-all">{v}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Response body */}
              <div>
                <button
                  onClick={() => setShowBody(!showBody)}
                  className="flex items-center gap-1 text-[10px] font-medium text-gray-500 hover:text-gray-700 uppercase"
                >
                  {showBody ? <ChevronUp className="w-2.5 h-2.5" /> : <ChevronDown className="w-2.5 h-2.5" />}
                  Body
                </button>
                {showBody && result.response_body !== undefined && (
                  <pre className="mt-0.5 p-1.5 bg-gray-900 text-green-400 rounded text-[10px] overflow-x-auto max-h-40 whitespace-pre-wrap break-words">
                    {(() => {
                      try {
                        return JSON.stringify(JSON.parse(result.response_body || ''), null, 2);
                      } catch {
                        return result.response_body || '(vacio)';
                      }
                    })()}
                  </pre>
                )}
              </div>

              {/* Error */}
              {result.error && (
                <div className="p-1.5 bg-red-100 rounded text-red-700 text-[11px]">
                  {result.error}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
