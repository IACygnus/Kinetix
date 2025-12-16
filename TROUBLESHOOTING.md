# 🔧 Solución de Problemas - Troubleshooting

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

## 🚨 Problema 8: Gemini AI no responde

### Verificar configuración
1. Asegúrate de que API Key esté en `.env`:
   ```env
   GEMINI_API_KEY=tu_api_key_completa_aqui
   ```

2. Verifica en el frontend que diga:
   ```
   🤖 Gemini AI: Configurado
   ```

3. Si no, reinicia backend:
   ```bash
   docker-compose restart backend
   ```

### Probar API Key manualmente
```bash
docker-compose exec backend python -c "
from app.core.config import settings
print(f'API Key: {settings.GEMINI_API_KEY[:10]}...')
"
```

---

## 🚨 Problema 9: Error "ENOENT: no such file or directory"

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

## 🚨 Problema 10: "Cannot start service: driver failed"

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
```

Envía estos archivos cuando pidas ayuda.

---

## ✅ Verificación de Salud del Sistema

Ejecuta este script para verificar todo:

```bash
echo "=== Estado de Docker ==="
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
```

---

**Recuerda:** La mayoría de problemas se resuelven con:
1. Verificar que Docker Desktop esté corriendo
2. Reiniciar los servicios: `docker-compose restart`
3. Reconstruir si es necesario: `docker-compose up --build -d`
