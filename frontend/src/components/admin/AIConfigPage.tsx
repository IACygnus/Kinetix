/**
 * AI Configuration Page
 * Admin-only: provider, model, API key, usage limits with progress bars
 */
import { useState, useEffect } from 'react';
import { Brain, TestTube, RotateCcw, Save, CheckCircle, XCircle, Loader2, Eye, EyeOff } from 'lucide-react';
import { aiConfigAPI } from '../../services/api';
import type { AIConfigInfo, AIProviderInfo, AITestResult } from '../../types';

export default function AIConfigPage() {
  const [config, setConfig] = useState<AIConfigInfo | null>(null);
  const [providers, setProviders] = useState<AIProviderInfo[]>([]);
  const [testResult, setTestResult] = useState<AITestResult | null>(null);

  const [selectedProvider, setSelectedProvider] = useState('gemini');
  const [selectedModel, setSelectedModel] = useState('gemini-2.0-flash');
  const [apiKey, setApiKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [isActive, setIsActive] = useState(true);
  const [dailyLimit, setDailyLimit] = useState(1000);
  const [monthlyLimit, setMonthlyLimit] = useState(20000);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError('');
    try {
      const [cfgData, modelsData] = await Promise.all([
        aiConfigAPI.get(),
        aiConfigAPI.getModels(),
      ]);
      setConfig(cfgData);
      setProviders(modelsData);
      setSelectedProvider(cfgData.provider);
      setSelectedModel(cfgData.model_name);
      setIsActive(cfgData.is_active);
      setDailyLimit(cfgData.daily_request_limit);
      setMonthlyLimit(cfgData.monthly_request_limit);
    } catch {
      setError('Error cargando configuracion');
    } finally {
      setLoading(false);
    }
  };

  const availableModels = providers.find((p) => p.id === selectedProvider)?.models || [];

  const handleProviderChange = (newProvider: string) => {
    setSelectedProvider(newProvider);
    const prov = providers.find((p) => p.id === newProvider);
    if (prov && prov.models.length > 0) {
      setSelectedModel(prov.models[0]);
    }
    setTestResult(null);
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const payload: Record<string, unknown> = {
        provider: selectedProvider,
        model_name: selectedModel,
        is_active: isActive,
        daily_request_limit: dailyLimit,
        monthly_request_limit: monthlyLimit,
      };
      if (apiKey.trim()) {
        payload.api_key = apiKey.trim();
      }
      const updated = await aiConfigAPI.save(payload);
      setConfig(updated);
      setApiKey('');
      setShowKey(false);
      setSuccess('Configuracion guardada exitosamente');
      setTestResult(null);
      setTimeout(() => setSuccess(''), 4000);
    } catch {
      setError('Error guardando configuracion');
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    setError('');
    try {
      const result = await aiConfigAPI.test();
      setTestResult(result);
    } catch {
      setTestResult({ status: 'error', message: 'Error de conexion', provider: selectedProvider, model: selectedModel });
    } finally {
      setTesting(false);
    }
  };

  const handleResetUsage = async () => {
    setResetting(true);
    try {
      await aiConfigAPI.resetUsage();
      const cfgData = await aiConfigAPI.get();
      setConfig(cfgData);
      setSuccess('Contadores reseteados');
      setTimeout(() => setSuccess(''), 3000);
    } catch {
      setError('Error reseteando contadores');
    } finally {
      setResetting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-[#f5a623]" />
      </div>
    );
  }

  const dailyUsed = config?.daily_requests_used || 0;
  const dailyMax = config?.daily_request_limit || 1000;
  const dailyPct = Math.min((dailyUsed / dailyMax) * 100, 100);

  const monthlyUsed = config?.monthly_requests_used || 0;
  const monthlyMax = config?.monthly_request_limit || 20000;
  const monthlyPct = Math.min((monthlyUsed / monthlyMax) * 100, 100);

  const getBarColor = (pct: number) =>
    pct >= 90 ? 'bg-red-500' : pct >= 70 ? 'bg-amber-500' : 'bg-emerald-500';

  return (
    <div className="min-h-screen bg-[#0a1628]">
      {/* Header */}
      <div className="bg-[#0a1628] px-6 py-6 border-b border-[#f5a623]/20">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-[#f5a623]/10 rounded-xl">
            <Brain className="w-8 h-8 text-[#f5a623]" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-white">Configuracion de IA</h1>
            <p className="text-xl text-gray-400">Proveedor, modelo y API key para analisis inteligente</p>
          </div>
        </div>
      </div>

      <div className="p-6 max-w-4xl mx-auto space-y-6">

      {/* Alerts */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex items-center gap-3">
          <XCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
          <span className="text-xl text-red-300">{error}</span>
        </div>
      )}
      {success && (
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4 flex items-center gap-3">
          <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0" />
          <span className="text-xl text-green-300">{success}</span>
        </div>
      )}

      {/* ===== SECTION 1: Provider Selector ===== */}
      <div className="bg-[#162040] border border-[#f5a623]/20 rounded-2xl p-6 space-y-5">
        <h2 className="text-2xl font-semibold text-white flex items-center gap-2">
          <Brain className="w-5 h-5 text-[#f5a623]" />
          Proveedor de IA
        </h2>

        {/* Provider cards */}
        <div className="grid grid-cols-2 gap-4">
          {providers.map((p) => (
            <button
              key={p.id}
              onClick={() => handleProviderChange(p.id)}
              className={`p-5 rounded-xl border-2 transition-all text-left ${
                selectedProvider === p.id
                  ? 'border-[#f5a623] bg-[#f5a623]/10'
                  : 'border-[#2a3f6f] bg-[#0d1f3c] hover:border-[#f5a623]/50'
              }`}
            >
              <span className={`text-2xl font-semibold ${selectedProvider === p.id ? 'text-[#f5a623]' : 'text-gray-300'}`}>
                {p.name}
              </span>
              <p className="text-lg text-gray-400 mt-1">{p.models.length} modelos disponibles</p>
            </button>
          ))}
        </div>

        {/* ===== SECTION 2: Model Selector ===== */}
        <div>
          <label className="block text-xl font-medium text-gray-300 mb-2">Modelo</label>
          <select
            value={selectedModel}
            onChange={(e) => { setSelectedModel(e.target.value); setTestResult(null); }}
            className="w-full bg-[#0d1f3c] border border-[#2a3f6f] rounded-xl px-4 py-3 text-xl text-white focus:outline-none focus:border-[#f5a623] transition-colors"
          >
            {availableModels.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>

        {/* ===== SECTION 3: API Key ===== */}
        <div>
          <label className="block text-xl font-medium text-gray-300 mb-2">
            API Key
            {config?.api_key_masked && (
              <span className="ml-2 text-lg text-green-400 font-normal">
                ({config.api_key_masked})
              </span>
            )}
          </label>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <input
                type={showKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={config?.api_key_masked ? 'Dejar vacio para mantener la actual' : 'Ingresa tu API key'}
                className="w-full bg-[#0d1f3c] border border-[#2a3f6f] rounded-xl px-4 py-3 pr-12 text-xl text-white placeholder-gray-500 focus:outline-none focus:border-[#f5a623] transition-colors"
              />
              <button
                type="button"
                onClick={() => setShowKey(!showKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
              >
                {showKey ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
            <button
              onClick={handleTest}
              disabled={testing || (!config?.api_key_masked && !apiKey.trim())}
              className="flex items-center gap-2 px-5 py-3 bg-[#2a3f6f] hover:bg-[#3a4f7f] text-white rounded-xl text-xl font-medium transition-colors disabled:opacity-50"
            >
              {testing ? <Loader2 className="w-5 h-5 animate-spin" /> : <TestTube className="w-5 h-5" />}
              Probar Conexion
            </button>
          </div>
        </div>

        {/* Test Result */}
        {testResult && (
          <div className={`rounded-xl p-4 flex items-center gap-3 ${
            testResult.status === 'ok'
              ? 'bg-green-500/10 border border-green-500/30'
              : 'bg-red-500/10 border border-red-500/30'
          }`}>
            {testResult.status === 'ok'
              ? <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0" />
              : <XCircle className="w-5 h-5 text-red-400 flex-shrink-0" />}
            <div>
              <p className={`text-xl ${testResult.status === 'ok' ? 'text-green-300' : 'text-red-300'}`}>
                {testResult.message}
              </p>
              <p className="text-lg text-gray-400 mt-1">
                {testResult.provider} / {testResult.model}
              </p>
            </div>
          </div>
        )}

        {/* Active toggle + Limits */}
        <div className="grid grid-cols-3 gap-4 pt-2">
          <div className="flex items-center gap-3">
            <label className="text-xl text-gray-300">Activo</label>
            <button
              onClick={() => setIsActive(!isActive)}
              className={`relative w-12 h-7 rounded-full transition-colors ${
                isActive ? 'bg-emerald-500' : 'bg-[#2a3f6f]'
              }`}
            >
              <span className={`absolute top-1 w-5 h-5 rounded-full bg-white transition-transform ${
                isActive ? 'left-6' : 'left-1'
              }`} />
            </button>
          </div>
          <div>
            <label className="block text-lg text-gray-400 mb-1">Limite diario</label>
            <input
              type="number"
              min={1}
              value={dailyLimit}
              onChange={(e) => setDailyLimit(Number(e.target.value) || 1)}
              className="w-full bg-[#0d1f3c] border border-[#2a3f6f] rounded-lg px-3 py-2 text-xl text-white focus:outline-none focus:border-[#f5a623]"
            />
          </div>
          <div>
            <label className="block text-lg text-gray-400 mb-1">Limite mensual</label>
            <input
              type="number"
              min={1}
              value={monthlyLimit}
              onChange={(e) => setMonthlyLimit(Number(e.target.value) || 1)}
              className="w-full bg-[#0d1f3c] border border-[#2a3f6f] rounded-lg px-3 py-2 text-xl text-white focus:outline-none focus:border-[#f5a623]"
            />
          </div>
        </div>

        {/* Save button */}
        <div className="pt-2">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-6 py-3 bg-[#f5a623] hover:bg-[#e09410] text-[#0a1628] rounded-xl text-xl font-bold transition-colors disabled:opacity-50"
          >
            {saving ? <Loader2 className="w-5 h-5 animate-spin" /> : <Save className="w-5 h-5" />}
            Guardar Configuracion
          </button>
        </div>
      </div>

      {/* ===== SECTION 4: Usage Stats ===== */}
      <div className="bg-[#162040] border border-[#f5a623]/20 rounded-2xl p-6 space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-semibold text-white">Consumo de Solicitudes</h2>
          <button
            onClick={handleResetUsage}
            disabled={resetting}
            className="flex items-center gap-2 px-4 py-2 text-lg bg-[#2a3f6f] hover:bg-[#3a4f7f] text-gray-300 rounded-lg transition-colors disabled:opacity-50"
          >
            {resetting ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-4 h-4" />}
            Resetear Contadores
          </button>
        </div>

        {/* Daily progress */}
        <div>
          <div className="flex justify-between text-xl text-gray-300 mb-2">
            <span>Uso diario</span>
            <span className="font-mono font-semibold">
              {dailyUsed.toLocaleString()} / {dailyMax.toLocaleString()}
            </span>
          </div>
          <div className="w-full bg-[#0d1f3c] rounded-full h-4">
            <div
              className={`h-4 rounded-full transition-all ${getBarColor(dailyPct)}`}
              style={{ width: `${dailyPct}%` }}
            />
          </div>
          <p className="text-lg text-gray-500 mt-1">
            {dailyPct.toFixed(1)}% utilizado
            {config?.last_reset_daily && ` — ultimo reset: ${config.last_reset_daily}`}
          </p>
        </div>

        {/* Monthly progress */}
        <div>
          <div className="flex justify-between text-xl text-gray-300 mb-2">
            <span>Uso mensual</span>
            <span className="font-mono font-semibold">
              {monthlyUsed.toLocaleString()} / {monthlyMax.toLocaleString()}
            </span>
          </div>
          <div className="w-full bg-[#0d1f3c] rounded-full h-4">
            <div
              className={`h-4 rounded-full transition-all ${getBarColor(monthlyPct)}`}
              style={{ width: `${monthlyPct}%` }}
            />
          </div>
          <p className="text-lg text-gray-500 mt-1">
            {monthlyPct.toFixed(1)}% utilizado
            {config?.last_reset_monthly && ` — ultimo reset: ${config.last_reset_monthly}`}
          </p>
        </div>
      </div>

      </div>{/* end p-6 max-w-4xl content wrapper */}
    </div>
  );
}
