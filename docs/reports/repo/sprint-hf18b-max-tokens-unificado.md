# HF18b (REAL) — Diagnóstico forense del max_tokens de gpt-4.1

## TL;DR

La generación de JMX **ya usa 32768** con gpt-4.1. No había un bug de
`max_tokens=4096` en el path de generación. El `4096` que aparece en los logs
proviene **solo del endpoint de refine quirúrgico**, donde es **intencional**
(devuelve un JSON de operaciones pequeño, no un JMX completo). Se aplicaron dos
mejoras defensivas menores y se confirmó por logs que la generación corre a
32768.

## Diagnóstico forense (read-only)

### Paths que llaman al SDK de OpenAI

- **Un solo `client.chat.completions.create` en `script_ai.py`** (línea ~1669,
  dentro de `_call_ai`). **Toda** la generación de JMX pasa por ahí:
  `/generate`, `/generate-from-file`, la auto-continuación (Sprint 2.7b),
  `/refine` y el refine quirúrgico. No hay llamadas al SDK dispersas.
- `gemini.py` tiene otras 2 llamadas OpenAI (líneas 701, 808) pero son del
  **análisis de JTL / imágenes**, no del Diseñador IA. Ambas ya usan el dict.
- **No existe** ningún "HF17 GUARDIAN" ni "Emergency finalization" en el
  backend (0 coincidencias). Ese concepto no aplica a este código.

### Cómo se calcula el max_tokens efectivo en `_call_ai`

```python
if max_tokens_override is not None:
    model_ceiling = OPENAI_MAX_TOKENS.get(model, OPENAI_DEFAULT_MAX_TOKENS)
    effective_max_tokens = min(max_tokens_override, model_ceiling)
else:
    effective_max_tokens = OPENAI_MAX_TOKENS.get(model, OPENAI_DEFAULT_MAX_TOKENS)
```

Los 5 call-sites de `_call_ai` y su resultado para el modelo activo `gpt-4.1`:

| Call site | override | Resultado gpt-4.1 |
|---|---|---|
| `/generate` | — | `get("gpt-4.1")` = **32768** ✅ |
| `/generate-from-file` | — | **32768** ✅ |
| auto-continuación (2.7b) | — | **32768** ✅ |
| `/refine` | `OPENAI_MAX_TOKENS.get(model)` = 32768 | `min(32768, 32768)` = **32768** ✅ |
| **refine quirúrgico** (línea 2540) | **`4096` hardcoded** | `min(4096, 32768)` = **4096** (intencional) |

### Origen real del "4096" en los logs

1. **Refine quirúrgico** — `_call_ai(messages, ai_conf, max_tokens_override=4096)`
   con el comentario *"The operations JSON is small, 4096 is plenty."* Devuelve
   un parche JSON diminuto, no un JMX. **Es correcto, no se toca** (regla:
   hardcodes intencionales se reportan, no se arreglan).
2. **Logs históricos con `model=gpt-4o`** — anteriores al cambio de modelo en DB
   (HF18b sesión previa). Prueban que esos `16384`/`4096` son de antes de activar
   gpt-4.1; no representan el comportamiento actual.

### Confirmación del modelo activo

```
SELECT model_name FROM ai_config WHERE is_active=true;  -> gpt-4.1  (exacto)
```

`gpt-4.1` **ya estaba** en `OPENAI_MAX_TOKENS` con `32768`
(`backend/app/services/ai/gemini.py:46`).

## Conclusión sobre la baja cobertura con Pideky

No se puede atribuir a un `max_tokens=4096` en la generación: ese path corre a
32768. Si hubo truncación, el origen es otro (densidad del prompt, "stop
mentiroso" ya cubierto por HF18a, o tamaño del HAR), y se debe medir con la
prueba real de Pideky ahora que gpt-4.1 corre a plena capacidad.

## Cambios aplicados (2 defensivos, ningún fix del path de generación)

1. **`gpt-4.1-mini` 16384→32768 y `gpt-4.1-nano` 8192→32768**
   (`gemini.py`). Estaban infra-provisionados: si algún día se activa una
   variante, truncaría sin causa visible. La familia gpt-4.1 soporta 32K.
   `gpt-4.1` (modelo activo) ya estaba correcto.
2. **WARNING de "modelo ausente del dict"** en `_call_ai` (`script_ai.py`):

   ```python
   if model and model not in OPENAI_MAX_TOKENS:
       logger.warning("model '%s' NOT in OPENAI_MAX_TOKENS; usando default %d "
                       "(posible truncacion). Agregalo al dict.", model, OPENAI_DEFAULT_MAX_TOKENS)
   ```

   Este log habría avisado de inmediato ante un modelo nuevo sin entrada en el
   dict (la clase de bug que se sospechaba).

## Lo que NO se tocó (reportado, no arreglado)

- **Refine quirúrgico `max_tokens_override=4096`**: intencional (JSON pequeño).
- **Modelo gpt-4o en el dict (16384)**: intacto, disponible para rollback.

## Validaciones

- **Restart backend** (sin rebuild): arranca healthy, sin errores.
- **Curl `/generate` (3 samplers GET):** HTTP 200, `is_valid=True`, cierra
  `</jmeterTestPlan>`, 3 samplers, sin error.
- **Log del call:** `OpenAI call model=gpt-4.1 max_tokens=32768 finish_reason=stop`.
- **Tests:** `199 → 200 PASS` (+1: variantes gpt-4.1 = 32768), 2 slow
  deselected, 0 regresiones.

## Estado

LISTO para la prueba REAL con `qa_pideky_com5.har`: gpt-4.1 confirmado corriendo
a 32768 en el path de generación. Si la cobertura sigue baja, el cuello de
botella no es max_tokens y hay que mirar prompt/HAR.

## Archivos

- `backend/app/services/ai/gemini.py` — mini/nano → 32768.
- `backend/app/api/v1/endpoints/script_ai.py` — WARNING modelo ausente en `_call_ai`.
- `backend/tests/test_openai_max_tokens.py` — +1 test (variantes).
- Backups: `gemini.py.bak_hf18b_20260708_113410`,
  `script_ai.py.bak_hf18b_20260708_113410`,
  `ai_config_backup_20260707_200456.sql` (sesión previa).
