# 016 — R1: autoguardado con indicador en el reporte individual

**Fecha:** 2026-08-14
**Estado:** ✅ Implementado. `tsc --noEmit` **exit 0**. **Pendiente: validación visual de Fredy** (criterio único de éxito).
**Alcance:** **1 archivo** — `Dashboard.tsx` (PROTEGIDO, autorización acotada a R1). **+98 / −10** (el archivo **crece 88 líneas**).
**Numeración:** primer reporte con la norma nueva. Había 15 archivos en `docs/reporte_bug/` → este es el **016**.

> **Sobre el presupuesto (~60-90, tope 100):** el archivo crece **88 líneas netas** —dentro de la banda— y las **inserciones son 98**, por debajo del tope de 100. Si el conteo que quieres es *churn* (inserciones + borrados = 108), avísame y recorto: el candidato obvio es el flush en blur (3 líneas) o el `keepalive` de `beforeunload` (12), ambos extras que pediste explícitamente en el enunciado.

`api.ts` **no se tocó**: `updateAnalysis(id, data: Record<string, string | undefined>)` ya aceptaba un payload parcial.

---

## 1. Diagnóstico previo (read-only, antes de editar)

1. **Botón:** `handleSaveChanges` (`:309`) → `testAPI.updateAnalysis(executionId, {…})` → **`PUT /executions/{id}/analysis`** (`api.ts:210`).
2. **Manda siempre los 13 campos completos** (11 análisis + `ai_conclusions` + `ai_recommendations`), no un delta.
3. **Estado:** 13 `useState` (`:204-216`), hidratados en `loadData` (`:266-278`) desde `GET /executions/{id}`.
4. **Edición:** `emitEdit(field, setter)` (`:304`) — hace `setter(value)` y avisa al padre por `onAnalysisEdit` (canal del integrado, F2).
5. **Feedback:** `alert()` bloqueante al terminar + el flag `saving` para deshabilitar el botón. Sin indicador de estado.
6. **Hallazgo clave:** `EditableTextArea` (`:166`) **solo confirma en `onBlur`**. Sin clic fuera, el padre no se entera de nada — así que un autosave enganchado al estado actual nunca se dispararía escribiendo.

**Imágenes:** no van por este flujo. `Dashboard.tsx` no referencia attachments (0 coincidencias); monitoreo y evidencias viven en sus propias páginas con sus endpoints `/attachments`. **Fuera del alcance de R1**, con su propio guardado.

---

## 2. Qué se implementó

### El enganche (resuelve el hallazgo 6)

`EditableTextArea` recibe un `debounceMs?: number` **opcional**: cuando está presente, una pausa al escribir también confirma el texto (además del blur de siempre). **Sin la prop, el componente se comporta exactamente como antes.**

```tsx
onChange={(e) => {
  const v = e.target.value;
  setLocalValue(v);
  if (debounceMs) { clearDraft(); draftTimer.current = window.setTimeout(() => { … onSave(v); }, debounceMs); }
}}
onBlur={() => { clearDraft(); onSave(localValue); }}
```

Se pasa `debounceMs={autoSaveMs}` en 6 puntos (uno de ellos es `AnalysisBox`, que cubre las 7 gráficas): **12 cajas editables en total**.

**Cero `setState` por tecla en el Dashboard:** el estado local del textarea es suyo (ya lo era); el padre se entera una vez por pausa de 1,8 s, no por pulsación.

### El autoguardado (patrón F3)

```tsx
const AUTOSAVE_MS = 1800;
const autoSaveMs = embedded ? undefined : AUTOSAVE_MS;
const saveTimerRef = useRef<number | null>(null);
const pendingRef = useRef<Record<string, string>>({});   // cola de campos, en ref
```

- `queueSave(field, value)` — encola el campo y rearma el debounce. Se llama desde `emitEdit` (una línea) y desde las dos cajas de conclusiones/recomendaciones, que usaban `setState` directo.
- `flushSave()` — envía **solo los campos pendientes** por el **mismo PUT**. Si falla, **devuelve lo pendiente a la cola** sin pisar lo escrito después, y marca error.
- **Fusión, no pisado:** el payload es un delta y el endpoint aplica `{k: v for k, v in data.model_dump().items() if v is not None}` (`upload.py:805`) — lo no enviado no se toca.
- **Flush en blur:** `onBlur` en el contenedor raíz (el evento burbujea) → salir de cualquier caja guarda ya, sin esperar el debounce.
- **`beforeunload`:** PUT best-effort con `keepalive`, igual que F3 en el integrado (no un diálogo de confirmación).

### El indicador

Barra fija abajo a la derecha, copiada del integrado: `Autoguardado activo` / `Guardando...` / `Guardado HH:MM` / `Error al guardar` + botón **Reintentar** (llama a `flushSave`, que conserva la cola).

**El botón "Guardar Todos los Cambios" se conserva** como flush manual completo: descarta el debounce en vuelo y vacía la cola (su PUT manda los 13 campos y los deja al día), y además refresca el indicador.

---

## 3. El modo embebido no dispara nada — 4 compuertas

La regla "no escribir en `test_executions`" del informe integrado **sigue intacta**. Cuatro guardas independientes, cualquiera de ellas basta:

| # | Línea | Guarda |
|---|---:|---|
| 1 | 266 | `const autoSaveMs = embedded ? undefined : AUTOSAVE_MS` → sin `debounceMs` no hay timer en las cajas |
| 2 | 291 | `queueSave`: `if (embedded) return;` → nada entra a la cola |
| 3 | 301 | `beforeunload`: `if (embedded \|\| !pend.length) return;` |
| 4 | 644 | El flush en blur y la barra solo se montan con `!embedded` |

`emitEdit` sigue llamando a `onAnalysisEdit?.()` igual que antes: en el integrado el texto sigue yendo **al canal de overrides** que maneja la página padre. **Opción B sin cambios.**

> **Sobre el comportamiento del integrado:** en modo embebido `autoSaveMs` es `undefined`, así que las cajas siguen confirmando **solo en blur**, exactamente como antes. La confirmación por pausa es exclusiva de la vista individual — el integrado no cambia en nada.

---

## 4. Validación ejecutada

| Check | Resultado |
|---|---|
| `npx tsc --noEmit` | **exit 0** |
| Vite HMR | `hmr update /src/components/dashboard/Dashboard.tsx` sin errores |
| **Regla 16** | Los hooks nuevos están en las líneas **267-320** (`useRef`, `useState`, `useCallback`, `useEffect`); el primer early return está en la **545**. Orden de hooks intacto |
| Compuertas `embedded` | **4/4** presentes (tabla arriba) |
| **No-regresión del PUT** | Ver abajo |

### No-regresión del contrato del PUT

Enviado un payload **parcial de un solo campo** (con su valor actual, para no alterar datos) y comparados los 13 campos `ai_*` antes/después:

```
PUT parcial (1 campo): HTTP=200
campos ai_* comparados : 13
campos alterados       : ninguno — el delta NO pisa lo no enviado
```

El contrato no cambió: es el mismo endpoint que usa el botón desde siempre, y ya soportaba deltas.

---

## 5. Historial

```
$ git log --oneline -1
1ae4f6f R1: autosave con indicador en reporte individual
```

Anteriores: `0dc5cd4` (F5) · `4ed0957` (UI-2) · `f069527` (GRAF1-C.2) · `fad4f01` (GRAF1-C).

---

## 6. Validación visual para Fredy — dos vistas

**(a) Reporte individual**
1. Abrir un reporte y editar cualquier caja de análisis. **Sin hacer clic fuera**, esperar ~3 s.
2. La barra de abajo a la derecha debe pasar por `Guardando...` y quedar en **`Guardado HH:MM`**.
3. **F5** → el texto persiste.
4. Salir de una caja con clic fuera → guarda **de inmediato**, sin esperar los 1,8 s.
5. El botón **"Guardar Todos los Cambios"** sigue funcionando igual (con su alerta).
6. Opcional: cortar la red (DevTools offline), editar → **`Error al guardar` + Reintentar**; restaurar y pulsar Reintentar → `Guardado HH:MM` sin perder el texto.

**(b) Informe integrado — la Opción B sigue intacta**
1. Abrir un informe integrado y editar una caja de sección.
2. El guardado sigue yendo a **overrides** (barra del integrado, no la nueva).
3. Abrir el **reporte individual** de esa misma ejecución y confirmar que **NO cambió**.

---

## 7. Higiene

- `origin` (producción) **no se tocó**. Push únicamente a `github backup-trabajo-local`.
- Backup `Dashboard.tsx.bak_r1_20260814_112442`.
- Sin `docker compose build` ni reinicio del backend: el cambio es solo frontend (HMR).
- **Ningún análisis IA ejecutado** — cuota intacta.
- Sin cambios en datos: la prueba del PUT reescribió un campo con su propio valor.
