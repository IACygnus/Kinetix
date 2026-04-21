/**
 * Centralized Chart Configuration - v2.0
 * Shared across Recharts (App) and Chart.js (HTML/PDF exports)
 */

export const CHART_COLORS = [
  '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
  '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1',
  '#14b8a6', '#e11d48', '#7c3aed', '#0ea5e9', '#d946ef',
];

export const HTTP_CODE_COLORS: Record<string, string> = {
  '200': '#10b981', '201': '#34d399', '204': '#6ee7b7',
  '301': '#60a5fa', '302': '#93c5fd',
  '400': '#f59e0b', '401': '#fb923c', '403': '#fdba74',
  '404': '#ef4444', '405': '#dc2626',
  '500': '#dc2626', '502': '#b91c1c', '503': '#991b1b',
};

export const CHART_LAYOUT = {
  minHeight: 600,
  aspectRatio: 16 / 9,
  gridColumns: { desktop: 2, tablet: 1, mobile: 1 },
  gap: 24,
  padding: { top: 20, right: 30, bottom: 60, left: 60 },
};

export const CHART_LABELS = {
  rotationThreshold: 6,
  rotationAngle: -45,
  truncateThreshold: 10,
  truncateLength: 12,
  fontSizeNormal: 12,
  fontSizeSmall: 10,
  fontSizeTiny: 8,
  maxTicksX: 20,
};

export const CHART_LEGEND = {
  position: 'bottom' as const,
  align: 'center' as const,
  maxHeight: 80,
  scrollable: true,
  fontSize: 14,
  iconSize: 12,
};

export const CHART_TOOLTIP = {
  enabled: true,
  formatMs: (val: number) => `${val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ms`,
  formatTps: (val: number) => `${val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} req/s`,
  formatPercent: (val: number) => `${val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`,
  formatCount: (val: number) => val.toLocaleString(),
};

export const CHARTS_SPEC = {
  responseTimesByLabel: {
    title: 'Response Times por Transaccion',
    xAxis: { label: 'Tiempo', type: 'time' },
    yAxis: { label: 'Response Time (ms)', unit: 'ms' },
    type: 'multi-line',
    colorBy: 'label',
  },
  responseTimeOverTime: {
    title: 'Response Time Over Time',
    xAxis: { label: 'Tiempo', type: 'time' },
    yAxis: { label: 'Response Time (ms)', unit: 'ms' },
    type: 'line-area',
    color: '#3b82f6',
  },
  throughputOverTime: {
    title: 'Throughput Over Time',
    xAxis: { label: 'Tiempo', type: 'time' },
    yAxis: { label: 'Requests/s', unit: 'req/s' },
    type: 'line-area',
    color: '#10b981',
  },
  latencyOverTime: {
    title: 'Latency Over Time',
    xAxis: { label: 'Tiempo', type: 'time' },
    yAxis: { label: 'Latency (ms)', unit: 'ms' },
    type: 'line-area',
    color: '#8b5cf6',
  },
  errorRateOverTime: {
    title: 'Error Rate Over Time',
    xAxis: { label: 'Tiempo', type: 'time' },
    yAxis: { label: 'Error Rate (%)', unit: '%' },
    type: 'line-area',
    color: '#ef4444',
  },
  responseCodesPerSecond: {
    title: 'Response Codes per Second',
    xAxis: { label: 'Tiempo', type: 'time' },
    yAxis: { label: 'Codes/s', unit: 'count/s' },
    type: 'stacked-area',
    colorBy: 'code',
  },
  transactionsPerSecond: {
    title: 'Transactions per Second',
    xAxis: { label: 'Tiempo', type: 'time' },
    yAxis: { label: 'TPS', unit: 'tps' },
    type: 'multi-line',
    colorBy: 'label',
  },
  activeThreadsOverTime: {
    title: 'Active Threads Over Time',
    xAxis: { label: 'Tiempo', type: 'time' },
    yAxis: { label: 'Threads', unit: 'count' },
    type: 'line-area',
    color: '#6366f1',
  },
};

/**
 * Get color for a label by index (cycles through CHART_COLORS)
 */
export function getColorForIndex(index: number): string {
  return CHART_COLORS[index % CHART_COLORS.length];
}

/**
 * Get color for HTTP status code
 */
export function getCodeColor(code: string): string {
  return HTTP_CODE_COLORS[code] || '#94a3b8';
}

/**
 * Truncate label if too long
 */
export function truncateLabel(label: string, maxLen?: number): string {
  const max = maxLen ?? CHART_LABELS.truncateLength;
  return label.length > max ? label.substring(0, max) + '...' : label;
}

/**
 * Calculate adaptive font size based on number of labels
 */
export function getAdaptiveFontSize(labelCount: number): number {
  if (labelCount > 25) return CHART_LABELS.fontSizeTiny;
  if (labelCount > 15) return CHART_LABELS.fontSizeSmall;
  return CHART_LABELS.fontSizeNormal;
}

/**
 * Calculate X axis interval to prevent overlap
 */
export function getXAxisInterval(dataLength: number): number {
  if (dataLength <= CHART_LABELS.maxTicksX) return 0;
  // KNX-11: More aggressive interval for long tests to prevent label overlap
  return Math.max(1, Math.ceil(dataLength / CHART_LABELS.maxTicksX));
}

/**
 * Should rotate labels?
 */
export function shouldRotateLabels(labelCount: number): boolean {
  return labelCount > CHART_LABELS.rotationThreshold;
}
