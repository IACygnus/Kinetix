/**
 * API Service - JMeter Analyzer Pro v2.0
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
    clientId: string = ''
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
};

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

export default api;
