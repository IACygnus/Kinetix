/**
 * DashboardHome - Pagina de inicio post-login con KPIs - SQA Corporate Branding
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText,
  Users,
  Clock,
  TrendingUp,
  Plus,
  Activity,
  AlertCircle,
  BarChart3,
} from 'lucide-react';
import { dashboardAPI, monitoringAPI } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import type { DashboardStats, MonitoringHealth } from '../../types';

export default function DashboardHome() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [monitorHealth, setMonitorHealth] = useState<MonitoringHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [data, health] = await Promise.all([
          dashboardAPI.getStats(),
          monitoringAPI.getHealth().catch(() => null),
        ]);
        setStats(data);
        setMonitorHealth(health);
      } catch {
        setError('Error al cargar estadisticas');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'Sin datos';
    return new Date(dateStr).toLocaleDateString('es-ES', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-sqa-gold" />
      </div>
    );
  }

  return (
    <div className="space-y-6 w-full">
      {/* Header */}
      <div className="bg-gradient-to-r from-sqa-navy to-sqa-navy-light rounded-2xl p-8 shadow-lg">
        <h1 className="text-5xl font-bold text-white">
          Dashboard <span className="text-sqa-gold">SQA</span>
        </h1>
        <p className="text-2xl text-slate-300 mt-1">
          Bienvenido, {user?.full_name || 'Usuario'}
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-2xl p-4 flex items-center gap-3">
          <AlertCircle className="w-7 h-7 text-red-500" />
          <span className="text-xl text-red-700">{error}</span>
        </div>
      )}

      {/* KPI Cards */}
      <div className={`grid grid-cols-1 sm:grid-cols-2 gap-5 ${user?.role === 'admin' ? 'lg:grid-cols-4' : 'lg:grid-cols-3'}`}>
        <KPICard
          icon={<FileText className="w-8 h-8" />}
          label="Total Reportes"
          value={stats?.total_reports ?? 0}
          color="blue"
        />
        {user?.role === 'admin' && (
          <KPICard
            icon={<Users className="w-8 h-8" />}
            label="Usuarios Registrados"
            value={stats?.total_users ?? 0}
            color="emerald"
          />
        )}
        <KPICard
          icon={<Clock className="w-8 h-8" />}
          label="Ultimo Analisis"
          value={formatDate(stats?.last_analysis ?? null)}
          color="gold"
          isText
        />
        <KPICard
          icon={<TrendingUp className="w-8 h-8" />}
          label="Reportes Recientes"
          value={stats?.recent_reports?.length ?? 0}
          color="purple"
        />
      </div>

      {/* Service Status */}
      {monitorHealth && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <ServiceStatusCard
            label="Grafana"
            status={monitorHealth.grafana_status}
            message={monitorHealth.grafana_message}
          />
          <ServiceStatusCard
            label="InfluxDB"
            status={monitorHealth.influxdb_status}
            message={monitorHealth.influxdb_message}
          />
        </div>
      )}

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {(user?.role === 'admin' || user?.role === 'analyst') && (
          <button
            onClick={() => navigate('/performance/new')}
            className="flex items-center gap-4 p-6 bg-white border border-gray-200 rounded-2xl shadow-sm hover:shadow-md hover:border-sqa-gold/50 transition-all group"
          >
            <div className="w-14 h-14 bg-sqa-gold/10 rounded-xl flex items-center justify-center group-hover:bg-sqa-gold/20">
              <Plus className="w-8 h-8 text-sqa-gold" />
            </div>
            <div className="text-left">
              <p className="text-2xl font-semibold text-gray-800">Nuevo Reporte</p>
              <p className="text-xl text-gray-500">Analizar archivos JTL</p>
            </div>
          </button>
        )}

        <button
          onClick={() => navigate('/monitoring/realtime')}
          className="flex items-center gap-4 p-6 bg-white border border-gray-200 rounded-2xl shadow-sm hover:shadow-md hover:border-emerald-400/50 transition-all group"
        >
          <div className="w-14 h-14 bg-emerald-50 rounded-xl flex items-center justify-center group-hover:bg-emerald-100">
            <Activity className="w-8 h-8 text-emerald-600" />
          </div>
          <div className="text-left">
            <p className="text-2xl font-semibold text-gray-800">Monitoreo Real-Time</p>
            <p className="text-xl text-gray-500">Dashboard Grafana</p>
          </div>
        </button>

        <button
          onClick={() => navigate('/performance/history')}
          className="flex items-center gap-4 p-6 bg-white border border-gray-200 rounded-2xl shadow-sm hover:shadow-md hover:border-purple-400/50 transition-all group"
        >
          <div className="w-14 h-14 bg-purple-50 rounded-xl flex items-center justify-center group-hover:bg-purple-100">
            <BarChart3 className="w-8 h-8 text-purple-600" />
          </div>
          <div className="text-left">
            <p className="text-2xl font-semibold text-gray-800">Historial</p>
            <p className="text-xl text-gray-500">Ver reportes anteriores</p>
          </div>
        </button>
      </div>

      {/* Recent Reports */}
      <div className="bg-white rounded-2xl shadow-lg overflow-hidden border border-gray-200">
        <div className="px-6 py-5 border-b border-gray-200">
          <h2 className="text-3xl font-bold text-gray-800">Reportes Recientes</h2>
        </div>
        <div className="divide-y divide-gray-100">
          {stats?.recent_reports && stats.recent_reports.length > 0 ? (
            stats.recent_reports.map((report) => (
              <button
                key={report.id}
                onClick={() => navigate(`/performance/report/${report.id}`)}
                className="w-full flex items-center justify-between px-6 py-5 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center gap-4">
                  <FileText className="w-7 h-7 text-gray-400" />
                  <div className="text-left">
                    <p className="text-2xl font-medium text-gray-800">
                      {report.name}
                    </p>
                    <p className="text-xl text-gray-500">{report.jtl_filename}</p>
                  </div>
                </div>
                <div className="flex items-center gap-5">
                  <span className="text-xl text-gray-500">
                    {report.total_requests.toLocaleString()} muestras
                  </span>
                  <span
                    className={`text-xl font-semibold px-3 py-1 rounded-lg ${
                      report.error_rate > 5
                        ? 'bg-red-100 text-red-700'
                        : report.error_rate > 1
                        ? 'bg-amber-100 text-amber-700'
                        : 'bg-emerald-100 text-emerald-700'
                    }`}
                  >
                    {report.error_rate.toFixed(2)}% error
                  </span>
                  <span className="text-xl text-gray-400">
                    {formatDate(report.created_at)}
                  </span>
                </div>
              </button>
            ))
          ) : (
            <div className="px-6 py-14 text-center">
              <FileText className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <p className="text-2xl text-gray-500">No hay reportes aun</p>
              {(user?.role === 'admin' || user?.role === 'analyst') && (
                <button
                  onClick={() => navigate('/performance/new')}
                  className="mt-4 text-2xl text-sqa-gold hover:text-sqa-gold-light transition-colors"
                >
                  Crear primer reporte
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function KPICard({
  icon,
  label,
  value,
  color,
  isText = false,
}: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  color: string;
  isText?: boolean;
}) {
  const colorMap: Record<string, { bg: string; icon: string; border: string; text: string }> = {
    blue: { bg: 'bg-blue-50', icon: 'text-blue-600', border: 'border-l-4 border-l-blue-500', text: 'text-blue-700' },
    emerald: { bg: 'bg-emerald-50', icon: 'text-emerald-600', border: 'border-l-4 border-l-emerald-500', text: 'text-emerald-700' },
    gold: { bg: 'bg-amber-50', icon: 'text-sqa-gold', border: 'border-l-4 border-l-sqa-gold', text: 'text-sqa-gold-dark' },
    purple: { bg: 'bg-purple-50', icon: 'text-purple-600', border: 'border-l-4 border-l-purple-500', text: 'text-purple-700' },
  };

  const c = colorMap[color] || colorMap.blue;

  return (
    <div className={`bg-white ${c.border} rounded-2xl shadow-lg p-6 border border-gray-200`}>
      <div className="flex items-center gap-4 mb-3">
        <div className={`w-14 h-14 ${c.bg} rounded-xl flex items-center justify-center`}>
          <span className={c.icon}>{icon}</span>
        </div>
        <span className="text-2xl text-gray-500">{label}</span>
      </div>
      <p className={`${isText ? 'text-xl' : 'text-6xl font-bold'} ${c.text}`}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </p>
    </div>
  );
}

function ServiceStatusCard({
  label,
  status,
  message,
}: {
  label: string;
  status: string;
  message: string;
}) {
  const getStyle = () => {
    switch (status) {
      case 'ok':
        return { dot: 'bg-emerald-500', text: 'text-emerald-600', border: 'border-emerald-200' };
      case 'error':
        return { dot: 'bg-red-500', text: 'text-red-600', border: 'border-red-200' };
      case 'not_configured':
        return { dot: 'bg-amber-500', text: 'text-amber-600', border: 'border-amber-200' };
      default:
        return { dot: 'bg-gray-400', text: 'text-gray-500', border: 'border-gray-200' };
    }
  };

  const s = getStyle();

  return (
    <div className={`bg-white border ${s.border} rounded-2xl px-6 py-5 flex items-center justify-between shadow-sm`}>
      <div className="flex items-center gap-3">
        <span className={`w-3.5 h-3.5 rounded-full ${s.dot} ${status === 'ok' ? 'animate-pulse' : ''}`} />
        <span className="text-2xl font-medium text-gray-700">{label}</span>
      </div>
      <span className={`text-xl ${s.text}`}>{message}</span>
    </div>
  );
}
