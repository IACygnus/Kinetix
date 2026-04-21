// frontend/src/components/script-designer/RequestEditor.tsx
import { useState } from 'react';
import { Plus, X } from 'lucide-react';
import { ScriptRequest } from '../../api/scriptDesignerApi';
import AssertionPanel from './AssertionPanel';
import VariableExtractorPanel from './VariableExtractorPanel';
import VariableAutocomplete from './VariableAutocomplete';
import BodyEditor from './BodyEditor';
import JMeterResultDetail from './JMeterResultDetail';
import type { RequestDetail } from './JMeterResultDetail';
import type { ScriptVariable } from './VariableManager';
import type { DataFileOption } from './VariableInlineEditor';

const METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'];
const BODY_TYPES = ['json', 'xml', 'form', 'raw'] as const;

const COMMON_HEADERS = [
  'Authorization', 'Content-Type', 'Accept', 'Accept-Language',
  'Accept-Encoding', 'Cache-Control', 'Connection', 'User-Agent',
  'X-Request-ID', 'X-Correlation-ID', 'X-API-Key', 'X-CSRF-Token',
  'Origin', 'Referer', 'Cookie', 'If-Modified-Since',
  'correlacion_id', 'consumidor_id', 'operacion_invocacion_id',
  'direccion_ip_invocacion', 'empresa', 'negocio',
];

type Tab = 'Request' | 'Params' | 'Assertions' | 'Extractors' | 'Result';

interface Props {
  request: ScriptRequest;
  onChange: (req: ScriptRequest) => void;
  variables: ScriptVariable[];
  runResult?: RequestDetail | null;
  dataFiles?: DataFileOption[];
  onVariableChange?: (updated: ScriptVariable) => void;
  onVariableCreate?: (newVar: ScriptVariable) => void;
  runResults?: Record<string, any>;
}

export default function RequestEditor({ request, onChange, variables, runResult, dataFiles, onVariableChange, onVariableCreate, runResults }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>('Request');
  const [newHeaderKey, setNewHeaderKey] = useState('');
  const [newHeaderVal, setNewHeaderVal] = useState('');

  const update = (patch: Partial<ScriptRequest>) => onChange({ ...request, ...patch });

  // ── Header management ────────────────────────────────────────────────────
  const headerEntries = Object.entries(request.headers || {});

  const addHeader = () => {
    if (!newHeaderKey.trim()) return;
    update({ headers: { ...request.headers, [newHeaderKey.trim()]: newHeaderVal } });
    setNewHeaderKey('');
    setNewHeaderVal('');
  };

  const removeHeader = (key: string) => {
    const h = { ...request.headers };
    delete h[key];
    update({ headers: h });
  };

  const updateHeaderKey = (oldKey: string, newKey: string) => {
    if (!newKey.trim() || newKey === oldKey) return;
    const entries = Object.entries(request.headers);
    const newHeaders: Record<string, string> = {};
    for (const [k, v] of entries) {
      newHeaders[k === oldKey ? newKey.trim() : k] = v;
    }
    update({ headers: newHeaders });
  };

  const updateHeaderValue = (key: string, newValue: string) => {
    update({ headers: { ...request.headers, [key]: newValue } });
  };

  // ── Params management ────────────────────────────────────────────────────
  const paramEntries = Object.entries(request.params || {});
  const paramCount = paramEntries.length;

  const handleParamKeyChange = (oldKey: string, newKey: string) => {
    if (!newKey.trim() || newKey === oldKey) return;
    const entries = Object.entries(request.params || {});
    const newParams: Record<string, string> = {};
    for (const [k, v] of entries) {
      newParams[k === oldKey ? newKey.trim() : k] = v;
    }
    update({ params: newParams });
  };

  const handleParamValueChange = (key: string, newValue: string) => {
    update({ params: { ...(request.params || {}), [key]: newValue } });
  };

  const handleParamDelete = (key: string) => {
    const p = { ...(request.params || {}) };
    delete p[key];
    update({ params: p });
  };

  const handleParamAdd = () => {
    const existing = request.params || {};
    // Find a unique key name
    let newKey = '';
    let i = 1;
    while (newKey === '' || newKey in existing) {
      newKey = `param${i}`;
      i++;
    }
    update({ params: { ...existing, [newKey]: '' } });
  };

  const showBody = !['GET', 'HEAD', 'OPTIONS'].includes(request.method);

  return (
    <div className="flex flex-col h-full">
      {/* Request name + method + URL bar */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <input
          type="text"
          value={request.name}
          onChange={e => update({ name: e.target.value })}
          className="w-full text-base font-semibold text-gray-800 border-0 border-b border-transparent hover:border-gray-300 focus:border-blue-500 focus:outline-none mb-3 pb-1"
          placeholder="Transaction name..."
        />
        <div className="flex gap-2">
          <select
            value={request.method}
            onChange={e => update({ method: e.target.value })}
            className="border border-gray-300 rounded-lg px-3 py-2.5 text-sm font-mono font-bold focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {METHODS.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
          <div className="flex-1 relative group">
            <VariableAutocomplete
              value={request.url}
              onChange={val => update({ url: val })}
              variables={variables}
              placeholder="https://${host}/api/endpoint"
              className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            {/* Tooltip with full URL when truncated */}
            {(request.url || '').length > 60 && (
              <div className="absolute top-full left-0 z-50 hidden group-hover:block
                            bg-gray-900 text-white text-sm px-3 py-2 rounded shadow-lg
                            max-w-xl break-all mt-1 font-mono pointer-events-none">
                {request.url}
              </div>
            )}
          </div>
        </div>

        {/* Think time */}
        <div className="flex items-center gap-2 mt-3">
          <label className="text-sm text-gray-500 font-medium">Think time (ms):</label>
          <input
            type="number"
            value={request.think_time_ms}
            onChange={e => update({ think_time_ms: parseInt(e.target.value) || 0 })}
            className="w-24 border border-gray-200 rounded-lg px-3 py-1.5 text-sm"
            min={0}
          />
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-200 px-6">
        <div className="flex gap-0">
          {(['Request', 'Params', 'Assertions', 'Extractors'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab}
              {tab === 'Params' && paramCount > 0 && (
                <span className="ml-1.5 bg-blue-100 text-blue-600 text-xs rounded-full px-1.5 py-0.5 font-bold">
                  {paramCount}
                </span>
              )}
              {tab === 'Assertions' && request.assertions.length > 0 && (
                <span className="ml-1.5 bg-gray-100 text-gray-600 text-xs rounded-full px-1.5 py-0.5 font-bold">
                  {request.assertions.length}
                </span>
              )}
              {tab === 'Extractors' && request.extractors.length > 0 && (
                <span className="ml-1.5 bg-purple-100 text-purple-600 text-xs rounded-full px-1.5 py-0.5 font-bold">
                  {request.extractors.length}
                </span>
              )}
            </button>
          ))}

          {/* Result tab — only visible when there's a result */}
          {runResult && (
            <button
              onClick={() => setActiveTab('Result')}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
                activeTab === 'Result'
                  ? 'border-green-500 text-green-700'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${runResult.success ? 'bg-green-500' : 'bg-red-500'}`} />
              Resultado
              <span className={`text-xs font-bold ${runResult.status_code && Number(runResult.status_code) < 400 ? 'text-green-600' : 'text-red-600'}`}>
                {runResult.status_code ?? 'ERR'}
              </span>
            </button>
          )}
        </div>
      </div>

      {/* Tab content */}
      {activeTab === 'Result' && runResult ? (
        <JMeterResultDetail result={runResult} />
      ) : (
        <div className="flex-1 overflow-y-auto p-6">

          {activeTab === 'Request' && (
            <div className="space-y-6">
              {/* Headers */}
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-2">Headers</h3>
                <div className="border border-gray-200 rounded-lg overflow-hidden">
                  {/* Existing headers — editable */}
                  {headerEntries.map(([key, val]) => (
                    <div key={key} className="flex items-center gap-2 px-3 py-2 border-b border-gray-100 last:border-0 bg-white hover:bg-gray-50 group">
                      <input
                        list="common-headers-list"
                        value={key}
                        onChange={e => updateHeaderKey(key, e.target.value)}
                        className="font-mono text-sm text-gray-700 w-48 bg-transparent border-0 border-b border-transparent hover:border-gray-300 focus:border-blue-500 focus:outline-none px-0 py-0.5"
                      />
                      <span className="text-gray-400 text-sm">:</span>
                      <VariableAutocomplete
                        value={String(val)}
                        onChange={newVal => updateHeaderValue(key, newVal)}
                        variables={variables}
                        placeholder="Value or ${variable}"
                        className="font-mono text-sm text-gray-800 flex-1 bg-transparent border-0 border-b border-transparent hover:border-gray-300 focus:border-blue-500 focus:outline-none px-0 py-0.5"
                      />
                      <button
                        onClick={() => removeHeader(key)}
                        className="text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 flex-shrink-0"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  ))}

                  {/* Add new header row */}
                  <div className="flex gap-2 p-2.5 bg-gray-50">
                    <input
                      list="common-headers-list"
                      type="text"
                      value={newHeaderKey}
                      onChange={e => setNewHeaderKey(e.target.value)}
                      placeholder="Header name"
                      className="font-mono text-sm border border-gray-300 rounded-lg px-3 py-2 w-48 focus:outline-none focus:ring-1 focus:ring-blue-500"
                      onKeyDown={e => e.key === 'Enter' && addHeader()}
                    />
                    <VariableAutocomplete
                      value={newHeaderVal}
                      onChange={val => setNewHeaderVal(val)}
                      variables={variables}
                      placeholder="Value or ${variable}"
                      className="font-mono text-sm border border-gray-300 rounded-lg px-3 py-2 flex-1 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                    <button
                      onClick={addHeader}
                      className="text-sm text-blue-600 hover:text-blue-700 font-medium px-3 flex items-center gap-1"
                    >
                      <Plus className="w-4 h-4" /> Add
                    </button>
                  </div>
                </div>
                <datalist id="common-headers-list">
                  {COMMON_HEADERS.map(h => <option key={h} value={h} />)}
                </datalist>
              </div>

              {/* Body */}
              {showBody && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-semibold text-gray-700">Body</h3>
                    <div className="flex gap-1">
                      {BODY_TYPES.map(bt => (
                        <button
                          key={bt}
                          onClick={() => update({ body_type: bt })}
                          className={`text-sm px-2.5 py-1 rounded-md ${
                            request.body_type === bt
                              ? 'bg-blue-100 text-blue-700 font-medium'
                              : 'text-gray-500 hover:bg-gray-100'
                          }`}
                        >{bt}</button>
                      ))}
                    </div>
                  </div>
                  <BodyEditor
                    value={request.body || ''}
                    onChange={val => update({ body: val })}
                    variables={variables}
                    dataFiles={dataFiles}
                    onVariableChange={onVariableChange}
                    onVariableCreate={onVariableCreate}
                    placeholder={
                      request.body_type === 'json'
                        ? '{\n  "key": "${variable}"\n}'
                        : request.body_type === 'form'
                        ? 'key=value&key2=${variable}'
                        : ''
                    }
                  />
                </div>
              )}
            </div>
          )}

          {activeTab === 'Params' && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-sm font-semibold text-gray-700">Query Parameters</h3>
                  <p className="text-sm text-gray-400 mt-0.5">
                    Se agregan a la URL como <code className="bg-gray-100 px-1 rounded">?key=value</code>.
                    Usa <code className="bg-gray-100 px-1 rounded">{`\${variable}`}</code> para valores dinamicos.
                  </p>
                </div>
                <button onClick={handleParamAdd}
                  className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1">
                  <Plus className="w-4 h-4" /> Add param
                </button>
              </div>

              {paramCount === 0 ? (
                <div className="text-sm text-gray-400 italic text-center py-8 border border-dashed border-gray-200 rounded-lg">
                  No hay query params definidos. Los params que ya estan en la URL se muestran arriba.
                </div>
              ) : (
                <div className="space-y-2">
                  {paramEntries.map(([key, value]) => (
                    <div key={key} className="flex gap-2 items-center">
                      <input
                        value={key}
                        onChange={e => handleParamKeyChange(key, e.target.value)}
                        placeholder="Key"
                        className="flex-1 text-sm font-mono px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500"
                      />
                      <VariableAutocomplete
                        value={String(value)}
                        onChange={val => handleParamValueChange(key, val)}
                        variables={variables}
                        placeholder="Value or ${variable}"
                        className="flex-1 text-sm font-mono px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500"
                      />
                      <button onClick={() => handleParamDelete(key)}
                        className="p-2 text-red-400 hover:bg-red-50 rounded flex-shrink-0">
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* URL preview with params */}
              {paramCount > 0 && (
                <div className="mt-4 p-3 bg-gray-50 rounded-lg border border-gray-200">
                  <p className="text-sm font-medium text-gray-500 mb-1">URL con parametros:</p>
                  <code className="text-sm text-blue-700 break-all">
                    {request.url}
                    {paramCount > 0 ? '?' + paramEntries
                      .filter(([k]) => k)
                      .map(([k, v]) => `${k}=${v}`)
                      .join('&') : ''}
                  </code>
                </div>
              )}
            </div>
          )}

          {activeTab === 'Assertions' && (
            <AssertionPanel
              assertions={request.assertions}
              onChange={assertions => update({ assertions })}
            />
          )}

          {activeTab === 'Extractors' && (
            <VariableExtractorPanel
              extractors={request.extractors}
              onChange={extractors => update({ extractors })}
              lastResponseBody={runResults?.[request.id]?.response_body || runResult?.response_body || ''}
              requestName={request.name}
            />
          )}
        </div>
      )}
    </div>
  );
}
