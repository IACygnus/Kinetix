/**
 * ETAPA 3 (D36) — Aviso de estilo encima de una caja de análisis.
 *
 * Lo calcula el backend al leer (`detectar_estilo`, D35) y llega en
 * `style_warnings`. Aquí solo se pinta: una franja ámbar discreta con los
 * términos detectados. Desaparece sola en cuanto el texto se corrige y se
 * guarda, porque el aviso se recalcula en cada lectura y no se persiste.
 *
 * NO aparece en el PDF ni en el HTML exportados: este componente vive solo en
 * la pantalla de edición.
 */
import { AlertTriangle } from 'lucide-react';

export default function AvisoEstilo({ terminos }: { terminos?: string[] | null }) {
  if (!terminos || terminos.length === 0) return null;
  // Más de seis términos no caben en una línea y no aportan: se resumen.
  const visibles = terminos.slice(0, 6);
  const resto = terminos.length - visibles.length;
  return (
    <div
      className="mb-2 flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-1.5 text-xs text-amber-800"
      title="Detectado automáticamente al leer el informe. No sale en el PDF ni en el HTML."
    >
      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
      <span>
        <span className="font-semibold">Revisar estilo:</span>{' '}
        {visibles.join(', ')}
        {resto > 0 ? ` y ${resto} más` : ''}
      </span>
    </div>
  );
}
