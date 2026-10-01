Pendiente de validación visual de Fredy
Commit base `5c3a46c` · 1 de octubre de 2026 · Bloque 3, paso 3.5 — la pantalla de la caja única

# La pantalla de la caja única del integrado

La aplicación estaba cerrada (regla 31). **No se tocó ningún protegido** (`Dashboard.tsx` incluido) **ni
la rama web**. El texto de las pruebas es todo ZZTEST, en la base de pruebas.

---

## 1. Qué cambió

### `ConsolidatedAnalysisSection.tsx`

- **Con `unico`:** el título es «Conclusiones y Recomendaciones» y debajo van **dos cajas a lo ancho**,
  «Conclusiones» y, debajo, «Recomendaciones». No sale el rótulo crudo «unico» ni «Prueba de
  Carga/Estrés». Mismo autoguardado (`onDraftChange` + `onEdit`) y misma copia local que siempre: la
  caja única es una clave más del consolidado.
- **Sin `unico`** (los no regenerados, D3): el mismo código de antes, sin cambios. Solo se saltan las
  claves que empiezan por `_`.
- **Versión anterior (D2):** si el integrado tiene `_legado`, debajo va un `<details>` plegado,
  «Versión anterior (solo lectura)». Por tipo de prueba muestra la fecha, la marca «editada a mano» y los
  textos en bloques de texto seleccionable, sin cajas de edición.
- **Error al generar (502):** se ve un aviso rojo arriba (`role="alert"`) con el motivo. Las cajas no se
  tocan. Antes, el error salía al pie, debajo de todo.
- **F5 sin cambios:** con ediciones, «Regenerar» pide la misma confirmación.
- El texto de «Se generarán análisis separados para Carga y Estrés» pasa a «Se generará un solo análisis
  para todas las pruebas».

### `IntegratedReportPage.tsx`

- **Deja de usar `data.unified_conclusions`.**
- El aplanador entiende `unico` (mismo formato que `_flatten_consolidated`) y salta `_legado`. Las dos
  copias que tenía repetidas dentro del archivo pasan a usar la misma función.
- Guarda `consolidado_anterior` del GET y `__consolidado_anterior` de la generación, y se lo pasa al
  componente.

### Backend (`integrated_report.py`)

- La respuesta de `generate-consolidated` lleva `__consolidado_anterior`, para enseñar la versión
  anterior sin recargar.
- **Sin IA configurada** (el caso del 8002), crear el analizador lanzaba fuera del `try` y daba un **500
  mudo**. Ahora es un 502 con su motivo, como cualquier otro fallo de la IA, y tampoco se guarda nada.

---

## 2. El corte de R1.1, resuelto (corrige el 138)

En la regresión, R1.1 volvió a cortarse con `Server disconnected`, **con el 8002 recién arrancado y sin
`--reload`**. Eso descarta la hipótesis del 138.

- **Lo que se vio en el log del 8002:** en las vueltas que fallan, la exportación del HTML responde 200 y
  **la del PDF no llega a registrarse**. Las dos van por la misma conexión (mismo puerto de cliente). En las
  que pasan, las dos se registran por el mismo puerto.
- **La causa:** el 8001 corre con `--timeout-keep-alive 300` y el 8002 con el valor por defecto de uvicorn,
  5 s. El servidor cerraba la conexión entre las dos exportaciones.

| 8002 | Vueltas de R1.1 sola | Cortes |
|---|---|---|
| keep-alive por defecto (5 s) | 5 | **3** |
| `--timeout-keep-alive 300`, como el 8001 | 4 | **0** |

**Arreglo:** `--timeout-keep-alive 300` en `reiniciar_8002.sh` y en `scripts/preparar_base_de_pruebas.sh`.
Es de las pruebas, no del producto: el 8001 y producción ya lo llevaban.

---

## 3. Suites

| Suite | Resultado |
|---|---|
| `pantalla_conclusion_unica.py` (nueva, Playwright, 8002 recién reiniciado) | **TODO PASA, 27 comprobaciones**: con `unico`, dos cajas a lo ancho y sin rótulos crudos; legado plegado, de solo lectura, seleccionable, con fecha y marca de edición; editar → «Guardado» → la base lo tiene con el legado intacto → recargar y sigue; regenerar sin IA → confirmación F5 → aviso con motivo, cajas y base intactas; sin `unico`, las cuatro cajas de siempre |
| `conclusion_unica.py` (A + B) | **TODO PASA** |
| `cierre_r1.sh` (R1.1-R1.4, C2 integrado, C2 individual) | **TODO PASA** |
| TypeScript (`tsc --noEmit`) | 0 errores |

Los dos integrados que siembra la suite, «ZZTEST-B3 unico» y «ZZTEST-B3 por tipo», quedan en la base de
pruebas: se crean o se actualizan por nombre y nunca se borran (reglas 28 y 29).

## 4. Lo que no se comprobó

- **La pantalla con un integrado real y la mirada de Fredy** (regla 9). Los pasos van en el mensaje de
  cierre.
- **El 502 con la IA configurada pero caída** en pantalla. Se comprobó sin IA (8002) y, en el backend, con
  un sustituto que no responde (142).
