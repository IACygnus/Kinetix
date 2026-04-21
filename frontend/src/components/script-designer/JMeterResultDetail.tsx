// frontend/src/components/script-designer/JMeterResultDetail.tsx
/**
 * Vista tipo "View Results Tree" de JMeter.
 * Tabs:
 *   1. Resultado del Muestreador — metricas (tiempo, bytes, codigo)
 *   2. Peticion — que envio (metodo, URL, body, headers)
 *   3. Datos de Respuesta — que recibio (body + cabeceras)
 */
import { useState } from 'react';
import { CheckCircle, XCircle, Copy, Check } from 'lucide-react';

export interface RequestDetail {
  name?: string;
  method?: string;
  resolved_url?: string;
  status_code: number | string | null;
  duration_ms: number;
  elapsed_ms?: number;
  success: boolean;
  error?: string | null;
  failure_message?: string;
  bytes?: number;
  // Petition
  petition_text?: string;
  sent_headers?: string;
  sent_body?: string;
  // Response
  response_body?: string;
  response_headers?: Record<string, string>;
  response_headers_raw?: string;
  // Assertions
  assertion_failures?: string[];
}

type JMeterTab = 'sampler' | 'petition' | 'response';

interface Props {
  result: RequestDetail;
}

export default function JMeterResultDetail({ result }: Props) {
  const [activeTab, setActiveTab] = useState<JMeterTab>('sampler');
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const copy = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const code = result.status_code;
  const codeNum = typeof code === 'string' ? parseInt(code) : code;
  const codeStr = code ? String(code) : 'ERR';

  const codeColor = !codeNum       ? 'text-red-600'
                  : codeNum < 300  ? 'text-green-600'
                  : codeNum < 400  ? 'text-yellow-600'
                  : 'text-red-600';

  const headerBg = !codeNum       ? 'bg-red-50 border-red-200'
                 : codeNum < 300  ? 'bg-green-50 border-green-200'
                 : codeNum < 400  ? 'bg-yellow-50 border-yellow-200'
                 : 'bg-red-50 border-red-200';

  const formatJSON = (text: string) => {
    try { return JSON.stringify(JSON.parse(text), null, 2); }
    catch { return text; }
  };

  const tabCls = (t: JMeterTab) =>
    `px-4 py-2 text-sm font-medium border-b-2 transition-colors cursor-pointer ${
      activeTab === t
        ? 'border-[#0a1628] text-[#0a1628] bg-white'
        : 'border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-50'
    }`;

  const formattedBody = formatJSON(result.response_body || '');
  const byteSize = result.bytes || new Blob([result.response_body || '']).size;
  const errorMsg = result.error || result.failure_message || '';

  return (
    <div className="flex flex-col h-full overflow-hidden">

      {/* Status bar */}
      <div className={`flex items-center gap-3 px-4 py-2.5 border-b flex-shrink-0 ${headerBg}`}>
        {result.success
          ? <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0" />
          : <XCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
        }
        <span className={`text-xl font-bold ${codeColor}`}>{codeStr}</span>
        <span className="text-sm text-gray-600 truncate flex-1">
          {result.name || result.resolved_url || ''}
        </span>
        <span className="text-sm font-medium text-gray-500 ml-auto flex-shrink-0">
          {result.duration_ms || result.elapsed_ms || 0} ms
        </span>
      </div>

      {/* JMeter Tabs */}
      <div className="flex border-b border-gray-200 bg-gray-50 flex-shrink-0">
        <button className={tabCls('sampler')} onClick={() => setActiveTab('sampler')}>
          Resultado del Muestreador
        </button>
        <button className={tabCls('petition')} onClick={() => setActiveTab('petition')}>
          Peticion
        </button>
        <button className={tabCls('response')} onClick={() => setActiveTab('response')}>
          Datos de Respuesta
        </button>
      </div>

      {/* TAB 1: Sampler Result */}
      {activeTab === 'sampler' && (
        <div className="flex-1 overflow-auto p-4 bg-white">
          <div className="space-y-1 font-mono text-sm text-gray-800">
            {result.name && (
              <p><span className="text-gray-500 inline-block w-52">Nombre del hilo:</span>{result.name}</p>
            )}
            <p><span className="text-gray-500 inline-block w-52">URL:</span>{result.resolved_url || ''}</p>
            <p><span className="text-gray-500 inline-block w-52">Tiempo de carga:</span>{result.duration_ms || result.elapsed_ms || 0} ms</p>
            <p><span className="text-gray-500 inline-block w-52">Tamano en bytes:</span>{byteSize}</p>
            <p>
              <span className="text-gray-500 inline-block w-52">Codigo de respuesta:</span>
              <span className={codeColor + ' font-bold'}>{codeStr}</span>
            </p>
            <p>
              <span className="text-gray-500 inline-block w-52">Mensaje:</span>
              {result.success ? 'OK' : (errorMsg || `Error ${codeStr}`)}
            </p>
            {errorMsg && !result.success && (
              <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm whitespace-pre-wrap">
                {errorMsg}
              </div>
            )}
            {result.assertion_failures && result.assertion_failures.length > 0 && (
              <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-md">
                <p className="text-sm font-semibold text-red-800 mb-1">Assertions fallidas:</p>
                <ul className="list-disc list-inside space-y-0.5">
                  {result.assertion_failures.map((msg: string, i: number) => (
                    <li key={i} className="text-sm text-red-700">{msg}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: Petition */}
      {activeTab === 'petition' && (
        <PetitionSubTabs
          petitionText={result.petition_text || `${result.method || 'GET'} ${result.resolved_url || ''}`}
          sentHeaders={result.sent_headers || ''}
          copy={copy}
          copiedKey={copiedKey}
        />
      )}

      {/* TAB 3: Response Data */}
      {activeTab === 'response' && (
        <ResponseSubTabs
          responseBody={formattedBody}
          responseHeadersRaw={result.response_headers_raw || ''}
          responseHeaders={result.response_headers || {}}
          copy={copy}
          copiedKey={copiedKey}
        />
      )}
    </div>
  );
}

// ─── Sub-tabs Petition ────────────────────────────────────────────────────────
function PetitionSubTabs({ petitionText, sentHeaders, copy, copiedKey }: {
  petitionText: string; sentHeaders: string;
  copy: (t: string, k: string) => void; copiedKey: string | null;
}) {
  const [sub, setSub] = useState<'body' | 'headers'>('body');
  return (
    <div className="flex-1 overflow-hidden flex flex-col">
      <div className="flex border-b border-gray-200 bg-white flex-shrink-0">
        <button onClick={() => setSub('body')}
          className={`px-4 py-2 text-sm border-b-2 transition-colors ${sub === 'body' ? 'border-blue-500 text-blue-700' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
          Request Body
        </button>
        <button onClick={() => setSub('headers')}
          className={`px-4 py-2 text-sm border-b-2 transition-colors ${sub === 'headers' ? 'border-blue-500 text-blue-700' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
          Cabeceras de peticion
        </button>
      </div>
      <div className="flex-1 overflow-auto relative">
        <button onClick={() => copy(sub === 'body' ? petitionText : sentHeaders, `petition-${sub}`)}
          className="absolute top-2 right-2 z-10 flex items-center gap-1 text-xs px-2 py-1 bg-gray-700 text-gray-300 hover:text-white rounded">
          {copiedKey === `petition-${sub}` ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
          {copiedKey === `petition-${sub}` ? 'Copiado' : 'Copiar'}
        </button>
        <pre className="p-4 text-sm font-mono text-green-400 bg-gray-900 min-h-full whitespace-pre-wrap break-words">
          {sub === 'body' ? (petitionText || '(sin body)') : (sentHeaders || '(sin cabeceras enviadas)')}
        </pre>
      </div>
    </div>
  );
}

// ─── Sub-tabs Response Data ───────────────────────────────────────────────────
function ResponseSubTabs({ responseBody, responseHeadersRaw, responseHeaders, copy, copiedKey }: {
  responseBody: string; responseHeadersRaw: string; responseHeaders: Record<string, string>;
  copy: (t: string, k: string) => void; copiedKey: string | null;
}) {
  const [sub, setSub] = useState<'body' | 'headers'>('body');
  return (
    <div className="flex-1 overflow-hidden flex flex-col">
      <div className="flex border-b border-gray-200 bg-white flex-shrink-0">
        <button onClick={() => setSub('body')}
          className={`px-4 py-2 text-sm border-b-2 transition-colors ${sub === 'body' ? 'border-blue-500 text-blue-700' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
          Response Body
        </button>
        <button onClick={() => setSub('headers')}
          className={`px-4 py-2 text-sm border-b-2 transition-colors ${sub === 'headers' ? 'border-blue-500 text-blue-700' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
          Cabeceras de respuesta
        </button>
      </div>
      <div className="flex-1 overflow-auto relative">
        <button onClick={() => copy(sub === 'body' ? responseBody : responseHeadersRaw, `resp-${sub}`)}
          className="absolute top-2 right-2 z-10 flex items-center gap-1 text-xs px-2 py-1 bg-gray-700 text-gray-300 hover:text-white rounded">
          {copiedKey === `resp-${sub}` ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
          {copiedKey === `resp-${sub}` ? 'Copiado' : 'Copiar'}
        </button>
        {sub === 'body' ? (
          <pre className="p-4 text-sm font-mono text-green-400 bg-gray-900 min-h-full whitespace-pre-wrap break-words">
            {responseBody || '(sin body)'}
          </pre>
        ) : (
          <pre className="p-4 text-sm font-mono text-cyan-300 bg-gray-900 min-h-full whitespace-pre-wrap break-words">
            {responseHeadersRaw ||
              (Object.keys(responseHeaders).length > 0
                ? Object.entries(responseHeaders).map(([k, v]) => `${k}: ${v}`).join('\n')
                : '(sin cabeceras de respuesta)')}
          </pre>
        )}
      </div>
    </div>
  );
}
