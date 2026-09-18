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

/** ETAPA H2b (§5.1). Se dice «desfase», no «exceso» (H-D27). */
export type EstadoDesfase = 'en_rango' | 'por_agotarse' | 'desfasado';

export interface Desfase {
  consumed_pct: string | number;
  overrun_status: EstadoDesfase;
  overrun_hours: string | number;
  overrun_label: string;
}

export interface ActividadDeProyecto extends Desfase {
  activity_id: string;
  activity_name: string;
  estimated_hours: string | number;
  consumed_hours: string | number;
  remaining_hours: string | number;
  over_estimate: boolean;
}

export interface Proyecto extends Desfase {
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

// ===================== CONSULTA (ETAPA H3, §5) =====================

export interface ConsultaPersona {
  user_id: string;
  user_name: string;
  hours: string | number;
  billable_hours: string | number;
  overtime_hours: string | number;
  entries_count: number;
}

/** Un proyecto en la consulta.
 *
 *  `hours_in_range` es lo del rango consultado; `consumed_hours` es todo lo que
 *  lleva el proyecto **desde siempre**, que es contra lo que se mide el desfase.
 *  No son la misma cifra y no se pintan en la misma columna. */
export interface ConsultaProyecto extends Desfase {
  project_id: string;
  project_name: string;
  client_id: string;
  client_name: string;
  status: string;
  estimated_hours: string | number;
  consumed_hours: string | number;
  remaining_hours: string | number;
  hours_in_range: string | number;
  overtime_in_range: string | number;
  entries_in_range: number;
  people: ConsultaPersona[];
}

export interface Consulta {
  desde: string;
  hasta: string;
  projects: ConsultaProyecto[];
  total_hours: string | number;
  total_overtime: string | number;
  projects_count: number;
  people_count: number;
  overrun_count: number;
}

export interface FiltrosConsulta {
  desde: string;
  hasta: string;
  client_id?: string;
  project_id?: string;
  user_id?: string;
  solo_desfasados?: boolean;
}

/** Una casilla del calendario (ETAPA H2b, §4.1). Viene resuelta del backend. */
export interface DiaDelMes {
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
  entries_count: number;
  /** Alguno de sus registros toca una actividad desfasada (H-D27). */
  has_over_estimate: boolean;
}

export interface Mes {
  user_id: string;
  user_name: string;
  year: number;
  month: number;
  first_day: string;
  last_day: string;
  days: DiaDelMes[];
  total_expected: string | number;
  total_ordinary: string | number;
  total_overtime: string | number;
  pending_days: number;
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
  // ---------- Consulta (H3) ----------
  consulta: async (f: FiltrosConsulta): Promise<Consulta> =>
    (await api.get('/time/consulta', { params: f })).data,

  /** Los días que se despliegan al ampliar una fila (H-D33). */
  diasDeConsulta: async (
    projectId: string, desde: string, hasta: string, userId?: string,
  ): Promise<Registro[]> =>
    (await api.get('/time/consulta/dias', {
      params: { project_id: projectId, desde, hasta, user_id: userId },
    })).data,

  /** El mes entero para el calendario (ETAPA H2b). */
  mes: async (anio: number, mes: number, userId?: string): Promise<Mes> =>
    (await api.get('/time/month', { params: { anio, mes, user_id: userId } })).data,

  /** La semana de esa fecha. El calendario la usa para el detalle del día:
   *  es el único sitio donde vienen los registros con todos sus campos. */
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

/** `2026-09-14` -> `14`. El número del día, para la casilla del calendario. */
export const diaDelMes = (iso: string): number => Number(iso.split('-')[2]);

/** La columna de esa fecha en el calendario: 0 = lunes … 6 = domingo, el mismo
 *  criterio con el que el backend sembró la jornada. */
export const columnaLunesPrimero = (iso: string): number => {
  const [a, m, d] = iso.split('-').map(Number);
  return (new Date(a, m - 1, d).getDay() + 6) % 7;
};

/** `2026, 9` -> `septiembre de 2026`. */
export const nombreDelMes = (anio: number, mes: number): string =>
  new Date(anio, mes - 1, 1).toLocaleDateString('es-CO', { month: 'long', year: 'numeric' });

/** Mueve el par (año, mes) n meses, sin pasar por fechas. */
export const moverMes = (anio: number, mes: number, n: number): { anio: number; mes: number } => {
  const total = anio * 12 + (mes - 1) + n;
  return { anio: Math.floor(total / 12), mes: (total % 12) + 1 };
};

/** El lunes de la semana que contiene esa fecha (mismo criterio que el backend). */
export const lunesDe = (iso: string): string => {
  const [a, m, d] = iso.split('-').map(Number);
  const f = new Date(a, m - 1, d);
  return sumarDias(iso, -((f.getDay() + 6) % 7));
};
