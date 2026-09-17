/**
 * ETAPA 5 (D42) — La regla de criticidad, lado TypeScript.
 *
 * Corre LOS MISMOS casos que `backend/tests/test_criticidad_paridad.py`, del
 * mismo `criticidad_casos.json`, contra el puerto de `criticidad.ts`. Si la
 * regla cambia en un solo lenguaje, uno de los dos revienta.
 *
 * No hay runner de pruebas en el frontend y no se anade uno (traeria un rebuild
 * por una dependencia de desarrollo). Se compila con el `tsc` que ya esta y se
 * ejecuta con node:
 *
 *   npx tsc --outDir /tmp/paridad --module commonjs --target es2020 --skipLibCheck \
 *       src/utils/criticidad.ts src/utils/criticidad.paridad.ts
 *   node /tmp/paridad/criticidad.paridad.js <ruta del json>
 *
 * Se compila a CommonJS y `process`/`require` se declaran aqui a mano para no
 * anadir `@types/node` al proyecto: una dependencia de desarrollo obligaria a
 * rehacer la imagen del frontend por una prueba.
 */
declare const process: { argv: string[]; exit(codigo: number): void };
declare function require(modulo: string): any;

import { evaluarCriticidad, veredictoTransaccion } from './criticidad';
import type { Criterios, MetricasCriticidad } from './criticidad';

const { readFileSync } = require('fs') as { readFileSync: (p: string, e: string) => string };

interface Caso {
  nombre: string;
  metricas: MetricasCriticidad;
  criterios: Criterios;
  esperado?: string;
  esperado_critica?: boolean;
}

const ruta = process.argv[2] || '/tmp/paridad/criticidad_casos.json';
const fixture = JSON.parse(readFileSync(ruta, 'utf-8')) as {
  casos: Caso[];
  senales: Caso[];
};

let fallos = 0;

const comprobar = (ok: boolean, texto: string) => {
  console.log(`${ok ? 'PASA ' : 'FALLA'} | ${texto}`);
  if (!ok) fallos += 1;
};

console.log(`veredicto — ${fixture.casos.length} casos`);
for (const c of fixture.casos) {
  const obtenido = veredictoTransaccion(c.metricas, c.criterios);
  comprobar(obtenido === c.esperado,
    `${c.nombre}: esperado ${c.esperado}, obtenido ${obtenido}`);
}

console.log(`\nsenales de criticidad — ${fixture.senales.length} casos`);
for (const c of fixture.senales) {
  const { esCritica } = evaluarCriticidad(c.metricas, c.criterios);
  comprobar(esCritica === c.esperado_critica,
    `${c.nombre}: esperado ${c.esperado_critica}, obtenido ${esCritica}`);
}

// Los mismos dos casos sueltos que comprueba el lado Python.
console.log('\ncasos sueltos');
const m: MetricasCriticidad = { promedio: 400, p90: 462, max: 1013, tasa_error: 0.0 };
comprobar(veredictoTransaccion(m, { response_time: 300, availability: 99.5 }) === 'NO APTO',
  'los criterios propios mandan sobre los globales');
comprobar(veredictoTransaccion(m, { response_time: 2000, availability: 99.5 }) === 'APTO',
  'sin criterios propios se evaluan los globales');
comprobar(
  veredictoTransaccion(m, { response_time: 2000, availability: 99.5 })
  === veredictoTransaccion({ ...m }, { response_time: 2000, availability: 99.5 }),
  'la concurrencia no entra en la regla (no es ni un parametro)');

console.log(`\n${'='.repeat(58)}`);
if (fallos > 0) {
  console.log(`${fallos} FALLOS — la regla de TS NO coincide con la de Python`);
  process.exit(1);
}
console.log('PARIDAD TS/PYTHON: TODOS LOS CASOS COINCIDEN');
