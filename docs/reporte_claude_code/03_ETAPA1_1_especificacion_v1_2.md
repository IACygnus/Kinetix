a98edd9 · 2026-09-15

# ETAPA 1.1 — Especificación del informe v1.2

**Llamadas reales a la IA en este sub-paso: 0.**
Solo documento. Ningún archivo de código tocado.

Backup: `docs/ESPECIFICACION-informe.md.bak_etapa1_1.1_20260915_210712` (cubierto por `.gitignore`).

---

## Cambios aplicados

`git diff` da **19 inserciones, 3 eliminaciones** — exactamente los 6 cambios pedidos, ninguno más.

| # | Ubicación | Cambio |
|---|---|---|
| 1 | Línea 3 | `Versión 1.1` → **`Versión 1.2 · Aprobada por Fredy Bonilla`** |
| 2 | §2.1, tras "Se quitan P90 y Max. Se añade TPS." | Añadida la **definición de TPS**: muestras ÷ duración total de la prueba, alineada con `get_summary_table_data` |
| 3 | §6, al final | Añadido el **alcance del selector**: solo exports individuales; el integrado se evaluará después |
| 4 | §7 | Frase sustituida para remitir a la excepción de §6 |
| 5 | §8, fila "Validación" | Nuevo texto: Claude Code encadena los sub-pasos; Fredy valida **cada etapa completa** |
| 6 | Final del documento | Nueva sección **Historial de versiones** con las filas 1.1 y 1.2 |

### Las tres únicas líneas eliminadas

Las 3 eliminaciones del diff son las sustituciones de los cambios 1, 4 y 5 — no hay borrado
de contenido. El resto es adición pura.

---

## Nota sobre la definición de TPS

La definición que entra en §2.1 (muestras ÷ duración total de la prueba) queda anclada a
`get_summary_table_data`, que es la función que ya alimenta la tabla resumen del informe.
Con eso, panel e informe quedan obligados a mostrar el mismo número: si alguno divergiera,
sería un defecto contra la especificación, no una ambigüedad de la especificación.

Este sub-paso **no implementa** la columna TPS en el panel — solo fija su definición.

---

## Estado

Sub-paso 1.1 completado. Se continúa con 1.2 (preparación, read-only) sin pausa.
