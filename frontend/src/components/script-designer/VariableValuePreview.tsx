// frontend/src/components/script-designer/VariableValuePreview.tsx
/**
 * Preview panel showing what value will be sent for a variable at runtime.
 * Appears as the rightmost panel when editing a variable that has a value.
 */
import { Eye, FileText, Shuffle, Type, AlertCircle } from 'lucide-react';
import type { ScriptVariable } from './VariableManager';

const EXAMPLES: Record<string, string[]> = {
  '$randomFirstName': ['Carlos', 'Maria', 'Jose', 'Ana', 'Luis', 'Laura'],
  '$randomLastName':  ['Gonzalez', 'Perez', 'Rodriguez', 'Lopez', 'Martinez'],
  '$randomEmail':     ['user_k3m9@test.com', 'user_x7b2@test.com', 'user_p1q8@test.com'],
  '$randomAlphaNum':  ['k3m9x2b1', 'p7q2r4s8', 'a1b2c3d4'],
  '$randomInt':       ['742', '103', '867', '245', '591'],
  '$guid':            ['a1b2c3d4-e5f6-7890-abcd-ef1234567890'],
  '$timestamp':       [String(Date.now()), String(Date.now() - 1000)],
  '$randomIP':        ['192.168.1.45', '10.0.0.127', '172.16.0.89'],
};

function getExamples(value: string): { examples: string[]; label: string } {
  for (const [key, examples] of Object.entries(EXAMPLES)) {
    if (value.includes(key.replace('$', ''))) {
      return { examples, label: key };
    }
  }
  const intMatch = value.match(/\$randomInt\((\d+),(\d+)\)/);
  if (intMatch) {
    const lo = parseInt(intMatch[1]);
    const hi = parseInt(intMatch[2]);
    const samples = Array.from({ length: 4 }, () =>
      String(Math.floor(Math.random() * (hi - lo + 1)) + lo)
    );
    return { examples: samples, label: `$randomInt(${lo},${hi})` };
  }
  const dateMatch = value.match(/\$randomDate\(([^,]+),([^,]+),([^)]+)\)/);
  if (dateMatch) {
    return {
      examples: ['2023-04-15', '2021-11-28', '2024-07-03'],
      label: `$randomDate(${dateMatch[3]})`,
    };
  }
  return { examples: [value], label: 'Valor fijo' };
}

interface Props {
  varName: string;
  variable: ScriptVariable | null;
}

export default function VariableValuePreview({ varName, variable }: Props) {
  if (!variable) {
    return (
      <div className="flex flex-col h-full bg-gray-50 p-3">
        <div className="flex items-center gap-2 mb-2">
          <AlertCircle className="w-4 h-4 text-amber-500" />
          <p className="text-sm font-medium text-gray-700">Sin configurar</p>
        </div>
        <p className="text-xs text-gray-500">
          Esta variable no tiene valor asignado aun.
          Usa el panel de la izquierda para configurarla.
        </p>
      </div>
    );
  }

  const { value, type, datafile_name, datafile_column } = variable;

  const typeConfig = {
    manual:    { icon: Type,     label: 'Valor fijo',          color: 'text-blue-600' },
    imported:  { icon: Type,     label: 'Valor importado',     color: 'text-purple-600' },
    auto:      { icon: Shuffle,  label: 'Funcion aleatoria',   color: 'text-indigo-600' },
    extractor: { icon: Eye,      label: 'Extraido en runtime', color: 'text-amber-600' },
    datafile:  { icon: FileText, label: 'Desde archivo',       color: 'text-green-600' },
    builtin:   { icon: Shuffle,  label: 'Sistema',             color: 'text-gray-600' },
  }[type] || { icon: Type, label: type, color: 'text-gray-600' };

  const Icon = typeConfig.icon;

  return (
    <div className="flex flex-col h-full bg-gray-50 overflow-hidden">
      {/* Header */}
      <div className="px-3 py-2.5 bg-gray-800 text-white flex-shrink-0">
        <div className="flex items-center gap-1.5 mb-0.5">
          <Eye className="w-3.5 h-3.5 text-gray-400" />
          <p className="text-xs text-gray-400">Preview del valor</p>
        </div>
        <code className="text-sm font-mono text-[#f5a623]">{`\${${varName}}`}</code>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
        {/* Type badge */}
        <div className="flex items-center gap-2">
          <Icon className={`w-4 h-4 ${typeConfig.color}`} />
          <span className={`text-sm font-medium ${typeConfig.color}`}>{typeConfig.label}</span>
        </div>

        {/* Manual / imported: fixed value */}
        {(type === 'manual' || type === 'imported') && value && (
          <div className="space-y-1.5">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Valor que se enviara
            </p>
            <div className="bg-white border border-gray-200 rounded p-2">
              <code className="text-sm text-gray-800 break-all">{value}</code>
            </div>
            <p className="text-xs text-gray-400">Este valor es igual en cada ejecucion.</p>
          </div>
        )}

        {/* Auto / builtin: random examples */}
        {(type === 'auto' || type === 'builtin') && value && (
          <div className="space-y-1.5">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Ejemplos de valores generados
            </p>
            <div className="space-y-1">
              {getExamples(value).examples.slice(0, 5).map((ex, i) => (
                <div key={i} className="flex items-center gap-2 bg-white border border-gray-200 rounded px-2 py-1.5">
                  <span className="text-xs text-gray-400 w-4 text-right">{i + 1}</span>
                  <code className="text-sm text-indigo-700">{ex}</code>
                </div>
              ))}
            </div>
            <p className="text-xs text-gray-400">
              Cada usuario virtual recibira un valor diferente.
            </p>
            <div className="bg-indigo-50 border border-indigo-200 rounded p-2">
              <p className="text-xs text-indigo-700">
                Funcion: <code className="font-mono">{value}</code>
              </p>
            </div>
          </div>
        )}

        {/* Extractor */}
        {type === 'extractor' && (
          <div className="space-y-1.5">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Extraido en runtime
            </p>
            <div className="bg-amber-50 border border-amber-200 rounded p-2">
              <p className="text-xs text-amber-700">
                Esta variable se captura de la respuesta de un request anterior
                usando la expresion regular definida en el tab "Extractors".
              </p>
            </div>
            {value && (
              <div>
                <p className="text-xs text-gray-500 mb-1">Valor default (si falla extraccion):</p>
                <code className="text-sm bg-white border border-gray-200 rounded px-2 py-1 block">{value}</code>
              </div>
            )}
          </div>
        )}

        {/* Data file */}
        {type === 'datafile' && (
          <div className="space-y-1.5">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Desde archivo
            </p>
            <div className="bg-white border border-gray-200 rounded p-2 space-y-1">
              <div className="flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-green-600" />
                <span className="text-sm font-medium text-gray-700">{datafile_name}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-gray-400">Columna:</span>
                <code className="text-xs bg-green-50 text-green-700 px-1.5 py-0.5 rounded">{datafile_column}</code>
              </div>
            </div>
            <p className="text-xs text-gray-400">
              Cada usuario virtual tomara la fila correspondiente del archivo.
            </p>
          </div>
        )}

        {/* No value configured */}
        {!value && type !== 'datafile' && type !== 'extractor' && (
          <div className="bg-amber-50 border border-amber-200 rounded p-2">
            <p className="text-xs text-amber-700">
              Esta variable no tiene valor asignado. Usa el panel de edicion para configurarla.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
