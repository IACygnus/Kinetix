/**
 * Cliente de API del MÓDULO DE HORAS (ETAPA H1).
 *
 * Todo cuelga de `/time` (H-D9). Reusa el `api` de axios del resto de Kinetix,
 * que ya lleva las cookies httpOnly y el interceptor de CSRF: el módulo no
 * necesita nada propio para autenticarse.
 */
import api from '../services/api';

export interface Actividad {
  id: string;
  name: string;
  is_active: boolean;
  created_at: string;
  /** En cuántos proyectos está. Decide si se puede borrar (H-D4). */
  projects_count: number;
  /** Si tiene horas registradas. Con horas no se borra nunca. */
  has_entries: boolean;
}

export interface ActividadDeProyecto {
  activity_id: string;
  activity_name: string;
  estimated_hours: string | number;
  consumed_hours: string | number;
  remaining_hours: string | number;
  over_estimate: boolean;
}

export interface Proyecto {
  id: string;
  client_id: string;
  client_name: string;
  name: string;
  description?: string | null;
  status: 'activo' | 'cerrado';
  created_at: string;
  total_estimated_hours: string | number;
  total_consumed_hours: string | number;
  activities_count: number;
}

export interface ProyectoDetalle extends Proyecto {
  activities: ActividadDeProyecto[];
}

export interface CambioDeEstimacion {
  id: string;
  activity_id: string;
  activity_name: string;
  previous_hours: string | number | null;
  new_hours: string | number | null;
  change_type: 'alta' | 'cambio' | 'baja';
  changed_by_name: string;
  changed_at: string;
}

// ===================== REGISTRO DE HORAS (ETAPA H2) =====================

export interface Registro {
  id: string;
  user_id: string;
  user_name: string;
  created_by?: string | null;
  created_by_name: string;
  date: string;
  client_id?: string | null;
  client_name: string;
  project_id: string;
  project_name: string;
  project_status: string;
  activity_id: string;
  activity_name: string;
  hours: string | number;
  billable: boolean;
  overtime: boolean;
  notes?: string | null;
  source: string;
  /** H-D16: esa actividad ya pasó de lo estimado en ese proyecto. */
  over_estimate: boolean;
}

export interface Dia {
  date: string;
  expected_hours: string | number;
  ordinary_hours: string | number;
  overtime_hours: string | number;
  total_hours: string | number;
  is_holiday: boolean;
  is_absence: boolean;
  non_working_reason: string;
  incomplete: boolean;
  missing_hours: string | number;
  entries: Registro[];
}

export interface Semana {
  user_id: string;
  user_name: string;
  week_start: string;
  week_end: string;
  days: Dia[];
  total_expected: string | number;
  total_ordinary: string | number;
  total_overtime: string | number;
}

export interface DiaPendiente {
  date: string;
  expected_hours: string | number;
  ordinary_hours: string | number;
  missing_hours: string | number;
  /** El lunes de su semana: es lo que necesita el enlace de H-D18. */
  week_start: string;
}

export interface Disponibilidad {
  activity_id: string;
  activity_name: string;
  estimated_hours: string | number;
  consumed_hours: string | number;
  remaining_hours: string | number;
  over_estimate: boolean;
}

export interface RegistroNuevo {
  user_id?: string;
  date: string;
  project_id: string;
  activity_id: string;
  hours: number;
  billable: boolean;
  overtime: boolean;
  notes?: string;
}

export const horasApi = {
  // ---------- Registro (H2) ----------
  semana: async (fecha: string, userId?: string): Promise<Semana> =>
    (await api.get('/time/week', { params: { fecha, user_id: userId } })).data,

  diasPendientes: async (userId?: string, desde?: string, hasta?: string): Promise<DiaPendiente[]> =>
    (await api.get('/time/pending-days', { params: { user_id: userId, desde, hasta } })).data,

  disponibilidad: async (projectId: string): Promise<Disponibilidad[]> =>
    (await api.get(`/time/projects/${projectId}/disponibilidad`)).data,

  crearRegistro: async (datos: RegistroNuevo): Promise<Registro> =>
    (await api.post('/time/entries', datos)).data,

  editarRegistro: async (id: string, datos: Partial<RegistroNuevo>): Promise<Registro> =>
    (await api.put(`/time/entries/${id}`, datos)).data,

  borrarRegistro: async (id: string): Promise<void> => {
    await api.delete(`/time/entries/${id}`);
  },

  // ---------- Actividades ----------
  listarActividades: async (soloActivas = false): Promise<Actividad[]> =>
    (await api.get('/time/activities', { params: { solo_activas: soloActivas } })).data,

  crearActividad: async (name: string): Promise<Actividad> =>
    (await api.post('/time/activities', { name })).data,

  editarActividad: async (id: string, datos: { name?: string; is_active?: boolean }): Promise<Actividad> =>
    (await api.put(`/time/activities/${id}`, datos)).data,

  borrarActividad: async (id: string): Promise<void> => {
    await api.delete(`/time/activities/${id}`);
  },

  // ---------- Proyectos ----------
  listarProyectos: async (filtros?: { client_id?: string; estado?: string; texto?: string }): Promise<Proyecto[]> =>
    (await api.get('/time/projects', { params: filtros })).data,

  verProyecto: async (id: string): Promise<ProyectoDetalle> =>
    (await api.get(`/time/projects/${id}`)).data,

  crearProyecto: async (datos: {
    client_id: string;
    name: string;
    description?: string;
    activities: { activity_id: string; estimated_hours: number }[];
  }): Promise<ProyectoDetalle> => (await api.post('/time/projects', datos)).data,

  editarProyecto: async (id: string, datos: { name?: string; description?: string }): Promise<ProyectoDetalle> =>
    (await api.put(`/time/projects/${id}`, datos)).data,

  cerrarProyecto: async (id: string): Promise<ProyectoDetalle> =>
    (await api.post(`/time/projects/${id}/cerrar`)).data,

  reabrirProyecto: async (id: string): Promise<ProyectoDetalle> =>
    (await api.post(`/time/projects/${id}/reabrir`)).data,

  /** Añadir una actividad al proyecto o cambiar su estimación (escribe historial). */
  guardarActividadDeProyecto: async (
    projectId: string, activity_id: string, estimated_hours: number,
  ): Promise<ProyectoDetalle> =>
    (await api.put(`/time/projects/${projectId}/actividades`, { activity_id, estimated_hours })).data,

  quitarActividadDeProyecto: async (projectId: string, activityId: string): Promise<ProyectoDetalle> =>
    (await api.delete(`/time/projects/${projectId}/actividades/${activityId}`)).data,

  historial: async (projectId: string): Promise<CambioDeEstimacion[]> =>
    (await api.get(`/time/projects/${projectId}/historial`)).data,
};

/** Horas a texto español: 40 -> "40", 10.5 -> "10,5". */
export const horas = (v: string | number | null | undefined): string => {
  if (v === null || v === undefined) return '—';
  const n = typeof v === 'string' ? parseFloat(v) : v;
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('es-CO', { maximumFractionDigits: 2 });
};

/** H-D8: el paso de 0,25, validado también en el cliente. */
export const esPasoValido = (n: number): boolean =>
  Number.isFinite(n) && n > 0 && Math.round(n * 100) % 25 === 0;

/** `2026-09-14` -> `lunes, 14 de septiembre`. Sin `new Date(iso)`, que
 *  interpreta la cadena como UTC y en Colombia devuelve el día anterior. */
export const fechaLarga = (iso: string): string => {
  const [a, m, d] = iso.split('-').map(Number);
  return new Date(a, m - 1, d).toLocaleDateString('es-CO', {
    weekday: 'long', day: 'numeric', month: 'long',
  });
};

/** `2026-09-14` -> `14/09`. */
export const fechaCorta = (iso: string): string => {
  const [, m, d] = iso.split('-');
  return `${d}/${m}`;
};

/** Suma días a una fecha ISO sin pasar por UTC. */
export const sumarDias = (iso: string, dias: number): string => {
  const [a, m, d] = iso.split('-').map(Number);
  const f = new Date(a, m - 1, d + dias);
  return `${f.getFullYear()}-${String(f.getMonth() + 1).padStart(2, '0')}-${String(f.getDate()).padStart(2, '0')}`;
};

/** Hoy, en ISO y en hora LOCAL.
 *
 *  `toISOString()` no sirve: convierte a UTC, y en Colombia (UTC−5) a partir de
 *  las siete de la tarde devolvería el día siguiente. En un módulo que va de
 *  fechas, eso es un registro puesto en el día equivocado. */
export const hoyISO = (): string => {
  const f = new Date();
  return `${f.getFullYear()}-${String(f.getMonth() + 1).padStart(2, '0')}-${String(f.getDate()).padStart(2, '0')}`;
};

/** El lunes de la semana que contiene esa fecha (mismo criterio que el backend). */
export const lunesDe = (iso: string): string => {
  const [a, m, d] = iso.split('-').map(Number);
  const f = new Date(a, m - 1, d);
  return sumarDias(iso, -((f.getDay() + 6) % 7));
};
