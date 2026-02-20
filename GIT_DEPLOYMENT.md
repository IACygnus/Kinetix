# 🚀 Git Deployment Guide - v1.3.0

Guía completa para subir la actualización v1.3.0 (Grafana + InfluxDB) a tu repositorio Git.

---

## 📋 Pre-requisitos

### 1. Verificar Git configurado
```bash
# Verificar que git esté instalado
git --version

# Verificar configuración de usuario
git config --global user.name
git config --global user.email

# Si no están configurados:
git config --global user.name "Tu Nombre"
git config --global user.email "tu@email.com"
```

### 2. Verificar repositorio remoto
```bash
# Ver remote configurado
git remote -v

# Resultado esperado:
# origin  https://github.com/tu-usuario/jmeter-analyzer.git (fetch)
# origin  https://github.com/tu-usuario/jmeter-analyzer.git (push)
```

---

## 🔧 OPCIÓN A: Actualización Completa (Recomendado)

Use esta opción si quieres actualizar TODA la documentación y archivos nuevos.

### Paso 1: Verificar estado actual
```bash
# Navegar al directorio del proyecto
cd C:\tu\proyecto\jmeter-analyzer

# Ver estado de Git
git status

# Ver rama actual
git branch
```

### Paso 2: Crear rama para la actualización
```bash
# Crear y cambiar a nueva rama
git checkout -b feature/grafana-influxdb-v1.3.0

# Verificar que estás en la nueva rama
git branch
```

### Paso 3: Actualizar archivos de documentación

#### 3.1. Reemplazar README.md
```bash
# Hacer backup del README actual
cp README.md README.md.backup

# Reemplazar con el nuevo README.md
# (Copiar el contenido del archivo README.md que te entregué)
```

#### 3.2. Agregar/Actualizar archivos nuevos
```bash
# Copiar CHANGELOG.md
# (Copiar el contenido del archivo CHANGELOG.md que te entregué)

# Copiar GRAFANA_SETUP.md
# (Copiar el contenido del archivo GRAFANA_SETUP.md que te entregué)

# Verificar que .gitignore esté actualizado
# (Ver sección de .gitignore abajo)
```

### Paso 4: Verificar cambios
```bash
# Ver archivos modificados
git status

# Ver diferencias en README.md
git diff README.md

# Ver todos los archivos nuevos/modificados
git diff --stat
```

### Paso 5: Agregar archivos al staging
```bash
# Opción 1: Agregar archivos específicos
git add README.md
git add CHANGELOG.md
git add GRAFANA_SETUP.md
git add grafana/
git add docker-compose.yml
git add .gitignore

# Opción 2: Agregar todos los archivos (cuidado)
git add .

# Verificar staging
git status
```

### Paso 6: Crear commit
```bash
# Commit con mensaje descriptivo
git commit -m "feat: add Grafana + InfluxDB real-time monitoring (v1.3.0)

- Added Grafana 10.2.3 + InfluxDB 2.7 to docker-compose
- Created 9-panel professional dashboard for real-time metrics
- Integrated JMeter Backend Listener with InfluxDB
- Added comprehensive Grafana setup documentation
- Updated README with Grafana/InfluxDB section
- Created detailed CHANGELOG.md
- Data retention: 30 days in InfluxDB
- Auto-refresh dashboard every 5 seconds

New features:
- Response Time Over Time (live)
- Active Threads visualization
- Error Rate gauge with thresholds
- Throughput monitoring
- Percentiles (p90/p95/p99)
- Requests by Transaction pie chart
- Transaction Details table

Breaking changes: None
Migration required: No (auto-provisioned)
"
```

### Paso 7: Push a GitHub
```bash
# Push de la rama feature a GitHub
git push origin feature/grafana-influxdb-v1.3.0

# Si es la primera vez:
git push -u origin feature/grafana-influxdb-v1.3.0
```

### Paso 8: Crear Pull Request en GitHub

1. **Ir a GitHub**: https://github.com/tu-usuario/jmeter-analyzer
2. **Aparecerá banner**: "feature/grafana-influxdb-v1.3.0 had recent pushes"
3. **Click**: "Compare & pull request"
4. **Completar PR**:
   - **Title**: `feat: Add Grafana + InfluxDB real-time monitoring (v1.3.0)`
   - **Description**:
     ```markdown
     ## 🎯 Objetivo
     Agregar monitoreo en tiempo real de pruebas JMeter con Grafana e InfluxDB.

     ## ✨ Cambios principales
     - ✅ Grafana 10.2.3 + InfluxDB 2.7 integrados
     - ✅ Dashboard con 9 paneles profesionales
     - ✅ JMeter Backend Listener configurado
     - ✅ Documentación completa (GRAFANA_SETUP.md)
     - ✅ README actualizado
     - ✅ CHANGELOG.md creado

     ## 📊 Nuevas métricas en tiempo real
     - Response Time Over Time
     - Active Threads
     - Error Rate (gauge con umbrales)
     - Throughput (req/s)
     - Percentiles (p90/p95/p99)
     - Requests by Transaction (pie chart)
     - Transaction Details (tabla)

     ## 🔧 Cambios técnicos
     - Agregados servicios `grafana` e `influxdb` a docker-compose.yml
     - Auto-provisioning de datasource InfluxDB
     - Auto-provisioning de dashboard
     - Volúmenes persistentes para Grafana e InfluxDB
     - Queries Flux corregidas para paneles 8 y 9

     ## 📚 Documentación
     - README.md: Sección completa de Grafana
     - GRAFANA_SETUP.md: Guía paso a paso
     - CHANGELOG.md: Historial de versiones
     - Troubleshooting actualizado

     ## 🧪 Testing
     - ✅ Tested en Windows 11
     - ✅ Tested con JMeter 5.5
     - ✅ Tested con test de 1000 usuarios
     - ✅ Dashboard actualiza cada 5s correctamente

     ## 📋 Checklist
     - [x] Código funcional
     - [x] Documentación actualizada
     - [x] Sin breaking changes
     - [x] Backward compatible
     - [x] Tests pasados
     - [x] Screenshots incluidos (opcional)
     ```
5. **Click**: "Create pull request"
6. **Merge**: Si todo está OK, hacer merge a `main`

### Paso 9: Actualizar rama main local
```bash
# Cambiar a main
git checkout main

# Pull de los cambios mergeados
git pull origin main

# Opcional: Borrar rama feature local
git branch -d feature/grafana-influxdb-v1.3.0
```

### Paso 10: Crear Tag de versión
```bash
# Crear tag v1.3.0
git tag -a v1.3.0 -m "Release v1.3.0: Grafana + InfluxDB Real-Time Monitoring

New Features:
- Grafana 10.2.3 + InfluxDB 2.7 integration
- 9 professional dashboard panels
- JMeter Backend Listener support
- Real-time metrics visualization

Documentation:
- GRAFANA_SETUP.md comprehensive guide
- Updated README.md
- Created CHANGELOG.md

See CHANGELOG.md for full details.
"

# Push del tag
git push origin v1.3.0

# Verificar tag creado
git tag
```

---

## 🔧 OPCIÓN B: Actualización Directa a Main (No recomendado)

Solo usa esta opción si trabajas solo y no necesitas code review.

```bash
# Asegúrate de estar en main
git checkout main

# Actualizar archivos
# (Reemplazar README.md, agregar CHANGELOG.md, etc.)

# Agregar archivos
git add README.md CHANGELOG.md GRAFANA_SETUP.md grafana/ docker-compose.yml .gitignore

# Commit
git commit -m "feat: add Grafana + InfluxDB v1.3.0"

# Push directo a main
git push origin main

# Crear tag
git tag -a v1.3.0 -m "Release v1.3.0"
git push origin v1.3.0
```

---

## 📝 .gitignore Actualizado

Asegúrate de que tu `.gitignore` incluya:

```gitignore
# ============================================
# .gitignore para JMeter Analyzer Pro v1.3.0
# ============================================

# ===== Python Backend =====
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
pip-wheel-metadata/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST
*.log

# ===== Virtual Environments =====
venv/
ENV/
env/
.venv

# ===== Environment Variables =====
.env
.env.local
.env.*.local

# ===== JMeter Uploads =====
backend/uploads/*.jtl
backend/uploads/*.csv
backend/uploads/*.log

# ===== Database =====
*.db
*.sqlite
*.sqlite3
data/postgres/

# ===== Grafana Data =====
data/grafana/

# ===== InfluxDB Data =====
data/influxdb/

# ===== Node / React Frontend =====
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
.pnp/
.pnp.js
coverage/
build/
.DS_Store
.env.local
.env.development.local
.env.test.local
.env.production.local
*.tsbuildinfo

# ===== IDEs =====
.vscode/
.idea/
*.swp
*.swo
*~

# ===== OS =====
.DS_Store
Thumbs.db
desktop.ini

# ===== Docker =====
# NO ignorar docker-compose.yml (necesario)

# ===== Logs =====
*.log
logs/
backend_logs.txt

# ===== Temp/Debug =====
*.tmp
*.temp
charts_debug.json

# ===== Git =====
.git/

# ===== Documentation Backups =====
*.backup
README.md.backup
```

**Aplicar .gitignore**:
```bash
# Guardar .gitignore actualizado
# Agregar al commit
git add .gitignore
git commit -m "chore: update .gitignore for Grafana/InfluxDB"
```

---

## 🧪 Verificación Pre-Push

Antes de hacer push, verifica:

### 1. Archivos críticos incluidos
```bash
# Verificar que estos archivos estén en el commit
git ls-files | grep -E "README|CHANGELOG|GRAFANA_SETUP|docker-compose|grafana/"
```

**Resultado esperado**:
```
README.md
CHANGELOG.md
GRAFANA_SETUP.md
docker-compose.yml
grafana/dashboards/dashboard.yml
grafana/dashboards/jmeter-dashboard.json
grafana/datasources/influxdb.yml
```

### 2. Sin archivos sensibles
```bash
# Verificar que .env NO esté en el commit
git status | grep .env

# Si aparece, removelo:
git reset .env
echo ".env" >> .gitignore
```

### 3. Sin datos de prueba
```bash
# Verificar que no hay JTLs en el commit
git status | grep -E "\.jtl|\.csv"

# Si aparecen, removelos
git reset backend/uploads/*.jtl
```

---

## 🎯 Comandos Rápidos (Cheat Sheet)

```bash
# Ver estado
git status

# Ver diferencias
git diff

# Agregar archivos
git add archivo.txt

# Commit
git commit -m "mensaje"

# Push
git push origin nombre-rama

# Ver historial
git log --oneline

# Ver ramas
git branch

# Cambiar rama
git checkout nombre-rama

# Crear rama
git checkout -b nueva-rama

# Ver remote
git remote -v

# Ver tags
git tag

# Crear tag
git tag -a v1.3.0 -m "mensaje"

# Push tag
git push origin v1.3.0
```

---

## 🐛 Troubleshooting Git

### Problema: "fatal: not a git repository"
```bash
# Estás en el directorio incorrecto
cd C:\tu\proyecto\jmeter-analyzer

# Verificar
git status
```

### Problema: "rejected - non-fast-forward"
```bash
# Alguien más hizo push antes
git pull origin main

# Resolver conflictos si hay
# Luego push
git push origin main
```

### Problema: "Authentication failed"
```bash
# Si usas HTTPS con GitHub
# Necesitas Personal Access Token (no contraseña)

# Generar token:
# GitHub → Settings → Developer settings → Personal access tokens
# → Generate new token → Seleccionar scopes: repo

# Usar token como contraseña al hacer push
```

### Problema: Commit incorrecto
```bash
# Deshacer último commit (mantiene cambios)
git reset --soft HEAD~1

# Editar mensaje del último commit
git commit --amend -m "nuevo mensaje"
```

### Problema: Archivo sensible commiteado
```bash
# Remover del historial (PELIGROSO)
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all

# Forzar push
git push origin --force --all
```

---

## ✅ Checklist Final

Antes de hacer push:

- [ ] README.md actualizado con sección Grafana
- [ ] CHANGELOG.md creado con v1.3.0
- [ ] GRAFANA_SETUP.md agregado
- [ ] .gitignore actualizado
- [ ] docker-compose.yml incluye Grafana e InfluxDB
- [ ] grafana/datasources/influxdb.yml incluido
- [ ] grafana/dashboards/* incluidos
- [ ] .env NO está en el commit
- [ ] Sin archivos .jtl o datos de prueba
- [ ] Commit message descriptivo
- [ ] Branch creada correctamente
- [ ] Tests funcionando localmente
- [ ] Documentación revisada

---

## 📚 Referencias

- **Git Documentation**: https://git-scm.com/doc
- **GitHub Flow**: https://guides.github.com/introduction/flow/
- **Semantic Versioning**: https://semver.org/
- **Conventional Commits**: https://www.conventionalcommits.org/

---

**¡Listo para deployment!** 🚀

Una vez mergeado y taggeado, tu versión v1.3.0 estará disponible en GitHub.
