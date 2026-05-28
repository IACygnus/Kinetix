/**
 * API Service - SQA Kinetix Pro
 */
import axios from 'axios';
import type { UserInfo, UserCreate, UserUpdate, ProfileUpdate, PasswordChange, DashboardStats, MonitoringConfig, MonitoringConfigUpdate, MonitoringHealth, ClientInfo, ClientCreate, ClientUpdate, UserClientAssign, UserWithClients, AIConfigInfo, AIConfigCreate, AIProviderInfo, AITestResult } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000, // 5 minutes for long uploads with Gemini analysis
  withCredentials: true, // Send cookies automatically
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor — add CSRF token header on mutating requests
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

// Interceptor — notify on 401 (except auth endpoints to avoid login loop)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const url = error.config?.url || '';
      // Don't redirect on auth endpoints — AuthContext handles those
      const isAuthEndpoint = url.includes('/auth/me') || url.includes('/auth/refresh') || url.includes('/auth/login');
      if (!isAuthEndpoint) {
        window.dispatchEvent(new Event('session-expired'));
      }
    }
    return Promise.reject(error);
  }
);

// ============ AUTH ============
export const authAPI = {
  login: async (username: string, password: string) => {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);

    const response = await api.post('/auth/login', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  logout: async () => {
    const response = await api.post('/auth/logout');
    return response.data;
  },

  refreshToken: async () => {
    const response = await api.post('/auth/refresh');
    return response.data;
  },

  getCurrentUser: async (): Promise<UserInfo> => {
    const response = await api.get('/auth/me');
    return response.data;
  },
};

// ============ DASHBOARD ============
export const dashboardAPI = {
  getStats: async (): Promise<DashboardStats> => {
    const response = await api.get('/dashboard/stats');
    return response.data;
  },
};

// ============ USERS ============
export const usersAPI = {
  list: async (): Promise<UserInfo[]> => {
    const response = await api.get('/users');
    return response.data;
  },

  get: async (id: string): Promise<UserInfo> => {
    const response = await api.get(`/users/${id}`);
    return response.data;
  },

  create: async (data: UserCreate): Promise<UserInfo> => {
    const response = await api.post('/users', data);
    return response.data;
  },

  update: async (id: string, data: UserUpdate): Promise<UserInfo> => {
    const response = await api.put(`/users/${id}`, data);
    return response.data;
  },

  toggle: async (id: string): Promise<UserInfo> => {
    const response = await api.patch(`/users/${id}/toggle`);
    return response.data;
  },

  resetPassword: async (id: string, newPassword: string) => {
    const response = await api.post(`/users/${id}/reset-password`, { new_password: newPassword });
    return response.data;
  },
};

// ============ PROFILE ============
export const profileAPI = {
  get: async (): Promise<UserInfo> => {
    const response = await api.get('/profile');
    return response.data;
  },

  update: async (data: ProfileUpdate): Promise<UserInfo> => {
    const response = await api.put('/profile', data);
    return response.data;
  },

  changePassword: async (data: PasswordChange) => {
    const response = await api.put('/profile/password', data);
    return response.data;
  },
};

// ============ PERFORMANCE (v2.0 - multi-JTL) ============
export const testAPI = {
  extractJTLLabels: async (file: File): Promise<{ labels: string[]; count: number }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/extract-jtl-labels', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  validateJTL: async (files: File[]) => {
    const formData = new FormData();
    files.forEach((f) => formData.append('files', f));

    const response = await api.post('/validate-jtl', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  uploadJTL: async (
    files: File[],
    name: string,
    description: string = '',
    testType: string = 'load',
    client: string = '',
    project: string = '',
    acceptanceCriteria: string = '',
    clientId: string = '',
    metricUnit: string = 'TPS',
  ) => {
    const formData = new FormData();
    files.forEach((f) => formData.append('files', f));

    const params = new URLSearchParams();
    params.append('name', name);
    params.append('description', description);
    params.append('test_type', testType);
    params.append('client', client);
    params.append('project', project);
    params.append('client_id', clientId);
    params.append('acceptance_criteria', acceptanceCriteria);
    params.append('metric_unit', metricUnit);

    const response = await api.post(`/upload?${params.toString()}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  getExecutions: async () => {
    const response = await api.get('/executions');
    return response.data;
  },

  deleteExecution: async (id: string) => {
    const response = await api.delete(`/executions/${id}`);
    return response.data;
  },

  getExecution: async (id: string) => {
    const response = await api.get(`/executions/${id}`);
    return response.data;
  },

  getCharts: async (id: string) => {
    const response = await api.get(`/executions/${id}/charts`);
    return response.data;
  },

  updateAnalysis: async (id: string, data: Record<string, string | undefined>) => {
    const response = await api.put(`/executions/${id}/analysis`, data);
    return response.data;
  },

  exportHTML: async (id: string) => {
    const response = await api.get(`/executions/${id}/export/html`, {
      responseType: 'blob',
    });
    return response.data;
  },

  exportPDF: async (id: string) => {
    const response = await api.get(`/executions/${id}/export/pdf`, {
      responseType: 'blob',
    });
    return response.data;
  },
};

// ============ CLIENTS (Phase 6) ============
export const clientsAPI = {
  list: async (): Promise<ClientInfo[]> => {
    const response = await api.get('/clients');
    return response.data;
  },

  create: async (data: ClientCreate): Promise<ClientInfo> => {
    const response = await api.post('/clients', data);
    return response.data;
  },

  update: async (id: string, data: ClientUpdate): Promise<ClientInfo> => {
    const response = await api.put(`/clients/${id}`, data);
    return response.data;
  },

  delete: async (id: string) => {
    await api.delete(`/clients/${id}`);
  },

  getMyClients: async (): Promise<ClientInfo[]> => {
    const response = await api.get('/clients/user-clients');
    return response.data;
  },

  getAssignments: async (): Promise<UserWithClients[]> => {
    const response = await api.get('/clients/assignments');
    return response.data;
  },

  assign: async (data: UserClientAssign) => {
    const response = await api.post('/clients/assignments', data);
    return response.data;
  },

  unassign: async (userId: string, clientId: string) => {
    await api.delete(`/clients/assignments/${userId}/${clientId}`);
  },
};

// ============ AI CONFIG ============
export const aiConfigAPI = {
  get: async (): Promise<AIConfigInfo> => {
    const response = await api.get('/ai-config');
    return response.data;
  },

  save: async (data: AIConfigCreate): Promise<AIConfigInfo> => {
    const response = await api.post('/ai-config', data);
    return response.data;
  },

  getModels: async (): Promise<AIProviderInfo[]> => {
    const response = await api.get('/ai-config/models');
    return response.data;
  },

  test: async (): Promise<AITestResult> => {
    const response = await api.post('/ai-config/test');
    return response.data;
  },

  resetUsage: async () => {
    const response = await api.post('/ai-config/reset-usage');
    return response.data;
  },

  getModelsLive: async (provider: string): Promise<LiveModelsResponse> => {
    const response = await api.get('/ai-config/models/live', { params: { provider } });
    return response.data;
  },
};

export interface LiveModelsResponse {
  provider: string;
  models: string[];
  is_live: boolean;
  message: string | null;
}

// ============ MONITORING (Phase 4) ============
export const monitoringAPI = {
  getConfig: async (): Promise<MonitoringConfig> => {
    const response = await api.get('/monitoring/config');
    return response.data;
  },

  updateConfig: async (data: MonitoringConfigUpdate): Promise<MonitoringConfig> => {
    const response = await api.put('/monitoring/config', data);
    return response.data;
  },

  getHealth: async (): Promise<MonitoringHealth> => {
    const response = await api.get('/monitoring/health');
    return response.data;
  },
};

// =========================================================================
// Integrated Reports API
// =========================================================================
export interface IntegratedReportSummary {
  id: string;
  name: string;
  section_count: number;
  has_consolidated: boolean;
  created_at: string;
  updated_at: string;
  created_by?: string | null;
}

export interface IntegratedReportDetail extends IntegratedReportSummary {
  sections: any[];
  consolidated_analysis: Record<string, any>;
}

export const integratedReportsAPI = {
  list: async (): Promise<IntegratedReportSummary[]> => {
    const response = await api.get('/reports/integrated-reports');
    return response.data;
  },

  getById: async (id: string): Promise<IntegratedReportDetail> => {
    const response = await api.get(`/reports/integrated-reports/${id}`);
    return response.data;
  },

  update: async (
    id: string,
    payload: Partial<Pick<IntegratedReportDetail, 'name' | 'sections' | 'consolidated_analysis'>>
  ): Promise<IntegratedReportDetail> => {
    const response = await api.patch(`/reports/integrated-reports/${id}`, payload);
    return response.data;
  },

  remove: async (id: string): Promise<void> => {
    await api.delete(`/reports/integrated-reports/${id}`);
  },
};

// =========================================================================
// AI Script Designs API — Persistencia de sesiones del Diseñador IA
// =========================================================================

export type AIDesignReferenceFileType = 'postman' | 'openapi' | 'swagger' | 'har' | 'jmx' | 'text';

export interface AIConversationMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string | null;
}

export interface AIScriptDesignSummary {
  id: string;
  session_id: string;
  name: string | null;
  client_id: string;
  user_id: string | null;
  is_draft: boolean;
  message_count: number;
  has_jmx: boolean;
  reference_file_name: string | null;
  reference_file_type: AIDesignReferenceFileType | null;
  created_at: string;
  updated_at: string;
}

export interface AIScriptDesignDetail {
  id: string;
  session_id: string;
  name: string | null;
  client_id: string;
  user_id: string | null;
  is_draft: boolean;
  conversation: AIConversationMessage[];
  current_jmx: string | null;
  reference_file_name: string | null;
  reference_file_content: string | null;
  reference_file_type: AIDesignReferenceFileType | null;
  created_at: string;
  updated_at: string;
}

export interface AIScriptDesignUpsertPayload {
  session_id: string;
  client_id: string;
  conversation: AIConversationMessage[];
  current_jmx?: string | null;
  reference_file_name?: string | null;
  reference_file_content?: string | null;
  reference_file_type?: AIDesignReferenceFileType | null;
}

export interface AIScriptDesignSaveAsPayload {
  name: string;
  client_id?: string;
}

export const aiScriptDesignsAPI = {
  list: async (params?: {
    client_id?: string;
    include_drafts?: boolean;
  }): Promise<AIScriptDesignSummary[]> => {
    const response = await api.get('/script-designer/ai/designs', {
      params: {
        client_id: params?.client_id,
        include_drafts: params?.include_drafts ?? false,
      },
    });
    return response.data;
  },

  getById: async (id: string): Promise<AIScriptDesignDetail> => {
    const response = await api.get(`/script-designer/ai/designs/${id}`);
    return response.data;
  },

  getLastDraft: async (): Promise<AIScriptDesignDetail | null> => {
    const response = await api.get('/script-designer/ai/designs/last-draft');
    return response.data;
  },

  upsert: async (payload: AIScriptDesignUpsertPayload): Promise<AIScriptDesignDetail> => {
    const response = await api.post('/script-designer/ai/designs/upsert', payload);
    return response.data;
  },

  saveAs: async (
    id: string,
    payload: AIScriptDesignSaveAsPayload
  ): Promise<AIScriptDesignDetail> => {
    const response = await api.patch(`/script-designer/ai/designs/${id}/save-as`, payload);
    return response.data;
  },

  remove: async (id: string): Promise<void> => {
    await api.delete(`/script-designer/ai/designs/${id}`);
  },
};


// =========================================================================
// AI Script Structure API — Parse/Regenerate JMX (Sprint 2.x)
// =========================================================================
import type { AIScriptStructure } from '../types/aiScriptStructure';

export interface RegenerateJmxResponse {
  jmx_text: string;
  size_chars: number;
}

export const aiScriptStructureAPI = {
  parseJmx: async (jmx_text: string): Promise<AIScriptStructure> => {
    const response = await api.post('/script-designer/ai/parse-jmx', { jmx_text });
    return response.data;
  },

  regenerateJmx: async (structure: AIScriptStructure): Promise<RegenerateJmxResponse> => {
    const response = await api.post('/script-designer/ai/regenerate-jmx', structure);
    return response.data;
  },
};


// =========================================================================
// AI Design Data Files API (Sprint 2.4-HF2)
// =========================================================================

export interface AIDesignDataFile {
  id: string;
  design_id: string;
  original_filename: string;
  file_size: number;
  delimiter: string;
  encoding: string;
  columns: string[];
  row_count: number;
  variable_mapping: Record<string, string>;
  created_at: string;
  updated_at: string;
}

export interface AIDesignDataFilePreview {
  columns: string[];
  rows: string[][];
  row_count_total: number;
  delimiter_detected: string;
  encoding_detected: string;
}

export const aiDesignDataFilesAPI = {
  list: async (designId: string): Promise<AIDesignDataFile[]> => {
    const r = await api.get(`/script-designer/ai/designs/${designId}/data-files`);
    return r.data;
  },

  upload: async (
    designId: string,
    file: File,
    delimiter: string = ',',
    has_header: string = 'true',
    encoding: string = 'UTF-8',
  ): Promise<AIDesignDataFile> => {
    const form = new FormData();
    form.append('file', file);
    form.append('delimiter', delimiter);
    form.append('has_header', has_header);
    form.append('encoding', encoding);
    const r = await api.post(
      `/script-designer/ai/designs/${designId}/data-files`,
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
    return r.data;
  },

  preview: async (designId: string, fileId: string): Promise<AIDesignDataFilePreview> => {
    const r = await api.get(`/script-designer/ai/designs/${designId}/data-files/${fileId}/preview`);
    return r.data;
  },

  updateMapping: async (
    designId: string,
    fileId: string,
    mapping: Record<string, string>,
  ): Promise<AIDesignDataFile> => {
    const r = await api.patch(
      `/script-designer/ai/designs/${designId}/data-files/${fileId}`,
      { variable_mapping: mapping },
    );
    return r.data;
  },

  remove: async (designId: string, fileId: string): Promise<void> => {
    await api.delete(`/script-designer/ai/designs/${designId}/data-files/${fileId}`);
  },
};


export default api;
