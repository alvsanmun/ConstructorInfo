# Lanza una revision del agente EN LOCAL.
# La ejecucion diaria de verdad la hace GitHub Actions
# (.github/workflows/vigilancia.yml); esto es solo para probar o depurar.
#
#   .\revisar.ps1 -SinAviso        prueba, sin enviar Telegram
#   .\revisar.ps1                  revision normal (lee el token de .env)
#   .\revisar.ps1 -Solo bekinsa    una sola promotora
#
# Trabaja contra data/estado.db, NO contra estado/estado.json, para no pisarle
# la memoria a Actions.
param(
    [switch]$SinAviso,
    [switch]$Init,
    [string]$Solo
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $raiz ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Error "No encuentro el entorno virtual. Ejecuta primero:  python -m venv .venv"
    exit 1
}

$argumentos = @("-m", "constructoras.cli")
if ($SinAviso) { $argumentos += "--sin-aviso" }
if ($Init)     { $argumentos += "--init" }
if ($Solo)     { $argumentos += @("--solo", $Solo) }

$logDir = Join-Path $raiz "data"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("revision-" + (Get-Date -Format "yyyyMMdd") + ".log")

# El log lo escribe Python: en PowerShell 5.1 redirigir la salida de un .exe
# envuelve cada linea en un ErrorRecord y ademas marca la ejecucion como fallida.
$argumentos += @("--log", $log)

Set-Location $raiz
& $python @argumentos
$codigo = $LASTEXITCODE

# Conserva solo los ultimos 30 informes y 30 logs
Get-ChildItem (Join-Path $raiz "reports") -Filter "informe-*.html" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -Skip 30 |
    Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem $logDir -Filter "revision-*.log" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -Skip 30 |
    Remove-Item -Force -ErrorAction SilentlyContinue

exit $codigo
