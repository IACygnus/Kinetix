<#
    ===========================================================================
    INSTALADOR DEL AGENTE KINETIX — Windows (O-D20)
    ===========================================================================

    *** O-D21: ESCRITO PERO NO PROBADO ***

    El laboratorio de la etapa O2b es Linux. Este guion se ha escrito con el
    mismo diseno que el de Linux y se ha comprobado que **analiza sin errores**
    de sintaxis, pero **no se ha ejecutado contra un Windows Server**. Hasta que
    eso ocurra, no se le entrega a un cliente como algo probado. Esta declarado
    asi en el reporte de la etapa y en docs/observabilidad/requisitos-con-agente.md.

    Uso (PowerShell como administrador):

        .\instalar_agente.ps1 -Url http://kinetix:8086 -TokenFichero C:\tok.txt `
                              -Org performance -Cubo infra -Cliente acme

    Instala Telegraf 1.29.5 como servicio de Windows `KinetixAgente`, corriendo
    con la cuenta virtual `NT SERVICE\KinetixAgente`, que no es administrador y
    no tiene sesion interactiva (el equivalente de O-D19 en Windows).

    Todo lo que toca:
        C:\Program Files\KinetixAgente        el programa
        C:\ProgramData\KinetixAgente          la configuracion y el token
        el servicio KinetixAgente
    Y el desinstalador quita las tres cosas.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Url,
    [string]$Token,
    [string]$TokenFichero,
    [Parameter(Mandatory = $true)][string]$Org,
    [Parameter(Mandatory = $true)][string]$Cubo,
    [Parameter(Mandatory = $true)][string]$Cliente,
    [string]$NombreHost = $env:COMPUTERNAME,
    [string]$Paquete,
    [string]$Corrida = 'sin-corrida'
)

$ErrorActionPreference = 'Stop'

$Version    = '1.29.5'
# Igual que en Linux: suma calculada por nosotros sobre la descarga oficial.
# InfluxData no publica un fichero de suma al lado del paquete. Si su politica
# exige procedencia firmada por el fabricante, diganoslo.
$Suma       = 'A_CALCULAR_CUANDO_SE_PRUEBE_EN_WINDOWS'
$Origen     = "https://dl.influxdata.com/telegraf/releases/telegraf-$Version`_windows_amd64.zip"
$DirPrograma = 'C:\Program Files\KinetixAgente'
$DirConfig   = 'C:\ProgramData\KinetixAgente'
$Servicio    = 'KinetixAgente'
$Aqui        = Split-Path -Parent $MyInvocation.MyCommand.Path

# --- El token, del fichero o del parametro ---------------------------------
if ($TokenFichero) {
    # Preferido: asi el token no queda en la linea de ordenes, donde lo ve
    # cualquiera que mire los procesos.
    $Token = (Get-Content -Raw -Path $TokenFichero).Trim()
}
if (-not $Token) { throw 'Falta -Token o -TokenFichero' }

# --- Hay que ser administrador para instalar un servicio -------------------
$identidad = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identidad)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Hay que ejecutar PowerShell como administrador para instalar un servicio.'
}

Write-Host '== 1. El programa (Telegraf' $Version ')'
New-Item -ItemType Directory -Force -Path $DirPrograma | Out-Null
$temporal = Join-Path $env:TEMP ('kinetix-agente-' + [guid]::NewGuid())
New-Item -ItemType Directory -Force -Path $temporal | Out-Null
try {
    $zip = Join-Path $temporal 'telegraf.zip'
    if ($Paquete) {
        Write-Host "   del paquete local: $Paquete"
        Copy-Item -Path $Paquete -Destination $zip
    } else {
        Write-Host "   descargando de $Origen"
        Invoke-WebRequest -Uri $Origen -OutFile $zip -UseBasicParsing
    }

    $obtenida = (Get-FileHash -Path $zip -Algorithm SHA256).Hash.ToLower()
    if ($Suma -eq 'A_CALCULAR_CUANDO_SE_PRUEBE_EN_WINDOWS') {
        Write-Warning ("La suma del paquete de Windows aun no esta fijada (O-D21). " +
                       "La del paquete descargado es: $obtenida")
        Write-Warning 'Fijela en este guion antes de usarlo en un servidor de un cliente.'
    } elseif ($obtenida -ne $Suma.ToLower()) {
        throw "La suma NO coincide. Esperada: $Suma  Obtenida: $obtenida"
    } else {
        Write-Host '   suma verificada'
    }

    Expand-Archive -Path $zip -DestinationPath $temporal -Force
    $binario = Get-ChildItem -Path $temporal -Recurse -Filter 'telegraf.exe' |
               Select-Object -First 1
    if (-not $binario) { throw 'No encuentro telegraf.exe dentro del paquete' }
    Copy-Item -Path $binario.FullName -Destination (Join-Path $DirPrograma 'telegraf.exe') -Force
} finally {
    Remove-Item -Recurse -Force $temporal -ErrorAction SilentlyContinue
}

Write-Host '== 2. La configuracion'
New-Item -ItemType Directory -Force -Path (Join-Path $DirConfig 'conf.d') | Out-Null
Copy-Item -Path (Join-Path $Aqui 'agente.conf') `
          -Destination (Join-Path $DirConfig 'agente.conf') -Force

# En Windows el servicio no lee un EnvironmentFile: las variables van en el
# registro, bajo la propia clave del servicio.
@"
[global_tags]
  corrida = "$Corrida"
"@ | Set-Content -Path (Join-Path $DirConfig 'conf.d\00-corrida.conf') -Encoding UTF8

Write-Host '== 3. El servicio'
$rutaExe = Join-Path $DirPrograma 'telegraf.exe'
$argumentos = "--config `"$DirConfig\agente.conf`" --config-directory `"$DirConfig\conf.d`" --service-name $Servicio"

if (Get-Service -Name $Servicio -ErrorAction SilentlyContinue) {
    Write-Host '   ya existia; se para y se vuelve a crear'
    Stop-Service -Name $Servicio -Force -ErrorAction SilentlyContinue
    & sc.exe delete $Servicio | Out-Null
    Start-Sleep -Seconds 2
}

# Telegraf sabe registrarse solo como servicio de Windows.
& $rutaExe --config "$DirConfig\agente.conf" --config-directory "$DirConfig\conf.d" `
           --service install --service-name $Servicio | Out-Null

# Las variables de entorno del servicio, en el registro. El token va aqui y no
# en la linea de ordenes, que la ve cualquiera.
$clave = "HKLM:\SYSTEM\CurrentControlSet\Services\$Servicio"
$entorno = @(
    "KX_HOST=$NombreHost",
    "KX_CLIENTE=$Cliente",
    "KX_INFLUX_URL=$Url",
    "KX_INFLUX_ORG=$Org",
    "KX_INFLUX_BUCKET=$Cubo",
    "KX_INFLUX_TOKEN=$Token"
)
New-ItemProperty -Path $clave -Name 'Environment' -PropertyType MultiString `
                 -Value $entorno -Force | Out-Null

# O-D19 en Windows: cuenta virtual del servicio, sin privilegios de
# administrador y sin sesion interactiva.
& sc.exe config $Servicio obj= "NT SERVICE\$Servicio" | Out-Null
& sc.exe failure $Servicio reset= 86400 actions= restart/5000/restart/5000/restart/5000 | Out-Null

# Que solo el sistema y los administradores puedan leer el token.
$acl = Get-Acl $DirConfig
$acl.SetAccessRuleProtection($true, $false)
$acl.Access | ForEach-Object { $acl.RemoveAccessRule($_) | Out-Null }
foreach ($quien in @('NT AUTHORITY\SYSTEM', 'BUILTIN\Administrators', "NT SERVICE\$Servicio")) {
    $regla = New-Object Security.AccessControl.FileSystemAccessRule(
        $quien, 'ReadAndExecute', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
    $acl.AddAccessRule($regla)
}
Set-Acl -Path $DirConfig -AclObject $acl

Start-Service -Name $Servicio
Start-Sleep -Seconds 3
$estado = (Get-Service -Name $Servicio).Status
if ($estado -ne 'Running') {
    throw "El servicio no arranco. Estado: $estado"
}

Write-Host ''
Write-Host 'Agente Kinetix instalado.'
Write-Host "  servicio   $Servicio  ($estado)"
Write-Host "  cuenta     NT SERVICE\$Servicio  (no es administrador)"
Write-Host "  host       $NombreHost"
Write-Host "  cliente    $Cliente"
Write-Host "  corrida    $Corrida"
Write-Host "  destino    $Url  cubo $Cubo"
Write-Host ''
Write-Warning 'O-D21: este instalador NO se ha probado en un Windows Server.'
