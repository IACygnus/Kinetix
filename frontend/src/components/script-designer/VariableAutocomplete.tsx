// frontend/src/components/script-designer/VariableAutocomplete.tsx
import { useState, useRef, useCallback, KeyboardEvent } from 'react';
import type { ScriptVariable } from './VariableManager';
import { BUILTIN_VARIABLES } from './VariableManager';

interface Props {
  value: string;
  onChange: (value: string) => void;
  variables: ScriptVariable[];
  placeholder?: string;
  className?: string;
  multiline?: boolean;
  rows?: number;
}

export default function VariableAutocomplete({ value, onChange, variables, placeholder, className, multiline = false, rows = 3 }: Props) {
  const [showDropdown, setShowDropdown] = useState(false);
  const [dropdownItems, setDropdownItems] = useState<{ name: string; value: string; type: string }[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [triggerStart, setTriggerStart] = useState(-1);
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement>(null);

  const allVarNames = [
    ...variables.map(v => ({ name: v.name, value: v.value || '', type: v.type })),
    ...BUILTIN_VARIABLES.map(b => ({ name: b.name, value: 'auto-generado', type: 'builtin' })),
  ];

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const val = e.target.value;
    const cursor = e.target.selectionStart || 0;
    onChange(val);

    // Detectar si hay un ${ antes del cursor
    const before = val.slice(0, cursor);
    const triggerIdx = before.lastIndexOf('${');
    if (triggerIdx !== -1 && !before.slice(triggerIdx).includes('}')) {
      const partial = before.slice(triggerIdx + 2).toLowerCase();
      const filtered = allVarNames.filter(v => v.name.toLowerCase().startsWith(partial));
      if (filtered.length > 0) {
        setDropdownItems(filtered);
        setShowDropdown(true);
        setTriggerStart(triggerIdx);
        setActiveIndex(0);
        return;
      }
    }
    setShowDropdown(false);
  }, [onChange, allVarNames]);

  const selectItem = useCallback((item: { name: string }) => {
    const cursor = inputRef.current?.selectionStart || 0;
    const before = value.slice(0, triggerStart);
    const after = value.slice(cursor).replace(/^[^}]*}?/, '');
    const newVal = `${before}\${${item.name}}${after}`;
    onChange(newVal);
    setShowDropdown(false);
    setTimeout(() => {
      inputRef.current?.focus();
      const newCursor = (before + `\${${item.name}}`).length;
      inputRef.current?.setSelectionRange(newCursor, newCursor);
    }, 0);
  }, [value, triggerStart, onChange]);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (!showDropdown) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setActiveIndex(i => Math.min(i + 1, dropdownItems.length - 1)); }
    if (e.key === 'ArrowUp') { e.preventDefault(); setActiveIndex(i => Math.max(i - 1, 0)); }
    if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); selectItem(dropdownItems[activeIndex]); }
    if (e.key === 'Escape') setShowDropdown(false);
  }, [showDropdown, dropdownItems, activeIndex, selectItem]);

  const TYPE_COLORS: Record<string, string> = {
    manual: 'text-blue-600', imported: 'text-purple-600', auto: 'text-indigo-600',
    extractor: 'text-amber-600', datafile: 'text-green-600', builtin: 'text-gray-500'
  };

  const sharedClassName = className || 'w-full text-sm px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-300';

  return (
    <div className="relative">
      {multiline ? (
        <textarea
          ref={inputRef as React.RefObject<HTMLTextAreaElement>}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onBlur={() => setTimeout(() => setShowDropdown(false), 150)}
          placeholder={placeholder}
          className={sharedClassName}
          rows={rows}
        />
      ) : (
        <input
          ref={inputRef as React.RefObject<HTMLInputElement>}
          type="text"
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onBlur={() => setTimeout(() => setShowDropdown(false), 150)}
          placeholder={placeholder}
          className={sharedClassName}
        />
      )}
      {showDropdown && dropdownItems.length > 0 && (
        <div className="absolute z-50 left-0 top-full mt-1 w-72 bg-white border border-gray-200 rounded-md shadow-lg max-h-52 overflow-y-auto">
          {dropdownItems.map((item, i) => (
            <div
              key={item.name}
              className={`px-3 py-2 cursor-pointer flex items-center justify-between ${i === activeIndex ? 'bg-blue-50' : 'hover:bg-gray-50'}`}
              onMouseDown={() => selectItem(item)}
            >
              <code className="text-sm font-mono text-gray-800">{`\${${item.name}}`}</code>
              <div className="flex items-center gap-2 ml-2">
                {item.value && item.type !== 'builtin' && (
                  <span className="text-xs text-gray-400 truncate max-w-[80px]">{item.value}</span>
                )}
                <span className={`text-xs ${TYPE_COLORS[item.type] || 'text-gray-500'}`}>
                  {item.type}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
