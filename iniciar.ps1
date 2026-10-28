$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$runtime = Join-Path $projectRoot '.venv\Scripts\python.exe'
$frontendRoot = Join-Path $projectRoot 'frontend'
$logRoot = Join-Path $projectRoot 'tmp'
$pidFile = Join-Path $logRoot 'servicios.json'
if (-not (Test-Path -LiteralPath $runtime)) { throw 'Instala las dependencias siguiendo README.md.' }
if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot 'node_modules'))) { throw 'Ejecuta npm ci dentro de frontend.' }
if (Test-Path -LiteralPath $pidFile) { throw 'Ya existe un registro de servicios. Usa detener.ps1 antes de reiniciar.' }
if (Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in 8000,4200 }) {
    throw 'Los puertos 8000 o 4200 están ocupados. Detén los servidores anteriores antes de iniciar.'
}
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
Push-Location $projectRoot
try {
    # cmd evita que la salida normal de docker (en stderr) detenga el script con ErrorActionPreference=Stop
    cmd /c "docker compose up -d postgres 2>&1" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'No se pudieron iniciar los servicios de Docker.' }
    $backendProcess = Start-Process -FilePath $runtime -ArgumentList @('-u','-X','utf8','run.py') `
        -WorkingDirectory (Join-Path $projectRoot 'backend') -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logRoot 'backend.log') -RedirectStandardError (Join-Path $logRoot 'backend-error.log')
    $nodeRuntime = (Get-Command node -ErrorAction Stop).Source
    $frontendProcess = Start-Process -FilePath $nodeRuntime `
        -ArgumentList @('node_modules/@angular/cli/bin/ng.js','serve','--host','127.0.0.1','--proxy-config','proxy.conf.json') `
        -WorkingDirectory $frontendRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logRoot 'frontend.log') -RedirectStandardError (Join-Path $logRoot 'frontend-error.log')
    @($backendProcess,$frontendProcess) | ForEach-Object {
        @{id=$_.Id; inicio=$_.StartTime.ToUniversalTime().ToString('o'); ruta=$_.Path}
    } | ConvertTo-Json | Set-Content -LiteralPath $pidFile -Encoding utf8
    Write-Host 'Iniciando Trama: http://127.0.0.1:4200'
    Write-Host 'Los registros de arranque están en tmp/. Para detener: .\detener.ps1'
} finally { Pop-Location }
