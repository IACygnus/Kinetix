# 🚀 JMeter Analyzer Pro

> Sistema profesional de análisis y gestión de reportes JMeter con IA integrada (Gemini)

---

## ⚡ CONFIGURACIÓN RÁPIDA (Para Presentación)

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
2. Buscar la línea: `GEMINI_API_KEY=AIzaSyBzSNFbAf9D3...VM_M`
3. Reemplazar con tu API Key completa de Google AI Studio

### Paso 4: Levantar el Proyecto
```bash
# Desde la terminal de VS Code (Ctrl+` o Cmd+`)
docker-compose up -d
```

### Paso 5: Acceder a la Aplicación
- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8001
- **Documentación API:** http://localhost:8001/docs

---

## 🎯 Características

- 🔐 **Autenticación JWT** (Fase 2 - próxima)
- 📊 **Dashboard interactivo** con métricas en tiempo real
- 🤖 **Análisis con IA** usando Gemini 1.5 Pro
- 📈 **Visualización avanzada** de resultados JTL
- 🏗️ **Gestión de infraestructura**
- 📜 **Historial y comparativas**
- 🚀 **Arquitectura escalable**

---

## 🛠️ Stack Tecnológico

### Backend
- **FastAPI 0.104+** - Framework web moderno
- **PostgreSQL 15** - Base de datos
- **SQLAlchemy** - ORM async
- **Pandas** - Procesamiento de datos JTL
- **Google Generative AI** - Integración con Gemini

### Frontend
- **React 18** con TypeScript
- **Vite** - Build tool ultrarrápido
- **Tailwind CSS** - Diseño moderno
- **React Query** - Estado async
- **Recharts** - Gráficos

### DevOps
- **Docker + Docker Compose**
- **PostgreSQL 15**

---

## 📋 Requisitos

- **Docker Desktop** instalado y corriendo
- **Visual Studio Code** (recomendado)
- **Puertos libres:** 5173 (frontend), 8001 (backend), 5432 (PostgreSQL)
- **RAM:** Mínimo 4GB libres

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

## 📁 Estructura del Proyecto

```
jmeter-analyzer/
├── backend/                 # API FastAPI
│   ├── app/
│   │   ├── main.py         # Aplicación principal ✅
│   │   ├── core/           # Configuración ✅
│   │   ├── db/             # Base de datos ✅
│   │   ├── api/            # Endpoints
│   │   ├── schemas/        # Pydantic models
│   │   └── services/       # Lógica de negocio
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/               # React App
│   ├── src/
│   │   ├── App.tsx        # Componente principal ✅
│   │   ├── main.tsx       # Entry point ✅
│   │   └── ...
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml     # Orquestación ✅
├── .env                   # Variables de entorno ✅
└── README.md             # Este archivo
```

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

# Limpiar todo (¡CUIDADO! Borra datos)
docker-compose down -v
```

### Acceso a Contenedores
```bash
# Shell del backend
docker-compose exec backend /bin/bash

# Shell de PostgreSQL
docker-compose exec postgres psql -U jmeter_user -d jmeter_analyzer_db

# Shell del frontend
docker-compose exec frontend /bin/sh
```

---

## 🐛 Troubleshooting

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

### Problema: Error de conexión a base de datos
```bash
# Ver logs de PostgreSQL
docker-compose logs postgres

# Reiniciar solo PostgreSQL
docker-compose restart postgres
```

### Problema: Cambios en código no se reflejan
```bash
# Backend: Reiniciar contenedor
docker-compose restart backend

# Frontend: Refrescar navegador (Ctrl+F5)
```

---

## 📚 Documentación

### Endpoints de la API

Una vez iniciado, visita: http://localhost:8001/docs

Verás la documentación interactiva (Swagger) con todos los endpoints disponibles.

---

## 🔜 Roadmap

- [x] **Fase 1:** Setup y configuración ✅
- [ ] **Fase 2:** Autenticación JWT
- [ ] **Fase 3:** Parser de JTL y procesamiento
- [ ] **Fase 4:** Dashboard con visualizaciones
- [ ] **Fase 5:** Gestión de infraestructura
- [ ] **Fase 6:** Integración con Gemini AI
- [ ] **Fase 7:** Historial y comparativas
- [ ] **Fase 8:** Testing completo
- [ ] **Fase 9:** Despliegue en servidor

---

## 🆘 Ayuda Rápida

### Si algo no funciona:

1. **Verificar Docker:** `docker ps`
2. **Ver logs:** `docker-compose logs -f`
3. **Reiniciar todo:** `docker-compose restart`
4. **Limpiar y reiniciar:** `docker-compose down -v && docker-compose up -d`

### Contactos
- Documentación de FastAPI: https://fastapi.tiangolo.com/
- Documentación de React: https://react.dev/
- Gemini API: https://ai.google.dev/

---

## 📄 Licencia

Propietario - Todos los derechos reservados

---

**Versión:** 1.0.0 (Fase 1)  
**Última actualización:** Diciembre 2024  
**Configuración:** Optimizada para puerto 8001 (backend) y 5173 (frontend)
