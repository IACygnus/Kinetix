# Cierre de limpieza — reportes recuperados, CLAUDE.md al día, imports muertos

**Fecha:** 2026-08-17
**Commit:** `8c7413a` — *Docs: recuperar reportes, actualizar CLAUDE.md y quitar
imports muertos*
**Push:** `github/backup-trabajo-local` (`25e023b..8c7413a`). **`origin` NO se
tocó.**
**Estado:** **COMPLETADO · CERO CAMBIOS FUNCIONALES VERIFICADOS**, con **una
entrega parcial que necesita tu decisión** (§4).

---

## 1. Los 5 reportes, recuperados

```
git restore docs/reporte_bug/{graf1-fix-serie-dual,graf1a-serie-ia,
            graf1b-pantalla,graf1c-exports,dperf1-fixes-bcd}.md
```

Verificado que están y con su tamaño íntegro:

| Reporte | Líneas |
|---|---|
| `graf1-fix-serie-dual.md` | 178 |
| `graf1a-serie-ia.md` | 137 |
| `graf1b-pantalla.md` | 118 |
| `graf1c-exports.md` | 250 |
| `dperf1-fixes-bcd.md` | 228 |

Coinciden exactamente con las cifras que reportaba el `git diff` del borrado, así
que la traza técnica de GRAF1 y DPERF-1 está completa. Tras el `restore` vuelven
a ser idénticos a HEAD, por eso **no generan cambio en el commit**: nunca
llegaron a salir del repositorio, solo del disco.

> Nota: quedaba un sexto borrado, `docs/reports/sprint-hf18b-max-tokens-unificado.md`.
> **Ese no lo toqué**: no está en tu lista y el archivo existe en
> `docs/reports/repo/`, o sea que fue un movimiento deliberado, no una pérdida.

---

## 2. `CLAUDE.md`: cuatro datos corregidos

| # | Línea | Antes | Ahora |
|---|---|---|---|
| a | 187 | `report_generator.py  # build_pdf_html / build_standalone_html` | `# build_pdf_html` |
| a | 489-490 | bloque describiendo `build_standalone_html(...)` como HTML responsivo | eliminado |
| b | 395 | «12 secciones IA + 2 … **en paralelo controlado**» | «**de forma secuencial** (12 pasos escritos a mano en `run_ai_and_verdict`, uno detrás de otro)» |
| c | 565 | `AIScriptDesigner.tsx` **(532 líneas)** | **(1.352 líneas)** |

El dato (c) lo verifiqué antes de escribirlo: `wc -l` da **1352**.

Solo correcciones de hechos. **No se tocó ninguna regla de desarrollo, no se
reescribió ninguna sección, no se añadió documentación nueva.**

---

## 3. Imports muertos eliminados

```python
-from app.config.chart_config import (
-    CHART_COLORS, HTTP_CODE_COLORS, TEST_TYPE_LABELS,
-    get_color_for_index, get_code_color,
-)
+from app.config.chart_config import get_color_for_index, get_code_color
```

Confirmado por conteo antes de borrar — los tres muertos aparecen **una sola
vez** (la propia línea del import), los dos vivos aparecen 2 y 3 veces:

```
CHART_COLORS: 1        get_color_for_index: 2
HTTP_CODE_COLORS: 1    get_code_color: 3
TEST_TYPE_LABELS: 1
```

Y descarté el riesgo real de este tipo de borrado —que alguien los reimporte
**desde** este módulo—: nadie lo hace. `export_html.py:29` los toma directamente
de `app.config.chart_config`, su fuente legítima, sin pasar por aquí.

---

## 4. Lo que NO pude entregar por git: `INFORME_PROYECTO_KINETIX.md`

Hice la corrección (d) —quitar `build_standalone_html(...)` de la línea 707— y
**el archivo en disco ya está corregido** (`grep` da 0 apariciones). Pero:

```
git ls-files INFORME_PROYECTO_KINETIX.md   ->  (vacío)
error: pathspec 'INFORME_PROYECTO_KINETIX.md' did not match any file(s) known to git
```

**Ese archivo no está versionado.** No es que se me olvidara commitearlo: no
está en el repositorio, así que la corrección vive **solo en tu máquina** y no
viaja en el push. Si quieres que quede en el repo hay que añadirlo con
`git add`, y eso es incorporar un documento nuevo al control de versiones —una
decisión tuya, no una corrección de datos—, así que no lo hice por mi cuenta.

---

## 5. Una frase que dejé sin tocar, a propósito

`CLAUDE.md:483`, justo encima del bloque que sí corregí:

> «construcción de HTML para **los dos exportadores (PDF y HTML standalone)**.»

Es la misma afirmación desactualizada que (a), solo que redactada de otra forma:
el módulo ya sirve a un solo exportador. **No la cambié** porque tu encargo decía
«SOLO estas correcciones» y esta no estaba en la lista.

El arreglo mínimo, si lo quieres, es una línea:

```
construcción de HTML para el exportador PDF.
```

Lo señalo porque tal como quedó, el párrafo introduce «dos exportadores» y
después describe uno solo.

---

## 6. Verificación de que nada cambió

Contra la línea base capturada antes de la limpieza:

| Métrica | Línea base | Ahora | |
|---|---|---|---|
| PDF individual | 8 págs | **8 págs** | idéntico ✔ |
| PDF integrado | 14 págs | **14 págs** | idéntico ✔ |
| HTML individual | 591.580 bytes | **591.580 bytes** | idéntico ✔ |

`py_compile` limpio · backend reiniciado **sin build** · `/docs` responde 200.

---

## 7. Archivos tocados

| Archivo | Qué | En git |
|---|---|---|
| `CLAUDE.md` | 4 correcciones de datos | sí (`8c7413a`) |
| `backend/app/services/export/report_generator.py` | −3 imports muertos | sí (`8c7413a`) |
| `INFORME_PROYECTO_KINETIX.md` | −1 línea | **no — archivo sin versionar** (§4) |
| 5 reportes de `docs/reporte_bug/` | recuperados del disco | sin cambio (ya coincidían con HEAD) |

Backup: `report_generator.py.bak_limpieza2_20260817_171727`.
