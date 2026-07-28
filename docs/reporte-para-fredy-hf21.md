# HF21 — Reporte para Fredy

## Estado

**SUCCESS** — con 1 acción manual pendiente de tu lado para producción (ver abajo).

## Fixes aplicados

### Bug 1 (file picker) — RESUELTO
La causa no era un `accept=".json"` genérico: la lista `ACCEPT_UPLOAD` del
Diseñador IA **no incluía `.har`**. Por eso Windows te escondía el archivo, y al
forzar "Todos los archivos" el diálogo se portaba raro.
Ahora acepta `.har` + `application/octet-stream` (el MIME real con el que
Chrome/Windows reporta los HAR). Se selecciona directo, sin cambiar el filtro.

### Bug 2 (drag & drop) — RESUELTO
No existía **ningún** handler de drag en el archivo. Ahora el área del chat es
zona de drop, con recuadro punteado indigo y el texto "Suelta el archivo aquí".
Detalle que cuidé: si soltabas un archivo mientras la IA estaba generando, el
navegador lo abría y **te tumbaba la conversación**. Eso queda bloqueado.

### Mejora 3 (límite) — APLICADA: 50 MB → 500 MB
- Frontend `MAX_UPLOAD_BYTES` → 500 MB (+ hint del UI actualizado)
- Backend `MAX_FILE_BYTES` → 500 MB
- `frontend/Dockerfile` nginx → `client_max_body_size 500m`

## Descubrimiento importante durante la implementación

**`MAX_FILE_BYTES` tenía doble uso** y subirlo a secas habría sido una regresión
seria de coste.

Además de ser el techo de upload, era el límite por defecto de `_truncate()`
— la función que recorta el texto **que entra al prompt de la IA** (usada en 4
lugares). Subirlo a 500 MB habría permitido que un archivo **no-HAR** de 500 MB
(un Swagger/JSON gigante, que no pasa por el compresor de HAR) se fuera
**entero** al modelo. Coste desbordado y riesgo de OOM.

Lo separé en dos constantes:

```python
MAX_FILE_BYTES    = 500 MB   # techo de UPLOAD  (lo que puedes adjuntar)
MAX_CONTEXT_CHARS =  50 MB   # techo de CONTEXTO (lo que ve la IA)
```

Subes 500 MB, pero lo que llega al modelo sigue topado en 50 MB — exactamente
igual que antes. **Cero cambio en consumo de tokens.**

## Cambios técnicos

- `frontend/src/pages/AIScriptDesigner.tsx` — `.har` en `accept`; `addFiles()`
  compartido entre picker y drop; handlers `onDragOver`/`onDragLeave`/`onDrop`
  + overlay visual; `MAX_UPLOAD_BYTES` 500 MB; hint del UI.
- `backend/app/api/v1/endpoints/script_ai.py` — `MAX_FILE_BYTES` 500 MB;
  nueva `MAX_CONTEXT_CHARS` 50 MB; `_truncate()` usa la nueva.
- `frontend/Dockerfile` — `client_max_body_size 500m`.

## ⚠ Acción manual pendiente (solo para PRODUCCIÓN)

En el repo **no hay** carpeta `nginx/` ni `deployment/`. El nginx versionado
(el del `frontend/Dockerfile`) **solo sirve la SPA, no proxea `/api`** — no es
el que limita uploads.

El que sí está en la ruta del upload en producción es el nginx **externo** del
servidor, que no está versionado:

```bash
# En 20.81.141.77
nano /etc/nginx/sites-available/kinetix.sqasa.co
#   → agregar dentro del server: client_max_body_size 500m;
nginx -t && nginx -s reload
```

**El default de nginx es 1 MB.** Sin este cambio, en `kinetix.sqasa.co`
cualquier HAR va a fallar con **413** por más que backend y frontend acepten
500 MB.

**En local (lo que vas a probar ahora) no aplica** — el browser habla directo a
`localhost:8001`.

## Validaciones

- `npx tsc --noEmit` → **EXIT=0**
- Tests backend → **208 passed** (suite completa, sin regresiones)
- Probé el stack de multipart dentro del contenedor con un archivo de **60 MB**
  (sobre el viejo tope): llega completo, sin 413/400.
- `docker compose restart frontend backend` → backend healthy (`/health` 200),
  Vite ready.

### Nota sobre el conteo de tests
El enunciado decía "249 PASS actuales", pero el repo tiene **208**.
`pytest --collect-only` recoge 208 en `backend/tests/` (19 archivos de test), y
HF21 **no tocó ningún test**. La cifra 249 está desactualizada — no es una
regresión, los 208 pasan todos.

## Git

- Commit: `<hash>`
- Push a **github**: `<estado>`
- **origin (Azure): NO tocado** ✅

## Siguiente paso

1. Ventana incógnito nueva de Chrome (Ctrl+Shift+N) — importante, para que
   Vite no sirva el bundle viejo desde caché.
2. `localhost:5173`, login `admin` / `sqa2024`.
3. Diseñador IA → **prueba las dos vías**:
   - Botón "Adjuntar archivo" → `qa_pideky_com5.har` debe aparecer sin cambiar
     el filtro a "Todos los archivos".
   - **Arrastrar** el `.har` directo sobre el área del chat → debe salir el
     recuadro punteado y luego el chip del archivo.
4. Verificar el chip con nombre y tamaño.
5. Generar con el prompt de Pideky.
6. Compartir el JMX resultante para análisis.

> Copia de este reporte también en `/tmp/reporte-para-fredy-hf21.md` (lo pediste
> ahí), pero la versión buena vive en `docs/` según la regla del proyecto.
