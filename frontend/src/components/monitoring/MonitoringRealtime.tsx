/**
 * MonitoringRealtime - Grafana iframe embedding con kiosk mode - v2.0 Phase 4
 * Features: time range selector, auto-refresh toggle, fullscreen, open in Grafana
 */
import { useEffect, useState, useCallback } from 'react';
import {
  Activity,
  ExternalLink,
  RefreshCw,
  Maximize2,
  Minimize2,
  Clock,
  AlertCircle,
  CheckCircle2,
  Loader2,
} from 'lucide-react';
import { monitoringAPI } from '../../services/api';
import type { MonitoringConfig, MonitoringHealth } from '../../types';

const TIME_RANGES = [
  { label: '5m', value: 'now-5m', desc: 'Ultimos 5 min' },
  { label: '15m', value: 'now-15m', desc: 'Ultimos 15 min' },
  { label: '30m', value: 'now-30m', desc: 'Ultimos 30 min' },
  { label: '1h', value: 'now-1h', desc: 'Ultima hora' },
  { label: '3h', value: 'now-3h', desc: 'Ultimas 3 horas' },
  { label: '6h', value: 'now-6h', desc: 'Ultimas 6 horas' },
  { label: '12h', value: 'now-12h', desc: 'Ultimas 12 horas' },
  { label: '24h', value: 'now-24h', desc: 'Ultimas 24 horas' },
];

const REFRESH_INTERVALS = [
  { label: 'Off', value: '' },
  { label: '5s', value: '5s' },
  { label: '10s', value: '10s' },
  { label: '30s', value: '30s' },
  { label: '1m', value: '1m' },
  { label: '5m', value: '5m' },
];

export default function MonitoringRealtime() {
  const [config, setConfig] = useState<MonitoringConfig | null>(null);
  const [health, setHealth] = useState<MonitoringHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [timeRange, setTimeRange] = useState('now-15m');
  const [refreshInterval, setRefreshInterval] = useState('10s');
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [cfg, hlth] = await Promise.all([
          monitoringAPI.getConfig(),
          monitoringAPI.getHealth(),
        ]);
        setConfig(cfg);
        setHealth(hlth);
      } catch {
        setError('Error al cargar configuracion de monitoreo');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const buildIframeUrl = useCallback(() => {
    if (!config?.grafana_url || !config?.grafana_dashboard_uid) return '';

    // Use external Grafana URL (for browser access from host)
    const baseUrl = config.grafana_url
      .replace('grafana:3000', 'localhost:3000')
      .replace(/\/$/, '');
    const uid = config.grafana_dashboard_uid;
    const params = new URLSearchParams({
      orgId: '1',
      kiosk: 'tv',
      'var-from': timeRange,
      from: timeRange,
      to: 'now',
      theme: 'dark',
    });
    if (refreshInterval) {
      params.set('refresh', refreshInterval);
    }
    return `${baseUrl}/d/${uid}?${params.toString()}`;
  }, [config, timeRange, refreshInterval]);

  const handleRefresh = () => {
    // Force iframe reload by toggling a key
    setRefreshInterval((prev) => {
      const temp = prev === '10s' ? '10s ' : '10s';
      setTimeout(() => setRefreshInterval(prev), 50);
      return temp;
    });
  };

  const toggleFullscreen = () => setIsFullscreen(!isFullscreen);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-700 rounded-lg p-6 flex items-center gap-3">
        <AlertCircle className="w-7 h-7 text-red-400" />
        <span className="text-red-300 text-xl">{error}</span>
      </div>
    );
  }

  const iframeUrl = buildIframeUrl();
  const isNotConfigured = !config?.is_configured;

  return (
    <div className={`${isFullscreen ? 'fixed inset-0 z-50 bg-slate-950 p-2' : 'space-y-4'}`}>
      {/* Header Bar */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <Activity className="w-7 h-7 text-emerald-400" />
          <div>
            <h1 className="text-3xl font-bold text-white">Monitoreo Real-Time</h1>
            {!isFullscreen && (
              <p className="text-slate-400 text-lg">Dashboard de Grafana integrado</p>
            )}
          </div>
          {/* Health indicators */}
          {health && (
            <div className="flex items-center gap-2 ml-4">
              <StatusDot status={health.grafana_status} label="Grafana" />
              <StatusDot status={health.influxdb_status} label="InfluxDB" />
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Time Range Selector */}
          <div className="flex items-center gap-1 bg-slate-800 border border-slate-700 rounded-lg p-0.5">
            <Clock className="w-5 h-5 text-slate-400 ml-2" />
            {TIME_RANGES.map((tr) => (
              <button
                key={tr.value}
                onClick={() => setTimeRange(tr.value)}
                title={tr.desc}
                className={`px-3 py-1.5 text-lg rounded-md transition-colors ${
                  timeRange === tr.value
                    ? 'bg-indigo-600 text-white'
                    : 'text-slate-400 hover:text-white hover:bg-slate-700'
                }`}
              >
                {tr.label}
              </button>
            ))}
          </div>

          {/* Auto-refresh selector */}
          <select
            value={refreshInterval}
            onChange={(e) => setRefreshInterval(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-slate-300 text-lg rounded-lg px-3 py-2 focus:outline-none focus:border-indigo-500"
            title="Auto-refresh interval"
          >
            {REFRESH_INTERVALS.map((ri) => (
              <option key={ri.value} value={ri.value}>
                {ri.value ? `↻ ${ri.label}` : '↻ Off'}
              </option>
            ))}
          </select>

          {/* Action buttons */}
          <button
            onClick={handleRefresh}
            className="p-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
            title="Recargar dashboard"
          >
            <RefreshCw className="w-6 h-6" />
          </button>

          <button
            onClick={toggleFullscreen}
            className="p-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
            title={isFullscreen ? 'Salir de pantalla completa' : 'Pantalla completa'}
          >
            {isFullscreen ? <Minimize2 className="w-6 h-6" /> : <Maximize2 className="w-6 h-6" />}
          </button>

          {config?.grafana_url && (
            <a
              href={config.grafana_url.replace('grafana:3000', 'localhost:3000')}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-4 py-2 bg-slate-700 text-slate-200 rounded-lg hover:bg-slate-600 transition-colors text-lg"
            >
              <ExternalLink className="w-5 h-5" />
              Grafana
            </a>
          )}
        </div>
      </div>

      {/* Not configured warning */}
      {isNotConfigured && (
        <div className="bg-amber-900/20 border border-amber-700 rounded-lg p-4 flex items-start gap-3">
          <AlertCircle className="w-7 h-7 text-amber-400 mt-0.5" />
          <div>
            <p className="text-lg text-amber-300 font-medium">Monitoreo no configurado</p>
            <p className="text-lg text-amber-400/70 mt-1">
              Un administrador debe configurar las conexiones de Grafana e InfluxDB en
              Configuracion &gt; Monitoreo antes de poder visualizar los dashboards.
            </p>
          </div>
        </div>
      )}

      {/* Grafana iframe */}
      <div
        className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden"
        style={{ height: isFullscreen ? 'calc(100vh - 60px)' : 'calc(100vh - 220px)', minHeight: '400px' }}
      >
        {iframeUrl ? (
          <iframe
            key={iframeUrl}
            src={iframeUrl}
            className="w-full h-full border-0"
            title="Grafana Dashboard"
            allow="fullscreen"
          />
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-slate-500">
            <Activity className="w-16 h-16 mb-4 opacity-30" />
            <p className="text-2xl font-medium">Dashboard no disponible</p>
            <p className="text-lg mt-1">Configure la conexion a Grafana para visualizar metricas</p>
          </div>
        )}
      </div>
    </div>
  );
}

function StatusDot({ status, label }: { status: string; label: string }) {
  const getColor = () => {
    switch (status) {
      case 'ok':
        return 'text-emerald-400';
      case 'error':
        return 'text-red-400';
      case 'not_configured':
        return 'text-amber-400';
      default:
        return 'text-slate-500';
    }
  };

  return (
    <div className="flex items-center gap-1" title={`${label}: ${status}`}>
      {status === 'ok' ? (
        <CheckCircle2 className={`w-5 h-5 ${getColor()}`} />
      ) : (
        <AlertCircle className={`w-5 h-5 ${getColor()}`} />
      )}
      <span className={`text-lg ${getColor()}`}>{label}</span>
    </div>
  );
}
