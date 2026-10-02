/**
 * «Analista IA» — el mini gráfico de la tarjeta «La prueba»: usuarios activos
 * (área) y fallos (barras) por tramo, con la subida y la bajada sombreadas.
 * Los datos son `ficha.serie` (como mucho 120 puntos) y `ficha.fases`.
 */
import { Area, Bar, ComposedChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { Ficha } from '../../api/analistaApi';

const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`;

export default function MiniGrafico({ ficha }: { ficha: Ficha }) {
  const puntos = ficha.serie?.puntos || [];
  if (puntos.length === 0) {
    return <p className="text-xs text-gray-400">Sin serie para el gráfico (sesión anterior a la pantalla).</p>;
  }
  const datos = puntos.map(([t, u, e]) => ({ t, usuarios: u, fallos: e }));
  const f = ficha.fases;
  const fin = f.duracion_s;
  return (
    <div className="w-full" data-testid="mini-grafico">
      <div className="mb-0.5 flex gap-3 text-[10px] text-gray-500">
        <span><span className="mr-1 inline-block h-0.5 w-3 bg-indigo-600 align-middle" />usuarios activos</span>
        <span><span className="mr-1 inline-block h-2 w-2 bg-red-500/60 align-middle" />fallos</span>
      </div>
      <div className="h-28 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={datos} margin={{ top: 4, right: 4, bottom: 0, left: -18 }}>
          {f.disponible && f.subida_hasta_s != null && f.subida_hasta_s > 0 && (
            <ReferenceArea x1={0} x2={f.subida_hasta_s} yAxisId="u" fill="#e5e7eb" fillOpacity={0.6} />
          )}
          {f.disponible && f.bajada_desde_s != null && !f.sin_bajada && (
            <ReferenceArea x1={f.bajada_desde_s} x2={fin} yAxisId="u" fill="#e5e7eb" fillOpacity={0.6} />
          )}
          <XAxis dataKey="t" type="number" domain={[0, fin]} tickFormatter={mmss} tick={{ fontSize: 10 }} />
          <YAxis yAxisId="u" allowDecimals={false} tick={{ fontSize: 10 }} />
          {/* Los fallos, en el tercio de abajo: si no, tapan la línea de usuarios. */}
          <YAxis yAxisId="e" orientation="right" hide domain={[0, (max: number) => Math.max(1, max * 3)]} />
          <Tooltip
            labelFormatter={(t) => `min ${mmss(Number(t))}`}
            formatter={(v: number, n: string) => [v, n === 'usuarios' ? 'Usuarios activos' : 'Fallos en el tramo']}
          />
          <Bar yAxisId="e" dataKey="fallos" fill="#dc2626" opacity={0.55} isAnimationActive={false} />
          <Area yAxisId="u" type="stepAfter" dataKey="usuarios" stroke="#4f46e5" strokeWidth={2} fill="#c7d2fe"
            fillOpacity={0.35} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
      </div>
    </div>
  );
}
