Commit base `92f3ea3` · 2 de octubre de 2026 · Reporte 151 — cuatro ajustes tras el reporte 150

# Razonamiento por tipo de llamada, percentiles tal cual, el umbral del veredicto y el modelo ligero

La aplicación estaba cerrada (regla 31). Cuatro partes, un commit cada una, con push a `github`:

| Parte | Commit | Qué |
|---|---|---|
| 1 | `c768572` | Razonamiento por tipo de llamada (se aplica) |
| 2 | `8e4b3e1` | Percentiles tal cual (regla 3 del estilo) |
| 3 | `db3adba` | `Dashboard.tsx`: la columna de umbral del veredicto por transacción |
| 4 | `92f3ea3` | Modelo ligero: preparado, medido y **no activado** |

Regresión final: `estructura_prompts.py`, `cierre_b5.sh` (A a J) y `cierre_r1.sh`, **todo pasa**.
`tsc` limpio.

---

## 1. Razonamiento por tipo de llamada

**Una sola definición: `backend/app/services/ai/reparto.py`.** La aplica `_generate` según el
nombre de la sección, así que ningún llamador tiene que acordarse.

| Esfuerzo | Llamadas |
|---|---|
| **El de la configuración** | resumen del informe general (`summary_table`) y **resumen de cada transacción** (`txreport_summary`), conclusiones, recomendaciones, comparativa (`comparison_analysis`) y conclusión única del integrado (`consolidated_unico`) |
| **Bajo, siempre** | chat del Analista IA, las seis gráficas generales y las cinco de cada transacción, **errores**, **redirecciones**, capturas (`analyze_image`) y sus análisis globales de monitoreo y evidencias |

Dos decisiones de interpretación que Fredy debe confirmar:

- **Resumen de cada transacción, con el nivel de la configuración.** Lo entendí como «resumen».
  Si debe ir en bajo, se cambia en una línea de `CON_ESFUERZO_CONFIGURADO`.
- **Errores, redirecciones y capturas, en bajo.** No están en la lista de «nivel de la
  configuración», y en el 150 errores ya iba con las gráficas.

- **Pantalla de configuración** (`AIConfigPage.tsx`): sigue con un solo valor y debajo dice: «Se
  aplica al resumen, las conclusiones, las recomendaciones, la comparativa y la conclusión del
  informe integrado. El chat del Analista IA, las gráficas, los errores y las capturas usan
  siempre razonamiento bajo».
- **La telemetría (`AI_TELEMETRY`) y el log `AI CALL`** registran el esfuerzo y el modelo
  **realmente enviados** en cada llamada.
- **La configuración de Fredy queda en `medium`.** Estaba en `low` desde el 2/10 a las 17:51
  UTC. Se cambió con el `POST /ai-config` del producto (solo `reasoning_effort`), no con SQL.
  Proveedor y modelo siguen siendo `openai` / `gpt-5.5`.
- **Suite `b5_h_reparto.py`**: un colector sustituye al cliente de OpenAI y guarda el modelo y
  el `reasoning_effort` de cada petición. Recorre un informe completo, una transacción, el chat,
  la comparativa, la conclusión única y una captura, con la configuración en medio:
  **20 tipos de llamada, cada uno con el esfuerzo esperado**. Comprueba además el modelo
  ligero (punto 4).
- `estructura_prompts.py`: la comprobación de las capturas ahora exige **bajo** (antes, el de la
  configuración). Es el cambio pedido.

## 2. Percentiles tal cual

- **Regla 3 de la guía**: «PERCENTILES TAL CUAL. Se nombran como los escribe Fredy: «percentil 95
  de 8.108 ms». Como mucho uno o dos por párrafo, y NUNCA la lista P50/P90/P95/P99 ni todos los
  percentiles seguidos».
- **El modelo de resumen vuelve a la frase original de Fredy**: «con un promedio de 4.823 ms,
  percentil 95 de 8.108 ms y un máximo de 9.221 ms».
- **`percentil_frase`** ya no traduce a personas: devuelve `percentil 95 de 8.108 ms` y
  `mediana de 142 ms`. Por ahí pasan los datos que reciben los prompts: el bloque de la
  ejecución, la tabla por transacción y el informe de transacción. El rótulo «LECTURA DE SUS
  PERCENTILES (copia estas frases tal cual)» pasa a «SUS PERCENTILES (dato de apoyo: si hacen
  falta, como mucho uno o dos, nombrados tal cual)».
- **El detector** deja de avisar por «percentil sin traducir» y avisa cuando hay **más de dos
  percentiles distintos en un mismo párrafo o viñeta**. El aviso dice, por ejemplo,
  «4 percentiles en un párrafo». Sigue solo detectando y reportando (regla 21).
- **Suite `b5_i_percentiles.py`** (11 comprobaciones).

## 3. `Dashboard.tsx` — el umbral del veredicto por transacción

**Protegido. Autorizado por Fredy con diff mínimo: 3 líneas.** La lógica vive en
`frontend/src/utils/umbralTiempo.ts`, que no está protegido. El diff entero:

```diff
@@ -12,6 +12,7 @@
 import { FranjaRespaldo } from '../common/AvisoRespaldo';   // F2
+import { umbralDeTiempo } from '../../utils/umbralTiempo';   // 151
 import { useChartLayers, capasComoParams } from '../../hooks/useChartLayers';   // ETAPA 6 (D46-D48)
@@ -676,7 +677,7 @@
-                      <th className="text-center py-3 px-4 text-base font-bold text-gray-500 uppercase">Umbral RT (ms)</th>
+                      <th className="text-center py-3 px-4 text-base font-bold text-gray-500 uppercase">{execution.acceptance_criteria_json?.analista ? 'Criterio de tiempo' : 'Umbral RT (ms)'}</th>
@@ -689,7 +690,7 @@
-                          <td className="py-3 px-4 text-xl text-center text-gray-400">{rtThreshold}</td>
+                          <td className="py-3 px-4 text-xl text-center text-gray-400" data-testid="umbral-tx">{umbralDeTiempo(execution.acceptance_criteria_json, txn) ?? rtThreshold}</td>
```

`Dashboard.tsx` pasa de 1057 a 1058 líneas.

- **Con criterios del Analista IA**, la columna se llama «Criterio de tiempo» y muestra el
  criterio de tiempo declarado para esa transacción, con su medida, operador, valor y unidad:
  «máximo ≤ 5 s». Si la medida fue supuesta, lo dice («(medida supuesta)»). Un criterio de toda la
  prueba sale con «(toda la prueba)», y si hay varios se separan con «·». **Sin criterio de tiempo,
  «sin criterio». El 2.000 ya no aparece.**
- **Nuevo Reporte**: sin la marca `analista`, la función devuelve `null` y la celda sigue
  pintando `rtThreshold` con su cadena de siempre, encabezado «Umbral RT (ms)» incluido.
- **Suite de pantalla `b5_j_umbral.py`** (Playwright contra el 8002, base de pruebas):
  - una ejecución del Analista con «máximo ≤ 5 s» solo para `1. Auth` → Auth muestra
    «máximo ≤ 5 s», las otras cinco «sin criterio» y ninguna celda muestra 2.000;
  - `ZZTEST-R1 carga`, de Nuevo Reporte → «Umbral RT (ms)» con los números de siempre.

  Queda dentro de `cierre_b5.sh` como J.

## 4. El modelo ligero — solo medir y proponer

### Lo que queda preparado (y apagado)

- `AI_MODELO_LIGERO` (variable de entorno del backend). Con valor, **el chat y las gráficas**
  (generales y por transacción) usan ese modelo; todo lo demás sigue con el principal. **Vacío =
  el mismo modelo, y así queda.** No está en `docker-compose.yml` ni en `.env`. Activarlo exige
  añadirla y reiniciar el backend, y eso es decisión de Fredy (regla 7).
- Funciona con los dos proveedores. Con Gemini, `_modelo_gemini()` crea el modelo ligero la
  primera vez que hace falta.
- `OPENAI_MAX_TOKENS` incluye a los dos candidatos (16.384 y 8.192, alineados con `gpt-5-mini` y
  `gpt-5-nano`), para que no caigan al 4.096 por defecto.
- **La configuración y el modelo en uso no se tocaron**: el modelo ligero existió solo dentro del
  proceso de la prueba.

### Los candidatos (de `/ai-config/models/live` con la clave de Fredy)

La lista viva devuelve 100 modelos. De la familia gpt-5, los más livianos son estos (no hay
`gpt-5.5-mini` ni `gpt-5.5-nano`):

1. **`gpt-5.4-mini`**: el «mini» más reciente que ve la clave (2026-03-17) y el más cercano a
   gpt-5.5 en capacidad. **Es el que se midió.**
2. **`gpt-5.4-nano`**: aún más ligero. Queda como segundo candidato, **sin medir**: el chat
   necesita extraer criterios con JSON estricto, y si el mini ya falla ahí (ver abajo), el nano no
   promete más.

### La medición

El script es `backend/pruebas_e2e/corrida_modelo_ligero.py`. Usa el JTL de Fredy, los criterios
de su sesión `ea4cdd73` (los mismos del 150) y su archivo de errores. La copia temporal del
archivo de errores se borró al terminar. La conexión a la base es de solo lectura, `_upsert` es
un colector y los contadores no se tocaron. Cada versión genera el informe general, los tres de
transacción y los tres turnos del chat de Fredy: **31 llamadas, sin un fallo**.

| Llamadas | Versión | Modelo / esfuerzo | N.º | Entrada | Caché | Salida | Razonamiento | Segundos |
|---|---|---|---|---|---|---|---|---|
| Chat | (a) | gpt-5.5 / bajo | 3 | 9.558 | 1.792 | 1.463 | 553 | 17,8 |
| Chat | (b) | gpt-5.4-mini / bajo | 3 | 9.558 | 4.096 | 2.216 | 1.058 | 10,6 |
| Gráficas | (a) | gpt-5.5 / bajo | 21 | 127.717 | 91.136 | 6.904 | 2.433 | 108,1 |
| Gráficas | (b) | gpt-5.4-mini / bajo | 21 | 127.663 | 95.744 | 6.200 | 1.966 | 45,8 |
| Resumen, conclusiones y recomendaciones | (a) | gpt-5.5 / medio | 3 | 20.067 | 7.680 | 2.873 | 1.536 | 38,7 |
| Resumen, conclusiones y recomendaciones | (b) | gpt-5.5 / medio | 3 | 19.947 | 14.592 | 3.893 | 2.560 | 45,5 |
| Errores y resumen de cada transacción | (a) | gpt-5.5 | 4 | 27.537 | 8.448 | 3.467 | 2.637 | 42,9 |
| Errores y resumen de cada transacción | (b) | gpt-5.5 | 4 | 27.533 | 23.552 | 2.485 | 1.676 | 34,6 |
| **Total** | **(a)** | | **31** | **184.879** | **109.056** | **14.707** | **7.159** | **207,5** |
| **Total** | **(b)** | | **31** | **184.701** | **137.984** | **14.794** | **7.260** | **136,5** |

**Tiempo de pared del informe:**

| Versión | General | Transacciones | Total |
|---|---|---|---|
| (a) | 83,5 s | 107,5 s | **191,0 s** |
| (b) | 64,5 s | 62,8 s | **127,3 s (−33 %)** |

**Coste, como fórmula** (por modelo, con su tarifa vigente; la salida ya incluye el razonamiento):

```
coste = (entrada − caché) × P_entrada + caché × P_caché + salida × P_salida

(a) gpt-5.5:       (184.879 − 109.056) × P_entrada(5.5) + 109.056 × P_caché(5.5) + 14.707 × P_salida(5.5)
(b) gpt-5.5:       ( 47.480 −  38.144) × P_entrada(5.5) +  38.144 × P_caché(5.5) +  6.378 × P_salida(5.5)
  + gpt-5.4-mini:  (137.221 −  99.840) × P_entrada(mini) + 99.840 × P_caché(mini) + 8.416 × P_salida(mini)
```

Los tokens de las dos versiones son casi los mismos. El ahorro sale de que **el 74 % de la
entrada y el 57 % de la salida pasan a la tarifa del mini**. **Cuidado con la caché de (b):**
corrió después de (a), y las llamadas de gpt-5.5 encontraron en caché el prefijo que dejó (a).
Por eso los tokens en caché del resumen y del resto suben en (b). La caché es de cada modelo: el
mini empezó en frío.

**El reparto de la parte 1, frente al informe del 150 (todo en medio):** sin contar el chat, (a)
son 28 llamadas con 13.244 de salida, 6.606 de razonamiento y 189,7 s, frente a 22.414, 15.892 y
311,7 s: **−41 % de salida, −58 % de razonamiento y −39 % de tiempo**. Es lo que se proponía en
el 150.

### ¿Respetó el estilo? ¿Salió válido el JSON?

| | (a) gpt-5.5 | (b) gpt-5.4-mini |
|---|---|---|
| Gráficas en **un solo párrafo** | 21 de 21 | 21 de 21 |
| Cifras por texto (media) | 6,2 | 5,5 |
| Palabras por texto (media) | 145 | 140 |
| Textos que **citan rampas o escalones** | 2 (de pasada: «no en las rampas») | **4** («En la rampa de arranque…», «variaciones esperables entre escalones») |
| Avisos del detector de estilo | 0 | 0 |
| **JSON del chat válido** | 3 de 3 | 3 de 3 |
| **El chat entendió la corrección de Fredy** | **sí**: pasó los 64.000 a «cada servicio» | **no**: siguió con `suma: true` |

**Lo que hay que mirar antes de decidir: el chat.** El JSON del mini sale válido, pero razona
peor:

- **Turno 2.** Fredy corrige «es por servicio, no el total». gpt-5.5 pasó los 64.000 a «cada
  servicio». El mini **mantuvo el total combinado** (`suma: true`).
- **Turno 1.** El mini se inventó el alcance del criterio de 5 s («suma» de AsegurarFondos y
  Originator, que no tiene sentido en un tiempo de respuesta). Además preguntó si «lo de
  receptor era concurrencia o volumen», cuando Fredy lo había dicho.

Con esos datos, mi propuesta (la decisión es de Fredy):

- **Gráficas con `gpt-5.4-mini`: viable.** Mismo formato y menos cifras. Tarda menos de la mitad
  (108 → 46 s sumados), y el informe completo pasa de 191 a 127 s de pared. Cita más las rampas
  y los escalones: es leve, pero va contra la guía.
- **Chat con `gpt-5.4-mini`: no recomendado.** Extraer criterios es la parte crítica del
  Analista, y ahí el mini **no aplicó una corrección explícita**.
- Si Fredy quiere separar las dos cosas, hay que partir `es_ligera()` en dos (una línea).

La página con las gráficas de (a) y (b) lado a lado, la tabla y el chat turno a turno está en
**`C:\proyectos\Kinetix_pruebas\r2\modelo_ligero.html`**. Cada texto lleva sus párrafos, cifras,
palabras y menciones a rampas.

## Archivos

| Archivo | Cambio |
|---|---|
| `backend/app/services/ai/reparto.py` | **nuevo**: esfuerzo y modelo por tipo de llamada |
| `backend/app/services/ai/gemini.py` | `_generate` y `analyze_image` usan el reparto; `modelo_ligero` en el analizador y en `get_gemini_analyzer`; `_modelo_gemini`; dos entradas en `OPENAI_MAX_TOKENS` |
| `backend/app/services/ai/estilo.py` | regla 3, modelo de resumen, `percentil_frase`, detector |
| `backend/app/services/ai/contexto_prompt.py`, `transaction_report.py` | rótulos de los percentiles |
| `frontend/src/components/admin/AIConfigPage.tsx` | el texto de a qué se aplica el esfuerzo |
| `frontend/src/components/dashboard/Dashboard.tsx` | **protegido, autorizado**: 3 líneas (diff arriba) |
| `frontend/src/utils/umbralTiempo.ts` | **nuevo** |
| `backend/pruebas_e2e/b5_h_reparto.py`, `b5_i_percentiles.py`, `b5_j_umbral.py` | **nuevas** suites, en `cierre_b5.sh` |
| `backend/pruebas_e2e/estructura_prompts.py` | las capturas, en bajo |
| `backend/pruebas_e2e/corrida_modelo_ligero.py` | **nuevo**: la medición del punto 4 |

## Pendiente de Fredy

1. Validar en pantalla la tabla «Veredicto por Transacción» de una ejecución del Analista y de
   una de Nuevo Reporte, y el texto de la pantalla de configuración.
2. Confirmar que el resumen de cada transacción va con el nivel de la configuración, y que
   errores, redirecciones y capturas van en bajo.
3. Leer `modelo_ligero.html` y decidir si las gráficas (y solo ellas) pasan a `gpt-5.4-mini`.
