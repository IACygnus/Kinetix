# B6.3 — Fallback silencioso: causa raíz, mensaje honesto y prompts más puntuales

**Fecha:** 2026-08-16
**Commit:** `fa43d6d` — *B6.3: diagnostico de fallback silencioso + mensaje
honesto + prompts mas puntuales*
**Push:** `github/backup-trabajo-local` (`0789548..fa43d6d`). **`origin` NO se
tocó.**
**Estado:** **CAUSA RAÍZ CONFIRMADA CON DATOS · CORREGIDA · VERIFICADA CON LOS
DOS MODELOS.**

**Presupuesto:** B+C ~40-70 líneas → **76 insertadas / 11 borradas, 3 archivos.**
**Llamadas reales de IA:** **5** (declaré un máximo de 2-3; me pasé — detalle y
justificación en §6).

---

## PARTE A — DIAGNÓSTICO

### A.1 Los logs de las 16:41 del 16/08 no existen

Hay que decirlo tal cual: **no pude leerlos.** El buffer del contenedor tiene
30.835 líneas pero su última ejecución registrada es `f22ab720` y no contiene ni
una línea con `gpt-5`. Además los timestamps del log están desfasados (marcan
junio), por lo que `--since 48h` devuelve cero. La evidencia del incidente salió
entonces de la base de datos y del código, no de los logs.

Lo que sí confirma la base:

```sql
SELECT id, created_at, LEFT(ai_analysis_summary,90), LENGTH(ai_analysis_summary)
FROM test_executions WHERE id::text LIKE 'bf9ffd01%';

bf9ffd01… | 2026-08-16 16:41:59 | "La prueba proceso 25,773 solicitudes con una
tasa de error del 0.39% y un tiempo de respue…" | 807
```

807 caracteres de plantilla estadística: es `FallbackAnalyzer`, confirmado.

### A.2 El circuit breaker NO se abrió

`gemini.py:820` solo abre el circuito cuando se agotan los reintentos en la rama
de *rate limit*. El fallo real salía por otra rama y devolvía `None` de
inmediato, sección por sección. Por eso las 12 cayeron al fallback **sin** que
el circuito se abriera.

### A.3 El kwarg de tokens era el correcto

`_OPENAI_NEWGEN_PREFIXES = ("gpt-5", "o1", "o3", "o4")` y
`"gpt-5-mini".startswith("gpt-5")` → **True**. Verificado en ejecución:

```
modelo=gpt-5-mini | kwarg={'max_completion_tokens': 16384}
```

B6.2 estaba bien hecho. El problema era otro.

### A.4 El techo de 16384 sobraba

### A.5 La prueba controlada (la que decide)

**Llamada real 1** — con la configuración exacta del pipeline:

```
modelo=gpt-5-mini | kwarg={'max_completion_tokens': 16384} | temperature=0.7

*** EXCEPCION: BadRequestError
    Error code: 400 - {'error': {'message': "Unsupported value: 'temperature'
    does not support 0.7 with this model. Only the default (1) value is
    supported.", 'type': 'invalid_request_error', 'param': 'temperature',
    'code': 'unsupported_value'}}
```

**Llamada real 2** — lo mismo, sin `temperature`:

```
finish_reason : stop
content       : 1357 caracteres
usage         : prompt=565 completion=1118 total=1683
  detalle completion: CompletionTokensDetails(reasoning_tokens=768, …)

VEREDICTO: DEVUELVE ANALISIS
```

### A.6 Causa raíz

**`gpt-5-mini` rechaza `temperature=0.7` con un 400.** El pipeline la manda en
todas las llamadas (`gemini.py:792`), así que **todas** las secciones fallaban.

**La hipótesis principal queda refutada, y conviene dejarlo escrito:** no era el
presupuesto de razonamiento. El modelo gastó **1.118 tokens de completion (768
de razonamiento) de los 16.384 disponibles** — sobraba margen de sobra. Subir el
techo no habría arreglado nada.

Y encaja con `error=null`: el 400 se atrapaba en `_generate`, se logueaba y se
devolvía `None`, pero **el motivo no subía a `ai_status`**, que solo se rellena
cuando el fallo escapa hasta el pipeline.

---

## PARTE B — CORRECCIONES

### B3 · La temperatura se filtra en el único punto de paso

En `openai_chat_completion`, por donde pasan todas las llamadas de chat, con la
misma estrategia híbrida de B6.2 — se evita por prefijo conocido y, si aun así
llega el 400, se aprende y se cachea por modelo:

```python
if "temperature" in kwargs and not _openai_temperature_kwarg(model_name, kwargs["temperature"]):
    kwargs = {k: v for k, v in kwargs.items() if k != "temperature"}
...
except Exception as e:
    if _openai_is_temperature_error(e) and "temperature" in kwargs:
        _openai_no_temp_cache[model_name] = True
        ...retry sin temperature...
```

Los 12 pasos del pipeline no se tocaron.

### B2 · El fallback deja de ser invisible

```python
if not result:
    fin = getattr(response.choices[0], "finish_reason", "?") …
    motivo = f"{self.model_name} devolvio contenido vacio (finish_reason={fin})"
    logger.error(f"AI EMPTY for {section_name}: {motivo}")
    GeminiAnalyzer._last_error = motivo
```

Y en el pipeline, cuando no hubo excepción pero tampoco éxito:

```python
if not ai_status.get("success") and not ai_status.get("error"):
    ai_status["error"] = GeminiAnalyzer._last_error or f"{provider} no devolvio analisis; se uso el analizador de respaldo"
```

### B1 · El aviso ya no miente

`Dashboard.tsx:630` decía siempre `'Gemini no disponible'`, incluso con OpenAI.
Ahora usa el motivo real y, si no lo hay, nombra provider y modelo reales:

```tsx
: aiToast.error
  || `${aiToast.provider || 'El proveedor de IA'} ${aiToast.model || ''} no devolvio analisis: se uso el analizador de respaldo`
```

---

## PARTE C — PROMPTS MÁS PUNTUALES

Cuatro reglas nuevas en el `SYSTEM_PROMPT` (empezar por el dato, prohibido el
preámbulo, prohibido el cierre que repite, fuera el relleno), párrafos de 3-5 a
2-4 oraciones, y un segundo ejemplo de lo que **no** hay que escribir.

**El hallazgo que hacía falta:** los topes de palabras estaban **en conflicto**.
El sistema pedía un máximo y cada sección pedía otro mayor — y ganaba el de la
sección. Alineados:

| Sección | Antes | Ahora |
|---|---|---|
| Tabla resumen | 250 | **150** |
| Cada gráfica (×7) | 200 | **120** |
| Errores | 200 | **120** |
| Redirecciones | 200 | **120** |
| Conclusiones | 600 | **350** |
| Recomendaciones | 600 | **350** |

**Techo por informe: 3.250 → 1.930 palabras, un 41% menos** (~5.200 → ~3.088
tokens de salida a 1,6 tok/palabra).

**Coste honesto del cambio:** el `SYSTEM_PROMPT` pasa de 1.611 a 2.445
caracteres (~403 → ~611 tokens), y va en **cada** llamada: +208 tokens × 14
llamadas ≈ **+2.900 tokens de entrada** por informe, contra ~2.100 menos de
salida. En dinero salen parecidos (la entrada es más barata); la ganancia real es
**tiempo de generación y legibilidad**, no factura.

**Medición, sin adornos:** en prueba aislada el mismo prompt pasó de **456 a 335
palabras (-27%)** solo con el `SYSTEM_PROMPT`. Los topes por sección no entran en
esa prueba porque llamé a `_generate` directamente. Y hay que decirlo: **los
modelos se saltan el tope** — con 120 pedidas escribieron 335. El tope empuja
hacia abajo, no garantiza. La reducción real se verá en tu próximo informe
completo.

Lo que **no** se tocó: las palabras prohibidas, `sanitize_ai_text`, y la mención
obligatoria de picos — ahora es regla explícita (nº 15) además de vivir en el
prompt de la gráfica. Los análisis de imagen (Vision, 300/200 palabras) quedan
como estaban: no son secciones del informe.

---

## VALIDACIÓN

**Llamadas 3 y 4** — por el camino real (`_generate`), tras el fix:

```
gpt-5-mini: ANALISIS OK — 2860 caracteres, 456 palabras
  palabras prohibidas: ninguna
  menciona el pico (max): SI ['21060', '21058']
  markdown residual: no

gpt-4.1:    ANALISIS OK — 2424 caracteres, 386 palabras
  palabras prohibidas: ninguna
  menciona el pico (max): SI ['21060', '21058']
  markdown residual: no
```

**Llamada 5** — tras alinear los topes:

```
gpt-5-mini: ANALISIS OK — 2047 caracteres, 335 palabras
  palabras prohibidas: ninguna | menciona el pico: SI | markdown: no
```

**Los dos modelos sirven.** `gpt-5-mini` funciona perfectamente para esto: no
hace falta que cambies de modelo. Y la lección GRAF1 sobrevive: los dos citan
los picos de 21.060 y 21.058 ms.

---

## 6. Coste de IA: me pasé del límite que declaré

Dije 2-3 llamadas y usé **5**: dos de diagnóstico (una falló con el 400, sin
tokens de salida), dos de la validación que pedía el encargo (`gpt-5-mini` y
`gpt-4.1`) y una quinta tras alinear los topes. Las tres últimas eran la
validación exigida; la quinta la decidí yo para no reportar un número sin
medirlo. Coste total: unos 6.000 tokens, céntimos. Lo digo porque el límite lo
puse yo y lo rebasé.

---

## 7. Un aviso que no tiene que ver con este sprint

Al revisar el árbol antes de commitear vi **5 reportes borrados del working
tree** que yo no toqué y que **no están en el commit** (verificado:
`git show --stat fa43d6d` solo lista mis 3 archivos):

```
 D docs/reporte_bug/dperf1-fixes-bcd.md
 D docs/reporte_bug/graf1-fix-serie-dual.md
 D docs/reporte_bug/graf1a-serie-ia.md
 D docs/reporte_bug/graf1b-pantalla.md
 D docs/reporte_bug/graf1c-exports.md
```

`sprint-hf18b` sí aparece movido a `docs/reports/repo/`, pero **los cuatro
`graf1*` y `dperf1` no están en ninguna parte del árbol**. Como el borrado está
sin commitear, se recuperan con:

```
git restore docs/reporte_bug/graf1-fix-serie-dual.md docs/reporte_bug/graf1a-serie-ia.md \
            docs/reporte_bug/graf1b-pantalla.md docs/reporte_bug/graf1c-exports.md \
            docs/reporte_bug/dperf1-fixes-bcd.md
```

No lo he ejecutado: si los borraste a propósito, restaurarlos sería deshacer tu
decisión. Tú dices.

---

## 8. Archivos tocados

| Archivo | Qué | Backup |
|---|---|---|
| `backend/app/services/ai/gemini.py` | filtro de temperatura + motivo del fallo + prompts | `.bak_b63_20260816_114730` |
| `backend/app/services/ai/analysis_pipeline.py` | `ai_status.error` cuando el fallback es silencioso | `.bak_b63_20260816_114730` |
| `frontend/src/components/dashboard/Dashboard.tsx` | mensaje con provider/modelo/motivo reales | `.bak_b63_20260816_114730` |

`py_compile` limpio · `tsc --noEmit` exit 0 · backend reiniciado **sin build**.

**Pendiente tuyo:** genera un informe real con `gpt-5-mini` y comprueba que ya
no sale el analizador de respaldo, y de paso mira si los textos te resultan más
directos.
