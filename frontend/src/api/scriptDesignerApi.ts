// frontend/src/api/scriptDesignerApi.ts
/**
 * Script Designer API — Sprint 1
 * Uses the shared axios instance from services/api.ts for CSRF + cookie support.
 */
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';

// Create dedicated instance with same config as main api (withCredentials + CSRF)
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

// CSRF interceptor (same as services/api.ts)
api.interceptors.request.use((config) => {
  if (config.method && config.method !== 'get') {
    const csrfToken = document.cookie
      .split('; ')
      .find((row) => row.startsWith('csrf_token='))
      ?.split('=')[1];
    if (csrfToken) {
      config.headers['X-CSRF-Token'] = csrfToken;
    }
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
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

export interface ScriptRequest {
  id: string;
  order: number;
  name: string;
  protocol: string;
  method: string;
  url: string;
  headers: Record<string, string>;
  body: string;
  body_type: 'json' | 'xml' | 'form' | 'raw';
  params: Record<string, string>;
  assertions: Array<{ type: string; value: string }>;
  think_time_ms: number;
  extractors: Array<{
    variable_name: string;
    extract_from: 'body' | 'header';
    regex: string;
    match_no: number;
    default_value: string;
    header_name?: string;
  }>;
}

export type VariableType = 'manual' | 'imported' | 'auto' | 'extractor' | 'datafile' | 'builtin';

export interface ScriptVariableModel {
  name: string;
  value: string;
  type: VariableType;
  source_hint?: string;
  source?: string;              // legacy field from older imports
  default_value?: string;       // solo para type=extractor
  datafile_name?: string;       // solo para type=datafile
  datafile_column?: string;     // solo para type=datafile
}

export interface ScriptModel {
  requests: ScriptRequest[];
  variables: ScriptVariableModel[];
  data_files: any[];
  protocol: string;
}

export interface Script {
  id: number;
  name: string;
  description: string | null;
  client_id: string | null;
  user_id: string;
  script_model: ScriptModel;
  origin: string;
  created_at: string;
  updated_at: string;
}

// ─── Scripts ──────────────────────────────────────────────────────────────────

export const scriptApi = {
  list: () => api.get<Script[]>('/scripts/'),

  get: (id: number) => api.get<Script>(`/scripts/${id}`),

  create: (data: { name: string; description?: string; script_model: ScriptModel; origin?: string }) =>
    api.post<Script>('/scripts/', data),

  update: (id: number, data: { name?: string; description?: string; script_model?: ScriptModel }) =>
    api.put<Script>(`/scripts/${id}`, data),

  delete: (id: number) => api.delete(`/scripts/${id}`),

  exportJMX: (id: number) =>
    api.post(`/scripts/${id}/export-jmx`, {}, { responseType: 'blob' }),
};

// ─── HAR Import ───────────────────────────────────────────────────────────────

export interface HARImportStats {
  total_entries: number;
  imported: number;
  filtered_static: number;
  filtered_tracker: number;
  filtered_other: number;
}

export interface HARImportResponse {
  script_model: ScriptModel;
  stats: HARImportStats;
}

export const harApi = {
  preview: (file: File, baseUrlFilter?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    if (baseUrlFilter) formData.append('base_url_filter', baseUrlFilter);
    return api.post<HARImportResponse>('/har-import/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
};

// ─── Data Files ───────────────────────────────────────────────────────────────

export interface DataFile {
  id: number;
  script_id: number;
  original_filename: string;
  stored_filename: string;
  file_path: string;
  columns: string[];
  row_count: number | null;
  variable_mapping: Record<string, string>;
  created_at: string;
}

export interface DataFilePreview {
  columns: string[];
  rows: Record<string, string>[];
  row_count: number | null;
  variable_mapping: Record<string, string>;
}

export const dataFileApi = {
  upload: (scriptId: number, file: File) => {
    const formData = new FormData();
    formData.append('script_id', String(scriptId));
    formData.append('file', file);
    return api.post<DataFile>('/data-files/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  listByScript: (scriptId: number) =>
    api.get<DataFile[]>(`/data-files/script/${scriptId}`),

  preview: (fileId: number) =>
    api.get<DataFilePreview>(`/data-files/${fileId}/preview`),

  updateMapping: (fileId: number, variableMapping: Record<string, string>) =>
    api.put<DataFile>(`/data-files/${fileId}/mapping`, { variable_mapping: variableMapping }),

  delete: (fileId: number) => api.delete(`/data-files/${fileId}`),
};

// ─── Script Variables (Sprint 7) ──────────────────────────────────────────────

export const variableApi = {
  /** Escanear variables del script desde el backend */
  scan: (scriptId: number) =>
    api.get<{ script_id: number; total: number; variables: ScriptVariableModel[] }>(`/scripts/${scriptId}/variables`),

  /** Obtener columnas de un data file */
  getColumns: (fileId: number) =>
    api.get<{ columns: string[] }>(`/data-files/${fileId}/columns`),
};

// ─── Executions ───────────────────────────────────────────────────────────────

export interface SmokeTestResult {
  execution_id: number;
  success: boolean;
  total_requests: number;
  passed_requests: number;
  failed_requests: number;
  duration_ms: number;
  jtl_file_path: string;
  request_details: Array<{
    name: string;
    url: string;
    status_code: string;
    elapsed_ms: number;
    success: boolean;
    failure_message: string;
    bytes: number;
  }>;
  unresolved_variables: Array<{ variable: string; context_keys: string[] }>;
  error_message: string;
}

export interface AICorrelation {
  variable_name: string;
  description: string;
  extract_from_request: number;
  extract_from: 'body' | 'header';
  regex: string;
  match_no: number;
  default_value: string;
  used_in_requests: number[];
  header_name: string;
}

export interface AICorrelateResult {
  correlations: AICorrelation[];
  analysis_summary: string;
  error?: string;
}

export interface AIDebugResult {
  requests_to_remove: number[];
  reasons: Record<string, string>;
  analysis_summary: string;
  error?: string;
}

export const executionApi = {
  smokeTest: (scriptId: number | undefined, scenarioId?: number, scriptModel?: ScriptModel) =>
    api.post<SmokeTestResult>('/executions/smoke-test', {
      script_id: scriptId || undefined,
      scenario_id: scenarioId,
      script_model: scriptModel || undefined,
    }),

  aiCorrelate: (scriptId: number) =>
    api.post<AICorrelateResult>('/executions/ai-correlate', { script_id: scriptId }),

  aiDebug: (scriptId: number) =>
    api.post<AIDebugResult>('/executions/ai-debug', { script_id: scriptId }),

  downloadJTL: (executionId: number) =>
    api.get(`/executions/${executionId}/download-jtl`, { responseType: 'blob' }),
};
