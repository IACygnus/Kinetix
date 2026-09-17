533bade · 2026-09-16

# ETAPA 3.3 — Los diecinueve prompts

**Llamadas reales a la IA en este sub-paso: 0.** Todo se construyó con stubs que
cuentan, y las dos puertas de salida reales (`openai_chat_completion` y el
cliente de Gemini) quedaron saboteadas para que cualquier llamada de verdad
reventara la prueba en lugar de gastar cuota. El contador quedó en **0 llamadas
reales** y así se declara.

Regla 4 (más de 3 archivos o 50 líneas → avisar): esta etapa se dividió en
sub-pasos precisamente por eso, y este es el sub-paso que toca los prompts.
Son **seis archivos**, todos con copia de seguridad `.bak_etapa3_3.3_*`.
**Ningún archivo protegido tocado.**

---

## 1. Qué cambió, archivo por archivo

| Archivo | Qué |
|---|---|
| `gemini.py` | `SYSTEM_PROMPT` reconstruido desde `estilo.py`; `STYLE_REMINDER` eliminado; `_generate` inyecta el estilo una vez (D34); 6 prompts reescritos; `build_tier_summary` y la tabla de transacciones sin jerga y en español; el análisis de imagen recibe el bloque de estilo por primera vez |
| `transaction_report.py` | `UX_RULE`, `FORMATO_NUMERICO` y `_n()` eliminados: ahora vienen de `estilo.py`; percentiles entregados como frase completa; sin `SYSTEM_PROMPT` embebido |
| `analysis_pipeline.py` | Los bloques de datos de las 6 gráficas, en español y con los percentiles traducidos |
| `analysis_ai.py` | Monitoreo y evidencias: datos en español, percentiles traducidos, sin `SYSTEM_PROMPT` embebido, sin la palabra «hallazgo» |
| `compare.py` | Comparativo: sin markdown en el prompt, datos en español, percentiles traducidos, **con permiso de dictamen** |
| `integrated_report.py` | Conclusiones unificadas y consolidado: sin `SYSTEM_PROMPT` embebido, **con permiso de dictamen**, KPIs en español con percentiles |

---

## 2. D34 — el estilo viaja una vez, y lo pone `_generate`

Antes, con OpenAI, el `SYSTEM_PROMPT` viajaba **dos veces**: como mensaje
`system` y otra vez dentro del prompt de usuario, porque cada prompt empezaba
por `f"""{SYSTEM_PROMPT}…"""`. Con Gemini viajaba una sola vez pero desde dentro
del prompt, porque el modelo se crea sin `system_instruction`.

Ahora la responsabilidad es de `_generate` y de nadie más:

- **OpenAI**: mensaje `system` con el bloque, y el prompt de usuario solo lleva
  datos e instrucciones.
- **Gemini**: `generate_content(f"{sistema}\n\n{prompt}")`.
- Ningún prompt del producto vuelve a incluirlo. Comprobado sobre los 32
  prompts construidos.

`_generate` recibe además `permite_veredicto`, que elige entre `SYSTEM_PROMPT`
(6.213 chars) y `SYSTEM_PROMPT_VEREDICTO` (6.531 chars, el mismo más el permiso
de dictaminar). Solo cuatro secciones piden la segunda.

La telemetría también se corrigió: `prompt_chars` ahora mide **lo que se envía
de verdad** (estilo + prompt). Antes medía solo el prompt de usuario, que ya
traía el estilo dentro.

### Lo que cuesta, medido

Caracteres enviados por llamada, `E2-validacion` (antes) contra los prompts
construidos sobre el mismo JTL (después):

| Sección | Antes | Después | Diferencia |
|---|---|---|---|
| `summary_table` | 12.481 | 10.703 | −14,2 % |
| `errors` | 11.133 | 7.691 | −30,9 % |
| `chart_response_times` | 13.244 | 11.013 | −16,8 % |
| `chart_latency` | 11.409 | 7.031 | −38,4 % |
| `chart_error_rate` | 11.420 | 6.985 | −38,8 % |
| `chart_codes_per_second` | 11.424 | 7.048 | −38,3 % |
| `chart_transactions_per_second` | 11.588 | 7.165 | −38,2 % |
| `chart_active_threads` | 11.405 | 6.987 | −38,7 % |
| `txreport_summary` | 12.858 | 7.644 | −40,5 % |
| `txreport_chart_response_times` | 12.495 | 7.328 | −41,4 % |
| `txreport_chart_latency` | 13.154 | 7.981 | −39,3 % |
| `txreport_chart_error_rate` | 12.542 | 7.387 | −41,1 % |
| `txreport_chart_codes` | 12.528 | 7.357 | −41,3 % |
| `txreport_chart_tps` | 12.510 | 7.360 | −41,2 % |
| **Las 28 llamadas, sin conclusiones ni recomendaciones** | **322.363** | **199.794** | **−38,0 %** |

`conclusions` (−43,9 %) y `recommendations` (−43,9 %) quedan fuera del total a
propósito: **su cifra está inflada**, porque embeben los análisis de las demás
secciones y en esta prueba esos análisis son textos de stub de una línea. Con
textos reales su ahorro será el estructural, no el que sale en la tabla.

El ahorro fijo, el que no depende de los datos: **3.665 caracteres por llamada**
(3.347 en las dos que llevan el permiso de dictamen). Y eso **pese a que el
bloque de estilo creció** de 4.939 a 6.213 caracteres para absorber `UX_RULE`,
`FORMATO_NUMERICO`, `STYLE_REMINDER` y las reglas nuevas de D29-D31.

---

## 3. Lo que ven ahora los prompts

Fragmento real del prompt de la tabla resumen, construido sobre `ff186cc7`:

```
| Transaccion | Muestras | Errores | Error | Promedio | P95 | P99 | Minimo | Maximo | Caudal |
| 1. Auth | 1.686 | 0 | 0,00% | 422 ms | 486 ms | 696 ms | 353 ms | 1.013 ms | 5,62 por segundo |
| 4. Get_Booking_Id | 1.677 | 692 | 41,26% | 108 ms | 139 ms | 206 ms | 85 ms | 438 ms | 5,59 por segundo |

LAS TRANSACCIONES AGRUPADAS POR SU TIEMPO DE RESPUESTA:
=== TIEMPOS BAJOS (promedio por debajo de 500 ms) — 6 transacciones ===
  1. Auth: promedio 422 ms, maximo 1.013 ms, errores 0, caudal 5,62 por segundo
    1 de cada 10 usuarios espera mas de 462 ms (P90: 462 ms)
    1 de cada 20 usuarios espera mas de 486 ms (P95: 486 ms)
    1 de cada 100 usuarios espera mas de 696 ms (P99: 696 ms)
```

Antes esa misma información le llegaba así:

```
| 1. Auth | 1,686 | 0 | 0.00% | 422 | 486 | 696 | 353 | 1013 | 5.62 |

CLASIFICACION POR TIERS DE PERFORMANCE:
=== TIER EXCELENTE (<500ms) - 6 transacciones ===
  1. Auth: avg=422ms, P95=486ms, P99=696ms, max=1013ms, errores=0, TPS=5.62
=== ALERTA: ALTA VARIABILIDAD (P99/avg > 3x, max/avg > 10x o max >= 10000ms) ===
```

Y la estructura que se le pedía al resumen terminaba con
`«3. VEREDICTO: Listo para produccion? Prioridades de mejora.»`. Ahora termina
con *«No digas si el sistema está listo para producción: eso va en las
conclusiones del informe.»*

---

## 4. Las diez contradicciones del reporte 30

| # | Qué era | Cómo queda |
|---|---|---|
| 1 | El resumen pedía el veredicto de producción | La instrucción lo prohíbe; `permite_veredicto=False` |
| 2 | El ejemplo aprobado del `SYSTEM_PROMPT` decía «tier excelente» | Los cuatro ejemplos viejos se retiraron; el único ejemplo es la referencia §4.3, que no tiene jerga |
| 3 | `build_tier_summary` entregaba `=== TIER CRITICO ===` | Entrega `=== TIEMPOS MUY ALTOS (promedio por encima de 5.000 ms) ===` |
| 4 | Las instrucciones por gráfica pedían «distribución por tiers» y «variabilidad P99/avg» | Piden lo mismo dicho como lo lee un gerente |
| 5 | Tres prompts usaban «hallazgo», palabra prohibida | Ninguno la usa |
| 6 | Los percentiles solo se traducían por transacción | Se traducen en los 26 prompts que llevan percentiles |
| 7 | El formato español solo llegaba por transacción | Llega a los 32 prompts |
| 8 | `STYLE_REMINDER` repetía seis reglas del `SYSTEM_PROMPT` | Eliminado |
| 9 | `compare.py` escribía markdown en el prompt | Sin markdown |
| 10 | Topes de palabras entre 120 y 500 sin criterio | Gráficas 130, resumen 180, errores 140, conclusiones y recomendaciones 350, correlaciones 400-500 |

---

## 5. La validación con stubs

```
PROMPTS CONSTRUIDOS: 32   ·   LLAMADAS REALES: 0
...
Percentiles traducidos en los 26 prompts que llevan percentiles.
TODAS LAS COMPROBACIONES EN VERDE.
```

Se construyeron los **32 prompts** de una ejecución completa: los 10 del informe
general, los 6 × 3 de las transacciones, monitoreo, evidencias, comparativo y
consolidado. Sobre cada uno:

| Comprobación | Resultado |
|---|---|
| El bloque de estilo aparece **exactamente una vez** en lo que se envía | 32/32 |
| La referencia §4.3 aparece **una vez** y **con** su prohibición de copiar | 32/32 |
| El prompt de usuario **ya no** repite el bloque de estilo (D34) | 32/32 |
| El permiso de dictamen está **solo** en `conclusions`, `recommendations`, `comparison_analysis`, `unified_conclusions` y `consolidated_*` | 32/32 |
| **Cero cifras en formato inglés** en los datos que construye el código | 32/32 |
| Los percentiles llegan con su frase de usuario | 26/26 |

Sobre el alcance de la última fila: en los prompts de monitoreo, evidencias y
consolidado se comprueba **el bloque de datos que construye el código**, no los
textos de IA anteriores que esos prompts embeben (análisis de imágenes y de
secciones ya guardados). Esos textos son de la Etapa 2 y traen sus propias
cifras a la inglesa; se corregirán solos cuando se regeneren.

Ejecuciones cubiertas: `ff186cc7` para el informe general y las transacciones;
`919b350d` para monitoreo y evidencias (`ff186cc7` no tiene adjuntos);
`E2-validacion` para el consolidado.

---

## 6. Un error que cometí y cómo quedó

La primera pasada de la prueba con stubs **llamó a los endpoints de monitoreo y
evidencias tal cual, y esos endpoints guardan**. El resultado: el análisis
global de monitoreo y el de evidencias de la ejecución `919b350d` quedaron
sobrescritos con el texto del stub.

- **Qué se perdió:** las dos claves `monitoring_ai_analysis` y
  `evidence_ai_analysis` de esa ejecución. Los análisis **por imagen** no se
  tocaron, y ninguna otra ejecución se vio afectada.
- **Cómo quedó:** las dos claves se borraron, así que esa ejecución está como si
  nunca se hubiera generado el análisis global. Fredy puede regenerarlo desde la
  pantalla de Monitoreo y de Evidencias cuando quiera; son dos llamadas.
- **Qué se cambió para que no vuelva a pasar:** la prueba desactiva `commit`
  mientras construye esos prompts y hace `rollback` al terminar. Verificado: la
  segunda pasada no dejó rastro en base.

No se creó ningún informe integrado: ese `INSERT` falló por clave foránea antes
de escribir.

---

## 7. Regresión

`pytest tests/` completo dentro del contenedor:

```
1 failed, 467 passed, 5 warnings in 12.13s
```

El único fallo es
`test_analysis_pipeline.py::test_pipeline_parsea_jtl_y_popula_metricas_basicas`,
y **es anterior a la Etapa 3**: parchea `app.services.ai.analysis_pipeline.time`
y ese módulo ya no importa `time`. Comprobado con el árbol limpio en `533bade`:
falla exactamente igual. Queda anotado en `37_HF-3_deuda.md` §6.

Las 57 pruebas de `test_estilo.py` siguen en verde.

---

## 8. Decisiones técnicas de este sub-paso

| # | Decisión | Por qué |
|---|---|---|
| T6 | El comparativo carga vs estrés **sí dictamina** | Es un informe completo con recomendaciones de capacidad, no una sección de otro informe. Las conclusiones unificadas y el consolidado del integrado, igual |
| T7 | `build_tier_summary` conserva su nombre | Lo importan otros módulos; lo que se fue es la palabra «tier» de su salida, que es lo que veía el modelo |
| T8 | `prepare_insights_for_prompt` y las claves `tiers['critical']`… **no cambian** | Son nombres internos que el modelo nunca ve. Renombrarlos habría tocado `analysis_pipeline`, los verdicts y el fallback sin ganar nada |
| T9 | El análisis de imagen recibe el bloque de estilo dentro del prompt, no por `_generate` | No pasa por `_generate`: la llamada multimodal es directa. Es la única excepción y está comprobada |
| T10 | La variable local `pct` de `analyze_errors` pasó a `porcentaje` | Tapaba al helper `pct()` importado de `estilo.py` |

---

## 9. Lo que este sub-paso NO hizo

- **Ningún texto se regeneró.** Los informes guardados siguen con los textos de
  la Etapa 2; los prompts nuevos solo actúan en la próxima generación. Eso es
  3.5.
- **Ningún endpoint devuelve `style_warnings` todavía.** Eso es 3.4.
- La parada de D36 en `Dashboard.tsx` (reporte 30 §3) sigue abierta.

Siguiente: 3.4, el aviso de estilo en pantalla.
