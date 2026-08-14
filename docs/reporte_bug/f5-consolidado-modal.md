# F5 — El consolidado lee las ediciones + modal de confirmación (cierre B2/B4)

**Fecha:** 2026-08-14
**Estado:** ✅ Implementado y validado con script determinista. **Pendiente: validación visual de Fredy** (criterio único de éxito).
**Alcance:** 2 archivos, **+45 / −3 líneas**. Presupuesto ~60-100 / máx 3 archivos. Dentro.
**Cierra:** B4 (punto 1) y B2 (punto 2) — **último pendiente de la emergencia original**.

| Archivo | + | − |
|---|---:|---:|
| `endpoints/integrated_report.py` | 9 | 2 |
| `components/integrated/ConsolidatedAnalysisSection.tsx` | 36 | 1 |

`py_compile` OK · `tsc --noEmit` **exit 0** · backend reiniciado sin build · backups `.bak_f5_20260814_111414`.

---

## 1. Punto (1) — El consolidado se redacta sobre el texto editado (B4)

El endpoint armaba el prompt con `execution.ai_conclusions` / `ai_recommendations`, es decir, **el texto original de la IA en `test_executions`**, ignorando lo que el usuario hubiera corregido en el informe.

Ahora usa la **misma fuente que los exports (F6)**, sin duplicar lógica:

```python
    # F5 (B4): el consolidado se redacta sobre el texto EDITADO por el usuario,
    # no sobre el original de la IA. Misma fuente que usan los exports (F6).
    overrides_by_exec = await _load_section_overrides(db, request.report_id)
...
            # F5 (B4): si el usuario corrigio el texto de esta seccion, la version
            # corregida es la que alimenta el prompt. Sin overrides, identico a antes.
            _ov = (overrides_by_exec.get(section.source_id) or {}).get("analysis") or {}
            executions_by_type[tt].append({
                ...
                "conclusions": _ov.get("ai_conclusions", execution.ai_conclusions) or "",
                "recommendations": _ov.get("ai_recommendations", execution.ai_recommendations) or "",
            })
```

Se reusa `_load_section_overrides` tal cual (lee de la DB, no del request — así funciona también al abrir el informe desde el historial). `request.report_id` llega por la sección `__meta` que el frontend ya enviaba (HF9.1).

**El veredicto como insumo (`:1752-1842`) NO se tocó** — decisión del CTO confirmada.

### Qué columnas honra, exactamente

El prompt del consolidado consume **`ai_conclusions` y `ai_recommendations`** por ejecución (más KPIs, veredicto, monitoreo y evidencias). Esas dos son las que ahora respetan el override.

Los análisis por gráfica (`ai_analysis_errors`, `ai_analysis_response_times`, …) **no eran ni son entrada del prompt consolidado** — ni antes ni después de F5. Si Fredy quiere que editar "Análisis - Errores" también influya en el consolidado, eso es ampliar el insumo del prompt: cambio aparte, no un bug de F5.

### Evidencia — script determinista sobre el endpoint REAL

Ejecuté `generate_consolidated_analysis` de verdad, con el analizador sustituido por un stub que captura el prompt. **0 llamadas al modelo — cuota intacta.**

Informe de prueba con un override conocido en `ai_conclusions`:

```
informe de prueba: 623a5d44-ba77-49b3-9e94-59f697925671

prompts capturados        : 1 (0 llamadas reales a la IA)
contiene el OVERRIDE      : True
contiene el texto ORIGINAL: False

--- fragmento del prompt ---
Conclusiones originales del reporte:
TEXTO CORREGIDO X — conclusiones editadas a mano por el usuario

Recomendaciones originales del reporte:
CRITICAS

La principal prioridad debe enfocarse en la optimización de Adapter VerifMethod, que reportó un tiempo prome…

limpieza: informe de prueba eliminado -> True
```

Dos cosas se prueban de una vez: **con** override entra el texto corregido y desaparece el original; **sin** override (las recomendaciones, que no edité) sigue entrando el texto original de la IA. El comportamiento previo se conserva cuando no hay ediciones.

**Limpieza:** informe de prueba borrado (`SELECT count(*) … LIKE 'F5-TEST%'` → **0**) y script eliminado del contenedor y del host.

---

## 2. Punto (2) — Modal de confirmación, Opción D (B2)

### El flag SÍ es fiable — no hizo falta la opción conservadora

El prompt contemplaba mostrar el modal siempre que existiera un consolidado previo, por si no había flag confiable. **Lo hay:** `consolidated_analysis[tipo].edited` es un booleano real en la DB. Verificado en el registro guardado:

```json
"load": { "edited": false, "conclusions": "…", "generated_at": "…", "recommendations": "…" }
```

Lo escribe la página padre en cada blur (`IntegratedReportPage.tsx:152`, `merged[tt] = {…fields, edited: true}`) y viaja al PATCH, así que **sobrevive a recargar el informe desde el historial**. El generado nuevo lo devuelve en `false`.

Por eso el modal es **preciso**: aparece solo si hay ediciones manuales de verdad, no cada vez que existe un consolidado. Menos fricción y sin falsos positivos.

```tsx
const hasManualEdits = Object.values(consolidatedAnalysis || {}).some((d: any) => d?.edited);
...
<button onClick={() => (hasManualEdits ? setConfirmOpen(true) : handleGenerate())} …>
```

### El modal

Copia del patrón de confirmación de `ClientsPage.tsx:439-460` (`fixed inset-0 bg-black/60` + tarjeta `max-w-md`, botón secundario de texto para Cancelar y rojo para la acción destructiva). Sin librerías nuevas.

- **Texto:** "El analisis consolidado tiene ediciones manuales. Regenerar las reemplazara por el texto nuevo de la IA. Esta accion no se puede deshacer. ¿Continuar?"
- **[Cancelar]** → `setConfirmOpen(false)`. No dispara nada más: no toca el estado, no llama al endpoint, no cancela el autosave.
- **[Regenerar y reemplazar]** → `handleGenerate()`, que cierra el modal y **sigue el flujo actual intacto**: el `onGenerated` del padre sigue cancelando el debounce en vuelo y limpiando `pendingEditsRef` (F3). No se tocó esa ruta.

### Regla 16

Los 4 hooks (`generating`, `error`, `confirmOpen`, `draft` + el `useEffect`) están en las líneas 36-45, **todos antes del early return** de la línea 83 (`if (!hasAnalysis)`). El nuevo `useState` se añadió junto a los existentes, no dentro de ninguna rama. El orden de hooks no cambia entre renders.

El modal solo se renderiza en la rama con consolidado (`hasAnalysis`), que es la única que tiene botón "Regenerar" — en la rama vacía el botón es "Generar Analisis Consolidado" y **nunca** hay nada que pisar.

---

## 3. Historial

```
$ git log --oneline -1
e16f257 F5: consolidado lee ediciones como insumo + modal de confirmacion (cierre B2/B4 — fin de la emergencia original)
```

Anteriores: `4ed0957` (UI-2) · `f069527` (GRAF1-C.2) · `fad4f01` (GRAF1-C) · `0aa43b6` (GRAF1-B) · `337b018` (GRAF1-A).

---

## 4. Validación visual para Fredy

**(a) B4 — la corrección llega al consolidado**
1. Abrir un informe integrado con al menos una ejecución.
2. Editar la caja de **Conclusiones** (o Recomendaciones) de una sección con un texto reconocible.
3. Esperar el "Guardado hh:mm" de la barra inferior.
4. Pulsar **Regenerar** en el consolidado → las conclusiones consolidadas nuevas deben reflejar la corrección (el prompt ya no ve el texto viejo).

**(b) B2 — el modal protege las ediciones**
1. Editar a mano el consolidado (cualquiera de las dos cajas) y esperar el guardado.
2. Pulsar **Regenerar** → **aparece el modal**.
3. **Cancelar** → todo intacto: el texto editado sigue ahí, no se llamó a la IA, el autoguardado sigue vivo.
4. Volver a pulsar Regenerar → **Regenerar y reemplazar** → se sustituye por el texto nuevo de la IA (y el flag vuelve a `edited: false`, así que un segundo Regenerar inmediato no pedirá confirmación).

**(c) Sin ediciones — sin fricción**
Generar un consolidado y pulsar Regenerar sin haber tocado las cajas → **no aparece modal**, regenera directo, como siempre.

---

## 5. Higiene

- `origin` (producción) **no se tocó**. Push únicamente a `github backup-trabajo-local`.
- **Ningún análisis IA ejecutado** — el analizador se sustituyó por un stub en la prueba. Cuota intacta.
- Sin `docker compose build`; `docker restart jmeter_backend` + HMR en el frontend. Backend `health=200`, frontend `200`.
- Datos de prueba limpiados: 0 informes `F5-TEST%` en DB; script borrado del contenedor y del host.

**Con F5 cierra la emergencia original: B2 y B4 quedan resueltos.**
