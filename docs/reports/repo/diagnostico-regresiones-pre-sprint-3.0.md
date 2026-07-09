# Diagnóstico Forense — 3 Regresiones Pre-Sprint 3.0

## Contexto
Detectado durante validación manual de Fredy en Bloques 2-4 del checklist post-HF18b.
Estado del sistema: branch `backup-trabajo-local`, HF18b aplicado, tag
`pre-sprint-3.0-20260708_190944` en 2 remotes.

**Aclaración importante:** NO son regresiones contra una versión estable publicada.
Son bugs latentes en código WIP nunca terminado del AI Editor. AIScriptEditor.tsx
no está en CLAUDE.md — es código introducido en commits 2740786 y b20c6e3 que
nunca se mergearon a main.

---

## Regresión 1: CSV no se genera automáticamente

### Síntoma
- Prompt del usuario pedía CSV con firstname/lastname
- JMX generado tiene CSVDataSet con filename apuntando a variable sin definir
- No se genera archivo .csv físico
- Smoke test falla con "CSV sin archivo físico"

### Evidencia
- DB query confirmó el JMX generado tiene filename como variable sin resolver
  (`filename = ${csv_booking_data}` en el diseño `4a4fd1e8`, updated 2026-07-09 01:03)
- Grep completo en backend/app/ = 0 coincidencias para `sample_csv|create_sample|
  generate_csv|write_csv|auto_generate_csv`
- SYSTEM_PROMPT (script_ai.py:197) no instruye crear datos de ejemplo ni escribir archivo

### Causa raíz
Falta etapa post-generación que:
(a) Escriba un .csv de ejemplo con las columnas pedidas
(b) Reescriba el filename del CSVDataSet a ese path real

**NO EXISTIÓ NUNCA — no se rompió, faltó implementar.**

### Archivos relevantes
- `backend/app/api/v1/endpoints/script_ai.py:197` (SYSTEM_PROMPT)
- Ausencia total de módulo de generación en `backend/`

### Commit origen
`2740786` (código WIP inicial del AI Editor)

---

## Regresión 2: "unmapped" placeholder en listeners

### Síntoma
View Results Tree y Summary Report aparecen con:
- Triángulo amarillo de advertencia en el árbol
- Mensaje al seleccionar: "Edición disponible próximamente. Tipo: unmapped.
  Esta funcionalidad se habilita en sub-sprints posteriores (2.4c-e)"

### Causa raíz (DOS defectos independientes)

**B1 — Parser no reconoce listeners anidados en Thread Group**

La IA genera JMX con los listeners DENTRO del hashTree del Thread Group:
```xml
<ThreadGroup testname="Thread Group - Booking E2E">
  <hashTree>
    <ResultCollector ... testname="View Results Tree">
    <ResultCollector ... testname="Summary Report">
  </hashTree>
</ThreadGroup>
```

El mapeo `ResultCollector → listeners[]` solo existe en el dispatch TOP-LEVEL
(`jmx_to_structure.py:878`). El parser de hijos del Thread Group
`_parse_tg_children` (líneas 686-695) NO tiene rama para `ResultCollector` →
cae al `else` → `UnsupportedElement` → `unmapped[]`.

**B2 — No hay editor de listener aunque estuvieran bien mapeados**

Grep confirma: no existe `selected.kind === 'listener'` en el panel de detalle
(`frontend/src/` completo). Un listener top-level correctamente parseado también
caería al mismo placeholder (mostrando "Tipo: listener").

Comentario en `AIScriptEditor.tsx:2568-2571` dice explícitamente:
"Los renderers reales por kind vienen en 2.6c-g".

### Archivos relevantes
- `backend/app/services/engine/jmx_to_structure.py:686-695` (parser de hijos TG)
- `backend/app/services/engine/jmx_to_structure.py:878` (dispatch top-level)
- `backend/app/services/engine/jmx_to_structure.py:705` (_LISTENER_KIND_MAP)
- `frontend/src/pages/AIScriptEditor.tsx:1905` (ícono ⚠️)
- `frontend/src/pages/AIScriptEditor.tsx:2550-2563` (placeholder)

### Commit origen
`2740786`

---

## Regresión 3: Listeners agregados manualmente desaparecen

### Síntoma
- Fredy agrega listeners manualmente en el árbol
- Sidebar muestra "Listeners (2)"
- Después de otra acción (subir CSV, remontar componente), sidebar muestra "Listeners (0)"

### Causa raíz
Bug de state React — auto-save no se dispara para el path de "agregar/eliminar/toggle listener".

- `handleAddElement` (línea 702-714): usa `setStructure(next)` directo
- `handleDeleteElement` (línea 770): igual
- `handleToggleEnabled` (línea 837): igual

El único camino que persiste es `updateStructure` (línea 369-380) que marca
`isDirtyRef.current = true` y agenda el debounce de auto-save
(persistJmx → regenera JMX → upsert a DB).

`updateStructure` está cableado SOLO al panel de edición de samplers
(`onUpdateStructure={updateStructure}`, línea 1284).

**Consecuencia:** los listeners agregados viven solo en memoria React. Cualquier
`reloadStructure()` — que se dispara tras autocrear un CSV al subir un Data File
(línea 246-256) o al remontar el componente — vuelve a hacer `getById` del
`current_jmx` en DB (que nunca recibió los listeners) → `parseJmx` → Listeners (0).

### Archivos relevantes
- `frontend/src/pages/AIScriptEditor.tsx:702-714` (handleAddElement)
- `frontend/src/pages/AIScriptEditor.tsx:770` (handleDeleteElement)
- `frontend/src/pages/AIScriptEditor.tsx:837` (handleToggleEnabled)
- `frontend/src/pages/AIScriptEditor.tsx:369-380` (updateStructure — donde SÍ persiste)

### Commit origen
`b20c6e3`

---

## Acoplamiento entre Regresiones 2 y 3

Regresiones 2 y 3 están acopladas. Aunque se arregle #3 (persistir los listeners
agregados manualmente), estos se serializan top-level
(`structure_to_jmx.py:780-782`) y se re-parsearían como `listeners[]` correctamente
— pero los que la IA genera anidados en el TG seguirían cayendo en unmapped (#2).

Son fixes ortogonales pero deben resolverse ambos para tener listeners funcionales
en todos los flujos (IA-generado + agregado manual).

---

## Recomendación de resolución

Sugerencia de orden (subject to Fredy's decision):

1. **HF20a** — Parser reconoce ResultCollector anidado en Thread Group
   (`jmx_to_structure.py`) — desbloquea el rendering correcto del árbol
2. **HF20b** — updateStructure en handleAddElement/Delete/Toggle
   (`AIScriptEditor.tsx`) — persistencia de listeners agregados manualmente
3. **HF20c** — CSV auto-generation post-IA (backend + frontend hook)
   — requiere decidir si generar CSV con datos reales/dummy o pedir al usuario

Los 3 son atómicos y pueden aplicarse en cualquier orden. Ninguno bloquea al otro
técnicamente, aunque HF20a + HF20b juntos resuelven el flujo completo de listeners.

---

## Confirmación read-only

Nada del código del aplicativo fue modificado. Solo lecturas (Read, Grep, Glob),
`git log -S` (solo lectura), `docker ps`, y consultas SELECT contra `jmeter_postgres`.
