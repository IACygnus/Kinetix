# JMeter Analyzer Pro

Sistema profesional de analisis y gestion de reportes JMeter con **IA integrada** (Gemini) y **monitoreo en tiempo real** (Grafana + InfluxDB).

**Version: 2.0.0** | Febrero 2026

---

## Configuracion Rapida

### 1. Clonar y configurar

```bash
git clone <url-del-repositorio>
cd jmeter-analyzer
cp .env.example .env
```

Editar `.env` y configurar las variables requeridas (ver `.env.example` para la lista completa):

```env
GEMINI_API_KEY=<tu-api-key>
SECRET_KEY=<tu-clave-secreta>
ADMIN_DEFAULT_PASSWORD=<password-del-admin>
POSTGRES_PASSWORD=<password-de-bd>
```

### 2. Levantar servicios

```bash
docker-compose up --build -d
```

### 3. Acceder

| Servicio | URL | Notas |
|----------|-----|-------|
| Aplicacion (React) | http://localhost:5173 | Login con las credenciales del admin |
| API Docs (Swagger) | http://localhost:8001/docs | Documentacion interactiva |
| Grafana | http://localhost:3000 | Dashboards de monitoreo en tiempo real |
| InfluxDB | http://localhost:8086 | Series temporales |

> Las credenciales por defecto se configuran en `.env`. Ver `.env.example`.

---

## Arquitectura v2.0

```
                    +-------------------+
                    |   React 18 + TS   |  :5173
                    |   Tailwind + Vite  |
                    +---------+---------+
                              |
                              v
                    +---------+---------+
                    |  FastAPI Backend   |  :8001
                    |  JWT + Gemini AI   |
                    +---------+---------+
                              |
              +---------------+---------------+
              |                               |
    +---------+---------+           +---------+---------+
    |   PostgreSQL 15   |           |   InfluxDB 2.7    |  :8086
    |  (datos + usuarios)|          |  (series temporal) |
    +-------------------+           +---------+---------+
                                              |
                                    +---------+---------+
                                    |  Grafana 10.2.3   |  :3000
                                    |  (dashboards)     |
                                    +-------------------+
```

**5 contenedores Docker**: postgres, backend, frontend, influxdb, grafana.

---

## Funcionalidades

### Autenticacion y Usuarios (Phase 1)
- JWT con roles: admin, tester, viewer
- CRUD de usuarios, perfil, cambio de contrasena
- Dashboard Home con estadisticas globales
- Historial de ejecuciones con busqueda

### Multi-JTL Upload y Analisis (Phase 2)
- Upload de 1-5 archivos JTL por ejecucion
- Validacion de compatibilidad entre JTLs
- Separacion automatica de redirecciones (patron `TransactionName-N`)
- Tipos de prueba: load, stress, endurance, spike, scalability
- Criterios de aceptacion configurables

### Analisis IA con Gemini (Phases 2-3)
- 12 analisis individuales + 2 de sintesis (conclusiones, recomendaciones)
- Priorizacion: CRITICO / ALTO / MEDIO
- Cada seccion almacenada en columna independiente
- Edicion inline de todos los analisis

### Graficos y Exportacion (Phase 3)
- 8 graficos interactivos (Chart.js): Response Times, Throughput, Latency, Error Rate, Codes/s, TPS, Active Threads, Pie de Codigos
- Exportacion HTML standalone con graficos embebidos
- Exportacion PDF profesional (WeasyPrint + matplotlib): portada SQA, KPIs, tablas, graficos, analisis IA completo

### Monitoreo Real-time (Phase 4)
- Grafana integrado via iframe con time ranges y auto-refresh
- Panel de configuracion de monitoreo (admin)
- Token InfluxDB encriptado con Fernet
- Health checks de conectividad

---

## Stack Tecnologico

| Capa | Tecnologia |
|------|-----------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Chart.js |
| Backend | FastAPI 0.104, SQLAlchemy Async, Pandas, WeasyPrint, matplotlib |
| Base de datos | PostgreSQL 15 |
| IA | Google Gemini 1.5 Pro |
| Monitoreo | Grafana 10.2.3 + InfluxDB 2.7 |
| Infraestructura | Docker + Docker Compose |

---

## Variables de Entorno

Ver `.env.example` para la lista completa. Las mas importantes:

| Variable | Descripcion | Requerida |
|----------|-------------|-----------|
| `GEMINI_API_KEY` | API Key de Google Gemini | Si |
| `SECRET_KEY` | Clave secreta para JWT | Si (produccion) |
| `ADMIN_DEFAULT_PASSWORD` | Password del admin seed | Si |
| `POSTGRES_PASSWORD` | Password de PostgreSQL | Si |
| `FERNET_KEY` | Clave para encriptacion de tokens | Recomendada |
| `CORS_ORIGINS` | Origenes permitidos (produccion) | Si (produccion) |
| `INFLUXDB_TOKEN` | Token de InfluxDB | Si (si usa Grafana) |

---

## API Endpoints

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| POST | `/api/v1/auth/login` | Autenticacion |
| GET | `/api/v1/auth/me` | Usuario actual |
| GET | `/api/v1/dashboard/stats` | Estadisticas globales |
| POST | `/api/v1/validate-jtl` | Validar compatibilidad de JTLs |
| POST | `/api/v1/upload` | Subir JTL(s) y analizar |
| GET | `/api/v1/executions` | Listar ejecuciones |
| GET | `/api/v1/executions/{id}` | Detalle de ejecucion |
| GET | `/api/v1/executions/{id}/charts` | Datos de graficos |
| PUT | `/api/v1/executions/{id}/analysis` | Editar analisis IA |
| DELETE | `/api/v1/executions/{id}` | Eliminar ejecucion |
| GET | `/api/v1/executions/{id}/export/html` | Exportar HTML |
| GET | `/api/v1/executions/{id}/export/pdf` | Exportar PDF |
| GET/POST | `/api/v1/users` | CRUD usuarios |
| GET/PUT | `/api/v1/profile` | Perfil del usuario |
| GET/PUT | `/api/v1/monitoring/config` | Config de monitoreo |
| GET | `/api/v1/monitoring/health` | Health check monitoreo |

Documentacion interactiva completa en: http://localhost:8001/docs

---

## Despliegue en Produccion

```bash
# Usar el override de produccion
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

El override de produccion:
- Desactiva hot-reload y source mounts
- Usa `ENVIRONMENT=production` (CORS restringido)
- `restart: always` en todos los servicios
- Cierra puertos internos (postgres, influxdb)

> **Importante**: En produccion, configurar TODAS las variables en `.env`. No se usan defaults.

---

## Comandos Utiles

```bash
# Ver estado de servicios
docker-compose ps

# Ver logs
docker-compose logs -f backend

# Reiniciar un servicio
docker-compose restart backend

# Reconstruir tras cambios
docker-compose up --build -d

# Detener todo
docker-compose down

# Detener y borrar volumenes (CUIDADO: borra datos)
docker-compose down -v
```

---

## Estructura del Proyecto

```
jmeter-analyzer/
  backend/
    app/
      main.py                    # App principal, startup, migrations
      core/config.py             # Variables de entorno
      core/security.py           # JWT, bcrypt, roles
      api/v1/api.py              # Router centralizado
      api/v1/endpoints/          # auth, upload, export_html, export_pdf,
                                 # dashboard, users, profile, monitoring
      db/models/                 # User, TestExecution, MonitoringConfig
      schemas/                   # Pydantic models
      services/jtl/jtl_parser.py # Parser JTL con Pandas
      services/ai/gemini.py      # Analisis IA con Gemini
      config/chart_config.py     # Colores de graficos
    Dockerfile
    requirements.txt
  frontend/
    src/
      App.tsx                    # Rutas y layout
      components/                # auth, dashboard, layout, monitoring,
                                 # performance, profile, users, common
      context/AuthContext.tsx     # Estado de autenticacion
      services/api.ts            # Cliente HTTP (axios)
      types/index.ts             # Tipos TypeScript
      config/chartConfig.ts      # Colores de graficos
    Dockerfile
  grafana/
    datasources/influxdb.yml     # Datasource auto-provisionado
    dashboards/                  # Dashboard JSON + provisioning
  docker-compose.yml             # Dev (5 servicios)
  docker-compose.prod.yml        # Override de produccion
  .env.example                   # Template de variables
  CHANGELOG.md                   # Historial de cambios
  INICIO_RAPIDO.md               # Guia rapida (espanol)
```

---

## Seguridad

- JWT tokens con expiracion configurable
- Passwords hasheados con bcrypt
- Token InfluxDB encriptado con Fernet
- CORS restringido en produccion
- Todas las credenciales configurables via `.env`
- `.env` excluido de git via `.gitignore`

**Recomendaciones para produccion:**
1. Generar `SECRET_KEY` aleatorio: `python -c "import secrets; print(secrets.token_urlsafe(64))"`
2. Generar `FERNET_KEY`: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
3. Cambiar TODOS los passwords por defecto
4. Configurar `CORS_ORIGINS` con las URLs exactas del frontend
5. Habilitar HTTPS con reverse proxy (nginx/traefik)
6. Considerar rate limiting en el reverse proxy

---

## Documentacion Adicional

- [CHANGELOG.md](./CHANGELOG.md) — Historial de versiones
- [INICIO_RAPIDO.md](./INICIO_RAPIDO.md) — Guia de 5 minutos
- [GRAFANA_SETUP.md](./GRAFANA_SETUP.md) — Configuracion de Grafana + InfluxDB
- [API Docs](http://localhost:8001/docs) — Swagger interactivo (requiere servicios activos)

---

**Autor**: Fredy Bonilla — COE Leader & Performance Testing Specialist

**Version**: 2.0.0 | Backend :8001 | Frontend :5173 | Grafana :3000 | InfluxDB :8086
