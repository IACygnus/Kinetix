# Sprint 2.5.1 — Descarga JMX en Editor IA + Lista de Diseños

## Objetivo
Exponer en la UI la descarga del archivo `.jmx` en dos ubicaciones:
1. Header del Editor IA (junto a "Ver XML raw").
2. Cada fila de la lista "Mis Diseños IA".

## Endpoint backend reusado
`POST /script-designer/ai/download` (StreamingResponse, auth `admin|analyst`).

**Firma real (verificada en diagnóstico):**
```python
class DownloadRequest(BaseModel):
    jmx_content: str
    filename: Optional[str] = None
```
> El endpoint **NO acepta `design_id`** — solo `jmx_content`. Esto determinó el
> camino de implementación (ver abajo).

Verificado funcional desde curl:
```
download HTTP 200 size=79 bytes
content-disposition: attachment; filename="curl_test.jmx"
```

## Camino elegido (design_id vs contenido)
Como `/download` solo acepta `jmx_content`, **no se extendió el backend**. En su lugar:

- **Editor IA:** usa `originalJmx`, el estado que el editor ya mantiene en memoria
  y sincroniza con cada edición (auto-save regenera el JMX y actualiza
  `originalJmx`). → **1 call** a `/download`.
- **Lista de Diseños:** el summary no trae el JMX, solo `has_jmx`. → **2 calls**:
  `GET /designs/{id}` (obtiene `current_jmx`) → `POST /download`.

Ambos caminos encapsulados en `aiScriptDesignsAPI` para no duplicar la lógica
de blob/descarga (que ya existía en `AIScriptDesigner.tsx`).

## Componentes nuevos
- `frontend/src/services/api.ts`:
  - Helper interno `triggerJmxBlobDownload(jmxContent, filename)` — blob +
    `createObjectURL` + click sintético + `revokeObjectURL`.
  - `aiScriptDesignsAPI.downloadJmx(jmxContent, filename?)` — descarga por contenido.
  - `aiScriptDesignsAPI.downloadById(id, filename?)` — 2 calls (detalle → download).
- `frontend/src/pages/AIScriptEditor.tsx`:
  - Estado `downloadingJmx` + handler `handleDownloadJmx` (usa `originalJmx` +
    `designName`, errores vía `alert` para no disparar la pantalla de error
    completa que controla `if (error || !structure)`).
  - Botón "Descargar .jmx" en el header, antes de "Ver XML raw".
  - Import `Download` de lucide-react.
- `frontend/src/pages/AIScriptEditorList.tsx`:
  - Estado `downloadingId` + handler `handleDownloadDesign(id, name)`.
  - Botón ícono `Download` por fila (con `e.stopPropagation()`), antes de "Editar".
  - Import `Download` de lucide-react + `useCallback`.

## UX flujo
1. Editor IA → click "Descargar .jmx" → archivo descarga con el nombre del
   diseño saneado (`<nombre>.jmx`). Spinner "Descargando…" mientras corre.
2. Lista → click ícono Download por fila → descarga sin navegar; spinner por fila.

## Validación
- `tsc --noEmit`: **EXIT=0**.
- `Download` aparece 1 vez en import + 1 en JSX en cada archivo (sin duplicados).
- Líneas:
  - `AIScriptEditor.tsx`: 5849 → 5879 (+30)
  - `AIScriptEditorList.tsx`: 163 → 197 (+34)
  - `api.ts`: 746 → 776 (+30)
- Curl `POST /download`: **HTTP 200**, `Content-Disposition` correcto, JMX válido.

## Backups
`*.bak_251_20260603_124204` para api.ts, AIScriptEditor.tsx, AIScriptEditorList.tsx.

## Pendiente
Múltiples formatos de exportación (JTL Plan converter, locust, k6, etc.) —
postergado hasta cerrar todos los sprints pendientes y estabilizar el aplicativo.

## Estado: LISTO para Sprint 2.6 (listeners en vivo).
```