"""Genera grafana/dashboards/infraestructura.json (ETAPA O2a.4).

Se escribe con un programa y no a mano porque un tablero de Grafana son
cientos de lineas de JSON repetido, y lo repetido a mano se equivoca.
"""
import json

FUENTE = {"type": "influxdb", "uid": "influxdb-jmeter"}


def flux(consulta, ref="A"):
    return {"datasource": FUENTE, "query": consulta, "refId": ref,
            "hide": False, "rawQuery": True, "resultFormat": "time_series"}


def serie(titulo, x, y, ancho, alto, objetivos, unidad="short", descripcion="",
          overrides=None, relleno=15, apilado="none"):
    return {
        "type": "timeseries", "title": titulo, "description": descripcion,
        "datasource": FUENTE, "gridPos": {"x": x, "y": y, "w": ancho, "h": alto},
        "targets": objetivos,
        "fieldConfig": {
            "defaults": {
                "unit": unidad,
                "color": {"mode": "palette-classic"},
                "custom": {
                    "drawStyle": "line", "lineInterpolation": "smooth",
                    "lineWidth": 2, "fillOpacity": relleno, "showPoints": "never",
                    "spanNulls": True, "axisPlacement": "auto",
                    "stacking": {"group": "A", "mode": apilado},
                },
            },
            "overrides": overrides or [],
        },
        "options": {
            "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
    }


def cifra(titulo, x, y, ancho, alto, objetivos, unidad="short", descripcion=""):
    return {
        "type": "stat", "title": titulo, "description": descripcion,
        "datasource": FUENTE, "gridPos": {"x": x, "y": y, "w": ancho, "h": alto},
        "targets": objetivos,
        "fieldConfig": {"defaults": {"unit": unidad,
                                     "color": {"mode": "thresholds"},
                                     "thresholds": {"mode": "absolute",
                                                    "steps": [{"color": "green", "value": None}]}},
                        "overrides": []},
        "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                    "colorMode": "value", "graphMode": "area",
                    "textMode": "auto", "justifyMode": "auto"},
    }


def tabla(titulo, x, y, ancho, alto, objetivos, descripcion=""):
    return {
        "type": "table", "title": titulo, "description": descripcion,
        "datasource": FUENTE, "gridPos": {"x": x, "y": y, "w": ancho, "h": alto},
        "targets": objetivos,
        "fieldConfig": {"defaults": {"custom": {"align": "auto"}}, "overrides": []},
        "options": {"showHeader": True,
                    "sortBy": [{"displayName": "media_ms", "desc": True}]},
    }


def fila(titulo, y):
    return {"type": "row", "title": titulo, "collapsed": False,
            "gridPos": {"x": 0, "y": y, "w": 24, "h": 1}, "panels": []}


# --- Trozos de Flux que se repiten -----------------------------------------
RANGO = '  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)'
CORRIDA = '  |> filter(fn: (r) => r["corrida"] == "${corrida}")'


MODO = '  |> filter(fn: (r) => r["modo"] == "${modo}")'


def infra(medida, campos, extra="", host=None, cola=None, modo=False):
    lineas = ['from(bucket: "infra")', RANGO,
              '  |> filter(fn: (r) => r["_measurement"] == "%s")' % medida]
    if host:
        lineas.append('  |> filter(fn: (r) => r["host"] == "%s")' % host)
    lineas.append(CORRIDA)
    # Solo las medidas del servidor existen en los dos modos. Las de PostgreSQL
    # y las de Docker son siempre del recolector sin agente: filtrarlas por
    # `modo` las dejaria vacias al elegir «agente».
    if modo:
        lineas.append(MODO)
    if campos:
        condicion = " or ".join('r["_field"] == "%s"' % c for c in campos)
        lineas.append('  |> filter(fn: (r) => %s)' % condicion)
    if extra:
        lineas.append(extra)
    lineas.append('  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)')
    if cola:
        lineas.append(cola)
    return "\n".join(lineas)


paneles = []
y = 0

# ===========================================================================
paneles.append(fila("El servidor — modo «$modo»", y)); y += 1

paneles.append(serie(
    "CPU del servidor", 0, y, 12, 8,
    [flux(infra("cpu", ["usage_user", "usage_system", "usage_iowait"],
                host="lab_servidor", modo=True,
                cola='  |> keep(columns: ["_time", "_value", "_field"])'))],
    unidad="percent", apilado="normal", relleno=40,
    descripcion="Mismos campos en los dos modos: `usage_user`, `usage_system` "
                "y `usage_iowait`. Cambiar el selector «Modo» de arriba no "
                "cambia la consulta, solo de donde vienen los datos — esa es "
                "toda la promesa de O-D13."))

paneles.append(serie(
    "Carga del sistema", 12, y, 7, 8,
    [flux(infra("system", ["load1", "load5", "load15"], host="lab_servidor",
                modo=True,
                cola='  |> keep(columns: ["_time", "_value", "_field"])'))],
    descripcion="/proc/loadavg. Medida `system`, la nativa."))

paneles.append(cifra(
    "Memoria en uso", 19, y, 5, 4,
    [flux(infra("mem", ["used_percent"], host="lab_servidor", modo=True))],
    unidad="percent", descripcion="Medida `mem`, campo `used_percent`."))

paneles.append(cifra(
    "Procesos", 19, y + 4, 5, 4,
    [flux(infra("processes", ["total"], host="lab_servidor", modo=True))],
    descripcion="Medida `processes`. Es del contenedor: los PID si estan "
                "separados, a diferencia de la CPU y la memoria."))
y += 8

# ===========================================================================
paneles.append(fila("La base de datos — sin agente, por conexion", y)); y += 1

paneles.append(serie(
    "Conexiones por estado", 0, y, 8, 8,
    [flux(infra("postgresql_actividad", ["conexiones"],
                cola='  |> keep(columns: ["_time", "_value", "estado"])'))],
    descripcion="pg_stat_activity, agrupado por estado. Rol de solo lectura."))

paneles.append(serie(
    "Transacciones por segundo", 8, y, 8, 8,
    [flux(infra("postgresql", ["xact_commit", "xact_rollback"],
                extra='  |> filter(fn: (r) => r["db"] == "tienda")\n'
                      '  |> toFloat()\n'
                      '  |> derivative(unit: 1s, nonNegative: true)',
                cola='  |> keep(columns: ["_time", "_value", "_field"])'))],
    descripcion="Derivada de pg_stat_database.xact_commit. La medida "
                "`postgresql` es la del complemento nativo."))

paneles.append(serie(
    "Acierto de cache", 16, y, 8, 8,
    [flux('\n'.join([
        'from(bucket: "infra")', RANGO,
        '  |> filter(fn: (r) => r["_measurement"] == "postgresql")',
        '  |> filter(fn: (r) => r["db"] == "tienda")',
        CORRIDA,
        '  |> filter(fn: (r) => r["_field"] == "blks_hit" or r["_field"] == "blks_read")',
        '  |> toFloat()',
        '  |> derivative(unit: 1s, nonNegative: true)',
        '  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)',
        '  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")',
        '  |> map(fn: (r) => ({ _time: r._time, _value:',
        '       if (r.blks_hit + r.blks_read) > 0.0',
        '       then 100.0 * r.blks_hit / (r.blks_hit + r.blks_read)',
        '       else 100.0 }))',
    ]))],
    unidad="percent",
    descripcion="blks_hit / (blks_hit + blks_read). Cuando cae, la base esta "
                "yendo a disco."))
y += 8

paneles.append(tabla(
    "Las diez consultas mas lentas", 0, y, 16, 8,
    [flux('\n'.join([
        'from(bucket: "infra")', RANGO,
        '  |> filter(fn: (r) => r["_measurement"] == "postgresql_consultas_lentas")',
        CORRIDA,
        '  |> filter(fn: (r) => r["_field"] == "media_ms" or r["_field"] == "maxima_ms"'
        ' or r["_field"] == "llamadas")',
        '  |> last()',
        '  |> pivot(rowKey: ["consulta"], columnKey: ["_field"], valueColumn: "_value")',
        '  |> keep(columns: ["consulta", "media_ms", "maxima_ms", "llamadas"])',
        '  |> group()',
        '  |> sort(columns: ["media_ms"], desc: true)',
        '  |> limit(n: 10)',
    ]))],
    descripcion="pg_stat_statements. Es lo que convierte «la base va lenta» en "
                "«esta consulta va lenta»."))

paneles.append(cifra(
    "Tamano de la base", 16, y, 4, 8,
    [flux(infra("postgresql_tamano", ["bytes"],
                extra='  |> filter(fn: (r) => r["base"] == "tienda")'))],
    unidad="bytes"))

paneles.append(cifra(
    "Bloqueos en espera", 20, y, 4, 8,
    [flux(infra("postgresql_bloqueos", ["esperando"],
                cola='  |> group()\n  |> sum()') .replace(
        '  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)\n', ''))],
    descripcion="pg_locks con granted = false. Si sube, algo esta esperando a "
                "que otro suelte."))
y += 8

# ===========================================================================
paneles.append(fila("Los contenedores — por el socket de Docker (O-D16)", y)); y += 1

paneles.append(serie(
    "CPU por contenedor", 0, y, 12, 8,
    [flux(infra("docker_container_cpu", ["usage_percent"],
                cola='  |> keep(columns: ["_time", "_value", "container_name"])'))],
    unidad="percent",
    descripcion="Esto SI es del contenedor, no de la maquina. Leer el socket de "
                "Docker equivale a ser administrador: ver el documento de permisos."))

paneles.append(serie(
    "Memoria por contenedor", 12, y, 12, 8,
    [flux(infra("docker_container_mem", ["usage"],
                cola='  |> keep(columns: ["_time", "_value", "container_name"])'))],
    unidad="bytes"))
y += 8

# ===========================================================================
paneles.append(fila("La prueba y el servidor, en la misma corrida", y)); y += 1

paneles.append(serie(
    "Tiempo de respuesta de la prueba  vs  CPU del servidor", 0, y, 24, 10,
    [
        flux('\n'.join([
            'from(bucket: "jmeter")', RANGO,
            '  |> filter(fn: (r) => r["_measurement"] == "jmeter")',
            '  |> filter(fn: (r) => r["application"] == "${corrida}")',
            '  |> filter(fn: (r) => r["_field"] == "avg")',
            '  |> filter(fn: (r) => r["statut"] == "all")',
            '  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)',
            '  |> set(key: "_field", value: "Tiempo de respuesta (ms)")',
            '  |> keep(columns: ["_time", "_value", "_field"])',
        ]), ref="A"),
        flux('\n'.join([
            'from(bucket: "infra")', RANGO,
            '  |> filter(fn: (r) => r["_measurement"] == "cpu")',
            '  |> filter(fn: (r) => r["host"] == "lab_servidor")',
            CORRIDA,
            '  |> filter(fn: (r) => r["_field"] == "usage_idle")',
            '  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)',
            '  |> map(fn: (r) => ({ r with _value: 100.0 - r._value }))',
            '  |> set(key: "_field", value: "CPU en uso (%)")',
            '  |> keep(columns: ["_time", "_value", "_field"])',
        ]), ref="B"),
    ],
    unidad="ms", relleno=8,
    overrides=[{
        "matcher": {"id": "byName", "options": "CPU en uso (%)"},
        "properties": [
            {"id": "unit", "value": "percent"},
            {"id": "custom.axisPlacement", "value": "right"},
            {"id": "custom.axisLabel", "value": "CPU en uso (%)"},
            {"id": "color", "value": {"mode": "fixed", "fixedColor": "orange"}},
        ],
    }],
    descripcion="Las dos lineas del mismo rato. La de arriba viene del cubo "
                "`jmeter` por la etiqueta `application`; la de abajo del cubo "
                "`infra` por la etiqueta `corrida`. Son la MISMA cadena (O-D14), "
                "y esa coincidencia es toda la correlacion."))
y += 10

# ===========================================================================
paneles.append(fila("Los dos modos, lado a lado (O2b)", y)); y += 1

paneles.append(serie(
    "CPU del servidor: el agente (1 s) y el modo sin agente (10 s)", 0, y, 16, 9,
    [flux('\n'.join([
        'from(bucket: "infra")', RANGO,
        '  |> filter(fn: (r) => r["_measurement"] == "cpu")',
        '  |> filter(fn: (r) => r["host"] == "lab_servidor")',
        CORRIDA,
        '  |> filter(fn: (r) => r["_field"] == "usage_idle")',
        '  |> map(fn: (r) => ({ r with _value: 100.0 - r._value }))',
        '  |> keep(columns: ["_time", "_value", "modo"])',
    ]))],
    unidad="percent", relleno=0,
    descripcion="La MISMA maquina, medida de las dos formas a la vez. Los dos "
                "modos coinciden cuando la carga es sostenida; donde se separan "
                "es en los picos cortos: diez segundos de media aplastan un pico "
                "de tres. En la etapa O2b un pico real del 96 % aparecio como un "
                "26 % en el modo sin agente."))

paneles.append(serie(
    "Cuantos puntos por minuto escribe cada modo", 16, y, 8, 9,
    [flux('\n'.join([
        'from(bucket: "infra")', RANGO,
        '  |> filter(fn: (r) => r["_measurement"] == "cpu")',
        '  |> filter(fn: (r) => r["host"] == "lab_servidor")',
        CORRIDA,
        '  |> filter(fn: (r) => r["_field"] == "usage_idle")',
        '  |> aggregateWindow(every: 1m, fn: count, createEmpty: false)',
        '  |> keep(columns: ["_time", "_value", "modo"])',
    ]))],
    descripcion="60 y 6. Es la diferencia entre O-D18 (un segundo) y los diez "
                "segundos del modo sin agente, contada en puntos."))

tablero = {
    "uid": "kinetix-infraestructura",
    "title": "Kinetix — Infraestructura (sin agente)",
    "description": "ETAPA O2a. Servidor y base de datos mirados sin instalarles "
                   "nada, con la misma etiqueta de corrida que la prueba.",
    "tags": ["kinetix", "infraestructura", "sin-agente"],
    "timezone": "browser",
    "editable": True,
    "graphTooltip": 1,
    "schemaVersion": 38,
    "version": 2,
    "refresh": "10s",
    "time": {"from": "now-30m", "to": "now"},
    "timepicker": {},
    "fiscalYearStartMonth": 0,
    "weekStart": "",
    "style": "dark",
    "links": [],
    "liveNow": False,
    "annotations": {"list": []},
    "templating": {"list": [{
        "name": "modo",
        "label": "Modo",
        "description": "Con agente instalado en el servidor (un dato por "
                       "segundo) o sin agente, por SSH (uno cada diez). Las "
                       "consultas son LAS MISMAS: solo cambia de donde vienen.",
        "type": "custom",
        "query": "sin_agente,agente",
        "current": {"text": "sin_agente", "value": "sin_agente", "selected": True},
        "options": [
            {"text": "sin_agente", "value": "sin_agente", "selected": True},
            {"text": "agente", "value": "agente", "selected": False},
        ],
        "multi": False, "includeAll": False, "hide": 0, "skipUrlSync": False,
    }, {
        "name": "corrida",
        "label": "Corrida",
        "description": "La corrida de Kinetix. Es la misma cadena que la "
                       "etiqueta `application` del Backend Listener de JMeter.",
        "type": "query",
        "datasource": FUENTE,
        "definition": 'schema.tagValues(bucket: "infra", tag: "corrida")',
        "query": 'import "influxdata/influxdb/schema"\n'
                 'schema.tagValues(bucket: "infra", tag: "corrida", start: -30d)',
        "refresh": 2, "sort": 1, "multi": False, "includeAll": False,
        "hide": 0, "skipUrlSync": False, "regex": "", "current": {}, "options": [],
    }]},
    "panels": paneles,
}

destino = "/g/dashboards/infraestructura.json"
with open(destino, "w", encoding="utf-8") as fichero:
    json.dump(tablero, fichero, indent=2, ensure_ascii=False)
print("escrito:", destino)
print("paneles:", len([p for p in paneles if p["type"] != "row"]),
      "| filas:", len([p for p in paneles if p["type"] == "row"]))
sin_filtro = [p["title"] for p in paneles
              if p["type"] not in ("row",)
              and not any("corrida" in t["query"] or "application" in t["query"]
                          for t in p["targets"])]
print("paneles SIN filtro de corrida:", sin_filtro or "ninguno")
