# 📚 DOCUMENTACIÓN TÉCNICA COMPLETA
## JMeter Analyzer Pro v1.0 Beta

---

## 📋 RESUMEN EJECUTIVO

**JMeter Analyzer Pro** es un sistema web profesional para análisis automatizado de pruebas de performance JMeter. Combina procesamiento avanzado de archivos JTL con inteligencia artificial (Google Gemini) para generar reportes completos con análisis, conclusiones y recomendaciones técnicas.

### Propuesta de Valor:
- ✅ Análisis automático de resultados JMeter con IA
- ✅ Dashboard interactivo con 8 gráficos de performance
- ✅ Exportación a HTML y PDF con gráficas
- ✅ Edición manual de análisis IA
- ✅ Procesamiento de archivos JTL de cualquier tamaño

---

## 🏗️ ARQUITECTURA DEL SISTEMA

### Diagrama de Arquitectura:
```
┌─────────────────┐
│   Usuario       │
│   (Browser)     │
└────────┬────────┘
         │
         │ HTTP (5173)
         ▼
┌─────────────────────────────────┐
│   FRONTEND                      │
│   React 18 + TypeScript         │
│   Vite + Tailwind CSS           │
│   - Dashboard interactivo       │
│   - Gráficos Recharts           │
│   - Export PDF (html2canvas)    │
└────────┬────────────────────────┘
         │
         │ REST API (8001)
         │ JSON
         ▼
┌─────────────────────────────────┐
│   BACKEND                       │
│   FastAPI (Python 3.11)         │
│   - Upload & Parse JTL          │
│   - Análisis IA (Gemini)        │
│   - Export HTML (Jinja2)        │
└────────┬────────────────────────┘
         │
         ├─────────────┬──────────────┐
         │             │              │
         ▼             ▼              ▼
    ┌────────┐   ┌─────────┐   ┌──────────┐
    │ SQLAlch│   │ Pandas  │   │  Gemini  │
    │ (async)│   │  (JTL)  │   │   API    │
    └───┬────┘   └─────────┘   └──────────┘
        │
        ▼
    ┌────────────────┐
    │  PostgreSQL 15 │
    │  - Ejecuciones │
    │  - Análisis IA │
    └────────────────┘
```

### Patrón Arquitectónico:
- **Estilo**: Arquitectura de 3 capas (Presentación, Lógica, Datos)
- **Comunicación**: REST API con JSON
- **Persistencia**: PostgreSQL relacional
- **Containerización**: Docker Compose (3 contenedores)

---

## 💻 STACK TECNOLÓGICO

### Backend (FastAPI)

#### Framework & Core:
- **FastAPI** 0.104.1: Framework web asíncrono de alto rendimiento
- **Uvicorn** 0.24.0: Servidor ASGI con soporte async/await
- **Python** 3.11: Lenguaje base con type hints

#### Base de Datos:
- **SQLAlchemy** 2.0.23 (async): ORM con soporte asíncrono
- **asyncpg** 0.29.0: Driver PostgreSQL asíncrono
- **PostgreSQL** 15-alpine: Base de datos relacional

#### Procesamiento de Datos:
- **Pandas** 2.1.3: Procesamiento y análisis de archivos JTL
- **NumPy**: Cálculos de percentiles y estadísticas

#### Inteligencia Artificial:
- **google-generativeai** 0.3.1: SDK de Google Gemini API
- **Modelo**: gemini-1.5-pro

#### Exportación:
- **Jinja2** 3.1.2: Motor de templates para HTML
- **WeasyPrint** 60.1: Generación de PDF desde HTML (no usado actualmente)

#### Seguridad:
- **python-jose** 3.3.0: JWT tokens
- **passlib** 1.7.4: Hashing de contraseñas (bcrypt)

#### Utilidades:
- **python-multipart** 0.0.6: Manejo de uploads multipart
- **python-dotenv** 1.0.0: Variables de entorno

### Frontend (React + TypeScript)

#### Framework & Core:
- **React** 18.2.0: Librería UI con hooks
- **TypeScript** 5.2.2: Tipado estático
- **Vite** 5.0.8: Build tool y dev server

#### Estilos:
- **Tailwind CSS** 3.4.0: Framework CSS utility-first
- **PostCSS** 8.4.32: Procesador CSS

#### Visualización:
- **Recharts** 2.10.3: Librería de gráficos React
  - LineChart (multi-línea)
  - AreaChart (filled)
  - PieChart (errores)
- **lucide-react** 0.294.0: Iconos

#### Exportación PDF:
- **html2canvas** 1.4.1: Captura de DOM a canvas
- **jsPDF** 2.5.1: Generación de PDF desde imágenes

#### HTTP Client:
- **Fetch API** nativa: Comunicación con backend

### Infraestructura

#### Containerización:
- **Docker** 24+: Contenedores
- **Docker Compose** v2: Orquestación multi-contenedor

#### Estructura de Contenedores:
```yaml
services:
  postgres:      # PostgreSQL 15-alpine
  backend:       # FastAPI (Python 3.11)
  frontend:      # Node 18 + Vite
```

#### Networking:
- Red bridge interna para comunicación inter-contenedores
- Exposición de puertos específicos al host

#### Volúmenes:
- `postgres_data`: Persistencia de BD
- `./backend`: Código backend (bind mount)
- `./frontend`: Código frontend (bind mount)
- `/app/uploads`: Archivos JTL subidos

---

## 📊 MODELO DE DATOS

### Tabla: `test_executions`

```sql
CREATE TABLE test_executions (
    -- Identificación
    id                  UUID PRIMARY KEY,
    user_id             UUID,
    name                VARCHAR(255) NOT NULL,
    description         TEXT,
    jtl_filename        VARCHAR(255) NOT NULL,
    
    -- Metadata temporal
    start_time          TIMESTAMP,
    end_time            TIMESTAMP,
    duration_seconds    FLOAT,
    execution_date      TIMESTAMP,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW(),
    
    -- Métricas agregadas
    total_requests      INTEGER DEFAULT 0,
    total_errors        INTEGER DEFAULT 0,
    error_rate          FLOAT DEFAULT 0.0,
    avg_response_time   FLOAT DEFAULT 0.0,
    median_response_time FLOAT DEFAULT 0.0,
    min_response_time   FLOAT DEFAULT 0.0,
    max_response_time   FLOAT DEFAULT 0.0,
    p50_response_time   FLOAT DEFAULT 0.0,
    p90_response_time   FLOAT DEFAULT 0.0,
    p95_response_time   FLOAT DEFAULT 0.0,
    p99_response_time   FLOAT DEFAULT 0.0,
    throughput          FLOAT DEFAULT 0.0,
    avg_latency         FLOAT DEFAULT 0.0,
    kb_per_sec_received FLOAT DEFAULT 0.0,
    kb_per_sec_sent     FLOAT DEFAULT 0.0,
    
    -- Análisis IA (todos TEXT, nullable)
    ai_analysis_summary                   TEXT,
    ai_analysis_errors                    TEXT,
    ai_analysis_response_times            TEXT,
    ai_analysis_response_time_over_time   TEXT,
    ai_analysis_throughput                TEXT,
    ai_analysis_latency                   TEXT,
    ai_analysis_error_rate                TEXT,
    ai_analysis_codes_per_second          TEXT,
    ai_analysis_transactions_per_second   TEXT,
    ai_analysis_active_threads            TEXT,
    ai_recommendations                    TEXT,
    ai_conclusions                        TEXT
);
```

### Índices:
- PRIMARY KEY en `id` (UUID)
- Índice en `created_at` para listados ordenados

---

## 🔄 FLUJO DE PROCESAMIENTO

### 1. Upload de JTL

```
Usuario selecciona JTL
    │
    ▼
Frontend: POST /api/v1/upload
    │
    ▼
Backend recibe archivo
    │
    ├─ Validar extensión (.jtl, .csv)
    ├─ Guardar en /app/uploads
    ├─ Parsear con Pandas
    │  ├─ Leer CSV
    │  ├─ Convertir timestamps
    │  ├─ Calcular métricas
    │  └─ Agrupar por label
    │
    ├─ Llamar a Gemini IA (11 llamadas)
    │  ├─ Análisis general
    │  ├─ Análisis tabla resumen
    │  ├─ Análisis errores
    │  ├─ Análisis 8 gráficos
    │  ├─ Conclusiones
    │  └─ Recomendaciones
    │
    ├─ Crear registro en BD
    └─ Retornar ejecución
    │
    ▼
Frontend recibe datos
    │
    ├─ Guardar en estado
    └─ Navegar a Dashboard
```

**Tiempo actual**: 30-60 segundos (PROBLEMA)

### 2. Visualización Dashboard

```
Dashboard carga
    │
    ├─ GET /api/v1/executions/{id}
    │  └─ Datos de ejecución + análisis IA
    │
    └─ GET /api/v1/executions/{id}/charts
       └─ Datos para gráficos
    │
    ▼
Renderizar componentes:
    ├─ Cards de resumen (4)
    ├─ Tabla de transacciones
    ├─ Gráficos Recharts (8)
    ├─ Análisis IA editables
    └─ Botones de exportación
```

### 3. Exportación PDF

```
Usuario click "Exportar PDF"
    │
    ▼
Frontend: handleExportPDF()
    │
    ├─ Ocultar botones (.export-buttons)
    ├─ html2canvas(dashboard-content)
    │  └─ Captura TODO (gráficas incluidas)
    ├─ jsPDF.addImage()
    │  └─ Generar páginas múltiples
    ├─ pdf.save()
    └─ Restaurar botones
```

**Tiempo**: 5-10 segundos

---

## 🎨 COMPONENTES FRONTEND

### Dashboard.tsx (Principal)

**Responsabilidades**:
- Cargar datos de ejecución
- Renderizar 8 gráficos interactivos
- Manejar edición de análisis IA
- Exportar HTML/PDF
- Gestionar estado de UI

**Hooks principales**:
```typescript
useState: execution, charts, loading, análisis IA
useEffect: Cargar datos al montar
handleExportPDF: Capturar y generar PDF
handleSaveChanges: Guardar análisis editados
```

**Sub-componentes**:
- Cards de resumen (4)
- Tabla de estadísticas
- 8 gráficos Recharts
- Textareas editables
- Botones de acción

### Gráficos Implementados

1. **Response Times por Transacción** (LineChart multi-línea)
   - Legend interactiva (click para ocultar)
   - Eje X: Tiempo (elapsed/real)
   - Eje Y: ms

2. **Response Time Over Time** (AreaChart)
   - Tiempo promedio a lo largo del tiempo
   - Area filled con gradiente

3. **Throughput Over Time** (AreaChart)
   - Requests por segundo
   - Visualización de capacidad

4. **Latency Over Time** (AreaChart)
   - Latencia de red
   - Identifica problemas de conectividad

5. **Error Rate Over Time** (AreaChart)
   - Porcentaje de errores
   - Detecta picos de fallas

6. **Response Codes per Second** (LineChart multi-línea)
   - Códigos HTTP agrupados
   - 200, 404, 405, 500, etc.

7. **Transactions per Second** (LineChart multi-línea)
   - TPS por transacción
   - Balance de carga

8. **Active Threads Over Time** (AreaChart)
   - Concurrencia de usuarios
   - Ramp-up visualization

---

## 🔌 API ENDPOINTS

### Upload & Ejecuciones

**POST** `/api/v1/upload`
```
Query Params:
  - name: string (nombre de prueba)
  - description: string (cliente)
  - acceptance_criteria: string (opcional)
  
Body: multipart/form-data
  - file: .jtl o .csv

Response: TestExecutionResponse (JSON)
  - id, name, descripción
  - métricas agregadas
  - análisis IA completos
```

**GET** `/api/v1/executions`
```
Query Params:
  - limit: int (default 10)
  
Response: List[TestExecutionResponse]
  - Lista de ejecuciones ordenadas por fecha
```

**GET** `/api/v1/executions/{execution_id}`
```
Path Params:
  - execution_id: UUID

Response: TestExecutionResponse
  - Detalles completos de ejecución
```

**GET** `/api/v1/executions/{execution_id}/charts`
```
Path Params:
  - execution_id: UUID

Response: ChartData (JSON)
  - timeline: List[TimelineData]
  - by_label: List[LabelStats]
  - response_times_by_label: List[...]
  - throughput_timeline: List[...]
  - (8 datasets totales)
```

**PUT** `/api/v1/executions/{execution_id}/analysis`
```
Path Params:
  - execution_id: UUID
  
Body: UpdateAnalysisRequest (JSON)
  - ai_analysis_summary: string
  - ai_analysis_errors: string
  - ... (todos los campos editables)

Response: 200 OK
```

### Exportación

**GET** `/api/v1/executions/{execution_id}/export/html`
```
Response: text/html
  - Archivo HTML standalone
  - Content-Disposition: attachment
```

**GET** `/api/v1/executions/{execution_id}/export/pdf`
```
Response: application/pdf
  - PDF generado con WeasyPrint (backend)
  - NO usado actualmente (frontend genera PDF)
```

---

## 🤖 INTEGRACIÓN IA (GEMINI)

### Configuración

```python
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-pro')
```

### Prompts Implementados

#### 1. Análisis General
```
Entrada: Métricas globales (total requests, error rate, tiempos, throughput)
Salida: Análisis técnico de 3 párrafos sobre performance general
```

#### 2. Análisis Tabla Resumen
```
Entrada: Top 10 transacciones con métricas detalladas
Salida: 6-8 oraciones mencionando:
  - Total de transacciones ejecutadas
  - Transacciones con mejor/peor performance
  - Análisis de variabilidad (P95 vs promedio)
  - Rendimiento (throughput)
  - Transacciones exitosas vs fallidas
```

#### 3. Análisis de Errores
```
Entrada: Lista de errores por transacción con códigos HTTP
Salida: 5-6 oraciones sobre:
  - Total de errores y porcentaje
  - Códigos HTTP detectados y significado
  - Transacciones más afectadas
  - Causas técnicas posibles
  - Impacto en funcionalidad
  - Recomendación inmediata
```

#### 4-11. Análisis por Gráfico (8 análisis)
```
Entrada: Resumen de datos del gráfico específico
Salida: 3-4 oraciones técnicas sobre:
  - Patrones observados
  - Métricas específicas con números
  - Comportamiento del sistema
  - Conclusión sobre aspecto medido
```

#### 12. Conclusiones
```
Entrada: Métricas clave de la prueba
Salida: 3-4 conclusiones con viñetas sobre:
  - Evaluación de errores
  - Evaluación de tiempos de respuesta
  - Evaluación de capacidad
  - Evaluación de estabilidad
  - Veredicto claro (exitoso/fallido/requiere atención)
```

#### 13. Recomendaciones
```
Entrada: Métricas detalladas de la prueba
Salida: 4-5 recomendaciones accionables con viñetas:
  - Específicas y técnicas
  - Basadas en números reales
  - Accionables (qué hacer exactamente)
  - Con contexto de por qué es importante
```

### Rate Limits y Manejo de Errores

```python
try:
    response = model.generate_content(prompt)
    return response.text
except Exception as e:
    logger.error(f"Error en Gemini: {str(e)}")
    return fallback_analysis
```

**Fallbacks**: Análisis básicos con métricas calculadas si Gemini falla

---

## 🔒 SEGURIDAD

### Implementado:
- ✅ Validación de extensiones de archivo (.jtl, .csv)
- ✅ Validación UUID en todos los endpoints
- ✅ CORS configurado (whitelist de orígenes)
- ✅ Type checking con TypeScript
- ✅ Sanitización de nombres de archivo
- ✅ Variables de entorno para secretos

### Por Implementar:
- 🔲 Autenticación JWT (preparado pero no activo)
- 🔲 Rate limiting en API
- 🔲 Sanitización de contenido de análisis IA
- 🔲 Validación de tamaño máximo de archivo
- 🔲 HTTPS en producción

---

## 📦 DEPLOYMENT

### Requisitos del Sistema:
- Docker 24+
- Docker Compose v2
- 4GB RAM mínimo
- 10GB espacio en disco

### Variables de Entorno (.env):

```bash
# Backend
GEMINI_API_KEY=AIzaSy...
DATABASE_URL=postgresql+asyncpg://jmeter_user:jmeter_secure_2024@postgres:5432/jmeter_analyzer_db
SECRET_KEY=your-secret-key-here

# PostgreSQL
POSTGRES_USER=jmeter_user
POSTGRES_PASSWORD=jmeter_secure_2024
POSTGRES_DB=jmeter_analyzer_db

# Frontend
VITE_API_URL=http://localhost:8001
```

### Comandos de Deployment:

```bash
# Build y levantar servicios
docker-compose up -d --build

# Ver logs
docker-compose logs -f

# Detener servicios
docker-compose down

# Detener y limpiar volúmenes
docker-compose down -v
```

### Healthchecks:
- PostgreSQL: `pg_isready`
- Backend: `GET /docs` (FastAPI OpenAPI)
- Frontend: `GET /` (página principal)

---

## 🧪 TESTING

### Backend:
```bash
docker-compose exec backend pytest
```

### Frontend:
```bash
docker-compose exec frontend npm test
```

### E2E Manual:
1. Upload JTL → Verificar procesamiento exitoso
2. Dashboard → Verificar 8 gráficos + análisis IA
3. Editar análisis → Guardar → Verificar persistencia
4. Exportar HTML → Verificar descarga
5. Exportar PDF → Verificar gráficas incluidas

---

## 📈 MÉTRICAS Y MONITOREO

### Logs Backend (Uvicorn):
```
INFO:app.api.v1.endpoints.upload:🚀 Iniciando procesamiento...
INFO:app.api.v1.endpoints.upload:📊 JTL parseado: 11349 muestras
INFO:app.api.v1.endpoints.upload:🤖 Iniciando análisis general de IA...
INFO:app.api.v1.endpoints.upload:✅ Todos los análisis IA completados
```

### Métricas clave:
- Tiempo de procesamiento JTL
- Tiempo de análisis IA (actualmente 30-60s)
- Tamaño de archivos JTL procesados
- Tasa de errores en upload
- Tiempo de generación PDF

---

## 🐛 PROBLEMAS CONOCIDOS

### CRÍTICO - Performance IA:
**Síntoma**: Sistema se queda cargando indefinidamente al subir JTL
**Causa**: 11 llamadas secuenciales a Gemini (3-5 seg cada una)
**Impacto**: 30-60 segundos de espera, percepción de sistema colgado
**Solución propuesta**: Llamadas paralelas con asyncio.gather()

### Menor - WeasyPrint fonts:
**Síntoma**: Warnings sobre emojis no soportados en PDF backend
**Impacto**: Ninguno (no se usa PDF backend actualmente)

---

## 🚀 ROADMAP

### Versión 1.1 (Próxima):
- [ ] Análisis IA en paralelo (asyncio.gather)
- [ ] Reducir tiempo de procesamiento a <15 segundos
- [ ] Loading indicators mejorados

### Versión 1.2:
- [ ] Análisis asíncrono en background
- [ ] Websockets para actualizaciones en tiempo real
- [ ] Comparación entre ejecuciones

### Versión 2.0:
- [ ] Autenticación multi-usuario
- [ ] Proyectos y carpetas
- [ ] Histórico y tendencias
- [ ] Alertas automáticas

---

## 📞 SOPORTE Y CONTACTO

**Desarrollador**: Fredy Gabriel Bonilla
**Empresa**: SQA - Software Quality Assurance
**Versión**: 1.0 Beta
**Última actualización**: Diciembre 2024

---

**FIN DE DOCUMENTACIÓN TÉCNICA**
