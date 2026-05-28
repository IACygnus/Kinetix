# Sprint 2.4-HF3 — Función Helper + límite a 5 MB

**Fecha:** 2026-05-26
**Estado:** ✅ tsc EXIT=0

## Cambios

### Parte 1 — Límite de archivos a 5 MB

| Archivo | Cambio |
|---|---|
| `backend/app/api/v1/endpoints/script_ai.py` | `MAX_FILE_BYTES = 500 * 1024` → `5 * 1024 * 1024` (línea 47). Afecta a `/upload-file`, `/refine` y la función `_truncate`. |
| `frontend/src/pages/AIScriptDesigner.tsx` | `MAX_UPLOAD_BYTES = 500 * 1024` → `5 * 1024 * 1024` (línea 82). Indicador visual añadido en la barra del chat: `<span>Máx. 5 MB</span>`. |

Permite ahora subir Postman Collections grandes, OpenAPI completos y HARs de aplicaciones reales sin truncado.

### Parte 2 — Function Helper en el Editor IA

| Archivo | Diff |
|---|---|
| `frontend/src/pages/AIScriptEditor.tsx` | 3460 → **3857** (+397) |

Backup: `AIScriptEditor.tsx.bak_hf3_20260526_191143`.

#### Catálogo de 25 funciones JMeter

Organizadas en 6 categorías:

- **Aleatorios (4)**: `__Random`, `__RandomString`, `__UUID`, `__RandomFromMultipleVars`
- **Fechas (4)**: `__time`, `__timeShift`, `__RandomDate`, `__dateTimeConvert`
- **Contadores (3)**: `__counter`, `__intSum`, `__longSum`
- **Hilos (5)**: `__threadNum`, `__machineName`, `__machineIP`, `__property`, `__P`
- **Variables (3)**: `__V`, `__eval`, `__StringFromFile`
- **Strings (6)**: `__char`, `__changeCase`, `__urlencode`, `__urldecode`, `__escapeHtml`

Cada función incluye:
- `name`, `category`, `syntax` (template visible), `description`
- `params[]` con `name`, `label`, `default`, `hint?`, `type?` (`text`/`select`/`date_format`), `options?`

#### Componente `FunctionHelperButton`

Dropdown contextual disparado por botón `fx` (verde indigo).
- **Vista 1**: tabs por categoría + lista de funciones con preview de descripción.
- **Vista 2 (función seleccionada)**: formulario dinámico con los parámetros, preview live de la expresión generada, botón "Insertar".
- **Tipos especiales**:
  - `date_format`: dropdown con 12 formatos comunes + input libre.
  - `select`: dropdown con opciones predefinidas (ej. `TRUE/FALSE`, `UPPER/LOWER/CAPITALIZE`).
- Cierre con click fuera (ref + event listener).

`buildFunctionExpression(fn, values)` construye `${__fn(arg1,arg2,...)}` reemplazando los parámetros con los valores ingresados.

#### Wrappers `InputWithFx` y `TextareaWithFx`

Envuelven cualquier input/textarea con el botón `fx` adyacente. La inserción **preserva la posición del cursor** (split en `selectionStart..selectionEnd`, splice de la expresión, focus + setSelectionRange tras el evento).

#### Inputs envueltos (7)

| Panel | Campo | Tipo |
|---|---|---|
| `HTTPSamplerEditPanel` | Dominio | InputWithFx |
| `HTTPSamplerEditPanel` | Path | InputWithFx |
| `HTTPSamplerEditPanel` | Body raw | TextareaWithFx |
| `HeaderManagerEdit` | Valor del header (cada fila) | InputWithFx |
| `FormParamsEditor` | Valor del param (cada fila) | InputWithFx |
| `RegexExtractorEdit` | Template | InputWithFx |
| `RegexExtractorEdit` | Default | InputWithFx |
| `UDVsEditPanel` | Valor de variable (cada fila) | InputWithFx |
| `CSVDataSetEditPanel` | Filename del CSV | InputWithFx |

Match number del RegexExtractor queda como `<input>` normal (suele ser un literal `1`, no requiere función).

## Adaptaciones del prompt original

1. **Inputs en grids 12-col envueltos en `<div className="col-span-N">`** — el snippet directo de `InputWithFx` no soportaba `col-span-N` en su raíz. Solución: meto `InputWithFx` dentro de un `<div className="col-span-N">` y al wrapper le doy `className="flex-1 ..."` para que ocupe todo el ancho del div. Aplica a HeaderManager, FormParams, UDVs.
2. **`InputWithFx.disabled` añadido** como prop opcional — no estaba en el snippet pero tsc lo pedía para ciertos usos.
3. **`InputWithFx`/`TextareaWithFx` no spread genérico** (`...rest`) — el snippet original lo permitía pero generaba conflictos de tipo con `onChange`. Simplifiqué a props explícitas (`value`, `onChange`, `placeholder`, `className`, `disabled`).
4. **`FN_CATEGORIES` calculado a nivel módulo** (no dentro del componente) — el snippet lo calculaba en cada render. Mover fuera mejora performance (mínima) y simplifica el código.
5. **Indicador "Máx. 5 MB" añadido junto al botón "Adjuntar archivo"** con separador `·` antes de "Ctrl+Enter para enviar" para mantener layout limpio.

## Validaciones

- ✅ `npx tsc --noEmit` → EXIT=0, sin warnings.
- ✅ Backend: cambio aislado a constante, no requiere tests.
- ⏳ Validación visual: pendiente Fredy.

## Cómo validar visualmente

1. **Límite 5MB**: ir al chat (`/ai-script-designer`), el indicador "Máx. 5 MB" debe aparecer junto al botón "Adjuntar archivo". Intentar subir un archivo de 2-3 MB (antes rechazado) → debe pasar.
2. **Function Helper**:
   - Abrir Editor IA con un diseño con JMX.
   - Seleccionar un Sampler → ver botón `fx` junto a Dominio, Path, y Body raw.
   - Click `fx` → dropdown con tabs Aleatorios/Fechas/Contadores/Hilos/Variables/Strings.
   - Elegir `__time` → seleccionar formato `yyyy-MM-dd HH:mm:ss` → Insertar → debe quedar `${__time(yyyy-MM-dd HH:mm:ss)}` en el campo en la posición del cursor.
   - Probar también en `Header value` (cada fila), `UDV value`, `CSV filename`, `Regex template`/`default`.

## Pendientes derivados

- **HF4**: integración Editor IA ↔ Chat (botón "Pedir a IA" desde el editor).
- **Futuro opcional**: añadir `__BeanShell`/`__groovy` al catálogo (scripts inline). Por ahora omitidos porque su uso requiere conocimiento avanzado y riesgo de errores.
- **Futuro opcional**: añadir `fx` a campos de TestPlan comments, ResponseAssertion test_strings, JsonExtractor json_path. Por ahora sólo los 7 más usados.

## Estado

**LISTO para HF4.** Límite ampliado a 5 MB end-to-end, Function Helper con 25 funciones operativo en los 7 inputs más usados del Editor IA. Sin rebuild Docker — Vite HMR ya tomó los cambios; backend con `--reload` también.
