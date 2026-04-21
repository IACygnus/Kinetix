// frontend/src/components/script-designer/VariableInlineEditor.tsx
/**
 * Panel lateral contextual para editar una variable específica.
 * Se abre al hacer click en ${varName} en el BodyEditor.
 *
 * Permite configurar:
 * 1. Valor manual (string directo)
 * 2. Desde archivo CSV/TXT (seleccionar archivo -> columna -> preview)
 * 3. Función random:
 *    - Nombre (firstName, lastName)
 *    - Email
 *    - Número entero (min-max)
 *    - Alfanumérico
 *    - Fecha en rango (dateFrom - dateTo, formato configurable)
 */
import { useState, useEffect } from 'react';
import {
  X, Shuffle, Type,
  Calendar, Hash, AtSign, User, AlignLeft, Database
} from 'lucide-react';
import type { ScriptVariable } from './VariableManager';

// ─── Tipos ────────────────────────────────────────────────────────────────────

export interface DataFileOption {
  id: number;
  filename: string;
  columns?: string[];
}

type SourceType = 'manual' | 'datafile' | 'random';

type RandomFunction =
  | 'firstName' | 'lastName' | 'email'
  | 'integer' | 'alphaNum'
  | 'dateRange';

interface RandomConfig {
  fn: RandomFunction;
  min?: number;
  max?: number;
  dateFrom?: string;
  dateTo?: string;
  dateFormat?: string;
}

interface Props {
  varName: string;
  currentVar: ScriptVariable | null;
  dataFiles: DataFileOption[];
  onApply: (updated: ScriptVariable) => void;
  onClose: () => void;
}

// ─── Formatos de fecha ────────────────────────────────────────────────────────
const DATE_FORMATS = [
  { value: 'YYYY-MM-DD',   label: 'YYYY-MM-DD   (2025-01-15)' },
  { value: 'DD/MM/YYYY',   label: 'DD/MM/YYYY   (15/01/2025)' },
  { value: 'MM/DD/YYYY',   label: 'MM/DD/YYYY   (01/15/2025)' },
  { value: 'DD-MM-YYYY',   label: 'DD-MM-YYYY   (15-01-2025)' },
  { value: 'YYYY/MM/DD',   label: 'YYYY/MM/DD   (2025/01/15)' },
  { value: 'D MMM YYYY',   label: 'D MMM YYYY   (15 Jan 2025)' },
  { value: 'timestamp',    label: 'Unix timestamp (1705276800)' },
  { value: 'iso',          label: 'ISO 8601 (2025-01-15T00:00:00Z)' },
];

const RANDOM_OPTIONS: { fn: RandomFunction; icon: typeof User; label: string; description: string }[] = [
  { fn: 'firstName',  icon: User,      label: 'Nombre propio',    description: 'Carlos, Maria, Jose...' },
  { fn: 'lastName',   icon: User,      label: 'Apellido',         description: 'Gonzalez, Perez...' },
  { fn: 'email',      icon: AtSign,    label: 'Email aleatorio',  description: 'user_x7k2@test.com' },
  { fn: 'integer',    icon: Hash,      label: 'Numero entero',    description: 'Rango configurable' },
  { fn: 'alphaNum',   icon: AlignLeft, label: 'Alfanumerico',     description: '8 caracteres aleatorios' },
  { fn: 'dateRange',  icon: Calendar,  label: 'Fecha en rango',   description: 'Entre dos fechas' },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────
function randomConfigToBuiltin(config: RandomConfig): string {
  switch (config.fn) {
    case 'firstName':  return '$randomFirstName';
    case 'lastName':   return '$randomLastName';
    case 'email':      return '$randomEmail';
    case 'integer':    return `$randomInt(${config.min ?? 0},${config.max ?? 1000})`;
    case 'alphaNum':   return '$randomAlphaNum';
    case 'dateRange':
      return `$randomDate(${config.dateFrom ?? '2020-01-01'},${config.dateTo ?? '2025-12-31'},${config.dateFormat ?? 'YYYY-MM-DD'})`;
    default: return '$randomAlphaNum';
  }
}

// ─── Componente principal ─────────────────────────────────────────────────────
export default function VariableInlineEditor({
  varName, currentVar, dataFiles, onApply, onClose
}: Props) {
  const [sourceType, setSourceType] = useState<SourceType>(
    currentVar?.type === 'datafile' ? 'datafile'
    : currentVar?.type === 'builtin' || (currentVar?.value?.startsWith('$random') ?? false) ? 'random'
    : 'manual'
  );

  // Manual
  const [manualValue, setManualValue] = useState(
    currentVar?.type !== 'datafile' ? (currentVar?.value || '') : ''
  );

  // DataFile
  const [selectedFile, setSelectedFile] = useState(currentVar?.datafile_name || '');
  const [selectedColumn, setSelectedColumn] = useState(currentVar?.datafile_column || '');
  const [columns, setColumns] = useState<string[]>([]);
  const [preview, setPreview] = useState<string[]>([]);
  const [loadingCols, setLoadingCols] = useState(false);

  // Random
  const [randomFn, setRandomFn] = useState<RandomFunction>('firstName');
  const [randomConfig, setRandomConfig] = useState<RandomConfig>({
    fn: 'firstName',
    min: 1,
    max: 1000,
    dateFrom: '2020-01-01',
    dateTo: '2025-12-31',
    dateFormat: 'YYYY-MM-DD',
  });

  // Cargar columnas al seleccionar archivo
  useEffect(() => {
    if (!selectedFile) { setColumns([]); setPreview([]); return; }
    const df = dataFiles.find(f => f.filename === selectedFile);
    if (!df) return;
    if (df.columns && df.columns.length > 0) { setColumns(df.columns); return; }
    setLoadingCols(true);
    const csrfToken = document.cookie.match(/csrf_token=([^;]+)/)?.[1] || '';
    const apiBase = (import.meta as any).env?.VITE_API_BASE_URL || '/api/v1';
    fetch(`${apiBase}/data-files/${df.id}/columns`, {
      credentials: 'include',
      headers: { 'X-CSRF-Token': csrfToken },
    })
      .then(r => r.json())
      .then(d => setColumns(d.columns || []))
      .catch(() => setColumns([]))
      .finally(() => setLoadingCols(false));
  }, [selectedFile, dataFiles]);

  // Cargar preview al seleccionar columna
  useEffect(() => {
    if (!selectedFile || !selectedColumn) { setPreview([]); return; }
    const df = dataFiles.find(f => f.filename === selectedFile);
    if (!df) return;
    const csrfToken = document.cookie.match(/csrf_token=([^;]+)/)?.[1] || '';
    const apiBase = (import.meta as any).env?.VITE_API_BASE_URL || '/api/v1';
    fetch(`${apiBase}/data-files/${df.id}/preview?column=${encodeURIComponent(selectedColumn)}&rows=5`, {
      credentials: 'include',
      headers: { 'X-CSRF-Token': csrfToken },
    })
      .then(r => r.ok ? r.json() : { values: [] })
      .then(d => setPreview(d.values || []))
      .catch(() => setPreview([]));
  }, [selectedFile, selectedColumn, dataFiles]);

  const updateRandomConfig = (patch: Partial<RandomConfig>) => {
    setRandomConfig(prev => ({ ...prev, ...patch }));
  };

  const handleApply = () => {
    let updated: ScriptVariable;

    if (sourceType === 'manual') {
      updated = {
        name: varName,
        value: manualValue,
        type: 'manual',
        source_hint: 'Valor manual',
      };
    } else if (sourceType === 'datafile') {
      updated = {
        name: varName,
        value: '',
        type: 'datafile',
        source_hint: `${selectedFile} -> ${selectedColumn}`,
        datafile_name: selectedFile,
        datafile_column: selectedColumn,
      };
    } else {
      const builtinRef = randomConfigToBuiltin({ ...randomConfig, fn: randomFn });
      updated = {
        name: varName,
        value: builtinRef,
        type: 'auto',
        source_hint: `Funcion: ${builtinRef}`,
        default_value: JSON.stringify({ ...randomConfig, fn: randomFn }),
      };
    }
    onApply(updated);
    onClose();
  };

  const canApply =
    (sourceType === 'manual') ||
    (sourceType === 'datafile' && !!selectedFile && !!selectedColumn) ||
    (sourceType === 'random');

  return (
    <div className="flex flex-col bg-white overflow-hidden"
         style={{ minWidth: '280px', maxWidth: '340px', height: '100%' }}>

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-[#0a1628] text-white flex-shrink-0">
        <div>
          <p className="text-xs text-gray-400 mb-0.5">Editando variable</p>
          <code className="text-sm font-mono text-[#f5a623]">{`\${${varName}}`}</code>
        </div>
        <button onClick={onClose} className="p-1 hover:bg-white/20 rounded">
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Selector de tipo */}
      <div className="px-4 py-3 border-b border-gray-200 flex-shrink-0">
        <p className="text-sm font-medium text-gray-700 mb-2">Fuente del valor</p>
        <div className="space-y-1.5">
          {([
            { value: 'manual' as const,   icon: Type,     label: 'Valor fijo' },
            { value: 'datafile' as const, icon: Database,  label: 'Desde CSV/TXT' },
            { value: 'random' as const,   icon: Shuffle,   label: 'Funcion aleatoria' },
          ]).map(opt => (
            <label key={opt.value}
              className={`flex items-center gap-3 px-3 py-2 rounded-md cursor-pointer border transition-colors ${
                sourceType === opt.value
                  ? 'border-blue-400 bg-blue-50 text-blue-800'
                  : 'border-gray-200 hover:bg-gray-50 text-gray-700'
              }`}>
              <input
                type="radio"
                name="sourceType"
                value={opt.value}
                checked={sourceType === opt.value}
                onChange={() => setSourceType(opt.value)}
                className="text-blue-600"
              />
              <opt.icon className="w-4 h-4 flex-shrink-0" />
              <span className="text-sm font-medium">{opt.label}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Contenido segun tipo */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">

        {/* Manual */}
        {sourceType === 'manual' && (
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1.5">
              Valor fijo
            </label>
            <input
              type="text"
              value={manualValue}
              onChange={e => setManualValue(e.target.value)}
              placeholder={`Valor para ${varName}`}
              autoFocus
              className="w-full text-sm px-3 py-2 border border-gray-300 rounded-md
                         focus:outline-none focus:ring-2 focus:ring-blue-300"
            />
            <p className="text-xs text-gray-400 mt-1.5">
              Este valor se usara en cada ejecucion (sin variacion).
            </p>
          </div>
        )}

        {/* Data File */}
        {sourceType === 'datafile' && (
          <div className="space-y-3">
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1.5">
                Archivo CSV / TXT
              </label>
              {dataFiles.length === 0 ? (
                <div className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md p-3">
                  No hay archivos de datos cargados.<br/>
                  Usa el boton "Data Files" para subir un CSV o TXT.
                </div>
              ) : (
                <select
                  value={selectedFile}
                  onChange={e => { setSelectedFile(e.target.value); setSelectedColumn(''); }}
                  className="w-full text-sm px-3 py-2 border border-gray-300 rounded-md
                             bg-white focus:outline-none focus:ring-2 focus:ring-blue-300"
                >
                  <option value="">Seleccionar archivo...</option>
                  {dataFiles.map(f => (
                    <option key={f.id} value={f.filename}>{f.filename}</option>
                  ))}
                </select>
              )}
            </div>

            {selectedFile && (
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1.5">
                  Columna (variable)
                  {loadingCols && <span className="text-gray-400 ml-2 text-xs">cargando...</span>}
                </label>
                <select
                  value={selectedColumn}
                  onChange={e => setSelectedColumn(e.target.value)}
                  disabled={columns.length === 0}
                  className="w-full text-sm px-3 py-2 border border-gray-300 rounded-md
                             bg-white focus:outline-none focus:ring-2 focus:ring-blue-300
                             disabled:bg-gray-100"
                >
                  <option value="">Seleccionar columna...</option>
                  {columns.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
            )}

            {preview.length > 0 && (
              <div>
                <p className="text-sm font-medium text-gray-700 mb-1.5">
                  Preview (primeras {preview.length} filas)
                </p>
                <div className="border border-gray-200 rounded-md overflow-hidden">
                  {preview.map((val, i) => (
                    <div key={i} className={`px-3 py-1.5 text-sm font-mono text-gray-700 ${
                      i % 2 === 0 ? 'bg-white' : 'bg-gray-50'
                    }`}>
                      <span className="text-gray-400 mr-2 text-xs">fila {i + 1}</span>
                      {val}
                    </div>
                  ))}
                </div>
                <p className="text-xs text-gray-400 mt-1">
                  Cada VirtualUser tomara la fila correspondiente al ejecutar.
                </p>
              </div>
            )}
          </div>
        )}

        {/* Random */}
        {sourceType === 'random' && (
          <div className="space-y-3">
            <p className="text-sm font-medium text-gray-700">Funcion aleatoria</p>

            <div className="space-y-1.5">
              {RANDOM_OPTIONS.map(opt => (
                <label key={opt.fn}
                  className={`flex items-center gap-3 px-3 py-2 rounded-md cursor-pointer border transition-colors ${
                    randomFn === opt.fn
                      ? 'border-purple-400 bg-purple-50'
                      : 'border-gray-200 hover:bg-gray-50'
                  }`}>
                  <input
                    type="radio"
                    name="randomFn"
                    value={opt.fn}
                    checked={randomFn === opt.fn}
                    onChange={() => { setRandomFn(opt.fn); updateRandomConfig({ fn: opt.fn }); }}
                  />
                  <opt.icon className="w-4 h-4 text-purple-600 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-gray-800">{opt.label}</p>
                    <p className="text-xs text-gray-500">{opt.description}</p>
                  </div>
                </label>
              ))}
            </div>

            {/* Config: numero entero */}
            {randomFn === 'integer' && (
              <div className="pt-2 border-t border-gray-200 space-y-2">
                <p className="text-sm font-medium text-gray-700">Rango</p>
                <div className="flex gap-2 items-center">
                  <div className="flex-1">
                    <label className="text-xs text-gray-500 block mb-1">Minimo</label>
                    <input type="number" value={randomConfig.min ?? 0}
                      onChange={e => updateRandomConfig({ min: parseInt(e.target.value) || 0 })}
                      className="w-full text-sm px-2 py-1.5 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-purple-300" />
                  </div>
                  <span className="text-gray-400 mt-5">—</span>
                  <div className="flex-1">
                    <label className="text-xs text-gray-500 block mb-1">Maximo</label>
                    <input type="number" value={randomConfig.max ?? 1000}
                      onChange={e => updateRandomConfig({ max: parseInt(e.target.value) || 1000 })}
                      className="w-full text-sm px-2 py-1.5 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-purple-300" />
                  </div>
                </div>
              </div>
            )}

            {/* Config: rango de fechas */}
            {randomFn === 'dateRange' && (
              <div className="pt-2 border-t border-gray-200 space-y-3">
                <p className="text-sm font-medium text-gray-700">Rango de fechas</p>
                <div>
                  <label className="text-xs text-gray-500 block mb-1">Fecha inicio</label>
                  <input type="date" value={randomConfig.dateFrom ?? '2020-01-01'}
                    onChange={e => updateRandomConfig({ dateFrom: e.target.value })}
                    className="w-full text-sm px-2 py-1.5 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-purple-300" />
                </div>
                <div>
                  <label className="text-xs text-gray-500 block mb-1">Fecha fin</label>
                  <input type="date" value={randomConfig.dateTo ?? '2025-12-31'}
                    onChange={e => updateRandomConfig({ dateTo: e.target.value })}
                    className="w-full text-sm px-2 py-1.5 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-purple-300" />
                </div>
                <div>
                  <label className="text-xs text-gray-500 block mb-1">Formato de salida</label>
                  <select value={randomConfig.dateFormat ?? 'YYYY-MM-DD'}
                    onChange={e => updateRandomConfig({ dateFormat: e.target.value })}
                    className="w-full text-sm px-2 py-1.5 border border-gray-300 rounded bg-white focus:outline-none focus:ring-2 focus:ring-purple-300">
                    {DATE_FORMATS.map(f => (
                      <option key={f.value} value={f.value}>{f.label}</option>
                    ))}
                  </select>
                </div>
              </div>
            )}

            {/* Preview del built-in */}
            <div className="pt-2 border-t border-gray-200">
              <p className="text-xs text-gray-500 mb-1">Se usara la funcion:</p>
              <code className="text-xs bg-purple-100 text-purple-800 px-2 py-1 rounded block font-mono break-all">
                {`\${${randomConfigToBuiltin({ ...randomConfig, fn: randomFn })}}`}
              </code>
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="flex gap-2 px-4 py-3 border-t border-gray-200 flex-shrink-0 bg-gray-50">
        <button onClick={onClose}
          className="flex-1 text-sm px-3 py-2 border border-gray-300 rounded-md
                     text-gray-700 hover:bg-gray-100">
          Cancelar
        </button>
        <button onClick={handleApply} disabled={!canApply}
          className="flex-1 text-sm px-3 py-2 rounded-md bg-[#0a1628] text-white
                     hover:bg-[#1a2d4a] disabled:opacity-40 disabled:cursor-not-allowed font-medium">
          Aplicar
        </button>
      </div>
    </div>
  );
}
