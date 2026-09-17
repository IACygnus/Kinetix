/**
 * useChartLayers — el control de capas promedio/maximo de las graficas (ETAPA 6, D46-D48).
 *
 * La especificacion v1.2 §3 pide poder apagar cualquiera de las dos capas que
 * hoy se dibujan juntas (promedio solido, maximo punteado). La seleccion es
 * POR GRAFICA y vive en la memoria de la sesion de pantalla: no se persiste
 * (D48), asi que no hay cambio de esquema ni endpoint nuevo.
 *
 * El estado vive en Dashboard —el ancestro comun del informe general y de los
 * bloques por transaccion— porque al exportar hay que leer la seleccion de
 * TODAS las graficas de la pantalla (D49), no solo la del bloque que se este
 * mirando.
 */
import { useCallback, useState } from 'react';

/** 'ambas' es el valor por defecto y el unico que reproduce lo de hoy. */
export type Capa = 'ambas' | 'promedio' | 'maximo';

export const CAPA_POR_DEFECTO: Capa = 'ambas';

/** Etiquetas del selector segmentado, en el orden en que se pintan. */
export const CAPAS: ReadonlyArray<{ valor: Capa; texto: string }> = [
  { valor: 'ambas', texto: 'Ambas' },
  { valor: 'promedio', texto: 'Promedio' },
  { valor: 'maximo', texto: 'Máximo' },
];

/**
 * Identificador estable de una grafica dentro de la pantalla.
 *
 * `alcance` es 'general' o 'tx:<nombre de la transaccion>' y `gráfica` la clave
 * corta de la grafica ('rt' hoy es la unica con serie dual). El mismo id viaja
 * al backend al exportar, de modo que los dos lados hablan de la misma grafica
 * sin tener que inventar un segundo vocabulario.
 */
export function idGrafica(alcance: string, gr: string): string {
  return `${alcance}|${gr}`;
}

export interface ChartLayers {
  /** Todo el mapa, para mandarlo al exportar. Solo lleva lo que se cambio. */
  capas: Record<string, Capa>;
  /** La capa de una grafica; 'ambas' si nadie la toco. */
  capaDe: (id: string) => Capa;
  setCapa: (id: string, capa: Capa) => void;
}

export function useChartLayers(): ChartLayers {
  const [capas, setCapas] = useState<Record<string, Capa>>({});

  const capaDe = useCallback(
    (id: string): Capa => capas[id] || CAPA_POR_DEFECTO,
    [capas],
  );

  const setCapa = useCallback((id: string, capa: Capa) => {
    // 'ambas' se guarda igual que las otras: el backend recibe un mapa explicito
    // y no tiene que adivinar si una grafica ausente es "por defecto" o "no
    // existe". Un mapa de 4 entradas no pesa nada en la URL.
    setCapas((p) => ({ ...p, [id]: capa }));
  }, []);

  return { capas, capaDe, setCapa };
}

/**
 * Las capas en el formato que viaja al backend: `id:valor`, repetido.
 * Se omiten las que quedaron en 'ambas' para que un export sin tocar nada
 * mande exactamente los mismos parametros que hoy (ninguno).
 */
export function capasComoParams(capas: Record<string, Capa>): string[] {
  return Object.entries(capas)
    .filter(([, v]) => v !== CAPA_POR_DEFECTO)
    .map(([id, v]) => `${id}:${v}`);
}
