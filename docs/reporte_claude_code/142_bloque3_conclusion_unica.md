Commit base `86c8dc7` · 1 de octubre de 2026 · Bloque 3, pasos 3.2, 3.3, 3.4 y 3.6 — la conclusión única del integrado

# La conclusión única del integrado

Decisiones de Fredy sobre el 141: **D1** fuera el texto unificado · **D2** el consolidado anterior, plegado
y de solo lectura (en pantalla, en 3.5) · **D3** los integrados no regenerados siguen igual · **D4** el
bloque de cada ejecución desde su JTL, con las cifras de la base si falta · **D5** D-a dentro de 3.4.

Este reporte **no copia textos de clientes**. El consolidado de hoy y el único, lado a lado, están en
**`C:\proyectos\Kinetix_pruebas\r2\integrado_unico.html`**.

**Condiciones de parada: ninguna se cumplió.** Suites en verde, nada cayó al respaldo y no se tocó ningún
protegido ni la rama web. **La pantalla no se ha tocado** (3.5 va aparte).

---

## 1. Qué cambió

| Commit | Paso | Qué |
|---|---|---|
| `e1acab0` | 3.2 | `services/ai/conclusion_unica.py`, nuevo: el prompt único y el corte en dos cajas. Si la IA no responde, no devuelve los dos bloques o deja uno vacío, lanza `ConclusionUnicaError` con el motivo |
| `194cabb` | 3.3 | `generate-consolidated` arma **un** análisis para todo el integrado y lo guarda en `consolidated_analysis.unico`. Lo que había por tipo pasa **entero** a `_legado` (no se borra nunca). Si la IA falla: **502 con el motivo y nada guardado** (D-b). GET devuelve el legado aparte (`consolidado_anterior`), PATCH lo conserva aunque la pantalla no lo mande, y el historial y los avisos lo saltan |
| `86c8dc7` | 3.4 | «Generar Informe Integrado» **ya no llama a la IA** (D1: una llamada menos). Con registro, **el PDF y el HTML pintan siempre lo guardado** y no el texto que manda la página (D-a) |
| `d3f1d5b` | 3.6 | La corrida con IA, la regresión y un ajuste de 3.3 (§3) |

### 1.1 Qué recibe el prompt único

Por cada ejecución del documento, en su orden:

1. **Su bloque de la ejecución**, el mismo de su informe individual (`contexto_de_parser`): cifras
   globales, tabla por transacción, agrupación por tiempo de respuesta, criterios, fases y hechos. Si
   falta el JTL, las cifras de la base (D4).
2. Su veredicto.
3. Sus conclusiones, recomendaciones y análisis de sección, con las correcciones del analista delante.
4. **Sus** capturas de infraestructura y **sus** evidencias, ya editadas y respetando el selector de R1.
   Antes se ataban al tipo de prueba.

Después, las transacciones que el documento detalla (mismo formato que leen las suites de R1) y la
instrucción de la guía de estilo:

- un solo análisis para todas las pruebas;
- de 4 a 7 viñetas de conclusiones, con el dictamen de viabilidad al final y explicado;
- de 4 a 7 viñetas de recomendaciones ligadas a hallazgos concretos;
- la infraestructura y las evidencias, dentro de las viñetas que toquen;
- sin repetir cifras.

Lleva el permiso de dictamen.

### 1.2 Lo que ve cada salida, hoy (sin 3.5)

| | Integrado no regenerado (D3) | Integrado regenerado |
|---|---|---|
| PDF y HTML | Igual que antes: el consolidado por tipo, con su rótulo | «Conclusiones:» + viñetas y «Recomendaciones:» + viñetas, sin rótulo por tipo. **Maquetación sin cambios** |
| Pantalla | Igual que antes | **Hasta 3.5**, la caja única sale con el rótulo crudo «unico» en el sitio del tipo de prueba. Se edita y se guarda bien; el legado no se ve, y lo conserva el servidor |

---

## 2. La corrida (3.6)

`backend/pruebas_e2e/corrida_integrado_unico.py`: lee el integrado en una conexión de **solo lectura**,
reúne los datos con el mismo código que el endpoint, hace **una** llamada y acaba en `rollback`. Integrado
`5c33feb0`: el más reciente de los 3 de carga y estrés, con capturas y con el consolidado editado a mano.

| | |
|---|---|
| Llamadas | **1** (antes: 1 unificado + 2 consolidados, uno por tipo) |
| Respuesta | `finish_reason = stop`, 28,8 s, 11.819 tokens de entrada, 2.238 de salida (1.536 de razonamiento) |
| Ejecuciones | carga y estrés, **las dos con su bloque desde el JTL**; las 7 capturas y la evidencia, dentro de la de carga |

| Caja | Viñetas | Palabras | Cifras |
|---|---|---|---|
| Hoy · carga · conclusiones (editada a mano) | 0 | 216 | 3 |
| Hoy · carga · recomendaciones (editada) | 0 | 185 | 1 |
| Hoy · estrés · conclusiones (editada) | 0 | 148 | 2 |
| Hoy · estrés · recomendaciones (editada) | 0 | 127 | 1 |
| **Única · conclusiones** | **6** | 233 | 2 |
| **Única · recomendaciones** | **6** | 186 | 4 |

- **Cuatro cajas pasan a dos.** Las dos únicas tienen viñetas, 0 avisos del detector de estilo, y la
  última viñeta de las conclusiones es el dictamen.
- **La infraestructura y las evidencias van dentro de las viñetas**: una de las conclusiones y dos de las
  recomendaciones las nombran (recuento por palabras clave), sin bloque aparte.
- **La izquierda está editada a mano por Fredy**, y la derecha es IA recién generada: la comparación es
  de forma y de contenido, no de calidad de la IA contra la IA.

---

## 3. Lo que la corrida destapó y se ajustó

La primera pasada dejó las 7 capturas y la evidencia en una «ejecución» aparte. En ese integrado, la
sección de carga apunta a una ejecución (`373db875`) y las de monitoreo y evidencias a otra (`35ca5b92`),
**con el mismo nombre**: la misma prueba subida dos veces. El consolidado de antes no lo notaba porque
ataba las capturas al tipo de prueba.

**Ajuste en `_reunir_conclusion_unica`:** unas capturas cuya ejecución no está en el documento como
prueba se atan a la prueba **del mismo nombre** o, si no la hay, a **la única de su tipo**. Si no hay a
dónde, quedan aparte con su nombre. Con eso, la segunda pasada (la del §2) las pone en la de carga. Coste:
1 llamada de más.

---

## 4. Suites

| Suite | Resultado |
|---|---|
| `conclusion_unica.py` (nueva) | **TODO PASA**. Parte A, sin base: el prompt, el corte y los fallos. Parte B, contra la base de pruebas: `unico` + `_legado`, el legado con su edición, error 502 y base intacta si la IA falla, regenerar conserva el legado, GET y PATCH, el aplanado, D-a y D1. Deja el integrado ZZTEST como estaba |
| `cierre_r1.sh` con el 8002 recién reiniciado (`reiniciar_8002.sh`) | **TODO PASA**: R1.1-R1.4, C2 integrado (`cableado_c2_integrado.py`) y C2 individual. Dos veces: tras 3.4 y tras el ajuste de §3 |
| `estructura_prompts.py` | **TODO PASA**. Su comprobación del límite de las unificadas pasa a «las unificadas ya no existen» |

---

## 5. Para 3.5 (pantalla, con la aplicación cerrada)

- `ConsolidatedAnalysisSection.tsx`:
  - la caja única con el título «Conclusiones» y «Recomendaciones», sin rótulo por tipo;
  - el consolidado anterior (`consolidado_anterior` del GET), plegado y de solo lectura (D2);
  - el texto de «Se generarán análisis separados para Carga y Estrés» sobra.
- `IntegratedReportPage.tsx`:
  - el aplanador entiende `unico`, aunque las exportaciones ya no lo usan;
  - deja de usar `data.unified_conclusions`;
  - enseña el error 502 del consolidado, que hoy ya llega como `detail` y el componente ya pinta en rojo.

## 6. Lo que no se comprobó

- **Si el texto único es mejor.** Es de Fredy: `integrado_unico.html`.
- **Los otros dos integrados de carga y estrés.** Solo se corrió uno.
- **La pantalla con la caja única** (§1.2): no se ha mirado, por la regla 31.
