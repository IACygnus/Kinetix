75cb593 · 2026-09-22

# ETAPA O2b — el agente

**0 llamadas a la IA.** Etapa previa: reportes **99** y **100**. El laboratorio
de O2a es el banco de pruebas de ésta.

---

## 0. Antes: el cierre de O2a

Commit `75cb593`, empujado a `github`. Y tres cosas que se cerraron con él:

- **Regla 35** en `CLAUDE.md` — borrar en InfluxDB exige tres condiciones a la
  vez, comprobación previa de que todo lo del cubo es de la prueba, y
  constancia en el reporte. Es la regla 28 escrita para otra base.
- **La respuesta a los procesos zombis, medida** (§1 de aquí abajo).
- **`.gitattributes`** — los `.sh`, `Dockerfile` y `.conf` se guardan con LF.
  Con `core.autocrlf=true`, un clon en Windows los sacaría con CRLF y dentro de
  un contenedor Linux respondería «bad interpreter». Estaba a un `git clone` de
  romperse en cualquier máquina que no fuera ésta.

---

## 1. Los zombis: la respuesta que faltaba

El reporte 99 §7.4 decía que un recolector sin agente fabrica zombis y que
`init: true` lo arregla. Eso es una observación del laboratorio, no una
garantía. Y era una garantía lo que había que dar.

Se midió, en las dos situaciones, con cinco conexiones cada una:

| Proceso 1 | Tras 5 conexiones |
|---|---|
| `sleep` (no entierra) | **5 zombis**, los cinco con `PPID 1` |
| `tini` (entierra, como systemd) | **0** |

Que los cinco tengan `PPID 1` es el dato que cierra la pregunta: son
**huérfanos reparentados**, no hijos que `sshd` se olvide de enterrar. Y
enterrar huérfanos es la razón de ser del proceso 1. **systemd lo hace siempre**,
igual que `sysvinit`, `OpenRC` o `upstart`; no hay configuración que lo apague.

Queda un escenario real, y está escrito: **que el objetivo sea un contenedor con
SSH dentro cuyo proceso 1 sea la aplicación**. En el documento de permisos §2.5,
con la respuesta corta primero —«no»— y el caso raro después.

---

## 2. O2b.1 — el agente en el laboratorio

### 2.1 Qué es (O-D17, O-D18, O-D19)

Telegraf **1.29.5**, la misma versión fijada del modo sin agente, corriendo
dentro de `lab_servidor` como el servicio `kinetix-agente`:

```
usuario   kinetix_agente   sin shell, sin contrasena, sin sudo, sin ningun grupo
programa  /opt/kinetix-agente/bin/telegraf
config    /etc/kinetix-agente/{agente.conf, conf.d/, entorno, LEEME.txt}
unidad    /etc/systemd/system/kinetix-agente.service
```

El instalador **comprueba** que el usuario no está en `docker`, `sudo`, `wheel`
ni `adm`, y se para si lo estuviera. No lo supone.

### 2.2 La aceptación

Minuto cerrado de las 15:58, medida `cpu`, campo `usage_idle`, mismo servidor:

```
modo=agente      60 puntos
modo=sin_agente   6 puntos
```

**Uno por segundo (O-D18) contra uno cada diez.** Y los segundos salen
consecutivos, sin un hueco —se comprobó marca a marca, no por el recuento de un
minuto, que al estar corriendo engaña—.

### 2.3 El esquema, el mismo (O-D13)

Las dos primeras versiones **no** coincidían: el agente traía `swap` y `kernel`
y el modo sin agente no. Se añadieron al lector por SSH —de `/proc/vmstat`,
`/proc/stat` y `entropy_avail`— copiando campo por campo lo que publica el
nativo. Ahora:

```
modo=agente      cpu disk diskio kernel mem net processes swap system
modo=sin_agente  cpu disk diskio kernel mem net processes swap system  + procesos_top
```

Las **nueve** medidas que comparten son idénticas. `procesos_top` sigue siendo
solo del modo sin agente y se llama distinto a propósito (reporte 99 §2.2).

---

## 3. O2b.2 — los dos modos, lado a lado

### 3.1 Lo que el agente ve y el otro no

Un pico de CPU de **tres segundos**, provocado a propósito con la máquina en
reposo (se esperó a que bajara del 22 %):

```
modo=agente (1 s)                    modo=sin_agente (10 s)
  16:31:58    7.3%                     16:31:50    9.6%
  16:31:59    8.3%
  16:32:00   60.9%                     16:32:00   18.2%
  16:32:01   96.3%   <-- el pico
  16:32:02   92.7%
  16:32:03   45.6%
  16:32:04   11.3%                     16:32:10   25.9%   <-- su maximo
  16:32:05   10.9%                     16:32:20   10.7%
```

| | El máximo que reportó |
|---|---|
| **Con agente** | **96,3 %** |
| Sin agente | **25,9 %** |

Los dos son correctos: el de diez segundos **promedia**, y promediar tres
segundos de saturación dentro de una ventana de diez la reduce a un cuarto.
Quien mirara solo la segunda cifra diría que el servidor iba holgado.

> **Un tropiezo por el camino, que cambió la prueba.** El primer intento salió
> inservible porque la máquina ya estaba al 95 % **antes** del pico. La causa
> era mía: los bucles de carga del primer guion se lanzaban en segundo plano y
> se mataban con `kill $(jobs -p)`, que en un `sh -c` no interactivo devuelve
> una lista vacía. Sobrevivieron al guion y estuvieron quemando ocho núcleos
> hasta que los vi —carga 13—. Ahora cada bucle se apaga solo con `timeout`: un
> proceso que se apaga solo no depende de que nadie se acuerde de apagarlo. Y
> antes de medir, el guion espera a que la máquina esté tranquila.

### 3.2 Lo que cuesta el agente — la cifra que pregunta un cliente

Medido de `/proc`, por diferencia, durante una prueba de carga:

| | |
|---|---|
| **CPU** | **0,44-0,57 % de un núcleo** · 0,06-0,07 % de la máquina de 8 |
| **Memoria propia (`RssAnon`)** | **~60 MB** |
| Memoria del programa (`RssFile`) | ~92 MB — páginas del ejecutable mapeadas de disco, que el núcleo descarta bajo presión |
| **Salida de red** | **~3 kB/s** |
| Escritura en disco | ninguna, salvo su propio registro |

La distinción entre las dos memorias no es un detalle: `VmRSS` decía 155 MB y
esa habría sido la cifra que le damos a un cliente. **Los 92 MB son el propio
Telegraf mapeado** (el ejecutable pesa 218 MB) y no le quitan memoria útil al
servidor. Lo que de verdad ocupa son 60 MB.

Se probó `GOMEMLIMIT=48MiB` para bajarlo y **apenas movió la aguja** (145 → 139
MB): lo que pesa no es el montón de Go. Se descartó, porque durante un corte de
red el colchón crece a propósito y un límite agresivo estorbaría.

Y el techo no es una promesa nuestra: lo hace cumplir el núcleo, comprobado con
`systemctl show` contra el servicio vivo:

```
CPUQuotaPerSecUSec=200ms          (20 % de un nucleo)
MemoryMax=268435456               (256 MB)
CapabilityBoundingSet=            (vacio: cero capacidades de root)
User=kinetix_agente
NoNewPrivileges=yes  ProtectSystem=strict  ProtectHome=yes
```

---

## 4. O2b.3 — el corte de red (O-D22)

El corte es **de verdad, a nivel de red**: se desconecta `lab_servidor` de la
red por la que alcanza InfluxDB. No se para el agente ni se toca su
configuración. Y se comprueba que el corte es real antes de empezar a contar
—un `wget` a `influxdb:8086/health` que tiene que fallar—.

Durante el corte el servidor **sigue trabajando**: la carga la genera `lab_db`
contra la tienda por la red del laboratorio, que no se toca. Si el servidor
estuviera ocioso no habría nada que perder y la prueba no valdría.

```
ventana del corte: 16:34:42Z -> 16:37:45Z  (183 s)

puntos del agente DURANTE el corte    183 de 183 esperados
puntos SIN AGENTE durante el corte      18
PASA | el agente recupero el 100 % del corte
```

**No se perdió un segundo.** El agente guarda en memoria lo que no puede enviar
y lo manda al volver la red.

**No hay PARADA de O-D22.**

### 4.1 Hasta dónde aguanta — y qué parte de eso es un cálculo

El agente escribe **20 series por segundo** (medido) y el colchón es de 50.000
métricas (configurado). Eso da unos **41 minutos** sin conexión.

Esa cifra es **aritmética sobre dos números, no una prueba**. Lo probado son
tres minutos. Está dicho así en el documento del cliente: si alguien necesita
garantía para cortes de horas, hay versiones de Telegraf que guardan en disco en
vez de en memoria, y habría que evaluarlas.

---

## 5. O2b.4 — la desinstalación

Probada en **los dos caminos**, y en los dos comprobada también **desde fuera
del guion**, por si el guion se estuviera engañando a sí mismo:

| Camino | Resultado |
|---|---|
| Con systemd (contenedor Ubuntu con systemd 249) | 10 de 10 comprobaciones |
| Sin systemd (`lab_servidor`) | 9 de 9 comprobaciones |

Desde fuera, después:

```
id: 'kinetix_agente': no such user
ls: cannot access '/opt/kinetix-agente': No such file or directory
ls: cannot access '/etc/kinetix-agente': No such file or directory
ls: cannot access '/usr/local/bin/kinetix-agente-corrida': No such file or directory
ls: cannot access '/var/log/kinetix-agente.log': No such file or directory
procesos telegraf: 0
Unit kinetix-agente.service could not be found.
```

El desinstalador **no dice** que ha limpiado: lo comprueba una cosa por línea y
**sale con error si algo sobrevivió**.

---

## 6. O-D20 y O-D21 — los instaladores

### 6.1 Linux: probado de verdad, con systemd

El laboratorio es un contenedor y no tiene systemd, así que el instalador
tiene dos caminos: el de systemd y un arranque en segundo plano con un aviso
bien visible. Para no dejar el camino importante sin probar, **se levantó un
contenedor Ubuntu aparte con systemd 249 de verdad** y se instaló allí:

```
servicio de systemd activo y habilitado para el arranque
el agente corre como: kinetix_agente  (pid 3365)
```

Y todo lo demás comprobado contra el servicio vivo: el endurecimiento de §3.2,
la recarga de la corrida sin reiniciar (`MainPID` idéntico antes y después), y
las nueve medidas llegando con `host=servidor_systemd`. Al terminar, ese
contenedor se retiró.

### 6.2 Windows: escrito y NO probado (O-D21)

`instalar_agente.ps1` y `desinstalar_agente.ps1` existen, con el mismo diseño:
servicio `KinetixAgente` con la cuenta virtual `NT SERVICE\KinetixAgente`, las
variables en el registro —no en la línea de órdenes—, permisos del directorio
de configuración restringidos, y un desinstalador que comprueba lo que queda.

Lo único que se ha hecho es **validar que analizan sin errores de sintaxis**:

```
OK    instalar_agente.ps1 - analiza sin errores
OK    desinstalar_agente.ps1 - analiza sin errores
```

**No se han ejecutado nunca contra un Windows Server.** La huella del paquete de
Windows está sin fijar a propósito, con un aviso en el propio guion. Está
declarado en el documento del cliente §9 con esas palabras: no lo instalen hasta
que lo probemos.

---

## 7. Dos fallos míos, de los que dejan lección

### 7.1 Construí la fuga contra la que yo mismo aviso

El primer arranque sin systemd pasaba el token así:

```
runuser -u kinetix_agente -- env KX_INFLUX_TOKEN=IrcRFKiG... /opt/.../telegraf
```

**Cualquiera en el servidor lo veía con `ps`.** Y el documento de permisos del
modo sin agente ya decía, escrito por mí, que de `ps` leemos `comm` y no `args`
«porque una línea de órdenes puede llevar una contraseña dentro».

Ahora el proceso lee el token él mismo del fichero de entorno, que es suyo y de
nadie más, y el instalador **comprueba al terminar** que el token no está en la
línea de órdenes de ningún proceso. Se añadió además `--token-fichero`, porque
con `--token` el secreto está en la línea de órdenes **del propio instalador**
mientras dura.

Dos tropiezos menores en esa comprobación, los dos instructivos: primero
señalaba al envoltorio `runuser` en vez de al agente (`pgrep -f` busca en la
línea de órdenes y la ruta del binario aparecía en las dos; con `pgrep -x`, que
mira el nombre del ejecutable, se acabó), y después `ps | grep <token>` **se
encontraba a sí mismo**, porque el propio `grep` lleva el token en su línea de
órdenes. La foto de `ps` se toma ahora antes de buscar en ella.

### 7.2 `docker exec -d` se traga los errores

El primer guion de comparación lanzaba JMeter con `docker exec -d` y seguía
adelante tan contento. JMeter no arrancaba, no había JTL, y no había ni una
línea que lo dijera. Ahora se lanza en segundo plano **desde el anfitrión**, con
la salida a un fichero, y se comprueba a los doce segundos que sigue vivo.

De paso: el bucle que esperaba a que terminara preguntaba con `pgrep` **dentro
de `jmeter_backend`, que no trae `pgrep` ni `ps`**. La orden fallaba con código
127 y el bucle salía en la primera vuelta, como si la prueba hubiera acabado ya.

---

## 8. El tablero, y la regresión

El tablero de infraestructura pasa de 13 a **15 paneles** y gana un selector
**«Modo»**. Los paneles del servidor filtran por él: cambiar el selector **no
cambia la consulta**, solo de dónde vienen los datos — que es exactamente lo que
O-D13 prometía. Los de PostgreSQL y los de contenedores no lo llevan, porque
esos solo existen en el modo sin agente y filtrarlos los dejaría vacíos.

Y una fila nueva al final, «Los dos modos, lado a lado»: la CPU medida de las
dos formas en la misma gráfica, y cuántos puntos por minuto escribe cada una
(60 y 6).

Comprobado que los 15 paneles **devuelven datos**, y en **las dos posiciones**
del selector:

```
selector Modo = sin_agente   ->  LOS 15 PANELES DEVUELVEN DATOS: TODO PASA
selector Modo = agente       ->  LOS 15 PANELES DEVUELVEN DATOS: TODO PASA
```

La regresión completa, en serie contra `jmeter_analyzer_test` (regla 34):

```
=== LA BASE DE FREDY, ANTES ===        === LA BASE DE FREDY, DESPUES ===
86f88bf73ffe47f15226188e5c58caaa       86f88bf73ffe47f15226188e5c58caaa
24 10 8 13 5 5                         24 10 8 13 5 5

SI — la base de Fredy no cambio ni una fila
suites: 13 · con fallo: 0    ·    507 comprobaciones
```

---

## 9. Lo que no se ha comprobado (regla 33)

- **Fredy no ha validado nada de O2b**, ni de O2a, ni O1, ni H5, H6 o H7.
- **El instalador de Windows no se ha ejecutado nunca** (O-D21). Solo se ha
  validado su sintaxis. La huella del paquete de Windows está sin fijar.
- **El corte de red probado es de tres minutos.** Los ~41 minutos de colchón son
  un cálculo a partir de dos números medidos, no una prueba.
- **Nada de esto ha visto un servidor de verdad.** Sigue siendo el laboratorio
  de O2a, con los matices del reporte 99 §2.3: aquí `cpu`, `mem` y `disk` son
  del anfitrión, y el agente —que corre dentro del contenedor— los lee igual de
  `/proc`, así que tiene la misma limitación. En una máquina virtual de un
  cliente no hay esa ambigüedad.
- **No se ha medido el agente bajo una carga que lo apriete de verdad** (cientos
  de discos, miles de procesos). Las cifras de §3.2 son de un servidor pequeño.
- **La procedencia del paquete no está firmada por el fabricante.** La huella la
  calculamos nosotros; InfluxData no publica una al lado del paquete. El camino
  bueno —su repositorio APT/YUM firmado con GPG— **se comprobó que existe y
  responde**, pero no está implementado.
- **`StrictHostKeyChecking` sigue apagado** en el modo sin agente del
  laboratorio, igual que en O2a.
- **No se tocó el servidor de Azure**, ni `services/engine/`, ni ningún archivo
  protegido.
- Los datos de las corridas `zztest-` de esta etapa **siguen en los dos cubos** a
  propósito, para que Fredy pueda mirar el tablero.

---

## 10. Estado

**Etapa O2b implementada, pendiente de validación de Fredy.**
