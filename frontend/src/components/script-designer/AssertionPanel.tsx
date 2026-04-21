// frontend/src/components/script-designer/AssertionPanel.tsx
import { Plus, X } from 'lucide-react';

interface Assertion {
  type: string;
  value: string;
}

interface Props {
  assertions: Assertion[];
  onChange: (assertions: Assertion[]) => void;
}

export default function AssertionPanel({ assertions, onChange }: Props) {
  const add = () => onChange([...assertions, { type: 'status_code', value: '200' }]);
  const remove = (i: number) => onChange(assertions.filter((_, idx) => idx !== i));
  const update = (i: number, patch: Partial<Assertion>) =>
    onChange(assertions.map((a, idx) => idx === i ? { ...a, ...patch } : a));

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700">Assertions</h3>
        <button onClick={add} className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1">
          <Plus className="w-4 h-4" /> Add Assertion
        </button>
      </div>

      {assertions.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-8">
          No assertions defined. The request will always be marked as successful.
        </p>
      ) : (
        <div className="space-y-2">
          {assertions.map((a, i) => (
            <div key={i} className="flex gap-2 items-center bg-gray-50 border border-gray-200 rounded-lg p-3">
              <select
                value={a.type}
                onChange={e => update(i, { type: e.target.value })}
                className="text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="status_code">Status Code equals</option>
                <option value="response_contains">Response contains</option>
              </select>
              <input
                type="text"
                value={a.value}
                onChange={e => update(i, { value: e.target.value })}
                className="flex-1 text-sm font-mono border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder={a.type === 'status_code' ? '200' : 'expected text'}
              />
              <button onClick={() => remove(i)} className="text-gray-400 hover:text-red-500">
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
