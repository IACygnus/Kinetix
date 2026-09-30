Commit base `a8ed054` · 30 de septiembre de 2026 · diagnóstico de solo lectura (Parte B), sin commit

# Configuración de IA: por qué se fue OpenAI, y cómo guardar los dos proveedores

La Parte A de este encargo (arreglar `/ai-config/estado` con Gemini) va en su propio commit,
`a8ed054`, y se resume en §0. Todo lo demás es **lectura**. No he cambiado código, base ni
configuración. Ninguna clave se ha impreso: solo sus cuatro últimos caracteres.

Las horas de `ai_config.updated_at` y del log del backend están en **UTC** (`datetime.utcnow`). En
Colombia es UTC-5: **las «04:50» son las 23:50 del 29/09**.

---

## 0. Parte A, en una línea

`estado_ia.py` pasaba `request_options` a `genai.get_model()`. **google-generativeai 0.3.1 no lo
acepta**: su firma es `get_model(name, *, client=None)`. Con Gemini, `/estado` decía siempre
`ok:false` y el panel de subida bloqueaba, aunque la clave sirviera.

El límite de 10 s se conserva esperando la respuesta en otro hilo (`Future.result(timeout=…)`). Si
vence, el resultado es `transitorio`, con el detalle «sin respuesta en 10 s».

Comprobado dentro del proceso, **sin escribir en la base**:

| Caso | Resultado |
|---|---|
| Clave real (…zo1g) con proveedor `gemini`, modelos 3.1-flash-lite-preview y 2.5-flash | `ok:true` |
| Clave inventada | `ok:false`, `clave`: «la clave de la IA no sirve (el proveedor la rechaza)», con el `API key not valid` de Google |
| Límite de tiempo forzado a 1 ms | `ok:false`, `transitorio`, con el detalle «sin respuesta en 0.001 s» |

**En el 8001 no he podido ver el `ok:true` con Gemini**, porque mientras trabajaba la configuración
cambió (§1.2). Hoy `/estado` devuelve `ok:false` / `clave` con el 401 de OpenAI, y eso es correcto.
El panel de subida (`UploadJTL.tsx:801-813`) bloquea **solo** si `estadoIA.ok` es falso. Con Gemini
guardado dejará de bloquear, pero **eso está pendiente de tu validación visual**.

**Aviso sobre el reporte 134:** su F-7 propone `generate_content(..., request_options=…)` y afirma
que `estado_ia.py:115` «ya lo usa con este SDK». Es justo lo que fallaba. `generate_content` acepta
`**kwargs`, pero no he comprobado que 0.3.1 acepte ahí `request_options`. **F-7 no se aplica tal cual
sin probarlo antes.**

---

## 1. ¿Qué cambió a las 04:50 UTC? Solo el dato

### 1.1 Código: nada

- Ningún commit toca la configuración de IA desde el 29/09 a las 12:18 (`43b895f`, F1/F2). El commit
  de esa noche, `c64ab54` (23:23 en Colombia), es del Backend Listener de InfluxDB: `monitoring.py`,
  `script_ai.py`, `listener_influxdb.py`, etc. **No toca `ai_config.py` ni `AIConfigPage.tsx`.**
- `git status` no muestra **ningún archivo de código sin commit**. Solo hay dos reportes de otra
  sesión, sin versionar:
  - `132_S2_1_token_maestro_diagnostico.md`: S2.1, el token maestro. No tiene que ver con la IA.
  - `134_diagnostico_config_ia_gemma.md`: el diagnóstico de anoche sobre esta misma pantalla. No
    los he tocado.

### 1.2 El dato: tres guardados, todos desde el navegador (`172.18.0.1`)

Tomado del reporte 134 §0 y de `docker logs` de hoy:

| Hora UTC (Colombia) | Qué pasó | Fila `ai_config` después |
|---|---|---|
| 04:41 (23:41 del 29/09) | La pantalla carga. `/models/live?provider=openai` → **OpenAI 401 «Incorrect API key»** con la clave guardada …ouwA | openai / gpt-5.5 / …ouwA |
| 04:42 | «Probar Conexión» → openai / gpt-5.5, **401** | la misma |
| 04:50 (23:50) | `POST /ai-config` con Gemini y una clave nueva | **gemini / gemini-3.1-flash-lite-preview / …zo1g** |
| **14:12 (09:12 de hoy)** | `POST /ai-config` con el proveedor OpenAI **y sin clave nueva** | **openai / gpt-4o-mini / …zo1g** |

**Por qué se fue OpenAI:** anoche su clave ya no servía. Se guardó Gemini encima y, como `ai_config`
tiene **una sola fila y una sola clave**, la de OpenAI se sobrescribió. No hubo borrado: el diseño no
tiene sitio para dos claves.

**Estado de ahora mismo, y es un riesgo:** el proveedor dice `openai`, pero la clave es la de Gemini.
OpenAI la rechaza (`401 invalid_api_key`, el mensaje enseña `AQ.Ab8RN…zo1g`). Mientras siga así:

- el panel de subida **bloquea**, con razón. Es el aviso F1 haciendo su trabajo;
- cualquier camino que no pase por ese panel (el Script Designer con IA, el análisis de imágenes, el
  integrado) **cae al respaldo**.

Guardar el proveedor sin tocar la clave la conserva (`_is_new_plaintext_key`, `ai_config.py:257-268`).
Así se llegó a esta combinación sin que la pantalla avisara.

---

## 2. La lista de modelos: los de GPT siguen en el código

La pantalla (`AIConfigPage.tsx`) combina dos fuentes:

1. **La lista fija** `PROVIDERS` (`ai_config.py:~42-49`, vía `GET /ai-config/models`):
   - Gemini: `gemini-3.1-flash-lite-preview`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`,
     `gemini-3-flash-preview`.
   - OpenAI: `gpt-4o-mini`, `gpt-4o`, `gpt-4-turbo`, `gpt-3.5-turbo`. Está así desde `b83f736`
     (10/03/2026). **No se ha quitado nada.** Tampoco incluye `gpt-5.5`, el modelo en uso según
     CLAUDE.md §6.
2. **La lista viva**, `GET /ai-config/models/live?provider=` (`:39-58`, `:78`, `:100`, `:275`), que se
   pide al proveedor **con la clave guardada, sea del proveedor que sea** (134 §2a).

Por eso, al elegir OpenAI hoy, la lista viva manda a OpenAI la clave de Gemini, falla, y la pantalla
enseña **los cuatro modelos fijos**. Se ve `gpt-4o-mini` y no `gpt-5.5`. Los modelos de GPT **solo se
ven al elegir OpenAI**, y **solo los cuatro fijos** mientras no haya una clave de OpenAI válida.

---

## 3. La clave de OpenAI en las copias

Descifrada **solo en memoria**, dentro de `jmeter_backend`, con la `FERNET_KEY` del backend. **No se
ha escrito en la base.**

| Copia | `ai_config.updated_at` (UTC) | Proveedor / modelo | Últimos 4 |
|---|---|---|---|
| `backup_20260930_token.sql` (hecha el 29/09 a las 19:25, antes de las 04:50) | 2026-09-29 16:58 | openai / gpt-5.5 | **ouwA** |
| `backup_20260929_o2e2b.sql` | 2026-09-29 16:58 | openai / gpt-5.5 | ouwA |
| `backup_20260928_1621_preR2.sql` | 2026-09-26 17:22 | openai / gpt-5.5 | ouwA |
| `backup_20260926_1310_preR1.sql` | 2026-09-26 17:22 | openai / gpt-5.5 | ouwA |
| `backup_20260923_h8.sql` | 2026-09-22 19:30 | openai / gpt-5.5 | ouwA |
| `backup_20260922_O2c.sql` | 2026-09-18 22:25 | openai / gpt-5.5 | ouwA |

**Del 18 al 29/09 hay una sola clave de OpenAI en las copias, …ouwA**, y hoy OpenAI la rechaza:

| Prueba | Resultado |
|---|---|
| `models.retrieve("gpt-4o")` | **FALLA**: `AuthenticationError`, **401**, `code=invalid_api_key`, `type=invalid_request_error` |
| `chat.completions.create(gpt-4o, «Responde solo: OK», max_tokens=5)` | **FALLA**: el mismo **401 `invalid_api_key`** |

Un `invalid_api_key` significa que la clave está revocada o no existe. No es un problema de cupo: eso
sería un 429 `insufficient_quota`. **Si te han confirmado que «ya funciona», tiene que ser otra clave,
nueva, que no está en ninguna copia.** La …ouwA no va a volver.

**La clave de Gemini …zo1g no está en ninguna copia**: se guardó a las 04:50, después de la última.
Hoy solo existe en la fila viva de `ai_config`. La clave de entorno `GEMINI_API_KEY` es otra, …SVQY,
y también funciona.

---

## 4. Propuesta: una clave por proveedor

### 4.1 El modelo de datos

**Una tabla nueva, `ai_provider_keys`**, con una fila por proveedor:

| Columna | Qué |
|---|---|
| `provider` | `gemini` / `openai`, **único** |
| `api_key_encrypted` | Fernet, como hoy |
| `model_name` | El último modelo elegido **para ese proveedor** |
| `reasoning_effort` | Solo lo usa OpenAI |
| `updated_at`, `updated_by` | Cuándo y quién cambió esa clave |

`ai_config` se queda como está. Su `provider` pasa a significar «**el proveedor activo**», y sus
límites y contadores siguen siendo globales. `ai_config.api_key_encrypted` y `model_name` se dejan
de escribir, pero **no se borran** (D60: nada se migra a mano).

**¿Por qué una tabla nueva y no columnas nuevas?** Porque la crea `create_all`: **ningún SQL** que
aplicar en producción (regla 10). Son las mismas razones de O2c §16.4: una columna nueva en
`ai_config` rompería su lectura hasta aplicar el `ALTER`.

**El arranque sin SQL:** la primera vez que se lee, si `ai_provider_keys` no tiene fila para el
proveedor de `ai_config`, se crea copiando la clave y el modelo de `ai_config`. Es idempotente, y
así **la …zo1g no se pierde** aunque la fila diga `openai`… con un matiz: hoy esa clave está bajo
`openai`. Ver §4.4.

### 4.2 El comportamiento

- **Guardar con una clave nueva** la escribe **solo en la fila de su proveedor**. La del otro no se
  toca nunca.
- **Cambiar de proveedor** no pide clave: activa el otro y **usa su clave y su último modelo**. Si ese
  proveedor no tiene clave, la pantalla lo dice antes de guardar («OpenAI no tiene clave guardada»)
  y no deja activarlo sin una.
- **`/models/live?provider=X` usa la clave de X.** Así desaparece el caso de «le mando a Google la
  clave de OpenAI» (134 F-2), sin lógica aparte.
- **«Probar conexión»** prueba el proveedor **que hay en pantalla**, con su clave (134 F-1).
- `load_ai_config_from_db` devuelve la clave **del activo**. `/estado`, `/upload`, `script_ai` y el
  análisis de imágenes no cambian: todos leen de ahí.
- `PROVIDERS["openai"]` gana `gpt-5.5` en la lista fija (134 F-8).

### 4.3 Alcance

| Paso | Capa | Archivos | Líneas (est.) |
|---|---|---|---|
| **P1** | Backend | `db/models/ai_provider_key.py` (nuevo) + registrar el modelo donde se importan los demás | ~30 |
| **P2** | Backend | `endpoints/ai_config.py` (guardar, leer, `/models/live`, `/test`) · `schemas/ai_config.py` (`AIConfigRead` gana `proveedores: {gemini: {tiene_clave, modelo}, openai: {…}}`, **sin claves**) | ~80 |
| **P3** | Backend | `services/ai/gemini.py::load_ai_config_from_db` (la clave del activo, con el arranque de §4.1) | ~20 |
| **P4** | **Pantalla (regla 31)** | `AIConfigPage.tsx` (estado de clave por proveedor, aviso al cambiar, «Probar» con lo de pantalla, refresco tras guardar) · `services/api.ts` (tipos y cuerpo de `test`) | ~60 |

- **Total:** unos **6 archivos y ~190 líneas**. Pasa del umbral de la regla 4, así que va en **cuatro
  pasos**, uno por prompt. P1 a P3 son del backend, no interrumpen la pantalla y van con `--reload`.
  P4 solo con tu aviso previo.
- **SQL:** ninguno. **Protegidos:** ninguno. `gemini.py` no está en la lista del §11.
- **Suites:** contra el 8002 (regla 34). Las claves de prueba serán inventadas; las pruebas de «la
  clave del otro proveedor no se toca» no necesitan claves reales.

### 4.4 Cómo recuperar las dos claves sin pegarlas en ningún chat

**Antes de nada: `pg_dump`** (regla 32). La …zo1g no está en ninguna copia (§3), y es lo único que
se puede perder aquí. **No la he hecho**: el encargo era no tocar nada. Te la propongo como primer
paso, antes de cualquier guardado.

Después, dos caminos:

- **Con la propuesta aplicada (recomendado):**
  1. Al arrancar, P3 copiaría la …zo1g a la fila de **`openai`**, porque eso dice hoy `ai_config`.
     Sin más, la clave de Gemini acabaría en la fila equivocada, y para ponerla en su sitio habría
     que volver a pegarla.
  2. Para evitarlo, en ese arranque **P3 reconoce el formato**: una clave que empieza por `AQ.` o
     `AIza` y está bajo `openai` va a la fila de `gemini`. Es una regla de un solo uso, solo para el
     arranque. **Decídelo tú**: es una heurística. La alternativa es volver a poner Gemini como
     proveedor activo antes de P3 (el último punto de abajo), y entonces no hace falta ninguna
     heurística.
  3. **La clave nueva de OpenAI la cargas tú, en la pantalla de configuración de IA**, en el campo de
     clave con OpenAI seleccionado. Va cifrada a su fila y ya no pisa la de Gemini.
- **Sin esperar a la propuesta**, para volver a funcionar hoy:
  - **Con Gemini:** en la pantalla, elige Gemini y un modelo y guarda **dejando la clave en blanco**.
    Se conserva la …zo1g y `/estado` pasará a `ok:true`.
  - **Con OpenAI:** elige OpenAI, pega la clave nueva **en la pantalla** y guarda. **Esto pisa la
    …zo1g**: solo después del `pg_dump`, o si Gemini da igual (la de entorno, …SVQY, sigue viva).

**En ningún caso hace falta que la clave pase por este chat.** Ni la cargo yo ni la leo. Solo
compruebo sus cuatro últimos caracteres y si el proveedor la acepta.

---

## 5. Pendiente de tu decisión

1. ¿Se hace el `pg_dump` ya, antes de cualquier guardado?
2. ¿Se aplica la propuesta de §4 (P1 → P4)? ¿Con la heurística de §4.4.2 o sin ella?
3. ¿Qué proveedor dejas activo mientras tanto? Hoy la fila está en una combinación que no funciona
   con ningún proveedor.
4. Validación visual de la Parte A (`a8ed054`): con Gemini guardado, el panel de subida no bloquea.
