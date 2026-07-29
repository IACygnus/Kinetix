# Reporte para Fredy — Fundación 1 (Sprint 3.0): Análisis multi-fase del HAR

**Fecha:** 2026-07-28 · **Branch:** `backup-trabajo-local` · **Commit:** `31906ba`
**Push:** ✅ solo a `github` (`6b665c7..31906ba`). **`origin` (Azure/producción) NO se tocó.**

---

## 1. Estado

**Implementado, testeado y validado en vivo contra la BD real.** Falta tu
validación visual, que sigue siendo el único criterio de éxito.

Antes de escribir una línea verifiqué todo el contexto del prompt contra el
repo: HEAD, baseline de tests, modelo, shape del HAR en DB, `_call_ai`,
`MAX_CONTEXT_CHARS` y los remotes. **Todo coincidía.**

---

## 2. Qué hace ahora el sistema que antes no hacía

Antes: el HAR entraba entero al modelo y salía un JMX, con la correlación
implícita en la buena voluntad del modelo.

Ahora hay un paso previo que responde dos preguntas **por separado** y **guarda
la respuesta**:

1. **¿Qué es cada request?** → `navigation` · `xhr` · `auth` · `write` · `config`
2. **¿Qué dato viaja de un request a otro?** → tokens, CSRF, IDs de recurso,
   con el request que lo produce, el que lo consume y qué extractor de JMeter
   usarías.

**El flujo de generación vigente no cambió.** `/generate`,
`/generate-from-file` y `/refine` quedaron intactos, como pediste.

---

## 3. Cambios (8 archivos, 1506 inserciones, 0 borrados)

| Archivo | Δ |
|---|---:|
| `backend/app/services/ai/har_flow_analyzer.py` *(nuevo)* | +557 |
| `backend/tests/test_har_flow_analyzer.py` *(nuevo)* | +436 |
| `backend/tests/test_analyze_har_endpoint.py` *(nuevo)* | +297 |
| `backend/app/api/v1/endpoints/script_ai.py` | +137 |
| `backend/migrations/sql/sprint-3.0-fundacion-1-har-analysis.sql` *(nuevo)* | +47 |
| `backend/app/db/models/ai_script_design.py` | +19 |
| `frontend/src/services/api.ts` | +7 |
| `frontend/src/pages/AIScriptDesigner.tsx` | +6 |

**Ningún archivo protegido fue tocado.** Backups `.bak_fund1_20260728_185824` de
los 4 archivos modificados.

### Base de datos

3 columnas nullable en `ai_script_designs`, con `ALTER TABLE` manual (sin
Alembic) y script ADD/DROP reversible versionado en el repo:

```sql
ALTER TABLE ai_script_designs
    ADD COLUMN IF NOT EXISTS har_analysis_classification JSONB,
    ADD COLUMN IF NOT EXISTS har_analysis_dependencies   JSONB,
    ADD COLUMN IF NOT EXISTS har_analysis_status         VARCHAR(32);
```

Ya aplicado y verificado. Rollback completo (`DROP COLUMN`) documentado en el
mismo archivo. Los 9 diseños HAR existentes quedaron en `NULL`; nada previo se
entera.

---

## 4. Tests — cifras reales, contadas con pytest

| Momento | Resultado |
|---|---|
| Baseline (`6b665c7`) | **208 passed** en 35.70s |
| Después | **259 passed** en 38.46s |
| **Delta** | **+51** |

La meta del prompt era ~218. Salieron 259. Ningún test previo se modificó ni se
rompió.

- 37 tests del analyzer (shape real del HAR, umbral, filtrado de categorías en
  Fase 2, parser JSON, fallo de Fase 2 reteniendo Fase 1).
- 14 tests del endpoint (404, 400, 403, 429, 503, idempotencia, persistencia).

---

## 5. Validación en vivo — lo que realmente importa

Con `openai / gpt-4.1`, contra diseños HAR reales de la BD.

**HAR chico (10 entries)** → no gasta IA:
```
"status":"skipped","error":"HAR con 10 entries funcionales; el analisis automatico requiere al menos 20."
```

**HAR Pideky (105 entries)** → `completed`, 4 dependencias:
```
counts: navigation 5 · xhr 82 · auth 5 · write 2 · config 11
```

| src → tgt | dato | conf | extractor sugerido |
|---|---|---|---|
| 6 → 11 | `AccessToken` | high | JSON Extractor sobre `$.AuthenticationResult.AccessToken` |
| 91 → 97 | `orderPideky` | high | JSON Extractor sobre `$.orders[0].orderPideky` |
| 91 → 99 | `orderPideky` | high | ídem |
| 91 → 101 | `orderPideky` | high | ídem |

Eso es correlación real y accionable: el token de Cognito y el ID de orden que
tres requests posteriores consumen. No es un resultado de laboratorio.

**HAR Veritran (106 entries)** → `completed`, 0 dependencias. Ver punto 7.

**Idempotencia:** la segunda llamada devuelve `"reused": true` sin gastar IA.
**Errores:** `404` en UUID inexistente, `400` en un diseño Postman.

---

## 6. Adaptaciones respecto al prompt (las 4, explícitas)

1. **Tests del endpoint sin infraestructura HTTP.** El repo no tiene
   `conftest.py`, `TestClient` ni fixtures de DB async — los 208 tests son
   unitarios sobre funciones. Montar esa infra era un cambio estructural fuera
   de alcance. Los tests llaman la función del endpoint **directamente** con un
   doble de sesión de DB. Mismos asserts, cero infra nueva.

2. **Idempotencia por hash del HAR**, guardado **dentro** del JSON de
   clasificación. Sin esto, el auto-save (que dispara `upsert` en cada turno)
   habría gastado 2 llamadas al modelo por turno. Respeta el límite de 3
   columnas: no agregué una cuarta.

3. **`_call_ai` se invoca directo, sin threadpool** — es síncrono y bloquea el
   event loop, igual que en los otros 5 llamados del módulo. Cambiar esa
   convención es transversal, no de esta fundación.

4. **Reporte en `docs/`, no en `/tmp`.** Regla tuya vigente: los reportes van
   siempre al repo. Este archivo es
   `docs/reporte-para-fredy-fundacion-1.md`.

---

## 7. Un hallazgo que vale la pena que veas

El HAR de 106 entries devolvió **0 dependencias**. No es un fallo del análisis:
**solo 36 de esos 106 entries traen cuerpo de respuesta**. `compress_har()`
conserva el body únicamente cuando el mimeType es json/xml/text; en el resto, el
valor producido no está en el archivo, así que ningún modelo puede
correlacionarlo.

Traducción práctica: **la cobertura de la Fase 2 depende de la calidad de la
grabación**. Un HAR exportado sin cuerpos de respuesta acota estructuralmente lo
que se puede detectar. Sugiero que la UI lo diga en vez de dejar creer que "no
hay dependencias" — pero es decisión tuya y no la tomé por mi cuenta.

---

## 8. Pendientes

- **UI del análisis:** no existe todavía. Esta fundación produce y persiste el
  dato; el consumo es de las fases siguientes.
- **`har_analysis_*` no expuestos en `AIScriptDesignDetail`** (schema Pydantic
  intacto a propósito, diff mínimo). Se agregan cuando la UI los necesite.
- **Tope de 200 entries por llamada.** Ningún HAR de la BD se acerca (máximo
  real: 106), pero uno mayor se analizaría parcial;
  `classification.analyzed_entries` lo deja registrado.
- **Rebuild de contenedores: NO ejecutado** (regla #7, el ciclo Docker lo
  manejás vos). El backend corre con `--reload` y tomó los cambios solo; el
  frontend **no** se rebuildeó, así que el wiring del fire-and-forget necesita
  tu rebuild para verse en el navegador. El backend ya es usable por API.

---

## 9. Cómo probarlo vos

```bash
# Reporte técnico completo (incluye el SQL ADD/DROP)
docs/reports/repo/sprint-3.0-fundacion-1-analisis-har.md

# Forzar un re-análisis de un diseño HAR
POST /api/v1/script-designer/ai/designs/{design_id}/analyze-har?force=true
```

```sql
SELECT id, har_analysis_status,
       har_analysis_classification->'counts' AS counts,
       jsonb_array_length(har_analysis_dependencies->'dependencies') AS deps
  FROM ai_script_designs
 WHERE har_analysis_status IS NOT NULL;
```
