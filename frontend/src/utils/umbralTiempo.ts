/**
 * Reporte 151 — la columna de umbral de la tabla «Veredicto por Transacción».
 *
 * Con criterios del Analista IA (`acceptance_criteria_json.analista`), la columna
 * muestra el criterio de TIEMPO realmente declarado para esa transacción, con su
 * valor y su medida («máximo ≤ 5 s»). Sin criterio de tiempo: «sin criterio».
 * Nunca 2.000 ms por defecto.
 *
 * Sin la marca del analista (Nuevo Reporte), devuelve null y Dashboard.tsx pinta
 * la columna como siempre.
 */

const MEDIDA: Record<string, string> = {
  promedio: 'promedio', mediana: 'mediana', p90: 'P90', p95: 'P95', p99: 'P99', max: 'máximo',
};
const OPERADOR: Record<string, string> = { '<': '<', '<=': '≤', '>': '>', '>=': '≥', '=': '=' };

interface CriterioLigero {
  tipo?: string;
  metrica?: string | null;
  metrica_supuesta?: boolean;
  operador?: string | null;
  valor?: number | null;
  unidad?: string | null;
  alcance?: { tipo?: string; transacciones?: string[]; transaccion?: string | null };
}

function aplica(c: CriterioLigero, txn: string): 'si' | 'global' | 'no' {
  const a = c.alcance || {};
  if (a.tipo === 'cada_transaccion') return 'si';
  if (a.tipo === 'global') return 'global';
  const txs = a.transacciones || (a.transaccion ? [a.transaccion] : []);
  return txs.includes(txn) ? 'si' : 'no';
}

function texto(c: CriterioLigero): string {
  const medida = MEDIDA[c.metrica || ''] || c.metrica || '?';
  const valor = c.valor != null ? c.valor.toLocaleString('es-CO', { maximumFractionDigits: 2 }) : '?';
  const supuesta = c.metrica_supuesta ? ' (medida supuesta)' : '';
  return `${medida} ${OPERADOR[c.operador || ''] || ''} ${valor} ${c.unidad || 'ms'}${supuesta}`.replace(/\s+/g, ' ');
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function umbralDeTiempo(criterios: any, txn: string): string | null {
  const an = criterios?.analista;
  if (!an || typeof an !== 'object') return null;   // el flujo de siempre
  const tiempos: CriterioLigero[] = (an.criterios || []).filter((c: CriterioLigero) => c.tipo === 'tiempo_respuesta');
  const propios = tiempos.filter((c) => aplica(c, txn) === 'si').map(texto);
  const globales = tiempos.filter((c) => aplica(c, txn) === 'global').map((c) => `${texto(c)} (toda la prueba)`);
  const todos = [...propios, ...globales];
  return todos.length ? todos.join(' · ') : 'sin criterio';
}
