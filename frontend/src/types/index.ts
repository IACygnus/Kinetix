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
  reasoning_effort?: string | null;   // ETAPA 2 (D13): low | medium | high
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

// ===================== ETAPA O1.6 — la configuración para JMeter =====================

/** Un parámetro del `InfluxdbBackendListenerClient`, listo para copiar. */
export interface ArgumentoJMeter {
  nombre: string;
  valor: string;
  explicacion: string;
  /** El token: se tapa hasta que se pide, para que no salga en una captura. */
  secreto: boolean;
}

/** Lo que hay que poner en el Backend Listener de una corrida (O-D5). */
export interface ConfiguracionJMeter {
  /** El nombre de la corrida (O-D4). Es la etiqueta por la que filtra el tablero. */
  application: string;
  clase_listener: string;
  argumentos: ArgumentoJMeter[];
  /** El tablero de Grafana ya filtrado por esta corrida (O-D6). */
  url_tablero: string;
  aviso: string;
}

// ===========================================================================
// OBSERVABILIDAD — los servidores observados (ETAPA O2c)
// ===========================================================================

export type TipoServidor = 'linux' | 'windows' | 'postgresql' | 'otro';
export type ModoServidor = 'sin_agente' | 'agente';

/**
 * Lo que la API devuelve de un servidor.
 *
 * O-D26: **aquí no hay credencial, y no puede haberla.** Lo único que se sabe
 * es si la tiene. Se escribe una vez y no vuelve a salir.
 */
export interface ServidorObservado {
  id: string;
  client_id: string;
  cliente_nombre?: string | null;
  name: string;
  tipo: TipoServidor;
  modo: ModoServidor;
  direccion: string;
  puerto: number;
  usuario?: string | null;
  activo: boolean;
  notas?: string | null;
  tiene_credencial: boolean;
  creado_en?: string | null;
  actualizado_en?: string | null;
}

export interface ComprobacionLectura {
  que: string;
  ok: boolean;
  detalle: string;
}

/** O-D24: si se llega, qué se lee, y el error REAL cuando falla. */
export interface ResultadoPrueba {
  ok: boolean;
  resumen: string;
  error?: string | null;
  lecturas: ComprobacionLectura[];
  duracion_ms: number;
}

export interface ParametroConfiguracion {
  nombre: string;
  valor: string;
  explicacion: string;
  secreto: boolean;
}

/** O-D25: lo que hay que poner, según el modo del servidor. */
export interface ConfiguracionServidor {
  servidor: string;
  modo: ModoServidor;
  titulo: string;
  explicacion: string;
  parametros: ParametroConfiguracion[];
  orden?: string | null;
  aviso: string;
}

// ===========================================================================
// OBSERVABILIDAD — las sesiones de monitoreo (ETAPA O2d)
// ===========================================================================

export type EstadoSesion = 'preparada' | 'en_curso' | 'terminada';

export interface ServidorDeSesion {
  id: string;
  name: string;
  tipo: TipoServidor;
  modo: ModoServidor;
  direccion: string;
}

/**
 * Una sesión GUARDADA (O-D35).
 *
 * Hasta O2c, una corrida era una cadena que había que copiar antes de cambiar
 * de pestaña. Aquí vive en la base: sales, vuelves, y sigue con sus métricas.
 */
export interface SesionMonitoreo {
  id: string;
  nombre: string;
  client_id: string;
  cliente_nombre?: string | null;
  proyecto: string;
  corrida: string;
  estado: EstadoSesion;
  notas?: string | null;
  servidores: ServidorDeSesion[];
  creada_en?: string | null;
  empezo_en?: string | null;
  termino_en?: string | null;
}

export interface SerieMetrica {
  etiqueta: string;
  unidad: string;
  /** [[milisegundos, valor], ...] — ya ordenados por tiempo. */
  puntos: number[][];
}

export interface GraficaServidor {
  titulo: string;
  explicacion: string;
  unidad: string;
  series: SerieMetrica[];
}

export interface MetricasDeServidor {
  servidor: string;
  tipo: string;
  graficas: GraficaServidor[];
}

/** O-D39: arriba la prueba, abajo la infraestructura, el mismo eje de tiempo. */
export interface MetricasDeSesion {
  corrida: string;
  desde: string;
  hasta: string;
  prueba: GraficaServidor[];
  infraestructura: MetricasDeServidor[];
  /** El motivo EXACTO cuando no hay nada que pintar. Una gráfica vacía sin
   *  explicación es el peor resultado posible: parece que el producto no va. */
  aviso: string;
  hay_datos: boolean;
}

export interface ConexionJMeter {
  url: string;
  token: string;
  corrida: string;
  parametros: { nombre: string; valor: string; explicacion: string }[];
  aviso: string;
}
