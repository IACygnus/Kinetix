# 🚀 JMeter Analyzer Pro

> Sistema profesional de análisis y gestión de reportes JMeter con IA integrada (Gemini)

**Versión:** 1.2.0 | **Última actualización:** Diciembre 2024

---

## ⚡ CONFIGURACIÓN RÁPIDA

### Paso 1: Descargar el Proyecto
Descarga la carpeta `jmeter-analyzer` completa

### Paso 2: Abrir en Visual Studio Code
```bash
# Opción A: Desde la terminal
code jmeter-analyzer

# Opción B: Desde VS Code
File > Open Folder > Seleccionar carpeta jmeter-analyzer
```

### Paso 3: Configurar API Key de Gemini
1. Abrir archivo `.env` en VS Code
2. Buscar la línea: `GEMINI_API_KEY=`
3. Pegar tu API Key completa de Google AI Studio
   - Obtener en: https://makersuite.google.com/app/apikey

### Paso 4: Levantar el Proyecto
```bash
# Desde la terminal de VS Code (Ctrl+` o Cmd+`)
docker-compose up --build -d
```

### Paso 5: Acceder a la Aplicación
- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8001
- **Documentación API:** http://localhost:8001/docs

---

## 🎯 Características

- 📊 **Dashboard interactivo** con métricas en tiempo real
- 🤖 **Análisis con IA** usando Gemini 1.5 Pro (síntesis inteligente)
- 📈 **Visualización avanzada** con 8 gráficos de performance
- 💡 **Conclusiones ejecutivas** sintetizando todos los análisis
- 🎯 **Recomendaciones priorizadas** (CRÍTICO/ALTO/MEDIO)
- ✏️ **Edición inline** de todos los análisis
- 📄 **Exportación** a PDF y HTML interactivo
- 🚀 **Arquitectura escalable** con Docker

---

## 🛠️ Stack Tecnológico

### Backend
- **FastAPI 0.104+** - Framework web moderno
- **PostgreSQL 15** - Base de datos
- **SQLAlchemy** - ORM async
- **Pandas** - Procesamiento de datos JTL
- **Google Generative AI** - Integración con Gemini 1.5 Pro

### Frontend
- **React 18** con TypeScript
- **Vite** - Build tool ultrarápido
- **Tailwind CSS** - Diseño moderno
- **Recharts** - Gráficos interactivos
- **html2canvas + jsPDF** - Exportación PDF

### DevOps
- **Docker + Docker Compose**
- **PostgreSQL 15**
- **Volúmenes persistentes**

---

## 📋 Requisitos

- **Docker Desktop** instalado y corriendo
- **Visual Studio Code** (recomendado)
- **Puertos libres:** 5173 (frontend), 8001 (backend), 5432 (PostgreSQL)
- **RAM:** Mínimo 4GB libres
- **API Key de Gemini** (gratuita en https://makersuite.google.com)

---

## 🚀 Inicio Rápido

### 1. Verificar Docker
```bash
# Verificar que Docker esté corriendo
docker --version
docker-compose --version
```

### 2. Configurar Variables
```bash
# Editar .env con tu API Key de Gemini
# Buscar: GEMINI_API_KEY=
# Pegar tu API Key completa
```

### 3. Levantar Servicios
```bash
# Primera vez: construir imágenes
docker-compose up --build -d

# Siguientes veces: solo levantar
docker-compose up -d
```

### 4. Ver Logs (Opcional)
```bash
# Ver logs de todos los servicios
docker-compose logs -f

# Solo backend
docker-compose logs -f backend

# Solo frontend
docker-compose logs -f frontend
```

### 5. Verificar Estado
```bash
docker-compose ps
```

Deberías ver 3 servicios corriendo:
- ✅ jmeter_postgres
- ✅ jmeter_backend
- ✅ jmeter_frontend

---

## 📊 Funcionalidades Principales

### 1. Upload y Parsing de JTL
- Sube archivos JTL/CSV de JMeter
- Extrae automáticamente métricas: tiempos, errores, throughput, percentiles
- Procesa 10,000+ muestras en segundos

### 2. Dashboard Interactivo
- **4 Cards de Resumen**: Total Requests, Avg Time, Error Rate, Throughput
- **Tabla Completa**: Estadísticas por transacción
- **8 Gráficos de Performance**:
  - Response Times por Transacción
  - Response Time Over Time
  - Throughput Over Time
  - Latency Over Time
  - Error Rate Over Time
  - Response Codes per Second
  - Transactions per Second
  - Active Threads Over Time

### 3. Análisis IA con Gemini (✨ v1.2.0)
- **10 Análisis Individuales**: Tabla resumen + errores + 8 gráficos
- **Conclusiones Generales** (NUEVO): Sintetizan TODOS los análisis en 4-5 puntos ejecutivos
- **Recomendaciones Priorizadas** (NUEVO): CRÍTICO/ALTO/MEDIO basadas en patrones detectados
- **Edición Inline**: Todos los análisis son editables y guardables

### 4. Exportación
- **PDF Completo**: Captura TODO el dashboard con gráficas
- **HTML Interactivo**: Standalone con Jinja2

---

## 📁 Estructura del Proyecto

```
jmeter-analyzer/
├── backend/                 # API FastAPI
│   ├── app/
│   │   ├── main.py         # Aplicación principal
│   │   ├── core/           # Configuración
│   │   ├── db/             # Base de datos
│   │   │   └── models/
│   │   │       └── test.py # Modelo con ai_conclusions
│   │   ├── api/            # Endpoints
│   │   │   └── v1/
│   │   │       └── endpoints/
│   │   │           └── upload.py  # Upload + síntesis IA
│   │   ├── schemas/        # Pydantic models
│   │   │   └── test.py     # Schemas con ai_conclusions
│   │   └── services/       # Lógica de negocio
│   │       ├── jtl/
│   │       │   └── jtl_parser.py  # Parser JTL
│   │       └── ai/
│   │           └── gemini.py      # Síntesis inteligente
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/               # React App
│   ├── src/
│   │   ├── App.tsx        # Componente principal
│   │   ├── main.tsx       # Entry point
│   │   └── components/
│   │       └── Dashboard/
│   │           └── Dashboard.tsx  # Dashboard con conclusiones
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml     # Orquestación
├── .env                   # Variables de entorno
├── README.md             # Este archivo
├── GUIA_INICIO.md        # Guía paso a paso
├── RESUMEN_EJECUTIVO.md  # Resumen del proyecto
└── TROUBLESHOOTING.md    # Solución de problemas
```

---

## 🧠 Arquitectura de Análisis IA

### Flujo de Análisis (12 llamadas a Gemini):

**Fase 1: Análisis Individuales (10 llamadas)**
1. Análisis tabla resumen
2. Análisis errores
3-10. Análisis de 8 gráficos individuales

**Fase 2: Síntesis Inteligente (2 llamadas) ✨ v1.2.0**
11. **Conclusiones**: Sintetizan los 10 análisis en 4-5 puntos ejecutivos
12. **Recomendaciones**: Priorizadas (CRÍTICO/ALTO/MEDIO) basadas en todos los análisis

**Tiempo total**: ~30-40 segundos por JTL

---

## 🔧 Comandos Útiles

### Docker Compose
```bash
# Iniciar servicios
docker-compose up -d

# Detener servicios
docker-compose down

# Ver logs
docker-compose logs -f

# Reconstruir imágenes
docker-compose up --build -d

# Ver estado
docker-compose ps

# Reiniciar servicios
docker-compose restart

# Limpiar todo (¡CUIDADO! Borra datos)
docker-compose down -v
```

### Acceso a Contenedores
```bash
# Shell del backend
docker-compose exec backend /bin/bash

# Shell de PostgreSQL
docker-compose exec postgres psql -U jmeter_user -d jmeter_analyzer_db

# Ver columnas de la tabla
docker-compose exec postgres psql -U jmeter_user -d jmeter_analyzer_db -c "\d test_executions"
```

### Base de Datos
```bash
# Agregar columna ai_conclusions (si no existe)
docker-compose exec postgres psql -U jmeter_user -d jmeter_analyzer_db -c "ALTER TABLE test_executions ADD COLUMN IF NOT EXISTS ai_conclusions TEXT;"

# Verificar que se agregó
docker-compose exec postgres psql -U jmeter_user -d jmeter_analyzer_db -c "SELECT column_name FROM information_schema.columns WHERE table_name='test_executions' AND column_name='ai_conclusions';"
```

---

## 🛠 Troubleshooting

### Problema: Puertos ocupados
```bash
# Ver qué proceso usa el puerto
# Windows
netstat -ano | findstr :8001

# Linux/Mac
lsof -i :8001

# Solución: Cambiar puerto en .env y docker-compose.yml
```

### Problema: Docker no inicia
```bash
# Verificar Docker Desktop
# Windows/Mac: Abrir Docker Desktop y asegurar que esté corriendo

# Verificar recursos
# Docker Desktop > Settings > Resources
# Asignar mínimo 4GB RAM
```

### Problema: Error "ai_conclusions is an invalid keyword"
```bash
# Ejecutar migración SQL
docker-compose exec postgres psql -U jmeter_user -d jmeter_analyzer_db -c "ALTER TABLE test_executions ADD COLUMN IF NOT EXISTS ai_conclusions TEXT;"

# Reiniciar backend
docker-compose restart backend
```

### Problema: Error de modelo Gemini
```
ERROR: 404 models/gemini-1.5-pro is not found
```
**Solución**: El código usa `gemini-1.5-pro-latest` (ya corregido en v1.2.0)

---

## 📚 Documentación

### Endpoints de la API

Una vez iniciado, visita: http://localhost:8001/docs

Verás la documentación interactiva (Swagger) con todos los endpoints disponibles:
- `POST /api/v1/upload` - Subir JTL con análisis IA
- `GET /api/v1/executions/{id}` - Obtener ejecución
- `GET /api/v1/executions/{id}/charts` - Obtener datos de gráficos
- `PUT /api/v1/executions/{id}/analysis` - Actualizar análisis
- `GET /api/v1/export/html/{id}` - Exportar HTML

---

## 📜 Changelog

### v1.2.0 - Síntesis Inteligente (Diciembre 2024) ✨
- ✅ Agregado campo `ai_conclusions` en BD
- ✅ Implementado `generate_conclusions()` con síntesis de 10 análisis
- ✅ Implementado `generate_recommendations()` con priorización
- ✅ Corregido modelo Gemini a `gemini-1.5-pro-latest`
- ✅ Actualizado endpoint `/analysis` para incluir conclusiones
- ✅ Schemas Pydantic actualizados

### v1.1.0 - Análisis Completo de Gráficos (Noviembre 2024)
- ✅ Agregado análisis IA para 8 gráficos individuales
- ✅ Exportación PDF desde frontend
- ✅ Edición inline de análisis
- ✅ Branding SQA personalizado

### v1.0.0 - Release Inicial (Octubre 2024)
- ✅ Parsing de JTL con Pandas
- ✅ Dashboard con 8 gráficos interactivos
- ✅ Análisis IA básico con Gemini
- ✅ Exportación HTML

---

## 🆘 Ayuda Rápida

### Si algo no funciona:

1. **Verificar Docker:** `docker ps`
2. **Ver logs:** `docker-compose logs -f`
3. **Reiniciar todo:** `docker-compose restart`
4. **Limpiar y reiniciar:** `docker-compose down -v && docker-compose up -d`

### Recursos Útiles
- Documentación de FastAPI: https://fastapi.tiangolo.com/
- Documentación de React: https://react.dev/
- Gemini API: https://ai.google.dev/
- Recharts Docs: https://recharts.org/

---

## 📄 Licencia

Propietario - Todos los derechos reservados

---

## 🤝 Contribuciones

Para contribuir al proyecto:

1. Crear rama feature: `git checkout -b feature/nueva-funcionalidad`
2. Hacer cambios y commit: `git commit -m "feat: descripción"`
3. Push: `git push origin feature/nueva-funcionalidad`
4. Crear Pull Request

---

**Versión:** 1.2.0  
**Última actualización:** Diciembre 2024  
**Configuración:** Optimizada para puerto 8001 (backend) y 5173 (frontend)

¡Gracias por usar JMeter Analyzer Pro! 🚀
