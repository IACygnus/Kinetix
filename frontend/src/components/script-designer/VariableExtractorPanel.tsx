// frontend/src/components/script-designer/VariableExtractorPanel.tsx
/**
 * Extractor panel with:
 * 1. Response body viewer from last "Probar" execution
 * 2. Visual selection -> auto regex generation
 * 3. CRUD for extractors (add, inline edit, delete)
 */
import { useState, useRef } from 'react';
import { Plus, Trash2, Edit2, Check, X, Code } from 'lucide-react';

interface Extractor {
  variable_name: string;
  extract_from: 'body' | 'header';
  regex: string;
  match_no: number;
  default_value: string;
  header_name?: string;
}

interface Props {
  extractors: Extractor[];
  onChange: (extractors: Extractor[]) => void;
  lastResponseBody?: string;
  requestName?: string;
}

// ── Generate regex from selected text in context ──────────────────────────────
function generateRegex(fullText: string, selectedText: string): string {
  if (!selectedText || !fullText) return '';

  const idx = fullText.indexOf(selectedText);
  if (idx === -1) {
    const escaped = selectedText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return `(${escaped})`;
  }

  const before = fullText.slice(Math.max(0, idx - 40), idx);

  // JSON string pattern: "key":"value"
  const jsonStrMatch = before.match(/"([^"]+)"\s*:\s*"?$/);
  if (jsonStrMatch) {
    const key = jsonStrMatch[1];
    if (before.endsWith('"')) {
      return `"${key}":"([^"]+)"`;
    }
    return `"${key}":(\\d+(?:\\.\\d+)?)`;
  }

  // JSON number pattern: "key":123
  const jsonNumMatch = before.match(/"([^"]+)"\s*:\s*$/);
  if (jsonNumMatch && /^\d/.test(selectedText)) {
    return `"${jsonNumMatch[1]}":(\\d+(?:\\.\\d+)?)`;
  }

  // Header pattern: Header-Name: value
  const headerMatch = before.match(/([A-Za-z-]+):\s*$/);
  if (headerMatch) {
    return `${headerMatch[1]}:\\s*([^\\r\\n]+)`;
  }

  // Fallback: capture with minimal context
  const ctxBefore = before.slice(-15).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const afterText = fullText.slice(idx + selectedText.length, idx + selectedText.length + 5);
  const ctxAfter = afterText.slice(0, 3).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

  if (ctxBefore && ctxAfter) {
    return `${ctxBefore}([^${ctxAfter[0] || '"'}]+)${ctxAfter}`;
  }

  const escaped = selectedText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return `(${escaped})`;
}

// ── Component ─────────────────────────────────────────────────────────────────
export default function VariableExtractorPanel({ extractors, onChange, lastResponseBody, requestName }: Props) {
  const [showBuilder, setShowBuilder] = useState(false);
  const [selection, setSelection] = useState('');
  const [generatedRegex, setGeneratedRegex] = useState('');
  const [newVarName, setNewVarName] = useState('');
  const [newMatchNo, setNewMatchNo] = useState(1);
  const [newDefault, setNewDefault] = useState('');
  const [editingIdx, setEditingIdx] = useState<number | null>(null);
  const [editValues, setEditValues] = useState<Partial<Extractor>>({});
  const previewRef = useRef<HTMLPreElement>(null);

  const hasResponse = !!lastResponseBody;

  const handlePreviewMouseUp = () => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed) return;
    const text = sel.toString().trim();
    if (!text || text.length < 1) return;
    setSelection(text);
    const regex = generateRegex(lastResponseBody || '', text);
    setGeneratedRegex(regex);
    // Auto-suggest variable name from JSON key
    if (!newVarName) {
      const bodyStr = lastResponseBody || '';
      const selIdx = bodyStr.indexOf(text);
      if (selIdx > 0) {
        const beforeSel = bodyStr.slice(Math.max(0, selIdx - 40), selIdx);
        const keyMatch = beforeSel.match(/"([^"]+)"\s*:\s*"?$/);
        if (keyMatch) setNewVarName(keyMatch[1]);
      }
    }
  };

  const handleAdd = () => {
    if (!newVarName.trim() || !generatedRegex.trim()) return;
    const newExtractor: Extractor = {
      variable_name: newVarName.trim(),
      extract_from: 'body',
      regex: generatedRegex.trim(),
      match_no: newMatchNo,
      default_value: newDefault,
    };
    onChange([...extractors, newExtractor]);
    setSelection('');
    setGeneratedRegex('');
    setNewVarName('');
    setNewMatchNo(1);
    setNewDefault('');
  };

  const handleAddManual = () => {
    onChange([...extractors, {
      variable_name: '',
      extract_from: 'body',
      regex: '',
      match_no: 1,
      default_value: '',
    }]);
  };

  const handleDelete = (idx: number) => onChange(extractors.filter((_, i) => i !== idx));

  const startEdit = (idx: number) => {
    setEditingIdx(idx);
    setEditValues({ ...extractors[idx] });
  };

  const saveEdit = (idx: number) => {
    onChange(extractors.map((e, i) => i === idx ? { ...e, ...editValues } as Extractor : e));
    setEditingIdx(null);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-gray-800">Variable Extractors</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Captura valores de las respuestas usando regex. Usa{' '}
            <code className="bg-gray-100 px-1 rounded text-xs">{`\${variable_name}`}</code>{' '}
            en requests posteriores.
          </p>
        </div>
        <div className="flex gap-2">
          {hasResponse && (
            <button onClick={() => setShowBuilder(!showBuilder)}
              className={`flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-md border transition-colors ${
                showBuilder
                  ? 'bg-blue-100 text-blue-800 border-blue-300'
                  : 'bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100'
              }`}>
              <Code className="w-4 h-4" />
              {showBuilder ? 'Cerrar constructor' : 'Constructor visual'}
            </button>
          )}
          <button onClick={handleAddManual}
            className="flex items-center gap-1.5 text-sm px-3 py-1.5 bg-[#0a1628] text-white rounded-md hover:bg-[#1a2d4a]">
            <Plus className="w-4 h-4" /> Add Extractor
          </button>
        </div>
      </div>

      {/* ── Visual builder ── */}
      {showBuilder && (
        <div className="border border-blue-200 rounded-md overflow-hidden bg-blue-50">
          <div className="px-4 py-2.5 bg-blue-100 border-b border-blue-200 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Code className="w-4 h-4 text-blue-700" />
              <span className="text-sm font-semibold text-blue-800">Constructor de Extractor</span>
            </div>
            <button onClick={() => setShowBuilder(false)} className="text-blue-500 hover:text-blue-700">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="p-4 space-y-3">
            {/* Response body viewer */}
            <div>
              <p className="text-xs font-semibold text-gray-600 mb-1.5 flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-full ${hasResponse ? 'bg-green-500' : 'bg-gray-400'}`} />
                {hasResponse
                  ? `Respuesta de "${requestName || 'request'}" — selecciona el valor a capturar:`
                  : 'Sin respuesta — ejecuta "Probar" primero'}
              </p>
              {hasResponse ? (
                <pre
                  ref={previewRef}
                  onMouseUp={handlePreviewMouseUp}
                  className="bg-gray-900 text-green-400 text-sm font-mono p-3 rounded
                             max-h-48 overflow-auto whitespace-pre-wrap break-words
                             select-text cursor-text border border-gray-700"
                >
                  {(() => {
                    try { return JSON.stringify(JSON.parse(lastResponseBody!), null, 2); }
                    catch { return lastResponseBody; }
                  })()}
                </pre>
              ) : (
                <div className="bg-gray-100 rounded p-4 text-center text-gray-500 text-sm border border-dashed border-gray-300">
                  Ejecuta el request con "Probar" para ver la respuesta aqui
                </div>
              )}
            </div>

            {/* Selection -> regex */}
            {selection && (
              <div className="bg-white border border-blue-300 rounded-md p-3 space-y-2">
                <div className="flex items-start gap-2">
                  <span className="text-xs font-semibold text-gray-500 w-28 flex-shrink-0 pt-0.5">Seleccionado:</span>
                  <code className="text-sm bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded font-mono break-all">
                    {selection.slice(0, 80)}{selection.length > 80 ? '...' : ''}
                  </code>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-xs font-semibold text-gray-500 w-28 flex-shrink-0 pt-0.5">Regex generada:</span>
                  <code className="text-sm bg-green-100 text-green-800 px-2 py-0.5 rounded font-mono break-all">
                    {generatedRegex}
                  </code>
                </div>
              </div>
            )}

            {/* Form */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Nombre de la variable <span className="text-red-500">*</span>
                </label>
                <input type="text" value={newVarName}
                  onChange={e => setNewVarName(e.target.value)}
                  placeholder="ej: token, bookingId"
                  className="w-full text-sm px-2 py-1.5 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-300 font-mono" />
                {newVarName && (
                  <p className="text-xs text-blue-600 mt-0.5">
                    Usar como: <code>{`\${${newVarName}}`}</code>
                  </p>
                )}
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Regex <span className="text-red-500">*</span>
                </label>
                <input type="text" value={generatedRegex}
                  onChange={e => setGeneratedRegex(e.target.value)}
                  placeholder={'"token":"([^"]+)"'}
                  className="w-full text-sm px-2 py-1.5 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-300 font-mono" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Match #</label>
                <input type="number" value={newMatchNo} min={1}
                  onChange={e => setNewMatchNo(Math.max(1, parseInt(e.target.value) || 1))}
                  className="w-full text-sm px-2 py-1.5 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-300" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Valor default</label>
                <input type="text" value={newDefault}
                  onChange={e => setNewDefault(e.target.value)}
                  placeholder="Opcional"
                  className="w-full text-sm px-2 py-1.5 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-300" />
              </div>
            </div>

            <button onClick={handleAdd}
              disabled={!newVarName.trim() || !generatedRegex.trim()}
              className="w-full text-sm py-2 bg-blue-700 text-white rounded-md font-medium
                         hover:bg-blue-800 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2">
              <Plus className="w-4 h-4" /> Agregar extractor
            </button>
          </div>
        </div>
      )}

      {/* ── Empty state ── */}
      {extractors.length === 0 && !showBuilder && (
        <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
          <p className="font-semibold text-blue-800 mb-2 text-sm">Como capturar el token de respuesta?</p>
          <div className="space-y-1.5 text-xs text-blue-700">
            {[
              ['1', hasResponse ? 'Click "Constructor visual" para ver la respuesta' : 'Ejecuta el request con "Probar" para obtener la respuesta'],
              ['2', 'Selecciona el valor que quieres capturar (ej: el token)'],
              ['3', 'La regex se genera automaticamente — ponle nombre a la variable'],
              ['4', `En el siguiente request usa \${token} en el header Authorization`],
            ].map(([n, text]) => (
              <div key={n} className="flex items-start gap-2">
                <span className="font-bold bg-blue-200 rounded px-1 flex-shrink-0">{n}</span>
                <span>{text}</span>
              </div>
            ))}
          </div>
          <div className="mt-3 p-2 bg-blue-100 rounded text-xs font-mono text-blue-900 space-y-1">
            <p>{'// Response body:'}</p>
            <p>{'{ "token": "eyJhbGci..." }'}</p>
            <p className="mt-1">{'// Regex generada al seleccionar:'}</p>
            <p>{'"token":"([^"]+)"'}</p>
            <p className="mt-1">{'// En el siguiente request:'}</p>
            <p>{'Authorization: Bearer ${token}'}</p>
          </div>
        </div>
      )}

      {/* ── Existing extractors list ── */}
      {extractors.length > 0 && (
        <div className="border border-gray-200 rounded-md overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-xs text-gray-500 font-medium">
                <th className="text-left px-3 py-2">Variable</th>
                <th className="text-left px-3 py-2">Source</th>
                <th className="text-left px-3 py-2">Regex</th>
                <th className="text-left px-3 py-2 w-14">Match</th>
                <th className="text-left px-3 py-2">Default</th>
                <th className="text-left px-3 py-2 w-20">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {extractors.map((ext, idx) => {
                const isEditing = editingIdx === idx;
                return (
                  <tr key={idx} className="border-t border-gray-100 hover:bg-gray-50">
                    {isEditing ? (
                      <>
                        <td className="px-2 py-1.5">
                          <input value={editValues.variable_name || ''} autoFocus
                            onChange={e => setEditValues(p => ({ ...p, variable_name: e.target.value }))}
                            className="w-full text-xs px-1.5 py-1 border border-blue-400 rounded font-mono focus:outline-none" />
                        </td>
                        <td className="px-2 py-1.5">
                          <select value={editValues.extract_from || 'body'}
                            onChange={e => setEditValues(p => ({ ...p, extract_from: e.target.value as 'body' | 'header' }))}
                            className="text-xs px-1 py-1 border border-blue-400 rounded focus:outline-none">
                            <option value="body">body</option>
                            <option value="header">header</option>
                          </select>
                        </td>
                        <td className="px-2 py-1.5">
                          <input value={editValues.regex || ''}
                            onChange={e => setEditValues(p => ({ ...p, regex: e.target.value }))}
                            className="w-full text-xs px-1.5 py-1 border border-blue-400 rounded font-mono focus:outline-none" />
                        </td>
                        <td className="px-2 py-1.5">
                          <input type="number" value={editValues.match_no ?? 1} min={1}
                            onChange={e => setEditValues(p => ({ ...p, match_no: parseInt(e.target.value) || 1 }))}
                            className="w-full text-xs px-1.5 py-1 border border-blue-400 rounded focus:outline-none" />
                        </td>
                        <td className="px-2 py-1.5">
                          <input value={editValues.default_value || ''}
                            onChange={e => setEditValues(p => ({ ...p, default_value: e.target.value }))}
                            className="w-full text-xs px-1.5 py-1 border border-blue-400 rounded focus:outline-none" />
                        </td>
                        <td className="px-2 py-1.5">
                          <div className="flex gap-1">
                            <button onClick={() => saveEdit(idx)} className="p-1 text-green-600 hover:bg-green-50 rounded">
                              <Check className="w-3.5 h-3.5" />
                            </button>
                            <button onClick={() => setEditingIdx(null)} className="p-1 text-gray-400 hover:bg-gray-100 rounded">
                              <X className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="px-3 py-2">
                          <code className="text-xs bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded font-mono">
                            {`\${${ext.variable_name}}`}
                          </code>
                        </td>
                        <td className="px-3 py-2 text-xs text-gray-500">{ext.extract_from}</td>
                        <td className="px-3 py-2">
                          <code className="text-xs text-gray-600 font-mono break-all">{ext.regex}</code>
                        </td>
                        <td className="px-3 py-2 text-xs text-gray-500">{ext.match_no}</td>
                        <td className="px-3 py-2 text-xs text-gray-500">{ext.default_value || '—'}</td>
                        <td className="px-3 py-2">
                          <div className="flex gap-1">
                            <button onClick={() => startEdit(idx)} className="p-1 text-blue-500 hover:bg-blue-50 rounded">
                              <Edit2 className="w-3.5 h-3.5" />
                            </button>
                            <button onClick={() => handleDelete(idx)} className="p-1 text-red-500 hover:bg-red-50 rounded">
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
