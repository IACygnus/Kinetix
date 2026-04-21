// frontend/src/components/script-designer/BodyEditor.tsx
/**
 * Body editor with three modes:
 * - Normal: textarea full width
 * - Edit variable: 50/50 (textarea | VariableInlineEditor), or 33/33/33 with preview
 * - Create from selection: 50/50 (textarea | VariableCreator)
 */
import { useState, useRef, useCallback } from 'react';
import {
  RotateCcw, RotateCw, Braces, ChevronDown, Code,
  Scissors, X, Database, Shuffle, Type
} from 'lucide-react';
import VariableInlineEditor from './VariableInlineEditor';
import VariableValuePreview from './VariableValuePreview';
import type { DataFileOption } from './VariableInlineEditor';
import type { ScriptVariable } from './VariableManager';

// ── Detect variable at cursor ─────────────────────────────────────────────────
const SYSTEM_BUILTINS = new Set([
  '$guid', '$randomIP', '$timestamp', '$isoTimestamp',
  '$randomInt', '$randomAlphaNum', '$randomFirstName', '$randomLastName', '$randomEmail',
]);

function getVarAtCursor(text: string, cursor: number): string | null {
  const before = text.slice(0, cursor);
  const after = text.slice(cursor);
  const start = before.lastIndexOf('${');
  if (start === -1) return null;
  if (before.slice(start).includes('}')) return null;
  const closeIdx = after.indexOf('}');
  if (closeIdx === -1) return null;
  const name = (before.slice(start + 2) + after.slice(0, closeIdx)).trim();
  if (!name || SYSTEM_BUILTINS.has(name)) return null;
  return name;
}

// ── Detect text selection ─────────────────────────────────────────────────────
function getSelection(ta: HTMLTextAreaElement): { text: string; start: number; end: number } | null {
  const s = ta.selectionStart;
  const e = ta.selectionEnd;
  if (s === e) return null;
  const text = ta.value.slice(s, e).trim();
  if (!text || text.length < 2) return null;
  if (text.startsWith('${') && text.endsWith('}')) return null;
  return { text, start: s, end: e };
}

// ── Undo/redo with refs ───────────────────────────────────────────────────────
function useHistory(initial: string) {
  const hist = useRef<string[]>([initial]);
  const cur = useRef(0);
  const [, tick] = useState(0);

  const push = useCallback((v: string) => {
    if (hist.current[cur.current] === v) return;
    hist.current = hist.current.slice(0, cur.current + 1).concat(v).slice(-100);
    cur.current = hist.current.length - 1;
    tick(n => n + 1);
  }, []);

  const undo = useCallback((): string | null => {
    if (cur.current <= 0) return null;
    cur.current--;
    tick(n => n + 1);
    return hist.current[cur.current];
  }, []);

  const redo = useCallback((): string | null => {
    if (cur.current >= hist.current.length - 1) return null;
    cur.current++;
    tick(n => n + 1);
    return hist.current[cur.current];
  }, []);

  return { push, undo, redo, canUndo: cur.current > 0, canRedo: cur.current < hist.current.length - 1 };
}

// ── Props ─────────────────────────────────────────────────────────────────────
interface Props {
  value: string;
  onChange: (v: string) => void;
  variables: ScriptVariable[];
  dataFiles?: DataFileOption[];
  onVariableChange?: (updated: ScriptVariable) => void;
  onVariableCreate?: (newVar: ScriptVariable) => void;
  placeholder?: string;
}

type PanelMode = 'none' | 'edit-var' | 'create-from-selection';

// ── Component ─────────────────────────────────────────────────────────────────
export default function BodyEditor({
  value, onChange, variables, dataFiles, onVariableChange, onVariableCreate, placeholder,
}: Props) {
  const taRef = useRef<HTMLTextAreaElement>(null);
  const history = useHistory(value);

  const [panelMode, setPanelMode] = useState<PanelMode>('none');
  const [activeVarName, setActiveVarName] = useState<string | null>(null);
  const [selection, setSelection] = useState<{ text: string; start: number; end: number } | null>(null);
  const [showPreview, setShowPreview] = useState(false);

  const [showInsert, setShowInsert] = useState(false);
  const [insertFilter, setInsertFilter] = useState('');

  const ALL_FUNCTIONS: { name: string; category: string; label: string; example: string }[] = [
    { name: '$randomFirstName',    category: 'Texto',    label: 'Nombre propio',        example: 'Carlos' },
    { name: '$randomLastName',     category: 'Texto',    label: 'Apellido',             example: 'Gonzalez' },
    { name: '$randomEmail',        category: 'Texto',    label: 'Email aleatorio',      example: 'user_k3@test.com' },
    { name: '$randomAlphaNum(8)',  category: 'Texto',    label: 'Alfanumerico (N=8)',   example: 'k3m9x2b1' },
    { name: '$randomString(6)',    category: 'Texto',    label: 'Solo letras (N=6)',    example: 'kxmqpr' },
    { name: '$randomWord',         category: 'Texto',    label: 'Palabra aleatoria',    example: 'phoenix' },
    { name: '$randomPhrase',       category: 'Texto',    label: 'Frase aleatoria',      example: 'alpha beta gamma' },
    { name: '$randomInt(1,1000)',   category: 'Numeros',  label: 'Entero en rango',      example: '742' },
    { name: '$randomFloat(1,100,2)',category: 'Numeros',  label: 'Decimal con 2 digitos',example: '34.72' },
    { name: '$randomPrice',        category: 'Numeros',  label: 'Precio (ej: 99.99)',   example: '99.99' },
    { name: '$randomDate(2020-01-01,2025-12-31,YYYY-MM-DD)', category: 'Fechas', label: 'Fecha en rango', example: '2023-04-15' },
    { name: '$today(YYYY-MM-DD)',   category: 'Fechas',  label: 'Fecha de hoy',         example: new Date().toISOString().slice(0, 10) },
    { name: '$tomorrow(YYYY-MM-DD)',category: 'Fechas',  label: 'Manana',               example: new Date(Date.now() + 86400000).toISOString().slice(0, 10) },
    { name: '$dateOffset(7,YYYY-MM-DD)', category: 'Fechas', label: 'Hoy + N dias',     example: new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10) },
    { name: '$guid',               category: 'Sistema',  label: 'UUID v4',              example: 'a1b2-c3d4...' },
    { name: '$timestamp',          category: 'Sistema',  label: 'Unix timestamp (ms)',  example: String(Date.now()) },
    { name: '$isoTimestamp',       category: 'Sistema',  label: 'ISO 8601',             example: '2025-01-15T10:30:00Z' },
    { name: '$randomIP',           category: 'Sistema',  label: 'IP aleatoria',         example: '192.168.1.45' },
    { name: '$randomCNP',          category: 'Datos',    label: 'ID (10 digitos)',      example: '1234567890' },
    { name: '$randomPhone',        category: 'Datos',    label: 'Telefono Colombia',    example: '+573001234567' },
  ];

  const userVars = variables.filter(v =>
    v.type !== 'builtin' &&
    (!insertFilter || v.name.toLowerCase().includes(insertFilter.toLowerCase()))
  );
  const filteredFunctions = ALL_FUNCTIONS.filter(f =>
    !insertFilter ||
    f.name.toLowerCase().includes(insertFilter.toLowerCase()) ||
    f.label.toLowerCase().includes(insertFilter.toLowerCase()) ||
    f.category.toLowerCase().includes(insertFilter.toLowerCase())
  );
  const fnCategories = [...new Set(filteredFunctions.map(f => f.category))];

  // ── Evaluate cursor/selection ───────────────────────────────────────────────
  const evaluateCursor = useCallback((ta: HTMLTextAreaElement) => {
    // First check for text selection
    const sel = getSelection(ta);
    if (sel && onVariableCreate) {
      setSelection(sel);
      setPanelMode('create-from-selection');
      setActiveVarName(null);
      setShowPreview(false);
      return;
    }
    // Then check for variable at cursor
    if (onVariableChange) {
      const varName = getVarAtCursor(ta.value, ta.selectionStart ?? 0);
      if (varName) {
        setActiveVarName(varName);
        setPanelMode('edit-var');
        setSelection(null);
        const existing = variables.find(v => v.name === varName);
        setShowPreview(!!existing?.value || existing?.type === 'datafile' || existing?.type === 'extractor');
        return;
      }
    }
    setPanelMode('none');
    setActiveVarName(null);
    setSelection(null);
    setShowPreview(false);
  }, [variables, onVariableChange, onVariableCreate]);

  const handleClick = (e: React.MouseEvent<HTMLTextAreaElement>) => evaluateCursor(e.currentTarget);
  const handleKeyUp = (e: React.KeyboardEvent<HTMLTextAreaElement>) => evaluateCursor(e.currentTarget);
  const handleMouseUp = () => {
    setTimeout(() => { if (taRef.current) evaluateCursor(taRef.current); }, 10);
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onChange(e.target.value);
    history.push(e.target.value);
    if (onVariableChange) {
      const found = getVarAtCursor(e.target.value, e.target.selectionStart ?? 0);
      if (found) { setActiveVarName(found); setPanelMode('edit-var'); }
      else { setPanelMode('none'); setActiveVarName(null); }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Escape') { closePanel(); return; }
    if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
      e.preventDefault(); const v = history.undo(); if (v !== null) onChange(v); return;
    }
    if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
      e.preventDefault(); const v = history.redo(); if (v !== null) onChange(v); return;
    }
    if (e.key === 'Tab') {
      e.preventDefault();
      const ta = e.currentTarget;
      const s = ta.selectionStart;
      const nv = value.slice(0, s) + '  ' + value.slice(ta.selectionEnd);
      onChange(nv); history.push(nv);
      setTimeout(() => ta.setSelectionRange(s + 2, s + 2), 0);
    }
  };

  const insertVariable = (varName: string) => {
    const ta = taRef.current; if (!ta) return;
    const s = ta.selectionStart;
    const syntax = `\${${varName}}`;
    const nv = value.slice(0, s) + syntax + value.slice(ta.selectionEnd);
    onChange(nv); history.push(nv);
    setTimeout(() => { ta.focus(); ta.setSelectionRange(s + syntax.length, s + syntax.length); }, 0);
    setShowInsert(false);
  };

  const formatJSON = () => {
    try { const f = JSON.stringify(JSON.parse(value), null, 2); onChange(f); history.push(f); } catch { /* noop */ }
  };

  const closePanel = () => {
    setPanelMode('none'); setActiveVarName(null); setSelection(null); setShowPreview(false);
  };

  // ── Create variable from selection ──────────────────────────────────────────
  const handleCreateFromSelection = (varName: string, newVar: ScriptVariable) => {
    if (!selection) return;
    const syntax = `\${${varName}}`;
    const newBody = value.slice(0, selection.start) + syntax + value.slice(selection.end);
    onChange(newBody); history.push(newBody);
    if (onVariableCreate) onVariableCreate(newVar);
    closePanel();
  };

  // ── Layout sizing ───────────────────────────────────────────────────────────
  const hasPanel = panelMode !== 'none';
  const hasPreview = panelMode === 'edit-var' && showPreview && activeVarName;
  const textareaClass = !hasPanel ? 'w-full' : hasPreview ? 'w-1/3' : 'w-1/2';
  const panelClass = hasPreview ? 'w-1/3' : 'w-1/2';

  const activeVar = activeVarName ? variables.find(v => v.name === activeVarName) ?? null : null;

  return (
    <div className="border border-gray-300 rounded-md overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center gap-1 px-2 py-1.5 bg-gray-50 border-b border-gray-200 flex-shrink-0 flex-wrap">
        <button onClick={() => { const v = history.undo(); if (v !== null) onChange(v); }}
          title="Deshacer (Ctrl+Z)" disabled={!history.canUndo}
          className="p-1 rounded text-gray-500 hover:bg-gray-200 disabled:opacity-30">
          <RotateCcw className="w-3.5 h-3.5" />
        </button>
        <button onClick={() => { const v = history.redo(); if (v !== null) onChange(v); }}
          title="Rehacer (Ctrl+Y)" disabled={!history.canRedo}
          className="p-1 rounded text-gray-500 hover:bg-gray-200 disabled:opacity-30">
          <RotateCw className="w-3.5 h-3.5" />
        </button>
        <div className="w-px h-4 bg-gray-300 mx-1" />
        <button onClick={formatJSON} title="Formatear JSON"
          className="flex items-center gap-1 text-xs px-2 py-1 rounded text-gray-600 hover:bg-gray-200">
          <Braces className="w-3.5 h-3.5" /> Formatear
        </button>
        <div className="w-px h-4 bg-gray-300 mx-1" />

        {/* Insert variable dropdown */}
        <div className="relative">
          <button onClick={() => setShowInsert(!showInsert)}
            className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-blue-50
                       text-blue-700 hover:bg-blue-100 border border-blue-200">
            <Code className="w-3.5 h-3.5" /> Insertar variable
            <ChevronDown className={`w-3 h-3 transition-transform ${showInsert ? 'rotate-180' : ''}`} />
          </button>
          {showInsert && (
            <div className="absolute top-full left-0 z-50 mt-1 w-64 bg-white border border-gray-200 rounded-md shadow-xl overflow-hidden">
              <div className="p-2 border-b">
                <input type="text" autoFocus placeholder="Buscar variable..."
                  value={insertFilter} onChange={e => setInsertFilter(e.target.value)}
                  className="w-full text-sm px-2 py-1.5 border border-gray-300 rounded focus:outline-none" />
              </div>
              <div className="max-h-56 overflow-y-auto">
                {userVars.length > 0 && (
                  <>
                    <p className="px-3 py-1 text-xs font-semibold text-gray-400 uppercase bg-gray-50">MIS VARIABLES</p>
                    {userVars.map(v => (
                      <button key={v.name} onClick={() => insertVariable(v.name)}
                        className="w-full text-left px-3 py-2 hover:bg-blue-50 flex items-center justify-between text-sm">
                        <code className="text-blue-700 font-mono">{`\${${v.name}}`}</code>
                        {v.value && <span className="text-xs text-gray-400 truncate max-w-[80px] ml-2">{v.value}</span>}
                      </button>
                    ))}
                  </>
                )}
                {fnCategories.map(cat => (
                  <div key={cat}>
                    <p className="px-3 py-1 text-xs font-semibold text-gray-400 uppercase bg-gray-50">{cat}</p>
                    {filteredFunctions.filter(f => f.category === cat).map(f => (
                      <button key={f.name} onClick={() => insertVariable(f.name)}
                        className="w-full text-left px-3 py-1.5 hover:bg-blue-50 flex items-center justify-between text-sm">
                        <div className="min-w-0">
                          <code className="text-indigo-600 font-mono text-xs">{`\${${f.name}}`}</code>
                          <p className="text-xs text-gray-500 truncate">{f.label}</p>
                        </div>
                        <span className="text-xs text-gray-400 italic ml-2 flex-shrink-0">{f.example}</span>
                      </button>
                    ))}
                  </div>
                ))}
                {userVars.length === 0 && filteredFunctions.length === 0 && (
                  <p className="text-sm text-gray-400 text-center py-4">Sin resultados</p>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Status indicators */}
        {panelMode === 'edit-var' && activeVarName && (
          <span className="text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full border border-blue-200 ml-1">
            Editando: <code className="font-mono">{`\${${activeVarName}}`}</code>
          </span>
        )}
        {panelMode === 'create-from-selection' && selection && (
          <span className="flex items-center gap-1 text-xs text-purple-600 bg-purple-50 px-2 py-0.5 rounded-full border border-purple-200 ml-1">
            <Scissors className="w-3 h-3" />
            Convertir: <code className="font-mono ml-0.5">"{selection.text.slice(0, 20)}{selection.text.length > 20 ? '...' : ''}"</code>
          </span>
        )}

        <span className="ml-auto text-xs text-gray-400 hidden sm:inline">
          Selecciona texto o click en ${'{var}'}
        </span>
      </div>

      {/* Main area */}
      <div className="flex" style={{ minHeight: '200px' }}>
        {/* Textarea */}
        <textarea
          ref={taRef}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onClick={handleClick}
          onKeyUp={handleKeyUp}
          onMouseUp={handleMouseUp}
          onBlur={() => setTimeout(() => setShowInsert(false), 200)}
          placeholder={placeholder || '{\n  "key": "${variable}"\n}'}
          rows={10}
          spellCheck={false}
          className={`text-sm px-3 py-2.5 font-mono bg-white focus:outline-none resize-none transition-all ${textareaClass}`}
          style={{ fontFamily: 'Consolas, Monaco, "Courier New", monospace', minHeight: '200px' }}
        />

        {/* Edit/Create panel */}
        {hasPanel && (
          <div className={`border-l border-gray-300 flex-shrink-0 overflow-hidden ${panelClass}`}>
            {panelMode === 'edit-var' && activeVarName && onVariableChange && (
              <VariableInlineEditor
                varName={activeVarName}
                currentVar={activeVar}
                dataFiles={dataFiles || []}
                onApply={(updated) => {
                  onVariableChange(updated);
                  setShowPreview(!!updated.value || updated.type === 'datafile');
                }}
                onClose={closePanel}
              />
            )}
            {panelMode === 'create-from-selection' && selection && (
              <VariableCreator
                selectedText={selection.text}
                dataFiles={dataFiles || []}
                existingVarNames={variables.map(v => v.name)}
                onCreate={handleCreateFromSelection}
                onClose={closePanel}
              />
            )}
          </div>
        )}

        {/* Preview panel */}
        {hasPreview && activeVarName && (
          <div className="w-1/3 border-l border-gray-300 flex-shrink-0 overflow-hidden">
            <VariableValuePreview varName={activeVarName} variable={activeVar} />
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-3 py-1.5 bg-gray-50 border-t border-gray-100">
        <span className="text-xs text-gray-400">
          Ctrl+Z deshacer &bull; Tab = 2 espacios &bull;
          Selecciona texto para crear variable &bull; Click en <code className="bg-gray-200 px-1 rounded">{`\${var}`}</code> para editar
        </span>
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════════════
// VariableCreator — inline subcomponent for creating a variable from selection
// ═══════════════════════════════════════════════════════════════════════════════

type CreatorSourceType = 'manual' | 'datafile' | 'random';
type CreatorRandomFn = 'firstName' | 'lastName' | 'email' | 'integer' | 'alphaNum' | 'dateRange';

function buildCreatorBuiltin(fn: CreatorRandomFn, cfg: { min: number; max: number; from: string; to: string; fmt: string }): string {
  switch (fn) {
    case 'firstName': return '$randomFirstName';
    case 'lastName':  return '$randomLastName';
    case 'email':     return '$randomEmail';
    case 'integer':   return `$randomInt(${cfg.min},${cfg.max})`;
    case 'alphaNum':  return '$randomAlphaNum';
    case 'dateRange': return `$randomDate(${cfg.from},${cfg.to},${cfg.fmt})`;
  }
}

const CREATOR_DATE_FORMATS = [
  { value: 'YYYY-MM-DD', label: 'YYYY-MM-DD' },
  { value: 'DD/MM/YYYY', label: 'DD/MM/YYYY' },
  { value: 'MM/DD/YYYY', label: 'MM/DD/YYYY' },
  { value: 'iso',        label: 'ISO 8601' },
  { value: 'timestamp',  label: 'Timestamp' },
];

const CREATOR_RANDOM_OPTIONS: { fn: CreatorRandomFn; label: string }[] = [
  { fn: 'firstName', label: 'Nombre propio' },
  { fn: 'lastName',  label: 'Apellido' },
  { fn: 'email',     label: 'Email aleatorio' },
  { fn: 'integer',   label: 'Entero (rango)' },
  { fn: 'alphaNum',  label: 'Alfanumerico' },
  { fn: 'dateRange', label: 'Fecha en rango' },
];

interface CreatorProps {
  selectedText: string;
  dataFiles: DataFileOption[];
  existingVarNames: string[];
  onCreate: (varName: string, newVar: ScriptVariable) => void;
  onClose: () => void;
}

function VariableCreator({ selectedText, dataFiles, existingVarNames, onCreate, onClose }: CreatorProps) {
  const [varName, setVarName] = useState('');
  const [src, setSrc] = useState<CreatorSourceType>('manual');
  const [file, setFile] = useState('');
  const [col, setCol] = useState('');
  const [cols, setCols] = useState<string[]>([]);
  const [fn, setFn] = useState<CreatorRandomFn>('firstName');
  const [cfg, setCfg] = useState({ min: 0, max: 1000, from: '2020-01-01', to: '2025-12-31', fmt: 'YYYY-MM-DD' });
  const [nameError, setNameError] = useState('');

  const handleCreate = () => {
    const trimmed = varName.trim();
    if (!trimmed) { setNameError('El nombre es obligatorio'); return; }
    if (existingVarNames.includes(trimmed)) { setNameError(`"${trimmed}" ya existe`); return; }
    if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(trimmed)) {
      setNameError('Solo letras, numeros y guion bajo. Debe empezar con letra.'); return;
    }

    let newVar: ScriptVariable;
    if (src === 'manual') {
      newVar = { name: trimmed, value: selectedText.replace(/^["']|["']$/g, ''), type: 'manual', source_hint: 'Desde seleccion de texto' };
    } else if (src === 'datafile') {
      newVar = { name: trimmed, value: '', type: 'datafile', source_hint: `${file} -> ${col}`, datafile_name: file, datafile_column: col };
    } else {
      const builtin = buildCreatorBuiltin(fn, cfg);
      newVar = { name: trimmed, value: builtin, type: 'auto', source_hint: `Funcion: ${builtin}` };
    }
    onCreate(trimmed, newVar);
  };

  const canCreate = varName.trim().length > 0 && (
    src === 'manual' ||
    (src === 'datafile' && !!file && !!col) ||
    src === 'random'
  );

  return (
    <div className="flex flex-col h-full bg-white overflow-hidden" style={{ height: '100%' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 bg-purple-900 text-white flex-shrink-0">
        <div className="min-w-0">
          <p className="text-xs text-purple-300">Crear variable desde seleccion</p>
          <code className="text-sm font-mono text-yellow-300 truncate block">
            "{selectedText.slice(0, 30)}{selectedText.length > 30 ? '...' : ''}"
          </code>
        </div>
        <button onClick={onClose} className="p-1 hover:bg-white/20 rounded ml-2 flex-shrink-0">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3 text-sm">
        {/* Variable name */}
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1">
            Nombre de la variable <span className="text-red-500">*</span>
          </label>
          <input type="text" autoFocus
            value={varName}
            onChange={e => { setVarName(e.target.value); setNameError(''); }}
            onKeyDown={e => e.key === 'Enter' && canCreate && handleCreate()}
            placeholder="ej: additionalNeeds"
            className={`w-full text-sm px-2 py-2 border rounded focus:outline-none focus:ring-2 focus:ring-purple-300 font-mono ${
              nameError ? 'border-red-400 bg-red-50' : 'border-gray-300'
            }`}
          />
          {nameError && <p className="text-xs text-red-600 mt-1">{nameError}</p>}
          {varName.trim() && !nameError && (
            <p className="text-xs text-purple-600 mt-1">
              En el body quedara: <code className="bg-purple-50 px-1 rounded">{`\${${varName.trim()}}`}</code>
            </p>
          )}
        </div>

        {/* Source selector */}
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1">Fuente del valor</label>
          <div className="space-y-1">
            {([
              { v: 'manual' as const, icon: Type, label: 'Valor fijo', desc: `Usar: "${selectedText.slice(0, 20)}"` },
              { v: 'datafile' as const, icon: Database, label: 'Desde CSV/TXT', desc: 'Leer de archivo' },
              { v: 'random' as const, icon: Shuffle, label: 'Funcion aleatoria', desc: 'Generar en runtime' },
            ]).map(opt => (
              <label key={opt.v}
                className={`flex items-center gap-2 px-2 py-2 rounded cursor-pointer border transition-colors ${
                  src === opt.v ? 'border-purple-400 bg-purple-50 text-purple-800' : 'border-gray-200 hover:bg-gray-50 text-gray-700'
                }`}>
                <input type="radio" name="creator-src" value={opt.v}
                  checked={src === opt.v} onChange={() => setSrc(opt.v)}
                  className="accent-purple-600" />
                <opt.icon className="w-3.5 h-3.5 flex-shrink-0" />
                <div className="min-w-0">
                  <p className="text-sm font-medium">{opt.label}</p>
                  <p className="text-xs text-gray-400 truncate">{opt.desc}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* DataFile config */}
        {src === 'datafile' && (
          <div className="space-y-2 border-t border-gray-100 pt-2">
            {dataFiles.length === 0 ? (
              <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-2">
                No hay archivos cargados. Usa "Data Files" para subir uno.
              </p>
            ) : (
              <>
                <select value={file} onChange={e => { setFile(e.target.value); setCol(''); setCols([]); }}
                  className="w-full text-sm px-2 py-1.5 border border-gray-300 rounded bg-white focus:outline-none">
                  <option value="">Seleccionar archivo...</option>
                  {dataFiles.map(f => <option key={f.id} value={f.filename}>{f.filename}</option>)}
                </select>
                {file && cols.length === 0 && (
                  <button onClick={async () => {
                    const df = dataFiles.find(f => f.filename === file);
                    if (!df) return;
                    try {
                      const csrfToken = document.cookie.match(/csrf_token=([^;]+)/)?.[1] || '';
                      const r = await fetch(`/api/v1/data-files/${df.id}/columns`, {
                        credentials: 'include',
                        headers: { 'X-CSRF-Token': csrfToken },
                      });
                      const d = await r.json();
                      setCols(d.columns || []);
                    } catch { setCols([]); }
                  }} className="text-xs text-blue-600 hover:underline">
                    Cargar columnas
                  </button>
                )}
                {cols.length > 0 && (
                  <select value={col} onChange={e => setCol(e.target.value)}
                    className="w-full text-sm px-2 py-1.5 border border-gray-300 rounded bg-white focus:outline-none">
                    <option value="">Seleccionar columna...</option>
                    {cols.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                )}
              </>
            )}
          </div>
        )}

        {/* Random config */}
        {src === 'random' && (
          <div className="space-y-2 border-t border-gray-100 pt-2">
            {CREATOR_RANDOM_OPTIONS.map(opt => (
              <label key={opt.fn}
                className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer border text-sm ${
                  fn === opt.fn ? 'border-purple-400 bg-purple-50 text-purple-800' : 'border-gray-200 hover:bg-gray-50'
                }`}>
                <input type="radio" name="creator-fn" value={opt.fn}
                  checked={fn === opt.fn} onChange={() => setFn(opt.fn)}
                  className="accent-purple-600" />
                {opt.label}
              </label>
            ))}
            {fn === 'integer' && (
              <div className="flex gap-2 pt-1">
                <input type="number" value={cfg.min} placeholder="Min"
                  onChange={e => setCfg(p => ({ ...p, min: +e.target.value }))}
                  className="flex-1 text-sm px-2 py-1 border border-gray-300 rounded focus:outline-none" />
                <input type="number" value={cfg.max} placeholder="Max"
                  onChange={e => setCfg(p => ({ ...p, max: +e.target.value }))}
                  className="flex-1 text-sm px-2 py-1 border border-gray-300 rounded focus:outline-none" />
              </div>
            )}
            {fn === 'dateRange' && (
              <div className="space-y-1.5 pt-1">
                <input type="date" value={cfg.from}
                  onChange={e => setCfg(p => ({ ...p, from: e.target.value }))}
                  className="w-full text-sm px-2 py-1 border border-gray-300 rounded focus:outline-none" />
                <input type="date" value={cfg.to}
                  onChange={e => setCfg(p => ({ ...p, to: e.target.value }))}
                  className="w-full text-sm px-2 py-1 border border-gray-300 rounded focus:outline-none" />
                <select value={cfg.fmt} onChange={e => setCfg(p => ({ ...p, fmt: e.target.value }))}
                  className="w-full text-sm px-2 py-1.5 border border-gray-300 rounded bg-white focus:outline-none">
                  {CREATOR_DATE_FORMATS.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
                </select>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="flex gap-2 px-3 py-2.5 border-t border-gray-200 bg-gray-50 flex-shrink-0">
        <button onClick={onClose}
          className="flex-1 text-sm px-3 py-2 border border-gray-300 rounded text-gray-700 hover:bg-gray-100">
          Cancelar
        </button>
        <button onClick={handleCreate} disabled={!canCreate}
          className="flex-1 text-sm px-3 py-2 rounded bg-purple-700 text-white font-medium
                     hover:bg-purple-800 disabled:opacity-40 disabled:cursor-not-allowed">
          Crear variable
        </button>
      </div>
    </div>
  );
}
