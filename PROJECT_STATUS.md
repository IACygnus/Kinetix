# PROJECT_STATUS — SQA Kinetix Pro

> Estado vivo del proyecto. Complemento operativo de `CLAUDE.md` (que
> documenta el "qué existe"). Aquí se registra "dónde estamos y qué falta".

---

## ESTADO ACTUAL (2026-09-20)

- **Branch activa:** `backup-trabajo-local`. **Todo el producto vive ahí.** `main`
  sigue en su commit `Initial commit` y no contiene nada.
- **Último tag publicado:** `v4.1.0` — cierra el **módulo de horas** (H1 a H7).
  El `v4.0.0` cerró el plan de corrección del informe (Etapas 1 a 7).
- **Remoto de push:** `github` (`IACygnus/Kinetix`), el único. `azure` tiene el
  push bloqueado a propósito.
- **Árbol de trabajo:** limpio. Todo lo de las siete etapas está commiteado.
- **Ambiente local:** funcional. `docker compose up -d` levanta los cinco
  servicios (`jmeter_postgres`, `jmeter_backend`, `jmeter_frontend`,
  `jmeter_influxdb`, `jmeter_grafana`).
- **Producción (`kinetix.sqasa.co` @ 20.81.141.77):** sincronización
  **pendiente**. Checklist en `docs/reporte_claude_code/53_checklist_despliegue.md`, y su
  versión CORREGIDA —puertos, target del frontend, media y DEBUG— en
  `docs/reporte_claude_code/59_handoff_despliegue_analisis.md` §4.

### Plan de corrección del informe — Etapas 1 a 7

Referencia única: **`docs/ESPECIFICACION-informe.md` v1.3**. Todo cambio del
informe se valida contra ese documento.

| Etapa | Qué cubrió | Estado |
|---|---|---|
| 1 | Diagnóstico y preparación | validada |
| 2 | Estructura del informe (v1.2 §1): informe por transacción con el mismo diseño del general, sin conclusiones propias, sin Throughput Over Time | **validada por Fredy** |
| 3 | Estilo de los textos de IA (§4): bloque de estilo único en los 19 prompts, formato español determinista, detector de jerga | **validada por Fredy** |
| 5 | Panel de selección (§2): columnas Transacción · Muestras · Promedio · TPS · Errores, criterios desplegables por fila | **validada por Fredy** |
| 5b | Botón "Criterios" por fila (§2.2) y **la IA usa los criterios efectivos** de cada transacción: el texto y la tabla de veredictos ya no pueden contradecirse | implementada, **pendiente validación** |
| 6 | Gráficas, exportación y cierre (§3, §6, §7): control de capas, tooltip, selector de exportación, tildes | implementada, **pendiente validación** |
| 7 | **Informe integrado completo**: sus bloques por transacción en pantalla y overrides propios en los exportados | implementada, **pendiente validación** |

No hay Etapa 4: el plan saltó de la 3 a la 5.

### Módulo de horas — Etapas H1 a H7

Referencia única: **`docs/ESPECIFICACION-horas.md` v1.4**. Es un módulo aparte del
de análisis: comparte la tabla `clients`, el usuario y la sesión, y nada más.
**Cero llamadas a la IA en todo el módulo.**

| Etapa | Qué cubrió | Estado |
|---|---|---|
| H1 | Modelo de datos (7 tablas), Actividades y Proyectos | **validada por Fredy** |
| H2 | Registro de horas: jornada, extras, días incompletos, permisos | **validada por Fredy** |
| H2b | El registro pasa a **calendario mensual**; la vista semanal se retira; alertas de desfase en Proyectos | **validada por Fredy** |
| H3 | Consulta de proyectos (§5) e **importación del Excel** (§6), con vista previa e idempotencia por `Id` | **validada por Fredy** |
| H5 | **El informe**: ocho secciones, HTML autocontenido e interactivo, PDF y CSV | implementada, **pendiente validación** |
| H6 | Ajustes del veredicto: estados nuevos, renombrar, filtros de cerrados, informe a ocho secciones | implementada, **pendiente validación** |
| H7 | Portada aprobada, **base de pruebas separada**, documentación y cierre | implementada, **pendiente validación** |

No hay Etapa H4: el plan saltó de H3 a H5.

### Observabilidad — Etapas O1, O2a, O2b y O2c

| Etapa | Qué cubrió | Estado |
|---|---|---|
| O1.1 | **Diagnóstico de solo lectura**: la cadena InfluxDB → Grafana no había funcionado nunca. Reporte **96** | cerrada |
| O1 | La fuente de datos arreglada, los puertos cerrados a la red, token de solo escritura, la corrida como filtro y la pantalla **Monitoreo en vivo** | implementada, **pendiente validación** |
| O2a | El **laboratorio** (`docker-compose.lab.yml`) y el **monitoreo de infraestructura sin agente**: Linux por SSH, PostgreSQL por conexión, cubo `infra`, tablero propio y el documento de permisos para el cliente. Reportes **99** y **100** | implementada, **pendiente validación** |
| O2b | El **agente**: Telegraf dentro del servidor, **una lectura por segundo** en vez de una cada diez, con instalador y desinstalador de systemd, y el mismo esquema. Reportes **101** y **102** | implementada, **pendiente validación** |
| O2c | **«Observabilidad» como sección propia del menú** y la pantalla de **Servidores**: alta, prueba de conexión que dice *qué se puede leer* y el error real cuando falla, y generador de configuración. Reportes **103** y **104** | implementada, **pendiente validación** |

Las dos aceptaciones que O1 dejó colgando del reinicio de Fredy **pasan**: la
fuente de datos responde `OK` y el 8086 y el 3000 ya no contestan por la IP de
la red. Sigue sin probarse **desde otra máquina**.

De O2a, lo que hay que tener presente: las métricas sin agente se escriben con
**los mismos nombres de campo que usaría un agente** —comprobado campo a campo,
cero campos que tenga el nativo y no tengamos nosotros—. Y en el laboratorio
`cpu`, `mem` y `disk` son del anfitrión, no del contenedor, porque `/proc` no
está separado; en un servidor de verdad no hay esa ambigüedad (reporte 99 §2.3).

De O2b: **la promesa de O-D13 se cumplió de punta a punta.** El tablero tiene un
selector «Modo» y cambiarlo **no cambia ni una consulta**: las mismas nueve
medidas con los mismos campos, solo que a un dato por segundo en vez de uno cada
diez. Las cifras que se le dan a un cliente —96,3 % contra 25,9 % en un pico de
tres segundos; 0,5 % de un núcleo y ~60 MB de coste; 183 de 183 segundos
recuperados tras un corte de red— están todas medidas, no estimadas. **Lo único
escrito y sin probar es el instalador de Windows** (O-D21).

De O2c: los servidores observados se dan de alta desde la pantalla, con su
credencial **cifrada y que no vuelve a salir** (O-D26), y la prueba de conexión
**dice qué se puede leer** en vez de un «ok». Dos cosas que conviene tener
presentes: **«Metricas Monitoreo» sigue en Análisis** y su nombre se presta a
confusión con la sección nueva (reporte 103 §5), y **el punto de entrada HTTPS
que el modo con agente necesitaría para un servidor de un cliente no existe**
(reporte 103 §1) — el documento del cliente ya lo dice así.

Lo que O1, O2a, O2b y O2c **no** tocan, y por qué: el WebSocket de métricas del
motor propio (O-D7) y que el motor publique en InfluxDB. Las dos cosas caen en
`backend/app/services/engine/`, **carpeta protegida**, y la segunda añade una
dependencia. Van con **O3**, con autorización expresa.

### El `--build` del 22 de septiembre de 2026

Un `docker compose up -d --build backend` que pedí yo recreó el contenedor y se
llevó `/tmp/e2e`: cuarenta y tantas suites desde H1, los relevos de red y la
herramienta de sesión. Se recuperaron del respaldo de
`C:\proyectos\Kinetix_pruebas\e2e\` —**las 12 de la regresión, íntegras**— y
ahora viven en **`backend/pruebas_e2e/`**, versionadas. De ahí sale la **regla
36**: ninguna prueba vive solo dentro de un contenedor. Reporte **103** §0.

### El incidente del 18 de septiembre de 2026

Borré con `psql` las horas que Fredy acababa de importar y las estimaciones que
había tecleado, creyendo que eran residuo de mis pruebas. **No lo eran.**
Diagnóstico en el reporte **92**, recuperación en el **93**, y las seis reglas que
salieron de ahí en **CLAUDE.md §13.1 (28 a 33)**. La **34** es la que las hace
cumplibles: las suites corren contra la base de pruebas, no contra la suya.

Lo que queda de aquello, ya cerrado en H7.2: **las suites automáticas ya no corren
contra la base de Fredy.** Hay una base aparte, `jmeter_analyzer_test`, con su
propio backend en el puerto 8002; se prepara desde cero con
`scripts/preparar_base_de_pruebas.sh`.

Reportes de las siete etapas: `docs/reporte_claude_code/01…59`, numerados de
forma consecutiva, con hash de commit y fecha en la primera línea.

---

## MÓDULOS AÑADIDOS POR EL PLAN DE CORRECCIÓN

### Backend

| Módulo | Etapa | Qué |
|---|---|---|
| `services/ai/estilo.py` | 3 | formato español determinista, frases de percentil, el bloque de estilo único (`BLOQUE_ESTILO`, `PERMISO_VEREDICTO`, `REFERENCIA_ESTILO`) y los dos detectores (`detectar_estilo`, `trazar_cifras`). **Solo detectan y reportan**: no regeneran ni llaman a la IA |
| `services/ai/analysis_pipeline.py` | 2 | orquestación de las secciones del informe |
| `services/ai/transaction_analysis.py` · `transaction_report.py` | 2 | el informe por transacción |
| `services/jtl/transaction_series.py` | 2 | las 5 series de UNA transacción, calculadas en proceso desde el DataFrame ya parseado |
| `services/export/seleccion.py` | 6 | lee `?tx=` y `?capa=`, filtra y valida. Una definición para PDF y HTML |
| `services/export/capas_html.py` | 6 | CSS, JS, selector y visibilidad inicial del control de capas del HTML |
| `services/ai/criterios.py` | 5b | **la única** resolución del umbral efectivo de cada transacción: la usan los prompts **y** `compute_per_transaction_verdicts`, así que texto y tabla no pueden discrepar |
| `services/export/client_logo.py` | 2 | logo del cliente en la portada |
| `db/models/transaction_analysis.py` | — | transacciones marcadas como críticas (legacy de solo lectura desde N3.4) |
| `db/models/transaction_chart_analysis.py` | 2 | los textos del informe por transacción. `SECTIONS_GENERADAS` = summary + las 5 gráficas |

### Frontend

| Módulo | Etapa | Qué |
|---|---|---|
| `components/dashboard/ReportBody.tsx` | 2 | **el cuerpo del informe, parametrizado por alcance** (`general` o `transaction`). Es lo que hace cierta por construcción la frase "el informe por transacción es el general, filtrado" |
| `components/dashboard/SummaryTable.tsx` | 2 | la tabla resumen, parametrizada por alcance |
| `components/dashboard/TransactionReportSection.tsx` | 2 | los bloques por transacción y su generación/sondeo |
| `components/common/AvisoEstilo.tsx` | 3 | el aviso ámbar con los términos de jerga detectados |
| `hooks/useChartLayers.ts` | 6 | el control de capas promedio/máximo, en memoria de sesión |
| `components/dashboard/ExportScopeDialog.tsx` | 6 | el diálogo "¿qué incluyo en la exportación?" |
| `components/dashboard/TransactionReportSection.tsx` | 7 | además: canal de overrides del integrado (`tx\|<label>\|<section>`) |

### `reasoning_effort`

`ai_config.reasoning_effort` (`low` / `medium` / `high`, `NULL` = `low`) se
añadió en la Etapa 2 y **solo se envía a los modelos de OpenAI que lo
soportan**. El proyecto no usa Alembic: la columna se aplica con
`docs/sql/etapa2_reasoning_effort.sql`, que es idempotente.
**Aplicada en desarrollo. Pendiente en producción.**

---

## ESTRUCTURA DEL INFORME (v1.2 §1)

```
PORTADA
INFORME GENERAL
  Tabla resumen por transacción (todas) + su análisis
  Response Times · Latency · Error Rate · Response Codes · TPS · Active Threads
  (cada gráfica con su análisis)
[nombre de la transacción 1]        ← página nueva en el PDF
  Tabla resumen filtrada + su análisis
  Las mismas gráficas menos Active Threads (los hilos son de toda la prueba)
[nombre de la transacción 2]
  …
CONCLUSIONES Y RECOMENDACIONES      ← una sola vez, de toda la prueba
```

- **"Throughput Over Time" salió del producto entero.** El escalar
  `throughput` (req/s) del KPI y de la tabla resumen **no** se tocó.
- **No existe "mini-informe".** El título de cada informe por transacción es el
  nombre de la transacción, y nada más.
- **"Response Time Over Time"** (promedio agregado) también salió: la fuente de
  verdad es "Response Times por Transacción" con su serie dual promedio/máximo.
- El bloque **"Análisis por Transacción Crítica"** se retiró en el HF-4 de las
  cuatro salidas, y su función se borró en la Etapa 6.

---

## FEATURES COMPLETADAS

### Plataforma base
- [x] **Autenticación JWT por cookie httpOnly** — login, refresh, logout, me.
      Rate-limit 5/15min/IP. CSRF double-submit cookie. Sliding session 30 min.
      *(Ver HF-3 en pendientes: el límite no funciona como se espera en producción.)*
- [x] **Roles:** admin, analyst, viewer (`require_role` dependency).
- [x] **Gestión de usuarios** — CRUD + toggle + reset-password.
- [x] **Clientes y asignaciones** — Client/UserClient con FK.
- [x] **Dashboard home** — `/dashboard/stats`.
- [x] **Profile** — editar perfil, cambiar password.

### Performance Testing — análisis
- [x] **Upload JTL** — soporta CSV y XML (`_is_xml_jtl` + `_parse_xml_jtl_to_df`
      con depth=1 para evitar contar samples anidados).
- [x] **Multi-JTL upload** (jtl_filenames JSON).
- [x] **Test types:** load, stress, endurance, scalability, spike, smoke.
- [x] **Redirect separation** — labels 30x identificados y separados.
- [x] **Análisis IA del informe general** — Gemini u OpenAI, con
      `FallbackAnalyzer` ante 429.
- [x] **Informe por transacción** — 6 secciones (resumen + 5 gráficas), con el
      mismo diseño del general (Etapa 2).
- [x] **Estilo de los textos** — bloque único en los 19 prompts, formato español,
      aviso ámbar cuando el detector encuentra jerga (Etapa 3).
- [x] **Verdict + per-transaction verdicts** (KNX-09) vs acceptance criteria.
- [x] **Capacity analysis** (KNX-17).
- [x] **Edición manual del análisis IA** — con autoguardado, y cada alcance en su
      canal: el general en `test_executions`, el de transacción en
      `transaction_chart_analyses`, el integrado en sus `overrides`.
- [x] **Panel de selección** — Transacción · Muestras · Promedio · TPS · Errores,
      con los criterios de aceptación desplegables por fila y recálculo inmediato
      de la criticidad (Etapa 5).

### Reportes
- [x] **HTML standalone** con Plotly interactivo (offline-capable).
- [x] **PDF profesional con WeasyPrint + matplotlib** — cover full-bleed
      (`@page :first { margin: 0 }`), branding SQA, Indigo `#4f46e5`.
- [x] **Selector de exportación** — al exportar PDF o HTML, el sistema pregunta
      si incluir solo el general o también las transacciones que se marquen
      (Etapa 6; no aplica al integrado).
- [x] **Control de capas** promedio/máximo por gráfica, en pantalla, PDF y HTML
      (Etapa 6).
- [x] **Reporte comparativo** carga vs estrés con IA.
- [x] **Reporte integrado drag-and-drop** — fusiona secciones de múltiples
      reportes en uno. Persistido en `integrated_reports`.
- [x] **Análisis IA consolidado** del reporte integrado.

### Configuración de IA
- [x] **Provider switch** entre Gemini y OpenAI. **Modelo en uso: `gpt-5.5`**
      (decisión de Fredy; no se propone volver a modelos anteriores).
- [x] **`reasoning_effort`** configurable (Etapa 2).
- [x] **API key encriptada** con Fernet en `ai_config`.
- [x] **Modelos live** (`/ai-config/models/live`) con cache TTL 5 min y
      fallback hardcoded.
- [x] **Test connection** desde la UI sin guardar primero.
- [x] **Límites diarios/mensuales** con auto-reset y contadores.
- [x] **Diagnóstico** `/gemini-test`.

### AI Script Designer
- [x] **Generación de JMX desde prompt** (`POST /script-designer/ai/generate`).
- [x] **Refinamiento conversacional** (`POST /refine`) con historial.
- [x] **Upload de archivos** — Postman, OpenAPI/Swagger (JSON/YAML), texto.
- [x] **Persistencia de archivo de referencia** entre refinamientos.
- [x] **Validación estructural** del JMX + lista de componentes, y descarga `.jmx`.

### Script Designer original
- [x] **Editor visual** de requests con onboarding y drafts.
- [x] **Variable Manager** con scan, autocomplete, inline editor.
- [x] **Data Files** — upload CSV, columnas, mapping a variables.
- [x] **Importers:** HAR, Postman, OpenAPI, WSDL, Chrome push-pull.
- [x] **Smoke Test** + Request Runner + Run Result Panel.
- [x] **Ejecución con motor propio** (Stepping Thread Group + virtual users).

### Monitoreo

> Corregido en la Etapa O1. Lo que decía antes —«InfluxDB 2.7 como sink de
> métricas live del motor propio»— **no era cierto y no lo fue nunca**: el motor
> propio no escribe en InfluxDB, no existe el cliente ni el código que lo
> intente, y el cubo tenía cardinalidad 0. Diagnóstico en el reporte **96**.

- [x] **Grafana embebido** vía iframe (`GF_SECURITY_ALLOW_EMBEDDING=true`).
- [x] **InfluxDB 2.7**, cubo `jmeter`, retención 30 días. Lo alimenta el
      **Backend Listener de un JMeter**, no el motor propio.
- [x] **Monitoreo en vivo** (O1.6): se elige cliente y proyecto, la pantalla da
      los diez parámetros del `InfluxdbBackendListenerClient` para copiar —y el
      componente `.jmx` ya relleno— y enseña el tablero **filtrado por esa
      corrida**.
- [x] **WebSocket** `/ws/executions/{id}/metrics`, del motor propio. Lo sirve el
      backend (hace el `101 Switching Protocols`), pero **en desarrollo el
      navegador no llega**: apunta a `localhost:5173` y `vite.config.ts` no tiene
      `proxy`. Es del motor: va con **O3**, no con O1 (O-D7).

### Attachments + IA visión
- [x] **Subida de imágenes** monitoring + evidence, con análisis IA por imagen
      (Gemini Vision / OpenAI Vision) y fallback OCR con `pytesseract`.

---

## PENDIENTES

### Del plan de corrección
1. **Validación de Fredy de las Etapas 5b, 6 y 7** — guiones en
   `56_ETAPA5b_para_fredy_cierre.md`, `52_ETAPA6_para_fredy_cierre.md` y
   `60_ETAPA7_para_fredy_cierre.md`.
1b. **Decidir el alcance de "solo análisis"** y responder las cinco preguntas de
   `59_handoff_despliegue_analisis.md` §5. Ese documento está escrito para abrir
   un chat nuevo sin el historial de las etapas.

### De producto (anteriores al plan, siguen abiertos)
2. **Historial de informe integrado** — falta la pantalla de reapertura/edición
   con drag-and-drop sobre un reporte ya persistido.
3. **Ajuste visual de gráficas con muchas transacciones** — la estrategia está en
   `services/export/high_cardinality_strategy.py`; falta pulir etiquetas,
   leyendas y agrupación visual.
4. **HF13** — parser JTL `summary_df` con archivos muy pequeños: las métricas
   pueden quedar en `NaN` o `0` cuando la prueba dura segundos.
5. **R4 — Design System responsive** para 15" y 27" simultáneas.
6. **JMX export desde Script Designer original** — el endpoint existe; falta
   validación final del UI.
7. **Tiempo de generación del informe** (v1.2 §5) — el informe tardaba ~40 s y
   hoy tarda más de 5 minutos con `gpt-5.5`. Las dos vías ya aplicadas (retirar
   Throughput, quitar conclusiones por transacción) recortan 1 + 2·N llamadas.
   **Agrupar llamadas sigue sin medir.**

### Operativas
8. **Despliegue a producción de las seis etapas** — lista completa en
   `docs/reporte_claude_code/53_checklist_despliegue.md`. **Nada de eso se ha
   ejecutado.**
9. **`docker-compose.prod.yml` no hace lo que parece.** Verificado en la Etapa
   6.6 con `docker compose -f docker-compose.yml -f docker-compose.prod.yml
   config`: compose **fusiona** las listas, así que los `ports: []` no cierran
   nada — **5432, 8086, 3000 y 8001 quedan publicados en `0.0.0.0`** — y el
   `target: builder` del compose base sobrevive, de modo que el frontend de
   producción se construiría con la fase de Vite y no con nginx.
   **Matizado en la Etapa 7:** Fredy verificó desde internet que los cuatro
   puertos **no responden** — el NSG de Azure los cierra —, y el target correcto
   **vive en el servidor**, desde donde ya se despliega. Pasa de urgencia a
   **deuda**. Con un reverso que hay que mirar antes de tocarlo: el bind
   `./backend:/app` que sobrevive a esa misma fusión es lo único que hoy conserva
   `/app/media`, donde viven las capturas de monitoreo y evidencias (31 filas en
   `execution_attachments`, carpeta gitignorada, sin volumen nombrado).
   Detalle en `59_handoff_despliegue_analisis.md` §4.2, §4.3 y §4.5.
10. **HF-3 — rate limit de `/auth/login` inservible en producción.** Con nginx
    proxando a `localhost:8001` todos los usuarios llegan con la misma IP:
    **cinco entradas en quince minutos dejan a toda la plataforma sin acceso**.
    Diagnóstico verificado en `docs/reporte_claude_code/37_HF-3_deuda.md`. No se
    implementó por decisión de alcance; sigue abierto.
11. **Un test en rojo, anterior al plan** —
    `tests/test_analysis_pipeline.py::test_pipeline_parsea_jtl_y_popula_metricas_basicas`
    (`1 failed, 492 passed`). Parchea `analysis_pipeline.time`, que ese módulo ya
    no importa. Arreglo: quitar el `patch`, una línea.
12. **Rotar API key de OpenAI** si sigue habiendo alguna expuesta en el histórico.
13. **Política de retención de `.bak`** — quedan **53** archivos
    (`find backend frontend -name "*.bak*" -type f | wc -l`), muy por debajo de
    los 294 de mayo. Los de las etapas siguen el patrón `*.bak_etapaN_N.M_FECHA`.
14. **Los scripts de verificación viven en `/tmp/e2e` dentro de `jmeter_backend`**,
    no en el repositorio: desaparecen si se recrea el contenedor.

---

## HERRAMIENTAS DE VERIFICACIÓN

**Viven en `backend/pruebas_e2e/`, versionadas** (regla 36), y se copian a
`/tmp/e2e` dentro de `jmeter_backend` —que es donde hay Python y Chromium— con
`sh /app/pruebas_e2e/sincronizar.sh`, que ademas levanta los relevos. Un relé TCP —`rele_5173.py`—
hace que el frontend se vea como `http://localhost:5173` para que el origen pase
el CORS.

| Script | Qué verifica |
|---|---|
| `verificar_etapa2.py` | **la suite completa**: diez pasos, las cuatro salidas |
| `captura_informe.py` | captura y compara el DOM del informe (equivalencia C1) |
| `cableado_c2.py` · `cableado_c2_integrado.py` | que cada edición guarde en su canal |
| `tabla_por_transaccion.py` | la tabla resumen de cada bloque |
| `pdf_real_html.py` · `html_real.py` · `html_check.py` · `html_render.py` | PDF y HTML individuales |
| `integrado_check.py` · `integrado_pdf_html.py` | el informe integrado |
| `hf4_check.py` | que el bloque retirado no vuelva por ninguna salida |
| `panel_seleccion.py` · `e5_verdictos.py` | el panel de selección (Etapa 5) |
| `capas_tooltip.py` · `export_alcance.py` · `dialogo_export.py` · `capas_exportadas.py` · `capas_html_render.py` | la Etapa 6 |
| `o16_pantalla.py` | Monitoreo en vivo de punta a punta (O1.6) |
| `o2a3_config.py` · `o2a3_correlacion.py` | la prueba de correlación de O2a.3 (las lanza `scripts/lab_prueba_correlacion.sh`, desde el anfitrión) |
| `probar_tablero.py` | que los 13 paneles del tablero de infraestructura **devuelvan datos**, no que «deberían» |
| `cierre_o2a.sh` · `cierre_o2b.sh` | la regresión completa en serie: 13 suites, **507** comprobaciones |

Y los que **no** viven ahí, porque necesitan `docker` y se lanzan desde el
anfitrión, o corren dentro del laboratorio:

| Script | Qué verifica |
|---|---|
| `scripts/lab_prueba_correlacion.sh` | el recorrido de O2a.3: la prueba se ve en el servidor |
| `scripts/lab_comparar_modos.sh` | O2b.2: qué ve el agente que el modo de 10 s no ve, y lo que cuesta |
| `scripts/lab_corte_de_red.sh` | O2b.3: un corte de red real, y cuántos datos se recuperan |
| `lab/colector/comparar_con_nativo.py` | la paridad campo a campo con el complemento nativo |
| `lab/agente/medir_coste.sh` | CPU, memoria propia y red que consume el agente |

Ninguno llama a la IA: todos trabajan sobre informes ya generados.

> **Cuidado con `/auth/login`:** está limitado a 5 intentos por 15 minutos y por
> IP, y **los logins correctos también consumen cupo**. Los scripts reutilizan la
> sesión de `/tmp/e2e_sesion.json` y nunca reintentan en bucle.
