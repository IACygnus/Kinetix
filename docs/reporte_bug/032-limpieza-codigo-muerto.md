# Limpieza — `build_standalone_html` muerto + archivado de `.bak`

**Fecha:** 2026-08-17
**Commit:** `4f0be8c` — *Limpieza: eliminar build_standalone_html muerto +
archivar .bak antiguos*
**Push:** `github/backup-trabajo-local` (`6fba62f..4f0be8c`). **`origin` NO se
tocó.**
**Estado:** **COMPLETADO · CERO CAMBIOS FUNCIONALES VERIFICADOS.**

Sprint cosmético. Un solo archivo tocado en git (`report_generator.py`,
**305 líneas borradas, 0 añadidas**); el archivado de `.bak` es local y no entra
al repositorio.

---

## 1. `build_standalone_html`: confirmado muerto y eliminado

### 1.1 La verificación (tres ángulos, no uno)

| Búsqueda | Resultado |
|---|---|
| `grep -rn "build_standalone_html" backend/ --include=*.py` (sin `.bak`) | **1 sola línea: su propia definición** (`report_generator.py:950`) |
| Referencias dinámicas: `getattr(`, `importlib`, `__import__`, `globals()`, `eval(`, `exec(` en todo `backend/app` | ninguna apunta a esta función (los `getattr` que hay son acceso a atributos de objetos: `finish_reason`, `client_id`, `raw_xml`…) |
| El nombre como string / `standalone` en cualquier forma | solo docstrings y comentarios de **otras** funciones (`export_html.py:2,131,502`, `integrated_report.py:1320,1677`) |

Confirmado lo que ya anticipaban los reportes 022, 023 y 029: el export HTML
individual pasa por `_build_plotly_html()` en `export_html.py`, y las únicas
menciones vivas de `build_standalone_html` estaban en archivos `.bak`.

### 1.2 Qué se borró exactamente

Líneas **946-1249**: la cabecera de sección `# Standalone HTML builder
(browser-optimized, fully offline)` y la función completa. El archivo pasa de
**1.249 a 943 líneas**.

### 1.3 Huérfanos tras el borrado: ninguno

Extraje del cuerpo de la función todas las llamadas a helpers del propio módulo.
Usaba exactamente **uno**:

| Helper | ¿Queda huérfano? |
|---|---|
| `markdown_to_html` | **No.** Sigue usado en `transaction_analyses_html` (línea 242) y en `build_pdf_html` (línea 345) |

Y ningún import queda sin uso: comprobé símbolo por símbolo (`datetime`,
`ZoneInfo`, `base64`, `plt`, `io`, `re`, `Dict`, `List`, `Any`, `Optional`,
`get_color_for_index`, `get_code_color`) que todos siguen teniendo usos en el
código vivo.

### 1.4 Un hallazgo colateral que NO toqué

`CHART_COLORS`, `HTTP_CODE_COLORS` y `TEST_TYPE_LABELS` se importan en la
línea 18 y **tienen cero usos en todo el archivo** — ni en el código vivo ni en
la función borrada. Es decir: **ya estaban muertos antes de este sprint**, no
los dejó huérfanos mi cambio.

No los quité porque el encargo acotaba la limpieza a lo que quedara huérfano
*tras el borrado*, y estos tres son un caso aparte. Son 3 nombres en una línea
de import; si quieres, se van en un cambio de una línea.

---

## 2. Archivos `.bak`

### 2.1 El inventario real es casi el doble de lo estimado

El encargo hablaba de ~294; el conteo real:

```
.bak totales en backend/ y frontend/ : 546
archivos distintos que los generan   : 98
```

Los que más acumulan: `integrated_report.py` (38), `script_ai.py` (35),
`report_generator.py` (30), `export_html.py` (29), `AIScriptEditor.tsx` (27).

### 2.2 Movidos, no borrados

Política acordada aplicada — **los 3 más recientes por archivo se quedan**, el
resto se archiva:

```
se conservan (3 mas recientes por archivo) : 210
se mueven a backups/archive/               : 336
fallos                                     : 0
```

Comprobación de que no se perdió nada:

```
en el arbol: 210
en archive : 336
suma       : 546   (original: 546)
```

Dos detalles de la ejecución:

- **El criterio de "más reciente" es la fecha de modificación**, no el nombre:
  no todos los `.bak` llevan timestamp en el nombre (hay `.bak_roto`,
  `.bak_antes_cambio`…), así que ordenar por nombre habría conservado los
  equivocados.
- **Se replica la ruta relativa dentro de `backups/archive/`**
  (`backups/archive/backend/app/...`) porque hay nombres de archivo repetidos en
  carpetas distintas; aplanarlos habría hecho que unos pisaran a otros.

Ejemplo de lo conservado para `report_generator.py`:

```
report_generator.py.bak_limpieza_20260817_165755   (el de hoy)
report_generator.py.bak_n35_20260815_161754
report_generator.py.bak_n24_20260815_124909
```

### 2.3 `.gitignore`: ya estaba cubierto, no hizo falta añadir nada

```
.gitignore:207:backups/    backups/archive/prueba.py.bak_x
```

`git check-ignore -v` confirma que la regla `backups/` (línea 207) ya cubre
`backups/archive/`. Las reglas `*.bak` (118) y `*.bak_*` (163) cubren los que
siguen en el árbol.

---

## 3. Git: cero `.bak` trackeados

```
git ls-files | grep -ci '\.bak'   ->  0
```

**Nada que reportar aquí:** ningún `.bak` está ni estuvo en el índice, así que
no hay que limpiar historial. Tras el archivado, `git status` sigue sin ver ni
uno.

---

## 4. Verificación de que no cambió nada

Se generaron las salidas **antes** de tocar el archivo y **después** del borrado
y del archivado, con el mismo payload:

| Métrica | Antes | Después | |
|---|---|---|---|
| PDF individual | 8 págs | **8 págs** | idéntico ✔ |
| PDF integrado | 14 págs | **14 págs** | idéntico ✔ |
| HTML individual | 591.580 bytes | **591.580 bytes** | idéntico ✔ |

El HTML vuelve al **mismo número de bytes**, que es la comprobación fuerte: no
es que se parezca, es el mismo documento.

`py_compile` limpio · backend reiniciado **sin build** · `/docs` responde 200.

---

## 5. Archivos tocados

| Archivo | Qué | Backup |
|---|---|---|
| `backend/app/services/export/report_generator.py` | −305 líneas (`build_standalone_html` + su cabecera) | `.bak_limpieza_20260817_165755` |

El archivado de `.bak` no toca el repositorio: `backups/` está ignorado.

---

## 6. Dos cosas que quedan a tu criterio

1. **Los 3 imports muertos** de `chart_config` (`CHART_COLORS`,
   `HTTP_CODE_COLORS`, `TEST_TYPE_LABELS`) — ya estaban muertos antes, fuera del
   alcance de este sprint. Una línea si los quieres fuera.
2. **Sigue pendiente lo del reporte 031 §7:** los 5 reportes borrados del
   working tree que yo no toqué (`graf1-*`, `graf1a`, `graf1b`, `graf1c`,
   `dperf1-fixes-bcd`). Siguen sin commitear y siguen siendo recuperables con
   `git restore`. No los he tocado.
