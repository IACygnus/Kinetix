958cba9 · 2026-09-21

# ETAPA O1 — el monitoreo de la prueba en vivo

**0 llamadas a la IA.** `pg_dump` antes de empezar (regla 32). Diagnóstico
previo: reporte **96**.

---

## 0. La copia de seguridad, y el permiso

```
C:\proyectos\Kinetix_pruebas\backup_20260921_O1.sql   6.727.185 bytes
25 tablas · time_entries dentro
```

Y antes de tocar pantalla, la comprobación de la regla 31: **ninguna petición
desde el navegador de Fredy (`172.18.0.1`) en 48 horas.** El log del backend solo
tenía sondeos de salud desde `127.0.0.1`.

---

## 1. O1.2 — la fuente de datos y los puertos

### 1.1 Por qué no funcionaba

Dos fallos a la vez, cada uno suficiente:

1. `grafana/datasources/influxdb.yml` escribía `${INFLUXDB_ORG:-performance}`.
   Esa forma con valor por defecto es de **bash**, no de Grafana: Grafana solo
   interpola `$VAR` y `${VAR}`.
2. Y aunque la entendiera, **al contenedor de Grafana no le llegaba ninguna
   variable `INFLUXDB_*`**: `docker-compose.yml` solo le pasaba las `GF_*`.

Resultado: `organization: ""` y la fuente respondiendo «missing organization in
datasource configuration».

### 1.2 El arreglo

El valor por defecto se resuelve **en Compose**, que sí entiende esa sintaxis, y
lo que llega al contenedor ya es un valor:

```yaml
# docker-compose.yml, servicio grafana
- INFLUXDB_ORG=${INFLUXDB_ORG:-performance}
- INFLUXDB_BUCKET=${INFLUXDB_BUCKET:-jmeter}
- INFLUXDB_TOKEN=${INFLUXDB_TOKEN:-jmeter-token-2024-super-secret}
```

```yaml
# grafana/datasources/influxdb.yml
organization: ${INFLUXDB_ORG}
defaultBucket: ${INFLUXDB_BUCKET}
token: ${INFLUXDB_TOKEN}
```

Con un `deleteDatasources` delante, para que un arranque sobre el volumen que ya
guarda la fuente mal escrita la reemplace en vez de conservarla.

### 1.3 O-D1 — los puertos, solo en el equipo

```yaml
- "127.0.0.1:${INFLUXDB_PORT:-8086}:8086"
- "127.0.0.1:${GRAFANA_PORT:-3000}:3000"
```

Vaciar la lista de `ports` **no cierra nada** —Compose fusiona, no reemplaza; es
la lección de la Etapa 6.6—: hay que publicar en una interfaz concreta.

Comprobado con `docker compose config`, que es solo lectura:

```
host_ip: 127.0.0.1   target: 3000   published: "3000"
host_ip: 127.0.0.1   target: 8086   published: "8086"
INFLUXDB_BUCKET: jmeter
INFLUXDB_ORG: performance
INFLUXDB_TOKEN: jmeter-token-2024-super-secret
```

### 1.4 Lo que falta: el reinicio

**Es de Fredy (regla 7).** El comando exacto está en §7. Hasta que lo aplique,
la fuente de datos sigue rota y los puertos siguen abiertos a la red: lo de
arriba está preparado y comprobado en la configuración renderizada, **no en
caliente**.

---

## 2. O1.3 — la configuración de monitoreo

La fila de `monitoring_config` apuntaba a un tablero y a una organización que no
existen. **No fue un tecleo de nadie**: eran los `default=` del modelo.

Corregido por el propio endpoint del producto —`PUT /monitoring/config`—, no con
SQL:

```
ANTES : uid «jmeter-realtime»   · org «jmeter-org»   · 2026-03-05
DESPUÉS: uid «jmeter-performance» · org «performance» · 2026-09-21
```

Y los dos `default=` de `backend/app/db/models/monitoring.py` cambiados, para que
una instalación nueva no vuelva a nacer rota.

**Un tercer fallo que apareció aquí.** El token que había guardado **no se puede
descifrar** con la `FERNET_KEY` actual: se cifró con otra. Comprobado en proceso,
`InvalidToken`. Por eso `/monitoring/health` daba `influxdb_status: error` con el
mensaje vacío. Quedó sustituido por el token nuevo de O1.4.

---

## 3. O1.4 — el token acotado y la prueba de punta a punta

### 3.1 O-D2 — el token

```
ID          115d29f5e0945000
Descripción kinetix-jmeter-escritura
Permisos    [write:orgs/…/buckets/b944c355e16718f0]
```

Un solo permiso: escribir, y solo en el cubo `jmeter`. Comprobado, no supuesto:

| Prueba | Respuesta |
|---|---|
| Escribir en `jmeter` | **204** |
| Leer de `jmeter` | **404** — «could not find bucket "jmeter"»: ni siquiera lo ve |
| Escribir en `_monitoring` | **403** |
| Listar tokens | 200, pero con **la lista vacía**: no hay fuga |

El de operador —que puede `write:/authorizations`, `write:/users` y
`write:/buckets`— no se enseña en ninguna pantalla ni sale del servidor.

### 3.2 La prueba con JMeter, y un error mío por el camino

El JMeter 5.6.3 que ya vive en `jmeter_backend` lanzó un JMX pequeño (3 hilos ×
20 vueltas, 60 peticiones) con su Backend Listener. **Los primeros dos intentos
perdieron todas las filas por transacción:**

```
ERROR o.a.j.v.b.i.HttpMetricsSender: responseCode: 422
  field type conflict: input field "count" on measurement "jmeter"
  is type float, already exists as type integer  dropped=3
```

La causa fui yo. Al probar el alcance del token en §3.1 escribí a mano
`count=1i` —un entero— y **la primera escritura fija el tipo del campo para todo
el *shard***. JMeter lo manda flotante y a partir de ahí InfluxDB lo rechazaba.

Borrar mi punto no bastó: el tipo siguió fijado. Hubo que borrar la medida
entera. Antes de hacerlo comprobé que **todo lo que había en el cubo era mío y
llevaba la marca**:

```
tagValues(application) -> zztest-alcance · zztest-o14-… · zztest-o14b-…
filas que NO empiezan por zztest-  -> ninguna
```

Y el cubo tenía **cardinalidad 0** esa misma mañana (reporte 96 §1.1): no había
nada de nadie. Borrado por la marca, no por diferencia (reglas 29 y 30).

Tras eso, a la primera:

```
summary =  60 in 00:00:07 = 8.1/s  Err: 0 (0.00%)
errores del Backend Listener: 0
```

### 3.3 Y los datos entran por donde el tablero los busca

La consulta **exacta** del panel «Response Time Over Time», contra los datos
nuevos:

```
application                  transaction     _value
zztest-o14c-20260921-1555    ZZTEST salud    2.1219512195121952
zztest-o14c-20260921-1555    all             2.0833333333333330
```

Con `summaryOnly=false` se ve la transacción por su nombre, no solo el total.

---

## 4. O1.5 — la corrida como filtro

El tablero tenía `"templating": { "list": [] }` y la palabra `application` no
aparecía ni una vez en sus 874 líneas: dos pruebas a la vez se superponían.

Ahora lleva la variable **«Corrida»** y sus nueve paneles filtran por ella:

```
variable «application» anadida · consultas con filtro nuevo: 9 · ya lo tenian: 0
```

Comprobado **contra la Grafana viva**, que recarga la provisión sola cada 10 s
(`updateIntervalSeconds: 10`), sin reinicio:

```
titulo   : JMeter Performance Testing Dashboard
variables: ['application']
paneles con el filtro de corrida: 9 de 9
```

---

## 5. O1.6 — la pantalla

### 5.1 El nombre de la corrida (O-D4)

`nombre_de_corrida()` en `monitoring.py`, una sola definición:

```
Compensar     + prueba final   -> compensar-prueba-final-20260921-1600
Bogotá Región + App Móvil 2.0  -> bogota-region-app-movil-2-0-20260921-1600
```

Minúsculas, sin tildes, sin espacios. Y es **la misma cadena** que viaja en la
etiqueta `application` del Backend Listener y en `?var-application=` del tablero
embebido: lo que se copia y lo que se mira no pueden discrepar, porque es el
mismo dato.

### 5.2 Los endpoints

| Verbo | Path | Qué da |
|---|---|---|
| GET | `/monitoring/proyectos?client_id=` | Los proyectos ya usados con ese cliente. Solo sugerencias |
| GET | `/monitoring/jmeter-config?client_id=&proyecto=` | Los diez parámetros, rellenos |
| GET | `/monitoring/jmeter-fragmento?client_id=&proyecto=` | El componente en XML, descargable |

El fragmento `.jmx` **no necesitó ninguna dependencia nueva**: es texto armado a
mano, con su escapado. Comprobado que parsea como XML y que el `&` de la URL sale
como `&amp;`.

Los dos primeros son de `admin` y `analyst`. El token va en la respuesta a
propósito —la pantalla existe para entregarlo— y por eso es el de O-D2, que solo
escribe en un cubo.

### 5.3 La pantalla

`frontend/src/pages/MonitoreoVivoPage.tsx`, en **Análisis → Monitoreo en vivo**.
Cliente y proyecto arriba; el nombre de la corrida en la banda azul con su botón
de copiar y la descarga del `.jmx`; los diez parámetros en tabla, cada uno con su
explicación en una línea y su botón; y abajo el tablero filtrado, con selector de
rango y de refresco.

El token sale **tapado** hasta pulsar «Ver el token», para que no se cuele en una
captura. Todo lo que se pulsa tiene 44 px de alto mínimo.

### 5.4 La validación

`o16_pantalla.py`, nueva. Hace el recorrido entero del guion de Fredy: genera la
configuración en la pantalla, **lee de la pantalla** la URL, el token y el nombre
de la corrida, lanza un JMeter de verdad con esos mismos valores y comprueba que
los puntos llegan a InfluxDB bajo esa corrida.

```
O1.6 — MONITOREO EN VIVO, DE PUNTA A PUNTA: TODO PASA   (25 comprobaciones)
```

Hizo falta un `rele_3000.py` —hermano del `rele_5173.py`— porque el navegador de
las pruebas corre dentro de `jmeter_backend`, donde el 3000 no es de nadie.

---

## 6. O1.7 — la regresión, en serie

| # | Suite | Comprobaciones |
|---|---|---|
| 1 | `pytest` | 670 pasan · 1 falla ajena (ver abajo) |
| 2 | `tsc --noEmit` | limpio |
| 3 | `h13_backend.sh` | 24 |
| 4 | `h15_pantallas.py` | 22 |
| 5 | `h22_backend.py` | 45 |
| 6 | `h2b2_backend.py` | 53 |
| 7 | `h2b3_pantalla.py` | 36 |
| 8 | `h32_consulta.py` | 53 |
| 9 | `h52_informe.py` | 60 |
| 10 | `h53_h54_documento.py` | 54 |
| 11 | `h6_ajustes.py` | 54 |
| 12 | `h71_portada.py` | 27 |
| 13 | `h7_pantallas_horas.py` | 36 |
| 14 | `o16_pantalla.py` | **25** |

**489 comprobaciones, todas verdes.** Doce suites, una detrás de otra, ninguna a
la vez que otra (regla 34 y la lección del reporte 88).

Y la base de Fredy, antes y después de la corrida entera:

```
=== ANTES ===   86f88bf73ffe47f15226188e5c58caaa   ·   24 10 8 13 5 5
=== DESPUÉS === 86f88bf73ffe47f15226188e5c58caaa   ·   24 10 8 13 5 5
SI — la base de Fredy no cambio ni una fila
suites: 12 · con fallo: 0
```

**El fallo de `pytest` sigue siendo el de siempre y no es de aquí:**
`test_analysis_pipeline` parchea `analysis_pipeline.time`, que el commit
`c3e3bb4` (13 de agosto de 2026) retiró del módulo. Ya estaba documentado en el
reporte 94 §6.

### 6.1 Un tropiezo del camino, que dejó regla

El backend de pruebas del 8002 arrancaba **sin `--reload`**, así que se quedaba
con el código del arranque: la suite nueva chocó contra un `404` en
`/monitoring/jmeter-config` aunque el endpoint estuviera escrito.
`scripts/preparar_base_de_pruebas.sh` ya lo levanta con `--reload`, igual que el
backend de siempre.

---

## 7. Lo que tiene que hacer Fredy

Reiniciar **dos contenedores** para que se apliquen el cierre de puertos (O-D1) y
la fuente de datos arreglada. No se reconstruye ninguna imagen:

```
cd C:\proyectos\Kinetix
docker compose up -d influxdb grafana
```

Los datos no se pierden: viven en los volúmenes `influxdb_data` y `grafana_data`.

Cuando esté, queda por comprobar —y lo compruebo yo en cuanto avise—:

```
1) la fuente de datos responde OK
   docker exec jmeter_backend curl -s -u admin:admin \
     http://jmeter_grafana:3000/api/datasources/uid/influxdb-jmeter/health

2) el 8086 y el 3000 ya NO responden por la IP de la red
   curl http://192.168.1.59:8086/health     (debe fallar)
   curl http://192.168.1.59:3000/api/health (debe fallar)
```

---

## 8. Lo que no se ha comprobado (regla 33)

- **La aceptación de O1.2 está pendiente del reinicio.** Lo comprobado es la
  configuración renderizada por `docker compose config`, no el comportamiento en
  caliente. Mientras tanto la fuente de datos **sigue rota** y los puertos
  **siguen abiertos**.
- **No he probado desde otra máquina** que los puertos queden cerrados. Igual que
  en el reporte 96: la prueba definitiva es un `curl` desde otro portátil.
- **Fredy no ha validado nada de O1**, ni H5, H6 o H7.
- **El WebSocket del motor propio no se tocó** (O-D7). Sigue sin llegar al
  navegador en desarrollo, por lo que dice el reporte 96 §1.4. Va con O3.
- **El motor propio sigue sin publicar en InfluxDB.** Ponerlo toca
  `services/engine/`, carpeta protegida, y añade `influxdb-client` a
  `requirements.txt`. **No entró en esta etapa y no se tocó nada de esa carpeta.**
- **En `jmeter_analyzer_test` sigue la fila suelta** `proyecto h1.3` del reporte
  94 §7. No se toca: la regla 28 dice que si hay que borrar algo, se para y se
  pide.

---

## 9. Estado

**Etapa O1 implementada, pendiente de validación de Fredy** — y con el reinicio
de `influxdb` y `grafana` pendiente de que él lo aplique.
