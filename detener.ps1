$ErrorActionPreference = 'Stop'
$pidFile = Join-Path $PSScriptRoot 'tmp\servicios.json'
if (-not (Test-Path -LiteralPath $pidFile)) { Write-Host 'No hay servicios registrados por iniciar.ps1.'; return }
$records = Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json
foreach ($record in $records) {
    $serviceProcess = Get-Process -Id $record.id -ErrorAction SilentlyContinue
    $recordedStart = ([datetime]$record.inicio).ToUniversalTime()
    if ($serviceProcess -and $serviceProcess.Path -eq $record.ruta -and
        $serviceProcess.StartTime.ToUniversalTime().Ticks -eq $recordedStart.Ticks) {
        taskkill.exe /PID $serviceProcess.Id /T /F | Out-Null
    }
}
Remove-Item -LiteralPath $pidFile
Write-Host 'Servidores de Trama detenidos. PostgreSQL conserva sus datos en Docker.'
