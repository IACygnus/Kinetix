21197e0 · 2026-09-16

# ETAPA 3 — CIERRE

**Llamadas reales a la IA en toda la etapa: 40 / 50.** Todas en 3.5: 28 de
`E3-estilo-pruebakinetix`, 10 de `E3-estilo-avianca` y 2 del informe integrado.
Los sub-pasos 3.1, 3.2, 3.3 y 3.4 consumieron **cero**, con stubs que cuentan y
con las dos puertas de salida reales saboteadas.

Rama `backup-trabajo-local`, todo empujado a `github`.

Este reporte sustituye al 25 como punto de entrada: para retomar basta este más
`docs/ESPECIFICACION-informe.md`.

---

## 1. Trazabilidad

| Sub-paso | Commit | Reporte | Llamadas |
|---|---|---|---|
| 3.1 Diagnóstico (read-only) | `9ed042e` | 30 | 0 |
| 3.2 Helpers deterministas | `533bade` | 31 | 0 |
| 3.3 Los diecinueve prompts | `9c2bacb` | 32 | 0 |
| 3.4 El aviso de estilo en pantalla | `441575b` | 33 | 0 |
| 3.5 Las corridas reales | `21197e0` | 34 | **40** |
| 3.6 Cierre | este | 35, 36 | 0 |

Punto de partida `6706591` (cierre de la Etapa 2) → punto de llegada `21197e0`.
**24 archivos, +2.521 / −468 líneas**, de las que 811 son el módulo nuevo y sus
pruebas, y 1.034 los cinco reportes.

| Archivo | Líneas |
|---|---|
| `backend/app/services/ai/estilo.py` *(nuevo)* | +480 |
| `backend/tests/test_estilo.py` *(nuevo)* | +331 |
| `backend/app/services/ai/gemini.py` | 551 tocadas |
| `backend/app/api/v1/endpoints/integrated_report.py` | 110 |
| `backend/app/api/v1/endpoints/analysis_ai.py` | 108 |
| `backend/app/services/ai/transaction_report.py` | 97 |
| `backend/app/api/v1/endpoints/compare.py` | 81 |
| `backend/app/services/ai/analysis_pipeline.py` | 40 |
| `frontend/src/components/dashboard/TransactionReportSection.tsx` | 39 |
| `frontend/src/components/common/AvisoEstilo.tsx` *(nuevo)* | +32 |
| `frontend/src/components/dashboard/ReportBody.tsx` | 16 |
| Los otros seis del frontend + `upload.py` + `schemas/test.py` | 61 |

**Ningún archivo protegido tocado.** `Dashboard.tsx`, `ScriptDesigner.tsx`,
`jtl_parser.py`, `virtual_user.py`, `report_generator.py`, `services/engine/`,
`export_html.py` y `export_pdf.py` están exactamente igual que en `6706591`.

---

## 2. Las once decisiones

| Dec. | Qué pedía | Estado | Dónde quedó |
|---|---|---|---|
| **D27** | Alcance: todos los textos de IA del informe y del integrado | **Hecha** — 19 prompts inventariados, los 19 tratados | reporte 30 §1 |
| **D28** | Un único bloque de estilo; se retiran las reglas dispersas | **Hecha** — `BLOQUE_ESTILO` (14 reglas) sustituye a `SYSTEM_PROMPT`, `STYLE_REMINDER`, `UX_RULE` y `FORMATO_NUMERICO` | `estilo.py` |
| **D29** | Vocabulario prohibido: tier, percentil suelto, variabilidad, dispersión, latencia crítica | **Hecha** — y además se sacó de los **datos** que ve el modelo (`=== TIER CRITICO ===` → `=== TIEMPOS MUY ALTOS ===`) | `gemini.py`, regla 1 del bloque |
| **D30** | Veredicto solo en conclusiones, recomendaciones y consolidado | **Hecha** — `permite_veredicto` en `_generate`; el resumen ya no pide «Listo para producción?» | regla 10 + `PERMISO_VEREDICTO` |
| **D31** | §4.3 como guía de tono, con prohibición de copiar | **Hecha y comprobada** donde se puede comprobar: en `E3-estilo-avianca`, 0 de 18 cifras y nombres del ejemplo | `REFERENCIA_ESTILO`, reporte 34 §3 |
| **D32** | Formato español desde el origen, con helper determinista | **Hecha** — `num`, `pct`, `ms`, `tiempo`, `veces`, `kbs` en los 32 prompts | `estilo.py` §1 |
| **D33** | Percentiles pre-traducidos en el bloque de datos | **Hecha** — `percentil_frase` en los 26 prompts que llevan percentiles | `estilo.py` §2 |
| **D34** | `SYSTEM_PROMPT` una sola vez por llamada | **Hecha** — lo pone `_generate` para los dos proveedores. −35,2 % de caracteres enviados y la caché del 7,8 % al 36,9 % | `gemini.py:_generate` |
| **D35** | `detectar_estilo` determinista tras sanitize, solo reporta | **Hecha** — 4 tipos, 6 endpoints de lectura, sin columna nueva en base | `estilo.py` §4 |
| **D36** | Aviso ámbar en pantalla, no en los exportados | **Hecha en transacciones, integrado, monitoreo, evidencias e imágenes.** **PENDIENTE en el informe general**: exige `Dashboard.tsx` | reporte 30 §3, reporte 33 §2 |
| **D37** | Trazabilidad de cifras y auditoría anti-texto-fijo, permanente | **Hecha** — 0 cifras de los informes escritas en código; 98,6 % y 97,8 % de cifras trazables, con las 10 restantes explicadas una a una | `estilo.py` §5, reportes 30 §4 y 34 §4 |

### Las cinco decisiones técnicas que tomé y declaro

| # | Decisión | Por qué |
|---|---|---|
| **T1** | El cierre «En producción, el usuario percibirá…» **no** es veredicto y nunca se marca | Lo exige la regla 11 del estilo y lo conserva D28. Marcarlo habría vuelto el detector inútil |
| **T2** | Punto con tres dígitos = miles a la española (`3.515`); con uno o dos = decimal inglés (`179.73`) | Determinista y sin falsos positivos en los 67 textos analizados |
| **T6** | El comparativo carga vs estrés **sí dictamina** | Es un informe completo con recomendaciones, no una sección de otro informe |
| **T11/T12** | `AnalysisBox` recibe `campo`; las secciones se leen por **ref**, no como dependencia | Sin la ref, React desmonta el textarea y se pierde el foco al escribir |
| **T15** | La tilde de «más» va en el helper de percentil | El modelo copia esa frase literalmente: lo que se escriba ahí es lo que lee el cliente |

Las demás (T3, T4, T5, T7-T10, T13, T14) están en los reportes 30 §6, 32 §8 y
33 §5.

---

## 3. El resultado, en una tabla

| Avisos del detector, por tipo | `E2-validacion` | `E3-estilo-pruebakinetix` |
|---|---|---|
| `formato_ingles` | 105 | **0** |
| `jerga` | 9 | **0** |
| `percentil_sin_traducir` | 9 | **0** |
| `veredicto_fuera_de_conclusiones` | 1 | **0** |
| **TOTAL** | **124** | **0** |

Mismo JTL, mismos criterios, mismas transacciones, mismo modelo, mismo
`reasoning_effort`. Lo único distinto son los prompts.

---

## 4. Lo que cuesta

| | `E2-validacion` | `E3-estilo-pruebakinetix` | |
|---|---|---|---|
| Llamadas por informe | 28 | 28 | igual |
| Caracteres enviados | 356.293 | **230.872** | −35,2 % |
| Tokens de prompt | 92.379 | **63.201** | −31,6 % |
| Cacheados | 7,8 % | **36,9 %** | ×4,7 |
| Texto visible por llamada | 226 | **263** | +16 % |
| **T2 − T0** | **141,0 s** | **159,0 s** | **+12,8 %** |

**El informe tarda 18 segundos más.** El prompt bajó un tercio pero el modelo
escribe más y tarda más en escribirlo. No era el objetivo de esta etapa y sigue
muy por debajo de los 354 s de la línea base de la Etapa 1; queda dicho para que
nadie se lo encuentre por sorpresa.

El **7,8 % de caché que el reporte 25 §5 dejaba para la Etapa 4 subió solo al
36,9 %** al enviar el bloque de estilo una vez y siempre igual.

---

## 5. Verificación

| Prueba | Resultado |
|---|---|
| `pytest tests/test_estilo.py` | **57 / 57** |
| `pytest tests/` (completo) | 467 pasan, 1 falla **anterior a esta etapa** (`37_HF-3_deuda.md` §6) |
| Prompts con stubs sobre `ff186cc7` | **32 construidos, 0 llamadas reales, 6 comprobaciones en verde** |
| `tsc --noEmit` del frontend | **0 errores** |
| Playwright `avisos_estilo.py` | **9 / 9** — el aviso aparece, se corrige, se guarda, se recarga y ya no está |
| `verificar_etapa2.py` sobre `E3-estilo-pruebakinetix` | **Las cuatro salidas pasan** |
| Telemetría de las corridas | **38 / 38 `outcome=ok`**, ninguna del `FallbackAnalyzer` |

---

## 6. Lo que queda abierto

### 6.1 Parada para Fredy — el aviso en el informe general

`D36` en el informe general necesita **~17 líneas en `Dashboard.tsx`**
(protegido). El diff está detallado en el reporte 30 §3 y **el endpoint ya
devuelve los `style_warnings`**: solo falta quién los pinte. Tres puntos, ninguna
gráfica, ningún cálculo, ningún guardado.

### 6.2 Fuera de alcance, anotado

- **Los títulos de gráfica de pantalla van sin tilde** («Response Times por
  Transaccion», «Codigos de Respuesta»). Se corrigen cuando se toquen esas
  pantallas en las Etapas 5 o 6; hacerlo ahora obligaría a tocar `Dashboard.tsx`
  por un motivo cosmético.
- **Los textos de las dos corridas nuevas llevan «espera mas de» sin tilde.** El
  helper ya está corregido; la próxima generación la lleva. No se regeneró:
  habría costado 40 llamadas por una tilde.
- **Los textos guardados de la Etapa 2 no cambian.** Siguen con su jerga y con
  su formato inglés, y por eso el aviso ámbar los marca. Se corrigen
  regenerándolos o editándolos a mano, que es justo lo que el aviso invita a
  hacer.

### 6.3 Pendiente de otras etapas (sin cambios respecto al reporte 25 §5)

Panel de selección (v1.2 §2) · control de capas avg/max (§3) · selector «qué
incluir» al exportar (§6) · la secuencialidad de las 28 llamadas.

---

## 7. Antes de desplegar

Lo del reporte 25 §6 **sigue vigente y no está hecho**:

1. **Ejecutar `docs/sql/etapa2_reasoning_effort.sql`** en la base del servidor.
   Sin esa columna, la primera lectura de `ai_config` revienta, el error se
   degrada a *warning* y **todos los informes salen con texto de
   `FallbackAnalyzer` sin aviso ninguno**.
2. Rebuild de los contenedores, que lo controla Fredy (regla 7). **La Etapa 3
   cambia backend y frontend: sin rebuild no se ve nada de esto.**
3. `reasoning_effort` queda en **`low`**, que es con lo que se midió todo.

La Etapa 3 **no añade ningún paso nuevo de despliegue**: no hay tablas ni
columnas nuevas.

---

## 8. Lo que falta de verdad

**La validación visual de Fredy** (regla 9). El guion está en el reporte 36.

**Estado: Etapa 3 implementada, pendiente validación de Fredy.**
