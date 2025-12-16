import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8001/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor para agregar token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const authAPI = {
  login: async (email: string, password: string) => {
    const formData = new FormData();
    formData.append('username', email);
    formData.append('password', password);
    
    const response = await api.post('/auth/login', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  getCurrentUser: async () => {
    const response = await api.get('/auth/me');
    return response.data;
  },
};

export const testAPI = {
  uploadJTL: async (file: File, name: string, description: string = '', acceptanceCriteria: string = '') => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post(
      `/upload?name=${encodeURIComponent(name)}&description=${encodeURIComponent(description)}&acceptance_criteria=${encodeURIComponent(acceptanceCriteria)}`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  getExecutions: async () => {
    const response = await api.get('/executions');
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

  updateAnalysis: async (id: string, data: {
    ai_analysis_summary?: string;
    ai_analysis_errors?: string;
    ai_analysis_response_times?: string;
    ai_analysis_response_time_over_time?: string;
    ai_analysis_throughput?: string;
    ai_analysis_latency?: string;
    ai_analysis_error_rate?: string;
    ai_analysis_codes_per_second?: string;
    ai_analysis_transactions_per_second?: string;
    ai_analysis_active_threads?: string;
  }) => {
    const response = await api.put(`/executions/${id}/analysis`, data);
    return response.data;
  },

  exportHTML: async (id: string) => {
    const response = await api.get(`/executions/${id}/export/html`, {
      responseType: 'blob'
    });
    return response.data;
  },

  exportPDF: async (id: string) => {
    const response = await api.get(`/executions/${id}/export/pdf`, {
      responseType: 'blob'
    });
    return response.data;
  },
};

export default api;