3b380e9 · 2026-09-17

# Handoff — desplegar SOLO el módulo de análisis

> **Este documento está escrito para abrirse en un chat nuevo, sin el historial de las
> etapas anteriores.** Todo lo que hace falta para retomar está aquí o en los archivos que
> se listan en §6.
>
> **No se ha ejecutado nada de lo que aquí se describe.** Ni despliegue, ni cambios de
> compose, ni nada en el servidor.

---

## 1. Estado del código

| | |
|---|---|
| Repositorio | `C:\proyectos\Kinetix` · remoto **`github`** (`IACygnus/Kinetix`), único destino de push |
| Rama | **`backup-trabajo-local`** — todo el producto vive ahí; `main` sigue en `Initial commit` |
| Último commit | `3b380e9` · *etapa7(7.3): validacion de punta a punta del integrado* |
| Último tag | `v3.1.0` — **las Etapas 1 a 7 no están etiquetadas** |
| Árbol de trabajo | limpio |
| Producción | `kinetix.sqasa.co` @ `20.81.141.77`, `/opt/apps/jmeter-analyzer`. **Sin sincronizar** |

### Qué contiene cada etapa

Referencia funcional única: **`docs/ESPECIFICACION-informe.md` v1.3**.

| Etapa | Qué hizo | Estado |
|---|---|---|
| 1 | Diagnóstico, telemetría de IA, timeout de 120 s y reintentos transitorios | validada |
| 2 | Estructura del informe (v1.3 §1): informe por transacción con el mismo diseño del general, sin conclusiones propias, sin Throughput Over Time. `reasoning_effort` | **validada por Fredy** |
| 3 | Estilo de los textos (§4): bloque de estilo único en los prompts, formato español determinista, detector de jerga con aviso ámbar | **validada por Fredy** |
| 5 | Panel de selección (§2.1): columnas Transacción · Muestras · Promedio · TPS · Errores, criterios desplegables por fila | **validada por Fredy** |
| 5b | Botón "Criterios" por fila (§2.2) y **la IA usa los criterios efectivos** de cada transacción | pendiente de validación |
| 6 | Control de capas promedio/máximo (§3), selector de exportación (§6), tildes | pendiente de validación |
| 7 | **Informe integrado completo**: sus bloques por transacción en pantalla y overrides propios en los exportados | pendiente de validación |

No hay Etapa 4: el plan saltó de la 3 a la 5. Los reportes de todas están en
`docs/reporte_claude_code/`, numerados `01`…`59`.

---

## 2. Inventario de módulos

> **Clasificación propuesta, NO decidida.** El alcance exacto de "solo análisis" lo decide
> Fredy (§5).

### 2.1 Candidatos a ANÁLISIS

| Módulo | Ruta(s) frontend | Router backend | Servicios | Tablas |
|---|---|---|---|---|
| Autenticación | `/login` | `auth` `/auth` | `core/security.py` | `users` |
| Usuarios | `/users`, `/users/new`, `/users/:id` | `users` `/users` | — | `users` |
| Perfil | `/profile` | `profile` `/profile` | — | `users` |
| Clientes y asignaciones | `/admin/clients`, `/admin/assignments` | `clients` `/clients` | `export/client_logo.py` | `clients`, `user_clients`, `client_logos` |
| Dashboard / stats | `/dashboard` | `dashboard` `/dashboard` | — | `test_executions`, `user_clients` |
| Upload JTL + panel | `/performance/new` | `upload` (sin prefijo) | `jtl/jtl_parser.py`, `ai/analysis_pipeline.py`, `ai/estilo.py`, `ai/criterios.py`, `ai/gemini.py` | `test_executions`, `test_results` |
| Historial e informe individual | `/performance/history`, `/performance/report/:id`, `/performance/report-latest` | `upload` | los de arriba | `test_executions` |
| Informe por transacción | (dentro del informe) | `upload` | `jtl/transaction_series.py`, `ai/transaction_report.py`, `ai/transaction_analysis.py` | `transaction_chart_analyses`, `transaction_analyses` |
| Exportación PDF / HTML | (botones del informe) | `export_pdf`, `export_html` | `export/report_generator.py`, `export/seleccion.py`, `export/capas_html.py`, `export/high_cardinality_strategy.py` | — |
| Informe integrado | `/performance/integrated`, `…/history`, `…/:reportId` | `integrated_report` `/reports` | los de export | `integrated_reports` |
| Comparativo carga vs estrés | (dentro del informe) | `compare` `/reports` | `ai/gemini.py` | `test_executions` |
| Monitoreo / evidencias / adjuntos | `/performance/monitoring`, `/performance/evidence` | `attachments` `/executions`, `analysis_ai` `/executions` | `ai/gemini.py` (Vision) | `execution_attachments` |
| Grafana / InfluxDB | `/monitoring/realtime`, `/monitoring/settings` | `monitoring` `/monitoring` | — | `monitoring_config` |
| Configuración de IA | `/admin/ai-config` | `ai_config` `/ai-config` | `ai/gemini.py` | `ai_config` |

### 2.2 Candidatos a NO ANÁLISIS

| Módulo | Ruta(s) frontend | Router backend | Servicios | Tablas |
|---|---|---|---|---|
| Script Designer | `/script-designer`, `…/history`, `…/:scriptId` | `scripts` `/scripts`, `script_variables` `/scripts` | `services/engine/**` | `script_designs` |
| AI Script Designer | `/ai-script-designer`, `…/history`, `…/editor/:id`, `/ai-script-editor` | `script_ai` `/script-designer/ai`, `ai_design_data_files` | `ai/jmx_chunk_assembler.py`, `ai/har_chunk_router.py`, `ai/har_flow_analyzer.py` | `ai_script_designs`, `ai_design_data_files` |
| Motor de ejecución | `/execution-dashboard` | `executions` `/executions`, `scenarios` `/scenarios`, `performance_executions` `/performance-executions` | `services/engine/**` | `scenarios`, `performance_executions` |
| Métricas en vivo | (dentro de Ejecución) | `ws_metrics` `/api/v1/ws` | `engine/metrics_collector.py` | — (InfluxDB) |
| Importadores | (modales del Designer) | `har_import` `/har-import`, `import_script` `/import` | `engine/*_importer.py` | `script_designs` |
| Data files (CSV) | (dentro del Designer) | `data_files` `/data-files` | `engine/data_file_service.py` | `data_files` |

### 2.3 Dependencias cruzadas — el hallazgo que importa

**La dependencia es de un solo sentido.** Verificado con grep sobre los dos conjuntos:

```
ANÁLISIS  →  motor / diseñador :  NINGUNA
motor / diseñador  →  ANÁLISIS :  TRES puntos
```

Los tres puntos, todos del lado NO-análisis:

| Archivo | Qué importa del análisis | Por qué |
|---|---|---|
| `endpoints/executions.py` | `TestExecution`, `JTLParser` | `POST /executions/{id}/generate-report` convierte una corrida del motor en una ejecución analizable |
| `endpoints/performance_executions.py` | `TestExecution`, `run_jtl_analysis_pipeline` | lo mismo, desde el historial del motor |
| `endpoints/script_ai.py` | `ai/gemini.py`, `ai/har_flow_analyzer.py`, `ai/har_chunk_router.py` | reusa el cliente de IA y los analizadores de HAR |

**Consecuencia: quitar el lado NO-análisis es limpio; quitar el de análisis rompería el
motor.** Es justo la dirección que hace falta.

### 2.4 Casos dudosos — que Fredy decida

| Caso | Por qué es dudoso |
|---|---|
| **`monitoring` (Grafana/InfluxDB)** | La pantalla "Real-Time" muestra métricas del **motor propio** mientras corre. Sin motor, el dashboard de Grafana queda sin fuente en vivo; la configuración sigue sirviendo para las capturas de monitoreo que se adjuntan al informe |
| **`ws_metrics`** | Solo tiene sentido con el motor. Si se va el motor, se va |
| **El prefijo `/executions`** | Lo comparten **tres** routers: `executions` (motor), `attachments` y `analysis_ai` (análisis). No registrar el del motor no rompe a los otros dos, pero hay que hacerlo a conciencia |
| **`services/ai/gemini.py`** | Es del análisis, pero el AI Script Designer lo usa. Si se llevan los dos módulos, no hay problema; si no, `script_ai.py` se queda sin cliente de IA |
| **Datos del motor ya analizados** | Hay **32 filas** en `performance_executions` y **13** en `script_designs`. Algunas corridas del motor produjeron `TestExecution` que hoy se ven en el historial de análisis. Quitar el motor no borra esos informes, pero sí el botón que los generó |
| **Menú "Diseño" y "Ejecución"** | Son dos grupos enteros del `Sidebar.tsx`. Ocultarlos es trivial; decidir si se ocultan o se retiran, no |

### 2.5 Volumen de datos hoy (desarrollo)

```
test_executions             67      script_designs              13
transaction_chart_analyses 270      scenarios                   23
integrated_reports          28      performance_executions      32
execution_attachments       31      ai_script_designs           21
test_results                 0      data_files                   0
```

---

## 3. Opciones técnicas para desplegar solo análisis

Ninguna implementada. Se listan de menos a más invasiva.

### Opción A — Ocultar por configuración (menús y rutas)

Una variable de entorno (p. ej. `KINETIX_MODULOS=analisis`) que el `Sidebar` y `App.tsx`
leen para no pintar los grupos "Diseño" y "Ejecución" ni registrar sus rutas.

- **Ventajas:** una sola rama, un solo despliegue, reversible con un cambio de variable.
  Tamaño pequeño: ~40 líneas entre `Sidebar.tsx`, `App.tsx` y el `.env`.
- **Riesgos:** el backend **sigue expuesto**. Quien conozca las URLs puede llamar a
  `/api/v1/scripts`, `/api/v1/executions/start`, etc. Es ocultar, no quitar.
- **Cuándo sirve:** si el objetivo es que el usuario no vea lo que no le toca, no que sea
  inalcanzable.

### Opción B — No registrar los routers (A + backend)

Además de A, `api.py` no incluye los routers del motor y del diseñador según la misma
variable.

- **Ventajas:** los endpoints devuelven 404 de verdad. Sigue siendo una rama y un
  despliegue. Tamaño: ~20 líneas más, en `api.py`.
- **Riesgos:** hay que respetar las tres dependencias de §2.3 — `executions.py` y
  `performance_executions.py` importan del análisis, no al revés, así que **no registrarlos
  no rompe nada**. El prefijo `/executions` compartido obliga a comprobar que `attachments`
  y `analysis_ai` siguen respondiendo.
- **Cuándo sirve:** es la opción por defecto razonable. **Recomendada** si el alcance es
  "el servidor solo ofrece análisis".

### Opción C — Rama separada con el código podado

Una rama `solo-analisis` de la que se borran los módulos NO-análisis.

- **Ventajas:** la imagen desplegada no contiene el código que no se usa. Menor superficie.
- **Riesgos:** **dos ramas que mantener**, y cada corrección hay que llevarla a las dos.
  Con el ritmo actual de etapas, es la que más trabajo continuo genera. Tamaño: grande de
  entrada y permanente después.
- **Cuándo sirve:** si hubiera una exigencia de que el código no viaje al servidor.

### Opción D — Dos despliegues del mismo código

Mismo repositorio, dos `docker compose` con distinta configuración (Opción B aplicada a uno).

- **Ventajas:** una sola base de código; el equipo de diseño sigue con su instancia.
- **Riesgos:** dos entornos, dos bases, duplicar la operación. Y hoy **ni siquiera hay uno
  desplegado al día**.
- **Cuándo sirve:** más adelante, si las dos audiencias conviven.

**Sugerencia, no decisión:** **B**, con A incluida. Es reversible, cabe en un despliegue y
la dirección de las dependencias la hace segura. Nada de esto se implementa sin que Fredy
fije el alcance.

---

## 4. Checklist de despliegue (actualiza al reporte 53)

### 4.1 Bloqueante — el `ALTER TABLE` de `reasoning_effort`

```bash
docker exec -i jmeter_postgres psql -U jmeter_user -d jmeter_analyzer_db \
  < docs/sql/etapa2_reasoning_effort.sql
```

Idempotente. **Verificación obligatoria después:** `GET /ai-config` responde **200** e
incluye `reasoning_effort`.

**Por qué es bloqueante:** el proyecto no usa Alembic y `Base.metadata.create_all` no añade
columnas a tablas existentes. Sin la columna, el backend arranca, la primera lectura de
`ai_config` falla, el error se degrada a un `warning` y **todos los informes salen con texto
de respaldo sin que nadie se entere**.

Estado: **aplicado en desarrollo · pendiente en producción**.

### 4.2 Puertos — CORREGIDO respecto al reporte 53

El reporte 53 los daba como expuestos. **Fredy verificó desde internet que 5432, 8086, 3000
y 8001 no responden: el NSG de Azure los está cerrando.** La protección es efectiva.

Lo que sigue siendo cierto, y queda como **deuda sin urgencia**: el `docker-compose.prod.yml`
**no los cierra por sí mismo**. `ports: []` no vacía la lista — Compose la fusiona — y los
cuatro quedan publicados en `0.0.0.0` a nivel de Docker. Si algún día cambia el NSG, o el
compose se lleva a otra máquina, la protección desaparece sin avisar.

Comprobable en solo lectura:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
```

Arreglo cuando se quiera: publicar con interfaz explícita, `127.0.0.1:5432:5432` y análogos.

### 4.3 Target del frontend — CORREGIDO respecto al reporte 53

El cambio que hace que el frontend se construya con nginx **vive en el servidor, y desde el
servidor ya se despliega**. No es un impedimento.

Queda anotado que el `docker-compose.prod.yml` del repositorio, fusionado con el base,
arrastra `target: builder` y el bind-mount del código: **el repositorio por sí solo no
produce el frontend de producción**. Quien despliegue desde cero en otra máquina tiene que
saberlo.

### 4.4 Rebuild en el servidor — obligatorio

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Las Etapas 2, 3, 5, 5b, 6 y 7 cambian backend **y** frontend. En local no hace falta
(`--reload` + Vite con el código montado); en el servidor **sí**.

### 4.5 Las imágenes de monitoreo y evidencias — NUEVO, y con un matiz

Las capturas que se adjuntan a un informe se escriben en **`/app/media/attachments/<id>/`**
(`attachments.py:21`). Hoy hay **31 filas** en `execution_attachments` apuntando ahí.

Lo verificado sobre los dos compose:

- **No hay volumen nombrado para `media`** en ninguno de los dos. `uploads_data` cubre
  `/app/uploads` (los JTL), no los adjuntos.
- En producción, esa carpeta sobrevive **solo porque el bind `./backend:/app` del compose
  base sigue vivo tras la fusión** — el mismo comportamiento de Compose que deja en pie el
  `target: builder` de §4.3.
- `backend/media/` está en `.gitignore` (línea 200) y **no está versionada**.

> **La trampa:** arreglar §4.3 —vaciar de verdad los `volumes` del backend, o pasar a una
> imagen sin bind-mount— **empezaría a perder las imágenes sin avisar**. Los dos puntos hay
> que tocarlos juntos: si se quita el bind, hay que añadir antes un volumen nombrado para
> `/app/media`.

Y con el bind tal como está, un despliegue que haga **checkout limpio en otro directorio**
tampoco se las lleva, porque no están en git.

No he podido verificar el procedimiento exacto de despliegue del servidor desde aquí, así
que **no afirmo que hoy se pierdan**: afirmo que su persistencia depende de un detalle
frágil y no declarado, y que hay que decidirlo antes de tocar el compose.

(Los PDF y HTML exportados no se guardan en disco — se devuelven por HTTP — así que para
ellos no hace falta nada.)

### 4.6 `DEBUG` — NUEVO

Existe `Settings.DEBUG: bool = False` (`core/config.py:13`), que solo se usa para
`reload=settings.DEBUG` en `main.py:318`. Está comentada en `.env.example` y **ninguno de
los dos compose la define**, así que en producción vale `False` por defecto.

**Acción:** comprobar que el `.env` del servidor no la traiga en `true` — es lo único que
podría reactivar el reload en producción. Va junto con `ENVIRONMENT=production`, que el
override sí fija.

### 4.7 HF-3 — bloqueante si hay varios usuarios

`/auth/login` está limitado a 5 intentos por 15 minutos **y por IP**, y **los logins
correctos también consumen cupo**. Con nginx proxando a `localhost:8001`, todos los usuarios
llegan con la misma IP: **cinco entradas en quince minutos dejan a toda la plataforma sin
acceso**, con un mensaje que parece error de contraseña. Y con `--workers 2` hay dos
contadores independientes en memoria de proceso.

Diagnóstico completo y diseño de la solución (tabla `login_attempts`, `--proxy-headers`,
`--forwarded-allow-ips` con el gateway real) en `docs/reporte_claude_code/37_HF-3_deuda.md`.

**Si el despliegue es de un solo usuario, no bloquea. Si lo van a usar varias personas, sí.**

### 4.8 Menor

- **Decidir el `reasoning_effort` de producción.** Toda la medición se hizo con `low`.
- **Un test en rojo anterior al plan:** `tests/test_analysis_pipeline.py::test_pipeline_parsea_jtl_y_popula_metricas_basicas` (492 pasan, 1 falla). Parchea `analysis_pipeline.time`, que ese módulo ya no importa. Arreglo: quitar el `patch`, una línea.
- **Los scripts de verificación** viven en `/tmp/e2e` dentro de `jmeter_backend` y en
  `C:\proyectos\Kinetix_pruebas\e2e\` (38 archivos). No están en el repositorio.

---

## 5. Preguntas abiertas para Fredy

1. **Alcance exacto de "solo análisis".** ¿La clasificación de §2.1 y §2.2 es la correcta?
   En concreto: ¿entra **Monitoreo Real-Time** (§2.4), que hoy muestra las métricas del motor
   mientras corre? ¿Y la **Configuración de IA**, que es administración pero la usa el
   análisis?
2. **Destino de respaldo en git.** ¿Se sigue pushando solo a `github/backup-trabajo-local`?
   ¿Hay que llevar algo a `main`, crear un tag (`v4.0.0`) o preparar el envío parcial al
   remoto `azure`, que según CLAUDE.md recibirá "solo una parte del producto"?
3. **Datos.** ¿El despliegue arranca con la **base de producción actual** o con una **limpia**?
   Si es la actual: hay 67 ejecuciones, 28 informes integrados y 31 adjuntos, y estos últimos
   dependen del volumen de §4.5.
4. **Ventana de despliegue.** Requiere rebuild de los dos contenedores y el `ALTER TABLE`
   previo. ¿Cuándo, y quién acompaña?
5. **HF-3.** ¿Cuántas personas van a entrar? Si son varias, hay que implementarlo antes
   (§4.7), y falta decidir el mensaje que ve quien queda bloqueado.

---

## 6. Archivos a adjuntar en el chat nuevo

| Archivo | Para qué |
|---|---|
| `CLAUDE.md` | referencia del proyecto: stack, estructura, reglas, deploy |
| `PROJECT_STATUS.md` | estado vivo y pendientes |
| `docs/ESPECIFICACION-informe.md` (v1.3) | la referencia funcional del informe |
| **este documento** (`59_handoff_despliegue_analisis.md`) | el punto de partida |
| `docs/reporte_claude_code/53_checklist_despliegue.md` | la deuda completa, de la que §4 es la versión corregida |
| `docs/reporte_claude_code/37_HF-3_deuda.md` | el diagnóstico y el diseño de HF-3 |
| `docker-compose.yml` y `docker-compose.prod.yml` | para razonar sobre §4.2 y §4.3 |
| `backend/app/api/v1/api.py` | el registro de routers, donde se aplicaría la Opción B |
| `frontend/src/App.tsx` y `frontend/src/components/layout/Sidebar.tsx` | rutas y menús, donde se aplicaría la Opción A |

Con eso basta: **no hace falta el historial de las siete etapas**.

---

**Nada de este documento se ha ejecutado.** Es el punto de partida de una conversación que
todavía no ha empezado.
