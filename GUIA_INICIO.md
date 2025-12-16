# 🎯 GUÍA PASO A PASO - Inicio Inmediato

> **Para presentación mañana** - Sigue estos pasos exactamente

---

## ✅ Pre-requisitos (Verificar ANTES de empezar)

### 1. Docker Desktop debe estar corriendo
- Abre Docker Desktop
- Espera a que diga "Engine running" (verde)
- Verifica en la imagen que subiste: tienes Docker instalado ✅

### 2. Verificar puertos libres
```bash
# En CMD o PowerShell de Windows:
netstat -ano | findstr :5173
netstat -ano | findstr :8001
netstat -ano | findstr :5432

# Si alguno está ocupado, mata el proceso o cambia el puerto en docker-compose.yml
```

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
5. Busca la línea (aproximadamente línea 44):
   ```env
   GEMINI_API_KEY=AIzaSyBzSNFbAf9D3...VM_M
   ```
6. **REEMPLAZA** con tu API Key completa de la imagen que subiste
7. Guarda el archivo (`Ctrl + S`)

### Opción B: Con Notepad

1. Navega a la carpeta `jmeter-analyzer`
2. Haz clic derecho en `.env` > Abrir con > Bloc de notas
3. Busca la línea `GEMINI_API_KEY=`
4. Pega tu API Key completa
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

---

## 🏗️ PASO 4: Construir y Levantar el Proyecto

**Primera vez (construye imágenes):**

```bash
docker-compose up --build -d
```

Este comando:
- `-d`: Corre en segundo plano
- `--build`: Construye las imágenes Docker

**Tiempo estimado:** 5-10 minutos la primera vez

---

## 👀 PASO 5: Ver el Progreso

Mientras se construye, puedes ver los logs:

```bash
docker-compose logs -f
```

Presiona `Ctrl + C` para salir de los logs (no detiene los servicios)

---

## ✅ PASO 6: Verificar que Todo Funciona

### A. Verificar servicios corriendo

```bash
docker-compose ps
```

Deberías ver 3 servicios "Up":
```
NAME                STATUS
jmeter_backend      Up
jmeter_frontend     Up
jmeter_postgres     Up
```

### B. Acceder a la aplicación

Abre tu navegador y ve a:

**Frontend:** http://localhost:5173

Deberías ver una pantalla con:
- ✅ Tarjeta de Frontend (verde)
- ✅ Tarjeta de Backend (verde)
- ✅ "Fase 1 Completada"

**Documentación API:** http://localhost:8001/docs

---

## 🐛 Si Algo Sale Mal

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

---

## 🎓 Comandos Útiles para tu Presentación

### Ver estado de servicios
```bash
docker-compose ps
```

### Ver logs en tiempo real
```bash
docker-compose logs -f
```

### Reiniciar todo
```bash
docker-compose restart
```

### Detener todo
```bash
docker-compose down
```

### Iniciar después de detener
```bash
docker-compose up -d
```

### Acceder a shell del backend (por si necesitas debug)
```bash
docker-compose exec backend /bin/bash
```

---

## 📸 Para tu Presentación

### Pantallas que puedes mostrar:

1. **Terminal con servicios corriendo:**
   ```bash
   docker-compose ps
   ```

2. **Frontend funcionando:**
   http://localhost:5173
   
3. **Documentación de la API:**
   http://localhost:8001/docs
   
4. **Health check del backend:**
   http://localhost:8001/health

5. **Docker Desktop:**
   - Muestra los 3 contenedores corriendo
   - Pestaña "Containers"

---

## ⏱️ Cronograma Sugerido para Hoy

- **13:00 - 13:30:** Descargar proyecto y configurar API Key ✅
- **13:30 - 14:00:** Primera ejecución con `docker-compose up --build` ✅
- **14:00 - 14:30:** Verificar que todo funciona, tomar screenshots ✅
- **14:30 - 15:00:** Preparar presentación con las pantallas ✅
- **15:00 - 17:00:** Practicar demo y resolver cualquier duda ✅

---

## 🆘 Contacto de Emergencia

Si algo falla y necesitas ayuda urgente:

1. Toma screenshot del error
2. Copia el log completo:
   ```bash
   docker-compose logs > error.txt
   ```
3. Envíame el error.txt

---

## ✅ Checklist Final

Antes de tu presentación, verifica:

- [ ] Docker Desktop corriendo
- [ ] `docker-compose ps` muestra 3 servicios "Up"
- [ ] Frontend accesible en http://localhost:5173
- [ ] Backend accesible en http://localhost:8001/docs
- [ ] Tarjetas en frontend muestran estado "verde"
- [ ] Screenshots tomados de todas las pantallas
- [ ] Sabes cómo reiniciar servicios si algo falla

---

## 🎯 Para la Demo de Mañana

### Flujo sugerido:

1. **Introducción (2 min):**
   - "Sistema profesional de análisis de reportes JMeter"
   - "Stack: FastAPI + React + PostgreSQL + Gemini AI"

2. **Arquitectura (3 min):**
   - Mostrar Docker Desktop con los 3 contenedores
   - Explicar separación backend/frontend/database

3. **Demo Frontend (3 min):**
   - Abrir http://localhost:5173
   - Mostrar tarjetas de estado
   - Explicar fases implementadas vs pendientes

4. **Demo Backend (3 min):**
   - Abrir http://localhost:8001/docs
   - Mostrar documentación automática
   - Ejecutar endpoint `/api/test` en vivo

5. **Próximos Pasos (2 min):**
   - Fase 2: Autenticación
   - Fase 3: Parser de JTL
   - Fase 6: Análisis con IA

---

## 🚀 ¡Listo para el Éxito!

Siguiendo esta guía paso a paso, tendrás tu proyecto funcionando en menos de 30 minutos.

**Recuerda:** La clave está en tener Docker corriendo y la API Key configurada.

**¡Mucho éxito en tu presentación!** 🎉
