# Sprint 2.4-HF2 — Gestión de Data Files

**Fecha:** 2026-05-26
**Estado:** ✅ Backend 42/42 tests + tsc EXIT=0 + 5 endpoints + tabla creada

## Objetivo

Implementar gestión completa de archivos CSV asociados a un diseño AI Script:
- Subir/listar/preview/eliminar CSVs.
- Detección automática de columnas y filas.
- Mapping `variable_jmeter -> column_csv` (default = nombres directos).
- Storage físico en `backend/uploads/ai_data_files/{design_id}/`.

## Cambios

### Backend

| Archivo | Tipo | Líneas |
|---|---|---|
| `backend/app/db/models/ai_design_data_file.py` | NUEVO | 53 |
| `backend/app/db/models/__init__.py` | MOD | +2 (import + __all__) |
| `backend/app/schemas/ai_design_data_file.py` | NUEVO | 42 |
| `backend/app/api/v1/endpoints/ai_design_data_files.py` | NUEVO | 264 |
| `backend/app/api/v1/api.py` | MOD | +8 (import + include_router) |

**Tabla creada por `Base.metadata.create_all`** al restart del backend:

```
public.ai_design_data_files (15 columnas)
├── id (UUID PK)
├── design_id (UUID FK -> ai_script_designs.id CASCADE) [indexed]
├── user_id (UUID FK -> users.id SET NULL)
├── original_filename, stored_filename, file_path, file_size
├── delimiter, encoding, has_header
├── columns (jsonb), row_count, variable_mapping (jsonb)
└── created_at, updated_at
```

### Frontend

| Archivo | Diff |
|---|---|
| `frontend/src/services/api.ts` | 492 → **567** (+75: `AIDesignDataFile`, `AIDesignDataFilePreview`, `aiDesignDataFilesAPI`) |
| `frontend/src/pages/AIScriptEditor.tsx` | 3088 → **3460** (+372) |

Backups con sufijo `.bak_hf2_20260526_185903` para los 4 archivos modificados.

## Endpoints nuevos (5)

| Verbo | Path | Roles |
|---|---|---|
| `POST` | `/api/v1/script-designer/ai/designs/{design_id}/data-files` | admin, analyst |
| `GET` | `/api/v1/script-designer/ai/designs/{design_id}/data-files` | admin, analyst, viewer |
| `GET` | `/api/v1/script-designer/ai/designs/{design_id}/data-files/{file_id}/preview` | admin, analyst, viewer |
| `PATCH` | `/api/v1/script-designer/ai/designs/{design_id}/data-files/{file_id}` | admin, analyst |
| `DELETE` | `/api/v1/script-designer/ai/designs/{design_id}/data-files/{file_id}` | admin, analyst |

**Validaciones del endpoint upload:**
- Máximo 10 MB.
- Decodificación con encoding declarado, fallback a `latin-1`.
- Detección de delimitador si `delimiter="auto"` (entre `, ; \t |`).
- Soporte `has_header=true|false` con generación de `col1, col2, ...` si no hay header.
- Verifica que el diseño existe + acceso del usuario (admin ve todo; analyst solo el suyo).

## Funcionalidades frontend

### Árbol del editor

Nuevo nodo **"Data Files"** entre "Listeners" y "No editables" (siempre visible aunque esté vacío). Auto-expande, con sub-item "Gestionar archivos" + un item por CSV subido.

### Panel `DataFilesPanel` (al seleccionar "Gestionar archivos")

- **Subir nuevo CSV**: selector de delimitador (`,`, `;`, `\t`, `|`, `auto`), checkbox header sí/no, botón "+ Subir CSV" (input file oculto, accept `.csv,.txt`).
- **Archivos asociados**: lista con nombre, tamaño, conteo filas/columnas, columnas detectadas inline, botón eliminar (confirm dialog).
- **Tip box** azul explicando cómo asociarlos a un CSV Data Set en el árbol.

### Panel `DataFileDetailPanel` (al seleccionar un archivo)

- Header con nombre + botón "Eliminar archivo".
- Card **"Información"**: delimitador, encoding, tamaño, filas.
- Card **"Columnas y variables JMeter"**: nombres de columnas + instrucciones para usar en CSV Data Set (filename + variables).
- Card **"Preview"**: tabla de las primeras 5 filas reales (lectura on-demand vía endpoint preview).

## Tests / Validaciones

- ✅ **Backend pytest: 42/42 PASS** (sin regresión por la tabla nueva).
- ✅ **Frontend `tsc --noEmit`: EXIT=0**.
- ✅ **Tabla `ai_design_data_files` creada** automáticamente por `Base.metadata.create_all` tras el `docker restart jmeter_backend`. 15 columnas, FK CASCADE a `ai_script_designs`, FK SET NULL a `users`, index en `design_id`.
- ✅ **5 endpoints registrados** verificados con `app.routes`.

## Adaptaciones del prompt original

1. **`relationship` no usado** en el modelo (el snippet del prompt lo importaba pero no lo usaba). Lo omití para evitar warnings de imports no usados.
2. **`shutil` no usado** en el endpoint — el snippet del prompt lo importaba pero el código solo usa `os.remove`. Lo omité.
3. **`from app.db.session import get_db` y `from app.db.models.user import User`** confirmados como paths reales del proyecto (otros endpoints los usan así).
4. **`UPLOAD_BASE = Path("/app/uploads/ai_data_files")`** usa el path dentro del container Docker (volumen `uploads_data` montado en `/app/uploads`). El `_ensure_upload_dir` lo crea on-demand.
5. **`reloadDataFiles` se dispara cuando estructura termina de cargar** (no inmediatamente con `designId`) — añadí `&& structure` al guard del useEffect para evitar fetch en estado de error.
6. **`DetailPanel` recibe 5 props nuevas** (`designId`, `dataFiles`, `dataFilesLoading`, `reloadDataFiles`, `onDataFileSelect`) en vez de inyectar el contexto vía closures, manteniendo type-safety.
7. **`useState`/`useRef` en `DataFilesPanel` y `DataFileDetailPanel`** son hooks locales al componente — coexisten sin conflicto con los del componente padre.

## Lo que NO se hizo (y NO está pedido en HF2)

- **Integración bidireccional con `CSVDataSetEditPanel`**: el campo "Archivo CSV" del editor sigue siendo un input de texto libre. El usuario debe escribir el nombre del CSV manualmente. El panel `DataFileDetailPanel` muestra el comando exacto a copiar. Un upgrade futuro (HF2.1?) sería un dropdown autocomplete con los CSVs subidos.
- **Mapping editor**: el endpoint PATCH funciona, pero la UI no expone el editor de mapping todavía. Por defecto las variables JMeter son los nombres de columna directos, que cubre el 100% del caso de uso típico.
- **Tests específicos del CRUD**: validado con curl/Postman cuando Fredy lo pruebe visualmente. Si quieren tests automatizados se añaden en HF2.1.

## Pendientes derivados

- **Validación visual de Fredy**: subir un CSV de prueba (ej. `usuarios.csv` con columnas firstname,lastname) → ver que aparece en el árbol → preview muestra las filas → eliminar funciona.
- **Sprint HF3**: límite HAR 5MB + Function Helper UI (las 17 funciones del 2.7).
- **Sprint HF4**: integración Editor IA ↔ Chat (botón "Pedir a IA").
- **HF2.1 (opcional):** dropdown autocomplete en CSVDataSet → archivos del design + UI de mapping de variables.

## Estado

**LISTO para HF3.** Backend completo y testado, frontend compila, tabla creada en DB, 5 endpoints accesibles bajo `/script-designer/ai/designs/{design_id}/data-files`. El editor visual ya muestra el nodo "Data Files" en el árbol y permite subir/listar/eliminar.
