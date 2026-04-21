// frontend/src/components/script-designer/VariableManager.tsx
import { useState, useMemo, useCallback } from 'react';
import {
  Plus, Trash2, Edit2, Check, X, Info, FileText,
  ChevronDown, ChevronUp, RefreshCw, AlertCircle, Database, Link2
} from 'lucide-react';

// ─── Tipos exportados ─────────────────────────────────────────────────────────
export type VariableType = 'manual' | 'imported' | 'auto' | 'extractor' | 'datafile' | 'builtin';

export interface ScriptVariable {
  name: string;
  value: string;
  type: VariableType;
  source_hint?: string;
  default_value?: string;
  datafile_name?: string;
  datafile_column?: string;
}

export interface DataFileInfo {
  id: number;
  filename: string;
  columns?: string[];
}

// ─── Variables del sistema ────────────────────────────────────────────────────
export const BUILTIN_VARIABLES = [
  { name: '$guid',            description: 'UUID v4 unico por request' },
  { name: '$randomIP',        description: 'IP aleatoria (ej: 192.168.1.45)' },
  { name: '$timestamp',       description: 'Unix timestamp en milisegundos' },
  { name: '$isoTimestamp',    description: 'Fecha ISO 8601 (ej: 2025-01-15T10:30:00Z)' },
  { name: '$randomInt',       description: 'Entero aleatorio entre 0 y 1000' },
  { name: '$randomAlphaNum',  description: 'String alfanumerico de 8 caracteres' },
  { name: '$randomFirstName', description: 'Nombre propio aleatorio (ej: Carlos, Maria)' },
  { name: '$randomLastName',  description: 'Apellido aleatorio (ej: Gonzalez, Perez)' },
  { name: '$randomEmail',     description: 'Email aleatorio (ej: user_x7k2@test.com)' },
];

export const BUILTIN_VAR_NAMES = new Set(BUILTIN_VARIABLES.map(b => b.name));

// ─── Escanear variables en un scriptModel ─────────────────────────────────────
export function scanVariablesFromModel(scriptModel: any): string[] {
  const json = JSON.stringify(scriptModel || {});
  const matches = [...new Set((json.match(/\$\{([^}]+)\}/g) || []).map((m: string) => m.slice(2, -1)))];
  return matches.filter(n => !BUILTIN_VAR_NAMES.has(n));
}

// ─── Colores por tipo ─────────────────────────────────────────────────────────
const TYPE_CONFIG: Record<VariableType, { label: string; color: string; bg: string }> = {
  manual:    { label: 'Manual',    color: 'text-blue-700',   bg: 'bg-blue-50 border-blue-200' },
  imported:  { label: 'Importada', color: 'text-purple-700', bg: 'bg-purple-50 border-purple-200' },
  auto:      { label: 'Auto',      color: 'text-indigo-700', bg: 'bg-indigo-50 border-indigo-200' },
  extractor: { label: 'Extractor', color: 'text-amber-700',  bg: 'bg-amber-50 border-amber-200' },
  datafile:  { label: 'Data File', color: 'text-green-700',  bg: 'bg-green-50 border-green-200' },
  builtin:   { label: 'Sistema',   color: 'text-gray-600',   bg: 'bg-gray-50 border-gray-200' },
};

// ─── Props ────────────────────────────────────────────────────────────────────
interface Props {
  variables: ScriptVariable[];
  dataFiles: DataFileInfo[];
  scriptModel: any;
  onChange: (variables: ScriptVariable[]) => void;
}

// ═════════════════════════════════════════════════════════════════════════════
export default function VariableManager({ variables, dataFiles, scriptModel, onChange }: Props) {
  const [search, setSearch] = useState('');
  const [editingName, setEditingName] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [editDefault, setEditDefault] = useState('');
  const [showBuiltins, setShowBuiltins] = useState(false);
  const [showMapper, setShowMapper] = useState(false);
  const [showNewForm, setShowNewForm] = useState(false);
  const [newVar, setNewVar] = useState({ name: '', value: '' });
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3500);
  };

  // ── Separar por tipo ────────────────────────────────────────────────────────
  const mainVars = useMemo(() => variables.filter(v => v.type !== 'builtin' && v.type !== 'datafile'), [variables]);
  const datafileVars = useMemo(() => variables.filter(v => v.type === 'datafile'), [variables]);

  const filteredMain = useMemo(() =>
    mainVars.filter(v => !search || v.name.toLowerCase().includes(search.toLowerCase())),
    [mainVars, search]);

  const filteredDF = useMemo(() =>
    datafileVars.filter(v => !search || v.name.toLowerCase().includes(search.toLowerCase())),
    [datafileVars, search]);

  // ── Escanear ────────────────────────────────────────────────────────────────
  const handleScan = useCallback(() => {
    const found = scanVariablesFromModel(scriptModel);
    const existingNames = new Set(variables.map(v => v.name));
    const newVars: ScriptVariable[] = found
      .filter(name => !existingNames.has(name))
      .map(name => ({ name, value: '', type: 'auto' as VariableType, source_hint: 'Detectada en requests' }));
    if (newVars.length === 0) {
      showToast('No se encontraron variables nuevas en los requests.');
    } else {
      onChange([...variables, ...newVars]);
      showToast(`Se agregaron ${newVars.length} variable(s): ${newVars.map(v => v.name).join(', ')}`);
    }
  }, [scriptModel, variables, onChange]);

  // ── Editar ──────────────────────────────────────────────────────────────────
  const startEdit = (v: ScriptVariable) => {
    setEditingName(v.name);
    setEditValue(v.value || '');
    setEditDefault(v.default_value || '');
  };

  const saveEdit = (v: ScriptVariable) => {
    onChange(variables.map(vv => vv.name === v.name
      ? { ...vv, value: editValue, ...(vv.type === 'extractor' ? { default_value: editDefault } : {}) }
      : vv
    ));
    setEditingName(null);
  };

  // ── Eliminar ────────────────────────────────────────────────────────────────
  const canDelete = (type: VariableType) => ['manual', 'imported', 'auto'].includes(type);

  const deleteVar = (name: string) => onChange(variables.filter(v => v.name !== name));

  // ── Nueva manual ────────────────────────────────────────────────────────────
  const addManual = () => {
    const trimmed = newVar.name.trim();
    if (!trimmed) return;
    if (variables.find(v => v.name === trimmed)) {
      showToast(`La variable "${trimmed}" ya existe.`); return;
    }
    onChange([...variables, { name: trimmed, value: newVar.value, type: 'manual', source_hint: '' }]);
    setNewVar({ name: '', value: '' });
    setShowNewForm(false);
  };

  // ── Vincular a data file ────────────────────────────────────────────────────
  const linkToDataFile = (varName: string, dfName: string, column: string) => {
    const exists = variables.find(v => v.name === varName);
    if (exists) {
      onChange(variables.map(v => v.name === varName
        ? { ...v, type: 'datafile' as VariableType, datafile_name: dfName, datafile_column: column }
        : v
      ));
    } else {
      onChange([...variables, {
        name: varName,
        value: '',
        type: 'datafile' as VariableType,
        source_hint: '',
        datafile_name: dfName,
        datafile_column: column,
      }]);
    }
    setShowMapper(false);
    showToast(`${varName} vinculada a ${dfName} -> ${column}`);
  };

  const unlinkDataFile = (varName: string) => {
    onChange(variables.map(v => v.name === varName
      ? { ...v, type: 'manual' as VariableType, datafile_name: undefined, datafile_column: undefined }
      : v
    ));
  };

  const totalNonBuiltin = variables.filter(v => v.type !== 'builtin').length;

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-full bg-white">

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50 flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-800">Variables</span>
          <span className="text-xs bg-gray-200 text-gray-600 px-2 py-0.5 rounded-full font-medium">
            {totalNonBuiltin}
          </span>
        </div>
        <div className="flex gap-1.5">
          <button onClick={handleScan}
            className="flex items-center gap-1 text-xs px-2 py-1 rounded-md border border-gray-300 bg-white hover:bg-gray-50 text-gray-700">
            <RefreshCw className="w-3 h-3" /> Escanear
          </button>
          <button onClick={() => setShowMapper(true)}
            className="flex items-center gap-1 text-xs px-2 py-1 rounded-md border border-green-400 bg-white hover:bg-green-50 text-green-700">
            <Link2 className="w-3 h-3" /> CSV
          </button>
          <button onClick={() => setShowNewForm(true)}
            className="flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-[#0a1628] text-white hover:bg-[#1a2d4a]">
            <Plus className="w-3 h-3" /> Nueva
          </button>
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <div className="mx-4 mt-2 flex items-center gap-2 text-xs bg-blue-50 border border-blue-200 text-blue-700 px-3 py-2 rounded-md flex-shrink-0">
          <Info className="w-3.5 h-3.5 flex-shrink-0" />{toast}
        </div>
      )}

      {/* Search */}
      <div className="px-4 pt-3 pb-2 flex-shrink-0">
        <input type="text" placeholder="Buscar variable..."
          value={search} onChange={e => setSearch(e.target.value)}
          className="w-full text-sm px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-300" />
      </div>

      {/* Scroll area */}
      <div className="flex-1 overflow-y-auto px-4 pb-6 space-y-5">

        {/* New var form */}
        {showNewForm && (
          <div className="p-3 border border-blue-300 rounded-md bg-blue-50 flex gap-2 items-end">
            <div className="flex-1">
              <label className="text-xs font-medium text-gray-700 mb-1 block">Nombre</label>
              <input type="text" placeholder="ej: baseUrl" value={newVar.name}
                onChange={e => setNewVar(p => ({ ...p, name: e.target.value }))}
                autoFocus
                className="w-full text-sm px-2 py-1.5 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-300" />
            </div>
            <div className="flex-1">
              <label className="text-xs font-medium text-gray-700 mb-1 block">Valor</label>
              <input type="text" placeholder="ej: https://api.prod.com" value={newVar.value}
                onChange={e => setNewVar(p => ({ ...p, value: e.target.value }))}
                onKeyDown={e => e.key === 'Enter' && addManual()}
                className="w-full text-sm px-2 py-1.5 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-300" />
            </div>
            <button onClick={addManual} className="p-2 rounded bg-green-600 text-white hover:bg-green-700"><Check className="w-4 h-4" /></button>
            <button onClick={() => { setShowNewForm(false); setNewVar({ name: '', value: '' }); }}
              className="p-2 rounded bg-gray-200 text-gray-600 hover:bg-gray-300"><X className="w-4 h-4" /></button>
          </div>
        )}

        {/* DataFile Mapper */}
        {showMapper && (
          <DataFileColumnMapper variables={variables} dataFiles={dataFiles}
            onLink={linkToDataFile} onClose={() => setShowMapper(false)} />
        )}

        {/* === Section: manual, imported, auto, extractor === */}
        {filteredMain.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
              Manuales e importadas ({filteredMain.length})
            </p>
            <div className="rounded-md border border-gray-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-xs text-gray-500 font-medium">
                    <th className="text-left px-3 py-2 w-[28%]">Variable</th>
                    <th className="text-left px-3 py-2 w-[32%]">Valor</th>
                    <th className="text-left px-3 py-2 w-[18%]">Tipo</th>
                    <th className="text-left px-3 py-2 w-[22%]">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredMain.map(v => {
                    const isEditing = editingName === v.name;
                    const cfg = TYPE_CONFIG[v.type];
                    return (
                      <tr key={v.name} className="border-t border-gray-100 hover:bg-gray-50">
                        <td className="px-3 py-2">
                          <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded font-mono text-gray-800">
                            {`\${${v.name}}`}
                          </code>
                          {v.source_hint && (
                            <p className="text-xs text-gray-400 mt-0.5 truncate max-w-[160px]">{v.source_hint}</p>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          {isEditing ? (
                            <div className="space-y-1">
                              <input type="text" value={editValue} autoFocus
                                onChange={e => setEditValue(e.target.value)}
                                placeholder={v.type === 'extractor' ? 'Vacio (runtime lo llena)' : 'Valor'}
                                className="w-full text-sm px-2 py-1 border border-blue-400 rounded focus:outline-none" />
                              {v.type === 'extractor' && (
                                <input type="text" value={editDefault}
                                  onChange={e => setEditDefault(e.target.value)}
                                  placeholder="Valor default si falla la extraccion"
                                  className="w-full text-xs px-2 py-1 border border-amber-300 rounded bg-amber-50 focus:outline-none" />
                              )}
                            </div>
                          ) : (
                            <div>
                              {v.type === 'extractor' ? (
                                <div>
                                  <span className="text-xs text-amber-600 flex items-center gap-1">
                                    <AlertCircle className="w-3 h-3" /> Se captura en runtime
                                  </span>
                                  {v.default_value && (
                                    <span className="text-xs text-gray-500 block mt-0.5">
                                      Default: <code className="bg-gray-100 px-1 rounded">{v.default_value}</code>
                                    </span>
                                  )}
                                </div>
                              ) : (
                                <span className={`text-sm break-all ${v.value ? 'text-gray-800' : 'text-gray-400 italic'}`}>
                                  {v.value || '(sin valor)'}
                                </span>
                              )}
                            </div>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${cfg.bg} ${cfg.color}`}>
                            {cfg.label}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          {isEditing ? (
                            <div className="flex gap-1">
                              <button onClick={() => saveEdit(v)} className="p-1 text-green-600 hover:bg-green-50 rounded" title="Guardar"><Check className="w-4 h-4" /></button>
                              <button onClick={() => setEditingName(null)} className="p-1 text-gray-400 hover:bg-gray-100 rounded" title="Cancelar"><X className="w-4 h-4" /></button>
                            </div>
                          ) : (
                            <div className="flex gap-1">
                              <button onClick={() => startEdit(v)} className="p-1 text-blue-600 hover:bg-blue-50 rounded"
                                title={v.type === 'extractor' ? 'Editar valor default' : 'Editar valor'}>
                                <Edit2 className="w-4 h-4" />
                              </button>
                              {canDelete(v.type) && (
                                <button onClick={() => deleteVar(v.name)} className="p-1 text-red-500 hover:bg-red-50 rounded" title="Eliminar">
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              )}
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* === Section: Data File === */}
        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
            Vinculadas a Data File ({filteredDF.length})
          </p>
          {filteredDF.length > 0 ? (
            <div className="rounded-md border border-gray-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-xs text-gray-500 font-medium">
                    <th className="text-left px-3 py-2 w-[30%]">Variable</th>
                    <th className="text-left px-3 py-2 w-[50%]">Archivo &rarr; Columna</th>
                    <th className="text-left px-3 py-2 w-[20%]"></th>
                  </tr>
                </thead>
                <tbody>
                  {filteredDF.map(v => (
                    <tr key={v.name} className="border-t border-gray-100 hover:bg-gray-50">
                      <td className="px-3 py-2">
                        <code className="text-xs bg-green-100 px-1.5 py-0.5 rounded font-mono text-green-800">
                          {`\${${v.name}}`}
                        </code>
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-1.5 text-xs text-gray-700">
                          <FileText className="w-3.5 h-3.5 text-green-600 flex-shrink-0" />
                          <span className="font-medium">{v.datafile_name}</span>
                          <span className="text-gray-400">&rarr;</span>
                          <code className="bg-gray-100 px-1 rounded">{v.datafile_column}</code>
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        <button onClick={() => unlinkDataFile(v.name)}
                          className="p-1 text-red-500 hover:bg-red-50 rounded" title="Desvincular">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-sm text-gray-400 italic py-4 text-center border border-dashed border-gray-200 rounded-md">
              Usa "CSV" para mapear una columna de tu CSV a una variable
            </div>
          )}
        </div>

        {/* === Section: Built-ins === */}
        <div>
          <button onClick={() => setShowBuiltins(!showBuiltins)}
            className="flex items-center gap-2 text-xs font-semibold text-gray-400 uppercase tracking-wide hover:text-gray-600">
            {showBuiltins ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            Funciones del sistema ({BUILTIN_VARIABLES.length})
          </button>
          {showBuiltins && (
            <div className="mt-2 rounded-md border border-gray-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-xs text-gray-500 font-medium">
                    <th className="text-left px-3 py-2 w-[35%]">Funcion</th>
                    <th className="text-left px-3 py-2">Descripcion</th>
                  </tr>
                </thead>
                <tbody>
                  {BUILTIN_VARIABLES.map(b => (
                    <tr key={b.name} className="border-t border-gray-100">
                      <td className="px-3 py-2">
                        <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded font-mono text-gray-700">
                          {`\${${b.name}}`}
                        </code>
                      </td>
                      <td className="px-3 py-2 text-xs text-gray-500">{b.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Empty state */}
        {totalNonBuiltin === 0 && !showNewForm && (
          <div className="text-center py-12 text-gray-400">
            <div className="text-5xl mb-3">&#128235;</div>
            <p className="text-sm font-medium">No hay variables en este script</p>
            <p className="text-xs mt-1 text-gray-400">
              Usa "Escanear" para detectar variables existentes en tus requests,<br/>
              o "Nueva" para crear una manualmente.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── DataFileColumnMapper ──────────────────────────────────────────────────────
interface MapperProps {
  variables: ScriptVariable[];
  dataFiles: DataFileInfo[];
  onLink: (varName: string, dfName: string, column: string) => void;
  onClose: () => void;
}

function DataFileColumnMapper({ variables, dataFiles, onLink, onClose }: MapperProps) {
  const [selVar, setSelVar] = useState('');
  const [selFile, setSelFile] = useState('');
  const [selCol, setSelCol] = useState('');
  const [cols, setCols] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const linkable = variables.filter(v => v.type !== 'builtin' && v.type !== 'datafile');

  const onFileChange = async (filename: string) => {
    setSelFile(filename); setSelCol('');
    if (!filename) { setCols([]); return; }
    const df = dataFiles.find(f => f.filename === filename);
    if (df?.columns?.length) { setCols(df.columns); return; }
    if (df?.id) {
      setLoading(true);
      try {
        const csrfToken = document.cookie
          .split('; ')
          .find(row => row.startsWith('csrf_token='))
          ?.split('=')[1] || '';
        const res = await fetch(`/api/v1/data-files/${df.id}/columns`, {
          credentials: 'include',
          headers: { 'X-CSRF-Token': csrfToken },
        });
        if (res.ok) { const d = await res.json(); setCols(d.columns || []); }
      } catch { setCols([]); }
      finally { setLoading(false); }
    }
  };

  return (
    <div className="p-4 border border-green-300 rounded-md bg-green-50">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Database className="w-4 h-4 text-green-700" />
          <p className="text-sm font-semibold text-green-800">Vincular variable a columna CSV</p>
        </div>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="w-4 h-4" /></button>
      </div>
      <div className="grid grid-cols-3 gap-3 mb-3">
        <div>
          <label className="text-xs font-medium text-gray-700 mb-1 block">Variable</label>
          <select value={selVar} onChange={e => setSelVar(e.target.value)}
            className="w-full text-sm px-2 py-1.5 border border-gray-300 rounded bg-white focus:outline-none focus:ring-2 focus:ring-green-300">
            <option value="">Seleccionar...</option>
            {linkable.map(v => <option key={v.name} value={v.name}>{`\${${v.name}}`}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs font-medium text-gray-700 mb-1 block">Archivo CSV</label>
          <select value={selFile} onChange={e => onFileChange(e.target.value)}
            className="w-full text-sm px-2 py-1.5 border border-gray-300 rounded bg-white focus:outline-none focus:ring-2 focus:ring-green-300">
            <option value="">Seleccionar...</option>
            {dataFiles.map(f => <option key={f.id} value={f.filename}>{f.filename}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs font-medium text-gray-700 mb-1 block">
            Columna {loading && <span className="text-gray-400 ml-1">cargando...</span>}
          </label>
          <select value={selCol} onChange={e => setSelCol(e.target.value)} disabled={!cols.length}
            className="w-full text-sm px-2 py-1.5 border border-gray-300 rounded bg-white disabled:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-green-300">
            <option value="">Seleccionar...</option>
            {cols.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      </div>
      <div className="flex justify-end">
        <button
          onClick={() => selVar && selFile && selCol && onLink(selVar, selFile, selCol)}
          disabled={!selVar || !selFile || !selCol}
          className="text-sm px-4 py-1.5 bg-green-700 text-white rounded hover:bg-green-800 disabled:opacity-40 disabled:cursor-not-allowed">
          Vincular
        </button>
      </div>
    </div>
  );
}
