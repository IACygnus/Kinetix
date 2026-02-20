# ===============================================
# SCRIPT DE DEPLOYMENT v1.3.0
# JMeter Analyzer Pro - Grafana + InfluxDB
# ===============================================

$ErrorActionPreference = "Stop"

# Colores
$Green = "Green"
$Red = "Red"
$Cyan = "Cyan"
$Yellow = "Yellow"

Write-Host "======================================================" -ForegroundColor $Cyan
Write-Host "  DEPLOYMENT v1.3.0 - GRAFANA + INFLUXDB" -ForegroundColor $Cyan
Write-Host "  JMeter Analyzer Pro" -ForegroundColor $Cyan
Write-Host "======================================================" -ForegroundColor $Cyan
Write-Host ""

# ===============================================
# PASO 1: VERIFICACIONES PRE-DEPLOYMENT
# ===============================================

Write-Host "[1/8] Verificaciones pre-deployment..." -ForegroundColor $Cyan

# Verificar Git instalado
try {
    $gitVersion = git --version
    Write-Host "✓ Git instalado: $gitVersion" -ForegroundColor $Green
} catch {
    Write-Host "✗ Git no está instalado" -ForegroundColor $Red
    Write-Host "  Instala Git desde: https://git-scm.com/downloads" -ForegroundColor $Yellow
    exit 1
}

# Verificar que estamos en un repo Git
if (-not (Test-Path ".git")) {
    Write-Host "✗ No estás en un repositorio Git" -ForegroundColor $Red
    Write-Host "  Ejecuta este script desde el directorio raíz del proyecto" -ForegroundColor $Yellow
    exit 1
}

Write-Host "✓ Repositorio Git detectado" -ForegroundColor $Green

# Verificar rama actual
$currentBranch = git rev-parse --abbrev-ref HEAD
Write-Host "  Rama actual: $currentBranch" -ForegroundColor $Cyan

# Verificar archivos críticos
$criticalFiles = @(
    "README.md",
    "docker-compose.yml",
    "grafana/datasources/influxdb.yml",
    "grafana/dashboards/jmeter-dashboard.json"
)

foreach ($file in $criticalFiles) {
    if (Test-Path $file) {
        Write-Host "✓ $file existe" -ForegroundColor $Green
    } else {
        Write-Host "✗ $file NO encontrado" -ForegroundColor $Red
        exit 1
    }
}

Write-Host ""

# ===============================================
# PASO 2: CREAR BRANCH FEATURE
# ===============================================

Write-Host "[2/8] Crear branch feature..." -ForegroundColor $Cyan

$branchName = "feature/grafana-influxdb-v1.3.0"

# Verificar si branch ya existe
$branchExists = git branch --list $branchName

if ($branchExists) {
    Write-Host "⚠ Branch $branchName ya existe" -ForegroundColor $Yellow
    $response = Read-Host "¿Quieres usarla? (s/n)"
    if ($response -ne "s") {
        Write-Host "Deployment cancelado" -ForegroundColor $Yellow
        exit 0
    }
    git checkout $branchName
} else {
    git checkout -b $branchName
    Write-Host "✓ Branch creada: $branchName" -ForegroundColor $Green
}

Write-Host ""

# ===============================================
# PASO 3: VERIFICAR ARCHIVOS A COMMITEAR
# ===============================================

Write-Host "[3/8] Verificar archivos a commitear..." -ForegroundColor $Cyan

# Verificar que .env NO esté staged
$envStaged = git diff --cached --name-only | Select-String ".env"
if ($envStaged) {
    Write-Host "✗ ALERTA: .env está en staging" -ForegroundColor $Red
    Write-Host "  Removiendo .env del staging..." -ForegroundColor $Yellow
    git reset .env
}

# Verificar que no haya archivos .jtl
$jtlFiles = git status --short | Select-String "\.jtl|\.csv"
if ($jtlFiles) {
    Write-Host "⚠ Archivos JTL detectados" -ForegroundColor $Yellow
    Write-Host "  Estos archivos NO deben commitearse" -ForegroundColor $Yellow
    git status --short | Select-String "\.jtl|\.csv"
}

# Mostrar archivos modificados
Write-Host ""
Write-Host "Archivos modificados:" -ForegroundColor $Cyan
git status --short

Write-Host ""

# ===============================================
# PASO 4: AGREGAR ARCHIVOS AL STAGING
# ===============================================

Write-Host "[4/8] Agregar archivos al staging..." -ForegroundColor $Cyan

$response = Read-Host "¿Agregar archivos específicos (e) o todos los archivos (t)? (e/t)"

if ($response -eq "e") {
    Write-Host ""
    Write-Host "Agrega archivos manualmente con:" -ForegroundColor $Yellow
    Write-Host "  git add README.md" -ForegroundColor $Cyan
    Write-Host "  git add CHANGELOG.md" -ForegroundColor $Cyan
    Write-Host "  git add GRAFANA_SETUP.md" -ForegroundColor $Cyan
    Write-Host "  git add grafana/" -ForegroundColor $Cyan
    Write-Host ""
    Write-Host "Luego ejecuta de nuevo este script" -ForegroundColor $Yellow
    exit 0
} else {
    # Agregar archivos específicos (más seguro que git add .)
    $filesToAdd = @(
        "README.md",
        "CHANGELOG.md",
        "GRAFANA_SETUP.md",
        "GIT_DEPLOYMENT.md",
        ".gitignore",
        "grafana/",
        "docker-compose.yml"
    )
    
    foreach ($file in $filesToAdd) {
        if (Test-Path $file) {
            git add $file
            Write-Host "✓ Agregado: $file" -ForegroundColor $Green
        }
    }
}

Write-Host ""

# ===============================================
# PASO 5: CREAR COMMIT
# ===============================================

Write-Host "[5/8] Crear commit..." -ForegroundColor $Cyan

$commitMessage = @"
feat: add Grafana + InfluxDB real-time monitoring (v1.3.0)

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
"@

git commit -m $commitMessage

Write-Host "✓ Commit creado" -ForegroundColor $Green
Write-Host ""

# ===============================================
# PASO 6: PUSH A GITHUB
# ===============================================

Write-Host "[6/8] Push a GitHub..." -ForegroundColor $Cyan

$response = Read-Host "¿Hacer push a GitHub? (s/n)"

if ($response -eq "s") {
    try {
        git push -u origin $branchName
        Write-Host "✓ Push exitoso" -ForegroundColor $Green
    } catch {
        Write-Host "✗ Error en push" -ForegroundColor $Red
        Write-Host "  Verifica tu conexión y credenciales" -ForegroundColor $Yellow
        exit 1
    }
} else {
    Write-Host "⚠ Push omitido" -ForegroundColor $Yellow
    Write-Host "  Recuerda hacer push manualmente:" -ForegroundColor $Yellow
    Write-Host "  git push -u origin $branchName" -ForegroundColor $Cyan
}

Write-Host ""

# ===============================================
# PASO 7: INSTRUCCIONES PULL REQUEST
# ===============================================

Write-Host "[7/8] Siguiente paso: Pull Request" -ForegroundColor $Cyan
Write-Host ""
Write-Host "1. Ve a GitHub:" -ForegroundColor $Yellow
Write-Host "   https://github.com/tu-usuario/jmeter-analyzer" -ForegroundColor $Cyan
Write-Host ""
Write-Host "2. Verás un banner:" -ForegroundColor $Yellow
Write-Host "   '$branchName had recent pushes'" -ForegroundColor $Cyan
Write-Host ""
Write-Host "3. Click en 'Compare & pull request'" -ForegroundColor $Yellow
Write-Host ""
Write-Host "4. Completar PR:" -ForegroundColor $Yellow
Write-Host "   Title: feat: Add Grafana + InfluxDB v1.3.0" -ForegroundColor $Cyan
Write-Host "   Description: Ver GIT_DEPLOYMENT.md para template" -ForegroundColor $Cyan
Write-Host ""
Write-Host "5. Click 'Create pull request'" -ForegroundColor $Yellow
Write-Host ""
Write-Host "6. Merge cuando esté aprobado" -ForegroundColor $Yellow
Write-Host ""

# ===============================================
# PASO 8: INSTRUCCIONES POST-MERGE
# ===============================================

Write-Host "[8/8] Post-merge (ejecutar DESPUÉS de merge):" -ForegroundColor $Cyan
Write-Host ""
Write-Host "# Cambiar a main" -ForegroundColor $Yellow
Write-Host "git checkout main" -ForegroundColor $Cyan
Write-Host ""
Write-Host "# Pull cambios" -ForegroundColor $Yellow
Write-Host "git pull origin main" -ForegroundColor $Cyan
Write-Host ""
Write-Host "# Crear tag v1.3.0" -ForegroundColor $Yellow
Write-Host "git tag -a v1.3.0 -m 'Release v1.3.0: Grafana + InfluxDB'" -ForegroundColor $Cyan
Write-Host ""
Write-Host "# Push tag" -ForegroundColor $Yellow
Write-Host "git push origin v1.3.0" -ForegroundColor $Cyan
Write-Host ""
Write-Host "# Borrar branch feature (opcional)" -ForegroundColor $Yellow
Write-Host "git branch -d $branchName" -ForegroundColor $Cyan
Write-Host ""

# ===============================================
# RESUMEN FINAL
# ===============================================

Write-Host "======================================================" -ForegroundColor $Cyan
Write-Host "  DEPLOYMENT PREPARADO ✅" -ForegroundColor $Green
Write-Host "======================================================" -ForegroundColor $Cyan
Write-Host ""
Write-Host "Branch creada: $branchName" -ForegroundColor $Cyan
Write-Host "Commit creado: feat: add Grafana + InfluxDB v1.3.0" -ForegroundColor $Cyan
Write-Host ""
Write-Host "📋 Próximos pasos:" -ForegroundColor $Yellow
Write-Host "1. Ir a GitHub y crear Pull Request" -ForegroundColor $Cyan
Write-Host "2. Merge PR cuando esté aprobado" -ForegroundColor $Cyan
Write-Host "3. Crear tag v1.3.0 en main" -ForegroundColor $Cyan
Write-Host ""
Write-Host "📚 Documentación creada:" -ForegroundColor $Yellow
Write-Host "- README.md (actualizado)" -ForegroundColor $Cyan
Write-Host "- CHANGELOG.md (nuevo)" -ForegroundColor $Cyan
Write-Host "- GRAFANA_SETUP.md (nuevo)" -ForegroundColor $Cyan
Write-Host "- GIT_DEPLOYMENT.md (nuevo)" -ForegroundColor $Cyan
Write-Host ""
Write-Host "======================================================" -ForegroundColor $Cyan
Write-Host "Presiona cualquier tecla para cerrar..." -ForegroundColor $Cyan
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
