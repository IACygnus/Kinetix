/**
 * ExportScopeDialog — "¿qué incluyo en la exportación?" (ETAPA 6, D50).
 *
 * v1.2 §6: al pulsar Exportar PDF o Exportar HTML, el sistema pregunta si quiere
 * solo el informe general o el general más las transacciones que se marquen.
 * Aplica a las DOS salidas individuales; el informe integrado queda fuera (§6).
 *
 * Vive aparte de Dashboard.tsx (protegido), que solo lo monta: el protegido no
 * gana ni el estado del diálogo ni la petición de la lista de transacciones.
 *
 * Regla 16: todos los hooks antes de cualquier return.
 */
import { useEffect, useState } from 'react';
import { X, FileDown, FileCode, Loader2 } from 'lucide-react';
import api from '../../services/api';

export type FormatoExport = 'pdf' | 'html';

/** `null` = todas las transacciones (lo de siempre); `[]` = solo el general. */
export type SeleccionExport = string[] | null;

export default function ExportScopeDialog({ executionId, formato, onCancelar, onExportar }: {
  executionId: string;
  /** El formato que se pidió; `null` mantiene el diálogo cerrado. */
  formato: FormatoExport | null;
  onCancelar: () => void;
  onExportar: (seleccion: SeleccionExport) => void;
}) {
  const [labels, setLabels] = useState<string[] | null>(null);
  const [soloGeneral, setSoloGeneral] = useState(false);
  const [marcadas, setMarcadas] = useState<Set<string>>(new Set());
  const [error, setError] = useState('');

  // Las transacciones que se pueden incluir son las que TIENEN informe: es el
  // mismo origen que usa la pantalla para decidir qué bloques pinta
  // (`report_labels`), así que el diálogo no puede ofrecer algo que el PDF no
  // sepa dibujar. Se piden al abrir, no antes: quien nunca exporta no paga la
  // petición.
  useEffect(() => {
    if (!formato) return;
    let vivo = true;
    setError('');
    api.get(`/executions/${executionId}/transaction-analyses`)
      .then((r) => {
        if (!vivo) return;
        const conInforme: string[] = r.data?.report_labels || [];
        setLabels(conInforme);
        setMarcadas(new Set(conInforme));   // todas marcadas por defecto (D50)
        setSoloGeneral(false);
      })
      .catch(() => {
        if (!vivo) return;
        // Sin la lista no se puede elegir, pero sí exportar: se cae al
        // comportamiento de siempre en vez de bloquear la exportación.
        setLabels([]);
        setError('No se pudo leer la lista de transacciones; se exportará el informe completo.');
      });
    return () => { vivo = false; };
  }, [executionId, formato]);

  // Sin transacciones con informe no hay nada que preguntar: se exporta como
  // siempre. Va en un efecto, no en el render, para no llamar a un setState del
  // padre durante el pintado.
  useEffect(() => {
    if (formato && labels && labels.length === 0 && !error) onExportar(null);
  }, [formato, labels, error, onExportar]);

  if (!formato) return null;

  const nombre = formato === 'pdf' ? 'PDF' : 'HTML';
  const Icono = formato === 'pdf' ? FileDown : FileCode;

  if (labels === null) {
    return (
      <Marco onCancelar={onCancelar} titulo={`Exportar ${nombre}`}>
        <div className="flex items-center gap-3 text-gray-500 py-6">
          <Loader2 className="w-5 h-5 animate-spin" /> Leyendo las transacciones del informe…
        </div>
      </Marco>
    );
  }

  if (labels.length === 0) {
    return (
      <Marco onCancelar={onCancelar} titulo={`Exportar ${nombre}`}>
        <p className="text-gray-600 py-4">{error || 'Este informe no tiene transacciones con análisis.'}</p>
        <Botones nombre={nombre} Icono={Icono} onCancelar={onCancelar} onExportar={() => onExportar(null)} />
      </Marco>
    );
  }

  const alternar = (l: string) => {
    const s = new Set(marcadas);
    if (s.has(l)) s.delete(l); else s.add(l);
    setMarcadas(s);
  };

  const exportar = () => {
    // "Solo el general" es la lista vacía, no `null`: `null` significaría
    // "todas" y es justo lo contrario de lo que se pidió.
    onExportar(soloGeneral ? [] : labels.filter((l) => marcadas.has(l)));
  };

  const ningunaMarcada = !soloGeneral && marcadas.size === 0;

  return (
    <Marco onCancelar={onCancelar} titulo={`Exportar ${nombre} — ¿qué incluyo?`}>
      <div className="space-y-3 py-2">
        <label className="flex items-start gap-3 p-4 rounded-xl border-2 cursor-pointer transition-colors"
          style={{ borderColor: soloGeneral ? '#f5a623' : '#e5e7eb' }}>
          <input type="radio" name="alcance-export" className="mt-1.5 w-5 h-5 accent-[#f5a623]"
            data-testid="opcion-solo-general"
            checked={soloGeneral} onChange={() => setSoloGeneral(true)} />
          <span>
            <span className="block text-lg font-bold text-gray-800">Solo informe general</span>
            <span className="block text-base text-gray-500">Portada, tabla resumen, gráficas generales y conclusiones.</span>
          </span>
        </label>

        <label className="flex items-start gap-3 p-4 rounded-xl border-2 cursor-pointer transition-colors"
          style={{ borderColor: !soloGeneral ? '#f5a623' : '#e5e7eb' }}>
          <input type="radio" name="alcance-export" className="mt-1.5 w-5 h-5 accent-[#f5a623]"
            data-testid="opcion-general-y-transacciones"
            checked={!soloGeneral} onChange={() => setSoloGeneral(false)} />
          <span>
            <span className="block text-lg font-bold text-gray-800">General y transacciones</span>
            <span className="block text-base text-gray-500">Se añade un informe por cada transacción marcada.</span>
          </span>
        </label>

        <div className={`ml-8 pl-4 border-l-2 border-gray-200 space-y-1 transition-opacity ${soloGeneral ? 'opacity-40 pointer-events-none' : ''}`}
          data-testid="lista-transacciones">
          {labels.map((l) => (
            <label key={l} className="flex items-center gap-3 py-1.5 cursor-pointer">
              <input type="checkbox" className="w-5 h-5 accent-[#f5a623]"
                data-tx={l}
                checked={marcadas.has(l)} disabled={soloGeneral}
                onChange={() => alternar(l)} />
              <span className="text-base text-gray-700">{l}</span>
            </label>
          ))}
        </div>

        {ningunaMarcada && (
          <p className="text-base text-amber-700">
            Sin ninguna transacción marcada se exporta solo el informe general.
          </p>
        )}
      </div>
      <Botones nombre={nombre} Icono={Icono} onCancelar={onCancelar} onExportar={exportar} />
    </Marco>
  );
}

function Marco({ titulo, onCancelar, children }: { titulo: string; onCancelar: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      data-testid="dialogo-export"
      onClick={onCancelar}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-xl max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h3 className="text-2xl font-bold text-gray-800">{titulo}</h3>
          <button onClick={onCancelar} aria-label="Cerrar"
            className="p-1.5 rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-600">
            <X className="w-6 h-6" />
          </button>
        </div>
        <div className="px-6 pb-6">{children}</div>
      </div>
    </div>
  );
}

function Botones({ nombre, Icono, onCancelar, onExportar }: {
  nombre: string;
  Icono: React.ComponentType<{ className?: string }>;
  onCancelar: () => void;
  onExportar: () => void;
}) {
  return (
    <div className="flex justify-end gap-3 pt-5 mt-2 border-t border-gray-200">
      <button onClick={onCancelar} data-testid="export-cancelar"
        className="px-6 py-3 text-lg font-semibold rounded-xl border border-gray-300 text-gray-600 hover:bg-gray-50">
        Cancelar
      </button>
      <button onClick={onExportar} data-testid="export-confirmar"
        className="flex items-center gap-2 px-6 py-3 text-lg font-bold rounded-xl bg-sqa-gold text-sqa-navy hover:bg-sqa-gold-light">
        <Icono className="w-6 h-6" /> Exportar {nombre}
      </button>
    </div>
  );
}
