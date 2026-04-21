// frontend/src/components/script-designer/RequestTable.tsx
import { ChevronUp, ChevronDown, X, Play, Loader2 } from 'lucide-react';
import { ScriptRequest } from '../../api/scriptDesignerApi';
import type { ScriptVariable } from './VariableManager';

const METHOD_COLORS: Record<string, string> = {
  GET:    'bg-green-100 text-green-700',
  POST:   'bg-blue-100 text-blue-700',
  PUT:    'bg-yellow-100 text-yellow-700',
  PATCH:  'bg-orange-100 text-orange-700',
  DELETE: 'bg-red-100 text-red-700',
};

interface Props {
  requests: ScriptRequest[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onReorder: (newOrder: ScriptRequest[]) => void;
  variables: ScriptVariable[];
  onRunSingle?: (requestId: string) => void;
  runningRequestId?: string | null;
}

export default function RequestTable({ requests, selectedId, onSelect, onDelete, onReorder, variables: _variables, onRunSingle, runningRequestId }: Props) {
  const moveUp = (index: number) => {
    if (index === 0) return;
    const newReqs = [...requests];
    [newReqs[index - 1], newReqs[index]] = [newReqs[index], newReqs[index - 1]];
    onReorder(newReqs);
  };

  const moveDown = (index: number) => {
    if (index === requests.length - 1) return;
    const newReqs = [...requests];
    [newReqs[index], newReqs[index + 1]] = [newReqs[index + 1], newReqs[index]];
    onReorder(newReqs);
  };

  if (requests.length === 0) {
    return (
      <div className="p-4 text-center text-gray-400 text-sm">
        No requests yet
      </div>
    );
  }

  return (
    <ul className="divide-y divide-gray-100">
      {requests.map((req, idx) => {
        const isRunning = runningRequestId === req.id;
        return (
          <li
            key={req.id}
            onClick={() => onSelect(req.id)}
            className={`px-3 py-3 cursor-pointer hover:bg-gray-50 group ${
              selectedId === req.id ? 'bg-blue-50 border-l-2 border-blue-500' : ''
            }`}
          >
            <div className="flex items-start gap-2">
              {/* Order controls */}
              <div className="flex flex-col items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity pt-0.5">
                <button
                  onClick={e => { e.stopPropagation(); moveUp(idx); }}
                  className="text-gray-400 hover:text-gray-600 disabled:opacity-30"
                  disabled={idx === 0}
                >
                  <ChevronUp className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={e => { e.stopPropagation(); moveDown(idx); }}
                  className="text-gray-400 hover:text-gray-600 disabled:opacity-30"
                  disabled={idx === requests.length - 1}
                >
                  <ChevronDown className="w-3.5 h-3.5" />
                </button>
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className={`text-xs font-mono font-bold px-1.5 py-0.5 rounded ${METHOD_COLORS[req.method] || 'bg-gray-100 text-gray-600'}`}>
                    {req.method}
                  </span>
                  <span className="text-sm text-gray-800 font-medium truncate">{req.name}</span>
                </div>
                <p className="text-sm text-gray-500 truncate">{req.url || '(no URL)'}</p>

                {/* Extractor variable badges */}
                {req.extractors.length > 0 && (
                  <div className="flex gap-1 flex-wrap mt-1">
                    {req.extractors.map((ext) => (
                      ext.variable_name && (
                        <span key={ext.variable_name}
                          className="text-xs bg-amber-100 text-amber-700 border border-amber-200 px-1.5 py-0.5 rounded-full font-mono">
                          &rarr; {`\${${ext.variable_name}}`}
                        </span>
                      )
                    ))}
                  </div>
                )}
              </div>

              <div className="flex items-center gap-1 flex-shrink-0 mt-0.5">
                {/* Run single button */}
                {onRunSingle && (
                  <button
                    onClick={e => { e.stopPropagation(); onRunSingle(req.id); }}
                    disabled={isRunning || !req.url}
                    title="Probar este request"
                    className="text-gray-400 hover:text-green-600 opacity-0 group-hover:opacity-100 transition-opacity disabled:opacity-30"
                  >
                    {isRunning
                      ? <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
                      : <Play className="w-4 h-4" />
                    }
                  </button>
                )}

                {/* Delete button */}
                <button
                  onClick={e => { e.stopPropagation(); onDelete(req.id); }}
                  className="text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
