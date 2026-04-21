// frontend/src/components/execution/LiveMetricsChart.tsx
import { useEffect, useRef, useState, useCallback } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, AreaChart, Area
} from 'recharts';
import { Pause, Play, Square, AlertCircle } from 'lucide-react';
import { MetricsSnapshot } from '../../api/executionApi';

interface Props {
  executionId: number;
  onStatusChange?: (status: string) => void;
  onFinal?: (snapshot: MetricsSnapshot) => void;
}

interface ChartPoint {
  time: string;
  vus: number;
  tps: number;
  avg_rt: number;
  p95_rt: number;
  error_rate: number;
}

const MAX_POINTS = 60;

export default function LiveMetricsChart({ executionId, onStatusChange, onFinal }: Props) {
  const [data, setData] = useState<ChartPoint[]>([]);
  const [status, setStatus] = useState<string>('connecting');
  const [lastSnapshot, setLastSnapshot] = useState<MetricsSnapshot | null>(null);
  const [error, setError] = useState<string>('');
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/v1/ws/executions/${executionId}/metrics`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    setStatus('connecting');
    setError('');

    ws.onopen = () => {
      setStatus('connected');
    };

    ws.onmessage = (event) => {
      try {
        const snapshot: MetricsSnapshot = JSON.parse(event.data);

        if (snapshot.error) {
          setError(snapshot.error);
          setStatus('error');
          return;
        }

        setLastSnapshot(snapshot);
        setStatus(snapshot.status);
        onStatusChange?.(snapshot.status);

        const time = new Date(snapshot.timestamp).toLocaleTimeString('es-CO', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        });

        setData(prev => {
          const newPoint: ChartPoint = {
            time,
            vus: snapshot.active_vus || 0,
            tps: snapshot.avg_tps || 0,
            avg_rt: snapshot.avg_response_time_ms || 0,
            p95_rt: snapshot.p95_response_time_ms || 0,
            error_rate: snapshot.error_rate_percent || 0,
          };
          const updated = [...prev, newPoint];
          return updated.slice(-MAX_POINTS);
        });

        if (snapshot.final) {
          onFinal?.(snapshot);
          ws.close();
        }
      } catch (e) {
        console.error('WS parse error:', e);
      }
    };

    ws.onerror = () => {
      setError('WebSocket connection error');
      setStatus('error');
    };

    ws.onclose = () => {
      if (status !== 'completed' && status !== 'error') {
        setStatus('disconnected');
      }
    };

    return ws;
  }, [executionId]);

  useEffect(() => {
    const ws = connect();
    return () => {
      ws.close();
    };
  }, [executionId]);

  const sendCommand = (cmd: 'stop' | 'pause' | 'resume') => {
    wsRef.current?.send(cmd);
  };

  const statusColor: Record<string, string> = {
    running: 'text-green-600',
    paused: 'text-yellow-600',
    completed: 'text-blue-600',
    error: 'text-red-600',
    connecting: 'text-gray-500',
    connected: 'text-gray-500',
    disconnected: 'text-gray-400',
  };

  return (
    <div className="space-y-4">
      {/* Status bar + controls */}
      <div className="flex items-center justify-between bg-gray-50 rounded-lg px-4 py-3 border border-gray-200">
        <div className="flex items-center gap-3">
          <span className={`text-sm font-semibold capitalize ${statusColor[status] || 'text-gray-500'}`}>
            {status === 'running' && <span className="inline-block w-2 h-2 rounded-full bg-green-500 mr-1.5 animate-pulse" />}
            {status}
          </span>
          {lastSnapshot && (
            <span className="text-xs text-gray-500">
              {lastSnapshot.active_vus} VUs &middot; {lastSnapshot.total_requests?.toLocaleString()} reqs
            </span>
          )}
        </div>

        {(status === 'running' || status === 'paused') && (
          <div className="flex gap-2">
            {status === 'running' && (
              <button
                onClick={() => sendCommand('pause')}
                className="px-3 py-1 text-xs border border-yellow-300 text-yellow-700 rounded hover:bg-yellow-50 flex items-center gap-1"
              >
                <Pause className="w-3 h-3" /> Pause
              </button>
            )}
            {status === 'paused' && (
              <button
                onClick={() => sendCommand('resume')}
                className="px-3 py-1 text-xs border border-green-300 text-green-700 rounded hover:bg-green-50 flex items-center gap-1"
              >
                <Play className="w-3 h-3" /> Resume
              </button>
            )}
            <button
              onClick={() => sendCommand('stop')}
              className="px-3 py-1 text-xs border border-red-300 text-red-700 rounded hover:bg-red-50 flex items-center gap-1"
            >
              <Square className="w-3 h-3" /> Stop
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-3 text-sm text-red-700 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" /> {error}
        </div>
      )}

      {/* KPI cards */}
      {lastSnapshot && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'Active VUs', value: lastSnapshot.active_vus || 0, unit: '' },
            { label: 'Avg TPS', value: (lastSnapshot.avg_tps || 0).toFixed(1), unit: 'req/s' },
            { label: 'Avg RT', value: Math.round(lastSnapshot.avg_response_time_ms || 0), unit: 'ms' },
            { label: 'Error Rate', value: (lastSnapshot.error_rate_percent || 0).toFixed(2), unit: '%', warn: (lastSnapshot.error_rate_percent || 0) > 1 },
          ].map(({ label, value, unit, warn }) => (
            <div key={label} className={`rounded-lg p-3 border ${warn ? 'bg-red-50 border-red-200' : 'bg-white border-gray-200'}`}>
              <p className="text-xs text-gray-500 mb-0.5">{label}</p>
              <p className={`text-xl font-bold ${warn ? 'text-red-600' : 'text-gray-800'}`}>
                {value}<span className="text-xs font-normal text-gray-400 ml-1">{unit}</span>
              </p>
            </div>
          ))}
        </div>
      )}

      {data.length === 0 ? (
        <div className="h-48 flex items-center justify-center text-gray-400 text-sm bg-gray-50 rounded-lg border border-dashed border-gray-300">
          Waiting for data...
        </div>
      ) : (
        <>
          {/* Chart 1: VUs + TPS */}
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <h4 className="text-xs font-semibold text-gray-600 mb-3 uppercase tracking-wide">VUs & Throughput</h4>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="time" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis yAxisId="left" tick={{ fontSize: 10 }} />
                <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10 }} />
                <Tooltip contentStyle={{ fontSize: 11 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line yAxisId="left" type="monotone" dataKey="vus" stroke="#6366f1" strokeWidth={2} dot={false} name="VUs" />
                <Line yAxisId="right" type="monotone" dataKey="tps" stroke="#10b981" strokeWidth={2} dot={false} name="TPS" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Chart 2: Response Times */}
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <h4 className="text-xs font-semibold text-gray-600 mb-3 uppercase tracking-wide">Response Times (ms)</h4>
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="time" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip contentStyle={{ fontSize: 11 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Area type="monotone" dataKey="p95_rt" stroke="#f59e0b" fill="#fef3c7" strokeWidth={2} dot={false} name="P95" />
                <Area type="monotone" dataKey="avg_rt" stroke="#3b82f6" fill="#eff6ff" strokeWidth={2} dot={false} name="Avg" />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Chart 3: Error Rate */}
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <h4 className="text-xs font-semibold text-gray-600 mb-3 uppercase tracking-wide">Error Rate (%)</h4>
            <ResponsiveContainer width="100%" height={120}>
              <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="time" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10 }} domain={[0, 'auto']} />
                <Tooltip contentStyle={{ fontSize: 11 }} formatter={(v: number) => [`${v}%`, 'Error Rate']} />
                <Area type="monotone" dataKey="error_rate" stroke="#ef4444" fill="#fef2f2" strokeWidth={2} dot={false} name="Error %" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}
