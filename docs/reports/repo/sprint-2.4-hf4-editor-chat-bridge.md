# Sprint 2.4-HF4 — Puente Editor IA ↔ Chat

**Fecha:** 2026-05-26
**Estado:** ✅ tsc EXIT=0

## Objetivo

Botón "Pedir a IA" en el header del Editor IA que abre el chat (`/ai-script-designer?designId=…`) con el JMX actual cargado y el textarea pre-poblado para escribir el ajuste deseado.

## Cambios

### Frontend

| Archivo | Diff |
|---|---|
| `frontend/src/pages/AIScriptEditor.tsx` | 3857 → 3870 (+13: import `Sparkles` + botón en header) |
| `frontend/src/pages/AIScriptDesigner.tsx` | 1136 → 1147 (+11: lectura `fromEditor` + setInput + banner) |

Backups con sufijo `.bak_hf4_20260526_191905`.

### Cambios funcionales

**Editor IA (`AIScriptEditor.tsx`):**
- Nuevo botón **"Pedir a IA"** en el header, junto a "Ver XML raw" y los indicadores de auto-save.
- Estilo indigo (consistente con el branding del Editor IA): fondo `indigo-50`, borde `indigo-200`, icono `Sparkles`, hover `indigo-100`.
- Deshabilitado si no hay `designId` (defensa contra clicks prematuros).
- Click navega a `/ai-script-designer?designId={id}&fromEditor=true`.

**Chat (`AIScriptDesigner.tsx`):**
- Lee `fromEditor` del query string (`searchParams.get('fromEditor') === 'true'`).
- Cuando hidrata el diseño y `fromEditor === true`, pre-pobla el textarea con: `"Vengo del Editor IA. Quiero que ajustes lo siguiente del JMX: "` — el usuario continúa escribiendo donde está el cursor.
- Banner informativo en azul indigo arriba del área de mensajes: **"Desde Editor IA: el chat ya tiene cargado el JMX actual. Describe qué ajuste necesitas."** Visible solo cuando `fromEditor=true`.

### Cómo funciona end-to-end

1. Usuario está en el Editor IA → hace clic en el botón **"Pedir a IA"** del header.
2. Navega a `/ai-script-designer?designId=…&fromEditor=true`.
3. El chat hidrata desde la DB (mismo flujo que ya existía con `?designId=…`):
   - Restaura `current_jmx` → la columna derecha muestra el JMX actual con validación.
   - Restaura `conversation` → los mensajes previos del chat siguen ahí.
4. **Nuevo**: por el flag `fromEditor`:
   - Aparece el banner azul "Desde Editor IA…".
   - El textarea ya tiene el prefijo escrito, el usuario completa: "...la URL del primer sampler para que use ${host} en lugar de hardcoded" + Enter.
5. La IA refina el JMX → al volver al Editor IA (botón ← o desde sidebar), el nuevo JMX está disponible.

## Adaptaciones del prompt original

1. **State del textarea se llama `input` (no `currentInput`).** El prompt asumía `setCurrentInput`; el código real usa `setInput`. Adapté.
2. **El pre-poblado va en el useEffect de hidratación**, justo antes del `catch`, garantizando que `fromEditor` activa setInput SOLO cuando la carga fue exitosa. Si la carga falla, el banner no aparece y el textarea queda vacío — consistente con el estado de error.
3. **Banner colocado dentro del scroll area del chat** (`overflow-y-auto`) en lugar de fixed top — es la primera cosa que ve el usuario al cargar y desaparece naturalmente al hacer scroll en conversaciones largas.
4. **Botón "Pedir a IA" colocado ANTES de "Ver XML raw"** en el header, no después — orden lógico: la acción primaria (ir a IA) primero, las herramientas (XML raw) después.

## Validaciones

- ✅ `npx tsc --noEmit` → EXIT=0, sin warnings.
- ✅ Sin tocar backend.
- ⏳ Validación visual pendiente Fredy.

## Cómo validar visualmente

1. Abrir Editor IA con un diseño con JMX (`/ai-script-designer/editor/{id}`).
2. En el header, junto a "Ver XML raw", debe aparecer el botón **"Pedir a IA"** (con icono ✨ indigo).
3. Click → navega a `/ai-script-designer?designId={id}&fromEditor=true`.
4. Verificar:
   - Banner azul **"Desde Editor IA…"** visible arriba del chat.
   - Conversación previa cargada (si la hay).
   - JMX actual mostrado en la columna derecha.
   - Textarea pre-poblado con `"Vengo del Editor IA. Quiero que ajustes lo siguiente del JMX: "`.
5. Continuar el texto, enviar, la IA debe refinar el JMX existente.
6. Botón ← del Editor IA debe volver al workspace `/ai-script-editor` (mantiene el comportamiento del HF1).

## Pendientes derivados

- **Sprint 2.4 completo** — todos los HF cerrados (HF1, HF2, HF3, HF4).
- **Backlog**: si el chat necesita más contexto del estado de edición (ej. "estoy editando el sampler X y quiero cambiar Y"), podría pasarse via query param adicional (`&context=sampler:abc123`). Por ahora el prefijo genérico cubre el caso de uso típico.

## Estado

**SPRINT 2.4 + HF1-4 COMPLETOS.** El Editor IA tiene ahora:
- ✅ Estructura base + árbol read-only (2.4a)
- ✅ Infraestructura + auto-save + Thread Group (2.4b)
- ✅ HTTP Sampler (2.4c)
- ✅ Children del Sampler (2.4d)
- ✅ Config global + sidebar + lista (2.4e)
- ✅ Bugs Stepping + body raw + unsupported (HF1)
- ✅ Data Files (HF2)
- ✅ Function Helper + límite 5 MB (HF3)
- ✅ Puente Editor ↔ Chat (HF4)

Más el Sprint 2.7 que actualizó el SYSTEM_PROMPT IA para generar JMX bien formado.

Listo para validación visual final y producción.
