/**
 * ETAPA 5 (D42) — La regla de criticidad por transacción, en TypeScript.
 *
 * Es un PUERTO LITERAL de lo que hace el backend, no una regla nueva:
 *   · el veredicto  -> `compute_per_transaction_verdicts` (gemini.py, KNX-09)
 *   · las 3 señales -> `POST /extract-jtl-transactions` (upload.py)
 *
 * Existe porque el panel tiene que recalcular la criticidad AL INSTANTE cuando
 * se editan los criterios de una fila (D42), y hasta ahora eso obligaba a
 * resubir el JTL entero al backend con 800 ms de debounce.
 *
 * La paridad con Python NO se confía a la lectura: `criticidad.paridad.ts` y
 * `backend/tests/test_criticidad_paridad.py` corren LOS MISMOS casos, del mismo
 * archivo `criticidad_casos.json`, y los dos tienen que dar lo mismo.
 *
 * Si alguna vez cambia la regla, cambia en los dos sitios o la paridad falla.
 */

/** Las métricas de UNA transacción que la regla necesita. */
export interface MetricasCriticidad {
  promedio: number;
  p90: number;
  max: number;
  tasa_error: number;
}

/** Criterios de aceptación: los globales, o los propios de una transacción. */
export interface Criterios {
  response_time?: number | string | null;
  availability?: number | string | null;
}

export type Veredicto = 'APTO' | 'APTO CON RESERVAS' | 'NO APTO';

/** Umbrales del backend para las señales que no dependen de los criterios. */
export const PICO_RELATIVO = 10;      // max >= 10 x promedio
export const PICO_ABSOLUTO_MS = 10000;  // max >= 10 s

const num = (v: number | string | null | undefined, porDefecto: number): number => {
  if (v === null || v === undefined || v === '') return porDefecto;
  const n = typeof v === 'number' ? v : parseFloat(v);
  return Number.isFinite(n) ? n : porDefecto;
};

/**
 * KNX-09, literal. Los valores por defecto (2000 ms y 99 %) son los del backend
 * y NO los del formulario: `compute_per_transaction_verdicts` usa esos.
 */
export function veredictoTransaccion(
  m: MetricasCriticidad,
  criterios: Criterios,
): Veredicto {
  const umbralRt = num(criterios.response_time, 2000);
  const umbralError = 100.0 - num(criterios.availability, 99.0);

  const fallaRt = m.p90 > umbralRt;
  const fallaError = m.tasa_error > umbralError;
  const avisoRt = m.p90 > umbralRt * 0.8 && !fallaRt;

  if (fallaRt || fallaError) return 'NO APTO';
  if (avisoRt) return 'APTO CON RESERVAS';
  return 'APTO';
}

export interface Criticidad {
  veredicto: Veredicto;
  esCritica: boolean;
  /** Las señales que dispararon la marca, ya redactadas (D45). */
  motivos: string[];
}

// --- Formato español, el mismo criterio que `estilo.py` (D32) ---
const esp = (n: number, dec = 0) =>
  n.toLocaleString('es-CO', { minimumFractionDigits: dec, maximumFractionDigits: dec });

/**
 * Las tres señales del backend. `criterios` son los efectivos de ESA fila: sus
 * propios valores si los tiene, los globales si no (D41).
 *
 * Sin criterios de tiempo ni de disponibilidad, la señal (a) se omite — igual
 * que hace el endpoint cuando no recibe ninguno de los dos.
 */
export function evaluarCriticidad(
  m: MetricasCriticidad,
  criterios: Criterios,
  conCriterios = true,
): Criticidad {
  const veredicto = veredictoTransaccion(m, criterios);
  const motivos: string[] = [];

  // (a) el veredicto por criterios
  if (conCriterios && (veredicto === 'NO APTO' || veredicto === 'APTO CON RESERVAS')) {
    const umbralRt = num(criterios.response_time, 2000);
    const umbralError = 100.0 - num(criterios.availability, 99.0);
    const partes: string[] = [];
    if (m.p90 > umbralRt * 0.8) {
      partes.push(
        `1 de cada 10 usuarios espera más de ${esp(m.p90)} ms (el límite son ${esp(umbralRt)} ms)`,
      );
    }
    if (m.tasa_error > umbralError) {
      partes.push(`${esp(m.tasa_error, 2)}% de errores (el límite es ${esp(umbralError, 2)}%)`);
    }
    motivos.push(
      (veredicto === 'NO APTO' ? 'no cumple: ' : 'queda al límite: ') + partes.join(' · '),
    );
  }

  // (b) pico relativo
  if (m.promedio > 0 && m.max >= PICO_RELATIVO * m.promedio) {
    motivos.push(
      `pico de ${esp(m.max)} ms, ${esp(m.max / m.promedio, 1)} veces su promedio`,
    );
  }

  // (c) pico absoluto
  if (m.max >= PICO_ABSOLUTO_MS) {
    motivos.push(`pico de ${esp(m.max / 1000, 1)} segundos, que apunta a una espera agotada`);
  }

  return { veredicto, esCritica: motivos.length > 0, motivos };
}
