b10de07 · 2026-09-17

# HF-4 + ETAPA 5 — CIERRE

**Llamadas reales a la IA: 22 / 50.** Todas de la corrida `E5-panel` (5.3).
HF-4, 5.1 y 5.2 consumieron **cero**.

Rama `backup-trabajo-local`, todo empujado a `github`.

---

## 1. Trazabilidad

| Sub-paso | Commit | Reporte | Llamadas |
|---|---|---|---|
| HF-4 — retiro del bloque por transacción crítica | `1046fd9` | 41 | 0 |
| 5.1 Diagnóstico del panel (read-only) | `729be9f` | 42 | 0 |
| 5.2 + 5.3 Implementación y validación | `b10de07` | 43 | **22** |
| 5.4 Cierre | este | 44, 45 | 0 |

Punto de partida `9a92de8` (cierre de la Etapa 3) → punto de llegada este
commit. **12 archivos**, de los que 4 son nuevos.

| Archivo | Cambio |
|---|---|
| `frontend/src/components/dashboard/UploadJTL.tsx` | 285 líneas tocadas |
| `backend/tests/fixtures/criticidad_casos.json` *(nuevo)* | +146 |
| `frontend/src/utils/criticidad.ts` *(nuevo)* | +122 |
| `backend/tests/test_criticidad_paridad.py` *(nuevo)* | +85 |
| `frontend/src/utils/criticidad.paridad.ts` *(nuevo)* | +80 |
| `backend/app/api/v1/endpoints/upload.py` | 30 |
| `backend/app/api/v1/endpoints/integrated_report.py` | 27 |
| `backend/app/services/export/report_generator.py` | 23 |
| `backend/app/api/v1/endpoints/export_html.py` | 19 |
| `backend/app/api/v1/endpoints/export_pdf.py` | 15 |
| `frontend/src/services/api.ts` | 2 |

### Archivos protegidos

| Archivo | Autorizado para | Tocado |
|---|---|---|
| `report_generator.py` | retirar el bloque (HF-4) | **sí**, 23 líneas |
| `export_html.py` | ídem | **sí**, 19 |
| `export_pdf.py` | ídem | **sí**, 15 |
| `Dashboard.tsx` | ídem | **no**: no pintaba el bloque |
| Los demás | — | no |

Los tres tocados están muy por debajo del límite de 40 líneas reales que fijaba
el plan.

---

## 2. Las ocho decisiones

| Dec. | Qué pedía | Estado |
|---|---|---|
| **D38** | Retirar el bloque «Análisis por Transacción Crítica» de las cuatro salidas, sin borrar filas | **Hecha.** PDF, HTML e integrado; en pantalla **nunca estuvo**. Las filas de `transaction_analyses` intactas |
| **D39** | Columnas Transacción · Muestras · Promedio · TPS · Errores | **Hecha.** El TPS es el `rendimiento` del propio informe, no un cálculo nuevo |
| **D40** | Fila desplegable con los tres criterios, varias abiertas a la vez, checkbox igual | **Hecha** |
| **D41** | Sin criterios propios se evalúan los globales; el global como marca de agua; «Usar globales» limpia | **Hecha** |
| **D42** | Criticidad al instante, misma regla que el backend, con paridad probada | **Hecha.** Solo existía en Python → portada a TS con 25 casos que corren los dos lados contra el mismo `esperado` |
| **D43** | Desaparece el bloque «Criterios por Transacción» | **Hecha** |
| **D44** | Los criterios viajan en `per_transaction`, sin cambio de esquema | **Hecha.** El payload es byte a byte el mismo |
| **D45** | Tildes y textos sin jerga en lo que se toque | **Hecha.** El motivo pasa a leerse como el informe |

### Las siete decisiones técnicas que tomé y declaro

| # | Decisión | Por qué |
|---|---|---|
| **T16** | `transaction_analyses_html` se conserva sin usar, documentada como retirada | Borrarla son 46 líneas en un protegido con autorización acotada a «retirar el bloque»; el presupuesto era 40 |
| **T17** | El nombre del bloque retirado no se escribe ni en los comentarios del HTML | La primera versión del comentario lo llevaba y el PDF **seguía conteniéndolo**. Misma lección que D22 con «mini-informe» |
| **T18** | Fuera el `useEffect` que resubía el JTL al cambiar un criterio global | Con criterios por fila sería una resubida por tecla |
| **T19** | El respaldo a `/extract-jtl-labels` deja de pintar panel | Una fila necesita sus métricas; sin ellas no hay fila. El endpoint nuevo es estrictamente más capaz |
| **T20** | La paridad de TS corre con `tsc` + `node`, sin runner de pruebas | Un runner son dependencias nuevas y una imagen nueva, por una prueba |
| **T21** | El panel dice por escrito que la concurrencia no mueve la marca | Es editable y se guarda, pero no entra en la regla. Mejor decirlo que dejar que se descubra |
| **T22** | Las gráficas esperadas se derivan del informe | Estaban clavadas en 3 transacciones |

---

## 3. Verificación

| Prueba | Resultado |
|---|---|
| `hf4_check.py` sobre `E3-estilo-pruebakinetix` | **24 / 24** |
| `hf4_check.py` sobre `E2-validacion` | **24 / 24** |
| Paridad de la regla, lado Python | **25 / 25** |
| Paridad de la regla, lado TypeScript | **25 / 25** |
| `panel_seleccion.py` (Playwright, sin generar nada) | **24 / 24** |
| `e5_verdictos.py` sobre la corrida real | **8 / 8** |
| Telemetría de `E5-panel` | **22 / 22 `outcome=ok`** |
| `tsc --noEmit` del frontend | **0 errores** |
| `pytest tests/` | **492 pasan**, 1 falla anterior (`37_HF-3_deuda.md` §6) |
| `verificar_etapa2.py` sobre `E5-panel` | **LAS CUATRO SALIDAS PASAN** |
| `verificar_etapa2.py` sobre `E3-estilo-pruebakinetix` | **LAS CUATRO SALIDAS PASAN** |

`verificar_etapa2.py` tiene ahora **once pasos**: el 10 es HF-4 sobre las cuatro
salidas.

---

## 4. Lo que hay que mirar con lupa

**La regla de criticidad vive ahora en dos lenguajes.** Es lo que pedía D42 y
está probada, pero es una duplicación real y hay que tratarla como tal:

- La fuente de verdad sigue siendo **Python** (`compute_per_transaction_verdicts`).
  El informe se calcula ahí; el TS solo decide qué se pinta en el panel.
- `criticidad_casos.json` es el contrato. **Si alguien cambia la regla en un solo
  lado, la paridad falla** — en Python con `pytest`, en TS con `node`.
- Si algún día se cambia el umbral del aviso (hoy el 80 %) o se añade una
  métrica, hay que tocar los dos y ampliar el fixture.

---

## 5. Lo que queda abierto

### 5.1 Fuera de alcance, anotado

- **`transaction_analyses_html` queda sin usar** (T16). Si al leer esto sigue
  igual, se puede retirar entera, son 46 líneas.
- **Los títulos de gráfica de pantalla van sin tilde** («Response Times por
  Transaccion»). Siguen pendientes de las Etapas 5/6 en las pantallas que las
  pintan; `Dashboard.tsx` no entraba en esta autorización.
- **El respaldo del panel** (T19): si `/extract-jtl-transactions` fallara, la
  pantalla se queda con los criterios generales y sin panel. No se ha visto
  fallar; queda dicho.

### 5.2 Pendiente de otras etapas (v1.2)

Control de capas avg/max (§3) · selector «qué incluir» al exportar (§6) · la
secuencialidad de las llamadas.

---

## 6. Antes de desplegar

Sin cambios respecto al reporte 35 §7: **ejecutar
`docs/sql/etapa2_reasoning_effort.sql`** en la base del servidor y rebuild
**allí**. La Etapa 5 **no añade ningún paso nuevo**: ni tablas, ni columnas, ni
cambios de esquema — `per_transaction` ya existía (D44).

En local **no hace falta rebuild**: basta Ctrl + Shift + R.

---

## 7. Lo que falta de verdad

**La validación visual de Fredy** (regla 9). El guion está en el reporte 45.

**Estado: Etapa 5 implementada, pendiente validación de Fredy.**
