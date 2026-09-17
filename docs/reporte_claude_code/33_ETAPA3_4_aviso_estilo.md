9c2bacb · 2026-09-16

# ETAPA 3.4 — El aviso de estilo en pantalla

**Llamadas reales a la IA en este sub-paso: 0.** El detector es determinista y no
llama a nada. **Ningún archivo protegido tocado.**

---

## 1. Qué se entregó

### Backend — D35 en los endpoints de lectura

| Endpoint | Qué devuelve ahora |
|---|---|
| `GET /executions/{id}` | `style_warnings: {columna: [términos]}` — solo las secciones marcadas |
| `GET /executions/{id}/transaction-report` | `style_warnings: [términos]` en cada sección |
| `GET /reports/integrated-reports/{id}` | `style_warnings: {sections: {...}, consolidated: {...}}` |
| `GET /executions/{id}/monitoring-analysis` | `style_warnings: [términos]` |
| `GET /executions/{id}/evidence-analysis` | `style_warnings: [términos]` |
| `GET /executions/{id}/image-analyses` | `style_warnings: [términos]` por imagen |

**Sin cambio de esquema**: no hay columna nueva ni `ALTER TABLE`. Los avisos se
calculan en cada lectura, así que **desaparecen solos** cuando el texto se
corrige y no hace falta invalidar nada.

`avisos_de_ejecucion(execution)` (en `estilo.py`) hace el barrido de las 13
columnas `ai_*` del informe general y omite las limpias: un informe sin
problemas devuelve `{}`.

### Frontend — D36 en pantalla

| Componente | Dónde aparece el aviso |
|---|---|
| `common/AvisoEstilo.tsx` *(nuevo, 32 líneas)* | La franja ámbar. Se pinta sola o no se pinta |
| `dashboard/TransactionReportSection.tsx` | Encima del resumen y de las 5 cajas de gráfica de cada transacción |
| `dashboard/ReportBody.tsx` | Pasa `campo` a `AnalysisBox` para que quien la pinte sepa de qué sección es |
| `integrated/ExecutionReportSection.tsx` | Encima de cada sección editable del integrado |
| `integrated/MonitoringReportSection.tsx` | Encima del análisis de cada imagen |
| `analysis/ImageAnalysisCard.tsx` | Encima del análisis de cada imagen (Monitoreo y Evidencias) |
| `pages/MonitoringPage.tsx`, `pages/EvidencePage.tsx` | Encima del análisis global |

El aviso dice **«Revisar estilo: dispersión, P99 sin traducir»** — los términos
concretos, no una queja genérica. Con más de seis se resumen («y 3 más»).
**Desaparece en cuanto se toca el texto**, sin esperar al guardado, y ya no
vuelve tras recargar si el texto quedó limpio.

**No sale en el PDF ni en el HTML exportados**: `AvisoEstilo` solo existe en los
componentes de pantalla. Los exportadores construyen su HTML en el backend y no
conocen este componente.

---

## 2. La parada de D36 sigue abierta

El **informe general** no pinta el aviso. Las once cajas del general viven en
`Dashboard.tsx`, que es un archivo protegido, y el diff mínimo son las ~17
líneas del reporte 30 §3. **El endpoint ya devuelve sus `style_warnings`**, así
que enchufarlo es solo el frontend.

Comprobado sobre `E2-validacion`:

```
GET /executions/59e25069-.../style_warnings
{
 "ai_analysis_summary": ["tier", "no deberia liberarse", "decimal con punto: 179.73", ...],
 "ai_analysis_response_times": ["tier", "P99 sin traducir", "unidad pegada: 108ms", ...],
 "ai_conclusions": [...], "ai_recommendations": [...]
}
```

Está calculado y viajando; solo falta quién lo pinte.

---

## 3. La prueba sobre la pantalla real

`avisos_estilo.py` con Playwright, sobre `E2-validacion` (textos de la Etapa 2,
con jerga), **9 de 9**:

```
backend: secciones con aviso en 6. Delete_Booking_Id -> {'summary': ['dispersion'],
                                                         'chart_response_times': ['dispersion']}
PASA  | el backend marca al menos una seccion de 6. Delete_Booking_Id
PASA  | el resumen de esa transaccion trae aviso de estilo
pantalla: 3 avisos ambar visibles
PASA  | se pintan al menos 2 avisos (hay 3)
  primero: Revisar estilo: variabilidad
PASA  | el aviso nombra el termino detectado
PASA  | hay secciones sin aviso (4): ['chart_latency', 'chart_error_rate',
                                      'chart_codes', 'chart_tps']
PASA  | se localiza la caja del resumen de la transaccion
PASA  | tras corregir el texto el backend ya no marca el resumen (devuelve [])
pantalla tras corregir y recargar: 2 avisos (antes 3)
PASA  | en pantalla queda al menos un aviso menos
restauracion del texto original: HTTP 200
PASA  | el texto original quedo restaurado

TODO EN VERDE
```

El tercer aviso de pantalla es de otra transacción: `5. Put_Update_Booking`
tiene «variabilidad» en su análisis de tiempos de respuesta. El detector marca
**solo** lo que tiene jerga: cuatro de las seis secciones de
`6. Delete_Booking_Id` no llevan aviso ninguno.

El ciclo completo queda demostrado: **el aviso aparece → se corrige el texto →
se guarda → se recarga → el aviso ya no está**. Y el texto original quedó
restaurado, incluida su marca `is_edited`, que la prueba había puesto en `true`
al escribir por el endpoint de edición.

---

## 4. Regresión

| Prueba | Resultado |
|---|---|
| `tsc --noEmit` del frontend completo | **0 errores** |
| `verificar_etapa2.py` — diez pasos, las cuatro salidas | **TODO PASA** |
| `pytest tests/test_estilo.py` | 57 en verde |

`verificar_etapa2.py` incluye el paso 9, el cableado C2 del integrado, que toca
las mismas cajas que ahora llevan aviso: ni la edición ni el guardado cambiaron.

---

## 5. Decisiones técnicas de este sub-paso

| # | Decisión | Por qué |
|---|---|---|
| T11 | `AnalysisBox` recibe un `campo` opcional desde `ReportBody` | La caja no sabía de qué sección era, y sin eso no puede buscar sus avisos. `Dashboard.tsx` no cambia: una función que ignora un prop opcional sigue siendo asignable al tipo |
| T12 | Las secciones se leen por **ref**, no como dependencia del `useCallback` | Si `AnalysisBox` cambiara de identidad al refrescarse los textos, React desmontaría el textarea y **se perdería el foco al escribir**. Ese era el motivo de las deps vacías originales y se respeta |
| T13 | Donde el usuario ya corrigió el texto (overrides del integrado, edición en curso de una imagen), el aviso **no se pinta** | El aviso describe el texto guardado en origen; sobre un texto que el usuario acaba de reescribir sería engañoso |
| T14 | El análisis **por imagen** también lleva aviso | Sale en el informe integrado como cualquier otro texto de IA (D27) |

---

## 6. Lo que este sub-paso NO hizo

- **Ningún texto se regeneró.** Eso es 3.5.
- **El informe general no pinta el aviso** — parada abierta (§2).

Siguiente: 3.5, las corridas reales de validación.
