# Sprint 3.0.c.1 — Reporte para Fredy

## Estado
**NO IMPLEMENTADO — BLOQUEADO EN DECISIÓN.**

Sprint 3.0.c.1 NO se ejecutó. No hay migración, ni módulo, ni tests, ni commit.
El reporte del prompt asumía un cierre exitoso (SUCCESS, "236 → 248 PASS", commit
hash), pero eso no ocurrió. Este documento refleja el estado real.

## Por qué no se implementó
Los prompts de Sprint 3.0 (3.0.a → 3.0.b → 3.0.c.1) se encadenan asumiendo que
el sub-sprint anterior aterrizó. Verificado contra el repo real: **ninguno de los
tres se aplicó**. 3.0.c.1 depende de infraestructura que no existe, así que
correrlo produciría código roto + un reporte falso.

Premisas del prompt vs realidad verificada:
- **Alembic**: el prompt pide `alembic upgrade head`. El proyecto NO tiene Alembic;
  usa `Base.metadata.create_all` + `ALTER TABLE` manual (regla #10 de CLAUDE.md).
- **Columnas de 3.0.b** (`har_analysis_classification`, `har_analysis_dependencies`,
  `har_analysis_status`): NO existen. `ai_script_designs` solo tiene
  `reference_file_name`, `reference_file_content`, `reference_file_type`.
- **Columna de 3.0.a** (`har_compressed_input`): NO existe. El HAR comprimido vive
  hoy en `reference_file_content` (con `reference_file_type='har'`).
- **Módulo `har_flow_analyzer.py` (3.0.b)**: NO existe.
- **Integración en `/generate-from-file`**: el prompt usa `design` + `session.commit()`,
  pero ese endpoint es STATELESS (devuelve la respuesta y el frontend persiste vía
  `/designs/upsert`). No hay `design` ni `session` ahí.
- **`_call_ai`** (script_ai.py:1626) es SÍNCRONO y devuelve `(text, finish_reason)`.
  El código del prompt hace `await _call_ai(...)`, que fallaría en runtime.
- **Forma real del HAR comprimido** (`compress_har()`):
  `{"log": {"entries": [ {request:{method,url,headers,postData?}, response:{status,statusText,content?}} ]}}`.
  El prompt asume `{"entries": [...]}` — accederlo así daría 0 entries siempre.

## Cambios aplicados
NINGUNO. El repo sigue en el commit de housekeeping `30a0807`
(branch `backup-trabajo-local`, solo en remote `github`).

## Tests
- Antes: **208 PASS** (el "236" del prompt no corresponde al repo real).
- Después: 208 PASS (sin cambios — no se agregó ni tocó nada).

## Descubrimientos importantes
1. Sprints 3.0.a, 3.0.b y 3.0.c.1 están redactados pero NO implementados.
2. El proyecto no usa Alembic (regla #10). Cualquier columna nueva = `ALTER TABLE`
   manual reversible.
3. La lógica pura de estos módulos (router de chunking, analyzer) SÍ es construible
   de forma decoplada y testeable sin DB, corrigiendo la forma del HAR (`log.entries`)
   y usando `_call_ai` de forma síncrona.
4. La persistencia + integración es el verdadero cuello de botella y necesita una
   decisión de arquitectura (endpoint design-aware vs hook en upsert), no más
   prompts encadenados.

## Git
- Commit hash: NINGUNO (no se creó commit para 3.0.c.1).
- Push a github: N/A.
- origin (Azure): NO tocado.

## Pendientes / decisión requerida
Se ofreció a Fredy elegir una vía para desatascar:
1. **Fundación de una sola vez** (recomendado): un `ALTER TABLE` manual con todas
   las columnas necesarias + módulos puros testeados + una integración design-aware
   limpia (endpoint dedicado, no el `/generate-from-file` stateless). Plan
   línea-por-línea para aprobación previa.
2. **Solo `har_chunk_router.py` + tests unitarios ahora**: lógica pura decoplada,
   verde hoy, sin DB. Building-block probado; persistencia/integración diferida.
3. **Documento de arquitectura del Sprint 3.0 completo** antes de escribir código.

## Siguiente paso
Esperando decisión de Fredy (vía 1, 2 o 3). Una vez elegida, se implementa sobre
la base real del repo (sin Alembic, columnas por ALTER manual, integración
design-aware) y el reporte reflejará números y arquitectura verdaderos.
