# R2 — Autoguardado con indicador en Monitoreo y Evidencias

**Fecha:** 2026-08-16
**Commit:** `50ae4a4` — *R2: autosave con indicador en Monitoreo y Evidencias*
**Push:** `github/backup-trabajo-local` (`0755692..50ae4a4`). **`origin` NO se
tocó.**
**Estado:** **IMPLEMENTADO · `tsc --noEmit` exit 0 · PENDIENTE TU VALIDACIÓN
VISUAL** (§5).

**Presupuesto:** máx 3 archivos → **138 insertadas / 6 borradas, 3 archivos.**

---

## 1. Diagnóstico express (read-only)

1. **Las dos páginas comparten componente:** `ImageAnalysisCard.tsx` (156
   líneas), usado por `MonitoringPage.tsx:8,232` y `EvidencePage.tsx:8,227`.
   Ningún otro sitio lo usa.
2. **El estado del texto vive en la tarjeta**, no en la página: `localAnalysis`
   + `isEdited` (`ImageAnalysisCard.tsx:23-24` antes del cambio).
3. **Guardaba solo con el botón**, que aparece únicamente si `isEdited`:
   `saveAnalysis()` hacía `PUT /executions/{id}/attachments/{aid}/analysis` con
   `{ai_analysis: localAnalysis}` (líneas 65-84).
4. **Las páginas hidratan** desde `GET /executions/{id}/image-analyses`, que sí
   devuelve `ai_analysis` (`MonitoringPage.tsx:76`).
5. **El informe integrado NO usa esta tarjeta** (grep sobre
   `components/integrated/*`: cero coincidencias); sus imágenes van por
   overrides (F4).
6. Conclusión: bastaba con añadir el debounce dentro de la tarjeta y un
   indicador por página, sin endpoints nuevos.

---

## 2. Lo que se hizo

### 2.1 Autoguardado dentro de la tarjeta (patrón F3/R1)

- **Debounce 1.8 s** al teclear; el texto pendiente vive en `pendingRef` y el
  temporizador en `saveTimerRef` — **el autoguardado no añade ni un `setState`
  por tecla**.
- **`onBlur` hace flush** inmediato, sin esperar al debounce.
- **`beforeunload`** reenvía lo pendiente con `keepalive`, igual que F3/R1.
- **Mismo endpoint de siempre**: `PUT .../attachments/{aid}/analysis`. Cero
  endpoints nuevos.
- **Payload por imagen**: cada tarjeta manda solo su `ai_analysis`, así que
  guardar una nunca pisa el análisis de otra.
- El botón **Guardar se conserva** y ahora es el flush manual (ambos caminos
  entran por la misma función `doSave`).

> Nota honesta: el `<textarea>` ya era controlado antes de R2, así que sigue
> habiendo un `setState` por tecla **preexistente**. Lo que R2 garantiza es no
> añadir ninguno más; convertirlo en no controlado sería un refactor del
> componente, fuera del encargo.

### 2.2 Activación por prop (componente compartido)

```typescript
/** R2: sin `autoSaveMs` el componente se comporta EXACTAMENTE como antes
 *  (solo guarda con el boton). */
autoSaveMs?: number;
onSaveStateChange?: (state: ImageSaveState, savedAt: string, retry: () => void) => void;
```

Solo Monitoreo y Evidencias pasan `autoSaveMs={1800}`. Cualquier otro uso
futuro de la tarjeta mantiene el comportamiento actual por defecto.

### 2.3 Indicador: uno por página

Mismo diseño que F3/R1 (fijo abajo a la derecha): `Autoguardado activo` →
`Guardando...` → `Guardado HH:MM`, y `Error al guardar` + **Reintentar**. Cada
tarjeta reporta su estado a la página y le entrega **cómo reintentar lo suyo**,
así el botón de reintento reenvía exactamente el texto que falló.

---

## 3. La guarda del informe integrado

R1 necesitaba la bandera `embedded` porque el mismo `Dashboard` se renderiza
dentro del integrado. **Aquí la separación es estructural:** el integrado no
importa `ImageAnalysisCard` en ningún punto, y el autoguardado solo existe si
alguien pasa `autoSaveMs`. No hay contexto en el que pueda dispararse por
accidente; no hizo falta bandera.

---

## 4. Validación hecha

### 4.1 `tsc --noEmit` → exit 0

### 4.2 Regla 16

Hooks de `ImageAnalysisCard` en líneas **34-142** (5 `useState`, 3 `useRef`,
1 `useCallback`, 3 `useEffect`); los `return` tempranos están en **171 y 187**.
Todos los hooks van antes.

### 4.3 No-regresión del endpoint (curl)

```
GET  .../attachments/{aid}/analysis  ANTES   -> {'ai_analysis': '', ...}
PUT  .../attachments/{aid}/analysis          -> 200
GET  .../attachments/{aid}/analysis  DESPUES -> {'ai_analysis': '[R2_PRUEBA] texto de verificacion', ...}
PUT  (restaurar a vacio)                     -> 200
GET  .../attachments/{aid}/analysis  FINAL   -> {'ai_analysis': '', ...}
```

El endpoint que usa el autoguardado persiste y el dato quedó restaurado como
estaba.

> **Un tropiezo que vale la pena registrar:** mi primera comprobación leyó el
> resultado desde `GET /attachments`, y el marcador «no aparecía». No era un
> fallo del PUT: **ese endpoint no devuelve `ai_analysis`** (sus claves son
> `attachment_type, category, description, file_size, file_type, filename,
> filepath, id, sort_order, title`). Las páginas hidratan desde
> `/image-analyses`, que sí lo incluye — verificado. El guardado estaba bien
> desde el principio; el que estaba mal era mi verificador.

---

## 5. Lo que necesito que valides (visual)

1. **Monitoreo**: edita el análisis de una imagen y **no hagas clic fuera** →
   a los ~3 s debe decir `Guardado HH:MM` → F5 → el texto sigue ahí.
2. **Evidencias**: lo mismo.
3. **Botón Guardar**: sigue apareciendo al editar y sigue guardando.
4. **Varias imágenes**: edita dos distintas y comprueba que cada una conserva
   su propio texto (no se pisan).
5. **Informe integrado**: las imágenes siguen guardando por overrides y el
   análisis original de la imagen no cambia.

---

## 6. Archivos tocados

| Archivo | Qué | Backup |
|---|---|---|
| `frontend/src/components/analysis/ImageAnalysisCard.tsx` | debounce, flush, keepalive, props opcionales | `.bak_r2_20260816_105903` |
| `frontend/src/pages/MonitoringPage.tsx` | estado del indicador + props + indicador | `.bak_r2_20260816_105903` |
| `frontend/src/pages/EvidencePage.tsx` | ídem | `.bak_r2_20260816_105903` |

Backend sin tocar: no hay endpoints nuevos.
