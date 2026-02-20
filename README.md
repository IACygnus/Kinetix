# JMeter Analyzer Pro

Sistema profesional de análisis y gestión de reportes JMeter con **IA integrada** (Gemini) y **monitoreo en tiempo real** (Grafana + InfluxDB)

**Versión: 1.3.0** | Última actualización: Diciembre 2024

---

## ⚡ CONFIGURACIÓN RÁPIDA

### Paso 1: Clonar el Repositorio
```bash
git clone https://github.com/tu-usuario/jmeter-analyzer.git
cd jmeter-analyzer
```

### Paso 2: Configurar API Key de Gemini
```bash
# Editar archivo .env
nano .env

# Buscar la línea: GEMINI_API_KEY=
# Pegar tu API Key completa de Google AI Studio
# Obtener en: https://makersuite.google.com/app/apikey
```

### Paso 3: Levantar el Proyecto
```bash
# Primera vez: construir imágenes
docker-compose up --build -d

# Siguientes veces: solo levantar
docker-compose up -d
```

### Paso 4: Acceder a la Aplicación

| Servicio | URL | Credenciales |
|----------|-----|--------------|
| **Frontend (React)** | http://localhost:5173 | admin@jmeter.com / admin123 |
| **Backend API** | http://localhost:8001 | - |
| **API Docs (Swagger)** | http://localhost:8001/docs | - |
| **Grafana Dashboards** | http://localhost:3000 | admin / admin (cambiar en primer login) |
| **InfluxDB** | http://localhost:8086 | admin / admin123 |
| **PostgreSQL** | localhost:5432 | jmeter_user / jmeter_secure_2024 |

---

## 🎯 Características Principales

### 📊 Análisis Post-Ejecución (JTL Upload)
- ✅ **Upload de archivos JTL/CSV** - Sube resultados de JMeter
- ✅ **Dashboard interactivo** - Métricas en tiempo real
- ✅ **8 gráficos de performance** - Visualización avanzada con Recharts
- ✅ **Análisis con IA (Gemini 1.5 Pro)** - 10 análisis individuales + síntesis inteligente
- ✅ **Conclusiones ejecutivas** - IA sintetiza todos los análisis en 4-5 puntos
- ✅ **Recomendaciones priorizadas** - CRÍTICO/ALTO/MEDIO basadas en patrones
- ✅ **Edición inline** - Todos los análisis son editables
- ✅ **Exportación PDF/HTML** - Reportes profesionales descargables

### 📈 Monitoreo en Tiempo Real (Grafana) ✨ **NUEVO v1.3.0**
- ✅ **9 paneles de Grafana** - Visualización en vivo mientras JMeter ejecuta
- ✅ **Integración JMeter → InfluxDB** - Backend Listener envía métricas cada 5s
- ✅ **Métricas en tiempo real**: Response Time, Throughput, Error Rate, Active Threads, Percentiles (p90/p95/p99)
- ✅ **Retención de 30 días** - Historial de métricas en InfluxDB
- ✅ **Auto-refresh cada 5s** - Dashboard se actualiza automáticamente

---

## 🛠️ Stack Tecnológico

### Backend
- **FastAPI 0.104+** - Framework web moderno asíncrono
- **PostgreSQL 15** - Base de datos relacional
- **SQLAlchemy** - ORM async
- **Pandas** - Procesamiento de datos JTL
- **Google Generative AI** - Integración con Gemini 1.5 Pro

### Frontend
- **React 18** con TypeScript
- **Vite** - Build tool ultrarápido
- **Tailwind CSS** - Diseño moderno y responsivo
- **Recharts** - Gráficos interactivos
- **html2canvas + jsPDF** - Exportación PDF

### Monitoreo (✨ NUEVO v1.3.0)
- **Grafana 10.2.3** - Dashboards de tiempo real
- **InfluxDB 2.7** - Base de datos de series temporales
- **JMeter Backend Listener** - Envío de métricas a InfluxDB

### DevOps
- **Docker + Docker Compose** - Containerización
- **Volúmenes persistentes** - Datos permanentes

---

## 📋 Requisitos

- ✅ **Docker Desktop** instalado y corriendo
- ✅ **Docker Compose** v2.0+
- ✅ **Puertos libres**: 5173 (frontend), 8001 (backend), 5432 (PostgreSQL), 3000 (Grafana), 8086 (InfluxDB)
- ✅ **RAM**: Mínimo 4GB libres
- ✅ **API Key de Gemini** - Gratuita en https://makersuite.google.com/app/apikey

---

## 🚀 Guía de Inicio

### 1. Verificar Docker
```bash
# Verificar que Docker esté corriendo
docker --version
docker-compose --version

# Verificar que Docker Desktop esté activo (Windows/Mac)
```

### 2. Configurar Variables de Entorno
```bash
# Editar .env
nano .env
```

**Variables críticas**:
```env
# API Key de Gemini (OBLIGATORIO)
GEMINI_API_KEY=tu_api_key_aqui

# Base de datos PostgreSQL
DATABASE_URL=postgresql+asyncpg://jmeter_user:jmeter_secure_2024@postgres:5432/jmeter_analyzer_db

# InfluxDB (para Grafana)
INFLUXDB_TOKEN=jmeter-token-2024-super-secret
INFLUXDB_ORG=performance
INFLUXDB_BUCKET=jmeter
```

### 3. Levantar Servicios
```bash
# Primera vez: construir imágenes (tarda 3-5 minutos)
docker-compose up --build -d

# Siguientes veces: solo levantar
docker-compose up -d

# Ver logs mientras inicia
docker-compose logs -f
```

### 4. Verificar Estado
```bash
docker-compose ps
```

**Deberías ver 5 servicios corriendo**:
```
✅ jmeter_postgres  (PostgreSQL 15)
✅ jmeter_backend   (FastAPI)
✅ jmeter_frontend  (React)
✅ jmeter_influxdb  (InfluxDB 2.7)
✅ jmeter_grafana   (Grafana 10.2.3)
```

### 5. Acceso Inicial

#### Frontend (Upload JTL)
1. Abrir: http://localhost:5173
2. Login: `admin@jmeter.com` / `admin123`
3. Subir archivo JTL
4. Ver dashboard con análisis IA

#### Grafana (Monitoreo en Tiempo Real)
1. Abrir: http://localhost:3000
2. Login: `admin` / `admin` (cambiar contraseña en primer login)
3. Dashboard: **JMeter Performance → JMeter Performance Testing Dashboard**
4. Configurar JMeter Backend Listener (ver sección Grafana Setup)

---

## 📊 Funcionalidades Detalladas

### 1. Upload y Análisis de JTL

#### Proceso:
1. **Subir archivo JTL** desde frontend
2. **Parsing automático** con Pandas (extrae métricas)
3. **Análisis con IA** (12 llamadas a Gemini):
   - 10 análisis individuales (tabla, errores, 8 gráficos)
   - 1 síntesis de conclusiones (4-5 puntos ejecutivos)
   - 1 generación de recomendaciones priorizadas
4. **Visualización** en dashboard React
5. **Exportación** a PDF o HTML

#### Tiempo de procesamiento:
- **Parsing JTL**: 2-5 segundos (10,000 muestras)
- **Análisis IA**: 30-40 segundos (12 llamadas a Gemini)
- **Total**: ~45 segundos

#### Métricas extraídas:
- Total Requests, Avg Response Time, Error Rate, Throughput
- Min/Max/Avg/Median/p90/p95/p99 por transacción
- Errores por código HTTP
- Throughput, Latency, Active Threads over time

### 2. Dashboard Interactivo

#### 4 Cards de Resumen:
- **Total Requests**: Número total de requests
- **Avg Response Time**: Tiempo promedio en ms
- **Error Rate**: Porcentaje de errores
- **Throughput**: Requests/segundo

#### Tabla de Estadísticas:
- Una fila por transacción (endpoint)
- Columnas: Label, Samples, Avg, Min, Max, p90, p95, p99, Error %, Throughput

#### 8 Gráficos de Performance:
1. **Response Times por Transacción** - Barras comparativas
2. **Response Time Over Time** - Líneas temporales
3. **Throughput Over Time** - Áreas temporales
4. **Latency Over Time** - Líneas temporales
5. **Error Rate Over Time** - Porcentaje en el tiempo
6. **Response Codes per Second** - Stacked bars
7. **Transactions per Second** - Líneas por transacción
8. **Active Threads Over Time** - Área de concurrencia

### 3. Análisis IA con Gemini 1.5 Pro

#### 10 Análisis Individuales:
Cada análisis incluye:
- **Hallazgos clave** - ¿Qué detectó la IA?
- **Métricas relevantes** - Datos concretos
- **Recomendaciones** - Acciones específicas

Análisis generados:
1. Tabla de estadísticas resumen
2. Análisis de errores
3-10. Análisis de cada uno de los 8 gráficos

#### Conclusiones Generales (✨ v1.2.0):
- **Síntesis inteligente** de los 10 análisis
- **4-5 puntos ejecutivos** máximo
- **Lenguaje claro** para stakeholders

#### Recomendaciones Priorizadas (✨ v1.2.0):
- **CRÍTICO**: Problemas graves (ej: error rate > 10%)
- **ALTO**: Optimizaciones importantes (ej: p99 > 2000ms)
- **MEDIO**: Mejoras recomendadas (ej: throughput bajo)

#### Edición Inline:
- **Todos los análisis son editables** directamente en UI
- Click en el texto → Editar → Guardar
- Se guarda en PostgreSQL

### 4. Monitoreo en Tiempo Real con Grafana ✨ **NUEVO v1.3.0**

#### Arquitectura:
```
┌──────────────┐
│   JMETER     │  Backend Listener envía métricas
│   (Local)    │  URL: http://localhost:8086/write?db=jmeter
└──────┬───────┘  Token: jmeter-token-2024-super-secret
       │
       ↓
┌──────────────┐
│  INFLUXDB    │  Almacena series temporales
│  (Docker)    │  Bucket: jmeter | Org: performance
│  Port: 8086  │  Retención: 30 días
└──────┬───────┘
       │
       ↓ Queries Flux
┌──────────────┐
│   GRAFANA    │  Visualiza dashboards
│  (Docker)    │  Auto-refresh: 5s
│  Port: 3000  │  9 paneles profesionales
└──────────────┘
```

#### 9 Paneles de Grafana:

1. **📊 Response Time Over Time**
   - Gráfica de líneas
   - Tiempo de respuesta promedio por transacción
   - Actualización en tiempo real

2. **👥 Active Threads**
   - Gráfica de área
   - Hilos activos (concurrencia)
   - Visualiza ramp-up

3. **❌ Error Rate**
   - Gauge (medidor)
   - Porcentaje de errores
   - Umbrales: verde < 1%, amarillo 1-5%, rojo > 5%

4. **🚀 Throughput**
   - Gauge
   - Requests por segundo
   - Calculado con derivative

5. **📈 Total Requests**
   - Stat (contador)
   - Suma total de requests
   - Color verde

6. **💥 Total Errors**
   - Stat (contador)
   - Suma total de errores
   - Color rojo

7. **📊 Response Time Percentiles (p90, p95, p99)**
   - Gráfica de líneas
   - 3 líneas (p90 amarillo, p95 naranja, p99 rojo)
   - Muestra distribución de tiempos

8. **🏷️ Requests by Transaction**
   - Pie chart
   - Distribución de requests por endpoint
   - Visualiza carga por transacción

9. **📋 Transaction Details**
   - Tabla
   - Todas las métricas por transacción
   - Columnas: transaction, count, errors, avg, min, max, p90, p95, p99
   - Sorteable y con colores

#### Configuración JMeter Backend Listener:

Para enviar métricas a InfluxDB durante ejecución de test:

1. **En JMeter**, agregar **Backend Listener** al Test Plan
2. **Backend Listener Implementation**: `org.apache.jmeter.visualizers.backend.influxdb.InfluxdbBackendListenerClient`
3. **Parámetros**:

| Parámetro | Valor |
|-----------|-------|
| influxdbMetricsSender | org.apache.jmeter.visualizers.backend.influxdb.HttpMetricsSender |
| influxdbUrl | `http://localhost:8086/write?db=jmeter` |
| application | PerformanceTest |
| measurement | jmeter |
| summaryOnly | false |
| samplersRegex | .* |
| percentiles | 90;95;99 |
| testTitle | Test Performance |
| **influxdbToken** | `jmeter-token-2024-super-secret` |

4. **Ejecutar test** → Ver métricas en Grafana en tiempo real

**Ver guía completa**: [GRAFANA_SETUP.md](./GRAFANA_SETUP.md)

### 5. Exportación de Reportes

#### PDF (desde Frontend):
- Click en botón **"Exportar PDF"**
- Captura TODO el dashboard (cards + tabla + gráficos + análisis IA)
- Genera PDF descargable
- Incluye branding profesional

#### HTML (desde API):
- Endpoint: `GET /api/v1/export/html/{execution_id}`
- Genera HTML standalone con Jinja2
- Incluye todos los datos + gráficos embebidos
- Puede abrirse sin conexión

---

## 📁 Estructura del Proyecto

```
jmeter-analyzer/
├── backend/                     # API FastAPI
│   ├── app/
│   │   ├── main.py             # Aplicación principal
│   │   ├── core/               # Configuración
│   │   │   ├── config.py       # Variables de entorno
│   │   │   └── security.py     # JWT, hashing
│   │   ├── db/                 # Base de datos
│   │   │   ├── models/
│   │   │   │   ├── test.py     # Modelo TestExecution (con ai_conclusions)
│   │   │   │   └── user.py     # Modelo User
│   │   │   └── session.py      # Async DB session
│   │   ├── api/                # Endpoints
│   │   │   └── v1/
│   │   │       ├── api.py      # Router principal
│   │   │       └── endpoints/
│   │   │           ├── auth.py         # Login
│   │   │           ├── upload.py       # Upload JTL + IA
│   │   │           ├── export_html.py  # Exportar HTML
│   │   │           └── export_pdf.py   # Exportar PDF
│   │   ├── schemas/            # Pydantic models
│   │   │   ├── test.py         # Schemas con ai_conclusions
│   │   │   └── auth.py         # Login/Token schemas
│   │   └── services/           # Lógica de negocio
│   │       ├── jtl/
│   │       │   └── jtl_parser.py      # Parseo JTL con Pandas
│   │       └── ai/
│   │           └── gemini.py          # Síntesis IA con Gemini
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/                   # React App
│   ├── src/
│   │   ├── App.tsx            # Componente principal
│   │   ├── main.tsx           # Entry point
│   │   ├── components/
│   │   │   ├── auth/
│   │   │   │   └── Login.tsx          # Componente login
│   │   │   ├── dashboard/
│   │   │   │   ├── Dashboard.tsx      # Dashboard principal (con conclusiones)
│   │   │   │   └── UploadJTL.tsx      # Upload de archivos
│   │   │   ├── charts/
│   │   │   │   ├── StatsTable.tsx     # Tabla de estadísticas
│   │   │   │   ├── ByLabelChart.tsx   # Gráficos por transacción
│   │   │   │   └── TimelineChart.tsx  # Gráficos temporales
│   │   │   └── common/
│   │   │       └── LoadingSpinner.tsx # Spinner de carga
│   │   ├── hooks/
│   │   │   └── usePDFExport.ts        # Hook para exportar PDF
│   │   ├── services/
│   │   │   └── api.ts                 # Cliente HTTP (axios)
│   │   └── types/
│   ├── Dockerfile
│   └── package.json
│
├── grafana/                    # Configuración Grafana ✨ NUEVO v1.3.0
│   ├── datasources/
│   │   └── influxdb.yml       # Datasource InfluxDB auto-provisionado
│   └── dashboards/
│       ├── dashboard.yml       # Provisioning config
│       └── jmeter-dashboard.json  # Dashboard con 9 paneles
│
├── docker-compose.yml          # Orquestación (5 servicios)
├── .env                        # Variables de entorno
├── .gitignore                  # Archivos ignorados por Git
├── README.md                   # Este archivo
├── GRAFANA_SETUP.md           # Guía de Grafana ✨ NUEVO v1.3.0
├── CHANGELOG.md               # Historial de versiones
├── GUIA_INICIO.md             # Guía paso a paso
├── RESUMEN_EJECUTIVO.md       # Resumen del proyecto
└── TROUBLESHOOTING.md         # Solución de problemas
```

---

## 🔧 Comandos Útiles

### Docker Compose

```bash
# Iniciar servicios
docker-compose up -d

# Detener servicios
docker-compose down

# Ver logs de todos los servicios
docker-compose logs -f

# Ver logs de un servicio específico
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f grafana
docker-compose logs -f influxdb

# Reconstruir imágenes (después de cambios en código)
docker-compose up --build -d

# Ver estado de servicios
docker-compose ps

# Reiniciar servicios
docker-compose restart

# Reiniciar servicio específico
docker-compose restart backend
docker-compose restart grafana

# Limpiar TODO (¡CUIDADO! Borra datos)
docker-compose down -v
```

### Acceso a Contenedores

```bash
# Shell del backend
docker-compose exec backend /bin/bash

# Shell de PostgreSQL
docker-compose exec postgres psql -U jmeter_user -d jmeter_analyzer_db

# Ver columnas de tabla test_executions
docker-compose exec postgres psql -U jmeter_user -d jmeter_analyzer_db -c "\d test_executions"

# Shell de InfluxDB
docker-compose exec influxdb /bin/bash

# Query manual a InfluxDB
docker exec -it jmeter_influxdb influx query \
  'from(bucket: "jmeter") |> range(start: -5m) |> limit(n: 10)' \
  --org performance \
  --token jmeter-token-2024-super-secret
```

### Base de Datos PostgreSQL

```bash
# Ver todas las ejecuciones
docker-compose exec postgres psql -U jmeter_user -d jmeter_analyzer_db -c "SELECT id, file_name, created_at FROM test_executions;"

# Ver análisis AI de una ejecución
docker-compose exec postgres psql -U jmeter_user -d jmeter_analyzer_db -c "SELECT ai_summary, ai_conclusions FROM test_executions WHERE id = 1;"

# Agregar columna ai_conclusions (si no existe)
docker-compose exec postgres psql -U jmeter_user -d jmeter_analyzer_db -c "ALTER TABLE test_executions ADD COLUMN IF NOT EXISTS ai_conclusions TEXT;"
```

### InfluxDB (Grafana)

```bash
# Ver datos en bucket jmeter
docker exec -it jmeter_influxdb influx query \
  'from(bucket: "jmeter") |> range(start: -5m)' \
  --org performance \
  --token jmeter-token-2024-super-secret

# Contar registros
docker exec -it jmeter_influxdb influx query \
  'from(bucket: "jmeter") |> range(start: -1h) |> count()' \
  --org performance \
  --token jmeter-token-2024-super-secret

# Listar transacciones únicas
docker exec -it jmeter_influxdb influx query \
  'from(bucket: "jmeter") |> range(start: -5m) |> keep(columns: ["transaction"]) |> distinct(column: "transaction")' \
  --org performance \
  --token jmeter-token-2024-super-secret

# Borrar todos los datos (útil para testing)
docker exec -it jmeter_influxdb influx delete \
  --bucket jmeter \
  --start 1970-01-01T00:00:00Z \
  --stop $(date -u +"%Y-%m-%dT%H:%M:%SZ") \
  --org performance \
  --token jmeter-token-2024-super-secret
```

---

## 🛠 Troubleshooting

### Problema: Puertos ocupados

```bash
# Ver qué proceso usa el puerto (Windows)
netstat -ano | findstr :8001
netstat -ano | findstr :5173
netstat -ano | findstr :3000
netstat -ano | findstr :8086

# Ver qué proceso usa el puerto (Linux/Mac)
lsof -i :8001
lsof -i :5173
lsof -i :3000
lsof -i :8086

# Solución: Cambiar puerto en docker-compose.yml
# O matar el proceso que ocupa el puerto
```

### Problema: Docker no inicia

```bash
# Verificar Docker Desktop
# Windows/Mac: Abrir Docker Desktop y asegurar que esté corriendo

# Verificar recursos asignados
# Docker Desktop > Settings > Resources
# Asignar mínimo 4GB RAM, 2 CPUs
```

### Problema: Error "ai_conclusions is an invalid keyword"

```bash
# Ejecutar migración SQL
docker-compose exec postgres psql -U jmeter_user -d jmeter_analyzer_db \
  -c "ALTER TABLE test_executions ADD COLUMN IF NOT EXISTS ai_conclusions TEXT;"

# Reiniciar backend
docker-compose restart backend
```

### Problema: Grafana no muestra datos

```bash
# 1. Verificar que InfluxDB esté corriendo
docker-compose ps influxdb

# 2. Verificar que JMeter Backend Listener esté configurado
#    Ver GRAFANA_SETUP.md

# 3. Verificar que hay datos en InfluxDB
docker exec -it jmeter_influxdb influx query \
  'from(bucket: "jmeter") |> range(start: -5m) |> limit(n: 5)' \
  --org performance \
  --token jmeter-token-2024-super-secret

# 4. Verificar datasource en Grafana
# http://localhost:3000 > Configuration > Data Sources > InfluxDB-JMeter
# Click "Save & Test" → Debe decir "Data source is working"

# 5. Reiniciar Grafana
docker-compose restart grafana
```

### Problema: Frontend no carga

```bash
# Ver logs del frontend
docker-compose logs -f frontend

# Reconstruir contenedor
docker-compose up --build frontend -d

# Verificar que backend esté corriendo
curl http://localhost:8001/docs
```

### Problema: Error 401 en JMeter Backend Listener

```bash
# Verificar que el token esté configurado correctamente
# En JMeter Backend Listener, agregar parámetro:
# Name: influxdbToken
# Value: jmeter-token-2024-super-secret

# Verificar que el token coincida con .env
cat .env | grep INFLUXDB_TOKEN
```

---

## 📚 Documentación Adicional

- **[GRAFANA_SETUP.md](./GRAFANA_SETUP.md)** - Guía completa de Grafana + InfluxDB ✨ NUEVO
- **[CHANGELOG.md](./CHANGELOG.md)** - Historial de versiones
- **[GUIA_INICIO.md](./GUIA_INICIO.md)** - Guía paso a paso detallada
- **[TROUBLESHOOTING.md](./TROUBLESHOOTING.md)** - Solución de problemas comunes
- **API Docs (Swagger)**: http://localhost:8001/docs (una vez iniciado)

---

## 📜 Changelog

### v1.3.0 - Monitoreo en Tiempo Real (Diciembre 2024) ✨
- ✅ Agregado Grafana 10.2.3 + InfluxDB 2.7
- ✅ Dashboard con 9 paneles profesionales
- ✅ Integración JMeter Backend Listener → InfluxDB
- ✅ Métricas en tiempo real (auto-refresh 5s)
- ✅ Retención de datos 30 días
- ✅ Documentación completa (GRAFANA_SETUP.md)

### v1.2.0 - Síntesis Inteligente (Diciembre 2024)
- ✅ Agregado campo ai_conclusions en BD
- ✅ Implementado generate_conclusions() - síntesis de 10 análisis
- ✅ Implementado generate_recommendations() - priorización CRÍTICO/ALTO/MEDIO
- ✅ Corregido modelo Gemini a gemini-1.5-pro-latest
- ✅ Actualizado endpoint /analysis para incluir conclusiones
- ✅ Schemas Pydantic actualizados

### v1.1.0 - Análisis Completo de Gráficos (Noviembre 2024)
- ✅ Agregado análisis IA para 8 gráficos individuales
- ✅ Exportación PDF desde frontend con html2canvas
- ✅ Edición inline de análisis IA
- ✅ Branding SQA personalizado

### v1.0.0 - Release Inicial (Octubre 2024)
- ✅ Parsing de JTL con Pandas
- ✅ Dashboard con 8 gráficos interactivos (Recharts)
- ✅ Análisis IA básico con Gemini
- ✅ Exportación HTML con Jinja2
- ✅ Login con JWT

---

## 🔐 Seguridad

### Credenciales Predeterminadas

**IMPORTANTE**: Cambiar todas las credenciales en producción.

| Servicio | Usuario | Contraseña | Variable en .env |
|----------|---------|------------|------------------|
| Frontend | admin@jmeter.com | admin123 | - (hardcoded) |
| PostgreSQL | jmeter_user | jmeter_secure_2024 | DATABASE_URL |
| Grafana | admin | admin | - (cambiar en primer login) |
| InfluxDB | admin | admin123 | INFLUXDB_ADMIN_PASSWORD |

### Recomendaciones:
1. Cambiar `GEMINI_API_KEY` - Nunca commitear al repo
2. Cambiar `DATABASE_URL` password
3. Cambiar `SECRET_KEY` para JWT
4. Cambiar `INFLUXDB_TOKEN`
5. Habilitar HTTPS en producción
6. Usar variables de entorno seguras (Docker Secrets, HashiCorp Vault)

---

## 🆘 Ayuda Rápida

Si algo no funciona:

1. ✅ **Verificar Docker**: `docker ps`
2. ✅ **Ver logs**: `docker-compose logs -f`
3. ✅ **Reiniciar todo**: `docker-compose restart`
4. ✅ **Limpiar y reiniciar**: `docker-compose down -v && docker-compose up -d`
5. ✅ **Leer troubleshooting**: [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)

---

## 🔗 Recursos Útiles

- **FastAPI**: https://fastapi.tiangolo.com/
- **React**: https://react.dev/
- **Gemini API**: https://ai.google.dev/
- **Recharts**: https://recharts.org/
- **Grafana**: https://grafana.com/docs/
- **InfluxDB**: https://docs.influxdata.com/
- **JMeter**: https://jmeter.apache.org/

---

## 📄 Licencia

Propietario - Todos los derechos reservados

---

## 🤝 Contribuciones

Para contribuir al proyecto:

1. **Crear rama feature**: `git checkout -b feature/nueva-funcionalidad`
2. **Hacer cambios y commit**: `git commit -m "feat: descripción"`
3. **Push**: `git push origin feature/nueva-funcionalidad`
4. **Crear Pull Request** en GitHub

### Convención de commits:
- `feat:` - Nueva funcionalidad
- `fix:` - Corrección de bug
- `docs:` - Cambios en documentación
- `refactor:` - Refactorización de código
- `test:` - Agregado de tests
- `chore:` - Tareas de mantenimiento

---

## 👨‍💻 Autor

**Fredy** - COE Leader & Performance Testing Specialist

---

## ⭐ Agradecimientos

- Anthropic Claude - Asistencia en desarrollo
- Google Gemini - IA para análisis
- Comunidad Open Source

---

**Versión**: 1.3.0  
**Última actualización**: Diciembre 2024  
**Configuración optimizada**: Backend :8001 | Frontend :5173 | Grafana :3000 | InfluxDB :8086

🚀 **¡Gracias por usar JMeter Analyzer Pro!**
