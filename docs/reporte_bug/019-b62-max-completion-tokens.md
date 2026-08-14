# 019 — B6.2: compatibilidad `max_completion_tokens` para modelos de nueva generación

**Fecha:** 2026-08-14
**Estado:** ✅ Implementado y validado contra la API real. "Probar Conexión" con **gpt-5 pasa**.
**Alcance:** 3 archivos, **+74 / −16** (61 de las líneas nuevas son el helper + comentarios en `gemini.py`).
**Origen:** pendiente declarado en `b6-fix-selector-modelo.md`; error real de Fredy al probar gpt-5.
**Numeración:** había 18 reportes → este es el **019**.

`py_compile` OK (3) · backend reiniciado sin build · backups `.bak_b62_20260814_155302`.

---

## 1. Inventario previo (read-only)

`grep -rn "chat.completions.create" backend/app` → **4 puntos** donde se arma una llamada OpenAI. **Los 4 quedan cubiertos**:

| # | Punto | Qué es | Tope que usaba |
|---|---|---|---|
| 1 | `ai_config.py:428` | **Probar Conexión** (el que falló) | `max_tokens=10` |
| 2 | `gemini.py:733` | Análisis de secciones (`_generate`) | `_openai_max_tokens_for(model)` |
| 3 | `gemini.py:835` | Visión (análisis de imágenes) | `min(_openai_max_tokens_for(model), 1024)` |
| 4 | `script_ai.py:1726` | Diseñador IA (`_call_ai`: generar, refinar, chunks) | `effective_max_tokens` |

El resto de coincidencias de `max_tokens` en el repo son **variables locales y textos de log**, no kwargs de la API (verificado tras el fix: `grep "max_tokens="` solo devuelve dos strings de logging).

**Dónde vive el helper:** en `gemini.py`, junto a `_openai_max_tokens_for`. Justificación por estructura real: `script_ai.py` **ya importa** `OPENAI_MAX_TOKENS` desde ahí (`:54-56`), así que `gemini.py` ya es el módulo compartido de configuración OpenAI. Crear un módulo nuevo habría añadido una capa sin resolver nada. `ai_config.py` no importaba de `gemini.py`; se añadió un import local dentro de la función para no crear un import circular a nivel de módulo.

---

## 2. Estrategia elegida: **prefijos + aprendizaje del 400 como red de seguridad**

Las dos opciones del enunciado, combinadas — que es lo que el propio enunciado marca como aceptable:

```python
_OPENAI_NEWGEN_PREFIXES = ("gpt-5", "o1", "o3", "o4")
_openai_token_param_cache: Dict[str, str] = {}

def _openai_token_param(model_name, limit) -> dict      # kwarg correcto, cacheado
def _openai_is_token_param_error(err) -> bool           # ¿el 400 es de este parámetro?
def openai_chat_completion(client, model_name, messages, limit, **kwargs)
```

**Por qué las dos y no una:**

- Solo prefijos → frágil ante un modelo futuro que no empiece por `gpt-5`/`o*`. Volveríamos al mismo 400.
- Solo fallback → **todo** modelo nuevo paga un 400 antes de acertar, y en el flujo de análisis (12+ llamadas) eso es ruido y latencia.
- Juntas: los modelos conocidos aciertan a la primera; los desconocidos aprenden solos, **una vez por proceso**, y quedan cacheados.

`openai_chat_completion` reintenta **una sola vez** y solo si el error es exactamente el del parámetro; cualquier otro error (429, key inválida, etc.) se propaga intacto, sin cambiar el comportamiento de reintentos que ya existía.

---

## 3. Techo de tokens para gpt-5 (punto 3)

Añadida **una** entrada nueva a `OPENAI_MAX_TOKENS`:

```python
# B6.2: la familia gpt-5 exige max_completion_tokens (ver openai_chat_completion).
# 16384 conservador, alineado con gpt-5-mini; su techo real documentado es mayor.
"gpt-5": 16384,
```

`gpt-5-mini` (16384) y `gpt-5-nano` (8192) ya estaban; faltaba `gpt-5` a secas, que es justo el que Fredy seleccionó — habría caído al default de 4096 con el warning de B6. **Ninguna entrada existente se modificó** (regla de doble uso: los consumidores son `gemini.py` y `script_ai.py`, y añadir una clave nueva no altera a los demás modelos).

Resolución verificada en el contenedor:

```
gpt-4.1     max_tokens              techo=32768
gpt-4o      max_tokens              techo=16384
gpt-5       max_completion_tokens   techo=16384
gpt-5-mini  max_completion_tokens   techo=16384
o1 / o3-mini / o4-mini              max_completion_tokens
modelo-futuro-x  max_tokens         techo=4096 (+ warning de B6)
```

---

## 4. Validación

### 4.1 Contra la API real — Probar Conexión

| Modelo | Antes | Ahora |
|---|---|---|
| **gpt-5** | 400 `'max_tokens' is not supported…` | **`{"status":"ok","message":"Conexion exitosa. Respuesta: OK"}`** |
| **gpt-4.1** | ok | **ok** (sin regresión del camino clásico) |

### 4.2 Hallazgo durante la validación: respuesta vacía en modelos de razonamiento

En la primera corrida, gpt-5 devolvió `status: ok` pero **`Respuesta: ` vacía**. No era un fallo del fix: los modelos de razonamiento consumen el tope en tokens internos, y con `max_completion_tokens=10` no queda ninguno para el texto visible. Fredy habría visto "Conexión exitosa" con una respuesta en blanco y habría dudado del resultado.

Corregido en el mismo punto (3 líneas): **256 tokens para los de razonamiento, 10 para los clásicos**. Sigue siendo un coste despreciable para un test puntual. Tras el ajuste, **gpt-5 responde `OK` igual que gpt-4.1**.

### 4.3 Aprendizaje y caché (prueba determinista, sin coste de API)

Con un cliente falso y un modelo que **no** coincide con ningún prefijo conocido:

```
kwarg inicial (adivinado): max_tokens
1a llamada -> RESPUESTA-OK | intentos: ['max_tokens', 'max_completion_tokens']   ← aprende
2a llamada -> RESPUESTA-OK | intentos: ['max_completion_tokens']                 ← ya no reintenta
cache aprendida: max_completion_tokens
WARNING modelo modelo-razonador-futuro-2027 exige max_completion_tokens; cacheado…
```

**El 400 se paga una sola vez por proceso.** Con gpt-5 ni siquiera eso: acierta por prefijo y en los logs **no hay ni un reintento** (`grep "exige max_completion_tokens"` → 0 durante las pruebas reales).

### 4.4 Estado de `ai_config` — sin cambios

`SELECT` antes y después, **idénticos**:

```
provider | model_name | is_active | daily_used | monthly_used | key_len
openai   | gpt-5      | t         | 0          | 48           | 312
```

> ⚠️ **Corrección a un supuesto del encargo:** el enunciado decía "gpt-4.1 sigue siendo el activo". **No lo es: la configuración persistida ya está en `gpt-5`** — quedó así cuando probaste el modelo y el test falló. No lo cambié: restaurar a gpt-4.1 habría sido alterar tu configuración por una suposición mía. Consecuencia práctica: **tu próximo análisis usará gpt-5**. Si quieres volver a gpt-4.1, cámbialo en la UI (o dímelo y lo hago).

No se ejecutó ningún análisis completo — cuota intacta. Las únicas llamadas reales fueron 5 tests de conexión (10-256 tokens cada uno).

---

## 5. Historial

```
$ git log --oneline -1
bf8b8f0 B6.2: compatibilidad max_completion_tokens para modelos de nueva generacion
```

Anteriores: `5f30b96` (SEC-2) · `89dbccc` (SEC-1) · `24eb0a5` (R1) · `0dc5cd4` (F5).

---

## 6. Instrucción para Fredy

1. **Configuración de IA → seleccionar gpt-5 → Probar Conexión.** Debe responder *"Conexión exitosa. Respuesta: OK"*. (La config ya está en gpt-5; el selector solo lo confirma.)
2. Si quieres la prueba de verdad: **corre UN análisis** de un JTL pequeño con gpt-5 y compáralo con uno de gpt-4.1.
3. **Advertencias antes de hacerlo**, para que ningún resultado te sorprenda:
   - Los modelos de razonamiento son **más lentos**: piensan antes de responder, y son 12+ secciones por análisis. Espera un tiempo total mayor que con gpt-4.1 — tenlo en cuenta si cronometras para DPERF-1.
   - **Consumen más tokens por respuesta** (los de razonamiento interno también se facturan) con el mismo texto visible de salida.
   - El techo de salida está en **16384** conservador. Si algún análisis sale truncado, subirlo es una línea en `OPENAI_MAX_TOKENS`.
   - Si el texto sale más corto de lo normal, avisa: sería señal de que el razonamiento se está comiendo el presupuesto y hay que subir ese techo.
4. El Diseñador IA y el análisis de imágenes quedaron cubiertos por el mismo helper: si cambias a gpt-5, **no** volverá a aparecer el 400 en esas pantallas.

---

## 7. Higiene

- `origin` (producción) **no se tocó**. Push únicamente a `github backup-trabajo-local`.
- Backups `.bak_b62_20260814_155302` de los 3 archivos.
- Sin `docker compose build`; `docker restart jmeter_backend` · `health=200`.
- No se tocó el modelo persistido, ni prompts, ni el selector (punto 4 del encargo).
- Coste de la validación: 5 llamadas de test (≤256 tokens). **Ningún análisis completo ejecutado.**
