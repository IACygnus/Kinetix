"""Lectura de un Linux SIN AGENTE, por SSH (O-D11), en protocolo de linea.

Lo ejecuta Telegraf desde `[[inputs.exec]]` con `data_format = "influx"`: este
programa escribe por la salida estandar exactamente lo que escribiria un
complemento nativo, y Telegraf lo trata igual.

O-D13 manda: **mismos nombres de medida y de campo que los complementos
nativos** (`cpu`, `mem`, `disk`, `diskio`, `net`, `system`, `processes`), para
que en O2b se pueda cambiar a agente sin tocar tableros ni alertas. Lo que no se
ha podido reproducir se declara en el reporte de la etapa, no se disimula aqui.

Una sola conexion SSH por intervalo y por servidor: se piden todos los ficheros
de golpe y se reparten aqui. Un cliente pregunta cuantas conexiones abrimos, y
la respuesta tiene que ser un numero pequeno.
"""
import json
import os
import subprocess
import sys
import time

# ---------------------------------------------------------------------------
# Configuracion (toda por entorno, para que el .conf no lleve secretos)
# ---------------------------------------------------------------------------
USUARIO = os.environ.get("KX_SSH_USUARIO", "kinetix_lector")
LLAVE = os.environ.get("KX_SSH_LLAVE", "/llaves/kinetix_lector")
OBJETIVOS = [h.strip() for h in os.environ.get("KX_OBJETIVOS", "").split(",") if h.strip()]
ESTADO_DIR = os.environ.get("KX_ESTADO", "/var/lib/kinetix")
ESPERA = int(os.environ.get("KX_SSH_ESPERA", "8"))

# Misma lista que el complemento `inputs.disk` ignora por defecto, menos
# `overlay`: en el laboratorio la raiz ES overlay y sin ella no habria disco.
# `9p` y `drvfs` se anaden porque son como Docker en Windows le ensena al
# contenedor una carpeta del anfitrion: no son discos del servidor y sus cifras
# son las del portatil, no las de la maquina que se esta mirando.
IGNORAR_FS = set(
    (os.environ.get("KX_DISCO_IGNORAR") or
     "tmpfs,devtmpfs,devfs,iso9660,squashfs,aufs,fuse.snapfuse,nsfs,"
     "cgroup,cgroup2,9p,drvfs")
    .split(","))

# Los diez tiempos de /proc/stat, en el orden en que vienen, con el nombre que
# les pone el complemento `cpu`.
CAMPOS_CPU = ["user", "nice", "system", "idle", "iowait", "irq", "softirq",
              "steal", "guest", "guest_nice"]

# /proc/meminfo -> campos de `mem` que son un volcado directo (en bytes).
MEMINFO_DIRECTO = {
    "Active": "active", "Inactive": "inactive", "Dirty": "dirty",
    "Writeback": "write_back", "WritebackTmp": "write_back_tmp",
    "Slab": "slab", "SReclaimable": "sreclaimable", "SUnreclaim": "sunreclaim",
    "Mapped": "mapped", "PageTables": "page_tables", "Shmem": "shared",
    "SwapCached": "swap_cached", "SwapFree": "swap_free", "SwapTotal": "swap_total",
    "CommitLimit": "commit_limit", "Committed_AS": "committed_as",
    "HugePages_Free": "huge_pages_free", "HugePages_Total": "huge_pages_total",
    "Hugepagesize": "huge_page_size",
    "VmallocTotal": "vmalloc_total", "VmallocUsed": "vmalloc_used",
    "VmallocChunk": "vmalloc_chunk",
}

# Los cuatro de memoria alta/baja no existen en /proc/meminfo de un x86_64, y
# el complemento nativo los publica igualmente a cero. Se copia esa decision
# para que la lista de campos sea exactamente la misma.
MEMINFO_ALTA_BAJA = {"HighFree": "high_free", "HighTotal": "high_total",
                     "LowFree": "low_free", "LowTotal": "low_total"}

# Las letras de estado de `ps` -> los campos del complemento `processes`.
ESTADOS_PS = {"R": "running", "S": "sleeping", "D": "blocked", "T": "stopped",
              "t": "stopped", "Z": "zombies", "I": "idle", "X": "dead",
              "W": "paging"}

# Lo que se le pide al servidor. Un solo comando, bloques delimitados.
COMANDO_REMOTO = r"""
echo '##stat';      cat /proc/stat
echo '##meminfo';   cat /proc/meminfo
echo '##loadavg';   cat /proc/loadavg
echo '##uptime';    cat /proc/uptime
echo '##netdev';    cat /proc/net/dev
echo '##diskstats'; cat /proc/diskstats
echo '##df';        df -T -P -B1 2>/dev/null
echo '##dfi';       df -P -i 2>/dev/null
echo '##nproc';     nproc
echo '##who';       who 2>/dev/null | wc -l
echo '##ps';        ps -eo stat= 2>/dev/null
echo '##snmp';      cat /proc/net/snmp
echo '##hilos';     ps -eo nlwp= 2>/dev/null
echo '##top';       ps -eo pcpu=,pmem=,comm= --sort=-pcpu 2>/dev/null | head -n 5
echo '##fin';       true
"""


# ---------------------------------------------------------------------------
# Protocolo de linea
# ---------------------------------------------------------------------------
def _escapar(texto, es_campo=False):
    if es_campo:
        return str(texto).replace("\\", "\\\\").replace('"', '\\"')
    # En una etiqueta el protocolo solo pide escapar coma, igual y espacio. La
    # barra invertida NO se escapa, y una barra al final de un valor rompe la
    # linea entera: se come la coma que la sigue. Aparecio de verdad —el
    # montaje de Windows sale en `df` como dispositivo `C:\`— y dejaba a
    # Telegraf sin ni una metrica de Linux. Se cambia por barra normal: ningun
    # dispositivo de Linux lleva una invertida.
    texto = str(texto).replace("\\", "/")
    return texto.replace(",", "\\,").replace(" ", "\\ ").replace("=", "\\=")


def punto(medida, etiquetas, campos, cuando):
    """Una linea de protocolo, o None si no hay ni un campo que escribir."""
    valores = []
    for clave, valor in campos.items():
        if valor is None:
            continue
        if isinstance(valor, bool):
            valores.append(clave + "=" + ("true" if valor else "false"))
        elif isinstance(valor, int):
            valores.append(clave + "=" + str(valor) + "i")
        elif isinstance(valor, float):
            valores.append(clave + "=" + repr(round(valor, 6)))
        else:
            valores.append(clave + '="' + _escapar(valor, es_campo=True) + '"')
    if not valores:
        return None
    partes = [_escapar(medida)]
    for clave, valor in etiquetas.items():
        if valor not in (None, ""):
            partes.append(_escapar(clave) + "=" + _escapar(valor))
    return ",".join(partes) + " " + ",".join(valores) + " " + str(cuando)


# ---------------------------------------------------------------------------
# Estado entre intervalos (la CPU se mide por diferencia, no por acumulado)
# ---------------------------------------------------------------------------
def llave_utilizable():
    """SSH rechaza una llave que puedan leer otros, y un montaje de Docker en
    Windows llega con los permisos abiertos («Permissions 0777 ... are too
    open»). Se copia a un sitio privado y se usa la copia.
    """
    try:
        if (os.stat(LLAVE).st_mode & 0o077) == 0:
            return LLAVE
    except OSError:
        return LLAVE  # que falle el ssh y lo diga, no este programa

    copia = os.path.join(ESTADO_DIR, "llave_lector")
    try:
        os.makedirs(ESTADO_DIR, exist_ok=True)
        with open(LLAVE, "rb") as origen:
            contenido = origen.read()
        try:
            if open(copia, "rb").read() == contenido:
                os.chmod(copia, 0o600)
                return copia
        except OSError:
            pass
        with open(copia, "wb") as destino:
            destino.write(contenido)
        os.chmod(copia, 0o600)
        return copia
    except OSError as exc:
        # Sin esto, el fallo salia como un volcado de pila que Telegraf corta
        # por la primera linea, y no se sabia de que se quejaba.
        raise RuntimeError(
            "no se pudo dejar una copia privada de la llave en %s (%s). "
            "El directorio tiene que pertenecer al usuario que corre Telegraf."
            % (ESTADO_DIR, exc))


def _leer_estado(host):
    try:
        with open(os.path.join(ESTADO_DIR, "cpu_" + host + ".json")) as fichero:
            return json.load(fichero)
    except Exception:
        return None


def _guardar_estado(host, datos):
    try:
        os.makedirs(ESTADO_DIR, exist_ok=True)
        ruta = os.path.join(ESTADO_DIR, "cpu_" + host + ".json")
        with open(ruta + ".tmp", "w") as fichero:
            json.dump(datos, fichero)
        os.replace(ruta + ".tmp", ruta)
    except Exception as exc:
        sys.stderr.write("no se pudo guardar el estado de cpu: " + str(exc) + "\n")


# ---------------------------------------------------------------------------
# Troceado de la respuesta
# ---------------------------------------------------------------------------
def trocear(salida):
    bloques, actual = {}, None
    for linea in salida.splitlines():
        if linea.startswith("##"):
            actual = linea[2:].strip()
            bloques[actual] = []
        elif actual is not None:
            bloques[actual].append(linea)
    return bloques


# ---------------------------------------------------------------------------
# Un traductor por complemento nativo
# ---------------------------------------------------------------------------
def metricas_cpu(host, lineas, cuando):
    for linea in lineas:
        if not linea.startswith("cpu "):
            continue
        crudos = [int(v) for v in linea.split()[1:11]]
        crudos += [0] * (10 - len(crudos))
        ahora = dict(zip(CAMPOS_CPU, crudos))
        previo = _leer_estado(host)
        _guardar_estado(host, ahora)
        if not previo:
            return []  # el primer intervalo no tiene contra que restar
        deltas = {c: ahora[c] - previo.get(c, 0) for c in CAMPOS_CPU}
        total = sum(deltas.values())
        if total <= 0:
            return []
        campos = {"usage_" + c: 100.0 * deltas[c] / total for c in CAMPOS_CPU}
        return [punto("cpu", {"host": host, "cpu": "cpu-total"}, campos, cuando)]
    return []


def metricas_mem(host, lineas, cuando):
    crudo = {}
    for linea in lineas:
        if ":" not in linea:
            continue
        clave, resto = linea.split(":", 1)
        trozos = resto.split()
        if not trozos:
            continue
        crudo[clave] = int(trozos[0]) * (1024 if len(trozos) > 1 else 1)

    total = crudo.get("MemTotal", 0)
    if not total:
        return []
    libre = crudo.get("MemFree", 0)
    buferes = crudo.get("Buffers", 0)
    # Misma formula que gopsutil, que es lo que usa el complemento nativo.
    cache = crudo.get("Cached", 0) + crudo.get("SReclaimable", 0)
    disponible = crudo.get("MemAvailable", libre + buferes + cache)
    usada = total - libre - buferes - cache

    campos = {
        "total": total, "free": libre, "available": disponible, "used": usada,
        "buffered": buferes, "cached": cache,
        "used_percent": 100.0 * usada / total,
        "available_percent": 100.0 * disponible / total,
    }
    for clave, nombre in MEMINFO_DIRECTO.items():
        if clave in crudo:
            campos[nombre] = crudo[clave]
    for clave, nombre in MEMINFO_ALTA_BAJA.items():
        campos[nombre] = crudo.get(clave, 0)
    return [punto("mem", {"host": host}, campos, cuando)]


def metricas_system(host, bloques, cuando):
    carga = (bloques.get("loadavg") or [""])[0].split()
    arriba = (bloques.get("uptime") or [""])[0].split()
    if len(carga) < 3 or not arriba:
        return []
    segundos = int(float(arriba[0]))
    dias, resto = divmod(segundos, 86400)
    horas, resto = divmod(resto, 3600)
    minutos = resto // 60
    formato = ((str(dias) + " days, ") if dias else "") + \
        ("%d:%02d" % (horas, minutos))
    campos = {
        "load1": float(carga[0]), "load5": float(carga[1]),
        "load15": float(carga[2]),
        "n_cpus": int((bloques.get("nproc") or ["0"])[0] or 0),
        "n_users": int((bloques.get("who") or ["0"])[0] or 0),
        "uptime": segundos, "uptime_format": formato,
    }
    return [punto("system", {"host": host}, campos, cuando)]


def metricas_net(host, lineas, cuando):
    puntos = []
    for linea in lineas:
        if ":" not in linea:
            continue
        interfaz, resto = linea.split(":", 1)
        interfaz = interfaz.strip()
        valores = resto.split()
        if interfaz == "lo" or len(valores) < 16:
            continue  # el nativo tampoco publica `lo` por defecto
        v = [int(x) for x in valores]
        campos = {
            "bytes_recv": v[0], "packets_recv": v[1], "err_in": v[2], "drop_in": v[3],
            "bytes_sent": v[8], "packets_sent": v[9], "err_out": v[10], "drop_out": v[11],
        }
        puntos.append(punto("net", {"host": host, "interface": interfaz}, campos, cuando))
    return puntos


def metricas_net_protocolo(host, lineas, cuando):
    """Los contadores de IP, ICMP, TCP y UDP de /proc/net/snmp.

    El complemento nativo los publica en la MISMA medida `net`, sin etiqueta de
    interfaz, con el nombre del protocolo por delante: `tcp_retranssegs`,
    `tcp_currestab`, `udp_inerrors`… En una prueba de carga son de los datos
    mas utiles que hay —retransmisiones y conexiones establecidas— y por eso se
    reproducen en vez de declararlos como perdidos.

    El fichero viene por parejas de lineas: una de nombres y otra de valores.
    """
    pendiente, campos = {}, {}
    for linea in lineas:
        protocolo, separador, resto = linea.partition(":")
        if not separador:
            continue
        trozos = resto.split()
        if protocolo in pendiente:
            for nombre, valor in zip(pendiente.pop(protocolo), trozos):
                try:
                    campos[protocolo.lower() + "_" + nombre.lower()] = int(valor)
                except ValueError:
                    pass
        else:
            pendiente[protocolo] = trozos
    return [punto("net", {"host": host}, campos, cuando)] if campos else []


def metricas_diskio(host, lineas, cuando):
    puntos = []
    for linea in lineas:
        campos_linea = linea.split()
        if len(campos_linea) < 14:
            continue
        nombre = campos_linea[2]
        if nombre.startswith("loop") or nombre.startswith("ram"):
            continue
        v = [int(x) for x in campos_linea[3:14]]
        campos = {
            "reads": v[0], "merged_reads": v[1], "read_bytes": v[2] * 512,
            "read_time": v[3], "writes": v[4], "merged_writes": v[5],
            "write_bytes": v[6] * 512, "write_time": v[7],
            "iops_in_progress": v[8], "io_time": v[9], "weighted_io_time": v[10],
        }
        puntos.append(punto("diskio", {"host": host, "name": nombre}, campos, cuando))
    return puntos


def metricas_disk(host, bloques, cuando):
    inodos = {}
    for linea in (bloques.get("dfi") or [])[1:]:
        trozos = linea.split()
        if len(trozos) >= 6:
            inodos[trozos[-1]] = trozos[1:4]

    puntos = []
    for linea in (bloques.get("df") or [])[1:]:
        trozos = linea.split()
        if len(trozos) < 7:
            continue
        dispositivo, tipo = trozos[0], trozos[1]
        if tipo in IGNORAR_FS:
            continue
        camino = trozos[-1]
        total, usado, libre = int(trozos[2]), int(trozos[3]), int(trozos[4])
        campos = {"total": total, "used": usado, "free": libre,
                  "used_percent": (100.0 * usado / (usado + libre)) if (usado + libre) else 0.0}
        if camino in inodos:
            i_total, i_usados, i_libres = (int(x) if x.isdigit() else 0
                                           for x in inodos[camino])
            campos.update({"inodes_total": i_total, "inodes_used": i_usados,
                           "inodes_free": i_libres})
            if i_total:
                campos["inodes_used_percent"] = 100.0 * i_usados / i_total
        etiquetas = {"host": host, "device": dispositivo.replace("/dev/", ""),
                     "fstype": tipo, "path": camino, "mode": "rw"}
        puntos.append(punto("disk", etiquetas, campos, cuando))
    return puntos


def metricas_processes(host, bloques, cuando):
    campos = {nombre: 0 for nombre in set(ESTADOS_PS.values())}
    campos.update({"total": 0, "unknown": 0})
    for linea in bloques.get("ps", []):
        estado = (linea.strip() or "?")[0]
        campos["total"] += 1
        campos[ESTADOS_PS.get(estado, "unknown")] = \
            campos.get(ESTADOS_PS.get(estado, "unknown"), 0) + 1
    if not campos["total"]:
        return []
    campos["total_threads"] = sum(
        int(l.strip()) for l in bloques.get("hilos", []) if l.strip().isdigit())
    return [punto("processes", {"host": host}, campos, cuando)]


def metricas_procesos_top(host, lineas, cuando):
    """NO es un nombre nativo: `procstat` pide un estado por PID que aqui no hay.

    Se llama distinto a proposito, para que nadie lo confunda con el complemento
    nativo cuando en O2b lleguen los dos a la vez.
    """
    puntos = []
    for posicion, linea in enumerate(lineas, start=1):
        trozos = linea.split(None, 2)
        if len(trozos) < 3:
            continue
        campos = {"cpu_usage": float(trozos[0]), "memoria_usage": float(trozos[1])}
        # `puesto` va de ETIQUETA, no de campo: con tres `sshd` en la lista, si
        # el puesto fuera un campo las tres lineas serian la misma serie en el
        # mismo instante y InfluxDB se quedaria solo con la ultima.
        puntos.append(punto("procesos_top",
                            {"host": host, "proceso": trozos[2].strip(),
                             "puesto": str(posicion)},
                            campos, cuando))
    return puntos


# ---------------------------------------------------------------------------
def interrogar(destino, llave):
    """Una conexion SSH, una foto completa del servidor."""
    host, _, puerto = destino.partition(":")
    orden = [
        "ssh", "-n", "-q",
        "-o", "BatchMode=yes",
        # En el laboratorio los contenedores se recrean y con ellos su llave de
        # maquina. En un cliente esto NO se deja asi: se fija la huella del
        # servidor. Esta escrito en el documento de permisos.
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ConnectTimeout=" + str(ESPERA),
        "-i", llave,
    ]
    if puerto:
        orden += ["-p", puerto]
    orden += [USUARIO + "@" + host, COMANDO_REMOTO]

    completado = subprocess.run(orden, capture_output=True, text=True,
                                timeout=ESPERA + 4)
    if completado.returncode != 0:
        raise RuntimeError("ssh " + host + " devolvio " + str(completado.returncode) +
                           ": " + (completado.stderr or "").strip()[:200])
    return host, trocear(completado.stdout)


def main():
    if not OBJETIVOS:
        sys.stderr.write("KX_OBJETIVOS esta vacio: no hay a quien preguntar\n")
        return 0

    cuando = int(time.time() * 1e9)
    llave = llave_utilizable()
    lineas = []
    for destino in OBJETIVOS:
        try:
            host, bloques = interrogar(destino, llave)
        except Exception as exc:
            # Que un servidor caido no deje sin metricas a los demas.
            sys.stderr.write(str(exc) + "\n")
            continue
        lineas += metricas_cpu(host, bloques.get("stat", []), cuando)
        lineas += metricas_mem(host, bloques.get("meminfo", []), cuando)
        lineas += metricas_system(host, bloques, cuando)
        lineas += metricas_net(host, bloques.get("netdev", []), cuando)
        lineas += metricas_net_protocolo(host, bloques.get("snmp", []), cuando)
        lineas += metricas_diskio(host, bloques.get("diskstats", []), cuando)
        lineas += metricas_disk(host, bloques, cuando)
        lineas += metricas_processes(host, bloques, cuando)
        lineas += metricas_procesos_top(host, bloques.get("top", []), cuando)

    for linea in lineas:
        if linea:
            print(linea)
    return 0


if __name__ == "__main__":
    sys.exit(main())
