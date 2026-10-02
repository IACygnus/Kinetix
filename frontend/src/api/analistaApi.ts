/**
 * «Analista IA» — BLOQUE 5. Los tipos son el contrato del reporte 147 (§3 y §4).
 */
import api from '../services/api';

export type EstadoResultado = 'cumple' | 'no_cumple' | 'no_evaluado' | 'lo_confirma_el_analista';
export type EstadoCriterios = 'sin_declarar' | 'declarados' | 'no_hay_criterios_acordados';

export interface ResultadoCriterio {
  estado: EstadoResultado;
  medido: number | null;
  unidad: string | null;
  texto: string;
  motivo: string | null;
  nota: string | null;
}

export interface Criterio {
  id: string;
  texto: string;
  tipo: string;
  metrica: string | null;
  operador: string | null;
  valor: number | null;
  unidad: string | null;
  cantidad: number | null;
  alcance: { tipo: 'global' | 'transaccion' | 'cada_transaccion'; transaccion: string | null };
  origen: 'chat' | 'manual';
  en_motor: boolean;
  confirmacion: 'cumple' | 'no_cumple' | null;
  resultado: ResultadoCriterio;
}

export interface Pendiente {
  id: string;
  obligatorio: boolean;
  pregunta: string;
  estado: 'pendiente' | 'resuelto' | 'descartado';
  respuesta: string | null;
}

export interface TransaccionFicha {
  label: string;
  muestras: number;
  promedio: number;
  p90: number;
  max: number;
  tps: number;
  errores: number;
  tasa_error: number;
  critica: boolean;
  verdict: string | null;
  motivo: string;
  informe: boolean;
  informe_origen: 'auto' | 'analista';
}

export interface AdjuntoCorto {
  id: string;
  nombre: string;
  errores: number;
  grupos: number;
  cuadra: boolean;
  cruce: string;
}

export interface Ficha {
  version: number;
  prueba: { cliente: string | null; cliente_id: string | null; proyecto: string; tipo: string; unidad: string; jtl: string[] };
  cifras: {
    peticiones: number; errores: number; tasa_error: number; promedio_ms: number; mediana_ms: number;
    p90_ms: number; p95_ms: number; p99_ms: number; max_ms: number; caudal: number; duracion_s: number;
    inicio: string | null; fin: string | null; redirecciones: number;
  };
  fases: {
    disponible: boolean; max_usuarios: number | null; subida_hasta_s: number | null; bajada_desde_s: number | null;
    duracion_s: number; sin_subida: boolean; sin_bajada: boolean; motivo: string | null; texto: string;
  };
  serie?: { paso_s: number; puntos: [number, number | null, number][] };
  fallos: { total: number; concentracion: string | null; concentrados: boolean };
  transacciones: TransaccionFicha[];
  transacciones_tope: number;
  criterios: { estado: EstadoCriterios; ninguno_acordado: boolean; lista: Criterio[] };
  relato: { id: string; texto: string; origen: string; creado: string }[];
  contexto: { ambiente: string | null; version: string | null };
  errores_detalle: { adjuntos: AdjuntoCorto[] };
  pendientes: Pendiente[];
  listo: {
    n: number; m: number;
    obligatorios: { listos: number; total: number };
    opcionales: { listos: number; total: number };
    puede_generar: boolean;
    faltan: string[];
  };
}

export interface Mensaje {
  id: string;
  rol: 'ia' | 'analista';
  texto: string;
  momento: string;
  origen: 'ia' | 'fijo' | 'error' | null;
  pregunta: boolean;
  cambios: Record<string, unknown> | null;
  avisos: string[];
}

export interface GrupoErrores {
  transaccion: string;
  codigo: string | null;
  mensaje: string;
  recuento: number;
  porcentaje: number;
  primero: string | null;
  ultimo: string | null;
}

export interface Adjunto {
  id: string;
  nombre: string;
  formato: 'csv' | 'xml';
  tamano: number;
  execution_id: string | null;
  creado: string;
  resumen: { errores: number; grupos_total: number; grupos: GrupoErrores[]; cruce: { cuadra: boolean; texto: string }; avisos: string[] };
}

export interface Sesion {
  id: string;
  estado: 'abierta' | 'generando' | 'generada';
  cliente: string | null;
  cliente_id: string | null;
  proyecto: string;
  tipo: string;
  unidad: string;
  jtl: string[];
  ficha: Ficha;
  mensajes: Mensaje[];
  adjuntos: Adjunto[];
  execution_id: string | null;
  creada: string;
  actualizada: string | null;
  turno?: { ok: boolean };
}

export interface SesionResumen {
  id: string;
  estado: Sesion['estado'];
  cliente: string | null;
  proyecto: string;
  tipo: string;
  criterios: EstadoCriterios | null;
  listo: Ficha['listo'] | null;
  execution_id: string | null;
  creada: string;
  actualizada: string | null;
}

export interface CambiosFicha {
  transacciones?: Record<string, boolean>;
  relato?: { agregar?: string[]; editar?: { id: string; texto: string }[]; quitar?: string[] };
  criterios?: {
    quitar?: string[];
    editar?: { id: string; confirmacion?: 'cumple' | 'no_cumple' | null }[];
    ninguno_acordado?: boolean;
  };
  contexto?: { ambiente?: string | null; version?: string | null };
  pendientes?: { descartar?: string[]; reabrir?: string[] };
}

export interface ResultadoGenerar {
  resultado: 'generado' | 'faltan_criterios';
  execution_id?: string;
  ai_status?: { respaldo?: number; secciones?: number; motivo_frase?: string; motivo?: string | null; error?: string | null };
  mensaje?: string;
  sesion: Sesion;
}

/** El texto de error que manda el backend, o uno genérico. */
export function detalleError(err: unknown, porDefecto: string): string {
  const e = err as { response?: { status?: number; data?: { detail?: unknown } } };
  const d = e.response?.data?.detail;
  if (typeof d === 'string') return d;
  if (Array.isArray(d) && d.length) return 'Datos no válidos: ' + d.map((x: { msg?: string }) => x.msg).join('; ');
  return porDefecto;
}

export function codigoError(err: unknown): number | undefined {
  return (err as { response?: { status?: number } }).response?.status;
}

const BASE = '/analista/sesiones';

export const analistaAPI = {
  crear: async (datos: { files: File[]; proyecto: string; tipo: string; clientId: string; unidad: string }): Promise<Sesion> => {
    const fd = new FormData();
    datos.files.forEach((f) => fd.append('files', f));
    fd.append('proyecto', datos.proyecto);
    fd.append('tipo', datos.tipo);
    fd.append('client_id', datos.clientId);
    fd.append('unidad', datos.unidad);
    const r = await api.post(BASE, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
    return r.data;
  },
  listar: async (): Promise<SesionResumen[]> => (await api.get(BASE)).data,
  leer: async (id: string): Promise<Sesion> => (await api.get(`${BASE}/${id}`)).data,
  cambiar: async (id: string, cambios: CambiosFicha): Promise<Sesion> => (await api.patch(`${BASE}/${id}`, cambios)).data,
  cambiarPrueba: async (id: string, datos: { proyecto: string; tipo: string; client_id: string; unidad: string }): Promise<Sesion> =>
    (await api.put(`${BASE}/${id}/prueba`, datos)).data,
  adjuntar: async (id: string, archivo: File): Promise<Sesion> => {
    const fd = new FormData();
    fd.append('archivo', archivo);
    const r = await api.post(`${BASE}/${id}/adjuntos`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
    return r.data;
  },
  mensaje: async (id: string, texto: string): Promise<Sesion> => (await api.post(`${BASE}/${id}/mensajes`, { texto })).data,
  /** 409 «faltan_criterios» no es un error para la pantalla: se devuelve igual. */
  generar: async (id: string): Promise<ResultadoGenerar> => {
    try {
      return (await api.post(`${BASE}/${id}/generar`)).data;
    } catch (err) {
      const e = err as { response?: { status?: number; data?: ResultadoGenerar } };
      if (e.response?.status === 409 && e.response.data?.resultado === 'faltan_criterios') return e.response.data;
      throw err;
    }
  },
};
