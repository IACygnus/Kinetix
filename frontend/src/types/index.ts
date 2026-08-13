/**
 * Tipos compartidos - SQA Kinetix Pro
 */

export interface UserInfo {
  id: string;
  username: string;
  email: string;
  full_name: string;
  role: 'admin' | 'analyst' | 'viewer';
  is_active: boolean;
  created_at: string;
  updated_at: string;
  created_by?: string | null;
}

export interface UserCreate {
  username: string;
  email: string;
  full_name: string;
  password: string;
  role: string;
  is_active: boolean;
}

export interface UserUpdate {
  username?: string;
  email?: string;
  full_name?: string;
  password?: string;
  role?: string;
  is_active?: boolean;
}

export interface ProfileUpdate {
  full_name?: string;
  email?: string;
}

export interface PasswordChange {
  current_password: string;
  new_password: string;
}

export interface DashboardStats {
  total_reports: number;
  total_users: number;
  last_analysis: string | null;
  recent_reports: RecentReport[];
}

export interface RecentReport {
  id: string;
  name: string;
  jtl_filename: string;
  total_requests: number;
  error_rate: number;
  created_at: string;
}

export type UserRole = 'admin' | 'analyst' | 'viewer';

// Clients (Phase 6)
export interface ClientInfo {
  id: string;
  name: string;
  description?: string | null;
  contact_name?: string | null;
  contact_email?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  has_logo?: boolean;   // N1.3
}

export interface ClientCreate {
  name: string;
  description?: string;
  contact_name?: string;
  contact_email?: string;
}

export interface ClientUpdate {
  name?: string;
  description?: string;
  contact_name?: string;
  contact_email?: string;
  is_active?: boolean;
}

export interface UserClientAssign {
  user_id: string;
  client_id: string;
}

export interface UserWithClients {
  id: string;
  username: string;
  full_name: string;
  role: string;
  is_active: boolean;
  clients: ClientInfo[];
}

// AI Config
export interface AIProviderInfo {
  id: string;
  name: string;
  models: string[];
}

export interface AIConfigInfo {
  id: string;
  provider: string;
  model_name: string;
  api_key_masked: string;
  is_active: boolean;
  daily_request_limit: number;
  monthly_request_limit: number;
  daily_requests_used: number;
  monthly_requests_used: number;
  last_reset_daily: string | null;
  last_reset_monthly: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface AIConfigCreate {
  provider?: string;
  model_name?: string;
  api_key?: string;
  is_active?: boolean;
  daily_request_limit?: number;
  monthly_request_limit?: number;
}

export interface AITestResult {
  status: 'ok' | 'error';
  message: string;
  provider: string;
  model: string;
}

// AI Status (upload response)
export interface AIStatus {
  provider: string; // "gemini" | "openai" | "fallback"
  model: string | null;
  success: boolean;
  error: string | null;
}

// Monitoring (Phase 4)
export interface MonitoringConfig {
  id: string;
  grafana_url: string | null;
  grafana_dashboard_uid: string | null;
  influxdb_url: string | null;
  influxdb_org: string | null;
  influxdb_bucket: string | null;
  has_influxdb_token: boolean;
  is_configured: boolean;
  updated_at: string | null;
  updated_by: string | null;
}

export interface MonitoringConfigUpdate {
  grafana_url?: string;
  grafana_dashboard_uid?: string;
  influxdb_url?: string;
  influxdb_org?: string;
  influxdb_bucket?: string;
  influxdb_token?: string;
}

export interface MonitoringHealth {
  grafana_status: 'ok' | 'error' | 'not_configured' | 'unknown';
  grafana_message: string;
  influxdb_status: 'ok' | 'error' | 'not_configured' | 'unknown';
  influxdb_message: string;
  is_configured: boolean;
}
