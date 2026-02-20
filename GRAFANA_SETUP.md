# 📊 Grafana + InfluxDB Setup Guide

Guía completa para configurar monitoreo en tiempo real de pruebas JMeter con Grafana e InfluxDB.

**Versión**: 1.3.0 | **Última actualización**: Diciembre 2024

---

## 🎯 Objetivo

Visualizar métricas de JMeter **en tiempo real** mientras el test se ejecuta, usando:
- **JMeter Backend Listener** → Envía métricas cada 5 segundos
- **InfluxDB 2.7** → Almacena series temporales
- **Grafana 10.2.3** → Visualiza dashboards interactivos

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                        MONITOREO EN TIEMPO REAL                  │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐
│   JMETER     │  1. Backend Listener envía métricas
│   (Local)    │     Cada 5 segundos
│              │     URL: http://localhost:8086/write?db=jmeter
│              │     Token: jmeter-token-2024-super-secret
└──────┬───────┘
       │
       │ HTTP POST con line protocol
       │ application=PerformanceTest
       │ measurement=jmeter
       │
       ↓
┌──────────────┐
│  INFLUXDB    │  2. Almacena series temporales
│  (Docker)    │     Bucket: jmeter
│  Port: 8086  │     Org: performance
│              │     Retención: 30 días
└──────┬───────┘     Formato: Line Protocol
       │
       │ Flux queries cada 5s
       │ from(bucket: "jmeter")
       │
       ↓
┌──────────────┐
│   GRAFANA    │  3. Visualiza dashboards
│  (Docker)    │     9 paneles profesionales
│  Port: 3000  │     Auto-refresh: 5s
│              │     Time range: Last 5 minutes
└──────────────┘
```

---

## 📋 Pre-requisitos

### Servicios Docker Corriendo
```bash
# Verificar que los 5 servicios estén activos
docker-compose ps

# Deberías ver:
✅ jmeter_postgres
✅ jmeter_backend
✅ jmeter_frontend
✅ jmeter_influxdb
✅ jmeter_grafana
```

### Puertos Disponibles
- **3000** - Grafana
- **8086** - InfluxDB

### JMeter Instalado
- JMeter 5.5+ recomendado
- Plugins: ninguno necesario (Backend Listener viene incluido)

---

## 🚀 Instalación Paso a Paso

### Paso 1: Levantar Stack Completo

```bash
# Desde el directorio raíz del proyecto
cd jmeter-analyzer

# Levantar todos los servicios
docker-compose up -d

# Esperar que todos los servicios estén "healthy"
docker-compose ps
```

**Tiempo estimado**: 30-60 segundos

---

### Paso 2: Verificar InfluxDB

```bash
# Verificar que InfluxDB esté corriendo
docker-compose logs influxdb | head -n 20

# Deberías ver:
✅ "Server started"
✅ "InfluxDB started"
```

**Verificar bucket y token**:
```bash
docker exec -it jmeter_influxdb influx bucket list \
  --org performance \
  --token jmeter-token-2024-super-secret
```

**Resultado esperado**:
```
ID                  Name    Retention   Shard group duration
xxxxxxxxxxxxx       jmeter  720h0m0s    24h0m0s
```

---

### Paso 3: Acceder a Grafana

1. **Abrir navegador**: http://localhost:3000
2. **Login inicial**:
   - Usuario: `admin`
   - Contraseña: `admin`
3. **Cambiar contraseña** (recomendado) o Skip
4. **Dashboard principal**: Dashboards → JMeter Performance → JMeter Performance Testing Dashboard

---

### Paso 4: Verificar Datasource

1. En Grafana: **⚙️ Configuration → Data Sources**
2. Buscar: **InfluxDB-JMeter**
3. Click en **InfluxDB-JMeter**
4. Scroll abajo
5. Click en **Save & Test**

**Resultado esperado**:
```
✅ Data source is working. 1 buckets found
```

**Si falla**, verificar:
- InfluxDB está corriendo: `docker-compose ps influxdb`
- Token correcto en `grafana/datasources/influxdb.yml`
- URL correcta: `http://influxdb:8086` (dentro de Docker network)

---

### Paso 5: Configurar JMeter Backend Listener

#### 5.1. Abrir JMeter Test Plan

1. Abrir JMeter
2. Cargar tu Test Plan (ej: `Performance_Test.jmx`)

#### 5.2. Agregar Backend Listener

1. **Click derecho** en Test Plan
2. **Add → Listener → Backend Listener**

#### 5.3. Configurar Backend Listener

**Backend Listener Implementation**:
```
org.apache.jmeter.visualizers.backend.influxdb.InfluxdbBackendListenerClient
```

**Async Queue size**: `5000`

**Parámetros** (agregar manualmente):

| Name | Value | Descripción |
|------|-------|-------------|
| `influxdbMetricsSender` | `org.apache.jmeter.visualizers.backend.influxdb.HttpMetricsSender` | Clase sender |
| `influxdbUrl` | `http://localhost:8086/write?db=jmeter` | URL InfluxDB (v1 compat) |
| `application` | `PerformanceTest` | Nombre de tu aplicación |
| `measurement` | `jmeter` | Nombre de la measurement |
| `summaryOnly` | `false` | Enviar todas las métricas |
| `samplersRegex` | `.*` | Regex para samplers (todos) |
| `percentiles` | `90;95;99` | Percentiles a calcular |
| `testTitle` | `Test Performance` | Título del test |
| `influxdbToken` | `jmeter-token-2024-super-secret` | **CRÍTICO**: Token de auth |

#### 5.4. Screenshot de Configuración

```
┌────────────────────────────────────────────────────────────┐
│ Backend Listener                                            │
├────────────────────────────────────────────────────────────┤
│ Name: Backend Listener                                      │
│                                                              │
│ Backend Listener Implementation:                            │
│ org.apache.jmeter.visualizers.backend.influxdb...Client    │
│                                                              │
│ Async Queue size: 5000                                      │
│                                                              │
│ Parameters:                                                  │
│ ┌──────────────────────┬─────────────────────────────────┐│
│ │ Name                 │ Value                           ││
│ ├──────────────────────┼─────────────────────────────────┤│
│ │ influxdbMetricsSender│ org.apache.jmeter.visualizers...││
│ │ influxdbUrl          │ http://localhost:8086/write?... ││
│ │ application          │ PerformanceTest                 ││
│ │ measurement          │ jmeter                          ││
│ │ summaryOnly          │ false                           ││
│ │ samplersRegex        │ .*                              ││
│ │ percentiles          │ 90;95;99                        ││
│ │ testTitle            │ Test Performance                ││
│ │ influxdbToken        │ jmeter-token-2024-super-secret ││
│ └──────────────────────┴─────────────────────────────────┘│
└────────────────────────────────────────────────────────────┘
```

#### 5.5. Guardar Test Plan

```bash
# Guardar en JMeter
File → Save Test Plan As → Performance_Test_With_Grafana.jmx
```

---

### Paso 6: Ejecutar Test y Ver Métricas

#### 6.1. Ejecutar Test
```bash
# En JMeter
Run → Start (Ctrl+R)
```

#### 6.2. Ver Logs de JMeter

**✅ Logs correctos** (envío exitoso):
```
INFO o.a.j.v.b.BackendListener: Started worker
INFO o.a.j.v.b.i.HttpMetricsSender: Sent 150 metrics to InfluxDB
```

**❌ Logs con error** (revisa configuración):
```
ERROR o.a.j.v.b.i.HttpMetricsSender: Error writing metrics to influxDB
responseCode: 401
responseBody: {"code":"unauthorized","message":"unauthorized access"}
```

**Solución error 401**: Verificar que `influxdbToken` esté configurado correctamente.

#### 6.3. Ver Dashboard en Grafana

1. **Abrir Grafana**: http://localhost:3000/d/jmeter-performance
2. **Time range**: Cambiar a "Last 5 minutes"
3. **Auto-refresh**: Ya configurado en 5s

**Dentro de 30 segundos**, deberías ver:
- ✅ Response Time Over Time - Gráfica con líneas
- ✅ Active Threads - Área verde
- ✅ Error Rate - Gauge con porcentaje
- ✅ Throughput - Gauge con req/s
- ✅ Total Requests - Contador incrementándose
- ✅ Total Errors - Contador rojo
- ✅ Percentiles - 3 líneas (p90/p95/p99)
- ✅ Requests by Transaction - Pie chart
- ✅ Transaction Details - Tabla con métricas

---

## 📊 Paneles de Grafana Explicados

### Panel 1: 📊 Response Time Over Time
**Tipo**: Time series (líneas)
**Métrica**: Tiempo de respuesta promedio por transacción
**Query Flux**:
```flux
from(bucket: "jmeter")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "jmeter")
  |> filter(fn: (r) => r["_field"] == "avg")
  |> filter(fn: (r) => r["statut"] == "all")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
```
**Interpretación**:
- ✅ **Línea estable**: Performance consistente
- ⚠️ **Picos ocasionales**: Posibles timeouts o GC
- ❌ **Línea ascendente**: Sistema degradándose

---

### Panel 2: 👥 Active Threads
**Tipo**: Time series (área)
**Métrica**: Hilos activos (usuarios virtuales)
**Query Flux**:
```flux
from(bucket: "jmeter")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "jmeter")
  |> filter(fn: (r) => r["_field"] == "meanAT")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
```
**Interpretación**:
- **Ramp-up**: Aumento gradual de usuarios
- **Steady state**: Meseta de carga constante
- **Ramp-down**: Disminución gradual

---

### Panel 3: ❌ Error Rate
**Tipo**: Gauge (medidor)
**Métrica**: Porcentaje de errores
**Query Flux**:
```flux
from(bucket: "jmeter")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "jmeter")
  |> filter(fn: (r) => r["_field"] == "countError" or r["_field"] == "count")
  |> filter(fn: (r) => r["transaction"] == "all")
  |> aggregateWindow(every: v.windowPeriod, fn: last, createEmpty: false)
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> map(fn: (r) => ({ r with error_rate: 
      if exists r.count and r.count > 0 
      then float(v: r.countError) / float(v: r.count) 
      else 0.0 
    }))
```
**Umbrales**:
- 🟢 **< 1%**: Excelente
- 🟡 **1-5%**: Aceptable
- 🔴 **> 5%**: Crítico

---

### Panel 4: 🚀 Throughput
**Tipo**: Gauge (medidor)
**Métrica**: Requests por segundo
**Query Flux**:
```flux
from(bucket: "jmeter")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "jmeter")
  |> filter(fn: (r) => r["_field"] == "count")
  |> filter(fn: (r) => r["transaction"] == "all")
  |> aggregateWindow(every: 5s, fn: sum, createEmpty: false)
  |> map(fn: (r) => ({ r with _value: float(v: r._value) / 5.0 }))
```
**Interpretación**:
- **Estable**: Sistema procesando carga constante
- **Bajando con más usuarios**: Cuello de botella
- **Creciendo con usuarios**: Escalando correctamente

---

### Panel 5: 📈 Total Requests
**Tipo**: Stat (contador)
**Métrica**: Suma total de requests
**Query Flux**:
```flux
from(bucket: "jmeter")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "jmeter")
  |> filter(fn: (r) => r["_field"] == "count")
  |> filter(fn: (r) => r["transaction"] == "all")
  |> aggregateWindow(every: v.windowPeriod, fn: last, createEmpty: false)
```

---

### Panel 6: 💥 Total Errors
**Tipo**: Stat (contador)
**Métrica**: Suma total de errores
**Query Flux**: Similar al Panel 5, pero con `countError`

---

### Panel 7: 📊 Response Time Percentiles
**Tipo**: Time series (líneas)
**Métrica**: p90, p95, p99
**Query Flux**:
```flux
from(bucket: "jmeter")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "jmeter")
  |> filter(fn: (r) => r["_field"] == "pct90.0" or r["_field"] == "pct95.0" or r["_field"] == "pct99.0")
  |> filter(fn: (r) => r["transaction"] == "all")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
```
**Interpretación**:
- **p90**: 90% de requests están debajo de este tiempo
- **p95**: 95% de requests están debajo
- **p99**: 99% de requests están debajo (outliers)

---

### Panel 8: 🏷️ Requests by Transaction
**Tipo**: Pie chart
**Métrica**: Distribución de requests por endpoint
**Query Flux** (CORREGIDA):
```flux
from(bucket: "jmeter")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "jmeter")
  |> filter(fn: (r) => r["_field"] == "count")
  |> filter(fn: (r) => r["transaction"] != "all" and r["transaction"] != "internal")
  |> filter(fn: (r) => r["statut"] == "all")
  |> group(columns: ["transaction"])
  |> last()
  |> group()
```
**Interpretación**: Visualiza qué endpoints tienen más carga

---

### Panel 9: 📋 Transaction Details
**Tipo**: Table
**Métrica**: Todas las métricas por transacción
**Query Flux** (CORREGIDA):
```flux
from(bucket: "jmeter")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "jmeter")
  |> filter(fn: (r) => r["transaction"] != "internal" and r["transaction"] != "all")
  |> filter(fn: (r) => r["statut"] == "all")
  |> group(columns: ["transaction", "_field"])
  |> last()
  |> group(columns: ["transaction"])
  |> pivot(rowKey:["transaction"], columnKey: ["_field"], valueColumn: "_value")
  |> keep(columns: ["transaction", "count", "countError", "avg", "min", "max", "pct90.0", "pct95.0", "pct99.0"])
```
**Interpretación**: Tabla completa con métricas desglosadas por endpoint

---

## 🔧 Comandos Útiles

### Verificar Datos en InfluxDB

```bash
# Ver últimos 10 registros
docker exec -it jmeter_influxdb influx query \
  'from(bucket: "jmeter") |> range(start: -5m) |> limit(n: 10)' \
  --org performance \
  --token jmeter-token-2024-super-secret

# Contar registros de los últimos 5 minutos
docker exec -it jmeter_influxdb influx query \
  'from(bucket: "jmeter") |> range(start: -5m) |> count()' \
  --org performance \
  --token jmeter-token-2024-super-secret

# Ver transacciones únicas
docker exec -it jmeter_influxdb influx query \
  'from(bucket: "jmeter") |> range(start: -5m) |> keep(columns: ["transaction"]) |> distinct(column: "transaction")' \
  --org performance \
  --token jmeter-token-2024-super-secret
```

### Borrar Datos de Prueba

```bash
# Borrar todos los datos del bucket jmeter
docker exec -it jmeter_influxdb influx delete \
  --bucket jmeter \
  --start 1970-01-01T00:00:00Z \
  --stop $(date -u +"%Y-%m-%dT%H:%M:%SZ") \
  --org performance \
  --token jmeter-token-2024-super-secret
```

### Reiniciar Grafana

```bash
# Reiniciar servicio Grafana
docker-compose restart grafana

# Ver logs de Grafana
docker-compose logs -f grafana
```

---

## 🐛 Troubleshooting

### Problema: Grafana muestra "No data"

**Síntoma**: Todos los paneles dicen "No data"

**Causas posibles**:

#### 1. JMeter no está enviando datos

```bash
# Ver logs de JMeter - Buscar estas líneas:
✅ INFO o.a.j.v.b.BackendListener: Started worker
✅ INFO o.a.j.v.b.i.HttpMetricsSender: Sent 150 metrics

# Si ves errores:
❌ ERROR o.a.j.v.b.i.HttpMetricsSender: Error writing metrics
```

**Solución**: Revisar configuración de Backend Listener (Paso 5)

#### 2. InfluxDB no tiene datos

```bash
# Verificar datos en InfluxDB
docker exec -it jmeter_influxdb influx query \
  'from(bucket: "jmeter") |> range(start: -1h) |> limit(n: 5)' \
  --org performance \
  --token jmeter-token-2024-super-secret

# Si retorna vacío, JMeter no está enviando datos
```

**Solución**: Verificar que JMeter esté ejecutándose y token sea correcto

#### 3. Datasource no configurado

```bash
# En Grafana: Configuration → Data Sources → InfluxDB-JMeter
# Click "Save & Test"
# Debe decir: "Data source is working"
```

**Solución**: Verificar URL, token, org, bucket en `grafana/datasources/influxdb.yml`

---

### Problema: Error 401 Unauthorized en JMeter

**Síntoma**:
```
ERROR o.a.j.v.b.i.HttpMetricsSender: Error writing metrics to influxDB
responseCode: 401
responseBody: {"code":"unauthorized","message":"unauthorized access"}
```

**Causa**: Token faltante o incorrecto

**Solución**:
```bash
# Verificar que influxdbToken esté en Backend Listener
# Name: influxdbToken
# Value: jmeter-token-2024-super-secret

# Verificar token en .env
cat .env | grep INFLUXDB_TOKEN
```

---

### Problema: Panel "Requests by Transaction" muestra "No data"

**Causa**: Query incorrecta (bug corregido en v1.3.0)

**Solución**:
1. Editar panel en Grafana
2. Reemplazar query con la versión corregida (ver Panel 8 arriba)
3. Apply

---

### Problema: Panel "Transaction Details" muestra "No data"

**Causa**: Query incorrecta (bug corregido en v1.3.0)

**Solución**:
1. Editar panel en Grafana
2. Reemplazar query con la versión corregida (ver Panel 9 arriba)
3. Apply

---

## 📚 Referencias

- **InfluxDB Flux Language**: https://docs.influxdata.com/flux/
- **Grafana Dashboards**: https://grafana.com/docs/grafana/latest/dashboards/
- **JMeter Backend Listener**: https://jmeter.apache.org/usermanual/realtime-results.html
- **InfluxDB Line Protocol**: https://docs.influxdata.com/influxdb/v2.7/reference/syntax/line-protocol/

---

## ✅ Checklist de Verificación

- [ ] Docker Compose levantado (`docker-compose ps`)
- [ ] InfluxDB corriendo y bucket "jmeter" existe
- [ ] Grafana accesible en http://localhost:3000
- [ ] Datasource "InfluxDB-JMeter" configurado y testeado
- [ ] Dashboard "JMeter Performance Testing Dashboard" visible
- [ ] JMeter Backend Listener configurado con todos los parámetros
- [ ] `influxdbToken` agregado correctamente
- [ ] Test JMeter ejecutándose
- [ ] Logs de JMeter muestran "Sent X metrics"
- [ ] Grafana muestra datos en los 9 paneles

---

**¡Listo! Ya tienes monitoreo en tiempo real de tus pruebas de performance.** 🎉
