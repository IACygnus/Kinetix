<#
    ===========================================================================
    DESINSTALADOR DEL AGENTE KINETIX — Windows (O-D20)
    ===========================================================================

    *** O-D21: ESCRITO PERO NO PROBADO ***  (ver instalar_agente.ps1)

        .\desinstalar_agente.ps1

    Deja el servidor como estaba: ni servicio, ni archivos, ni procesos. Y no lo
    dice: lo comprueba una por una al final y falla si algo sobrevivio.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Continue'

$DirPrograma = 'C:\Program Files\KinetixAgente'
$DirConfig   = 'C:\ProgramData\KinetixAgente'
$Servicio    = 'KinetixAgente'

$identidad = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identidad)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Hay que ejecutar PowerShell como administrador.'
}

Write-Host '== 1. Parar el servicio'
if (Get-Service -Name $Servicio -ErrorAction SilentlyContinue) {
    Stop-Service -Name $Servicio -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    $exe = Join-Path $DirPrograma 'telegraf.exe'
    if (Test-Path $exe) {
        & $exe --service uninstall --service-name $Servicio 2>$null | Out-Null
    }
    & sc.exe delete $Servicio 2>$null | Out-Null
    Start-Sleep -Seconds 2
    Write-Host '   servicio parado y eliminado'
} else {
    Write-Host '   el servicio ya no estaba'
}

Write-Host '== 2. Terminar cualquier proceso suelto'
Get-Process -Name 'telegraf' -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -and $_.Path.StartsWith($DirPrograma) } |
    ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }

Write-Host '== 3. Quitar los archivos'
foreach ($ruta in @($DirPrograma, $DirConfig)) {
    if (Test-Path $ruta) {
        Remove-Item -Recurse -Force $ruta -ErrorAction SilentlyContinue
    }
}
Write-Host '   quitados el programa y la configuracion (con el token dentro)'

Write-Host ''
Write-Host '== 4. Comprobacion: ¿queda algo?'
$restos = 0
function Comprobar([string]$que, [scriptblock]$sigueAhi) {
    if (& $sigueAhi) {
        Write-Host "FALLA | queda: $que"
        $script:restos++
    } else {
        Write-Host "PASA  | no queda: $que"
    }
}
Comprobar 'el servicio'                 { [bool](Get-Service -Name $Servicio -ErrorAction SilentlyContinue) }
Comprobar 'el directorio del programa'  { Test-Path $DirPrograma }
Comprobar 'el directorio de config'     { Test-Path $DirConfig }
Comprobar 'la clave del registro'       { Test-Path "HKLM:\SYSTEM\CurrentControlSet\Services\$Servicio" }
Comprobar 'algun proceso del agente'    {
    [bool](Get-Process -Name 'telegraf' -ErrorAction SilentlyContinue |
           Where-Object { $_.Path -and $_.Path.StartsWith($DirPrograma) })
}

Write-Host ''
if ($restos -gt 0) {
    Write-Host "QUEDAN $restos RESTOS. El servidor NO esta como estaba."
    exit 1
}
Write-Host 'El agente Kinetix se ha ido del todo. El servidor esta como estaba.'
Write-Warning 'O-D21: este desinstalador NO se ha probado en un Windows Server.'
