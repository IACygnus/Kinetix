# Sprint 2.5c — UI Smoke Test

**Fecha:** 2026-06-01
**Branch:** backup-trabajo-local
**Owner:** Fredy Bonilla
**Estado:** ✅ Botón + modal + handler implementados; tsc EXIT=0

---

## 1. Resumen

UI completa para el smoke test del Editor IA (que consume el endpoint
`POST /script-designer/ai/designs/{id}/smoke-test` del Sprint 2.5b):

- Botón **"Probar (Smoke)"** en el header del Editor IA, al lado de "Pedir a IA".
- Click → modal con auto-ejecución del smoke test.
- Spinner "Ejecutando JMeter…" durante 5-10 s típicos.
- Resultado: badge de status (success/partial/failed/error) + tabla de samplers + log de JMeter expandible.
- Botón "Reintentar" si falla; al cerrar el modal el estado se limpia.

---

## 2. Archivos modificados

| Archivo | Tipo | Δ líneas |
|---|---|---|
| `frontend/src/services/api.ts` | MOD | +44 (interfaces `SmokeSamplerResult` + `SmokeTestResult` + wrapper `smokeTestAPI.run`) |
| `frontend/src/pages/AIScriptEditor.tsx` | MOD | +239 (imports `Play`/`XCircle` + estados + `runSmokeTest` + botón + cableado `SmokeTestModal` + componente `SmokeTestModal`) |

**Backups creados:**
- `frontend/src/services/api.ts.bak_25c_20260601_090519`
- `frontend/src/pages/AIScriptEditor.tsx.bak_25c_20260601_090519`

---

## 3. Componentes nuevos

### 3.1. `smokeTestAPI` (services/api.ts)

```ts
export interface SmokeSamplerResult {
  label: string;
  success: boolean;
  response_code: string;
  response_message: string;
  elapsed_ms: number;
  failure_message?: string | null;
}

export interface SmokeTestResult {
  status: 'success' | 'partial' | 'failed' | 'error';
  duration_sec: number;
  total_samples: number;
  successful_samples: number;
  failed_samples: number;
  samplers: SmokeSamplerResult[];
  jmeter_log_tail?: string | null;
  error_message?: string | null;
}

export const smokeTestAPI = {
  run: (designId, timeoutSec = 60) => POST /script-designer/ai/designs/{id}/smoke-test
                                       con axios timeout = (timeoutSec + 30) * 1000
};
```

El timeout del axios sobre-aprovisiona +30 s sobre el `timeout_sec` que se pasa al backend para dar margen al subprocess JMeter (arranque de JVM ~3 s).

### 3.2. Estados nuevos en `AIScriptEditor`

```ts
const [smokeModalOpen, setSmokeModalOpen] = useState(false);
const [smokeRunning, setSmokeRunning] = useState(false);
const [smokeResult, setSmokeResult] = useState<SmokeTestResult | null>(null);
const [smokeError, setSmokeError] = useState<string | null>(null);
const [smokeShowLog, setSmokeShowLog] = useState(false);
```

### 3.3. `runSmokeTest` + auto-trigger

- `runSmokeTest` (useCallback) llama a `smokeTestAPI.run(designId, 60)` y captura
  `e.response?.data?.detail || e.message` como mensaje.
- `useEffect` auto-ejecuta al abrir el modal si no hay resultado/error/running.
- Al cerrar el modal, un `setTimeout(200ms)` limpia `result/error/showLog`
  para que el siguiente click vuelva a relanzar.

### 3.4. Botón "Probar (Smoke)" en el header

```tsx
<button
  onClick={() => setSmokeModalOpen(true)}
  disabled={!designId || smokeRunning}
  className="... text-emerald-700 bg-emerald-50 border-emerald-200 ..."
  title="Ejecutar smoke test (1 usuario, 1 iteración) con JMeter real"
>
  <Play className="w-4 h-4" />
  Probar (Smoke)
</button>
```

Colocado **antes** del botón "Pedir a IA" en el mismo flex container —
no rompe la disposición existente del header.

### 3.5. `SmokeTestModal`

Componente nuevo al final del archivo (después de `AddElementModal`):

| Zona | Contenido |
|---|---|
| **Header** | Icono Play emerald + "Smoke Test" + subtítulo "(1 usuario, 1 iteración)" + botón X |
| **Body — running** | `Loader2` spinner emerald + "Ejecutando JMeter…" + nota de duración esperada |
| **Body — error** | Tarjeta roja con `XCircle` + mensaje del error |
| **Body — result** | (1) Banner de status con badge coloreado (emerald/amber/red según `status`) y ratio `OK / total · duración`. (2) Tabla con columnas: icono ok/fail, label + failureMessage, response_code (coloreado 2xx/3xx/4xx/5xx), tiempo. (3) Log de JMeter colapsable con `ChevronRight`/`ChevronDown` (preformateado dark con `whitespace-pre-wrap`, max-h 64). |
| **Footer** | Nota informativa + botones "Reintentar" (cuando hay result/error y no está running) + "Cerrar" |

Estados manejados explícitamente:
- `running` → solo loader.
- `error` (excepción de red/HTTP) → tarjeta roja.
- `result.status === 'success'` → banner emerald.
- `result.status === 'partial'` → banner amber.
- `result.status === 'failed'` → banner rojo.
- `result.status === 'error'` (JMeter no arrancó) → banner rojo + `error_message` en el banner.
- Lista de samplers vacía → mensaje amber "No se ejecutó ningún sampler".

Códigos de respuesta colorados:
- `2xx` → emerald.
- `3xx` → blue.
- `4xx` → amber.
- `5xx` u otros → red.

---

## 4. UX flujo

```
1. Usuario en Editor IA → click "Probar (Smoke)" (header, junto a Pedir a IA).
2. Modal abre. useEffect auto-dispara runSmokeTest().
3. UI muestra spinner emerald + "Ejecutando JMeter… (5-15 s)".
4. Backend ejecuta jmeter subprocess (Sprint 2.5b).
5. Llega response → setSmokeResult.
6. Modal renderiza: banner de status + tabla de samplers.
7. Usuario expande log de JMeter si necesita diagnosticar.
8. (a) Cerrar → estado se limpia tras 200 ms.
   (b) Reintentar → limpia result/error y vuelve a llamar runSmokeTest.
```

---

## 5. Validaciones

### 5.1. TypeScript check

```
npx tsc --noEmit → EXIT=0
```

### 5.2. Líneas del editor

| Archivo | Antes | Ahora | Δ |
|---|---|---|---|
| `AIScriptEditor.tsx` | 4 804 | **5 043** | +239 |
| `services/api.ts` | 602 | **646** | +44 |

Dentro del margen razonable (+~250 estimado del prompt).

### 5.3. Imports lucide-react reusados

Reuso `Loader2`, `AlertTriangle`, `CheckCircle2`, `X`, `ChevronDown`, `ChevronRight` (ya estaban). Añado `Play` y `XCircle` (faltaban).

Nota: el prompt mencionaba `CheckCircle` pero el archivo ya tenía `CheckCircle2` importado — uso el ya importado para no duplicar.

---

## 6. Garantías de no-regresión

- El botón **"Pedir a IA"** del HF4 sigue intacto (orden visual: ahora aparece después del nuevo "Probar (Smoke)").
- El botón **"Ver XML raw"** sigue funcionando.
- `SmokeTestModal` solo se renderiza si `open === true` (no afecta el DOM cuando está cerrado).
- `treeActions`, `AddElementModal` (HF7.A) y todo lo demás del Editor IA queda sin cambios.
- `tsc --noEmit` → EXIT=0.

---

## 7. Cómo validar visualmente

1. Abrir un diseño con JMX en `/ai-script-designer/editor/{designId}`.
2. En el header, debe aparecer el botón verde **"Probar (Smoke)"** a la izquierda de "Pedir a IA".
3. Click → modal abre con spinner emerald durante ~5-10 s.
4. Resultado esperado para el diseño booking-restful: status="success", 6 samplers OK con códigos 200/201, tiempos en ms.
5. Click en "Log de JMeter (N chars)" → expande las últimas líneas del jmeter.log.
6. "Reintentar" relanza la ejecución; "Cerrar" cierra el modal.
7. Probar con un diseño cuyo JMX apunte a un host inválido — debe mostrar status="failed" con failure_message de connection refused / no route to host, sin crashear.

---

## 8. Estado

**✅ LISTO para Sprint 2.5d (endpoint /execute full run con metrics_collector + JTL persistido).**

No se hizo `docker compose build`. El frontend recarga automáticamente vía Vite dev server.
