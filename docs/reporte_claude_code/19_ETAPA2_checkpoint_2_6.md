52fc170 · 2026-09-16

# ETAPA 2 — PUNTO DE CONTROL tras 2.6b

**Para qué sirve este archivo.** Basta él solo para retomar la Etapa 2 en una sesión nueva,
sin el historial de conversación. Si algo aquí contradice
`docs/ESPECIFICACION-informe.md` (v1.2), manda la especificación.

**Estado del repositorio:** rama `backup-trabajo-local`, remoto `github` (único destino de
push), último commit **`52fc170`**, empujado. `tsc --noEmit` exit 0.
**Presupuesto de IA de la etapa: 1 / 50 llamadas reales.**

---

## 1. Sub-pasos cerrados

| Paso | Commit | Qué dejó hecho |
|---|---|---|
| 2.1 | `8db8c65` | Diagnóstico read-only completo (reporte 13). Lista cerrada de 4 protegidos. PARADA PREVISTA, autorizada por Fredy |
| 2.2 | `776412f` + `b7930d3` | `reasoning_effort` configurable (D13) y D14. Columna nueva en `ai_config` |
| 2.3 | `0e6c80b` | Throughput Over Time fuera del backend y de la IA (D19): 11→10 llamadas, serie vacía |
| 2.4 | `3bc8733` | Informe por transacción de 8 a 6 secciones (D20). `SECTIONS_GENERADAS` (6) junto a `SECTIONS` (8) |
| 2.5 | `5c7f8fa` | Datos por alcance verificados (ya existían: no se añade endpoint agregador) + fuga de overrides en los prompts agregadores corregida |
| 2.6a | `0572b30` | **Extracción pura** del cuerpo del informe a `ReportBody.tsx` (C1 paso 1). `Dashboard.tsx` 1.317→1.053 líneas. Equivalencia demostrada al 0,000 % |
| — | (reporte 18) | PARADA por C3: el diff real en `Dashboard.tsx` (300) superó la estimación (~120-160) por no haber contado los 3 helpers. Fredy eligió continuar |
| 2.6b | `52fc170` | D19 y D18 en pantalla; informe por transacción sin acordeón, 6 secciones, títulos D16, textos D22 |

Reportes 13 a 18 en `docs/reporte_claude_code/`. Reglas 19 y 20 de CLAUDE.md: los reportes van
**solo** ahí, numerados consecutivos, con hash y fecha en la primera línea.

---

## 2. Decisiones D13–D26: dónde están

| Dec. | Qué pide | Estado | Dónde |
|---|---|---|---|
| D13 | `reasoning_effort` configurable (b: columna · c: clave del singleton · d: probarlo · e: telemetría) | **Hecha** | `db/models/ai_config.py`, `schemas/ai_config.py`, `endpoints/ai_config.py`, `services/ai/gemini.py`, `AIConfigPage.tsx` |
| D14 | Acompañante de D13 (ver reporte 14) | **Hecha** | ídem |
| D15 | Las 5 gráficas por transacción | **Ya estaba** | `services/jtl/transaction_series.py:CHART_TYPES` |
| D16 | El título del bloque es el nombre exacto de la transacción | **Hecha en pantalla** | `TransactionReportSection.tsx`. Falta en PDF/HTML/integrado |
| D17 | Orden: general → transacciones → conclusiones al final | **PENDIENTE en las 4 salidas** | `report_generator.py:1052-1057` 🔒, `export_html.py` 🔒, `integrated_report.py`, `Dashboard.tsx` 🔒 |
| D18 | Active Threads solo en el informe general | **Hecha en pantalla** | `ReportBody.tsx` (`esGeneral`) |
| D19 | Throughput Over Time fuera del producto (la **gráfica**, no el escalar req/s) | Backend y pantalla **hechas**; falta PDF, HTML e integrado | `analysis_pipeline.py`, `upload.py`, `ReportBody.tsx` · pendientes `export_pdf.py` 🔒, `report_generator.py` 🔒, `export_html.py` 🔒, `integrated_report.py`, `ExecutionReportSection.tsx`, `chartConfig.ts` |
| D20 | 6 secciones por transacción, no 8 | **Hecha** (backend 2.4, pantalla 2.6b) | `transaction_report.py`, `transaction_chart_analysis.py`, `TransactionReportSection.tsx` |
| D21 | Un solo render parametrizado por alcance, no una plantilla paralela | **A medias**: `ReportBody.tsx` existe y acepta `scope`, pero nadie lo llama todavía con alcance de transacción | pendiente pantalla (ajuste §3.3), PDF, HTML |
| D22 | La palabra "mini-informe" no se ve en el producto | **Hecha en pantalla** | `TransactionReportSection.tsx`. Faltan `export_html.py` 🔒 y `_SIN_TEXTO` / `report_generator.py:240,259` 🔒. Identificadores (`txreport_*`, `transaction_chart_analyses`) se conservan |
| D23 | Overrides de secciones retiradas: ignorar, **no borrar** | **Hecha** en los prompts agregadores (2.5) | `_SECCION_LABEL` en los agregadores. Falta al renderizar el integrado |
| D24 | Página nueva por transacción en el PDF | **PENDIENTE** | `report_generator.py` 🔒 (2.7) |
| D25 | No se tocan los textos de los prompts | Vigente. Única excepción razonada: reporte 17 §3 (encabezados numerados vacíos) | — |
| D26 | Retrocompatibilidad probada contra datos reales | Aplicada en cada paso | reportes 16 §3.2, 17 §3.4 |

🔒 = archivo protegido (CLAUDE.md §11). Los 4 de esta etapa están **autorizados** por Fredy:
`Dashboard.tsx`, `report_generator.py`, `export_pdf.py`, `export_html.py`. Ningún otro.

---

## 3. Qué falta para cerrar 2.6

> **AL DÍA (`adeebcc`): los tres ajustes de esta sección están hechos**, más D17 en
> pantalla. El detalle y las mediciones, en el **reporte 20**. Lo que sigue pendiente
> se lista en el §5 de ese reporte. Se conserva el enunciado original para que se vea
> qué se pidió.

Ajustes pedidos por Fredy después de 2.6b:

1. **Quitar el encabezado de grupo «Informe por Transaccion».** Tras el informe general, cada
   bloque empieza directamente con el label como título (§0 y §1 de la especificación).
   Revisar que el texto visible que se toque lleve tilde («Transacción», «Análisis»).
2. **Carga en SERIE, no en paralelo.** Hoy `TransactionReportSection` dispara `cargar(label)`
   para todos los labels a la vez. Debe ir una transacción tras otra. En el backend, envolver
   el cálculo de series de `/transaction-charts` (y el parseo que dispare) en
   `asyncio.to_thread` — el mismo patrón de D1/Etapa 1 (`b3cd3d1`). Solo archivos **no**
   protegidos: si el parseo vive en `jtl_parser.py` se envuelve la llamada, no el parser.
   **Medición exigida:** tiempo de carga de los 3 bloques de `ff186cc7` y de la ejecución
   Coomeva (`115346ea…`, 1 transacción, 1.800 s) y, durante esa carga, sonda a `/auth/me`
   con **máximo < 100 ms**.
3. **C2 en `ReportBody` con alcance de transacción.** La edición y el autoguardado de cada
   análisis en alcance transacción van al canal de `transaction_chart_analyses`; en alcance
   general, al canal actual. Hooks antes de cualquier return temprano (regla 16).
   Se valida con la prueba de cableado de Playwright.

Después: **referencia a mano en 26** (ver §5) → capturar → si no da 26, **investigar, no
ajustar** → encadenar 2.7 a 2.12.

### Plan previsto 2.7–2.12 (reporte 15, ajustable)

| Paso | Alcance |
|---|---|
| 2.7 | PDF: `export_pdf.py` 🔒 + `report_generator.py` 🔒 (D19, D17, D21, D24, D22) |
| 2.8 | HTML individual: `export_html.py` 🔒 |
| 2.9 | Integrado: `integrated_report.py` + `ExecutionReportSection.tsx` (D23 al renderizar) |
| 2.10 | Medición del tiempo de generación (dato para la Etapa 4) |
| 2.11 | Verificación de punta a punta con la herramienta E2E |
| 2.12 | Cierre de etapa |

---

## 4. Condiciones vigentes (C1–C4)

El texto canónico vive en el prompt de etapa de Fredy. Así las estoy aplicando:

- **C1 — Refactor en dos pasos.** Primero extracción **pura** (sin cambio de orden, contenido
  ni estilos) y se demuestra equivalencia; los cambios funcionales van en un commit aparte.
  Así se hizo 2.6a → 2.6b.
- **C2 — Cableado probado.** Un control que se mueve debe seguir guardando en su canal
  correcto, y se demuestra con la prueba de cableado de Playwright, no leyendo el código.
- **C3 — Freno por tamaño del diff, midiendo *cambios reales*.** Una línea eliminada de un
  archivo protegido que aparece literalmente en el archivo destino es un **movimiento**, no un
  cambio, siempre que la equivalencia esté demostrada. Herramienta: `medir_c3.py`. Umbral que
  se venía usando: estimación + 50 %. Tras el reporte 18, las estimaciones de los tres
  protegidos que faltan suben un 60 %: `report_generator.py` 240-320 · `export_html.py`
  190-260 · `export_pdf.py` 50-65.
- **C4 — Presupuesto de IA.** Máximo 50 llamadas reales en la etapa; cada reporte declara las
  suyas. Consumidas: **1** (la de `POST /ai-config/test`, autorizada, en 2.2).

Además: ruta única de reportes (`docs/reporte_claude_code/`) y **alcance solo Etapa 2** —
nada de la 1, la 3 o la 4 se toca de paso.

---

## 5. Herramienta E2E (Playwright dentro del contenedor)

**Por qué así:** el equipo no tiene node ni python; `jmeter_backend` sí tiene python y
Chromium. El navegador corre dentro del contenedor y un relé TCP hace que el frontend se vea
como `http://localhost:5173`, que es el origen que el backend admite por CORS.

Fuente de los scripts: `C:\proyectos\Kinetix_pruebas\e2e\` (fuera del repo a propósito: en el
repo solo van reportes).

    # 1. copiar los scripts al contenedor
    docker cp C:/proyectos/Kinetix_pruebas/e2e jmeter_backend:/tmp/e2e

    # 2. rele 5173 (proceso de fondo dentro del backend; NO toca contenedores ni configuracion)
    docker exec -d jmeter_backend python3 /tmp/e2e/rele_5173.py
    #    comprobar que esta arriba (0 = si):
    docker exec jmeter_backend python3 -c "import socket;print(socket.socket().connect_ex(('127.0.0.1',5173)))"

    # 3. capturar y comparar
    docker exec -e KX_PWD=sqa2024 jmeter_backend python3 /tmp/e2e/captura_informe.py capturar antes ff186cc7-5be0-4a59-957c-e6b6b0fa00f8
    docker exec jmeter_backend python3 /tmp/e2e/captura_informe.py comparar antes despues

- **Sesión reutilizada.** `/tmp/e2e_sesion.json` guarda las cookies. `POST /auth/login` está
  limitado a **5 por 15 minutos y por IP, y cuenta también los logins correctos**: por eso la
  regla es **un** intento y, si falla, error — nunca un bucle de reintentos.
- **Referencia de gráficas.** `/tmp/e2e_salida/referencia_graficas.json` guarda cuántos
  `svg.recharts-surface` debe traer cada ejecución; si una corrida trae menos, la página no
  cargó entera y la captura se descarta. Hoy contiene `{"ff186cc7": 12, "baseline2": 12}`,
  que es el valor **anterior** a 2.6b.
  **Tras los ajustes de §3 hay que fijarla a mano en 26** para `ff186cc7`
  (11 generales = 12 − Throughput, más 5 × 3 transacciones). Si la captura no da 26,
  **se investiga; no se ajusta el número**.
- **Qué compara:** DOM normalizado (ids de recharts y decimales neutralizados), píxeles de un
  PNG de página completa (umbral 1 %; ruido de base medido 0,000-0,348 %) y la lista de
  llamadas de datos (`/auth/*` excluidas).
- **Estado actual en el contenedor:** relé **arriba**, sesión viva, y las capturas `antes`,
  `calibracion` y `despues` de 2.6a en `/tmp/e2e_salida/`. `rele_5173.py` **no** está en
  `/tmp/e2e`: hay que volver a copiarlo si se reinicia el contenedor.

---

## 6. Deuda y avisos abiertos

| Qué | Dónde | Nota |
|---|---|---|
| **`ALTER TABLE` de `reasoning_effort`** | `docs/sql/etapa2_reasoning_effort.sql` | Idempotente. **Hay que ejecutarlo al desplegar**: `create_all` no altera tablas existentes y sin la columna todos los informes salen con texto de `FallbackAnalyzer` **sin aviso** (reporte 14, corrección `b7930d3`). Verificación posterior: `GET /ai-config` 200 con `reasoning_effort` |
| **HF-3 (rate limit)** | `docs/reporte_claude_code/HF-3_deuda.md` | Deuda registrada, fuera del alcance de la Etapa 2 |
| `throughputData` y `analysisThroughput` siguen viajando en el `ctx` | `Dashboard.tsx` 🔒 → `ReportBody.tsx` | Deliberado: quitarlos es diff en protegido y se hará en el paso que ya toque `Dashboard.tsx` |
| `ai_analysis_response_time_over_time` | `analysis_pipeline.py:46` | Campo legado que ya no se genera pero **existe como override** en base. No es de esta etapa; se anota para no confundirlo con Throughput |
| `SECTIONS` (8) se conserva junto a `SECTIONS_GENERADAS` (6) | `transaction_chart_analysis.py` | A propósito: gobierna validación, edición y `sort_order` de las filas ya guardadas |

---

## 7. Protocolo si se acaba el contexto

Cerrar el sub-paso en curso, actualizar este checkpoint (o escribir el siguiente número),
`git commit` + `git push github backup-trabajo-local`, y detenerse indicando que se abra una
sesión nueva. Nada a medias sin commit.
