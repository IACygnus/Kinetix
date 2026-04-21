// frontend/src/components/script-designer/ExecutionHistoryPanel.tsx
/**
 * Panel inferior de historial de ejecuciones.
 *
 * - Acumula hasta MAX_ENTRIES=50 ejecuciones (FIFO: al llegar a 51 borra la primera)
 * - Cada entrada puede ser tipo "single" (individual) o "smoke" (smoke test)
 * - Las entradas tipo "smoke" tienen sub-items (uno por request)
 * - Click en cualquier entrada o sub-item -> JMeterResultDetail en panel derecho
 * - Boton Limpiar borra todo el historial
 * - El panel es redimensionable verticalmente (drag del borde superior)
 * - Se puede colapsar/expandir
 */
import { useState, useRef, useCallback, useEffect } from 'react';
import {
  ChevronDown, ChevronUp, ChevronRight, Trash2,
  CheckCircle, XCircle, Clock, Zap, FlaskConical
} from 'lucide-react';
import JMeterResultDetail, { RequestDetail } from './JMeterResultDetail';

// --- Tipos ---

export type ExecutionEntryType = 'single' | 'smoke';

export interface ExecutionEntry {
  id: string;
  type: ExecutionEntryType;
  timestamp: number;
  duration_ms: number;
  success: boolean;
  // Para 'single': un solo result
  result?: RequestDetail;
  // Para 'smoke': multiples results
  results?: RequestDetail[];
  total?: number;
  passed?: number;
  failed?: number;
}

const MAX_ENTRIES = 50;

// --- Hook para gestionar el historial ---
export function useExecutionHistory() {
  const [entries, setEntries] = useState<ExecutionEntry[]>([]);

  const addEntry = useCallback((entry: Omit<ExecutionEntry, 'id' | 'timestamp'>) => {
    const newEntry: ExecutionEntry = {
      ...entry,
      id: crypto.randomUUID(),
      timestamp: Date.now(),
    };
    setEntries(prev => {
      const updated = [newEntry, ...prev];
      return updated.length > MAX_ENTRIES ? updated.slice(0, MAX_ENTRIES) : updated;
    });
  }, []);

  const clearHistory = useCallback(() => setEntries([]), []);

  return { entries, addEntry, clearHistory };
}

// --- Componente principal ---
interface Props {
  entries: ExecutionEntry[];
  onClear: () => void;
}

export default function ExecutionHistoryPanel({ entries, onClear }: Props) {
  const [collapsed, setCollapsed]       = useState(true);
  const [panelHeight, setPanelHeight]   = useState(280);
  const [selectedKey, setSelectedKey]   = useState<string | null>(null);
  const [selectedResult, setSelectedResult] = useState<RequestDetail | null>(null);
  const [expandedIds, setExpandedIds]   = useState<Set<string>>(new Set());
  const dragRef = useRef<{ startY: number; startH: number } | null>(null);

  // Auto-expand y auto-select cuando llega una nueva entrada
  useEffect(() => {
    if (entries.length > 0) {
      setCollapsed(false);
      const newest = entries[0];
      if (newest.type === 'smoke' && newest.results?.[0]) {
        setExpandedIds(prev => new Set([...prev, newest.id]));
        setSelectedKey(`${newest.id}-0`);
        setSelectedResult(newest.results[0]);
      } else if (newest.type === 'single' && newest.result) {
        setSelectedKey(newest.id);
        setSelectedResult(newest.result);
      }
    }
  }, [entries.length]); // eslint-disable-line react-hooks/exhaustive-deps

  // -- Resize drag --
  const onDragStart = (e: React.MouseEvent) => {
    dragRef.current = { startY: e.clientY, startH: panelHeight };
    const onMove = (ev: MouseEvent) => {
      if (!dragRef.current) return;
      const delta = dragRef.current.startY - ev.clientY;
      setPanelHeight(Math.max(160, Math.min(600, dragRef.current.startH + delta)));
    };
    const onUp = () => {
      dragRef.current = null;
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  };

  const toggleExpand = (id: string) => {
    setExpandedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const selectSingle = (entry: ExecutionEntry) => {
    setSelectedKey(entry.id);
    setSelectedResult(entry.result || null);
  };

  const selectSubItem = (entryId: string, idx: number, result: RequestDetail) => {
    setSelectedKey(`${entryId}-${idx}`);
    setSelectedResult(result);
  };

  const formatTime = (ts: number) => {
    const d = new Date(ts);
    return d.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  // --- Render ---
  return (
    <div
      className="flex flex-col border-t border-gray-300 bg-white flex-shrink-0"
      style={{ height: collapsed ? 36 : panelHeight }}
    >
      {/* Drag handle */}
      {!collapsed && (
        <div
          className="h-1.5 bg-gray-200 hover:bg-blue-400 cursor-row-resize flex-shrink-0 transition-colors"
          onMouseDown={onDragStart}
        />
      )}

      {/* Header del panel */}
      <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 border-b border-gray-200 flex-shrink-0">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center gap-1.5 text-sm font-medium text-gray-700 hover:text-gray-900"
        >
          {collapsed
            ? <ChevronUp   className="w-4 h-4" />
            : <ChevronDown className="w-4 h-4" />
          }
          <span>Historial de ejecuciones</span>
          {entries.length > 0 && (
            <span className="bg-gray-200 text-gray-600 text-xs px-1.5 py-0.5 rounded-full font-medium">
              {entries.length}/{MAX_ENTRIES}
            </span>
          )}
        </button>
        <div className="ml-auto flex items-center gap-2">
          {entries.length > 0 && (
            <button
              onClick={onClear}
              className="flex items-center gap-1 text-xs text-red-500 hover:text-red-700 px-2 py-1 hover:bg-red-50 rounded"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Limpiar
            </button>
          )}
        </div>
      </div>

      {/* Contenido del panel */}
      {!collapsed && (
        <div className="flex flex-1 overflow-hidden">

          {/* Panel izquierdo - arbol */}
          <div className="w-64 flex-shrink-0 border-r border-gray-200 overflow-y-auto bg-gray-50">
            {entries.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full py-6 text-gray-400">
                <FlaskConical className="w-8 h-8 mb-2 opacity-50" />
                <p className="text-sm text-center">
                  Sin ejecuciones aun.<br />
                  Usa "Probar" o "Smoke"
                </p>
              </div>
            ) : (
              entries.map((entry) => {
                const isExpanded = expandedIds.has(entry.id);
                const isSmoke    = entry.type === 'smoke';

                return (
                  <div key={entry.id}>
                    {/* Entrada principal */}
                    <div
                      className={`flex items-center gap-1.5 px-2 py-1.5 cursor-pointer text-sm transition-colors ${
                        selectedKey === entry.id
                          ? 'bg-blue-50 border-r-2 border-blue-500'
                          : 'hover:bg-gray-100'
                      }`}
                      onClick={() => {
                        if (isSmoke) {
                          toggleExpand(entry.id);
                          if (entry.results?.[0]) {
                            selectSubItem(entry.id, 0, entry.results[0]);
                          }
                        } else {
                          selectSingle(entry);
                        }
                      }}
                    >
                      {/* Icono expand para smoke */}
                      {isSmoke ? (
                        <button
                          className="flex-shrink-0 text-gray-400 hover:text-gray-600"
                          onClick={e => { e.stopPropagation(); toggleExpand(entry.id); }}
                        >
                          {isExpanded
                            ? <ChevronDown  className="w-3.5 h-3.5" />
                            : <ChevronRight className="w-3.5 h-3.5" />
                          }
                        </button>
                      ) : (
                        <span className="w-3.5 flex-shrink-0" />
                      )}

                      {/* Estado */}
                      {entry.success
                        ? <CheckCircle className="w-3.5 h-3.5 text-green-500 flex-shrink-0" />
                        : <XCircle     className="w-3.5 h-3.5 text-red-500   flex-shrink-0" />
                      }

                      {/* Label */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1">
                          {isSmoke
                            ? <span className="text-purple-600 font-medium">Smoke</span>
                            : <span className="text-blue-600 font-medium">
                                {entry.result?.name || 'Individual'}
                              </span>
                          }
                        </div>
                        <div className="flex items-center gap-1 text-gray-400">
                          <Clock className="w-3 h-3" />
                          <span>{entry.duration_ms}ms</span>
                          <span className="mx-0.5">&middot;</span>
                          <span>{formatTime(entry.timestamp)}</span>
                        </div>
                      </div>

                      {/* Para smoke: passed/failed */}
                      {isSmoke && (
                        <div className="flex-shrink-0 flex items-center gap-1">
                          <span className="text-green-600 font-bold">{entry.passed}</span>
                          <span className="text-gray-400">/</span>
                          <span className="text-red-600 font-bold">{entry.failed}</span>
                        </div>
                      )}

                      {/* Para individual: codigo */}
                      {!isSmoke && entry.result?.status_code && (
                        <span className={`font-bold flex-shrink-0 ${
                          Number(entry.result.status_code) < 400 ? 'text-green-600' : 'text-red-600'
                        }`}>
                          {entry.result.status_code}
                        </span>
                      )}
                    </div>

                    {/* Sub-items del smoke expandido */}
                    {isSmoke && isExpanded && (entry.results || []).map((r, idx) => (
                      <div
                        key={`${entry.id}-${idx}`}
                        className={`flex items-center gap-1.5 pl-8 pr-2 py-1 cursor-pointer text-sm transition-colors ${
                          selectedKey === `${entry.id}-${idx}`
                            ? 'bg-blue-50 border-r-2 border-blue-500'
                            : 'hover:bg-gray-100'
                        }`}
                        onClick={() => selectSubItem(entry.id, idx, r)}
                      >
                        {r.success
                          ? <CheckCircle className="w-3 h-3 text-green-500 flex-shrink-0" />
                          : <XCircle     className="w-3 h-3 text-red-500   flex-shrink-0" />
                        }
                        <span className="flex-1 truncate text-gray-700">
                          {r.name || `Request ${idx+1}`}
                        </span>
                        {r.status_code && (
                          <span className={`font-bold flex-shrink-0 ${
                            Number(r.status_code) < 400 ? 'text-green-600' : 'text-red-600'
                          }`}>
                            {r.status_code}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                );
              })
            )}
          </div>

          {/* Panel derecho - JMeter detail */}
          <div className="flex-1 overflow-hidden">
            {selectedResult ? (
              <JMeterResultDetail result={selectedResult} />
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-gray-400">
                <Zap className="w-8 h-8 mb-2 opacity-40" />
                <p className="text-sm text-center">
                  Selecciona una ejecucion del arbol<br />
                  para ver el detalle
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
