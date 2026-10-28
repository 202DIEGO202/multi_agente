# Verificación completa de Trama: calidad del código, pruebas y servicios en ejecución.
# Uso (desde la carpeta raíz):  .\verificar.ps1
# No modifica datos: las pruebas de integración usan la base aislada fabrica_test.

$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$results = @()

function Add-Result($name, $ok, $detail) {
    $script:results += [pscustomobject]@{ Comprobacion = $name; Resultado = $(if ($ok) { 'OK' } else { 'FALLA' }); Detalle = $detail }
    $color = if ($ok) { 'Green' } else { 'Red' }
    Write-Host ("[{0}] {1} - {2}" -f $(if ($ok) { 'OK' } else { 'FALLA' }), $name, $detail) -ForegroundColor $color
}

function Test-Url($url) {
    try { return (Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 10).StatusCode } catch { return 0 }
}

Write-Host "`n== 1. Docker y base de datos" -ForegroundColor Cyan
$pg = cmd /c "docker ps --format {{.Names}} 2>&1" | Select-String 'fabrica-fase1-postgres-1'
Add-Result 'PostgreSQL en Docker' ([bool]$pg) $(if ($pg) { 'contenedor en ejecución' } else { 'abra Docker Desktop y ejecute .\iniciar.ps1' })

Write-Host "`n== 2. Calidad del código (ruff)" -ForegroundColor Cyan
$lint = & $python -m ruff check (Join-Path $root 'backend\app') (Join-Path $root 'backend\tests') 2>&1 | Out-String
Add-Result 'Lint del backend' ($LASTEXITCODE -eq 0) ($lint.Trim().Split("`n")[-1])

Write-Host "`n== 3. Pruebas del backend (incluye integración con base aislada)" -ForegroundColor Cyan
$envLine = Get-Content (Join-Path $root '.env') | Where-Object { $_ -match '^DATABASE_URL=' } | Select-Object -First 1
if ($envLine) {
    $testUrl = ($envLine -replace '^DATABASE_URL=', '') -replace '/fabrica(\?|$)', '/fabrica_test$1'
    $exists = cmd /c "docker exec fabrica-fase1-postgres-1 psql -U fabrica -d fabrica -At -c ""select 1 from pg_database where datname='fabrica_test'"" 2>&1"
    if ($exists -notmatch '1') { cmd /c "docker exec fabrica-fase1-postgres-1 psql -U fabrica -d fabrica -c ""CREATE DATABASE fabrica_test"" 2>&1" | Out-Null }
    $env:TEST_DATABASE_URL = $testUrl
}
Push-Location (Join-Path $root 'backend')
$tests = & $python -m pytest -q -p no:cacheprovider --ignore=tests/test_live.py --ignore=tests/test_backlog_live.py 2>&1 | Out-String
$testsOk = $LASTEXITCODE -eq 0
Pop-Location
$summary = ($tests.Trim().Split("`n") | Where-Object { $_ -match 'passed|failed|error' } | Select-Object -Last 1)
Add-Result 'Pruebas del backend' $testsOk $summary
if ($summary -match 'skipped') { Add-Result 'Pruebas omitidas' $false 'hay pruebas omitidas: revise TEST_DATABASE_URL' }

Write-Host "`n== 4. Frontend (compilación y pruebas)" -ForegroundColor Cyan
Push-Location (Join-Path $root 'frontend')
$build = cmd /c "npx ng build 2>&1" | Out-String
Add-Result 'Compilación de Angular' ($build -match 'Application bundle generation complete') $(if ($build -match 'error') { 'hay errores de compilación' } else { 'compila sin errores' })
$front = cmd /c "npm test 2>&1" | Out-String
Add-Result 'Pruebas del frontend' ($front -match 'fail 0') (($front.Split("`n") | Where-Object { $_ -match 'pass \d' }) -join '').Trim()
Pop-Location

Write-Host "`n== 5. Plataforma en ejecución" -ForegroundColor Cyan
$api = Test-Url 'http://127.0.0.1:8000/api/health'
Add-Result 'Backend de Trama (8000)' ($api -eq 200) $(if ($api -eq 200) { 'responde' } else { 'no responde: ejecute .\iniciar.ps1' })
$ui = Test-Url 'http://127.0.0.1:4200'
Add-Result 'Interfaz de Trama (4200)' ($ui -eq 200) $(if ($ui -eq 200) { 'http://127.0.0.1:4200' } else { 'no responde: ejecute .\iniciar.ps1' })

Write-Host "`n== 6. Aplicaciones generadas desplegadas (instancias locales)" -ForegroundColor Cyan
$instances = Get-ChildItem (Join-Path $root 'infraestructura-local\instancias') -Directory -ErrorAction SilentlyContinue
if (-not $instances) { Write-Host 'No hay instancias desplegadas (opcional).' }
foreach ($instance in $instances) {
    $envFile = Join-Path $instance.FullName '.env'
    if (-not (Test-Path $envFile)) { continue }
    $vars = @{}
    Get-Content $envFile | ForEach-Object { if ($_ -match '^([^=]+)=(.*)$') { $vars[$matches[1]] = $matches[2] } }
    foreach ($app in @('PORTAL_PORT', 'PANEL_PORT')) {
        if ($vars[$app]) {
            $code = Test-Url ("http://127.0.0.1:{0}/" -f $vars[$app])
            Add-Result ("{0} · {1}" -f $instance.Name, $app.Replace('_PORT', '').ToLower()) ($code -eq 200) ("http://localhost:{0} → {1}" -f $vars[$app], $(if ($code) { $code } else { 'sin respuesta (instancia detenida)' }))
        }
    }
}

$failed = @($results | Where-Object { $_.Resultado -eq 'FALLA' }).Count
Write-Host ""
$results | Format-Table -AutoSize
if ($failed -eq 0) { Write-Host 'Todo correcto.' -ForegroundColor Green } else { Write-Host "$failed comprobaciones fallaron. Revise el detalle." -ForegroundColor Red }
