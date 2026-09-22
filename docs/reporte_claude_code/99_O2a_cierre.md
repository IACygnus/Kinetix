2ebb65b · 2026-09-22

# ETAPA O2a — el laboratorio y el monitoreo sin agente

**0 llamadas a la IA.** `pg_dump` antes de empezar (regla 32). Diagnóstico y
etapa previa: reportes **96**, **97** y **98**.

---

## 0. Antes de nada: la copia, y la comprobación de O1.2

```
C:\proyectos\Kinetix_pruebas\backup_20260921_O2a.sql   6.727.271 bytes
```

Fredy reinició `influxdb` y `grafana`, y las **dos aceptaciones que el reporte 97
§7 dejaba pendientes pasan**:

| Comprobación | Resultado |
|---|---|
| La fuente de datos de Grafana | `{"message":"datasource is working. 3 buckets found","status":"OK"}` |
| `192.168.10.3:8086` (la IP de la red) | rechaza la conexión |
| `192.168.10.3:3000` | rechaza la conexión |
| `127.0.0.1:8086` y `:3000` | siguen respondiendo `200` |

O-D1 y la fuente de datos quedan **cerrados**. Lo que sigue pendiente de
comprobar desde **otra máquina** sigue igual que en el reporte 97: aquí solo se
ha probado desde este equipo.

---

## 1. O2a.1 — el laboratorio (O-D8, O-D9)

`docker-compose.lab.yml`, 165 líneas, **proyecto de Compose aparte**
(`-p kinetix_lab`). No redefine ni un servicio de Kinetix y no puede reiniciarle
nada por accidente. Tres contenedores:

| Contenedor | Qué es | Redes |
|---|---|---|
| `lab_db` | PostgreSQL 15 con `pg_stat_statements` cargada al arrancar | `kinetix_lab` |
| `lab_servidor` | Ubuntu 22.04 con SSH y una tienda pequeña | `kinetix_lab` + `kinetix_jmeter_network` |
| `lab_colector` | Telegraf 1.29 | `kinetix_lab` + `kinetix_jmeter_network` |

La red de Kinetix se declara **externa**: se usa, no se toca. La necesitan dos, y
por motivos distintos: `lab_servidor` para que el JMeter que vive dentro de
`jmeter_backend` pueda pegarle —es el inyector—, y `lab_colector` para escribir
en `influxdb:8086`.

**Publicado a la red: nada.** Lo único que sale al equipo es el `8090`, y solo en
`127.0.0.1`, para poder mirar la aplicación a mano.

### 1.1 La aplicación, y una corrección de volumen

Cuatro endpoints, con `psycopg2` del paquete de Ubuntu: **ni un `pip install`, ni
una dependencia nueva en Kinetix**.

La primera siembra fue de 200.000 productos y **no valía**: PostgreSQL los
recorre en paralelo y la búsqueda «pesada» tardaba 50 ms. Con 1.500.000
productos y 200.000 pedidos (425 MB) la diferencia se ve:

| Endpoint | Tiempo | Qué hace |
|---|---|---|
| `GET /salud` | **4 ms** | no toca la base |
| `GET /productos` | **8 ms** | consulta por índice |
| `POST /pedidos` | **6 ms** | inserción, responde `201` |
| `GET /buscar` | **550-750 ms** | recorre 1.500.000 filas sin índice |

150 veces más cara que la barata. Eso es lo que hace que la prueba de §3 tenga
algo que enseñar.

---

## 2. O2a.2 — el recolector (O-D10 a O-D16)

### 2.1 Cómo se lee un Linux sin instalarle nada

`lab/colector/linux_sin_agente.py`, 476 líneas. Telegraf lo ejecuta desde
`[[inputs.exec]]` con `data_format = "influx"`: el programa escribe por la salida
estándar **exactamente lo que escribiría un complemento nativo**, y para Telegraf
es indistinguible.

**Una sola conexión SSH por intervalo y por servidor.** Se piden todos los
ficheros de golpe y se reparten dentro. Un cliente pregunta cuántas conexiones
abrimos, y la respuesta tiene que ser un número pequeño.

### 2.2 La paridad con el complemento nativo, comprobada — no declarada

O-D13 promete los mismos nombres de medida y de campo. Una promesa así no se
declara: se comprueba. Y **aquí se puede comprobar de verdad**, porque `/proc`
no está separado por contenedor: el recolector y `lab_servidor` miran la misma
máquina anfitriona para CPU, memoria y disco, así que los dos caminos son
directamente comparables.

`lab/colector/comparar_con_nativo.py` levanta un Telegraf con los complementos
**nativos** 25 segundos, corre el lector por SSH, y compara campo a campo:

| Medida | Campos idénticos | Solo el nativo | Solo el nuestro |
|---|---|---|---|
| `cpu` | 10 | — | — |
| `mem` | 34 | — | — |
| `disk` | 8 | — | — |
| `diskio` | 11 | — | — |
| `system` | 6 | — | `n_users` |
| `net` | **90** | — | — |
| `processes` | 11 | — | — |
| **Total** | **69 comparables + 90 de red** | **0** | **1** |

```
Medidas que solo tenemos nosotros: procesos_top
Medidas nativas que no reproducimos: ninguna
Campos que solo trae el nativo: 0
```

La primera pasada dejaba 87 campos fuera. Se añadieron los tres grupos que
faltaban en vez de declararlos como perdidos:

- **memoria alta/baja** (`high_free`, `high_total`, `low_free`, `low_total`): no
  existen en `/proc/meminfo` de un x86_64 y el nativo **los publica a cero
  igualmente**. Se copia esa decisión para que la lista sea la misma.
- **`total_threads`**, de `ps -eo nlwp=`.
- **los 82 contadores de `/proc/net/snmp`** (`tcp_retranssegs`,
  `tcp_currestab`, `udp_inerrors`…). En una prueba de carga son de los datos más
  útiles que hay: reproducirlos costaba veinte líneas.

**Lo único que no es nativo es `procesos_top`**, y se llama distinto **a
propósito**: el complemento `procstat` pide un estado por PID que aquí no hay, y
en O2b van a convivir los dos. Confundirlos sería peor que no tenerlo.

### 2.3 Lo que hay que decir sobre lo que se está midiendo

Esto no es un matiz, es la diferencia entre un dato y un dato mal leído:

| Medida | En este laboratorio mide… |
|---|---|
| `cpu`, `mem`, `disk`, `diskio`, `system` | **la máquina anfitriona entera**, no el contenedor. `/proc` no está separado por espacios de nombres, y el complemento nativo corriendo dentro del contenedor diría exactamente lo mismo |
| `net`, `processes` | **sí son del contenedor**: la red y los PID sí están separados |
| `docker_container_*` | el contenedor, y solo él |

En un servidor o una máquina virtual de verdad —que es el caso de un cliente—
los primeros son del servidor y no hay ambigüedad. Aquí, con contenedores
haciendo de servidores, hay que saberlo. Por eso el tablero enseña las dos
cosas: la máquina por SSH y el contenedor por el socket de Docker.

### 2.4 PostgreSQL sin agente (O-D12)

Medida `postgresql`, la nativa, con sus 35 campos (`numbackends`, `xact_commit`,
`blks_hit`, `blks_read`, `blk_read_time`, `deadlocks`, `temp_bytes`…). Y cuatro
consultas por `postgresql_extensible` —que también es maquinaria nativa, solo el
SQL es nuestro— para lo que la nativa no trae: `postgresql_actividad`,
`postgresql_bloqueos`, `postgresql_consultas_lentas` y `postgresql_tamano`.

El rol `kinetix_lector` tiene `pg_monitor` y **nada más**. Comprobado en §3, no
supuesto.

### 2.5 El cubo y el token (O-D15)

```
cubo        infra          id 339a1d628e46bae9   retencion 720h
token       kinetix-infra-escritura
permisos    [write:orgs/fea51f27d2fe936f/buckets/339a1d628e46bae9]
```

Un solo permiso: **escribir, y solo en `infra`**. El token maestro no se usa ni
se copia a ningún sitio. Al regenerarlo por segunda vez el guion creó un token
duplicado —la detección leía el JSON con una expresión que no casaba— y **lo
revoqué**: era mío, de cinco minutos antes, y quedó uno solo.

### 2.6 La corrida, sin reiniciar nada (O-D14)

`lab/colector/telegraf.d/00-corrida.conf` lleva una sola línea con la etiqueta.
`scripts/lab_corrida.sh` la reescribe y le manda a Telegraf una señal **HUP**:
recarga la configuración sin reiniciar el contenedor y sin perder un intervalo.

---

## 3. O2a.3 — la prueba que importa

`scripts/lab_prueba_correlacion.sh`. Pide la configuración **a los mismos
endpoints que la pantalla «Monitoreo en vivo»** de O1, pone esa corrida en el
recolector, y mide tres ventanas seguidas con la misma etiqueta:

```
corrida: zztest-laboratorio-o2a-zztest-tienda-20260922-1333
reposo 70s · prueba 120s · reposo 70s

summary = 1200 in 00:02:03 = 9.8/s  Avg: 967  Max: 8824  Err: 0 (0.00%)
```

| | reposo antes | **durante la prueba** | reposo después |
|---|---|---|---|
| CPU de la máquina (por SSH) | 10,21 % | **89,19 %** | 20,11 % |
| CPU del contenedor de la app | 3,82 % | **12,03 %** | 3,41 % |
| CPU del contenedor de la base | 0,00 % | **672,16 %** | 0,04 % |
| Transacciones de PostgreSQL | 0,60 tx/s | **13,18 tx/s** | 0,73 tx/s |

**20 comprobaciones, todas verdes.** La base se llevó casi siete núcleos: la
búsqueda sin índice hizo su trabajo.

### 3.1 La consulta de la aceptación, y su resultado

Las dos series salen de **cubos distintos** y se unen por **una sola cadena**:

```flux
prueba = from(bucket: "jmeter")
  |> range(start: -40m)
  |> filter(fn: (r) => r["application"] == "zztest-laboratorio-o2a-zztest-tienda-20260922-1333")
  |> filter(fn: (r) => r["_field"] == "avg" and r["statut"] == "all")
  |> aggregateWindow(every: 30s, fn: mean, createEmpty: false)
  |> map(fn: (r) => ({ _time: r._time, serie: "respuesta_ms", valor: r._value }))

servidor = from(bucket: "infra")
  |> range(start: -40m)
  |> filter(fn: (r) => r["corrida"] == "zztest-laboratorio-o2a-zztest-tienda-20260922-1333")
  |> filter(fn: (r) => r["_measurement"] == "cpu" and r["_field"] == "usage_idle")
  |> aggregateWindow(every: 30s, fn: mean, createEmpty: false)
  |> map(fn: (r) => ({ _time: r._time, serie: "cpu_en_uso", valor: 100.0 - r._value }))

union(tables: [prueba, servidor])
  |> pivot(rowKey: ["_time"], columnKey: ["serie"], valueColumn: "valor")
  |> sort(columns: ["_time"])
```

```
,_time                  ,cpu_en_uso          ,respuesta_ms
,2026-09-22T13:34:30Z   ,9.762552            ,
,2026-09-22T13:35:00Z   ,10.395875           ,
,2026-09-22T13:35:30Z   ,77.406850           ,618.246985
,2026-09-22T13:36:00Z   ,94.016869           ,938.200000
,2026-09-22T13:36:30Z   ,92.993497           ,1062.135000
,2026-09-22T13:37:00Z   ,92.346585           ,1049.597142
,2026-09-22T13:37:30Z   ,31.541473           ,
,2026-09-22T13:38:00Z   ,11.773383           ,
,2026-09-22T13:38:30Z   ,10.419328           ,
```

La CPU sube a la vez que el tiempo de respuesta y bajan juntas. **Esto es la
prueba de que el modo sin agente sirve para algo**, y no hay forma de obtenerla
sin la etiqueta compartida de O-D14.

### 3.2 Los permisos, comprobados

```
PASA  | leer 'productos' con el rol del recolector da permiso denegado
PASA  | pero si puede leer las vistas de estadistica
```

Y en el panel de consultas lentas aparece la búsqueda pesada, **con los
literales ya normalizados por PostgreSQL** —que es exactamente lo que el
documento de permisos le promete a un cliente—:

```
SELECT p.categoria, count(*) AS cuantos, round(avg(p.precio), $1) AS medio,
       sum(p.existencias) AS existencias FROM produ…   310 llamadas   3.701 ms de media
```

---

## 4. O2a.4 — el tablero

`grafana/dashboards/infraestructura.json`, uid `kinetix-infraestructura`,
provisionado igual que el de JMeter y recogido por la Grafana viva sin
reiniciar. Cuatro filas: el servidor, la base de datos, los contenedores, y las
dos líneas de tiempo juntas.

**13 paneles, y los 13 filtran por la variable «Corrida».** Y no se afirma que
pinten algo: `probar_tablero.py` saca la consulta de cada panel del JSON, le
pone la corrida de verdad y la lanza contra InfluxDB.

```
O2a.4 — LOS 13 PANELES DEVUELVEN DATOS: TODO PASA   (15 comprobaciones)
```

El panel de abajo lleva **dos consultas, una por cubo**, con el tiempo de
respuesta a la izquierda y la CPU a la derecha. Es la §3.1 dibujada.

---

## 5. O2a.5 — el documento de permisos

`docs/observabilidad/requisitos-sin-agente.md`, 263 líneas, **redactado para
enviarlo a un cliente**. Por cada tipo de servidor dice qué usuario, con qué
permisos, qué puerto y en qué dirección, qué datos se leen y **cuáles no**.

Tres cosas que no están ahí por rellenar:

- **De `pg_stat_activity` no se lee el texto de la consulta**, que puede traer
  valores reales. De `pg_stat_statements` sí, pero es el texto normalizado. Y si
  la política del cliente no permite ni eso, **se apaga esa consulta** y se
  pierde un panel; se dice cómo.
- **De `ps` se toma `comm`, no `args`**, porque una línea de órdenes puede llevar
  una contraseña dentro.
- **Lo de Docker (O-D16) va con su aviso en negrita**: quien puede leer el socket
  puede tomar la máquina anfitriona. Se implementa en el laboratorio; a un
  cliente no se le pide sin enseñarle esa sección. Y si dice que no, no se pierde
  casi nada.

La sección 8 dice lo que **no** cubre: Windows, otros motores, colas y cachés, y
el modo con agente.

---

## 6. O2a.6 — la regresión

Todas las suites en serie contra `jmeter_analyzer_test` por el 8002 (regla 34),
con la huella de la base de Fredy antes y después:

```
=== LA BASE DE FREDY, ANTES ===        === LA BASE DE FREDY, DESPUES ===
86f88bf73ffe47f15226188e5c58caaa       86f88bf73ffe47f15226188e5c58caaa
24 10 8 13 5 5                         24 10 8 13 5 5

SI — la base de Fredy no cambio ni una fila
suites: 13 · con fallo: 0
```

**504 comprobaciones, todas verdes.** Doce suites de siempre más
`probar_tablero.py`, nueva.

---

## 7. Los cuatro tropiezos, que dejan lección

### 7.1 `user: root` en el compose puede no significar nada

El `entrypoint` de la imagen oficial de Telegraf termina en
`exec su-exec telegraf "$@"`: **el proceso baja de privilegios aunque el
contenedor arranque como root**. `user: root` engañaba, y el síntoma era un
`exit status 1` sin explicación. Los dos permisos que hacen falta —escribir el
estado y leer el socket— se resuelven en el `Dockerfile`, sobre ese usuario.

### 7.2 Un volumen con nombre recuerda la propiedad del día que nació

Puesto el `chown` en el `Dockerfile`, seguía fallando: el volumen ya existía y
conservaba `root:root`. **El `chown` de una imagen no alcanza nunca a un volumen
que ya tiene contenido.** Se quitó el volumen: el estado es la lectura anterior
de la CPU y perderla al reiniciar cuesta un intervalo.

### 7.3 Una barra invertida al final de una etiqueta rompe la línea entera

Arreglados los permisos, apareció `metric parse error`. El montaje de Windows
sale en `df` como dispositivo `C:\`, y en protocolo de línea **una barra
invertida al final de un valor se come la coma que la sigue**. Una sola línea
mala y Telegraf tira el lote: no llegaba **ni una** métrica de Linux. Ahora la
barra se cambia por barra normal —ningún dispositivo de Linux lleva una
invertida— y los sistemas de ficheros `9p` y `drvfs` se ignoran, porque son la
carpeta del portátil y sus cifras no son las del servidor.

### 7.4 Un recolector sin agente fabrica zombis — pero solo si el proceso 1 no entierra

Cada conexión SSH deja un huérfano que el sistema reparenta al **proceso 1**.
En el laboratorio ese proceso era la tienda en Python, que no entierra a nadie:
**60 `sshd <defunct>` en unas horas**, visibles en la propia medida `processes`.
`init: true` pone a `tini` de proceso 1 y se acabó.

La pregunta que importa —porque es una garantía que se le da a un cliente— es si
esto le pasaría en **su** servidor. **No.** Medido en las dos situaciones, cinco
conexiones cada una:

| Proceso 1 | Tras 5 conexiones |
|---|---|
| `sleep` (no entierra) | **5 zombis**, los cinco con `PPID 1` |
| `tini` (entierra, como systemd) | **0** |

Que los cinco tengan `PPID 1` es el dato: son huérfanos reparentados, no hijos
que `sshd` se olvide de enterrar. Y enterrar huérfanos es la razón de ser del
proceso 1: **systemd lo hace siempre**, igual que `sysvinit`, `OpenRC` o
`upstart`. No hay configuración que lo apague.

Queda un solo escenario real en el que pasaría: **que el objetivo sea un
contenedor con SSH dentro cuyo proceso 1 sea la aplicación**. Está escrito en el
documento de permisos §2.5, con la respuesta corta primero y el caso raro
después, porque a un cliente no se le puede dar una garantía con un «depende»
escondido.

### 7.5 Y dos de higiene

- La columna del tipo de bloqueo se llamaba `modo` y **se comía la etiqueta
  global `modo`** de O-D13: esas filas salían con `modo=AccessShareLock` en vez
  de `modo=sin_agente`. Ahora es `tipo`.
- `inputs.docker` convertía **cada etiqueta de Docker en una etiqueta de la
  métrica**: veinticinco por punto, incluidas las rutas absolutas del equipo
  (`C:\proyectos\Kinetix\...`). Es cardinalidad inútil y es una fuga: en la base
  de métricas de un cliente no tienen por qué quedar las rutas de nadie.

En los dos casos borré del cubo `infra` las filas ya escritas con la etiqueta
mala, **después de comprobar que todo lo que hay ahí es mío**: un solo
`cliente=laboratorio`, una sola corrida, y el punto más antiguo posterior a la
creación del cubo (reglas 29 y 30).

---

## 8. Lo que no se ha comprobado (regla 33)

- **Fredy no ha validado nada de O2a**, ni O1, ni H5, H6 o H7.
- **No se ha probado desde otra máquina** que los puertos de O-D1 estén cerrados.
  Sigue siendo la prueba que falta, igual que en el reporte 97.
- **No se ha probado contra un servidor de verdad.** Todo esto corre contra
  contenedores que hacen de servidores. La técnica es la misma —los mismos
  ficheros, las mismas órdenes, el mismo SQL—, pero en un servidor o una máquina
  virtual las cifras de `cpu`, `mem` y `disk` serían del servidor y aquí son del
  anfitrión (§2.3).
- **`StrictHostKeyChecking` está apagado** en el laboratorio, porque los
  contenedores se recrean y con ellos su llave de máquina. **En un cliente eso no
  se deja así**: está dicho en el documento de permisos §2.6, pero no
  implementado.
- **Windows, Oracle, SQL Server y MySQL no están hechos.** Ni empezados.
- **El modo con agente (O2b) no existe todavía.** Lo único que se ha hecho para
  que llegue sin dolor es que los nombres coincidan, y eso sí está comprobado.
- **No se tocó el servidor de Azure**, como pedía el marco de la etapa.
- **No se tocó `services/engine/`** ni ningún archivo protegido. El motor propio
  sigue sin publicar en InfluxDB: va con O3, igual que el WebSocket (O-D7).
- Los datos de la corrida `zztest-…-20260922-1333` **siguen en los dos cubos** a
  propósito, para que Fredy pueda mirar el tablero. Se borran cuando quiera.

---

## 9. Estado

**Etapa O2a implementada, pendiente de validación de Fredy.**

---

## 10. Añadido al cerrar la etapa

Tres cosas que se hicieron **después** de escribir lo de arriba, al cerrar O2a:

- **La regla 35 de `CLAUDE.md`** — borrar en InfluxDB con tres condiciones a la
  vez, la comprobación previa obligatoria y la constancia en el reporte. Nace de
  los dos borrados de §7.5 y del precedente del reporte 97 §3.2: se estaban
  haciendo bien, pero por criterio y no por regla escrita.
- **La respuesta a los zombis, medida** (§7.4 y documento de permisos §2.5).
  Era una garantía que se le iba a dar a un cliente y estaba redactada como una
  observación del laboratorio.
- La sección del documento de permisos que era §2.5 (la huella del servidor)
  pasa a ser **§2.6**.
