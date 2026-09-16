ed6f0d0 · 2026-09-15

# ETAPA 1.3 — Corrida 1: línea base ANTES de los fixes

**Llamadas reales a la IA en este sub-paso: 35** (de las ~70 autorizadas; quedan ~35 para 1.6).
**Corrida VÁLIDA** — ninguna condición de PARADA se activó.

Ejecución creada: `30e085c7-e4a8-48a6-9b7d-d038480a6550` · `E1.3-baseline-1`
Datos crudos: `C:\proyectos\Kinetix_pruebas\baseline1.json` (corrida + 35 líneas de telemetría).

---

## Controles de validez — los tres pasan

| Control | Esperado | Obtenido |
|---|---|---|
| Nº de líneas `AI_TELEMETRY` | 11-12 generales + 24 de transacción | **11 + 24 = 35** ✓ |
| Todos los `outcome` | `ok` | **35/35 `ok`**, 35/35 `finish_reason="stop"` ✓ |
| Texto real en base (no fallback) | sí | 24/24 filas con texto · 3 labels · summary 1.033 ch · conclusiones 2.957 ch · recomendaciones 3.081 ch ✓ |

El bloque general trae **11** llamadas, no 12: esta ejecución no tiene redirecciones, así que la
sección condicional (`analysis_pipeline.py:293`) no se dispara. Coincide con lo previsto en E1.1.

Muestra del texto guardado (confirma que es IA, no plantilla de fallback):
> «6 transacciones quedaron en tier excelente y sostuvieron 33.59 Transacciones por segundo (TPS)
> durante 300s con 30 usuarios, pero la tasa de error glo…»

---

## Tiempos

| Medida | Valor |
|---|---|
| **T1 − T0** (bloque general, respuesta de `/upload`) | **119,1 s** |
| **T2 − T0** (percibido total, hasta la última transacción) | **354,3 s** = 5,9 min |
| Latencia sumada de IA (35 llamadas) | 351,6 s |

La latencia de IA es **el 99,2 %** del tiempo percibido. Confirma lo medido en E1.1: el tiempo
no está en el código de Kinetix, está en esperar al modelo, una llamada detrás de otra.

## Sonda `GET /auth/me` — la evidencia de H4

| Métrica | Valor |
|---|---|
| Muestras | 122 (1 error) |
| Mínimo | 2,6 ms |
| **Máximo** | **54.922,3 ms = 54,9 s** |
| p95 | 7,9 ms |
| Media | 457,9 ms |

**Una petición trivial de sesión tardó casi 55 segundos.** La referencia en reposo medida en 1.2
era p95 4,4 ms. El p95 de 7,9 ms engaña: la sonda pasa la mayor parte del tiempo en el bloque
por transacción, que **ya está protegido con `to_thread`** desde N4.10. El daño se concentra en
el bloque general, que es justo lo que 1.4 va a corregir.

Esto es la medición **ANTES**. El mismo número después del fix es el criterio de éxito de H4.

---

## Telemetría por llamada

| Sección | Alcance | Latencia s | prompt | completion | reasoning | %rz | cached |
|---|---|---|---|---|---|---|---|
| summary_table | general | 14,1 | 3.516 | 780 | 512 | 66% | 0 |
| errors | general | 6,6 | 2.899 | 512 | 321 | 63% | 0 |
| chart_response_times | general | 15,9 | 3.611 | 1.227 | 1.024 | **83%** | 0 |
| chart_throughput | general | 8,8 | 2.903 | 670 | 512 | 76% | 0 |
| chart_latency | general | 9,0 | 2.904 | 668 | 512 | 77% | 1.792 |
| chart_error_rate | general | 8,4 | 2.905 | 678 | 512 | 76% | 1.792 |
| chart_codes_per_second | general | 9,0 | 2.915 | 693 | 512 | 74% | 1.792 |
| chart_transactions_per_second | general | 11,3 | 2.984 | 625 | 438 | 70% | 1.792 |
| chart_active_threads | general | 8,3 | 2.899 | 682 | 512 | 75% | 0 |
| conclusions | general | 13,0 | 4.727 | 1.264 | 512 | 41% | 1.792 |
| recommendations | general | 14,3 | 4.143 | 1.261 | 512 | 41% | 0 |
| *(24 filas de transacción — 8 secciones × 3 labels)* | transacción | 7,4 – 14,9 | ~3.250–3.400 | 550 – 1.213 | 410 – 1.024 | 59–86% | 0 |

Tabla completa por llamada en `baseline1.json`.

### Totales

| Métrica | Valor |
|---|---|
| Tokens de prompt | 115.810 |
| Tokens de salida (`completion`) | 27.782 |
| **De ellos, razonamiento** | **19.085 → 68,7 %** |
| Tokens cacheados | 8.960 → **7,7 %** del prompt |
| Latencia por cada 1.000 tokens de razonamiento | **≈ 18,4 s** |

---

## Lectura preliminar (el análisis formal es 1.7)

**H1 apunta a confirmada:** el **68,7 %** de todo lo que el modelo genera es razonamiento que
nunca llega al informe. Las secciones de gráfica llegan al 83-86 %. Las dos secciones con más
texto útil (`conclusions`, `recommendations` generales) son las que menos razonan en proporción
(41 %), lo que encaja: ahí el modelo sí produce salida visible.

**Cache casi sin aprovechar (7,7 %)** y de forma irregular — aparece en algunas secciones
generales y en **ninguna** de transacción, pese a que las 24 llamadas por transacción comparten
el mismo `SYSTEM_PROMPT` duplicado que E1.1 documentó. Material para la Etapa 4, no para esta.

No se toca nada de esto ahora: 1.3 solo mide.

---

## Estado

Sub-paso 1.3 completado, corrida válida. Se continúa con 1.4 (fix H4).

Durante toda la corrida **no se modificó ningún archivo de `backend/`**, a propósito: con
`--reload` activo, una edición habría reiniciado el proceso a mitad de generación y habría
invalidado la línea base.
