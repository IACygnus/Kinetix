// frontend/src/api/executionApi.ts
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

// CSRF interceptor
api.interceptors.request.use(config => {
  if (config.method && config.method !== 'get') {
    const csrf = document.cookie
      .split('; ')
      .find(row => row.startsWith('csrf_token='))
      ?.split('=')[1];
    if (csrf) config.headers['X-CSRF-Token'] = csrf;
  }
  return config;
});

api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      const url = error.config?.url || '';
      const isAuthEndpoint = url.includes('/auth/me') || url.includes('/auth/refresh') || url.includes('/auth/login');
      if (!isAuthEndpoint) {
        window.dispatchEvent(new Event('session-expired'));
      }
    }
    return Promise.reject(error);
  }
);

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ScenarioTemplate {
  name: string;
  test_type: string;
  config: Record<string, number>;
}

export interface Scenario {
  id: number;
  name: string;
  test_type: string;
  thread_group_config: Record<string, number>;
  script_id: number;
  created_at: string;
}

export interface MetricsSnapshot {
  execution_id: number;
  timestamp: string;
  active_vus: number;
  status: string;
  total_requests?: number;
  error_rate_percent?: number;
  avg_response_time_ms?: number;
  p95_response_time_ms?: number;
  p99_response_time_ms?: number;
  avg_tps?: number;
  peak_tps?: number;
  final?: boolean;
  error?: string;
}

export interface ExecutionHistoryItem {
  id: number;
  status: string;
  is_active: boolean;
  started_at: string | null;
  completed_at: string | null;
  scenario_name: string;
  script_name: string;
  test_type: string;
  total_requests: number;
  error_rate_percent: number;
  avg_response_time_ms: number;
  duration_sec: number | null;
  jtl_file_path: string | null;
  output_filename: string | null;
}

// ─── API calls ────────────────────────────────────────────────────────────────

export const scenarioApi = {
  templates: () => api.get<Record<string, Record<string, number>>>('/scenarios/templates'),
  list: (scriptId?: number) => api.get<Scenario[]>(`/scenarios/${scriptId ? `?script_id=${scriptId}` : ''}`),
  create: (data: {
    name: string;
    test_type: string;
    thread_group_config: Record<string, number>;
    script_id: number;
  }) => api.post<Scenario>('/scenarios/', data),
  get: (id: number) => api.get<Scenario>(`/scenarios/${id}`),
  delete: (id: number) => api.delete(`/scenarios/${id}`),
};

export const fullExecutionApi = {
  start: (scenarioId: number, scriptId: number) =>
    api.post<{ execution_id: number; status: string; jtl_file_path: string; ws_url: string }>(
      '/executions/start',
      { scenario_id: scenarioId, script_id: scriptId }
    ),

  control: (executionId: number, action: 'stop' | 'pause' | 'resume') =>
    api.post(`/executions/${executionId}/control`, { action }),

  status: (executionId: number) =>
    api.get<{
      execution_id: number;
      status: string;
      active_vus: number;
      total_requests: number;
      error_rate_percent: number;
      avg_response_time_ms: number;
      started_at: string | null;
      duration_sec: number | null;
    }>(`/executions/${executionId}/status`),

  history: (limit = 20, offset = 0) =>
    api.get<{ items: ExecutionHistoryItem[]; total: number; has_more: boolean }>(
      `/executions/history?limit=${limit}&offset=${offset}`
    ),

  downloadJTL: (executionId: number) =>
    api.get(`/executions/${executionId}/download-jtl`, { responseType: 'blob' }),

  generateReport: (executionId: number) =>
    api.post<{ analysis_id: string; status: string; report_url: string }>(
      `/executions/${executionId}/generate-report`
    ),
};
