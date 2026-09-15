# Reporte para Fredy — Fundación 2 (Sprint 3.0): Generación por chunks

**Fecha:** 2026-07-28 · **Branch:** `backup-trabajo-local`
**Commit:** `81d2cc7` · **Push:** ✅ solo a `github` (`04042a9..81d2cc7`). **`origin` (Azure/producción) NO se tocó.**

---

## 1. Estado

**Implementado, testeado (349 PASS) y validado en vivo de punta a punta.**

La generación por chunks llegó a **`completed` 7/7 con 90 samplers y XML
válido** sobre el HAR de Pideky. Para llegar ahí hicieron falta 4 corridas
reales y dos mejoras que salieron de mirar los fallos, no de adivinar. La
sección 5 cuenta esa historia — vale la pena leerla, porque los dos fallos
enseñan más que el éxito.

Verifiqué todo el contexto contra el repo antes de escribir código: HEAD
descendiente de `31906ba`, baseline 259, shapes de F1, `current_jmx`,
`_call_ai`. Todo coincidía.

Verifiqué todo el contexto contra el repo antes de escribir código: HEAD
descendiente de `31906ba`, baseline 259, shapes de F1, `current_jmx`,
`_call_ai`. Todo coincidía.

**Un dato con el que no me quedo cómodo:** de los 6 bloques de transacciones,
uno (el chunk 4) no se pudo generar nunca porque sus 15 requests no entran en
los 32K tokens de salida del modelo. El JMX final tiene 90 de los 105
samplers. Está explicado en la sección 6 y la solución concreta en la 7.

---

## 2. Qué resuelve

La F1 dejó el HAR clasificado y con sus dependencias. Lo que seguía sin
resolverse es el techo físico: **un HAR de 100+ requests no entra en una sola
respuesta del modelo.** El síntoma ya lo veníamos parcheando desde HF18a con
`_detect_truncation`, y el mensaje que le mostrábamos al usuario ("reducí el
HAR", "pedí solo las transacciones críticas") era una rendición.

Ahora el problema cambia de forma: en vez de **una respuesta gigante que puede
truncarse**, son **N respuestas chicas que se ensamblan**.

Backward compat total: HAR chico o sin análisis → flujo de siempre.
`/generate`, `/generate-from-file` y `/refine` no se tocaron.

---

## 3. Cambios (8 archivos, 2452 inserciones, 1 borrado)

| Archivo | Δ |
|---|---:|
| `backend/tests/test_chunked_generation_endpoint.py` *(nuevo)* | +514 |
| `backend/app/services/ai/har_chunk_router.py` *(nuevo)* | +492 |
| `backend/app/api/v1/endpoints/script_ai.py` | +398 |
| `backend/tests/test_har_chunk_router.py` *(nuevo)* | +378 |
| `backend/tests/test_jmx_chunk_assembler.py` *(nuevo)* | +328 |
| `backend/app/services/ai/jmx_chunk_assembler.py` *(nuevo)* | +274 |
| `backend/migrations/sql/sprint-3.0-fundacion-2-chunking.sql` *(nuevo)* | +48 |
| `backend/app/db/models/ai_script_design.py` | +21 −1 |

Sin cambios en frontend. Ningún archivo protegido tocado. Backups
`.bak_fund2_20260728_201807` de los 2 archivos modificados.

**Base de datos:** 4 columnas nullable en `ai_script_designs`
(`generation_mode`, `chunks_plan`, `chunks_completed_count`,
`generation_status`), ALTER TABLE manual ya aplicado, DROP documentado en el
mismo script.

---

## 4. Tests — cifras reales contadas con pytest

| Momento | Resultado |
|---|---|
| Baseline (`04042a9`) | **259 passed** / 19.38s |
| Después | **349 passed** / 17.36s |
| **Delta** | **+90** |

33 del router · 33 del ensamblador · 24 de la orquestación. Ningún test previo
modificado ni roto.

**Los tests encontraron un bug real antes de gastar un peso en IA:**
`script_ai.py` ya tenía un endpoint llamado `validate_jmx` (`POST /validate`)
que ensombrecía mi import del ensamblador. El símbolo resolvía a la corrutina
del endpoint y todos los chunks habrían fallado siempre. Se importa aliasado.

---

## 5. Validación en vivo con Pideky — el resultado honesto

Diseño `97ccb36f-…`, 105 entries, análisis F1 `completed`.
_(Antes de correr guardé el JMX previo en `%TEMP%\pideky_jmx_pre_f2.xml`.)_

### Plan generado: 7 chunks

| Chunk | Contenido | Entries |
|---|---|---:|
| 1 | Esqueleto + auth + navigation + config | 21 |
| 2-6 | Transacciones | 15 c/u |
| 7 | Transacciones | 9 |

### Primera corrida: 412s → `partial`, 3/7

| Chunk | Resultado |
|---|---|
| 1 | ✅ 21 samplers, JMX completo y válido |
| 2 | ✅ +15 samplers (30 elementos insertados) |
| 3 | ✅ +15 samplers |
| 4 | ❌ **XML mal formado** |
| 5-7 | ⏸ pending (cortó al primer fallo, como acordamos) |

**Causa raíz, sacada de los logs:** la llamada del chunk 4 volvió con
`finish_reason=length`. El modelo agotó sus 32K tokens de salida y cortó el XML
a mitad. Esos 15 entries son requests a S3 con URLs y bodies largos: pesan
mucho más que los de los bloques 2 y 3.

**Lo importante: el JMX no se corrompió.** Después del fallo quedó en 51
samplers, XML válido, raíz `jmeterTestPlan`, con los prefijos `[C2]`/`[C3]`
correctos y 9 JSON Extractors. Verificado con el propio `validate_jmx` del
ensamblador. El invariante que más me importaba se cumplió en producción, no
solo en tests.

### Mejora que agregué al ver esto

El `failure_reason` decía `"mismatched tag: line 259, column 50"` — cierto pero
inútil: escondía la causa real. Ahora, cuando el proveedor reporta
`finish_reason=length`, el motivo lo dice explícito y **te avisa que
reintentar tal cual no va a servir**. Dos tests nuevos cubren esto.

### Segunda corrida (retry): 301s → `partial`, 3/7

El retry hizo exactamente lo suyo: `1 failed→pending`, recalculó el contador,
reanudó desde el 4 sin re-generar los 3 completados… y el chunk 4 **volvió a
truncarse**, tal como el mensaje nuevo predecía.

### Tercera corrida: diagnóstico — saltear el 4 para probar 5-7

Marqué el chunk 4 como `completed` **a mano por SQL** para que el flujo llegara
a los bloques siguientes. El chunk 5 falló, pero con **otro** error:
`not well-formed (invalid token): line 51, column 64`, y **sin**
`finish_reason=length`. O sea: el modelo terminó bien y aun así emitió XML
inválido.

Hipótesis: un `&` crudo dentro de una URL con query string
(`?page=1&size=20`), que en XML tiene que ser `&amp;`. Es de los errores más
comunes que comete un modelo generando XML.

### Segunda mejora que agregué

`escape_bare_ampersands()`: escapa solo los `&` que no abren una entidad
válida (`&amp;`, `&#38;`, `&#x26;` quedan intactos). No repara nada más — un
fragmento realmente roto sigue fallando, y hay un test que lo verifica.

### Cuarta corrida (retry con el saneo): 209s → ✅ **`completed`, 7/7**

Hipótesis confirmada: el chunk 5 se ensambló sin tocar nada más, y los bloques
6 y 7 pasaron limpio.

```json
{"generation_status":"completed","total_chunks":7,"chunks_completed":7,
 "samplers_total":90,"error":null}
```

---

## 6. El JMX que quedó

| Métrica | Valor |
|---|---|
| `validate_jmx` | **`(True, 'ok')`** |
| Raíz | `jmeterTestPlan` |
| Tamaño | 205.388 bytes |
| **`HTTPSamplerProxy`** | **90** |
| Distribución | 21 sin prefijo (esqueleto) + `[C2]`15 + `[C3]`15 + `[C5]`15 + `[C6]`15 + `[C7]`9 |
| `JSONPostProcessor` (extractores) | 18 |
| `HeaderManager` | 203 |
| `ResponseAssertion` | 270 |

90 = 105 − 15: exactamente los 15 entries del chunk 4 que nunca se generó. La
distribución por prefijo coincide bloque a bloque con el plan.

### Estado que dejé en la BD — honesto

El chunk 4 **nunca se generó**; el `completed` era mío, del diagnóstico. Lo
restauré a su estado real:

```
 chunk |  estado   | entries | motivo
-------+-----------+---------+---------------------------------------
 1     | completed |      21 | -
 2     | completed |      15 | -
 3     | completed |      15 | -
 4     | failed    |      15 | ...finish_reason=length...
 5     | completed |      15 | -
 6     | completed |      15 | -
 7     | completed |       9 | -

 generation_mode | chunks_completed_count | generation_status | jmx_len
 chunked         |                      6 | partial           |  205387
```

Si querés el JMX completo (105 samplers), corré `retry-failed-chunks` con un
modelo de mayor salida — o esperá el auto-split de la sección 7.

---

## 7. Lo que esto te dice del producto

1. **El pipeline funciona de punta a punta.** Esqueleto, ensamblado
   incremental, prefijos `[Cn]`, extractores derivados de las dependencias de
   la F1, persistencia por bloque, corte al fallo y retry reanudable: todo se
   comportó como se especificó, con datos reales.
2. **El invariante crítico se cumplió en producción, no solo en tests.** Hubo
   3 fallos reales y en los 3 el JMX previo quedó intacto y válido. Nunca
   apareció un JMX corrupto en la base.
3. **`_CHUNK_SIZE = 15` no es universal.** Sirve para bloques normales, se
   queda corto cuando los requests son pesados (URLs y bodies largos). Es un
   número fijo enfrentando un problema variable.
4. **La recomendación concreta** (no la implementé porque cambia el contrato de
   "cortar al primer fallo" que definiste vos — es tu decisión): cuando un
   chunk falla con `finish_reason=length`, **partirlo en dos y reintentar
   automáticamente** en vez de cortar. El `chunks_plan` persistido ya soporta
   ese modelo: es insertar dos chunks donde había uno y seguir. Con eso, un HAR
   como Pideky llegaría a 105/105 sin intervención.
5. **Dos de las mejoras de esta fundación no habrían existido sin correr el
   sistema de verdad.** Los tests estaban todos verdes con 342 y el feature
   igual fallaba la mitad de los bloques. El mensaje de error honesto y el
   escapado de `&` salieron de mirar logs reales.

---

## 8. Adaptaciones respecto al prompt

1. **`validate_jmx` importado con alias** (`validate_assembled_jmx`) por la
   colisión con el endpoint existente. Bug real, detectado por los tests.
2. **`get_dependencies_for_chunk` devuelve 3 claves, no 2.** Además de
   `produces`/`consumes` agregué `internal` (ambos extremos en el mismo
   bloque), porque el prompt del modelo lo trata distinto. `internal ⊆
   produces`.
3. **Tests de endpoint sin infraestructura HTTP**, mismo criterio que la F1:
   se invocan las funciones directamente con un doble de sesión de DB.
4. **`_plan_copy()` en cada persistencia.** SQLAlchemy marca una columna JSONB
   como sucia solo si se le **asigna** un objeto nuevo; mutar la lista en su
   lugar no habría persistido nada.
5. **Dos mejoras que no estaban en el prompt**, ambas nacidas de la corrida
   real: el `failure_reason` enriquecido con `finish_reason=length`, y el
   escapado de `&` sin escapar. Sin la segunda, la validación se habría quedado
   en `partial` por una comilla XML, no por un problema de diseño.

---

## 9. Cómo probarlo vos, paso a paso

```bash
# 0) Login (guarda cookies + CSRF)
curl -s -c cookies.txt -X POST http://localhost:8001/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=sqa2024"

# CSRF = valor de la cookie csrf_token en cookies.txt
```

```bash
# 1) Análisis F1 (idempotente: si ya corrió, devuelve reused=true sin gastar IA)
curl -s -b cookies.txt -X POST \
  "http://localhost:8001/api/v1/script-designer/ai/designs/<DESIGN_ID>/analyze-har" \
  -H "X-CSRF-Token: <CSRF>"

# 2) Generación por chunks (tarda: 1 llamada al modelo por bloque)
curl -s -b cookies.txt -X POST \
  "http://localhost:8001/api/v1/script-designer/ai/designs/<DESIGN_ID>/generate-chunked" \
  -H "X-CSRF-Token: <CSRF>"

# 3) Si quedó partial, reintentar los bloques fallidos
curl -s -b cookies.txt -X POST \
  "http://localhost:8001/api/v1/script-designer/ai/designs/<DESIGN_ID>/retry-failed-chunks" \
  -H "X-CSRF-Token: <CSRF>"
```

```sql
-- 4) Estado
SELECT generation_mode, chunks_completed_count, generation_status,
       jsonb_array_length(chunks_plan) AS total_chunks,
       length(current_jmx) AS jmx_len
  FROM ai_script_designs WHERE id = '<DESIGN_ID>';

-- 5) Detalle por bloque
SELECT c->>'chunk_id' AS chunk, c->>'status' AS estado,
       jsonb_array_length(c->'entry_idxs') AS entries,
       left(c->>'failure_reason', 90) AS motivo
  FROM ai_script_designs x, jsonb_array_elements(x.chunks_plan) c
 WHERE x.id = '<DESIGN_ID>' ORDER BY 1;
```

```bash
# 6) Verificar el JMX resultante
psql ... -t -A -c "SELECT current_jmx FROM ai_script_designs WHERE id='<DESIGN_ID>'" > out.jmx
grep -c "<HTTPSamplerProxy" out.jmx
python -c "import xml.etree.ElementTree as ET; ET.parse('out.jmx'); print('XML valido')"
```

---

## 10. Commit y pendientes

**Commit:** `81d2cc7` — *"Sprint 3.0 F2: generacion de JMX por chunks con
ensamblado incremental"*
**Push:** ✅ `github/backup-trabajo-local` (`04042a9..81d2cc7`).
**`origin` (Azure DevOps / producción): NO se tocó.**

Reporte técnico completo: `docs/reports/repo/sprint-3.0-fundacion-2-chunking.md`
(incluye el SQL ADD/DROP y el contrato de los dos endpoints).

**Pendientes:**

- **Sin UI.** Los dos endpoints van por curl; el botón de reintento es de un
  sprint futuro, como acordamos.
- **`chunks_plan` y `generation_*` no se exponen en `AIScriptDesignDetail`**
  (schema Pydantic intacto a propósito). Se agregan cuando la UI los pida.
- **Ejecución síncrona:** la request HTTP queda abierta toda la generación (412s
  en Pideky). Para HARs grandes conviene tarea en background con polling; el
  `chunks_plan` persistido ya soporta ese modelo.
- **`generate-chunked` sobrescribe `current_jmx`** cuando el esqueleto sale
  bien. Es lo buscado, pero la UI debería avisarlo antes de disparar.
- **Auto-split en truncación** — la recomendación de la sección 7.
- **Rebuild de contenedores: NO ejecutado** (regla #7). El backend corre con
  `--reload` y tomó los cambios solo.
