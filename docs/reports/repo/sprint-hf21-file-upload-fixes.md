# HF21 — Fix consolidado de file upload (Diseñador IA)

**Fecha:** 2026-07-28
**Branch:** `backup-trabajo-local`
**Archivos tocados:** 3 (`AIScriptDesigner.tsx`, `script_ai.py`, `frontend/Dockerfile`)

## Contexto

Detectado durante la validación end-to-end del Sprint 3.0 con `qa_pideky_com5.har`.
Fredy no pudo subir el HAR al Diseñador IA por 3 problemas de UI/límites.

---

## Bugs resueltos

### Bug 1 — File picker no mostraba los `.har` (CRÍTICO)

**Causa raíz encontrada:** no era un `accept=".json"` genérico. La constante
`ACCEPT_UPLOAD` (`AIScriptDesigner.tsx:100`) listaba
`.json,.yaml,.yml,.txt,.postman_collection,application/json,text/yaml,text/plain`
— **`.har` simplemente no estaba en la lista**. El diálogo de Windows filtraba
los HAR y al cambiar a "Todos los archivos" el picker se comportaba de forma
errática.

**Fix:** se agrega `.har` y `application/octet-stream` (el MIME con el que
Chrome/Windows reporta los `.har`; sin él el diálogo filtra el archivo aunque
la extensión esté declarada).

```
'.har,.json,.yaml,.yml,.txt,.postman_collection,
 application/json,application/octet-stream,text/yaml,text/plain'
```

El handler `handleFileChange` **no** rechazaba por extensión, así que no hubo
que relajar validación en el backend ni en el handler: el bloqueo era 100 % el
atributo `accept`.

### Bug 2 — Sin drag & drop (CRÍTICO)

**Causa raíz:** no existía ningún handler `onDragOver` / `onDragLeave` /
`onDrop` en el archivo. Único camino era el botón "Adjuntar archivo", que
sufría el Bug 1.

**Fix:** el contenedor del área de input es ahora zona de drop:

- `addFiles()` extraído como lógica compartida entre el picker y el drop
  (respeta `MAX_FILES = 5` y el aviso de sobre-tamaño, sin duplicar reglas).
- Validación de extensión en el drop vía `ACCEPTED_EXTENSIONS` — necesaria
  porque al soltar un archivo el atributo `accept` no se aplica.
- Overlay de feedback visual (`border-dashed` indigo + "Suelta el archivo
  aquí") con `pointer-events-none` para no bloquear el propio `drop`.
- `handleDragLeave` ignora el `leave` hacia un hijo del contenedor
  (`currentTarget.contains(relatedTarget)`), evitando el parpadeo clásico del
  overlay.
- `handleDragOver` llama `preventDefault()` **siempre**, incluso durante
  `isLoading`. Si no se cancela el `dragover`, el navegador abre el archivo
  soltado y se pierde la sesión del chat — con un HAR de cientos de MB eso
  significaba perder toda la conversación.

### Mejora 3 — Límite 50 MB → 500 MB

Aplicado en:

| Capa | Antes | Después |
|---|---|---|
| Frontend `MAX_UPLOAD_BYTES` | 50 MB | **500 MB** |
| Backend `MAX_FILE_BYTES` | 50 MB | **500 MB** |
| Hint del UI | "Máx. 50 MB" | "Arrastra o adjunta · Máx. 500 MB" |
| `frontend/Dockerfile` nginx | (sin directiva) | `client_max_body_size 500m` |

---

## Descubrimiento importante: `MAX_FILE_BYTES` tenía doble uso

`MAX_FILE_BYTES` no era solo el techo de upload. También era el **límite por
defecto de `_truncate()`** (`script_ai.py:1400`), la función que recorta el
texto que entra al prompt de la IA — usada en 4 sitios (líneas 1589, 2214,
2226, 2240).

Subirlo a 500 MB tal cual habría dejado que un archivo **no-HAR** de 500 MB
(un JSON/Swagger gigante, que no pasa por `har_compressor`) entrara **entero**
al prompt del modelo: coste desbordado y riesgo de OOM.

**Decisión:** se separan los dos conceptos.

```python
MAX_FILE_BYTES    = 500 * 1024 * 1024   # techo de UPLOAD (HF21)
MAX_CONTEXT_CHARS =  50 * 1024 * 1024   # techo de CONTEXTO hacia la IA
```

`_truncate()` pasa a usar `MAX_CONTEXT_CHARS`. Resultado: el upload acepta
500 MB, pero lo que ve el modelo sigue topado en 50 MB — **idéntico al
comportamiento previo a HF21**. Ningún cambio de coste de tokens.

Esto es una desviación consciente del borrador de la tarea (que pedía subir
`MAX_FILE_BYTES` a secas); sin ella el fix habría introducido una regresión de
coste.

## Nota sobre nginx (acción pendiente para producción)

- **No existe** `nginx/` ni `deployment/` en el repo.
- El único nginx versionado es el del `frontend/Dockerfile` (stage
  `production`), y **sirve solo la SPA — no proxea `/api`**. Se le agregó
  `client_max_body_size 500m` por consistencia, pero **no es el que limita los
  uploads**.
- El nginx que sí está en la ruta del upload en producción es el **externo**
  del servidor: `/etc/nginx/sites-available/kinetix.sqasa.co` (Azure
  `20.81.141.77`), que **no está versionado**.

> **Acción manual requerida antes de usar HAR >1 MB en producción:** agregar
> `client_max_body_size 500m;` a `/etc/nginx/sites-available/kinetix.sqasa.co`
> y recargar (`nginx -s reload`). El default de nginx es **1 MB**, así que en
> producción cualquier HAR fallará con **413** hasta que se aplique.
> En local (dev) no aplica: el browser habla directo a `localhost:8001`.

## Verificación del stack de upload

Starlette 0.27.0 expone `MultiPartParser.max_file_size = 1 MB`, pero es el
umbral de *spool a disco* (`SpooledTemporaryFile`), **no un rechazo**. Esa
versión no tiene el `max_part_size` que rechaza (introducido en 0.37+). No hay
límite de body en `main.py`, `Dockerfile` ni `docker-compose.yml`.

Comprobado empíricamente dentro del contenedor: se parseó un part multipart de
**60 MB** (sobre el viejo tope) y llegó completo, sin 413/400.

```
filename       : big.har
bytes recibidos: 62914560 = 60 MB
sin rechazo 413/400: OK
```

Verificado también que `_truncate()` sigue recortando en 50 MB y deja pasar
intactos los textos pequeños.

## Tests

```
208 passed, 6 warnings
```

- **208 pass**, no 249. El conteo de 249 del enunciado **no corresponde al
  estado actual del repo**: `pytest --collect-only` recoge exactamente 208
  tests en `backend/tests/` (19 archivos `test_*.py`). No se modificó ningún
  archivo de test en HF21 (`git status` lo confirma), y el número de tests
  recolectados es independiente de este cambio → **no hay regresión**; la cifra
  de referencia estaba desactualizada.
- Suite ejecutada completa (sin filtro `-m "not slow"`): 208/208 en verde.
- `npx tsc --noEmit` → **EXIT=0**.
- No se agregan tests unitarios nuevos: los cambios son de UI (Vitest no está
  configurado en el proyecto) y de constantes.

## Estado de servicios

`docker compose restart frontend backend` — ambos arriba:

- `jmeter_backend` — Up (healthy), `/health` → 200, uvicorn recargado.
- `jmeter_frontend` — Up, Vite v5.4.21 ready.
- Constantes confirmadas en runtime: `MAX_FILE_BYTES 500 MB`,
  `MAX_CONTEXT_CHARS 50 MB`.

## Backups

```
frontend/src/pages/AIScriptDesigner.tsx.bak_hf21_20260728_170718
backend/app/api/v1/endpoints/script_ai.py.bak_hf21_20260728_170718
frontend/Dockerfile.bak_hf21_20260728_170718
```

## Estado

**LISTO** para validación end-to-end del Sprint 3.0 con el HAR real de Pideky.
Criterio de éxito = validación visual de Fredy (regla 9 del proyecto).
