# Monitoreo con agente — qué instalamos en sus servidores

**SQA Kinetix Pro · Documento para el área de infraestructura del cliente**
Versión 1.0 · 22 de septiembre de 2026

> Este documento es el hermano de `requisitos-sin-agente.md`. **Si aún no han
> decidido entre los dos modos, lean primero aquel**: no instala nada y para
> muchas pruebas es suficiente. Aquí se explica qué se gana instalando algo, y
> qué cuesta exactamente.

---

## Lo que pedimos, en una frase

Instalar un programa pequeño —el **Agente Kinetix**, que es
[Telegraf](https://github.com/influxdata/telegraf) 1.29.5, software libre de
InfluxData— como un servicio del sistema, corriendo con un usuario propio sin
privilegios. Mide este servidor una vez por segundo y envía las cifras a la
plataforma de pruebas. **Se desinstala con una orden y no deja nada.**

---

## 1. ¿Por qué un agente, si el modo sin agente ya funciona?

Por una sola razón, y se ve mejor con un número que con una explicación.

Provocamos en nuestro laboratorio un pico de CPU de **tres segundos** y miramos
qué decía cada modo:

| Modo | El máximo que reportó |
|---|---|
| **Con agente**, una lectura por segundo | **96,3 %** |
| Sin agente, una lectura cada diez segundos | **25,9 %** |

Los dos modos son correctos. El de diez segundos promedia, y promediar un pico
de tres segundos dentro de una ventana de diez lo reduce a menos de un tercio.
Quien mirara solo la segunda cifra concluiría que el servidor iba holgado
cuando en realidad estuvo saturado.

**Cuándo importa esto:** picos cortos de CPU, agotamientos momentáneos de
memoria, ráfagas de disco, colas que se llenan y se vacían entre dos lecturas.
Si su prueba es de carga sostenida y sube despacio, el modo sin agente le dará
las mismas conclusiones y no hay que instalar nada.

---

## 2. Qué se instala, exactamente

| | |
|---|---|
| Programa | Telegraf 1.29.5 (`telegraf`), un único ejecutable |
| Servicio | `kinetix-agente` (Linux, systemd) · `KinetixAgente` (Windows) |
| Usuario | `kinetix_agente` — **sin shell, sin contraseña, sin `sudo`, sin ningún grupo** |
| Frecuencia | una lectura por segundo; se envía agrupado cada cinco |
| Destino | únicamente la dirección de InfluxDB que ustedes autoricen |

Y en **estas rutas, y nada más**:

```
/opt/kinetix-agente/          el programa
/etc/kinetix-agente/          la configuración y el token
/etc/systemd/system/kinetix-agente.service
/usr/local/bin/kinetix-agente-corrida
```

En Windows: `C:\Program Files\KinetixAgente`, `C:\ProgramData\KinetixAgente` y
el servicio.

### 2.1 De dónde sale el programa

Del paquete oficial de InfluxData,
`https://dl.influxdata.com/telegraf/releases/telegraf-1.29.5_linux_amd64.tar.gz`,
y el instalador **verifica su huella SHA-256 antes de instalar nada**.

Con una salvedad que decimos nosotros y que conviene que sepan: esa huella la
calculamos nosotros sobre nuestra propia descarga; **InfluxData no publica un
fichero de huella al lado del paquete**. Eso protege contra una corrupción o
contra que les entreguen algo distinto de lo que probamos, pero **no** contra
que la descarga de aquel día ya viniera manipulada.

Si su política exige procedencia firmada por el fabricante, **díganlo y lo
hacemos así**: InfluxData mantiene un repositorio APT/YUM firmado con GPG y el
instalador se adapta en una tarde. No está hecho porque nadie nos lo ha pedido
todavía, no porque sea difícil.

Y si el servidor no tiene salida a internet —lo normal en producción—, el
instalador acepta el paquete de un fichero local: `--paquete /ruta/telegraf.tar.gz`.

---

## 3. Qué consume — medido, no estimado

De nuestro laboratorio, con el agente midiendo una vez por segundo, durante una
prueba de carga:

| | |
|---|---|
| **CPU** | **0,5 % de un núcleo** (0,07 % de una máquina de 8 núcleos) |
| **Memoria propia** | **~60 MB** |
| Memoria del programa | ~92 MB de páginas del ejecutable, mapeadas desde disco. **No le quitan memoria al servidor**: el sistema las descarta cuando necesita memoria para otra cosa |
| **Red de salida** | **~3 kB/s** — unos 250 MB al mes si se dejara encendido todo el tiempo, que no es el caso |
| Escritura en disco | **ninguna**, salvo el registro del propio servicio |

Y por si estas cifras no les bastan, **el servicio lleva un techo que hace
cumplir el núcleo, no nosotros**:

```
MemoryMax=256M      si el agente intentara pasarse, el sistema lo frena
CPUQuota=20%        no puede usar más de una quinta parte de un núcleo
```

Los dos valores se pueden bajar si lo prefieren. Comprobado en el laboratorio
con `systemctl show`, no leído del fichero.

---

## 4. Qué permisos tiene — y cuáles no

El agente corre como `kinetix_agente`, que no está en ningún grupo. Además, el
servicio se declara en systemd con todas estas restricciones, **que aplica el
núcleo del sistema operativo**:

| Restricción | Qué significa |
|---|---|
| `CapabilityBoundingSet=` (vacío) | **cero capacidades de root.** Ni una |
| `NoNewPrivileges=yes` | no puede ganar privilegios ni aunque algo lo intente |
| `ProtectSystem=strict` | todo el sistema de ficheros en **solo lectura** para él |
| `ProtectHome=yes` | no ve `/home`, `/root` ni `/run/user` |
| `PrivateTmp=yes` | su `/tmp` es suyo y no toca el de nadie |
| `PrivateDevices=yes` | no ve los dispositivos físicos |
| `ProtectKernelTunables/Modules=yes` | no puede tocar el núcleo ni cargar módulos |
| `RestrictAddressFamilies=` | solo puede abrir conexiones de red normales |
| `SystemCallArchitectures=native` | no puede usar llamadas de otra arquitectura |

En Windows, el equivalente: el servicio corre con la cuenta virtual
`NT SERVICE\KinetixAgente`, que no es administrador y no tiene sesión
interactiva.

### 4.1 Lo que el agente NO mide, por no pedir más permisos

Esto es una decisión, no una limitación técnica. Todo lo de esta lista se
podría medir **subiendo los permisos del agente**, y hemos preferido no hacerlo:

| Lo que no medimos | Lo que habría que darle |
|---|---|
| CPU y memoria **por contenedor** de Docker | pertenencia al grupo `docker`, que **equivale a ser administrador de la máquina** |
| Estado SMART de los discos | `sudo smartctl` |
| Entrada/salida por proceso (`/proc/<pid>/io` de otros usuarios) | `CAP_SYS_PTRACE` |
| Estadísticas avanzadas de las tarjetas de red | `CAP_NET_ADMIN` |

Si alguna de ellas les resulta imprescindible, se habla: pero se habla sabiendo
lo que cuesta cada una.

---

## 5. Qué datos salen del servidor

Exactamente los mismos que en el modo sin agente, con los mismos nombres. Nueve
familias de cifras del sistema:

`cpu` · `mem` · `swap` · `disk` · `diskio` · `net` · `system` · `processes` ·
`kernel`

Es decir: uso de procesador, memoria, intercambio, espacio y actividad de
disco, tráfico y contadores de red, carga del sistema, número de procesos por
estado, y contadores del núcleo.

**Qué NO sale:**

- Ningún fichero suyo. Ni de datos, ni de registro, ni de configuración.
- **Ningún nombre de proceso ni línea de órdenes.** El agente no publica la
  lista de procesos, solo **cuántos** hay en cada estado.
- Ningún contenido de red. Se cuentan bytes y paquetes, no se mira dentro.
- Nada de sus bases de datos. (Eso va por el otro camino, con su propio rol de
  solo lectura: ver `requisitos-sin-agente.md` §3.)

Cada cifra viaja con cuatro etiquetas: el nombre del servidor, su nombre de
cliente, el modo (`agente`) y **la corrida**, que es el identificador de la
prueba concreta. Nada más.

---

## 6. La red

| Origen | Destino | Puerto | Dirección |
|---|---|---|---|
| El servidor con el agente | La plataforma Kinetix (InfluxDB) | 8086/TCP (o el que se acuerde) | **Saliente desde su servidor** |

**No hay que abrir ningún puerto entrante en su servidor.** Es al revés que el
modo sin agente: allí somos nosotros los que entramos por SSH; aquí es el
agente el que sale. Para muchas áreas de seguridad esto es más fácil de
autorizar, y es una razón legítima para preferir el agente.

La credencial que lleva el agente es un token que **solo puede escribir**, y
solo en el depósito de esta plataforma. No puede leer nada, ni siquiera lo que
él mismo escribió.

### 6.1 Si se cae la red

Lo medimos: **cortamos la red del servidor durante tres minutos mientras
trabajaba, y al volver no se perdió ni un segundo de datos** — 183 de 183.

El agente guarda en memoria lo que no puede enviar y lo manda cuando la red
vuelve. Con la configuración que entregamos, el colchón da para unos **40
minutos** sin conexión (50.000 lecturas a 20 por segundo). Esa última cifra es
un cálculo a partir de números medidos, no una prueba: **el corte más largo que
hemos probado es de tres minutos**. Si necesitan garantía para cortes de horas,
existe una versión de Telegraf que guarda en disco en vez de en memoria;
díganlo y la evaluamos.

---

## 7. Cómo se instala y cómo se quita

**Instalar** (una sola orden, como administrador):

```bash
sudo bash instalar_agente.sh \
     --url https://kinetix.ejemplo/influx --token-fichero /ruta/token.txt \
     --org performance --cubo infra --cliente "SU EMPRESA"
```

`--token-fichero` en vez de `--token` para que la credencial **no aparezca en
la línea de órdenes**, donde cualquiera en el servidor podría verla con `ps`.
Las dos formas funcionan; recomendamos la primera.

**Quitar:**

```bash
sudo bash desinstalar_agente.sh
```

El desinstalador no dice que ha limpiado: **lo comprueba y se lo enseña**, una
línea por cosa —el usuario, el grupo, el programa, la configuración, el
servicio, el registro, los procesos— y falla si algo sobrevivió.

```
PASA  | no queda: el usuario
PASA  | no queda: el directorio del programa
PASA  | no queda: la unidad de systemd
PASA  | no queda: algun proceso del agente
PASA  | no queda: el servicio en systemd
El agente Kinetix se ha ido del todo. El servidor esta como estaba.
```

Pueden ejecutarlo ustedes en cualquier momento, sin avisarnos.

---

## 8. Los dos modos, uno al lado del otro

| | Sin agente | Con agente |
|---|---|---|
| ¿Instala algo? | **No** | Sí, un servicio |
| Frecuencia | cada 10 s | **cada 1 s** |
| Ve picos cortos | no | **sí** |
| Dirección de la conexión | nosotros entramos (SSH 22) | **su servidor sale** (8086) |
| Puerto entrante a abrir | sí, el 22 | **ninguno** |
| Usuario en su servidor | uno de solo lectura, con llave | uno de servicio, sin privilegios |
| Coste en el servidor | ninguno | 0,5 % de un núcleo, ~60 MB |
| Si se cae la red | se pierde ese rato | **se recupera al volver** |
| Retirarlo | borrar una línea de `authorized_keys` | una orden, y se comprueba |

**Las métricas se llaman igual en los dos modos.** Eso no es casualidad: está
comprobado campo a campo, y significa que pueden empezar sin agente y cambiar
después —o al revés— sin rehacer un solo tablero ni una sola alerta.

---

## 9. Lo que este documento no cubre todavía

- **Windows Server: el instalador está escrito pero NO está probado.** Nuestro
  laboratorio es Linux. El guion existe, se ha comprobado que analiza sin
  errores de sintaxis, y no se ha ejecutado nunca contra un Windows real. **No
  lo instalen en un servidor suyo hasta que lo probemos**, y cuando lo hagamos
  lo diremos aquí.
- **Cortes de red de más de tres minutos**: el mecanismo está probado, la
  duración máxima es un cálculo (§6.1).
- **Arquitecturas que no sean x86-64.** ARM existe en Telegraf; no lo hemos
  probado.
- **Otros sistemas operativos** (AIX, Solaris, BSD).
