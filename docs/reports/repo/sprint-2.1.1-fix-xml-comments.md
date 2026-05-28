# Sprint 2.1.1 — Hotfix: Comments XML en parser

**Fecha:** 2026-05-25
**Estado:** ✅ Completado — 27/27 tests passing, bloqueador eliminado
**Tipo:** Hotfix bloqueante (detectado por Sprint 2.2 Test 5)

## Bug

El parser revienta con `TypeError: argument of type 'NoneType' is not iterable` al procesar JMX con comentarios XML.

**Root cause:**
- lxml representa `<!-- ... -->` como Comment con `tag = <cyfunction Comment>` (no string).
- `_walk_hashtree_children` iteraba los hijos del hashTree sin filtrar nodos non-Element.
- `comment.get("testclass", "")` retorna **`None`** (ignora el default vacío) porque los Comments no son Elements.
- El parser hace luego `"HTTPSampler" in testclass` → `"HTTPSampler" in None` → TypeError.

**Caso de uso afectado:** TODOS los JMX generados por la AI Script Designer suelen incluir `<!-- ... -->` para anotar secciones. Esto rompía el endpoint `POST /script-designer/ai/parse-jmx` con HTTP 500.

## Fix aplicado

Una línea funcional + docstring en `_walk_hashtree_children` (`backend/app/services/engine/jmx_to_structure.py`):

```python
# Filtrar nodos non-Element (Comments, Processing Instructions, etc.)
# lxml: Comments tienen elem.tag = <cyfunction Comment>, no string.
children = [c for c in hash_tree_elem if isinstance(c.tag, str)]
```

reemplaza el anterior `children = list(hash_tree_elem)`. Cero cambios en la lógica restante.

## Archivos modificados

| Archivo | Diff |
|---|---|
| `backend/app/services/engine/jmx_to_structure.py` | 779 → 785 (+6: 1 funcional + 5 docstring) |
| `backend/tests/test_jmx_parser.py` | 315 → 403 (+88: 2 tests nuevos con fixtures inline) |

Backup creado: `backend/app/services/engine/jmx_to_structure.py.bak_sprint2_1_1_20260525_104844`

## Tests

**27 / 27 PASS en 1.27s**

- ✅ 25 originales del Sprint 2.1 — **sin regresión**.
- ✅ 2 nuevos del Sprint 2.1.1:
  - `test_jmx_con_comentarios_xml_no_lanza_excepcion`: JMX con comentarios anidados (top-level y dentro del TG) parsea OK, mantiene conteos correctos.
  - `test_jmx_solo_con_comentarios_no_crashea`: edge case donde el hashTree contiene solo `<!-- -->` (0 TGs detectados, 0 unmapped — los comentarios se ignoran silenciosamente, no van a unmapped).

## Validación end-to-end (Sprint 2.2 Test 5 reproducido)

JMX REAL extraído de `ai_script_designs.current_jmx` (23 351 chars, 1 comentario XML interno):

**Antes del fix:** HTTP 500 — `argument of type 'NoneType' is not iterable`.

**Después del fix:** HTTP 200 — estructura parseada correctamente:

```
test_plan.name: Pruebas de Carga - Servicio de Reservas
thread_groups: 1
  - Escenario de Carga - 20 Hilos (kind=standard, enabled=True): 5 samplers, 0 controllers
samplers totales: 5
csv_data_sets: 0
user_defined_variables: 0
listeners: 0
unmapped: 0
metadata.referenced: ['bookingid', 'firstname', 'host', 'lastname', 'port', 'scheme', 'token', 'totalprice']
metadata.undefined: ['firstname', 'host', 'lastname', 'port', 'scheme', 'totalprice']
metadata.unmapped_count: 6
```

**Hallazgo bonus:** el `metadata.undefined` confirma el bug pendiente del SYSTEM_PROMPT IA — la IA referencia 8 variables (`${host}`, `${port}`, `${scheme}`, `${firstname}`, `${lastname}`, `${totalprice}`, etc.) pero no crea UDVs/CSVs para 6 de ellas. Esto NO es un bug del parser; es exactamente el caso de uso UX que la metadata fue diseñada para flagear. Anotado en backlog general.

## Pendientes derivados

- **Sprint 2.3 desbloqueado:** regenerador `AIScriptStructure → JMX` + round-trip.
- **Backlog (no de este sprint):** fix del SYSTEM_PROMPT en `script_ai.py` para que la IA genere UDVs/CSVs cuando referencia variables.

## Estado para Sprint 2.3

**LISTO.** Bloqueador del Sprint 2.2 eliminado. El endpoint `POST /script-designer/ai/parse-jmx` ahora funciona para el caso de uso principal (AI genera JMX → parse a structure editable).
