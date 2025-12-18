# 🎯 GUÍA PASO A PASO - JMeter Analyzer Pro v1.2.0

> **Inicio rápido** - Sigue estos pasos exactamente

---

## ✅ Pre-requisitos (Verificar ANTES de empezar)

### 1. Docker Desktop debe estar corriendo
- Abre Docker Desktop
- Espera a que diga "Engine running" (verde)
- Verifica versión mínima: Docker 20+ y Docker Compose 2+

### 2. Verificar puertos libres
```bash
# En CMD o PowerShell de Windows:
netstat -ano | findstr :5173
netstat -ano | findstr :8001
netstat -ano | findstr :5432

# Si alguno está ocupado, mata el proceso o cambia el puerto en docker-compose.yml
```

### 3. Obtener API Key de Gemini
1. Ve a: https://makersuite.google.com/app/apikey
2. Inicia sesión con cuenta de Google
3. Click en "Create API Key"
4. Copia la API Key completa

---

## 📦 PASO 1: Descargar y Ubicar el Proyecto

1. Descarga la carpeta `jmeter-analyzer` completa
2. Guárdala en una ubicación accesible, por ejemplo:
   ```
   C:\Users\TuUsuario\Projects\jmeter-analyzer
   ```

---

## 🔑 PASO 2: Configurar API Key de Gemini

**MUY IMPORTANTE: Sin este paso, la IA no funcionará**

### Opción A: Con Visual Studio Code (Recomendado)

1. Abre VS Code
2. `File` > `Open Folder` > Selecciona `jmeter-analyzer`
3. Busca el archivo `.env` en el explorador de archivos (raíz del proyecto)
4. Abre `.env`
5. Busca la línea:
   ```env
   GEMINI_API_KEY=tu_api_key_aqui
   ```
6. **REEMPLAZA** con tu API Key completa
7. Guarda el archivo (`Ctrl + S`)

### Opción B: Con Notepad

1. Navega a la carpeta `jmeter-analyzer`
2. Haz clic derecho en `.env` > Abrir con > Bloc de notas
3. Busca la línea `GEMINI_API_KEY=`
4. Pega tu API Key completa (sin espacios)
5. Guarda y cierra

---

## 🚀 PASO 3: Abrir Terminal

### Opción A: Desde VS Code (Más fácil)
1. Con el proyecto abierto en VS Code
2. Presiona `` Ctrl + ` `` (tecla de acento grave, al lado del 1)
3. O en el menú: `Terminal` > `New Terminal`

### Opción B: CMD de Windows
1. Abre CMD
2. Navega al proyecto:
   ```cmd
   cd C:\Users\TuUsuario\Projects\jmeter-analyzer
   ```

### Opción C: PowerShell
1. Abre PowerShell
2. Navega al proyecto:
   ```powershell
   cd C:\Users\TuUsuario\Projects\jmeter-analyzer
   ```

---

## 🏗️ PASO 4: Construir y Levantar el Proyecto

**Primera vez (construye imágenes):**

```bash
docker-compose up --build -d
```

Este comando:
- `--build`: Construye las imágenes Docker
- `-d`: Corre en segundo plano (detached)

**Tiempo estimado:** 5-10 minutos la primera vez

**Lo que verás:**
```
[+] Building 120.5s (25/25) FINISHED
[+] Running 3/3
 ✔ Container jmeter_postgres   Started
 ✔ Container jmeter_backend    Started
 ✔ Container jmeter_frontend   Started
```

---

## 💀 PASO 5: Ver el Progreso

Mientras se construye, puedes ver los logs:

```bash
docker-compose logs -f
```

**Busca estos mensajes de éxito:**
- Backend: `INFO: Application startup complete.`
- Frontend: `ready in 1234 ms`
- Postgres: `database system is ready to accept connections`

Presiona `Ctrl + C` para salir de los logs (no detiene los servicios)

---

## ✅ PASO 6: Verificar que Todo Funciona

### A. Verificar servicios corriendo

```bash
docker-compose ps
```

Deberías ver 3 servicios "Up":
```
NAME                STATUS              PORTS
jmeter_backend      Up (healthy)        0.0.0.0:8001->8001/tcp
jmeter_frontend     Up                  0.0.0.0:5173->5173/tcp
jmeter_postgres     Up                  0.0.0.0:5432->5432/tcp
```

### B. Acceder a la aplicación

Abre tu navegador y ve a:

**Frontend:** http://localhost:5173

Deberías ver:
- ✅ Interfaz de SQA - Software Quality Assurance
- ✅ Botón "Seleccionar Archivo" para subir JTL
- ✅ Sección de "Criterios de Aceptación"

**Documentación API:** http://localhost:8001/docs

Deberías ver:
- ✅ Swagger UI con endpoints documentados
- ✅ Endpoints de upload, executions, charts, export

**Health Check:** http://localhost:8001/health

Deberías ver:
```json
{"status": "healthy", "version": "1.2.0"}
```

---

## 🎯 PASO 7: Probar con un JTL de Ejemplo

### Opción A: Usar JTL de prueba incluido
Si el proyecto incluye `tests/fixtures/sample.jtl`:
1. Ve a http://localhost:5173
2. Click en "Seleccionar Archivo"
3. Navega a `jmeter-analyzer/tests/fixtures/sample.jtl`
4. Click en "Generar Reporte"
5. Espera ~30-40 segundos (análisis IA)
6. ¡Dashboard completo! 🎉

### Opción B: Usar tu propio JTL
1. Genera un JTL desde JMeter
2. Sube el archivo
3. Ve el análisis completo con IA

---

## 🛠 Si Algo Sale Mal

### Error: "Port 5173 is already in use"

**Opción 1:** Liberar el puerto
```bash
# Windows
netstat -ano | findstr :5173
# Anota el PID (último número)
taskkill /PID <número> /F
```

**Opción 2:** Cambiar puerto en `docker-compose.yml`
```yaml
frontend:
  ports:
    - "3000:5173"  # Cambiar 5173 por 3000
```

### Error: "Cannot connect to Docker daemon"

1. Abre Docker Desktop
2. Espera a que inicie completamente
3. Reintentar el comando

### Error: Backend no conecta

```bash
# Ver logs del backend
docker-compose logs backend

# Reiniciar backend
docker-compose restart backend
```

### Error: Frontend muestra "Error al conectar con el backend"

1. Verifica que el backend esté corriendo:
   ```bash
   docker-compose ps
   ```

2. Verifica que el puerto 8001 esté libre:
   ```bash
   netstat -ano | findstr :8001
   ```

3. Prueba acceder directamente:
   http://localhost:8001/health

### Error: "ai_conclusions is an invalid keyword"

```bash
# Agregar columna faltante a BD
docker-compose exec postgres psql -U jmeter_user -d jmeter_analyzer_db -c "ALTER TABLE test_executions ADD COLUMN IF NOT EXISTS ai_conclusions TEXT;"

# Reiniciar backend
docker-compose restart backend
```

### Error: Modelo Gemini no encontrado

Si ves:
```
ERROR: 404 models/gemini-1.5-pro is not found
```

**Ya está corregido en v1.2.0** - El código usa `gemini-1.5-pro-latest`

---

## 🎓 Comandos Útiles

### Ver estado de servicios
```bash
docker-compose ps
```

### Ver logs en tiempo real
```bash
# Todos los servicios
docker-compose logs -f

# Solo backend
docker-compose logs -f backend

# Solo frontend
docker-compose logs -f frontend

# Filtrar por palabra
docker-compose logs backend | findstr "ERROR"
```

### Reiniciar servicios
```bash
# Reiniciar todo
docker-compose restart

# Reiniciar solo backend
docker-compose restart backend
```

### Detener todo
```bash
docker-compose down
```

### Iniciar después de detener
```bash
docker-compose up -d
```

### Acceder a shell del backend (debug)
```bash
docker-compose exec backend /bin/bash
```

### Ver uso de recursos
```bash
docker stats
```

---

## 📊 Entendiendo el Dashboard

### Sección 1: Metadata
- Nombre del proyecto
- Cliente
- Archivo JTL subido
- Fecha/hora de inicio y fin
- Duración total

### Sección 2: Métricas Clave (4 Cards)
1. **Total Requests**: Total de peticiones ejecutadas
2. **Avg Response Time**: Tiempo promedio de respuesta
3. **Error Rate**: Porcentaje de errores
4. **Throughput**: Requests por segundo

### Sección 3: Tabla de Estadísticas
- Estadísticas detalladas por transacción
- Métricas: promedio, min, max, P50, P90, P95, P99
- Throughput y tasa de error por transacción

### Sección 4: Gráficos (8 Gráficos Interactivos)
1. Response Times por Transacción
2. Response Time Over Time
3. Throughput Over Time
4. Latency Over Time
5. Error Rate Over Time
6. Response Codes per Second
7. Transactions per Second
8. Active Threads Over Time

### Sección 5: Análisis IA (12 Análisis) ✨ v1.2.0
- Análisis de tabla resumen
- Análisis de errores
- Análisis de 8 gráficos
- **Conclusiones generales** (sintetizan todo)
- **Recomendaciones priorizadas** (CRÍTICO/ALTO/MEDIO)

### Sección 6: Exportación
- Botón "Exportar HTML Interactivo"
- Botón "Exportar PDF Completo"

---

## ✅ Checklist Final

Antes de usar el sistema, verifica:

- [ ] Docker Desktop corriendo
- [ ] `docker-compose ps` muestra 3 servicios "Up"
- [ ] Frontend accesible en http://localhost:5173
- [ ] Backend accesible en http://localhost:8001/docs
- [ ] Health check responde: http://localhost:8001/health
- [ ] API Key de Gemini configurada en `.env`
- [ ] Tienes un archivo JTL para probar

---

## 🎯 Flujo Completo de Uso

1. **Preparar JTL**: Ejecuta prueba en JMeter y guarda resultados (.jtl)
2. **Subir JTL**: Ve a http://localhost:5173 y sube el archivo
3. **Configurar**: Ingresa nombre, cliente, criterios de aceptación
4. **Generar**: Click en "Generar Reporte"
5. **Esperar**: ~30-40 segundos (análisis IA con 12 llamadas a Gemini)
6. **Ver Dashboard**: Métricas + gráficos + análisis IA completo
7. **Editar** (opcional): Modifica cualquier análisis IA inline
8. **Guardar** (opcional): Click en "💾 Guardar Todos los Cambios"
9. **Exportar**: Descarga PDF o HTML según necesites

---

## 💡 Tips y Mejores Prácticas

### Para JTLs Grandes (>50,000 muestras)
- El parsing tomará más tiempo (~2-3 minutos)
- El análisis IA sigue tomando ~30-40 segundos
- Considera usar intervalos más grandes (20s en lugar de 10s)

### Para Criterios de Aceptación
Formato recomendado:
```
• Tiempo de respuesta promedio < 2000ms
• Tasa de error < 0.5%
• Throughput > 50 req/s
• P95 < 3000ms
```

### Para Editar Análisis
- Todos los análisis IA son editables
- Usa las textareas para modificar
- Click en "Guardar" para persistir cambios
- Los cambios se guardan en la BD

### Para Exportar
- **PDF**: Captura visual completa (no editable)
- **HTML**: Interactivo, se puede abrir offline

---

## 🚀 ¡Listo para Usar!

Siguiendo esta guía paso a paso, tendrás el sistema funcionando en menos de 15 minutos.

**Recuerda:** 
- Docker corriendo ✅
- API Key configurada ✅
- Puertos libres ✅

**¡Éxito con tus análisis de performance!** 🎉

---

Para más ayuda, consulta:
- **README.md** - Documentación general
- **TROUBLESHOOTING.md** - Solución de problemas específicos
- **DOCUMENTACION_TECNICA_COMPLETA.md** - Detalles técnicos
