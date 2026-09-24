/**
 * Cliente de API del MÓDULO DE HORAS (ETAPA H1).
 *
 * Todo cuelga de `/time` (H-D9). Reusa el `api` de axios del resto de Kinetix,
 * que ya lleva las cookies httpOnly y el interceptor de CSRF: el módulo no
 * necesita nada propio para autenticarse.
 */
import api from '../services/api';

/** El cliente axios de Kinetix manda `application/json` por defecto. Para subir
 *  un archivo hay que decirlo explícitamente —como hacen todas las subidas del
 *  módulo de análisis—, o el multipart viaja sin su frontera y FastAPI contesta
 *  un 422 que no dice nada útil. */
const MULTIPART = { headers: { 'Content-Type': 'multipart/form-data' } };

/** Axios manda las listas como `seccion[]=a&seccion[]=b`, y FastAPI espera
 *  `seccion=a&seccion=b`: con los corchetes **no ve el parámetro y se queda con
 *  el valor por defecto**, sin dar ningún error. Es lo que hacía que quitar una
 *  sección del informe no quitara nada. */
const LISTAS = { paramsSerializer: { indexes: null as null } };

/** El mensaje de un error de la API, **siempre como texto**.
 *
 *  Un 422 de FastAPI trae `detail` como una lista de objetos, no como una
 *  cadena; metida tal cual en el JSX, React revienta la pantalla entera con
 *  «Objects are not valid as a React child» y el usuario se queda en blanco
 *  sin saber qué pasó. */
export const mensajeDeError = (e: any, porDefecto: string): string => {
  const d = e?.response?.data?.detail;
  if (typeof d === 'string' && d) return d;
  if (Array.isArray(d) && d.length) {
    const partes = d
      .map((x: any) => (typeof x === 'string' ? x : x?.msg))
      .filter(Boolean);
    if (partes.length) return partes.join('. ');
  }
  return porDefecto;
};

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

/**
 * ETAPA H8 (§3.1): **el estado del proyecto**. Lo decide una persona y no lo
 * deduce el sistema. Es la otra columna de §5.1, y no tiene nada que ver con
 * `EstadoDesfase`: una dice en qué punto está el trabajo y la otra cuántas
 * horas lleva gastadas.
 *
 * Lo que puede hacerse en cada estado **no se escribe aquí**: viene resuelto
 * del backend en `can_log_hours` y `can_edit_estimates`. Una segunda copia de
 * esa tabla en TypeScript acabaría permitiendo lo que el backend rechaza.
 */
export type EstadoProyecto =
  | 'pendiente' | 'en_ejecucion' | 'detenido' | 'no_viable' | 'finalizado';

/** El ESTADO de un proyecto, tal como lo devuelve el backend. */
export interface ConEstado {
  status: EstadoProyecto;
  status_label: string;
}

/** ETAPA H2b (§5.1). Se dice «desfase», no «exceso» (H-D27).
 *
 *  ETAPA H8 (H-D82): son **cuatro**. `cerrado` salió de aquí —cerrar un
 *  proyecto es un estado, no una forma de gastar horas— y «en rango» vuelve a
 *  leerse «En rango», porque «En ejecución» es ahora un estado.
 */
export type EstadoDesfase =
  | 'en_rango' | 'por_agotarse' | 'terminado' | 'desfasado';

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

export interface Proyecto extends Desfase, ConEstado {
  id: string;
  client_id: string;
  client_name: string;
  name: string;
  description?: string | null;
  created_at: string;
  total_estimated_hours: string | number;
  total_consumed_hours: string | number;
  activities_count: number;
  /** ETAPA H8 (§3.1), ya resueltos por el backend. **No se recalculan aquí.** */
  can_log_hours: boolean;
  can_edit_estimates: boolean;
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

/** ETAPA H8 (H-D83): una línea del historial de estados. */
export interface CambioDeEstado {
  id: string;
  previous_status: EstadoProyecto | null;
  previous_label: string;
  new_status: EstadoProyecto;
  new_label: string;
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

// ===================== EL INFORME (ETAPA H5, §7) =====================

/** Las ocho secciones de §7.2 (v1.3), en su orden y con su nombre. */
export const SECCIONES_INFORME: { clave: string; titulo: string }[] = [
  { clave: 'resumen', titulo: 'Resumen' },
  { clave: 'personas', titulo: 'Ocupación por persona' },
  { clave: 'facturacion', titulo: 'Facturable frente a no facturable' },
  { clave: 'clientes', titulo: 'Cobertura por cliente' },
  { clave: 'actividades', titulo: 'En qué se fue el tiempo' },
  { clave: 'proyectos', titulo: 'Consumido frente a estimado' },
  { clave: 'mapa', titulo: 'Mapa del mes' },
  // H-D68: «Días sin registrar» y «Horas día a día» salieron del informe.
  { clave: 'detalle', titulo: 'Detalle de registros' },
];



export interface FiltrosInforme {
  desde: string;
  hasta: string;
  user_id?: string[];
  client_id?: string;
  project_id?: string;
  solo_facturables?: boolean;
  /** H-D74: a quién va dirigido el informe. Vacío = el valor por defecto. */
  dirigido_a?: string;
}

export interface InformeResumen {
  total_hours: string | number;
  ordinary_hours: string | number;
  overtime_hours: string | number;
  billable_hours: string | number;
  billable_pct: string | number;
  pending_days: number;
  expected_hours: string | number;
  people_count: number;
  projects_count: number;
  entries_count: number;
}

export interface InformePersona {
  user_id: string;
  user_name: string;
  expected_hours: string | number;
  total_hours: string | number;
  ordinary_hours: string | number;
  overtime_hours: string | number;
  billable_hours: string | number;
  occupancy_pct: string | number;
  pending_days: number;
}

export interface InformeFacturacion {
  client_name: string;
  billable_hours: string | number;
  non_billable_hours: string | number;
  total_hours: string | number;
  billable_pct: string | number;
}

export interface InformeReparto {
  name: string;
  hours: string | number;
  pct: string | number;
}

export interface InformeMapaPersona {
  user_id: string;
  user_name: string;
  por_dia: (string | number)[];
  /** ETAPA H8 (H-D85): las horas extra de cada día, alineadas con `por_dia`.
   *  La casilla se parte en proporción a las de cada tipo. */
  extra_por_dia: (string | number)[];
  estados: string[];
  total_hours: string | number;
}

export interface InformePendiente {
  user_name: string;
  date: string;
  expected_hours: string | number;
  ordinary_hours: string | number;
  missing_hours: string | number;
}

export interface InformeFilaDiaria {
  client_name: string;
  project_name: string;
  activity_name: string;
  por_dia: (string | number)[];
  total_hours: string | number;
}

export interface InformeCapacidad {
  working_days: number;
  hours_per_analyst: string | number;
  people_count: number;
  total_hours: string | number;
}

export interface Informe {
  filtros: {
    desde: string; hasta: string; periodo: string; personas: string[];
    alcance: string; client_name: string; project_name: string;
    solo_facturables: boolean; dirigido_a: string;
  };
  dias: string[];
  capacidad: InformeCapacidad;
  resumen: InformeResumen;
  personas: InformePersona[];
  facturacion: InformeFacturacion[];
  por_cliente: InformeReparto[];
  por_actividad: InformeReparto[];
  proyectos: ConsultaProyecto[];
  mapa: InformeMapaPersona[];
  pendientes: InformePendiente[];
  diarias: InformeFilaDiaria[];
  detalle: Registro[];
  detalle_total: number;
  generado: string;
}

/** Lo que devuelve una descarga: el archivo, su nombre y, en PDF, sus páginas. */
export interface Descarga {
  blob: Blob;
  nombre: string;
  paginas?: number;
}

// ===================== IMPORTACIÓN (ETAPA H3, §6) =====================

export type AccionFila = 'nueva' | 'actualiza' | 'invalida';

export interface FilaImportacion {
  /** El número de fila **del archivo**, para poder ir a mirarla (H-D40). */
  numero: number;
  accion: AccionFila;
  motivo: string;
  external_id: string;
  date?: string | null;
  client_name: string;
  project_name: string;
  /** Ya traducida por la tabla de sinónimos: es la que se va a guardar. */
  activity_name: string;
  /** Lo que decía el archivo, solo cuando la tabla lo tradujo a otra cosa. */
  activity_original: string;
  hours?: string | number | null;
  billable: boolean;
  overtime: boolean;
  notes: string;
  crea_cliente: boolean;
  crea_proyecto: boolean;
  crea_actividad: boolean;
  overrun_status: EstadoDesfase;
  overrun_hours: string | number;
  overrun_label: string;
  cambia_de_persona: boolean;
}

export interface ProyectoAImportar {
  client_name: string;
  project_name: string;
}

/**
 * Una actividad del archivo que NO estaba en el catálogo (§4 de la carga real).
 *
 * No es un error —se crea igual—, pero lleva sus filas y sus horas porque con
 * el nombre a secas no se puede decidir si lo que falta es un sinónimo en
 * `services/horas/sinonimos_actividad.py` o si de verdad es una actividad nueva.
 */
export interface ActividadNueva {
  name: string;
  filas: number[];
  horas: string | number;
}

export interface VistaPrevia {
  sheet: string;
  sheets: string[];
  user_id: string;
  user_name: string;
  total_filas: number;
  nuevas: FilaImportacion[];
  actualizadas: FilaImportacion[];
  invalidas: FilaImportacion[];
  desfasadas: FilaImportacion[];
  clientes_a_crear: string[];
  proyectos_a_crear: ProyectoAImportar[];
  actividades_a_crear: string[];
  actividades_nuevas: ActividadNueva[];
  total_horas: string | number;
}

export interface ProyectoCreado {
  id: string;
  name: string;
  client_name: string;
}

export interface ResumenImportacion {
  creados: number;
  actualizados: number;
  omitidos: number;
  total_horas: string | number;
  clientes_creados: string[];
  actividades_creadas: string[];
  actividades_nuevas: ActividadNueva[];
  proyectos_creados: ProyectoCreado[];
  user_id: string;
  user_name: string;
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
export interface ConsultaProyecto extends Desfase, ConEstado {
  project_id: string;
  project_name: string;
  client_id: string;
  client_name: string;
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
  /** H-D84: por defecto se esconden los finalizados y los no viables. */
  incluir_finalizados?: boolean;
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
  // ---------- El informe (H5, §7) ----------
  informe: async (f: FiltrosInforme): Promise<Informe> =>
    (await api.get('/time/informe', { params: f, ...LISTAS })).data,

  /** El documento, como archivo. Se pide con axios y no con un `<iframe src>`
   *  para que viaje la cookie de sesión sin depender de cómo el navegador trate
   *  un marco de otro origen; después se enseña o se descarga desde un blob. */
  documentoInforme: async (
    formato: 'html' | 'pdf' | 'csv',
    f: FiltrosInforme,
    extra: { seccion?: string[]; descargar?: boolean } = {},
  ): Promise<Descarga> => {
    const r = await api.get(`/time/informe/${formato}`, {
      params: { ...f, ...extra }, responseType: 'blob', ...LISTAS,
    });
    const cd: string = r.headers['content-disposition'] || '';
    const m = /filename="([^"]+)"/.exec(cd);
    const paginas = r.headers['x-total-paginas'];
    return {
      blob: r.data,
      nombre: m ? m[1] : `informe-horas.${formato}`,
      paginas: paginas ? Number(paginas) : undefined,
    };
  },

  // ---------- Importación (H3, §6) ----------
  /** Analiza el archivo y devuelve qué pasaría. **No escribe nada** (§6.2.5). */
  vistaPreviaImportacion: async (archivo: File, userId?: string): Promise<VistaPrevia> => {
    const datos = new FormData();
    datos.append('archivo', archivo);
    if (userId) datos.append('user_id', userId);
    // El cliente axios manda 'application/json' por defecto: sin esta cabecera
    // el multipart llega sin su frontera y FastAPI contesta 422.
    return (await api.post('/time/import/preview', datos, MULTIPART)).data;
  },

  /** Aplica la importación en una transacción (H-D41). */
  confirmarImportacion: async (archivo: File, userId?: string): Promise<ResumenImportacion> => {
    const datos = new FormData();
    datos.append('archivo', archivo);
    if (userId) datos.append('user_id', userId);
    return (await api.post('/time/import/confirm', datos, MULTIPART)).data;
  },

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
  listarProyectos: async (filtros?: {
    client_id?: string;
    /** Uno de los cinco de §3.1. Vacío = el filtro por defecto de H-D84. */
    estado?: EstadoProyecto;
    /** H-D84: trae también los finalizados y los no viables. */
    incluir_finalizados?: boolean;
    texto?: string;
  }): Promise<Proyecto[]> =>
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

  /** ETAPA H8 (H-D83): el estado del proyecto, con su historial.
   *
   *  Sustituye a `cerrarProyecto`/`reabrirProyecto`, que eran el mismo cambio
   *  con dos botones y solo llegaban a uno de los cinco estados. */
  cambiarEstadoProyecto: async (id: string, status: EstadoProyecto): Promise<ProyectoDetalle> =>
    (await api.post(`/time/projects/${id}/estado`, { status })).data,

  /** Añadir una actividad al proyecto o cambiar su estimación (escribe historial). */
  guardarActividadDeProyecto: async (
    projectId: string, activity_id: string, estimated_hours: number,
  ): Promise<ProyectoDetalle> =>
    (await api.put(`/time/projects/${projectId}/actividades`, { activity_id, estimated_hours })).data,

  quitarActividadDeProyecto: async (projectId: string, activityId: string): Promise<ProyectoDetalle> =>
    (await api.delete(`/time/projects/${projectId}/actividades/${activityId}`)).data,

  historial: async (projectId: string): Promise<CambioDeEstimacion[]> =>
    (await api.get(`/time/projects/${projectId}/historial`)).data,

  /** ETAPA H8 (H-D83): el historial de estados. Endpoint aparte del de
   *  estimaciones —aquel va por actividad y este no tiene ninguna—, aunque la
   *  pantalla los enseñe juntos. */
  historialEstado: async (projectId: string): Promise<CambioDeEstado[]> =>
    (await api.get(`/time/projects/${projectId}/historial-estado`)).data,

  // ---------- Importar proyectos y estimaciones (ETAPA H8.5b) ----------

  /** La plantilla con las cinco columnas y dos filas de ejemplo (H-D101). */
  plantillaProyectos: async (): Promise<Blob> =>
    (await api.get('/time/import/proyectos/plantilla', { responseType: 'blob' })).data,

  vistaPreviaProyectos: async (archivo: File): Promise<VistaPreviaProyectos> => {
    const datos = new FormData();
    datos.append('archivo', archivo);
    return (await api.post('/time/import/proyectos/preview', datos, MULTIPART)).data;
  },

  /** Aplica el archivo, todo en una transacción (H-D99). */
  confirmarProyectos: async (archivo: File): Promise<ResumenProyectos> => {
    const datos = new FormData();
    datos.append('archivo', archivo);
    return (await api.post('/time/import/proyectos/confirm', datos, MULTIPART)).data;
  },

  // ---------- Borrado de un periodo (ETAPA H8.5, §4.3) ----------

  /** Qué se borraría. **No escribe nada**: es un `GET`. Solo admin. */
  borradoPreview: async (desde: string, hasta: string): Promise<BorradoPreview> =>
    (await api.get('/time/borrado/preview', { params: { desde, hasta } })).data,

  /** Borra. Las tres condiciones viajan explícitas y el backend las vuelve a
   *  comprobar: lo de la pantalla es comodidad, no seguridad. */
  borradoConfirm: async (datos: {
    desde: string; hasta: string; confirmacion: string; copia_hecha: boolean;
  }): Promise<BorradoResumen> =>
    (await api.post('/time/borrado/confirm', datos)).data,
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
// ====== IMPORTAR PROYECTOS Y ESTIMACIONES (ETAPA H8.5b, H-D94 a H-D101) ======

export interface FilaProyectoImportacion {
  numero: number;
  accion: 'crea' | 'actualiza' | 'igual' | 'invalida';
  motivo: string;
  client_name: string;
  project_name: string;
  activity_name: string;
  activity_original: string;
  status: string;
  status_label: string;
  estimated_hours: string | number | null;
  previous_hours: string | number | null;
  crea_cliente: boolean;
  crea_proyecto: boolean;
  crea_actividad: boolean;
}

export interface ProyectoImportado {
  client_name: string;
  project_name: string;
  status: EstadoProyecto;
  status_label: string;
  es_nuevo: boolean;
  cambia_de_estado: boolean;
  status_anterior_label: string;
  actividades: number;
  /** Lo que suma el proyecto entero en el archivo (H-D99). */
  total_hours: string | number;
  filas: FilaProyectoImportacion[];
}

export interface VistaPreviaProyectos {
  sheet: string;
  sheets: string[];
  total_filas: number;
  proyectos: ProyectoImportado[];
  invalidas: FilaProyectoImportacion[];
  proyectos_nuevos: number;
  proyectos_actualizados: number;
  estimaciones_nuevas: number;
  estimaciones_actualizadas: number;
  estimaciones_iguales: number;
  clientes_a_crear: string[];
  actividades_a_crear: string[];
  actividades_nuevas: ActividadNueva[];
  total_horas: string | number;
}

export interface ResumenProyectos {
  proyectos_creados: { id: string; name: string; client_name: string }[];
  proyectos_actualizados: number;
  estimaciones_creadas: number;
  estimaciones_actualizadas: number;
  estimaciones_iguales: number;
  estados_cambiados: number;
  clientes_creados: string[];
  actividades_creadas: string[];
  actividades_nuevas: ActividadNueva[];
  omitidas: number;
  total_horas: string | number;
}

// ============ BORRADO DE UN PERIODO (ETAPA H8.5, §4.3) ============

export interface BorradoPersona {
  user_name: string;
  entries: number;
  hours: string | number;
}

export interface BorradoPreview {
  desde: string;
  hasta: string;
  periodo: string;
  total_entries: number;
  total_hours: string | number;
  por_persona: BorradoPersona[];
  /** De dónde vinieron: dice si se borra lo que se importó o algo tecleado. */
  de_importacion: number;
  manuales: number;
  /** Lo que hay que teclear, literal. **La pantalla no la compone**: si la
   *  inventara por su cuenta podría no coincidir con la que el backend espera,
   *  y el botón no se activaría nunca. */
  frase_de_confirmacion: string;
  /** El `pg_dump` ya escrito (H-D89). Kinetix no lo ejecuta. */
  comando_copia: string;
  lo_que_no_se_borra: string;
}

export interface BorradoResumen {
  desde: string;
  hasta: string;
  periodo: string;
  entries_deleted: number;
  hours_deleted: string | number;
  performed_by: string;
  performed_at: string;
  lo_que_no_se_borro: string;
}

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
