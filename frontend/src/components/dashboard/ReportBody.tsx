/**
 * ReportBody — el cuerpo del informe, parametrizado por ALCANCE (ETAPA 2, D21).
 *
 * Extraido VERBATIM de Dashboard.tsx. En este primer paso solo existe el alcance
 * `general` y lo que pinta es identico a lo que pintaba Dashboard: es un refactor
 * puro, sin cambio de orden, contenido ni estilos (condicion C1 de la etapa).
 *
 * El bloque por transaccion usara ESTE MISMO componente con
 * `scope = {kind:'transaction', label}`, que es lo que garantiza por construccion
 * el "mismo diseño que el general" que pide la especificacion v1.2 §1.
 *
 * CustomChartTooltip, ScrollableLegend y getXAxisProps se movieron aqui enteros
 * porque solo se usaban en este bloque.
 */
import React from 'react';
import {
  LineChart, Line, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';
import ChartYAxisZoom from './ChartYAxisZoom';
import {
  CHART_LAYOUT,
  CHART_LABELS,
  CHART_TOOLTIP,
  getColorForIndex,
  getCodeColor,
  truncateLabel,
  getAdaptiveFontSize,
  getXAxisInterval,
  shouldRotateLabels,
  MAX_SUFFIX,
} from '../../config/chartConfig';

export type ReportScope =
  | { kind: 'general' }
  | { kind: 'transaction'; label: string };

interface CustomTooltipProps {
  active?: boolean;
  payload?: any[];
  label?: string;
  unit?: string;
  formatter?: (val: number) => string;
}

function CustomChartTooltip({ active, payload, label, unit = 'ms', formatter }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;

  const fmt = formatter || ((val: number) => {
    if (unit === 'ms') return CHART_TOOLTIP.formatMs(val);
    if (unit === 'req/s' || unit === 'tps') return CHART_TOOLTIP.formatTps(val);
    if (unit === '%') return CHART_TOOLTIP.formatPercent(val);
    return CHART_TOOLTIP.formatCount(val);
  });

  return (
    <div className="bg-slate-900 text-white rounded-lg shadow-2xl border border-slate-700 p-3 max-w-xs">
      <p className="text-xl text-slate-400 mb-2 font-mono border-b border-slate-700 pb-1">{label}</p>
      <div className="space-y-1 max-h-48 overflow-y-auto">
        {payload.filter((p: any) => p.value != null).sort((a: any, b: any) => (b.value || 0) - (a.value || 0)).map((entry: any, idx: number) => (
          <div key={idx} className="flex items-center justify-between gap-3 text-xl">
            <div className="flex items-center gap-1.5 min-w-0">
              <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: entry.color }} />
              <span className="truncate text-slate-300">{entry.name || entry.dataKey}</span>
            </div>
            <span className="font-mono font-semibold text-white flex-shrink-0">{fmt(entry.value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ===== SCROLLABLE LEGEND COMPONENT =====
interface ScrollableLegendProps {
  payload?: any[];
  hiddenLines: Set<string>;
  onToggle: (dataKey: string) => void;
}

function ScrollableLegend({ payload, hiddenLines, onToggle, onSetAll }: ScrollableLegendProps & { onSetAll?: (keys: Set<string>) => void }) {
  // FIX leyenda: Recharts NO honra legendType="none" cuando la leyenda usa `content`
  // propio. getLegendProps (util/getLegendProps.js) arma el payload con TODAS las
  // series y solo copia legendType en `type`; el descarte vive unicamente en
  // DefaultLegendContent.js:136 (`if (entry.type === 'none') return null`), que aqui
  // no se ejecuta. Se filtra en este componente para que las series de maximos no
  // aporten una segunda entrada por transaccion.
  const items = (payload || []).filter((e: any) => e && e.type !== 'none');
  if (items.length === 0) return null;

  const allKeys = items.map((e: any) => e.dataKey || e.value);
  const visibleCount = allKeys.filter((k: string) => !hiddenLines.has(k)).length;
  const allVisible = visibleCount === allKeys.length;
  const noneVisible = visibleCount === 0;

  const handleMasterToggle = () => {
    if (onSetAll) {
      // Direct Set replacement — fixes the bug where only last item toggled
      onSetAll(allVisible ? new Set(allKeys) : new Set());
    }
  };

  return (
    <div className="w-full px-2 py-1">
      {/* KNX-06: Master select/deselect */}
      {allKeys.length > 1 && (
        <div className="flex justify-center mb-1">
          <button
            onClick={handleMasterToggle}
            className="text-sm px-3 py-1 rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-100 transition-colors"
          >
            {allVisible ? 'Ocultar todas' : noneVisible ? 'Mostrar todas' : `${visibleCount}/${allKeys.length} visibles — Mostrar todas`}
          </button>
        </div>
      )}
      <div
        className="flex flex-wrap gap-x-4 gap-y-1 justify-center overflow-y-auto"
        style={{ maxHeight: '90px' }}
      >
        {items.map((entry: any, idx: number) => {
          const isHidden = hiddenLines.has(entry.dataKey || entry.value);
          return (
            <button
              key={idx}
              onClick={() => onToggle(entry.dataKey || entry.value)}
              className={`flex items-center gap-1.5 px-2 py-1 rounded text-xl transition-all hover:bg-gray-100 ${
                isHidden ? 'opacity-40 line-through' : 'opacity-100'
              }`}
            >
              <span
                className="w-4 h-1.5 rounded-full flex-shrink-0"
                style={{ backgroundColor: entry.color }}
              />
              <span className="text-gray-700 whitespace-nowrap">
                {truncateLabel(entry.value || entry.dataKey, 25)}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ===== ADAPTIVE X AXIS PROPS =====
function getXAxisProps(dataLength: number, labelCount?: number) {
  const count = labelCount ?? dataLength;
  // KNX-11: Always rotate if >6 labels OR if data is dense (>50 points)
  const rotate = shouldRotateLabels(count) || dataLength > 50;
  const fontSize = getAdaptiveFontSize(count);
  const interval = getXAxisInterval(dataLength);

  return {
    dataKey: 'displayTime',
    tick: { fontSize: rotate ? Math.min(fontSize, 11) : fontSize },
    height: rotate ? 85 : 50,
    angle: rotate ? CHART_LABELS.rotationAngle : 0,
    textAnchor: rotate ? ('end' as const) : ('middle' as const),
    interval,
    tickFormatter: (value: string) => {
      if (count > CHART_LABELS.truncateThreshold || dataLength > 100) {
        return truncateLabel(value, 8);
      }
      return value;
    },
  };
}

/**
 * Todo lo que el cuerpo necesita. Se pasa en un solo objeto y se desestructura con
 * los MISMOS nombres que tenia en Dashboard, para que el JSX de abajo quede
 * copiado tal cual y la equivalencia sea comprobable a simple vista.
 */
export interface ReportBodyCtx {
  // datos ya preparados
  responseTimesByLabel: any;
  rtMaxKeys: string[];
  rtMaxLabels: string[];
  latencyData: any[];
  errorRateData: any[];
  codesPerSecond: any;
  tpsByLabel: any;
  activeThreadsData: any[];
  // textos de IA y sus setters
  analysisResponseTimes: string;
  setAnalysisResponseTimes: (v: string) => void;
  analysisLatency: string;
  setAnalysisLatency: (v: string) => void;
  analysisErrorRate: string;
  setAnalysisErrorRate: (v: string) => void;
  analysisCodesPerSecond: string;
  setAnalysisCodesPerSecond: (v: string) => void;
  analysisTransactionsPerSecond: string;
  setAnalysisTransactionsPerSecond: (v: string) => void;
  analysisActiveThreads: string;
  setAnalysisActiveThreads: (v: string) => void;
  // leyendas plegables
  hiddenLinesResponseTimes: Set<string>;
  setHiddenLinesResponseTimes: React.Dispatch<React.SetStateAction<Set<string>>>;
  hiddenLinesTPS: Set<string>;
  setHiddenLinesTPS: React.Dispatch<React.SetStateAction<Set<string>>>;
  hiddenLinesCodes: Set<string>;
  setHiddenLinesCodes: React.Dispatch<React.SetStateAction<Set<string>>>;
  // helpers de la pantalla
  minH: number;
  emitEdit: (campo: string, setter: (v: string) => void) => (valor: string) => void;
  getYDomain: (key: string) => [number | string, number | string];
  extractY: (data: any[], keys: string[]) => number[];
  handleYRange: (key: string, mn: number | 'auto', mx: number | 'auto') => void;
  /** ETAPA 3 (D36): `campo` identifica la seccion, para que quien pinte la caja
   *  pueda buscar sus avisos de estilo. Quien no los use, lo ignora. */
  AnalysisBox: React.ComponentType<{ value: string; onChange: (v: string) => void; campo?: string }>;
  handleLegendClick: (
    dataKey: string,
    hiddenLines: Set<string>,
    setHiddenLines: React.Dispatch<React.SetStateAction<Set<string>>>,
  ) => void;
}

export default function ReportBody({ scope, ctx }: { scope: ReportScope; ctx: ReportBodyCtx }) {
  const {
    responseTimesByLabel, rtMaxKeys, rtMaxLabels, latencyData,
    errorRateData, codesPerSecond, tpsByLabel, activeThreadsData,
    analysisResponseTimes, setAnalysisResponseTimes,
    // D19: sin throughputData ni analysisThroughput: la grafica salio del producto.
    analysisLatency, setAnalysisLatency,
    analysisErrorRate, setAnalysisErrorRate,
    analysisCodesPerSecond, setAnalysisCodesPerSecond,
    analysisTransactionsPerSecond, setAnalysisTransactionsPerSecond,
    analysisActiveThreads, setAnalysisActiveThreads,
    hiddenLinesResponseTimes, setHiddenLinesResponseTimes,
    hiddenLinesTPS, setHiddenLinesTPS,
    hiddenLinesCodes, setHiddenLinesCodes,
    minH, emitEdit, getYDomain, extractY, handleYRange, AnalysisBox, handleLegendClick,
  } = ctx;
  // ETAPA 2 (D18/D21): el unico punto donde el alcance cambia lo que se pinta.
  // Todo lo demas es identico en general y en transaccion, que es justamente lo
  // que pide v1.2 §1: "el mismo informe general, filtrado".
  const esGeneral = scope.kind === 'general';

  return (
          <div className="bg-white rounded-b-2xl shadow-lg p-6 space-y-10 border border-gray-200 border-t-0">
            {/* 1. Response Times */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
              <h3 className="text-3xl font-bold text-gray-800 mb-4 border-l-4 border-[#0a1628] pl-4">Response Times por Transaccion</h3>
              <ResponsiveContainer width="100%" height={700}>
                <LineChart data={responseTimesByLabel.data} margin={CHART_LAYOUT.padding}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis {...getXAxisProps(responseTimesByLabel.data.length, responseTimesByLabel.labels.length)} />
                  <YAxis tick={{ fontSize: 14 }} tickCount={10} domain={getYDomain('rtByLabel')} allowDataOverflow={true} label={{ value: 'Tiempo (ms)', angle: -90, position: 'insideLeft', style: { fontSize: 14 } }} />
                  <Tooltip content={<CustomChartTooltip unit="ms" />} />
                  <Legend content={<ScrollableLegend hiddenLines={hiddenLinesResponseTimes} onToggle={(key) => handleLegendClick(key, hiddenLinesResponseTimes, setHiddenLinesResponseTimes)} onSetAll={setHiddenLinesResponseTimes} />} verticalAlign="bottom" />
                  {responseTimesByLabel.labels.map((label: string, idx: number) => (
                    <Line key={label} type="monotone" dataKey={label} stroke={getColorForIndex(idx)} strokeWidth={1.5} dot={false} connectNulls hide={hiddenLinesResponseTimes.has(label)} activeDot={{ r: 3 }} isAnimationActive={false} />
                  ))}
                  {/* GRAF1-B: maximo por transaccion — fina y punteada, mismo color que su promedio.
                      legendType="none" la excluye del payload de la leyenda (sin entrada duplicada);
                      se oculta junto con su promedio al usar la leyenda. */}
                  {rtMaxLabels.map((label: string) => (
                    <Line key={`${label}${MAX_SUFFIX}`} type="monotone" dataKey={`${label}${MAX_SUFFIX}`}
                      stroke={getColorForIndex(responseTimesByLabel.labels.indexOf(label))} strokeWidth={0.8}
                      strokeDasharray="2 3" strokeOpacity={0.85} dot={false} connectNulls legendType="none"
                      hide={hiddenLinesResponseTimes.has(label)} activeDot={{ r: 2 }} isAnimationActive={false} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
              <ChartYAxisZoom dataValues={extractY(responseTimesByLabel.data, [...responseTimesByLabel.labels, ...rtMaxKeys])} onRangeChange={(mn, mx) => handleYRange('rtByLabel', mn, mx)} />
              <AnalysisBox campo='ai_analysis_response_times' value={analysisResponseTimes} onChange={emitEdit('ai_analysis_response_times', setAnalysisResponseTimes)} />
            </div>

            {/* UI-2: grafica "Response Time Over Time" (promedio agregado) retirada.
                La fuente de verdad es "Response Times por Transaccion" con su serie
                dual avg/max. El analisis IA ya guardado se sigue cargando y guardando,
                solo deja de pintarse. */}

            {/* ETAPA 2 (D19): "Throughput Over Time" se retiro del producto entero
                (especificacion v1.2 §1.2). Iba aqui, entre Response Times y Latency.
                El escalar `throughput` (req/s) de la tabla resumen y de los KPI NO
                se toca: lo que sale es la GRAFICA y su analisis. */}

            {/* 4. Latency */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
              <h3 className="text-3xl font-bold text-gray-800 mb-4 border-l-4 border-[#0a1628] pl-4">Latency Over Time</h3>
              <ResponsiveContainer width="100%" height={minH}>
                <AreaChart data={latencyData} margin={CHART_LAYOUT.padding}>
                  <defs><linearGradient id="colorLatency" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#eab308" stopOpacity={0.8}/><stop offset="95%" stopColor="#eab308" stopOpacity={0.1}/></linearGradient></defs>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis {...getXAxisProps(latencyData.length)} />
                  <YAxis tick={{ fontSize: 14 }} tickCount={10} domain={getYDomain('latency')} allowDataOverflow={true} label={{ value: 'Latencia (ms)', angle: -90, position: 'insideLeft', style: { fontSize: 14 } }} />
                  <Tooltip content={<CustomChartTooltip unit="ms" />} />
                  <Area type="monotone" dataKey="value" stroke="#eab308" strokeWidth={1.5} dot={false} fillOpacity={0.15} fill="url(#colorLatency)" connectNulls isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
              <ChartYAxisZoom dataValues={extractY(latencyData, ['value'])} onRangeChange={(mn, mx) => handleYRange('latency', mn, mx)} />
              <AnalysisBox campo='ai_analysis_latency' value={analysisLatency} onChange={emitEdit('ai_analysis_latency', setAnalysisLatency)} />
            </div>

            {/* 5. Error Rate */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
              <h3 className="text-3xl font-bold text-gray-800 mb-4 border-l-4 border-[#0a1628] pl-4">Error Rate Over Time</h3>
              <ResponsiveContainer width="100%" height={minH}>
                <AreaChart data={errorRateData} margin={CHART_LAYOUT.padding}>
                  <defs><linearGradient id="colorErrorRate" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#ef4444" stopOpacity={0.8}/><stop offset="95%" stopColor="#ef4444" stopOpacity={0.1}/></linearGradient></defs>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis {...getXAxisProps(errorRateData.length)} />
                  <YAxis tick={{ fontSize: 14 }} tickCount={10} domain={getYDomain('errorRate')} allowDataOverflow={true} label={{ value: 'Error Rate (%)', angle: -90, position: 'insideLeft', style: { fontSize: 14 } }} />
                  <Tooltip content={<CustomChartTooltip unit="%" />} />
                  <Area type="monotone" dataKey="value" stroke="#ef4444" strokeWidth={1.5} dot={false} fillOpacity={0.15} fill="url(#colorErrorRate)" connectNulls isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
              <ChartYAxisZoom dataValues={extractY(errorRateData, ['value'])} onRangeChange={(mn, mx) => handleYRange('errorRate', mn, mx)} />
              <AnalysisBox campo='ai_analysis_error_rate' value={analysisErrorRate} onChange={emitEdit('ai_analysis_error_rate', setAnalysisErrorRate)} />
            </div>

            {/* 6. Response Codes per Second */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
              <h3 className="text-3xl font-bold text-gray-800 mb-4 border-l-4 border-[#0a1628] pl-4">Response Codes per Second</h3>
              <ResponsiveContainer width="100%" height={minH}>
                <LineChart data={codesPerSecond.data} margin={CHART_LAYOUT.padding}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis {...getXAxisProps(codesPerSecond.data.length, codesPerSecond.labels.length)} />
                  <YAxis tick={{ fontSize: 14 }} tickCount={10} domain={getYDomain('codes')} allowDataOverflow={true} label={{ value: 'Codes/sec', angle: -90, position: 'insideLeft', style: { fontSize: 14 } }} />
                  <Tooltip content={<CustomChartTooltip unit="count" />} />
                  <Legend content={<ScrollableLegend hiddenLines={hiddenLinesCodes} onToggle={(key) => handleLegendClick(key, hiddenLinesCodes, setHiddenLinesCodes)} onSetAll={setHiddenLinesCodes} />} verticalAlign="bottom" />
                  {codesPerSecond.labels.map((label: string) => {
                    const code = label.replace('HTTP ', '');
                    return <Line key={label} type="monotone" dataKey={label} stroke={getCodeColor(code)} strokeWidth={1.5} dot={false} connectNulls hide={hiddenLinesCodes.has(label)} activeDot={{ r: 3 }} isAnimationActive={false} />;
                  })}
                </LineChart>
              </ResponsiveContainer>
              <ChartYAxisZoom dataValues={extractY(codesPerSecond.data, codesPerSecond.labels)} onRangeChange={(mn, mx) => handleYRange('codes', mn, mx)} />
              <AnalysisBox campo='ai_analysis_codes_per_second' value={analysisCodesPerSecond} onChange={emitEdit('ai_analysis_codes_per_second', setAnalysisCodesPerSecond)} />
            </div>

            {/* 7. TPS */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
              <h3 className="text-3xl font-bold text-gray-800 mb-4 border-l-4 border-[#0a1628] pl-4">Transactions per Second</h3>
              <ResponsiveContainer width="100%" height={minH}>
                <LineChart data={tpsByLabel.data} margin={CHART_LAYOUT.padding}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis {...getXAxisProps(tpsByLabel.data.length, tpsByLabel.labels.length)} />
                  <YAxis tick={{ fontSize: 14 }} tickCount={10} domain={getYDomain('tps')} allowDataOverflow={true} label={{ value: 'TPS', angle: -90, position: 'insideLeft', style: { fontSize: 14 } }} />
                  <Tooltip content={<CustomChartTooltip unit="tps" />} />
                  <Legend content={<ScrollableLegend hiddenLines={hiddenLinesTPS} onToggle={(key) => handleLegendClick(key, hiddenLinesTPS, setHiddenLinesTPS)} onSetAll={setHiddenLinesTPS} />} verticalAlign="bottom" />
                  {tpsByLabel.labels.map((label: string, idx: number) => (
                    <Line key={label} type="monotone" dataKey={label} stroke={getColorForIndex(idx)} strokeWidth={1.5} dot={false} connectNulls hide={hiddenLinesTPS.has(label)} activeDot={{ r: 3 }} isAnimationActive={false} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
              <ChartYAxisZoom dataValues={extractY(tpsByLabel.data, tpsByLabel.labels)} onRangeChange={(mn, mx) => handleYRange('tps', mn, mx)} />
              <AnalysisBox campo='ai_analysis_transactions_per_second' value={analysisTransactionsPerSecond} onChange={emitEdit('ai_analysis_transactions_per_second', setAnalysisTransactionsPerSecond)} />
            </div>

            {/* 8. Active Threads */}
            {/* ETAPA 2 (D18): los hilos son de TODA la prueba, no de una transaccion
                (v1.2 §1.2), asi que esta grafica solo aparece en el alcance general. */}
            {esGeneral && (
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
              <h3 className="text-3xl font-bold text-gray-800 mb-4 border-l-4 border-[#0a1628] pl-4">Active Threads Over Time</h3>
              <ResponsiveContainer width="100%" height={minH}>
                <AreaChart data={activeThreadsData} margin={CHART_LAYOUT.padding}>
                  <defs><linearGradient id="colorThreads" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#ec4899" stopOpacity={0.8}/><stop offset="95%" stopColor="#ec4899" stopOpacity={0.1}/></linearGradient></defs>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis {...getXAxisProps(activeThreadsData.length)} />
                  <YAxis tick={{ fontSize: 14 }} tickCount={10} domain={getYDomain('threads')} allowDataOverflow={true} label={{ value: 'Threads', angle: -90, position: 'insideLeft', style: { fontSize: 14 } }} />
                  <Tooltip content={<CustomChartTooltip unit="count" />} />
                  <Area type="monotone" dataKey="value" stroke="#ec4899" strokeWidth={1.5} dot={false} fillOpacity={0.15} fill="url(#colorThreads)" connectNulls isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
              <ChartYAxisZoom dataValues={extractY(activeThreadsData, ['value'])} onRangeChange={(mn, mx) => handleYRange('threads', mn, mx)} />
              <AnalysisBox campo='ai_analysis_active_threads' value={analysisActiveThreads} onChange={emitEdit('ai_analysis_active_threads', setAnalysisActiveThreads)} />
            </div>
            )}
          </div>
  );
}
