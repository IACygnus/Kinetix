# 🔧 Solución de Problemas - Troubleshooting v1.2.0

---

## 🚨 Problema 1: "Port 8001 is already allocated"

### Causa
El puerto 8001 está siendo usado por otro programa.

### Solución A: Liberar el puerto
```bash
# Windows
netstat -ano | findstr :8001
# Anota el PID (última columna)
taskkill /PID <número> /F

# Ejemplo:
# Si ves: TCP 0.0.0.0:8001 0.0.0.0:0 LISTENING 1234
# Ejecuta: taskkill /PID 1234 /F
```

### Solución B: Cambiar puerto temporalmente
1. Editar `docker-compose.yml`:
   ```yaml
   backend:
     ports:
       - "8002:8001"  # Cambia 8001 por 8002 externamente
   ```

2. Editar `.env`:
   ```env
   BACKEND_PORT=8001  # Mantener 8001 interno
   ```

3. Reiniciar:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

4. Acceder en: http://localhost:8002

---

## 🚨 Problema 2: "Port 5173 is already allocated"

### Solución
Similar al problema 1, pero para frontend:

```yaml
frontend:
  ports:
    - "3000:5173"  # Usar puerto 3000 en lugar de 5173
```

Luego acceder a: http://localhost:3000

---

## 🚨 Problema 3: Backend conecta pero Frontend muestra error

### Error en navegador:
```
Error al conectar con el backend. Verifica que Docker esté corriendo.
```

### Causa
CORS o URL incorrecta.

### Solución
1. Verificar que backend esté corriendo:
   ```bash
   curl http://localhost:8001/health
   ```

2. Si responde, el problema es CORS. Editar `.env`:
   ```env
   CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000
   ```

3. Reiniciar backend:
   ```bash
   docker-compose restart backend
   ```

---

## 🚨 Problema 4: "Cannot connect to Docker daemon"

### Síntomas
```
ERROR: error during connect: This error may indicate that the docker daemon is not running.
```

### Solución
1. Abre Docker Desktop
2. Espera a ver "Engine running" (icono verde)
3. Si no inicia:
   - Windows: Reinicia Docker Desktop
   - Verifica en Task Manager que "Docker Desktop" esté corriendo

---

## 🚨 Problema 5: Base de datos no inicia

### Logs muestran:
```
postgres    | FATAL:  data directory "/var/lib/postgresql/data" has wrong ownership
```

### Solución
```bash
# Eliminar volumen corrupto
docker-compose down -v
docker volume rm jmeter-analyzer_postgres_data

# Reiniciar
docker-compose up -d
```

**⚠️ Advertencia:** Esto borra todos los datos de la base de datos.

---

## 🚨 Problema 6: Cambios en código no se reflejan

### Para Backend (Python)
```bash
# El reload automático está activado, pero si no funciona:
docker-compose restart backend

# O reconstruir:
docker-compose up --build backend -d
```

### Para Frontend (React)
```bash
# Normalmente Vite detecta cambios automáticamente
# Si no:
docker-compose restart frontend

# Limpiar cache del navegador: Ctrl + Shift + R
```

---

## 🚨 Problema 7: "ModuleNotFoundError" en backend

### Error:
```
ModuleNotFoundError: No module named 'fastapi'
```

### Solución
Reconstruir imagen del backend:
```bash
docker-compose build backend --no-cache
docker-compose up -d
```

---

## 🚨 Problema 8: ✨ "ai_conclusions is an invalid keyword" (v1.2.0)

### Error completo:
```
TypeError: 'ai_conclusions' is an invalid keyword argument for TestExecution
```

### Causa
El campo `ai_conclusions` no existe en la base de datos.

### Solución
```bash
# Agregar columna a la tabla
docker-compose exec postgres psql -U jmeter_user -d jmeter_analyzer_db -c "ALTER TABLE test_executions ADD COLUMN IF NOT EXISTS ai_conclusions TEXT;"

# Verificar que se agregó
docker-compose exec postgres psql -U jmeter_user -d jmeter_analyzer_db -c "SELECT column_name FROM information_schema.columns WHERE table_name='test_executions' AND column_name='ai_conclusions';"

# Debería mostrar:
#  column_name   
# ----------------
#  ai_conclusions

# Reiniciar backend
docker-compose restart backend
```

---

## 🚨 Problema 9: ✨ Modelo Gemini no encontrado (v1.2.0)

### Error:
```
ERROR: 404 models/gemini-1.5-pro is not found for API version v1beta
```

### Causa
El código intenta usar `gemini-1.5-pro` pero debe usar `gemini-1.5-pro-latest`.

### Solución
**Ya está corregido en v1.2.0**. Si ves este error:

1. Verifica que tengas el archivo correcto:
   ```bash
   # Ver contenido de gemini.py
   docker-compose exec backend cat /app/app/services/ai/gemini.py | grep "GenerativeModel"
   
   # Debería mostrar:
   # self.model = genai.GenerativeModel('gemini-1.5-pro-latest')
   ```

2. Si no, actualiza el archivo `backend/app/services/ai/gemini.py`:
   ```python
   # Línea ~19
   self.model = genai.GenerativeModel('gemini-1.5-pro-latest')
   ```

3. Reiniciar backend:
   ```bash
   docker-compose restart backend
   ```

---

## 🚨 Problema 10: Gemini AI no responde

### Verificar configuración
1. Asegúrate de que API Key esté en `.env`:
   ```env
   GEMINI_API_KEY=tu_api_key_completa_aqui
   ```

2. Verifica que la API Key sea válida:
   - Ve a: https://makersuite.google.com/app/apikey
   - Verifica que esté activa
   - Si es necesario, genera una nueva

3. Reinicia backend:
   ```bash
   docker-compose restart backend
   ```

### Probar API Key manualmente
```bash
docker-compose exec backend python -c "
import os
print(f'API Key: {os.getenv(\"GEMINI_API_KEY\")[:10]}...')
"
```

### Verificar conectividad
```bash
# Test endpoint simple
docker-compose exec backend python -c "
import google.generativeai as genai
import os
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-pro-latest')
response = model.generate_content('Hello')
print('Gemini responde:', response.text[:50])
"
```

---

## 🚨 Problema 11: Error "ENOENT: no such file or directory"

### Error al construir frontend
```
npm ERR! enoent ENOENT: no such file or directory, open 'package.json'
```

### Solución
1. Verificar que estás en la carpeta correcta:
   ```bash
   pwd  # Linux/Mac
   cd   # Windows
   ```

2. Debe mostrar algo como:
   ```
   C:\Users\TuUsuario\Projects\jmeter-analyzer
   ```

3. Si no, navega a la carpeta correcta y vuelve a intentar.

---

## 🚨 Problema 12: "Cannot start service: driver failed"

### Error completo:
```
ERROR: for backend  Cannot start service backend: driver failed programming external connectivity
```

### Causa
Conflicto de red de Docker.

### Solución
```bash
# Detener todo
docker-compose down

# Limpiar redes
docker network prune

# Reiniciar
docker-compose up -d
```

---

## 🚨 Problema 13: ✨ Análisis IA tarda mucho (>60 segundos)

### Causa
12 llamadas secuenciales a Gemini pueden tardar si:
- Conexión lenta a internet
- Rate limit de Gemini
- API Key gratuita con límites

### Solución A: Verificar logs
```bash
docker-compose logs backend | findstr "🤖"
# Debería mostrar progreso:
# 🤖 [1/10] Analizando tabla resumen...
# 🤖 [2/10] Analizando errores...
# etc.
```

### Solución B: Verificar rate limits
- API Key gratuita: 60 requests/min
- 12 llamadas = ~30-40 segundos es normal
- Si >60 segundos, verificar conexión

### Solución C: Upgrade API Key
Si necesitas más velocidad:
1. Ve a Google AI Studio
2. Considera plan de pago para más throughput

---

## 🚨 Problema 14: Frontend se queda cargando indefinidamente

### Síntomas
- Spinner de carga no termina
- Console muestra timeout

### Causa
Backend tomando >60 segundos o errores no manejados

### Solución
1. Ver logs del backend:
   ```bash
   docker-compose logs backend --tail=100 -f
   ```

2. Buscar errores:
   ```bash
   docker-compose logs backend | findstr "ERROR"
   ```

3. Si ves error de Gemini:
   - Verificar API Key
   - Verificar conectividad
   - Ver problema 9 y 10

4. Si no hay errores pero tarda mucho:
   - Es normal 30-40 segundos
   - Ver problema 13

---

## 📊 Comandos de Diagnóstico

### Ver todos los contenedores (incluso detenidos)
```bash
docker ps -a
```

### Ver logs de un contenedor específico
```bash
docker-compose logs <servicio>
# Ejemplo:
docker-compose logs backend
docker-compose logs frontend
docker-compose logs postgres
```

### Ver logs en tiempo real
```bash
docker-compose logs -f <servicio>
```

### Ver últimas 100 líneas
```bash
docker-compose logs --tail=100 backend
```

### Filtrar logs por palabra
```bash
# Windows
docker-compose logs backend | findstr "ERROR"
docker-compose logs backend | findstr "🤖"

# Linux/Mac
docker-compose logs backend | grep "ERROR"
docker-compose logs backend | grep "🤖"
```

### Verificar uso de recursos
```bash
docker stats
```

### Ver redes de Docker
```bash
docker network ls
```

### Inspeccionar red
```bash
docker network inspect jmeter-analyzer_jmeter_network
```

### Ver volúmenes
```bash
docker volume ls
```

### Inspeccionar volumen de BD
```bash
docker volume inspect jmeter-analyzer_postgres_data
```

---

## 🆘 Si Nada Funciona: Reset Completo

**⚠️ Última opción - Esto borra TODO:**

```bash
# 1. Detener y eliminar todo
docker-compose down -v

# 2. Eliminar imágenes
docker rmi jmeter-analyzer-backend jmeter-analyzer-frontend

# 3. Limpiar sistema
docker system prune -a --volumes

# 4. Reconstruir desde cero
docker-compose up --build -d
```

---

## 📞 Información para Soporte

Si necesitas pedir ayuda, recopila esta información:

```bash
# 1. Versión de Docker
docker --version
docker-compose --version

# 2. Sistema operativo
# Windows: ver /wmic os get caption
# Linux/Mac: uname -a

# 3. Logs completos
docker-compose logs > logs.txt

# 4. Estado de contenedores
docker-compose ps > status.txt

# 5. Contenido de .env (SIN API KEYS)
cat .env | grep -v "API_KEY" > config.txt

# 6. Verificar columnas de BD
docker-compose exec postgres psql -U jmeter_user -d jmeter_analyzer_db -c "\d test_executions" > schema.txt
```

Envía estos archivos cuando pidas ayuda.

---

## ✅ Verificación de Salud del Sistema

### Script de verificación completo:

```bash
echo "=== Versión de Docker ==="
docker --version
docker-compose --version

echo ""
echo "=== Contenedores corriendo ==="
docker-compose ps

echo ""
echo "=== Puertos en uso ==="
netstat -ano | findstr :5173
netstat -ano | findstr :8001
netstat -ano | findstr :5432

echo ""
echo "=== Health checks ==="
curl http://localhost:8001/health
curl http://localhost:5173

echo ""
echo "=== Verificar columna ai_conclusions ==="
docker-compose exec postgres psql -U jmeter_user -d jmeter_analyzer_db -c "SELECT column_name FROM information_schema.columns WHERE table_name='test_executions' AND column_name='ai_conclusions';"

echo ""
echo "=== Verificar modelo Gemini ==="
docker-compose exec backend grep -n "GenerativeModel" /app/app/services/ai/gemini.py
```

---

## 🎯 Problemas Comunes v1.2.0 y Soluciones Rápidas

| Problema | Solución Rápida |
|----------|----------------|
| Puerto ocupado | `taskkill /PID <número> /F` |
| Docker no inicia | Abrir Docker Desktop |
| Campo ai_conclusions no existe | Ejecutar migración SQL |
| Modelo Gemini 404 | Ya corregido en v1.2.0 |
| Análisis IA tarda mucho | Normal 30-40s, verificar logs |
| Frontend cargando infinito | Ver logs backend, buscar errores |
| CORS error | Agregar origen en CORS_ORIGINS |
| ModuleNotFoundError | `docker-compose build --no-cache` |

---

## 📚 Documentación Adicional

- **README.md** - Documentación general
- **GUIA_INICIO.md** - Guía paso a paso
- **RESUMEN_EJECUTIVO.md** - Resumen del proyecto
- **DOCUMENTACION_TECNICA_COMPLETA.md** - Detalles técnicos
- **PROMPT_MEMORIA_COMPLETA.md** - Contexto del proyecto

---

**Recuerda:** La mayoría de problemas se resuelven con:
1. Verificar que Docker Desktop esté corriendo ✅
2. Reiniciar los servicios: `docker-compose restart` ✅
3. Reconstruir si es necesario: `docker-compose up --build -d` ✅
4. Verificar logs: `docker-compose logs -f` ✅

**Para v1.2.0 específicamente:**
- Asegurar que `ai_conclusions` exista en BD
- Verificar modelo `gemini-1.5-pro-latest` en código
- 30-40 segundos de análisis es normal

---

**Versión:** 1.2.0  
**Última actualización:** Diciembre 2024
