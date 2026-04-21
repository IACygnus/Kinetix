/**
 * ChartYAxisZoom — Compact Y-axis zoom controls for Recharts charts.
 * Shows Auto-fit, P99, Reset buttons and a max slider when zoomed.
 */
import { useState, useCallback, useMemo } from 'react';

interface Props {
  dataValues: number[];
  onRangeChange: (yMin: number | 'auto', yMax: number | 'auto') => void;
}

export default function ChartYAxisZoom({ dataValues, onRangeChange }: Props) {
  const stats = useMemo(() => {
    if (!dataValues || dataValues.length === 0) return { min: 0, max: 100, p99: 100, p95: 100, mean: 50 };
    const sorted = dataValues.filter(v => v != null && !isNaN(v)).sort((a, b) => a - b);
    if (sorted.length === 0) return { min: 0, max: 100, p99: 100, p95: 100, mean: 50 };
    return {
      min: sorted[0],
      max: sorted[sorted.length - 1],
      p99: sorted[Math.min(Math.floor(sorted.length * 0.99), sorted.length - 1)],
      p95: sorted[Math.min(Math.floor(sorted.length * 0.95), sorted.length - 1)],
      mean: sorted.reduce((a, b) => a + b, 0) / sorted.length,
    };
  }, [dataValues]);

  const [isZoomed, setIsZoomed] = useState(false);
  const [yMax, setYMax] = useState(stats.max);

  const handleAutoFit = useCallback(() => {
    const newMax = Math.ceil(stats.p95 * 1.1);
    setYMax(newMax);
    setIsZoomed(true);
    onRangeChange(0, newMax);
  }, [stats, onRangeChange]);

  const handleP99 = useCallback(() => {
    const newMax = Math.ceil(stats.p99 * 1.05);
    setYMax(newMax);
    setIsZoomed(true);
    onRangeChange(0, newMax);
  }, [stats, onRangeChange]);

  const handleReset = useCallback(() => {
    setIsZoomed(false);
    setYMax(stats.max);
    onRangeChange('auto', 'auto');
  }, [stats, onRangeChange]);

  const handleSlider = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const val = Number(e.target.value);
    setYMax(val);
    setIsZoomed(true);
    onRangeChange(0, val);
  }, [onRangeChange]);

  if (!dataValues || dataValues.length < 5 || stats.max - stats.min < 1) return null;

  const btnBase = "text-xs px-2 py-0.5 rounded border transition-colors";
  const btnActive = `${btnBase} border-[#f5a623] bg-[#f5a623] text-[#0a1628] font-semibold`;
  const btnInactive = `${btnBase} border-gray-300 text-gray-500 hover:border-gray-400`;

  return (
    <div className="flex items-center gap-2 mt-1 mb-1 px-2">
      <span className="text-xs text-gray-400">Eje Y:</span>
      <button onClick={handleAutoFit} className={isZoomed ? btnActive : btnInactive} title="Auto-ajustar (P95)">Auto-fit</button>
      {stats.max > stats.mean * 3 && (
        <button onClick={handleP99} className={btnInactive} title="Mostrar hasta P99">P99</button>
      )}
      {isZoomed && (
        <>
          <button onClick={handleReset} className={btnInactive} title="Restaurar">Reset</button>
          <div className="flex items-center gap-1 flex-1 max-w-[200px]">
            <span className="text-xs text-gray-400">Max:</span>
            <input type="range" min={Math.max(1, Math.floor(stats.mean * 0.5))} max={Math.ceil(stats.max * 1.1)}
              value={yMax} onChange={handleSlider} className="flex-1 h-1" style={{ accentColor: '#f5a623' }} />
            <span className="text-xs text-gray-500 w-14 text-right">{yMax >= 1000 ? `${(yMax / 1000).toFixed(1)}k` : yMax.toFixed(0)}</span>
          </div>
        </>
      )}
    </div>
  );
}
