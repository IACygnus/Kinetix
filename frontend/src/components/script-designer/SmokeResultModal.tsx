// frontend/src/components/script-designer/SmokeResultModal.tsx
/**
 * Modal de resultados del Smoke Test.
 * Layout tipo JMeter View Results Tree:
 * - Panel izquierdo: arbol de requests con check/cross
 * - Panel derecho: detalle del request seleccionado (3 tabs tipo JMeter)
 */
import { useState } from 'react';
import { X, CheckCircle, XCircle, Clock } from 'lucide-react';
import JMeterResultDetail from './JMeterResultDetail';
import type { RequestDetail } from './JMeterResultDetail';
import type { SmokeTestResult } from '../../api/scriptDesignerApi';

interface Props {
  result: SmokeTestResult;
  onClose: () => void;
}

// Adapt smoke test request_details to RequestDetail format
function adaptDetail(d: SmokeTestResult['request_details'][0]): RequestDetail {
  return {
    name: d.name,
    resolved_url: (d as any).resolved_url || d.url || '',
    method: (d as any).method || '',
    status_code: d.status_code,
    duration_ms: (d as any).duration_ms || d.elapsed_ms || 0,
    elapsed_ms: d.elapsed_ms,
    success: d.success,
    failure_message: d.failure_message,
    bytes: d.bytes,
    error: d.success ? null : d.failure_message,
    petition_text: (d as any).petition_text || '',
    sent_headers: (d as any).sent_headers || '',
    sent_body: (d as any).sent_body || '',
    response_body: (d as any).response_body || '',
    response_headers: (d as any).response_headers || {},
    response_headers_raw: (d as any).response_headers_raw || '',
  };
}

export default function SmokeResultModal({ result, onClose }: Props) {
  const [selected, setSelected] = useState<number>(0);

  const details = (result.request_details || []).map(adaptDetail);
  const selectedResult = details[selected] || null;
  const overallOk = result.success;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div
        className="bg-white rounded-xl shadow-2xl flex flex-col overflow-hidden"
        style={{ width: '90vw', maxWidth: '1100px', height: '80vh', maxHeight: '700px' }}
      >
        {/* Header */}
        <div className={`flex items-center justify-between px-6 py-4 flex-shrink-0 ${
          overallOk ? 'bg-green-50 border-b border-green-200' : 'bg-red-50 border-b border-red-200'
        }`}>
          <div className="flex items-center gap-3">
            {overallOk
              ? <CheckCircle className="w-6 h-6 text-green-600" />
              : <XCircle className="w-6 h-6 text-red-600" />
            }
            <span className="text-lg font-bold text-gray-800">
              {overallOk ? 'Smoke Test Passed' : 'Smoke Test Failed'}
            </span>
          </div>
          <div className="flex items-center gap-6 text-center">
            <div>
              <p className="text-2xl font-bold text-gray-700">{result.total_requests}</p>
              <p className="text-xs text-gray-500">Total</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-green-600">{result.passed_requests}</p>
              <p className="text-xs text-gray-500">Passed</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-red-600">{result.failed_requests}</p>
              <p className="text-xs text-gray-500">Failed</p>
            </div>
            <div className="flex items-center gap-1">
              <Clock className="w-4 h-4 text-gray-400" />
              <div>
                <p className="text-xl font-bold text-gray-700">{result.duration_ms}ms</p>
                <p className="text-xs text-gray-500">Duracion</p>
              </div>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-gray-200 rounded-full">
            <X className="w-5 h-5 text-gray-600" />
          </button>
        </div>

        {/* Unresolved variables */}
        {result.unresolved_variables && result.unresolved_variables.length > 0 && (
          <div className="mx-6 mt-3 p-3 bg-amber-50 border border-amber-200 rounded-md flex-shrink-0">
            <p className="text-sm font-medium text-amber-800 mb-1">Variables sin valor asignado:</p>
            <div className="flex flex-wrap gap-2">
              {result.unresolved_variables.map((uv, i) => (
                <code key={i} className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded">
                  {`\${${typeof uv === 'string' ? uv : uv.variable}}`}
                </code>
              ))}
            </div>
          </div>
        )}

        {/* Error message */}
        {result.error_message && (
          <div className="mx-6 mt-3 p-3 bg-red-50 border border-red-200 rounded-md flex-shrink-0 text-sm text-red-700">
            {result.error_message}
          </div>
        )}

        {/* Two-panel layout */}
        <div className="flex flex-1 overflow-hidden">
          {/* Left panel — request tree */}
          <div className="w-64 flex-shrink-0 border-r border-gray-200 overflow-y-auto bg-gray-50">
            <p className="px-4 py-2 text-xs font-semibold text-gray-400 uppercase tracking-wide border-b border-gray-200">
              Requests
            </p>
            {details.map((r, idx) => {
              const isOk = r.success;
              const isSelected = selected === idx;
              const sc = r.status_code;
              const scNum = typeof sc === 'string' ? parseInt(sc) : sc;
              return (
                <button
                  key={idx}
                  onClick={() => setSelected(idx)}
                  className={`w-full text-left px-4 py-2.5 flex items-center gap-2 text-sm transition-colors ${
                    isSelected
                      ? 'bg-blue-50 border-r-2 border-blue-500 text-blue-800'
                      : 'hover:bg-gray-100 text-gray-700'
                  }`}
                >
                  {isOk
                    ? <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />
                    : <XCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
                  }
                  <span className="truncate flex-1">{r.name || `Request ${idx + 1}`}</span>
                  {scNum && (
                    <span className={`ml-auto text-xs font-bold flex-shrink-0 ${
                      scNum < 400 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {scNum}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Right panel — JMeter detail */}
          <div className="flex-1 overflow-hidden">
            {selectedResult ? (
              <JMeterResultDetail result={selectedResult} />
            ) : (
              <div className="flex items-center justify-center h-full text-gray-400 text-sm">
                Selecciona un request de la lista para ver el detalle
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
