Commit base `04d5523` · 1 de octubre de 2026 · Reporte 146 — las horas de los informes, en hora de Colombia

# Las horas de los informes, en hora de Colombia
Pendiente de validación visual de Fredy

## 1. El fallo

Todas las horas de los informes salían con 5 horas de más. Un ejemplo real: SODEXO (Pluxee), «Dispersion_2_1000C_1809», JTL
«resultados_general_carga 18-sept.-2026-171637.jtl». El informe decía «Inicio 18/9/2026 22:16:37» y debía decir 17:16:37.

### Diagnóstico

| Pregunta | Respuesta |
|---|---|
| ¿Dónde se convierte el `timeStamp`? | `jtl_parser.py:220` y `:254`, con `pd.to_datetime(unit='ms')`. El resultado es UTC sin zona y nadie lo pasaba a hora de Colombia |
| ¿Qué cuelga de ahí? | Las gráficas de pantalla (`/charts` y `transaction_series.py`), las del PDF (matplotlib), las del HTML y del integrado (Plotly), y las horas de reloj de los prompts: `contexto_prompt.linea_de_tiempo`, `fases._reloj` (la concentración y los hechos) y `resumen_serie._reloj` (la serie de R2) |
| ¿Y la cabecera? | `start_time` y `end_time` se leen de la base y se formatean con `strftime` en `export_html.py`, `export_pdf.py` e `integrated_report.py` (×2). En pantalla los pinta `Dashboard.tsx` con `new Date(naive)` |
| ¿Es una regresión? | **No.** Viene así desde el `Initial commit` (fc700e0). No hay `TZ` en ningún compose ni Dockerfile, y Postgres está en UTC |
| ¿Se guarda o se calcula? | La base guarda **solo** `start_time` y `end_time`, en UTC y sin zona. Sodexo tiene 22:16:37.835 → 23:03:51.154, con 2833 s. Las series no se guardan: cada petición vuelve a leer el JTL |

## 2. El arreglo

**Hay una sola definición:** el módulo nuevo `backend/app/services/zona_informe.py`.
- `ZONA_INFORMES` sale de `REPORT_TIMEZONE`, con **`America/Bogota` por defecto**. No usa la zona del servidor ni la del navegador.
- `a_informe(x)` convierte de UTC a hora del informe, sin zona: es la hora que se pinta.
- `a_utc(x)` hace la vuelta: es la hora que se guarda y la que se compara con otra fuente en UTC.
- Las dos aceptan `datetime`, `Timestamp`, `Series` y `None`.

**Un punto por capa:**

| Capa | Punto | Qué cubre |
|---|---|---|
| Lectura del JTL (backend) | `jtl_parser.py`: `df['timestamp'] = a_informe(...)` | Todo lo derivado: las gráficas de las cuatro salidas, los prompts y la fecha del prompt |
| Guardado | `a_utc(...)` en `upload.py`, `analysis_pipeline.py` y `executions.py` (motor propio) | **La base sigue recibiendo exactamente lo mismo que antes** |
| API para la pantalla | `field_serializer` en `TestExecutionResponse` para `start_time`, `end_time`, `execution_date`, `created_at` y `updated_at` | La pantalla, el Historial, el integrado en pantalla y la comparativa de selección |
| Cabecera de los exportados | `a_informe(...)` dentro del `strftime`: HTML, PDF, integrado (×2, más la fecha `execution_date` ×2) y `compare.py` | PDF, HTML e integrado |
| Frontend | **Sin cambios** | Recibe hora local sin zona y `new Date(naive)` + `toLocale…` la pinta tal cual, con cualquier zona del navegador |

**No cambia:**
- No se modifica la base ni se migra nada. La duración tampoco cambia, porque es una resta.
- No se ha tocado ningún archivo del frontend: tampoco `Dashboard.tsx`.
- Ni el módulo de horas ni observabilidad.

**Lo que se encontró por el camino.** `wapt_parser.py` convertía una hora de reloj sin zona como si fuera UTC. Con el cambio habría salido 5 horas antes, así que ahora la interpreta en la zona de los informes (`a_utc`). Locust usa época real y sale bien sin tocarlo.

### Los protegidos, diff entero (autorizados por Fredy)

`backend/app/services/jtl/jtl_parser.py` (2 líneas y el import):

```diff
@@ -9,6 +9,8 @@ from datetime import datetime
 from typing import Dict, List, Tuple, Optional, Set
 import logging
 
+from app.services.zona_informe import a_informe
+
 logger = logging.getLogger(__name__)
@@ -217,7 +219,7 @@ class JTLParser:
         # Convertir timestamp a datetime
-        self.df['timestamp'] = pd.to_datetime(self.df['timeStamp'], unit='ms')
+        self.df['timestamp'] = a_informe(pd.to_datetime(self.df['timeStamp'], unit='ms'))
@@ -251,7 +253,7 @@ class JTLParser:
         # Convertir timestamp a datetime
-        combined['timestamp'] = pd.to_datetime(combined['timeStamp'], unit='ms')
+        combined['timestamp'] = a_informe(pd.to_datetime(combined['timeStamp'], unit='ms'))
```

`backend/app/api/v1/endpoints/export_html.py` (2 líneas y el import):

```diff
@@ -13,6 +13,7 @@ import json
 from zoneinfo import ZoneInfo
+from app.services.zona_informe import a_informe   # 146
@@ -629,8 +630,8 @@ async def export_html(
-            'startTime': execution.start_time.strftime('%d/%m/%Y %H:%M:%S') if execution.start_time else '--',
-            'endTime': execution.end_time.strftime('%d/%m/%Y %H:%M:%S') if execution.end_time else '--',
+            'startTime': a_informe(execution.start_time).strftime('%d/%m/%Y %H:%M:%S') if execution.start_time else '--',
+            'endTime': a_informe(execution.end_time).strftime('%d/%m/%Y %H:%M:%S') if execution.end_time else '--',
```

`backend/app/api/v1/endpoints/export_pdf.py` (2 líneas y el import):

```diff
@@ -11,6 +11,7 @@ from typing import List, Optional
 from zoneinfo import ZoneInfo
+from app.services.zona_informe import a_informe   # 146
@@ -461,8 +462,8 @@ async def export_pdf(
-            'startTime': execution.start_time.strftime('%d/%m/%Y %H:%M:%S') if execution.start_time else '--',
-            'endTime': execution.end_time.strftime('%d/%m/%Y %H:%M:%S') if execution.end_time else '--',
+            'startTime': a_informe(execution.start_time).strftime('%d/%m/%Y %H:%M:%S') if execution.start_time else '--',
+            'endTime': a_informe(execution.end_time).strftime('%d/%m/%Y %H:%M:%S') if execution.end_time else '--',
```

`Dashboard.tsx` y `report_generator.py` **no se tocaron**. La rama web del HTML solo cambia en el dato de la cabecera, que es corrección de datos y está autorizada. La maquetación no cambia.

## 3. Quién necesita la hora ABSOLUTA (comprobación 1)

Revisé todos los consumidores de `df['timestamp']` y de `start_time`/`end_time`:

| Consumidor | ¿Compara con otra fuente en UTC? | Cómo queda |
|---|---|---|
| `upload.py:487-488`, `analysis_pipeline.py:629-630`, `executions.py:635-636` (guardado) | Sí: la base | **`a_utc`**. Comprobado: el ZZTEST se guarda como 22:16:37 y Sodexo sigue en 22:16:37.835 |
| `performance_executions.py:287` | Guarda `perf_exec.started_at`, que no sale del JTL, y lo sobrescribe el pipeline con `a_utc` | Sin cambio |
| `fases.concentracion` (`ts - f.t0`) | No: los dos lados salen del mismo `df` | Sin cambio, sigue cuadrando |
| `contexto_prompt`, `resumen_serie`, `transaction_report` (`hora_pico`) | No: son texto | Hora de Colombia |
| `validate_jtl_compatibility` (`jtl_parser.py:35-37`) | Compara archivos entre sí, siempre en UTC | Sin cambio, coherente |
| **Observabilidad**: `sesiones.py` (ventana InfluxDB), `monitoring.py` (corrida, proyectos), `ws_metrics.py` | **No leen ni `df['timestamp']` ni el `start_time` de una ejecución**: la ventana de la sesión sale de las fechas de `monitoring_sessions`, en UTC | **Sin cambio.** O1.6, O2d.2 y O2d.3 en verde |
| Capturas (`execution_attachments`, `analysis_ai.py`) | No: ninguna correlación por hora con la ejecución | Sin cambio |
| Filtros por rango contra la base | No hay ninguno sobre `start_time`/`end_time`. El Historial ordena por `created_at` **en el servidor** | Sin cambio |
| `wapt_parser.py` | Fabrica la época desde una hora de reloj | `a_utc` (ver §2) |

## 4. La pantalla, con el `field_serializer` (comprobación 2)

Revisé todos los sitios del frontend que leen `start_time`, `end_time` o `created_at` de una ejecución:

| Dónde | Cómo lo pinta | ¿Añade «Z» o reconvierte? |
|---|---|---|
| `Dashboard.tsx:561, 615, 619` | `new Date(x).toLocaleString('es-ES')` | No |
| `History.tsx:308` (y `DashboardHome.tsx:213`) | `new Date(x).toLocaleDateString` | No |
| `IntegratedReportPage.tsx:509, 723` | `new Date(start_time \|\| created_at)` | No |
| `EvidencePage.tsx:177`, `MonitoringPage.tsx:182` | `toLocaleDateString` | No |
| `ExecutionReportSection.tsx:93` | Código muerto (reporte 57) | No |
| Comparativa (`ComparisonReport.tsx`) | No pinta fechas | — |

- **Nada devuelve esas fechas al servidor** en un PUT o PATCH. La única excepción: `IntegratedReportPage.tsx:509` guarda `sourceDate` en las secciones del integrado, como **texto ya formateado**, y solo se ve en el constructor (línea 126), nunca en los exportados. Los integrados viejos conservan ese texto con la hora de antes; los nuevos lo guardan bien. No se ha tocado.
- **El orden y los filtros del Historial no cambian.** Lo ordena el servidor (`order_by created_at`) y sus filtros son de tipo, cliente y proyecto: ninguno por fecha.
- El historial de integrados lee `integrated_reports.created_at`, que no pasa por este schema: sin cambio.
- `TransactionReportSection.hora()` sigue añadiendo «Z» a `generated_at`, que es la hora de generación del texto y no la de la prueba. Sale en la zona del navegador, como antes.

## 5. Las suites

**Nuevas** (en `backend/pruebas_e2e/`):

| Suite | Qué comprueba | Resultado |
|---|---|---|
| `zona_horaria_informes.py` | JTL ZZTEST de época conocida (1789769797000 = 22:16:37Z), contra el 8002 y la base de pruebas. Cubre lo guardado (UTC), la duración, el cruce de medianoche y las **seis salidas**: cabecera de la API, las 7 series de `/charts` y las 4 de `/transaction-charts` (primer y último punto), HTML (cabecera y Plotly), PDF, integrado HTML y PDF, y prompts (línea de tiempo, fases y serie de R2) | **TODO PASA** |
| `zona_pdf_texto.py` | El texto visible de los PDF de la suite y del de Sodexo, leído fuera del contenedor | **TODO PASA** (3 PDF) |
| `zona_sodexo_lectura.py` | La ejecución real de Sodexo, **solo GET**, con un token en proceso (sin login): base sin cambios, API 17:16:37 → 18:03:51, 47m 13s, las series de 17:16 a 18:03, el HTML y el PDF | Ver el resultado al final de §5 |

**Una suite cambiada (comprobación 3):** `r2_series.py`, dos literales. Antes esperaba `20:23:27–20:24:21` y `(20:05:00)`; ahora espera `15:23:27–15:24:21` y `(15:05:00)`.
- **Por qué no es ajustar la prueba al resultado:** el JTL de Nova empieza en la época 20:04:55.259 **UTC**, y eso en Colombia son las 15:04:55. Su nombre de archivo («…_200455») lleva la hora UTC porque la inyectora que lo generó tenía el reloj en UTC. La suite copió en su día la hora UTC que el producto daba mal.
- `fases_r2.py` y `tramos_fases.py` no son suites con expectativas: son herramientas de diagnóstico que necesitan `/tmp/r2/…` y argumentos. No se corrieron.
- Ninguna otra suite lleva horas de reloj escritas.

**Regresión:**

| Suite | Resultado |
|---|---|
| `cierre_r1.sh` (R1.1 a R1.4, C2 integrado y C2 individual) | **TODO PASA** |
| `export_alcance.py` (6.3) · `capas_exportadas.py` (6.4) · `vinetas_export.py` | **TODO PASA** |
| `r2_series.py` | **TODO PASA** (con el cambio de arriba) |
| O1.6 `o16_pantalla.py` · O2d.2 `o2d2_sesiones.py` · O2d.3 `o2d3_jmx.py` | **TODO PASA** |
| O2d.5 `o2d5_pantalla.py` | 6 FALLA, todas en las gráficas **del servidor** (CPU, memoria, conexiones). Dependen del laboratorio: `lab_colector` está parado («Exited (255) 5 days ago») y no hay métricas de infraestructura. `sesiones.py` no importa nada de lo que se cambió. No levanté el laboratorio |

**Comprobación visual** de una gráfica del PDF de Sodexo (imagen extraída del PDF): su eje es **tiempo transcurrido** (00:00:00 → 00:47:06), no hora de reloj, así que no le afectaba el fallo.

Resultado de `zona_sodexo_lectura.py`: **TODO PASA**.
- La base no cambia: sigue en 22:16:37.835 UTC.
- La API devuelve 17:16:37.835 → 18:03:51.154, y la duración sigue siendo 47m 13s.
- Response Times por transacción, que va al segundo, empieza a las **17:16:37 y termina a las 18:03:51, igual que la cabecera**.
- Las series agregadas van por cubos: empiezan en el cubo de 17:16:36 y terminan en el de 18:03:44. Eso ya era así antes del cambio; ahora solo se le quitan las 5 horas.
- El HTML trae 57 trazas Plotly, todas empezando entre 17:16 y 17:18, y no contiene ninguna hora UTC.
- El texto del PDF dice 17:16:37 y 18:03:51, y no contiene ninguna hora UTC.

## 6. Los informes ya hechos (punto 4)

**El criterio:** hay hora corrida si el texto (de la IA o editado a mano) cita una hora de reloj `hh:mm[:ss]` que cae **dentro de la ventana UTC** de su prueba (±1 min).
- No cuentan los momentos «min M:SS», que son tiempo transcurrido y no cambian.
- Se miraron las columnas `ai_*` de la ejecución, `transaction_chart_analyses`, y los `overrides` y `consolidated_analysis` de los integrados.
- Lectura con `SELECT` y nada más.

**SODEXO (Pluxee): ninguno.** Ninguna de sus 7 ejecuciones ni de sus 6 integrados cita una hora de reloj en el texto. Sin filtro de ventana, las únicas horas que aparecen son los metadatos `generated_at` de los consolidados, que ya llevan `-05:00` y no se pintan. **Fredy puede volver a exportar los informes de Sodexo tal cual.**

| Ejecución | Inicio (Colombia) |
|---|---|
| Ejecucion_1_3400_1609 | 16/09 12:04:35 |
| Ejecucion_3_200C_1709 | 17/09 15:23:27 |
| Ejecucion_2_6000_1709 | 17/09 17:25:08 |
| Dispersion_1_500C_1809 | 18/09 15:46:40 |
| Dispersion_2_1000C_1809 (…171637.jtl) | 18/09 17:16:37 |
| Dispersion_2_1000C_1809 (…081510.jtl) | 21/09 08:15:10 |
| Dispersion_3_1000C_2109 | 21/09 09:42:08 |

Integrados de Sodexo: los seis «Informe Integrado - 01/10/2026» de las 18:23, 19:01, 19:32, 19:46, 19:59 y 20:18. Ninguno con hora corrida.

**Los demás clientes, solo el recuento:**

| Cliente | Ejecuciones | Con hora corrida | Integrados | Con hora corrida |
|---|---|---|---|---|
| (sin cliente) | 2 | 1 | 0 | 0 |
| BANCO FICOHSA | 3 | 1 | 4 | 0 |
| Bancoomeva | 2 | 1 | 2 | 0 |
| Colcomercio | 1 | 0 | 0 | 0 |
| Compensar | 14 | 0 | 4 | 0 |
| Editor IA | 5 | 0 | 3 | 0 |
| MEDICINA PREPAGADA COOMEVA | 3 | 0 | 3 | 0 |
| Nutresa | 1 | 0 | 7 | 0 |
| Occidente | 7 | 0 | 3 | 0 |
| SmokeTest | 1 | 0 | 0 | 0 |
| TestClient | 5 | 0 | 0 | 0 |
| iaperformance | 14 | 7 | 4 | 0 |
| popular | 8 | 0 | 12 | 1 |
| prueba avianca | 11 | 7 | 5 | 0 |

No se ha cambiado ningún texto. Fredy decide si los edita a mano o los regenera.

## 7. Despliegue

- **`REPORT_TIMEZONE`**: por defecto `America/Bogota`, **no hay que definirla**. Está anotada en `.env.example` y en `PROJECT_STATUS.md` (pendiente operativo 8, el del checklist de despliegue). `docker-compose.yml` la pasa al backend; el contenedor de desarrollo la recibirá en su próximo `up`, y mientras tanto usa el valor por defecto, que es el mismo.
- Sin SQL y sin migraciones. Solo hay que desplegar el backend.

## 8. Lo que queda a la vista

- Durante la prueba, el log del backend registró un `POST /auth/refresh` desde `172.18.0.1`, la IP del navegador. Lo más probable es una pestaña de Kinetix que quedó abierta. No se tocó ningún archivo del frontend.
- Un JTL que venga de una inyectora con el reloj en UTC lleva en el **nombre** la hora UTC, como el de Nova. Ahora el informe dirá la hora de Colombia y el nombre del archivo otra cosa. Es lo correcto: la época del JTL es absoluta.
- La numeración salta del 144 al 146 porque el número lo fijó el encargo; supongo que el 145 está reservado para el 5.1 del Analista IA, que queda en espera.
