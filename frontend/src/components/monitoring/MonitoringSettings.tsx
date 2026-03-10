/**
 * MonitoringSettings - Admin-only config form for Grafana + InfluxDB - v2.0 Phase 4
 * Features: form fields, test connection, status indicators, save
 */
import { useEffect, useState } from 'react';
import {
  Save,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  XCircle,
  Loader2,
  Eye,
  EyeOff,
  Server,
  Database,
} from 'lucide-react';
import { monitoringAPI } from '../../services/api';
import type { MonitoringConfig, MonitoringHealth, MonitoringConfigUpdate } from '../../types';

export default function MonitoringSettings() {
  const [config, setConfig] = useState<MonitoringConfig | null>(null);
  const [health, setHealth] = useState<MonitoringHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [showToken, setShowToken] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Form state
  const [form, setForm] = useState<MonitoringConfigUpdate>({
    grafana_url: '',
    grafana_dashboard_uid: '',
    influxdb_url: '',
    influxdb_org: '',
    influxdb_bucket: '',
    influxdb_token: '',
  });

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [cfg, hlth] = await Promise.all([
          monitoringAPI.getConfig(),
          monitoringAPI.getHealth(),
        ]);
        setConfig(cfg);
        setHealth(hlth);
        setForm({
          grafana_url: cfg.grafana_url || '',
          grafana_dashboard_uid: cfg.grafana_dashboard_uid || '',
          influxdb_url: cfg.influxdb_url || '',
          influxdb_org: cfg.influxdb_org || '',
          influxdb_bucket: cfg.influxdb_bucket || '',
          influxdb_token: '', // Never pre-filled
        });
      } catch {
        setError('Error al cargar configuracion');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleChange = (field: keyof MonitoringConfigUpdate, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setError('');
    setSuccess('');
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      // Only send non-empty fields; if token is empty, don't send it (keep existing)
      const payload: MonitoringConfigUpdate = {};
      if (form.grafana_url !== undefined) payload.grafana_url = form.grafana_url;
      if (form.grafana_dashboard_uid !== undefined) payload.grafana_dashboard_uid = form.grafana_dashboard_uid;
      if (form.influxdb_url !== undefined) payload.influxdb_url = form.influxdb_url;
      if (form.influxdb_org !== undefined) payload.influxdb_org = form.influxdb_org;
      if (form.influxdb_bucket !== undefined) payload.influxdb_bucket = form.influxdb_bucket;
      if (form.influxdb_token) payload.influxdb_token = form.influxdb_token;

      const updated = await monitoringAPI.updateConfig(payload);
      setConfig(updated);
      setForm((prev) => ({ ...prev, influxdb_token: '' }));
      setSuccess('Configuracion guardada correctamente');
    } catch {
      setError('Error al guardar configuracion');
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    // Save first, then test
    setTesting(true);
    setError('');
    setSuccess('');
    try {
      // Save changes first
      const payload: MonitoringConfigUpdate = {};
      if (form.grafana_url !== undefined) payload.grafana_url = form.grafana_url;
      if (form.grafana_dashboard_uid !== undefined) payload.grafana_dashboard_uid = form.grafana_dashboard_uid;
      if (form.influxdb_url !== undefined) payload.influxdb_url = form.influxdb_url;
      if (form.influxdb_org !== undefined) payload.influxdb_org = form.influxdb_org;
      if (form.influxdb_bucket !== undefined) payload.influxdb_bucket = form.influxdb_bucket;
      if (form.influxdb_token) payload.influxdb_token = form.influxdb_token;

      await monitoringAPI.updateConfig(payload);
      setForm((prev) => ({ ...prev, influxdb_token: '' }));

      const hlth = await monitoringAPI.getHealth();
      setHealth(hlth);

      const cfg = await monitoringAPI.getConfig();
      setConfig(cfg);

      if (hlth.grafana_status === 'ok' && hlth.influxdb_status === 'ok') {
        setSuccess('Conexion exitosa con Grafana e InfluxDB');
      } else {
        const issues = [];
        if (hlth.grafana_status !== 'ok') issues.push(`Grafana: ${hlth.grafana_message}`);
        if (hlth.influxdb_status !== 'ok') issues.push(`InfluxDB: ${hlth.influxdb_message}`);
        setError(issues.join(' | '));
      }
    } catch {
      setError('Error al probar conexion');
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-4xl font-bold text-white">Configuracion de Monitoreo</h1>
        <p className="text-slate-400 mt-1 text-xl">Administrar conexiones de Grafana e InfluxDB</p>
      </div>

      {/* Status Banner */}
      {config && (
        <div className={`rounded-lg p-4 flex items-center gap-3 ${
          config.is_configured
            ? 'bg-emerald-900/20 border border-emerald-700'
            : 'bg-amber-900/20 border border-amber-700'
        }`}>
          {config.is_configured ? (
            <CheckCircle2 className="w-7 h-7 text-emerald-400" />
          ) : (
            <AlertCircle className="w-7 h-7 text-amber-400" />
          )}
          <div>
            <p className={`text-lg font-medium ${config.is_configured ? 'text-emerald-300' : 'text-amber-300'}`}>
              {config.is_configured ? 'Monitoreo configurado' : 'Monitoreo no configurado'}
            </p>
            {config.updated_at && (
              <p className="text-lg text-slate-400 mt-0.5">
                Ultima actualizacion: {new Date(config.updated_at).toLocaleString('es-ES')}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Alerts */}
      {error && (
        <div className="bg-red-900/20 border border-red-700 rounded-lg p-3 flex items-center gap-2">
          <XCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
          <span className="text-lg text-red-300">{error}</span>
        </div>
      )}
      {success && (
        <div className="bg-emerald-900/20 border border-emerald-700 rounded-lg p-3 flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />
          <span className="text-lg text-emerald-300">{success}</span>
        </div>
      )}

      {/* Grafana Section */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Server className="w-7 h-7 text-orange-400" />
            <h2 className="text-2xl font-semibold text-white">Grafana</h2>
          </div>
          {health && <ServiceStatus status={health.grafana_status} message={health.grafana_message} />}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FormField
            label="URL de Grafana"
            placeholder="http://grafana:3000"
            value={form.grafana_url || ''}
            onChange={(v) => handleChange('grafana_url', v)}
            hint="URL interna (Docker) o externa del servidor Grafana"
          />
          <FormField
            label="Dashboard UID"
            placeholder="jmeter-realtime"
            value={form.grafana_dashboard_uid || ''}
            onChange={(v) => handleChange('grafana_dashboard_uid', v)}
            hint="UID del dashboard de Grafana a embeber"
          />
        </div>
      </div>

      {/* InfluxDB Section */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Database className="w-7 h-7 text-blue-400" />
            <h2 className="text-2xl font-semibold text-white">InfluxDB</h2>
          </div>
          {health && <ServiceStatus status={health.influxdb_status} message={health.influxdb_message} />}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FormField
            label="URL de InfluxDB"
            placeholder="http://influxdb:8086"
            value={form.influxdb_url || ''}
            onChange={(v) => handleChange('influxdb_url', v)}
            hint="URL del servidor InfluxDB"
          />
          <FormField
            label="Organizacion"
            placeholder="jmeter-org"
            value={form.influxdb_org || ''}
            onChange={(v) => handleChange('influxdb_org', v)}
            hint="Nombre de la organizacion en InfluxDB"
          />
          <FormField
            label="Bucket"
            placeholder="jmeter"
            value={form.influxdb_bucket || ''}
            onChange={(v) => handleChange('influxdb_bucket', v)}
            hint="Nombre del bucket de datos"
          />
          <div className="space-y-1.5">
            <label className="block text-lg font-medium text-slate-300">
              Token de acceso
              {config?.has_influxdb_token && (
                <span className="ml-2 text-lg text-emerald-400">(configurado)</span>
              )}
            </label>
            <div className="relative">
              <input
                type={showToken ? 'text' : 'password'}
                value={form.influxdb_token || ''}
                onChange={(e) => handleChange('influxdb_token', e.target.value)}
                placeholder={config?.has_influxdb_token ? '••••••••  (dejar vacio para mantener)' : 'Token de InfluxDB'}
                className="w-full px-5 h-14 pr-12 bg-slate-900 border border-slate-600 rounded-lg text-white text-xl placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
              <button
                type="button"
                onClick={() => setShowToken(!showToken)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
              >
                {showToken ? <EyeOff className="w-6 h-6" /> : <Eye className="w-6 h-6" />}
              </button>
            </div>
            <p className="text-lg text-slate-500">Se almacena encriptado (Fernet)</p>
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors text-xl font-medium"
        >
          {saving ? <Loader2 className="w-6 h-6 animate-spin" /> : <Save className="w-6 h-6" />}
          Guardar
        </button>

        <button
          onClick={handleTestConnection}
          disabled={testing}
          className="flex items-center gap-2 px-6 py-3 bg-slate-700 text-slate-200 rounded-lg hover:bg-slate-600 disabled:opacity-50 transition-colors text-xl font-medium"
        >
          {testing ? <Loader2 className="w-6 h-6 animate-spin" /> : <RefreshCw className="w-6 h-6" />}
          Probar Conexion
        </button>
      </div>
    </div>
  );
}

function FormField({
  label,
  placeholder,
  value,
  onChange,
  hint,
}: {
  label: string;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
  hint?: string;
}) {
  return (
    <div className="space-y-1.5">
      <label className="block text-lg font-medium text-slate-300">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-5 h-14 bg-slate-900 border border-slate-600 rounded-lg text-white text-xl placeholder-slate-500 focus:outline-none focus:border-indigo-500"
      />
      {hint && <p className="text-lg text-slate-500">{hint}</p>}
    </div>
  );
}

function ServiceStatus({ status, message }: { status: string; message: string }) {
  const getStyle = () => {
    switch (status) {
      case 'ok':
        return { icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-900/30', border: 'border-emerald-700' };
      case 'error':
        return { icon: XCircle, color: 'text-red-400', bg: 'bg-red-900/30', border: 'border-red-700' };
      case 'not_configured':
        return { icon: AlertCircle, color: 'text-amber-400', bg: 'bg-amber-900/30', border: 'border-amber-700' };
      default:
        return { icon: AlertCircle, color: 'text-slate-400', bg: 'bg-slate-800', border: 'border-slate-600' };
    }
  };

  const s = getStyle();
  const Icon = s.icon;

  return (
    <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-lg ${s.bg} border ${s.border}`}>
      <Icon className={`w-5 h-5 ${s.color}`} />
      <span className={s.color}>{message}</span>
    </div>
  );
}
