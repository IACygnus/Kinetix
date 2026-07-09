# Sprint 2.8 — SYSTEM_PROMPT para flujos enterprise

> Mejora del SYSTEM_PROMPT del Diseñador IA tras el caso real **Bancoomeva**
> (HAR enterprise). Origen: `docs/reports/comparativa-jmx-bancoomeva.md`.
> **Fecha:** 2026-06-17

---

## Problema (de comparativa-jmx-bancoomeva.md)

Tras el Sprint 2.7 (truncación resuelta), el JMX generado para Bancoomeva estaba
truncado **en calidad**, no en longitud:

| Métrica | Esperado | Generado |
|---|---|---|
| Samplers | 22 | 6 |
| UDV | 8 | 0 |
| Extractores | 8 | 0 |

Bugs concretos:
1. Dominios **hardcodeados** en los samplers (sin parametrizar).
2. **Cero extractores** de tokens (los samplers siguientes necesitan
   `tokenIdCliente`, `authToken`, etc.).
3. UDV vacío.
4. Endpoints faltantes (sin logout, sin EjecutarMotor).

---

## Cambios en `SYSTEM_PROMPT` (base)

Tres secciones nuevas insertadas **antes de `## FORMATO DE RESPUESTA`** (sin
tocar las reglas existentes):

1. **REGLAS DE CORRELACIÓN Y AUTENTICACIÓN (CRÍTICAS)** — detectar tokens JWT/
   Bearer, tokens de transacción (`tokenIdCliente`, `sessionId`, `csrf_token`),
   cookies de sesión (Cookie Manager, no extractor) y headers de auth que rotan.
   Incluye **ejemplo XML completo de `RegexExtractor`**.
2. **REGLAS DE MULTI-DOMINIO Y UDV (CRÍTICAS)** — una UDV por dominio único
   (`host_main`, `host_auth`, `host_user`, `host_products`, `host_pagos`…), con
   heurística de rol por path. Prohíbe hardcodear dominios.
3. **REGLAS DE COBERTURA DEL FLUJO (CRÍTICAS)** — incluir TODOS los requests
   funcionales (omitir solo assets/tracking), cubrir login → operaciones →
   logout, numerar samplers en orden cronológico.

## Cambios en `SYSTEM_PROMPT_CONSERVATIVE` (Sprint 2.7c)

Bloque **"REGLAS CRÍTICAS NO NEGOCIABLES (aplican AÚN en modo conservador)"**
añadido en versión condensada: correlación, multi-dominio y cobertura. La
economía de tokens de 2.7c se mantiene, pero **no a costa de la calidad** del
script (extractores y UDV siguen siendo obligatorios).

### Tamaño de los prompts (sano)

| Prompt | Antes | Ahora |
|---|---|---|
| `SYSTEM_PROMPT` | ~9.6K chars | **14 738 chars** (<30K) |
| `SYSTEM_PROMPT_CONSERVATIVE` | ~2.7K chars | **3 226 chars** |

---

## Verificación del HAR compressor (Parte 5 — read-only, NO modificado)

`backend/app/services/engine/har_compressor.py`:

| Aspecto | Estado |
|---|---|
| Headers de auth (`Authorization`, `x-api-key`, `x-auth-token`, `x-csrf-token`) | ✅ **Preservados** (`KEEP_HEADERS` tiene precedencia sobre los prefijos de ruido). |
| Response bodies (json/xml/text) | ✅ **Mantenidos**, truncados a `MAX_BODY_BYTES=2048` → la IA ve `"access_token":"..."`. |
| `_is_tracking()` vs endpoints de auth | ✅ Solo filtra dominios de analytics externos (GA, Hotjar, Sentry, NewRelic…); **no** filtra `/auth`, `/login`, `/oauth`. |
| Cookies de sesión (`Cookie` / `Set-Cookie`) | ⚠️ **Eliminadas** — están en `NOISE_HEADER_PREFIXES` y no en `KEEP_HEADERS`. |

**Conclusión:** el compressor NO sabotea la detección de tokens basados en
header `Authorization` ni en response body (los dos casos principales). El prompt
nuevo trabaja con información suficiente.

**Pendiente documentado (no se tocó este sprint):**
- ⚠️ `Set-Cookie` se elimina antes de llegar a la IA → la IA no puede *detectar*
  flujos basados en cookies de sesión. JMeter las maneja en runtime vía Cookie
  Manager, pero si un caso real depende de leer un valor de cookie, habría que
  mover `set-cookie` a `KEEP_HEADERS`. Evaluar en sprint posterior.
- ⚠️ Truncado de body a 2 KB podría cortar un token que aparezca tarde en un
  response grande. Tradeoff heredado de 2.7; revisar si surge un caso real.

---

## Tests — `backend/tests/test_script_ai_prompt_enterprise.py` (nuevo, 68 líneas, 8 tests)

Verifican el **contenido** de ambos prompts:
- Base: reglas de correlación / multi-dominio / cobertura, ejemplo de
  `RegexExtractor`, patrones de token comunes (≥2), subdominios funcionales (≥2).
- Conservador: mantiene correlación y multi-dominio.

---

## Validaciones

| Check | Resultado |
|---|---|
| `pytest -m "not slow"` | **165 passed**, 2 deselected |
| Tests nuevos | 8 PASS |
| Backend reload | `Application startup complete` (sin errores de import) |
| `SYSTEM_PROMPT` size | 14 738 chars (<30K) |
| `script_ai.py` | 3094 → 3188 líneas (+94) |
| Docker rebuild | **NO** |
| Backup | `script_ai.py.bak_28_20260617_113900` |

> El efecto real (22 samplers / 8 UDV / 8 extractores) sólo se confirmará con la
> **validación visual de Fredy** re-generando el JMX de Bancoomeva contra OpenAI
> en vivo. Los tests garantizan que las instrucciones están en los prompts, no
> que el modelo las cumpla — eso es validación visual.

---

## Pendientes Sprint 2.9

- **Multi-HAR** (UI + backend) para flujos divididos en varios archivos.
- Posible ajuste de `KEEP_HEADERS` para `set-cookie` si un caso lo requiere.
- Ajustes adicionales tras validar el primer caso real (Bancoomeva).

## Estado: LISTO para Sprint 2.9 (multi-HAR)
