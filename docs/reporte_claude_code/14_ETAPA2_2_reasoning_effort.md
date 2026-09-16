8db8c65 · 2026-09-15

# ETAPA 2.2 — `reasoning_effort` configurable (D13) + D14

**Llamadas reales a la IA en este sub-paso: 1** (la autorizada: `POST /ai-config/test`).
Presupuesto de etapa: **1 / 50**.
**Ningún archivo protegido tocado.** 11 archivos, 131 inserciones / 6 eliminaciones.

---

## 1. Verificación previa contra el SDK (D13a)

`openai 2.54.0` define `ReasoningEffort` como
`Literal['none','minimal','low','medium','high','xhigh','max']`, y
`chat.completions.create` acepta `reasoning_effort` (y `verbosity`).

**Se exponen solo `low`, `medium` y `high`**, como fija D13a. Los otros cuatro existen en el SDK
pero no se ofrecen: exponer un valor que el modelo concreto rechace reproduciría el patrón B6.3
(un 400 a mitad de informe, con el trabajo ya empezado).

---

## 2. Persistencia (D13b)

`docs/sql/etapa2_reasoning_effort.sql`, idempotente:

```sql
ALTER TABLE ai_config ADD COLUMN IF NOT EXISTS reasoning_effort VARCHAR(20);
COMMENT ON COLUMN ai_config.reasoning_effort IS '...';
```

**Aplicado en local** y verificado:

```
 model_name       | character varying(100) | not null
 reasoning_effort | character varying(20)  |
```

> **Para el despliegue:** este script hay que ejecutarlo en el servidor **antes** de desplegar el
> código de la Etapa 2.
>
> **Corrección sobre lo que decía la primera versión de este reporte.** Escribí que «el arranque
> falla al mapear el modelo». **Es falso, y el modo de fallo real es peor porque es silencioso:**
>
> - `Base.metadata.create_all` (`main.py:93`) **no altera tablas existentes**, así que el backend
>   **arranca sin problema**.
> - La primera lectura de `ai_config` incluye la columna inexistente y revienta en Postgres.
> - Ese error lo atrapa el `except Exception` de `load_ai_config_from_db`, que lo degrada a
>   **`logger.warning`** y cae al fallback por variables de entorno. Sin key en el entorno
>   devuelve `{}`, no se construye el analizador y **todos los informes salen con texto de
>   `FallbackAnalyzer`**.
> - `GET /ai-config` sí responde **500**.
>
> Es decir: no hay un fallo ruidoso que avise. Los informes se seguirían generando, con texto
> genérico, hasta que alguien lo notara leyéndolos.
>
> **Verificación posterior al despliegue:** `GET /ai-config` debe responder **200** e incluir
> `reasoning_effort`. Va al checklist y se repite en el cierre de la etapa.

`NULL ⇒ low` se resuelve en tres capas (modelo, lectura de config y helper del kwarg), así que
una fila antigua sin valor se comporta igual que una con `low` explícito.

---

## 3. Cambios

| Pieza | Archivo | Qué |
|---|---|---|
| Columna | `db/models/ai_config.py` | `reasoning_effort` nullable |
| Schemas | `schemas/ai_config.py` | campo en `AIConfigRead` y `AIConfigCreate` |
| Helpers | `services/ai/gemini.py` | `REASONING_EFFORTS`, `REASONING_EFFORT_DEFAULT`, `_openai_soporta_reasoning`, `_openai_reasoning_kwarg` |
| Analizador | `gemini.py` | `__init__(..., reasoning_effort)`; el kwarg viaja en `_generate` solo si aplica |
| Singleton (D13c) | `gemini.py` | la clave pasa de `provider:model:key[:8]` a `provider:model:key[:8]:effort` |
| Carga de config | `gemini.py` | `load_ai_config_from_db` devuelve `reasoning_effort` |
| Propagación | `analysis_ai.py` (3), `integrated_report.py` (2), `compare.py`, `analysis_pipeline.py`, `transaction_report.py` | los **8** sitios que construyen el analizador pasan el effort |

**El effort aplica a TODOS los caminos de IA, no solo al informe.** Los 8 sitios cubren: informe
general (`analysis_pipeline`), informe por transacción (`transaction_report`), conclusiones
unificadas y consolidado del integrado (`integrated_report`, 2), reporte comparativo (`compare`),
y análisis de monitoreo, de evidencias y de visión (`analysis_ai`, 3). Cambiar el valor en la
pantalla de configuración los afecta a todos a la vez.
| Telemetría (D13e) | `gemini.py` | campo `reasoning_effort` en `AI_TELEMETRY` |
| Endpoint | `api/v1/endpoints/ai_config.py` | lectura, guardado con validación, y **test con el effort real (D13d)** |
| Pantalla | `AIConfigPage.tsx`, `types/index.ts` | selector junto al modelo, visible solo si aplica |
| **D14** | `gemini.py` | rate-limit: sin dormir tras el último intento |

### Decisiones declaradas

- **Validación estricta en el guardado.** `POST /ai-config` rechaza con 400 cualquier valor fuera
  de `low/medium/high`. Se prefiere fallar al guardar que a mitad de un informe.
- **El criterio de "soporta razonamiento" se duplica en el frontend** (`/^(gpt-5|o1|o3|o4)/i`)
  porque la pantalla necesita decidir si mostrar el selector sin preguntar al backend. Es la
  **única duplicación consciente** de la etapa y queda anotada en el código: si cambian los
  prefijos en `gemini.py`, hay que tocar también `AIConfigPage.tsx`.
- **El frontend solo envía `reasoning_effort` si aplica.** Con Gemini o un modelo sin soporte, la
  clave no viaja y la fila conserva lo que tuviera.

---

## 4. Un hueco de robustez encontrado al correr la regresión

Al pasar las suites de la Etapa 1, `hf2_test` reventó con
`AttributeError: 'GeminiAnalyzer' object has no attribute 'reasoning_effort'`.

El disparador era un fixture antiguo (construye el analizador con `object.__new__`), pero
**el fallo señalaba un problema real del código**: los argumentos de `_tel(...)` se evalúan
**antes** de entrar en el `try/except` de `_emit_ai_telemetry`. Es decir, una excepción al
*calcular* un argumento de telemetría **sí puede tumbar una generación**, rompiendo el invariante
que se fijó en E1.2 («la telemetría nunca interrumpe la generación»).

Corregido con `getattr(self, "reasoning_effort", None)` en los dos puntos de uso y un comentario
que explica por qué ahí no puede haber nada que lance. No es cosmética: cualquier atributo nuevo
que se añada en el futuro a esa llamada tiene el mismo riesgo.

---

## 5. Validación

### Stubs — 14/14, 0 llamadas reales

| Escenario | Resultado |
|---|---|
| `gpt-5.5` + `low` / `medium` → el kwarg viaja | PASA |
| `gpt-4o` → **no** viaja | PASA |
| `gemini-2.5-flash` → **no** viaja | PASA |
| `o3-mini` → viaja | PASA |
| Valor inválido (`turbo`) → cae a `low` | PASA |
| `None` → `low` | PASA |
| Mismo effort → misma instancia del singleton | PASA |
| **Effort distinto → instancia nueva (D13c)** | PASA |
| El kwarg llega a la llamada: `{'temperature': 0.7, 'reasoning_effort': 'medium'}` | PASA |
| Telemetría lleva el effort (D13e) | PASA |
| Telemetría con `null` cuando no aplica | PASA |
| **D14**: rate-limit duerme `[5, 10]` y no los 15 finales | PASA |

### Regresión de la Etapa 1

| Suite | Antes | Ahora |
|---|---|---|
| 1.5 (HF-2) | 12/12 | **12/12** |
| Adenda A | 8/8 | **8/8** |
| Adenda B | 8/8 | **8/8** |

**Dos aserciones de la suite 1.5 se actualizaron a propósito**, no se «arreglaron»: D14 cambia el
tiempo dormido de `30 s` a `15 s` (5+10) y, con `Retry-After: 7`, de `21 s` a `14 s`. El número de
intentos y la apertura del circuito no cambian. Codificaban la conducta anterior y ahora
codifican la nueva.

### Compilación y tipos

`py_compile` OK en los 9 archivos de backend. **`npx tsc --noEmit` → exit 0.**

### Llamada real autorizada (D13d)

```
POST /ai-config/test  →  HTTP 200
{"status": "ok", "message": "Conexion exitosa. Respuesta: OK",
 "provider": "openai", "model": "gpt-5.5"}
```

**`gpt-5.5` acepta `reasoning_effort=low`.** No se activa la PARADA por rechazo del modelo.

`GET /ai-config` devuelve `{'provider': 'openai', 'model_name': 'gpt-5.5', 'reasoning_effort': 'low'}`.
**Base local configurada en `low`.**

---

## 6. Respuesta a la pregunta de la autorización (integrado en pantalla)

| Componente | Qué hace | Qué le toca |
|---|---|---|
| `DashboardEmbed.tsx` | **Incrusta `Dashboard`** (`import Dashboard from '../dashboard/Dashboard'`) | **Hereda** el cambio automáticamente. No se toca |
| `ExecutionReportSection.tsx` | Pinta **miniaturas propias** (`AreaChart` de 250-300 px) como vista previa de selección — no es el informe | **No** usa `ReportBody`. Solo se le retira el bloque de Throughput (líneas 21, 142-146) |

Declarado como pide la autorización: **aplica el caso «incrusta Dashboard»** para la vista del
informe, y la previsualización de selección es otra cosa y se trata aparte.

---

## Estado

Sub-paso 2.2 completado. Se continúa con 2.3 (retiro de Throughput Over Time en backend e IA).
