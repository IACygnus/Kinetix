/**
 * SelectorContenidoSeccion — qué entra de UNA sección del informe integrado
 * (ETAPA R1, R-D5).
 *
 * Sección de carga o estrés → qué transacciones llevan su informe propio.
 * Sección de monitoreo o evidencias → qué capturas entran.
 *
 * Mismo convenio que el selector del informe individual (`seleccion.py`,
 * `ExportScopeDialog`): `null` = TODAS —lo de siempre, y lo que tiene un
 * integrado anterior a R1—; una lista = solo esas; `[]` = ninguna. Marcar todas
 * vuelve a `null`, así que lo que se añada después a la ejecución entra solo.
 *
 * No reutiliza `ExportScopeDialog`: ese diálogo está atado a UNA ejecución y a un
 * formato de exportación. De él se reutiliza el origen de la lista de
 * transacciones —el mismo que usa la pantalla para decidir qué bloques pinta— y
 * el significado de `null` / `[]`.
 *
 * Regla 16: todos los hooks antes de cualquier return.
 */
import { useEffect, useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import api from '../../services/api';

export type TipoSeccion = 'load_test' | 'stress_test' | 'monitoring' | 'evidence';
type Opcion = { id: string; nombre: string };

export default function SelectorContenidoSeccion({ executionId, tipo, seleccion, onCambiar }: {
  executionId: string;
  tipo: TipoSeccion;
  seleccion: string[] | null | undefined;
  onCambiar: (nueva: string[] | null) => void;
}) {
  const [opciones, setOpciones] = useState<Opcion[] | null>(null);
  const [abierto, setAbierto] = useState(false);
  const esInforme = tipo === 'load_test' || tipo === 'stress_test';

  useEffect(() => {
    let vivo = true;
    const pedir = esInforme
      ? api.get(`/executions/${executionId}/transaction-analyses`).then((r) => {
          // Las mismas que pinta la pantalla: marcadas como críticas + con informe.
          const criticas: string[] = (r.data?.transaction_analyses || []).map((t: any) => t.label);
          const conInforme: string[] = r.data?.report_labels || [];
          return Array.from(new Set([...criticas, ...conInforme])).map((l) => ({ id: l, nombre: l }));
        })
      : api.get(`/executions/${executionId}/image-analyses?attachment_type=${tipo}`).then((r) =>
          (r.data || []).map((a: any) => ({ id: String(a.id), nombre: a.title || a.filename })));
    pedir.then((o) => { if (vivo) setOpciones(o); }).catch(() => { if (vivo) setOpciones([]); });
    return () => { vivo = false; };
  }, [executionId, tipo, esInforme]);

  if (!opciones || opciones.length === 0) return null;

  const cosa = esInforme ? 'transacciones' : 'capturas';
  const marcadas = seleccion == null ? new Set(opciones.map((o) => o.id)) : new Set(seleccion);
  const n = opciones.filter((o) => marcadas.has(o.id)).length;
  const resumen = n === opciones.length ? `todas las ${cosa} (${n})`
    : n === 0 ? (esInforme ? 'solo el informe general' : `ninguna captura`)
    : `${n} de ${opciones.length} ${cosa}`;

  const fijar = (s: Set<string>) => {
    const lista = opciones.filter((o) => s.has(o.id)).map((o) => o.id);
    onCambiar(lista.length === opciones.length ? null : lista);
  };
  const alternar = (id: string) => {
    const s = new Set(marcadas);
    if (s.has(id)) s.delete(id); else s.add(id);
    fijar(s);
  };

  return (
    <div className="mt-2" data-testid={`selector-${tipo}-${executionId}`}>
      <button type="button" onClick={() => setAbierto(!abierto)}
        className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900"
        data-testid="selector-resumen">
        {abierto ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        Incluye: <span className="font-semibold">{resumen}</span>
      </button>
      {abierto && (
        <div className="mt-2 ml-5 pl-3 border-l-2 border-gray-200 space-y-1">
          <div className="flex gap-3 text-xs mb-1">
            <button type="button" className="text-blue-700 hover:underline"
              onClick={() => fijar(new Set(opciones.map((o) => o.id)))}>Todas</button>
            <button type="button" className="text-blue-700 hover:underline"
              onClick={() => fijar(new Set())}>Ninguna</button>
          </div>
          {opciones.map((o) => (
            <label key={o.id} className="flex items-center gap-2 py-0.5 cursor-pointer text-sm text-gray-700">
              <input type="checkbox" className="w-4 h-4 accent-[#f5a623]" data-opcion={o.nombre}
                checked={marcadas.has(o.id)} onChange={() => alternar(o.id)} />
              {o.nombre}
            </label>
          ))}
          {n === 0 && !esInforme && (
            <p className="text-xs text-amber-700">Sin ninguna captura, esta sección no aparece en el informe.</p>
          )}
        </div>
      )}
    </div>
  );
}
