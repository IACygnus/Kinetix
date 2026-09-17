95ce8b6 · 2026-09-17

# ETAPA 5b.1 — Qué criterios recibe hoy cada prompt (read-only)

**Llamadas reales a la IA: 0.** Ningún archivo tocado. Los prompts se construyeron con un
**stub que cuenta y lanza** (`_generate` sustituido): contó 5 intentos y lanzó en los
cinco, así que no pudo escaparse ni una petición. Los seis prompts por transacción salen
de una función pura, sin analizador.

Ejecución usada: **`E5-panel`** (`c33488cb-5f1c-499b-86b3-4b58642c31cb`), que es justo el
caso que hay que poder distinguir:

```
Criterios globales:  response_time = 2.000 ms · availability = 99,5% · concurrency = 30
Criterios PROPIOS:   "1. Auth" -> response_time = 300 ms · availability = 99,5%
Veredictos:          "1. Auth" NO APTO   ·   "2. Get Booking" APTO
```

---

## 1. Respuesta corta

| Pregunta del plan | Respuesta |
|---|---|
| ¿Llega `per_transaction` a algún prompt? | **No. A ninguno de los 17.** |
| ¿Llega el umbral efectivo de la transacción al prompt de `transaction_report.py`? | **No. `build_section_prompts` no tiene ni parámetro de criterios.** |
| ¿Algún cambio de D55 exige un archivo protegido? | **No.** Ninguna condición de parada. |

La consecuencia práctica, con los datos de arriba: **la IA escribe sobre "1. Auth" sin
saber que su límite son 300 ms**, y el informe general solo conoce los 2.000 ms globales —
que es exactamente cómo un texto acaba contradiciendo la tabla de veredictos.

## 2. Los 6 prompts por transacción — ni un criterio

`transaction_report.build_section_prompts(label, m, series, test_type)`. **No hay
parámetro de criterios**, ni en esa función ni en `generate_transaction_report`.

Volcado literal para `"1. Auth"` de `E5-panel`:

| Sección | Tamaño | Bloque de criterios | ¿menciona 300? | ¿menciona 2.000? | ¿"criterio"? | ¿"limite"? |
|---|---|---|---|---|---|---|
| `summary` | 1.420 | **NINGUNO** | no | no | no | no |
| `chart_response_times` | 1.104 | **NINGUNO** | no | no | no | no |
| `chart_latency` | 1.757 | **NINGUNO** | no | no | no | no |
| `chart_error_rate` | 1.163 | **NINGUNO** | no | no | no | no |
| `chart_codes` | 1.133 | **NINGUNO** | no | no | no | no |
| `chart_tps` | 1.136 | **NINGUNO** | no | no | no | no |

Lo que sí llevan: las métricas reales de la transacción, la lectura de sus percentiles en
frase de usuario, el dígito de su serie, el pico con su ratio y el bloque de estilo. Todo
menos contra qué se la está midiendo.

## 3. Los 11 prompts del informe general — solo el criterio global

El informe general arma 11 prompts (`analysis_pipeline.py`): resumen, errores, 6 gráficas,
redirecciones —si las hay—, conclusiones y recomendaciones. Con los 6 por transacción son
**17**. (La Etapa 3 hablaba de 19 porque entonces las transacciones tenían 8 secciones;
D20 retiró dos.)

De los 11, **solo 3 reciben `acceptance_criteria`**, y los tres emiten un bloque **global**:

| Prompt | ¿recibe criterios? | Qué emite literalmente |
|---|---|---|
| `analyze_summary_table` | **sí** | `CRITERIOS DE ACEPTACION:` · Concurrencia 30 usuarios · Tiempo máximo aceptable **2.000 ms** · Disponibilidad mínima 99,5% |
| `generate_conclusions` | **sí** | lo mismo + `RESULTADO CALCULADO: NO APTO` y la instrucción de abrir por ahí |
| `generate_recommendations` | **sí** | lo mismo, sin veredicto |
| `analyze_errors` | **no** | — |
| `analyze_chart` × 6 | **no** | — |
| `analyze_redirects` | **no** | — |

**En ninguno de los tres aparece `per_transaction`.** El código que lo lee es
`compute_per_transaction_verdicts` (`gemini.py:441`), que calcula los veredictos de la
tabla — y ahí se queda. Los prompts nunca lo ven.

### Un falso positivo que conviene dejar por escrito

La primera pasada marcó "menciona 300: sí" en `summary_table` y en `conclusions`. Al
localizar cada aparición, **ninguna es el criterio**:

```
summary_table: "1 de cada 10 usuarios espera más de 300 ms (P90: 300 ms)"   <- un P90
summary_table: "- Duracion de la prueba: 300 segundos"                      <- la duración
conclusions:   "- Duracion de la prueba: 300 segundos"                      <- la duración
```

Buscar la cifra suelta no vale como comprobación: en 5b.2 hay que comprobar el **bloque de
criterios**, no que el número aparezca en algún sitio.

## 4. Dónde vive cada pieza y por qué no hay parada

| Qué habría que tocar para D55 | Archivo | ¿Protegido? |
|---|---|---|
| Pasar los criterios efectivos a los 6 prompts por transacción | `services/ai/transaction_report.py` | no |
| Que los dos llamadores los pasen | `api/v1/endpoints/upload.py` (líneas 879 y 967) | no |
| Añadir la lista de transacciones con criterios propios a los prompts generales | `services/ai/gemini.py` | no |
| Repartirlos desde el pipeline | `services/ai/analysis_pipeline.py` | no |
| La columna "Criterios" con su botón (D54) | `components/dashboard/UploadJTL.tsx` | no |

Los protegidos de §11 son `Dashboard.tsx`, `ScriptDesigner.tsx`, `jtl_parser.py`,
`virtual_user.py`, `report_generator.py`, `export_html.py`, `export_pdf.py` y `engine/`.
**Ninguno entra.** No se activa la parada.

Los dos llamadores de `generate_transaction_report` ya tienen `execution` en el ámbito, así
que `execution.acceptance_criteria_json` está a mano sin consultar nada nuevo.

## 5. Lo que ya existe y hay que respetar

- **La regla de resolución del umbral efectivo ya está escrita**, en
  `compute_per_transaction_verdicts` (`gemini.py:451-455`):

  ```python
  txn_criteria  = per_txn.get(label, {})
  rt_threshold  = float(txn_criteria.get('response_time', global_rt))
  er_threshold  = 100.0 - float(txn_criteria.get('availability', global_avail))
  ```

  D55 tiene que usar **esa misma resolución**, no una paralela, o el texto y el veredicto
  de la tabla podrían discrepar — que es el problema que esta etapa viene a cerrar.
- **El formato de las cifras sale de `estilo.py`** (`ms`, `num`, `pct`), que
  `transaction_report.py` ya importa. El bloque de criterios nuevo se formatea con esos
  helpers, sin tocar ninguna regla de estilo.
- **`error_rate` en `per_transaction` es fijo 0,5%** y lo escribe el panel
  (`UploadJTL.tsx:289`); el cálculo del veredicto no lo usa: deriva el umbral de error de
  `availability`. D55 debe hablar de disponibilidad, no de ese campo.

## 6. El panel hoy (para D54)

`UploadJTL.tsx`, tabla del panel de selección:

```
| ☐ | ▸ | Transacción | Muestras | Promedio | TPS | Errores |
      ↑
      la flecha que D54 retira (columna w-6, ChevronRight/ChevronDown)
```

- La fila se despliega con esa flecha y pueden estar **varias abiertas a la vez**
  (`filasAbiertas`, D40). Eso se conserva.
- El desplegable ya trae los tres campos con marca de agua del global y el botón **"Usar
  globales"** (D41), que borra los propios. Se conserva entero: D54 solo cambia **cómo se
  abre**.
- Junto al nombre hay además un chip índigo **"criterios propios"**. El botón nuevo dice lo
  mismo. **No lo retiro**: D54 no lo pide y quitarlo es una decisión visual de Fredy. Queda
  señalado para que lo decida al validar.
- `tieneCriteriosPropios(label)` (línea 176) ya es la función que decide el estado del
  botón: "Globales" o "Propios".

## 7. Presupuesto

| | |
|---|---|
| Llamadas a la IA en 5b.1 | **0** de 20 |
| Archivos tocados | **0** |

---

**Estado:** 5b.1 cerrado. Ninguna condición de parada: no hace falta ningún archivo
protegido. Sigue 5b.2 — implementación de D54 y D55.
