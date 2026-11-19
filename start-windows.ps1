$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Get-Command py -ErrorAction SilentlyContinue) -and -not (Get-Command python -ErrorAction SilentlyContinue)) {
  throw "Instala Python 3.11+ y marca Add Python to PATH."
}
$python = "python"
if (Get-Command py -ErrorAction SilentlyContinue) { $python = "py" }
if (-not (Test-Path ".venv/Scripts/python.exe")) {
  & $python -m venv .venv
  if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el entorno virtual." }
}
$venv = Join-Path $PSScriptRoot ".venv/Scripts/python.exe"
& $venv -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "No se pudieron instalar las dependencias." }
if (-not (Test-Path ".env")) {
  Write-Host "Primera ejecucion. PostgreSQL debe estar instalado y en marcha."
  $adminDsn = Read-Host "DSN de administrador PostgreSQL (ej.: host=localhost port=5432 dbname=postgres user=postgres password=...)"
  if ([string]::IsNullOrWhiteSpace($adminDsn)) { throw "Falta el DSN." }
  $env:POSTGRES_ADMIN_DSN = $adminDsn
  try {
    & $venv setup_windows.py
    if ($LASTEXITCODE -ne 0) { throw "Inicializacion fallida; revisa la base antes de reintentar." }
  } finally { Remove-Item Env:POSTGRES_ADMIN_DSN -ErrorAction SilentlyContinue }
}
Write-Host "Abre http://127.0.0.1:5084 ; Ctrl+C para detener la aplicacion."
& $venv app.py
exit $LASTEXITCODE
