# Monitoreo sin agente — qué necesitamos de sus servidores

**SQA Kinetix Pro · Documento para el área de infraestructura del cliente**
Versión 1.0 · 21 de septiembre de 2026

---

## Lo que pedimos, en una frase

Durante la ventana de la prueba de rendimiento queremos ver qué le pasa a sus
servidores. Para eso **no instalamos nada en ellos**: nos basta un usuario de
solo lectura por servidor y que nuestro recolector pueda abrir una conexión
hacia ellos. Nada nuestro se queda dentro de su máquina, y cuando la prueba
termina se revoca el acceso.

Este documento dice, por cada tipo de servidor: **qué usuario, con qué permisos,
qué puerto y en qué dirección, y qué datos leemos y cuáles no.**

---

## 1. Cómo funciona, para que se entienda qué se está autorizando

```
   Su red                                 |   Donde corre Kinetix
                                          |
   [ servidor Linux ]  <--- SSH 22 -------|--- [ recolector ]  ---> [ base de métricas ]
   [ PostgreSQL     ]  <--- TCP 5432 -----|
                                          |
   nadie entra desde aquí hacia Kinetix   |   todas las conexiones salen de aquí
```

- El **recolector** (Telegraf, imagen oficial, versión fijada) vive en nuestra
  infraestructura, no en la suya.
- **Todas las conexiones las abre el recolector hacia sus servidores.** Sus
  servidores nunca abren nada hacia nosotros y no necesitan salida a internet.
- La frecuencia por defecto es **una lectura cada 10 segundos**, y es **una sola
  conexión SSH por servidor y por lectura**: no abrimos una por métrica.
- No se escribe nada en sus servidores. Ni un fichero, ni una tabla, ni un
  registro de configuración.

---

## 2. Servidor Linux

### 2.1 El usuario

| Qué | Valor |
|---|---|
| Usuario | `kinetix_lector` (el nombre puede cambiarse) |
| Contraseña | **ninguna** — la cuenta se deja bloqueada (`passwd -l`) |
| Autenticación | **llave pública SSH**, que les entregamos nosotros |
| Grupos | **ninguno** más allá de su grupo propio |
| `sudo` | **no**. Ni una regla, ni con `NOPASSWD` |
| Shell | una shell normal (`/bin/bash`), porque ejecutamos órdenes de lectura |

Lo que hay que crear, exactamente:

```bash
useradd --create-home --shell /bin/bash kinetix_lector
passwd --lock kinetix_lector
mkdir -p /home/kinetix_lector/.ssh
chmod 700 /home/kinetix_lector/.ssh
# pegar aquí la llave pública que les entregamos
vi /home/kinetix_lector/.ssh/authorized_keys
chmod 600 /home/kinetix_lector/.ssh/authorized_keys
chown -R kinetix_lector:kinetix_lector /home/kinetix_lector/.ssh
```

Si quieren acotarlo más —y nos parece bien que lo hagan—, en `sshd_config`:

```
Match User kinetix_lector
    PasswordAuthentication no
    AllowTcpForwarding no
    PermitTunnel no
    X11Forwarding no
```

### 2.2 El puerto

| Origen | Destino | Puerto | Dirección |
|---|---|---|---|
| La IP del recolector de Kinetix | El servidor Linux | **22/TCP** (o el que usen) | Entrante al servidor |

No hace falta ningún puerto en sentido contrario.

### 2.3 Qué leemos

Ficheros de `/proc`, que son las estadísticas del núcleo, y dos órdenes
estándar:

| Fuente | Para qué |
|---|---|
| `/proc/stat` | CPU: usuario, sistema, espera de disco, inactivo |
| `/proc/meminfo` | Memoria: total, libre, disponible, caché, intercambio |
| `/proc/loadavg`, `/proc/uptime` | Carga del sistema y tiempo encendido |
| `/proc/net/dev` | Bytes y paquetes por interfaz de red |
| `/proc/diskstats` | Lecturas y escrituras por disco |
| `df -T -P -B1` y `df -P -i` | Espacio y nodos-i por punto de montaje |
| `nproc`, `who` | Número de CPU y de sesiones abiertas |
| `ps -eo stat=` y `ps -eo pcpu=,pmem=,comm=` | Cuántos procesos hay y cuáles son los cinco que más CPU consumen |

### 2.4 Qué NO leemos

- **Ningún fichero de su aplicación, de sus datos o de sus registros.**
- Ningún contenido de `/home`, `/etc`, `/var/log` ni de ningún directorio suyo.
- Ni argumentos de línea de órdenes ni variables de entorno de sus procesos: de
  `ps` tomamos el **nombre del ejecutable** (`comm`), no la línea completa
  (`args`), precisamente porque una línea de órdenes puede llevar una
  contraseña dentro.
- No escribimos nada.

### 2.5 ¿Nos deja el recolector procesos colgados en el servidor?

**No.** En un servidor Linux normal, no queda ni un proceso.

Esta es la respuesta corta y es la que vale para su caso. La larga, porque la
pregunta es razonable y merece un número, no una promesa:

Cada lectura abre una conexión SSH. Al cerrarse, uno de los procesos que
`sshd` crea para atenderla queda **huérfano** durante un instante, y el sistema
operativo se lo entrega al **proceso 1** — el proceso de arranque. Enterrar a
esos huérfanos es literalmente la razón de ser del proceso 1, y **systemd lo
hace siempre**; igual que `sysvinit`, `OpenRC` o `upstart`. No hay opción que
apagarlo ni configuración que lo impida.

Lo medimos en las dos situaciones, con cinco conexiones cada una:

| Proceso 1 | Tras 5 conexiones |
|---|---|
| Uno que entierra (como systemd, o `tini`) | **0 procesos colgados** |
| Uno que no entierra | **5 procesos colgados**, todos con «padre 1» |

**¿Cuándo podría pasarle a usted?** En un solo caso, y no es el suyo si nos da
un servidor o una máquina virtual: **si lo que monitorizamos es un contenedor
en el que se ha metido un servidor SSH y cuyo proceso 1 es la propia aplicación
en vez de un arranque de verdad.** Una aplicación normal no entierra huérfanos
porque nadie le ha pedido que lo haga.

Nos pasó a nosotros, en nuestro laboratorio, exactamente por eso: sesenta
procesos colgados en unas horas. Se arregla con una palabra —poniendo un
proceso de arranque mínimo (`tini`, o `docker run --init`)— y lo decimos aquí
en vez de callarlo porque es el único escenario en el que la respuesta de
arriba cambiaría.

Si su objetivo es un contenedor, **avísenos y lo comprobamos antes de empezar**:
se ve en un segundo y se resuelve en otro.

### 2.6 La huella del servidor

En nuestro laboratorio el recolector acepta la llave de máquina sin
comprobarla, porque los servidores de prueba se recrean a cada rato. **En su
instalación eso no se deja así:** fijamos la huella de cada servidor
(`known_hosts`) y una llave que cambie hace fallar la conexión y salta el aviso.
Es lo que impide que alguien se ponga en medio.

---

## 3. Servidor PostgreSQL

### 3.1 El rol

| Qué | Valor |
|---|---|
| Rol | `kinetix_lector` |
| Tipo de acceso | `LOGIN` con contraseña, o certificado si lo prefieren |
| Permiso | **`pg_monitor`**, un rol predefinido del propio PostgreSQL |
| Sobre sus tablas | **ninguno**. Ni un `SELECT` |
| Escritura | **ninguna** |

```sql
CREATE ROLE kinetix_lector LOGIN PASSWORD '<la que ustedes elijan>';
GRANT pg_monitor TO kinetix_lector;
GRANT CONNECT ON DATABASE <su_base> TO kinetix_lector;
```

`pg_monitor` es un rol **que trae PostgreSQL de fábrica** para exactamente este
caso. Da acceso a las vistas de estadística (`pg_stat_*`) y a unas pocas
funciones de tamaño. **No da acceso a los datos.** Si intentáramos leer una
tabla suya, PostgreSQL nos respondería «permiso denegado»; lo comprobamos en
cada instalación y les enseñamos el resultado.

### 3.2 El puerto

| Origen | Destino | Puerto | Dirección |
|---|---|---|---|
| La IP del recolector de Kinetix | El servidor PostgreSQL | **5432/TCP** | Entrante al servidor |

En `pg_hba.conf` basta una línea acotada a esa IP:

```
host    <su_base>   kinetix_lector   <ip-del-recolector>/32   scram-sha-256
```

Si su política exige TLS, lo usamos: el recolector admite `sslmode=require` y
`verify-full`.

### 3.3 Qué leemos

| Vista | Qué sacamos |
|---|---|
| `pg_stat_database` | Conexiones abiertas, transacciones confirmadas y revertidas, bloques leídos de caché y de disco, temporales, interbloqueos |
| `pg_stat_activity` | **Cuántas** sesiones hay en cada estado y cuánto lleva la más antigua |
| `pg_locks` | Cuántos bloqueos hay y cuántos están esperando |
| `pg_stat_statements` | Las diez sentencias más lentas, **ya normalizadas por PostgreSQL** |
| `pg_database_size()` | El tamaño de la base |

### 3.4 Qué NO leemos, y un punto que conviene hablar

- **No leemos ni una fila de sus tablas.**
- De `pg_stat_activity` tomamos el estado y los tiempos, **no el texto de la
  consulta** (`query`), que puede traer valores reales dentro.
- De `pg_stat_statements` sí tomamos el texto, pero **es el texto normalizado
  que guarda PostgreSQL**: los literales aparecen como `$1`, `$2`… Aun así,
  **si su política no permite que salga ni el texto normalizado, se apaga esa
  consulta** y se pierde solo el panel de «consultas más lentas»; todo lo demás
  sigue igual. Díganlo y lo configuramos así desde el principio.
- `pg_stat_statements` es una extensión que hay que cargar al arrancar
  (`shared_preload_libraries`). **Si no la tienen activada, no pedimos que
  reinicien nada por nosotros**: se trabaja sin ese panel.

---

## 4. Contenedores — léase antes de pedirlo

Podemos dar CPU y memoria **por contenedor** leyendo el socket de Docker. Es muy
útil, y hay que decir con todas las letras lo que cuesta:

> **Quien puede leer el socket de Docker puede tomar el control de la máquina
> anfitriona.** No es «un permiso de lectura más». Con ese acceso se pueden
> arrancar contenedores privilegiados, montar el disco del anfitrión y leerlo
> entero. El grupo `docker` equivale, en la práctica, a `root`.

Por eso:

- En nuestro laboratorio lo activamos, porque es nuestro y sabemos lo que hay.
- **A un cliente no se le pide sin explicarle esto.** Si después de leerlo lo
  autorizan, se hace con el socket montado **de solo lectura** y acotado a los
  contenedores de la prueba.
- Si no lo autorizan —que es una respuesta razonable—, **no se pierde casi
  nada**: la CPU, la memoria y el disco del servidor siguen llegando por SSH. Lo
  único que falta es el desglose por contenedor.
- La alternativa limpia, si la quieren, es un **socket intermediario de solo
  lectura** que exponga únicamente `GET /containers/*/stats`. Lo montamos
  nosotros y lo revisan ustedes.

---

## 5. Qué hacemos con lo que leemos

| Pregunta | Respuesta |
|---|---|
| ¿Dónde se guarda? | En la base de métricas de Kinetix (InfluxDB), en un depósito aparte llamado `infra` |
| ¿Cuánto tiempo? | 30 días por defecto; se ajusta a lo que pidan |
| ¿Con qué credencial escribe el recolector? | Un token de **solo escritura** y **solo sobre ese depósito**. No puede leer lo que escribió ni tocar ningún otro |
| ¿Quién lo ve? | Los tableros de Grafana de Kinetix, con la misma cuenta con la que ya ven las pruebas |
| ¿Cómo se cruza con la prueba? | Cada punto lleva la etiqueta **`corrida`**, que es el mismo nombre que la prueba de JMeter. Esa coincidencia es lo que permite poner la curva del servidor y la del tiempo de respuesta en la misma gráfica |
| ¿Sale de su país / de la infraestructura acordada? | No. Se queda donde esté desplegado Kinetix |

---

## 6. Cuando termine

1. Se borra la línea de `authorized_keys` del servidor Linux, o directamente el
   usuario: `userdel -r kinetix_lector`.
2. Se elimina el rol de PostgreSQL: `DROP ROLE kinetix_lector;`.
3. Se cierra la regla de cortafuegos.
4. Se revoca el token de escritura de nuestro lado.

Pueden hacerlo ustedes sin avisarnos. Si el recolector deja de poder entrar,
simplemente deja de haber datos nuevos: no rompe nada ni reintenta de forma
agresiva.

---

## 7. Resumen para la solicitud de cambio

| Servidor | Usuario | Permiso | Puerto | Dirección |
|---|---|---|---|---|
| Linux | `kinetix_lector`, con llave, sin contraseña, sin `sudo` | Lectura de `/proc` y `ps`/`df` | 22/TCP | Recolector → servidor |
| PostgreSQL | `kinetix_lector`, con contraseña | `pg_monitor` + `CONNECT` | 5432/TCP | Recolector → servidor |
| Docker *(opcional, léase §4)* | acceso al socket | equivale a administrador del anfitrión | socket local | — |

---

## 8. Lo que este documento no cubre todavía

Se dice para que nadie lo dé por hecho:

- **Windows Server.** Se haría por WinRM o WMI, con un usuario de solo lectura.
  Aún no está implementado ni probado en Kinetix.
- **Otros motores de base de datos** (Oracle, SQL Server, MySQL). Mismo
  planteamiento, distinto conjunto de vistas. Sin implementar.
- **Balanceadores, colas y cachés** (nginx, RabbitMQ, Redis). Telegraf trae
  complementos para todos ellos; no se han probado aquí.
- **Modo con agente.** Para pruebas largas o con mucho detalle, instalar el
  agente en el servidor da más precisión y menos conexiones. Es la etapa
  siguiente (O2b) y **las métricas se llaman igual**, así que cambiar de un modo
  al otro no obliga a rehacer tableros ni alertas.
