/**
 * SummaryTable — la tabla "Reporte Resumen", parametrizada por ALCANCE (ETAPA 2, D15/D21).
 *
 * Extraida VERBATIM de Dashboard.tsx. El informe general la pinta con todas las
 * transacciones y su fila TOTAL; el bloque de una transaccion la pinta con UNA
 * fila y sin TOTAL. Es el mismo componente y las mismas columnas: eso es lo que
 * hace cierta la frase de v1.2 §1, "el informe por transaccion es el informe
 * general, filtrado".
 *
 * `rows` son las filas de `by_label` de /charts, tal cual llegan del backend.
 */

export interface SummaryRow {
  label: string;
  count: number;
  success_count?: number;
  error_count?: number;
  error_rate?: number;
  avg_time: number;
  p90?: number;
  p95?: number;
  p99?: number;
  min_time: number;
  max_time: number;
  throughput?: number;
  kb_received?: number;
  kb_sent?: number;
}

const num = (v: number) => (v >= 1000 ? Math.round(v).toLocaleString() : v.toFixed(2));

export default function SummaryTable({ rows, durationSeconds, total, titulo = 'Reporte Resumen' }: {
  rows: SummaryRow[];
  durationSeconds: number;
  /** La ejecucion, para la fila TOTAL. Sin ella no se pinta esa fila (alcance transaccion). */
  total?: any;
  titulo?: string;
}) {
  return (
          <div className="w-full overflow-x-auto rounded-2xl shadow-lg border border-gray-200">
            <div className="bg-[#0a1628] px-6 py-4">
              <h2 className="text-3xl font-bold text-white">{titulo}</h2>
            </div>
            <table className="w-full table-auto text-lg">
              <thead className="bg-[#0a1628]">
                <tr>
                  <th className="px-3 py-2 text-left text-base font-bold text-white uppercase">Transaccion</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">Muestras</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">Errores</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">% Error</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">Promedio</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">Mediana</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">90%</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">95%</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">99%</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">Min</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">Max</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">TPS</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">KB/s Rec</th>
                  <th className="px-3 py-2 text-right text-base font-bold text-white uppercase">KB/s Env</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-100">
                {(rows || []).map((row: any, idx: number) => (
                  <tr key={idx} className="hover:bg-blue-50/50 transition-colors">
                    <td className="px-3 py-2 text-base font-medium text-gray-900 max-w-[250px] truncate" title={row.label}>{row.label}</td>
                    <td className="px-3 py-2 text-base text-right text-gray-700">{row.count.toLocaleString()}</td>
                    <td className="px-3 py-2 text-base text-right text-red-600 font-semibold">{(row.error_count ?? (row.count - row.success_count)).toLocaleString()}</td>
                    <td className={`px-3 py-2 text-base text-right font-semibold ${(row.error_rate ?? 0) === 0 ? 'text-green-600' : (row.error_rate ?? 0) < 5 ? 'text-orange-600 bg-orange-50' : 'text-red-600 bg-red-50'}`}>
                      {(row.error_rate ?? ((row.count - row.success_count) / row.count * 100)).toFixed(2)}%
                    </td>
                    <td className="px-3 py-2 text-base text-right text-gray-700">{num(row.avg_time)}</td>
                    <td className="px-3 py-2 text-base text-right text-gray-700">{num(row.avg_time)}</td>
                    <td className="px-3 py-2 text-base text-right text-gray-700">{num(row.p90 ?? row.avg_time * 1.5)}</td>
                    <td className="px-3 py-2 text-base text-right text-gray-700">{num(row.p95 ?? row.avg_time * 2)}</td>
                    <td className="px-3 py-2 text-base text-right text-gray-700">{num(row.p99 ?? row.avg_time * 3)}</td>
                    <td className="px-3 py-2 text-base text-right text-gray-700">{num(row.min_time)}</td>
                    <td className="px-3 py-2 text-base text-right text-gray-700">{num(row.max_time)}</td>
                    <td className="px-3 py-2 text-base text-right text-blue-700 font-semibold">{(row.throughput ?? (row.count / (durationSeconds || 1))).toFixed(2)}</td>
                    <td className="px-3 py-2 text-base text-right text-gray-700">{row.kb_received?.toFixed(2) || '--'}</td>
                    <td className="px-3 py-2 text-base text-right text-gray-700">{row.kb_sent?.toFixed(2) || '--'}</td>
                  </tr>
                ))}
                {total && (
                <tr className="bg-[#0a1628] text-white font-bold">
                  <td className="px-3 py-2 text-base">TOTAL PRINCIPALES</td>
                  <td className="px-3 py-2 text-base text-right">{total.total_requests.toLocaleString()}</td>
                  <td className="px-3 py-2 text-base text-right">{total.total_errors.toLocaleString()}</td>
                  <td className="px-3 py-2 text-base text-right">{total.error_rate.toFixed(2)}%</td>
                  <td className="px-3 py-2 text-base text-right">{total.avg_response_time.toFixed(2)}</td>
                  <td className="px-3 py-2 text-base text-right">{total.median_response_time?.toFixed(2) || '--'}</td>
                  <td className="px-3 py-2 text-base text-right">{total.p90_response_time.toFixed(2)}</td>
                  <td className="px-3 py-2 text-base text-right">{total.p95_response_time.toFixed(2)}</td>
                  <td className="px-3 py-2 text-base text-right">{total.p99_response_time.toFixed(2)}</td>
                  <td className="px-3 py-2 text-base text-right">{total.min_response_time.toFixed(2)}</td>
                  <td className="px-3 py-2 text-base text-right">{total.max_response_time.toFixed(2)}</td>
                  <td className="px-3 py-2 text-base text-right">{total.throughput.toFixed(2)}</td>
                  <td className="px-3 py-2 text-base text-right">{total.kb_per_sec_received?.toFixed(2) || '--'}</td>
                  <td className="px-3 py-2 text-base text-right">{total.kb_per_sec_sent?.toFixed(2) || '--'}</td>
                </tr>
                )}
              </tbody>
            </table>
          </div>
  );
}
