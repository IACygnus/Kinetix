958cba9 · 2026-09-21

# ETAPA O1.1 — diagnóstico del monitoreo actual (solo lectura)

**No se tocó nada:** ni código, ni `docker-compose`, ni la base, ni los
contenedores. Todo lo de abajo son lecturas: `GET`, `SELECT`, `docker exec` de
consulta y el listado de reglas del cortafuegos. **0 llamadas a la IA.**

---

## Resumen en una página

| Pieza | Estado | Desde |
|---|---|---|
| InfluxDB 2.7.12 | **vivo y vacío** — cardinalidad 0: nunca ha entrado un dato | siempre |
| Grafana 10.2.3 | **vivo**, con su tablero, pero **su fuente de datos no funciona** | 2026-02-20 |
| Fuente de datos `InfluxDB-JMeter` | **rota**: «missing organization in datasource configuration» | desde que se creó |
| `monitoring_config` (base) | apunta a un tablero y a una organización **que no existen** | 2026-03-05 |
| Pantalla «Monitoreo Grafana» | **oculta del menú**, marcada «desarrollo futuro» | 2026-04-21 (v3.0.0) |
| `/performance/monitoring` | **funciona**, pero no es Grafana: son capturas + IA | — |
| WebSocket de métricas vivas | el backend lo sirve; **el navegador no llega a él en desarrollo** | — |
| Motor propio → InfluxDB | **no escribe nunca**: no hay cliente ni código que lo intente | siempre |

**Nada de la cadena InfluxDB → Grafana ha funcionado jamás de punta a punta.** No
es una avería reciente: es una integración que se dejó a medias en febrero y
marzo de 2026 y que en abril se escondió del menú.

Y la buena noticia, que cambia el tamaño de O1: **`jmeter_backend` ya trae
Apache JMeter 5.6.3 con Java 21**, y ese JMeter incluye el
`InfluxdbBackendListenerClient`. El tablero de Grafana ya está escrito **contra
el esquema exacto de ese listener**. Falta conectar cuatro cables, no construir
la instalación.

---

## 1. Qué hay vivo

### 1.1 InfluxDB

```
Servidor        InfluxDB v2.7.12   (imagen influxdb:2.7-alpine)
Organización    performance        (id fea51f27d2fe936f)
Cubos           jmeter       720h0m0s  (30 días)
                _monitoring  168h0m0s
                _tasks        72h0m0s
Puerto          0.0.0.0:8086 -> 8086
```

**El cubo `jmeter` está vacío.** No es que caducara el dato por la retención de
30 días: la cardinalidad de la serie es **0**, que es lo que se mide sin importar
el rango de tiempo.

```
influxdb.cardinality(bucket:"jmeter", start: 2020-01-01T00:00:00Z)  ->  0
```

**El token.** `.env` no define ninguna variable de InfluxDB, así que rige el
valor por defecto de `docker-compose.yml`:
`jmeter-token-2024-super-secret`. Y ese token es el **de operador**:

```
read:/authorizations  write:/authorizations
read:/buckets         write:/buckets
read:/orgs            write:/orgs
read:/users           write:/users
… y así con todo
```

Es decir: **el único token que hoy existe puede borrar cubos, crear tokens y
cambiar la organización.** Dárselo a un JMeter de un cliente es darle la llave
maestra del InfluxDB entero. Esto pesa en la decisión de §2.

### 1.2 Grafana

```
Versión      10.2.3
Tablero      "JMeter Performance Testing Dashboard"   uid jmeter-performance
Carpeta      JMeter Performance
Fuente       InfluxDB-JMeter (uid influxdb-jmeter, url http://influxdb:8086)
Anónimo      HABILITADO, rol Viewer
```

Los nueve paneles del tablero: Response Time Over Time · Active Threads · Error
Rate · Throughput · Total Requests · Total Errors · Percentiles p90/p95/p99 ·
Requests by Transaction · Transaction Details.

**La fuente de datos no funciona.** Preguntándole a la propia Grafana:

```
GET /api/datasources/uid/influxdb-jmeter/health
{"message":"missing organization in datasource configuration error performing
  flux query","status":"ERROR"}
```

**Por qué.** `grafana/datasources/influxdb.yml` escribe los valores así:

```yaml
organization: ${INFLUXDB_ORG:-performance}
defaultBucket: ${INFLUXDB_BUCKET:-jmeter}
token: ${INFLUXDB_TOKEN:-jmeter-token-2024-super-secret}
```

Dos cosas fallan a la vez:

1. La provisión de Grafana **no entiende la sintaxis `${VAR:-valor}`** de bash.
   Solo interpola `$VAR` y `${VAR}`.
2. Y aunque la entendiera, **al contenedor de Grafana no le llega ninguna
   variable `INFLUXDB_*`**: `docker-compose.yml` solo le pasa `GF_*`.
   Comprobado dentro del contenedor: `env | grep -i influx` no devuelve nada.

Resultado, leído de la API de Grafana: `"organization":""`, `"defaultBucket":""`.

### 1.3 `monitoring_config`

Una sola fila, escrita el **5 de marzo de 2026** y nunca corregida:

| Columna | Valor guardado | Valor real | |
|---|---|---|---|
| `grafana_url` | `http://grafana:3000` | correcto dentro de la red | ✔ el frontend lo reescribe a `localhost:3000` para el navegador |
| `grafana_dashboard_uid` | **`jmeter-realtime`** | `jmeter-performance` | ✘ |
| `influxdb_url` | `http://influxdb:8086` | correcto | ✔ |
| `influxdb_org` | **`jmeter-org`** | `performance` | ✘ |
| `influxdb_bucket` | `jmeter` | `jmeter` | ✔ |
| `is_configured` | `true` | — | miente |

Los dos valores malos **no son un error de tecleo de nadie**: son los `default=`
del modelo, `backend/app/db/models/monitoring.py` líneas 19 y 23. La fila nació
con ellos. `jmeter-realtime` **no ha existido nunca** en `grafana/` — lo confirma
`git log -S"jmeter-realtime" -- grafana/`, que no devuelve ningún commit.

Comprobado contra la Grafana viva:

```
/api/dashboards/uid/jmeter-realtime     -> 404
/api/dashboards/uid/jmeter-performance  -> 200
```

Así que la pantalla de Real-Time construye un iframe hacia un tablero que no
existe.

**Quién la usa.** `MonitoringSettings.tsx` (admin) la escribe y
`MonitoringRealtime.tsx` la lee para montar el iframe. `monitoring.py` la sirve
en `GET/PUT /monitoring/config` y la usa en `GET /monitoring/health`, que solo
comprueba que Grafana e InfluxDB **respondan** — no que la fuente de datos
funcione ni que el tablero exista. Por eso el semáforo puede salir verde con
todo roto.

### 1.4 El WebSocket de métricas y el colector

`ws_metrics.py` (99 líneas) sirve `/api/v1/ws/executions/{id}/metrics`. Envía un
JSON cada **5 s** (`METRICS_INTERVAL_SEC = 5` en `stepping_controller.py`) y
acepta `stop`, `pause`, `resume` como texto. El snapshot es:

```
execution_id · timestamp · active_vus · status
total_requests · total_errors · error_rate_percent
avg/p95/p99/max/min_response_time_ms
avg_tps · peak_tps · total_bytes · duration_sec · successful_requests
```

Lo produce `MetricsCollector` (`metrics_collector.py`, 139 líneas), que guarda
**todos los resultados en una lista de Python en memoria** y calcula bajo
demanda. No persiste nada fuera del proceso.

Lo consume **`LiveMetricsChart.tsx`**, montado desde `ExecutionDashboard.tsx`,
con hasta 60 puntos en pantalla.

**Y aquí hay una rotura comprobada.** El componente arma la URL así:

```ts
`ws://${window.location.host}/api/v1/ws/executions/${id}/metrics`
```

`window.location.host` en desarrollo es `localhost:5173`, el dev server de Vite.
Y **`frontend/vite.config.ts` no tiene ningún `proxy`**. Probado con una petición
de upgrade real:

```
contra el backend  (8001):  HTTP/1.1 101 Switching Protocols   ✔
contra Vite        (5173):  sin respuesta (código 000); un GET normal da 403  ✘
```

O sea: **el backend sirve el WebSocket perfectamente, pero en desarrollo el
navegador no puede llegar a él.** En el servidor sí funcionaría, porque nginx
publica frontend y backend bajo el mismo `kinetix.sqasa.co` — no lo he
comprobado en el servidor y no lo afirmo.

### 1.5 El motor propio y InfluxDB

**No escribe en InfluxDB. Nunca.** Tres comprobaciones independientes:

1. `influxdb-client` **no está en `backend/requirements.txt`**.
2. `pip list | grep -i influx` dentro de `jmeter_backend` no devuelve nada.
3. `metrics_collector.py` no menciona InfluxDB por ningún lado; los únicos
   archivos del backend que nombran InfluxDB son los de configuración
   (`monitoring.py`, el modelo, el schema) y los que hablan del **Backend
   Listener de JMeter**, que es otra cosa.

Coherente con la cardinalidad 0 del cubo.

Estado de las ejecuciones del motor propio, por si ayuda a dimensionar:

```
error      23   del 2026-03-13 al 2026-06-22
completed   8   del 2026-06-02 al 2026-06-04
cancelled   1
```

Última actividad: **22 de junio de 2026**, hace tres meses. Ninguna de las ocho
que completaron dejó rastro en InfluxDB, como es de esperar.

### 1.6 Lo que sí existe y no está cableado

`backend/app/services/engine/jmeter_runner.py` (612 líneas) ejecuta **JMeter de
verdad** como subproceso:

```python
JMETER_HOME = os.environ.get("JMETER_HOME", "/opt/apache-jmeter-5.6.3")
```

y está instalado: `/opt/apache-jmeter-5.6.3/bin/jmeter`, con OpenJDK 21.

Tiene dos modos. `patch_jmx_for_smoke()` **desactiva** el Backend Listener (para
no ensuciar InfluxDB con un smoke) y `prepare_full_run_jmx()` lo **activa**, y
acepta un `influxdb_resolver` para reescribir UDVs como `${InfluxdbURL}`.

**Pero el único sitio que la llama no le pasa ese resolver:**

```python
# script_ai.py:4419
prepared_jmx = prepare_full_run_jmx(jmx, data_dir_resolver=data_dir_resolver)
```

Se habilita el listener y se deja su URL sin resolver. El cable está tendido y
sin conectar por un extremo.

---

## 2. La pregunta que decide O1

> ¿Puede un JMeter externo escribir en el InfluxDB de Kinetix y verse en la
> pantalla de monitoreo?

**Escribir: sí, hoy mismo. Verse: no, hasta arreglar la fuente de datos de
Grafana.** Por partes, con la evidencia de cada una.

### 2.1 ¿Llega la red?

| Comprobación | Resultado |
|---|---|
| Puerto publicado | `0.0.0.0:8086->8086`, escuchando en `::` (todas las interfaces) |
| IP de la máquina en la red | **192.168.1.59** (Wi-Fi) |
| Responde en esa IP | `http://192.168.1.59:8086/health` → **200** |
| Perfil de red del Wi-Fi | **Public** |
| Regla de entrada del cortafuegos | «Docker Desktop Backend», perfil **Public**, **Allow**, programa `com.docker.backend.exe`, TCP **cualquier puerto local**, habilitada |

Docker Desktop publica los puertos a través de ese ejecutable, y hay una regla
que lo permite en el perfil que gobierna la Wi-Fi. **La conclusión es que sí
llega**, pero lo digo con su matiz: no he podido probar desde otra máquina,
porque no la tengo. Lo comprobado es la regla y que el servicio responde en la IP
de red, no en loopback. Una prueba desde el portátil de otra persona lo cerraría
en dos minutos.

Y lo mismo vale, de propina, para **Grafana en el 3000, con acceso anónimo
habilitado**: sin credencial ninguna, `GET /api/search?type=dash-db` devuelve
**200** y la lista de tableros. Cualquiera que alcance la máquina ve los
tableros.

### 2.2 ¿Con qué credencial?

Hoy, solo con el token de operador (§1.1). **Lo recomendable es no usarlo**: hace
falta crear un token **acotado al cubo `jmeter` y solo de escritura**. Es una
operación de InfluxDB, no un cambio de código.

### 2.3 Qué habría que configurar en el JMeter del cliente

Un **Backend Listener** con `InfluxdbBackendListenerClient`. Va incluido en el
JMeter 5.6.3 que ya está en el contenedor —comprobado abriendo el jar:

```
ApacheJMeter_components.jar
   org/apache/jmeter/visualizers/backend/influxdb/InfluxdbBackendListenerClient.class
   org/apache/jmeter/visualizers/backend/influxdb/InfluxDBRawBackendListenerClient.class
```

Los nombres de los argumentos, leídos de la propia clase para no inventarlos:
`influxdbUrl`, `influxdbToken`, `application`, `measurement`, `summaryOnly`,
`samplersRegex`, `percentiles`, `testTitle`, `eventTags`.

Que exista `influxdbToken` es lo importante: **este JMeter habla InfluxDB 2.x
con token**, no hace falta la capa de compatibilidad 1.x.

Configuración concreta:

| Argumento | Valor |
|---|---|
| `influxdbUrl` | `http://192.168.1.59:8086/api/v2/write?org=performance&bucket=jmeter` |
| `influxdbToken` | el token acotado de §2.2 |
| `application` | el nombre que identifique **esa** corrida |
| `measurement` | `jmeter` — **no se toca**: el tablero filtra por él |
| `summaryOnly` | `false`, o no hay filas por transacción |
| `samplersRegex` | `.*` |
| `percentiles` | `90;95;99` |

### 2.4 ¿Encajaría el esquema?

Sí, y encaja bien. El listener emite la medida `jmeter` con las etiquetas
`application`, `transaction`, `statut` (`all`/`ok`/`ko`) y `responseCode`, y
campos como `count`, `avg` y `meanAT`. Leído de la clase compilada:

```
TAG_ALL · TAG_OK · TAG_KO · TAG_APPLICATION · TAG_RESPONSE_CODE
",statut="  ",transaction="  ",application="  ",responseCode="  "meanAT="
```

Y las consultas del tablero piden exactamente eso:

```flux
from(bucket: "jmeter")
  |> filter(fn: (r) => r["_measurement"] == "jmeter")
  |> filter(fn: (r) => r["_field"] == "avg")
  |> filter(fn: (r) => r["statut"] == "all")
```

**El tablero se escribió para un JMeter externo, no para el motor propio.** Eso
explica por qué nunca tuvo datos: el motor propio nunca habló ese idioma.

### 2.5 Lo que falta para distinguir una corrida de otra

**Nada lo distingue hoy.** El tablero tiene `"templating": { "list": [] }` —cero
variables— y la palabra `application` **no aparece ni una vez** en sus 874
líneas. Filtra solo por medida y por `statut`.

Consecuencia práctica: si dos personas lanzan a la vez, sus curvas se suman en el
mismo panel y no hay forma de separarlas. **Esto hay que añadirlo**: una variable
de tablero `application` y su filtro en los nueve paneles.

### 2.6 Lo que le falta a la pantalla para enseñar una ejecución que no lanzó el motor

La pantalla de Real-Time es un **iframe de Grafana**: por construcción le da igual
quién escribió los datos. No hay que cambiar su lógica. Le faltan tres cosas:

1. **Que la fuente de datos funcione** (§1.2) — si no, el iframe sale en blanco.
2. **Que el uid apunte al tablero que existe** (§1.3).
3. **Que se pueda elegir la corrida** (§2.5).

Y una cuarta, que es la de verdad: **nada ata un `application` de InfluxDB a una
fila de `test_executions`**. Se podrá ver la corrida en vivo, pero no saltar de
ella a su informe, ni al revés. Eso es diseño, no cableado.

### 2.7 Cuánto es

Sin implementar nada, lo que costaría cada pieza:

| Qué | Dónde | Coste | Quién decide |
|---|---|---|---|
| Token de escritura acotado al cubo | InfluxDB | ~15 min | Fredy (es crear credencial) |
| Arreglar la fuente de datos de Grafana | `docker-compose.yml` + `grafana/datasources/influxdb.yml` | ~20 min + reinicio de Grafana | **Fredy: regla 7** |
| Corregir `jmeter-realtime` → `jmeter-performance` y `jmeter-org` → `performance` | pantalla `/monitoring/settings`, sin SQL | ~5 min | — |
| Que una instalación nueva no nazca rota | `backend/app/db/models/monitoring.py` (2 líneas) | ~10 min | — |
| Variable `application` + filtro en 9 paneles | `grafana/dashboards/jmeter-dashboard.json` | ~1 h | — |
| Configurar el Backend Listener en el JMX del cliente | su JMX | ~10 min por script | — |
| Devolver «Monitoreo» al menú | `Sidebar.tsx` | ~10 min | Fredy: es pantalla suya (regla 31) |
| **Total para «un JMeter externo escribe y se ve, filtrable por corrida»** | | **3–5 h** | |

**Ninguna de esas piezas toca un archivo protegido.**

Lo que **sí** lo tocaría, y por eso no entra sin autorización:

- Que el **motor propio** publique también en InfluxDB. `metrics_collector.py`,
  `stepping_controller.py` y `jmeter_runner.py` viven en
  `backend/app/services/engine/`, y esa **carpeta entera está protegida**
  (CLAUDE.md §11). Además pediría `influxdb-client` en `requirements.txt` →
  reconstrucción del contenedor → decisión de Fredy (regla 7), como pasó con
  `openpyxl` en H3.
- Conectar el `influxdb_resolver` que `prepare_full_run_jmx()` ya acepta:
  el parámetro está en `jmeter_runner.py`, también protegido; quien lo llama
  (`script_ai.py`) no lo está.

---

## 3. El estado de la pantalla de monitoreo

Hay que separar dos pantallas que el nombre confunde.

### 3.1 `/performance/monitoring` — «Métricas Monitoreo». **Funciona.**

No tiene nada que ver con Grafana ni con InfluxDB. Es `MonitoringPage.tsx` (309
líneas): se suben **capturas o CSV** de la infraestructura —CPU, memoria, base de
datos, APM, red, logs— y se analizan con **Gemini Vision**, para que ese análisis
entre en el informe. Es la fuente de los adjuntos `attachment_type='monitoring'`.

Tiene datos y uso real: **67 ejecuciones**, **23 adjuntos de monitoreo** y 8 de
evidencia. Es la única entrada de monitoreo visible en el menú.

### 3.2 `/monitoring/realtime` — el Grafana embebido. **Oculta y rota.**

Desde **el 21 de abril de 2026** (commit `117ec39`, v3.0.0) toda la sección está
comentada en `Sidebar.tsx` con el rótulo:

```
/* OCULTO — Monitoreo Grafana (desarrollo futuro)
```

La ruta sigue existiendo en `App.tsx` y responde si se teclea la URL. Si se
teclea, fallan tres cosas a la vez, en este orden:

1. El iframe pide `/d/jmeter-realtime` → Grafana devuelve **404**.
2. Aunque el uid fuera el bueno, la fuente de datos responde **«missing
   organization»** y los paneles saldrían vacíos.
3. Y aunque funcionara, **el cubo está vacío**.

`MonitoringRealtime.tsx` está bien hecho —selector de rango, auto-refresco,
pantalla completa, y reescribe `grafana:3000` a `localhost:3000` para que el
navegador llegue—. El componente no es el problema.

**Desde cuándo está rota: desde siempre.** Los valores malos son los `default=`
del modelo, la fila se creó el 5 de marzo de 2026 con ellos, y el uid
`jmeter-realtime` nunca existió en la provisión de Grafana. No hubo un día en que
funcionara.

---

## 4. El terreno para O2 — solo inventario

Qué se podría observar **de este equipo de desarrollo**, sin instalar nada y sin
tocar el servidor de producción. Solo el listado; no me he conectado a nada de
producción.

### 4.1 Postgres de Kinetix

Ya sirve, sin instalar nada, las vistas de siempre: `pg_stat_database`,
`pg_stat_activity`, `pg_stat_user_tables`, `pg_statio_user_tables`,
`pg_locks`. Muestra real de ahora mismo:

```
conexiones 6 · commits 38.408 · rollbacks 882
bloques en caché 2.656.974 · leídos de disco 1.343 · aciertos 99,95 %
tuplas devueltas 7.251.533 · interbloqueos 0
```

Da: conexiones vivas y qué consulta corre cada una, tasa de acierto de caché,
transacciones por segundo, interbloqueos, tablas que más crecen, índices sin uso.

**Credencial:** la que ya existe, `jmeter_user` / `jmeter_secure_2024` sobre
`jmeter_analyzer_db`. Para métricas de todo el clúster haría falta un rol con
`pg_monitor`.

**Lo que falta y no se puede dar por hecho:** `pg_stat_statements` —la vista que
dice qué consulta consume el tiempo— está **disponible pero no instalada**:

```
pg_stat_statements | (sin versión instalada)
pg_buffercache     | (sin versión instalada)
pgstattuple        | (sin versión instalada)
```

Instalarla pide `shared_preload_libraries` en la configuración del servidor **y
reiniciar Postgres**. Eso ya no es observar: es cambiar. Decisión de Fredy.

### 4.2 Los contenedores, por el socket de Docker

**Hoy no hay forma sin cambiar algo.** Comprobado:

- `docker.sock` **no se monta en ningún servicio** de `docker-compose.yml` ni de
  `docker-compose.prod.yml`.
- La API de Docker **no está publicada por TCP**: nada escucha en 2375 ni 2376.
  En Windows solo está el *named pipe* local.

Daría: CPU, memoria, red y disco por contenedor, reinicios, estado de salud,
y los logs. Es lo que consume un `cAdvisor` o el propio `docker stats`.

**Credencial:** acceso al socket. En Linux, montarlo de solo lectura en el
contenedor que recoja. **Montar el socket de Docker en un contenedor le da
control de todo el demonio**, así que no es un cambio menor y conviene decirlo
antes que después.

### 4.3 El sistema anfitrión

Windows 11 con Docker Desktop. Sin instalar nada, ya se puede leer por
PowerShell/WMI: CPU, memoria, disco, red por interfaz, procesos, y los puertos en
escucha —de hecho es como comprobé lo del §2.1—.

Daría: si la máquina se queda sin memoria mientras corre una prueba, si el disco
es el cuello de botella, si el propio Docker Desktop se está comiendo la CPU.

**Credencial:** la sesión del usuario actual; para algunos contadores, permisos
de administrador local. Para que esos números lleguen a InfluxDB haría falta un
agente (Telegraf es el natural, y ya hay permisos `write:/telegrafs` en el
token), y eso **es instalar**: decisión de Fredy.

---

## 5. Propuesta de sub-pasos para O1

En este orden, porque cada uno depende del anterior.

| Sub-paso | Qué hace | Qué toca | ¿Protegido? |
|---|---|---|---|
| **O1.2** | Arreglar la fuente de datos de Grafana: pasarle las variables de InfluxDB al contenedor y quitar la sintaxis `${VAR:-valor}` que no entiende. Prueba de aceptación: `/api/datasources/uid/influxdb-jmeter/health` responde `OK` | `docker-compose.yml`, `grafana/datasources/influxdb.yml` | No. **Pero el compose y el reinicio de Grafana son de Fredy (regla 7)** |
| **O1.3** | Corregir `monitoring_config` desde la pantalla de configuración, y cambiar los dos `default=` del modelo para que una instalación nueva no nazca rota | `backend/app/db/models/monitoring.py` (2 líneas) | No |
| **O1.4** | Token acotado al cubo `jmeter`, solo escritura. Prueba de punta a punta con un JMX de prueba lanzado desde el JMeter que ya está en el contenedor, con su Backend Listener. Datos marcados `ZZTEST-` (regla 29) | ninguno | No |
| **O1.5** | La etiqueta de corrida: variable `application` en el tablero y su filtro en los nueve paneles. Convención de nombre para que una corrida se identifique | `grafana/dashboards/jmeter-dashboard.json` | No |
| **O1.6** | Devolver «Monitoreo» al menú y decidir qué enseña. **Antes de tocar `Sidebar.tsx`, avisar a Fredy y esperar (regla 31)** | `Sidebar.tsx` | No |
| **O1.7** | *Decisión, no código:* ¿se deja el 8086 abierto a la red y Grafana en anónimo? Hoy lo están. Con clientes escribiendo desde fuera esto pasa de descuido a superficie de ataque | — | — |

**Fuera de O1, y solo con autorización expresa:** que el motor propio publique en
InfluxDB. Toca `backend/app/services/engine/`, carpeta protegida entera, y añade
`influxdb-client` a `requirements.txt`, que obliga a reconstruir el contenedor.
Se plantea como O3 aparte, no colado dentro de O1.

---

## 6. Lo que no he comprobado (regla 33)

- **No he probado desde otra máquina** que el 8086 y el 3000 se alcancen por la
  red. Lo que sí está comprobado: que escuchan en todas las interfaces, que
  responden en `192.168.1.59`, y que hay una regla de entrada habilitada para
  `com.docker.backend.exe` en el perfil que gobierna la Wi-Fi. La conclusión es
  firme, la prueba definitiva la da un `curl` desde otro portátil.
- **No he comprobado el WebSocket en el servidor.** Lo medido es en desarrollo:
  el backend hace el upgrade y Vite no. Que nginx lo haga bien en
  `kinetix.sqasa.co` es plausible pero no lo he visto.
- **No he escrito ni un punto en InfluxDB** para verificar el camino completo del
  Backend Listener. Eso es O1.4, con permiso y con datos marcados.
- **No me he conectado a nada del servidor de producción.** El §4 es inventario
  de este equipo.
