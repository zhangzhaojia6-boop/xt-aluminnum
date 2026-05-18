$ErrorActionPreference = "Stop"

$BackendDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$RepoDir = Split-Path -Parent $BackendDir
$DbDir = Join-Path $RepoDir ".tmp\e2e"
$DbPath = Join-Path $DbDir "e2e.sqlite3"

New-Item -ItemType Directory -Force -Path $DbDir | Out-Null
Remove-Item -LiteralPath $DbPath -Force -ErrorAction SilentlyContinue

$env:APP_ENV = "e2e"
$env:DATABASE_URL = "sqlite:///$($DbPath.Replace('\', '/'))"
$env:SECRET_KEY = "e2e-secret-key-change-before-production-2026"
$env:INIT_ADMIN_USERNAME = $env:PLAYWRIGHT_USERNAME
$env:INIT_ADMIN_PASSWORD = $env:PLAYWRIGHT_PASSWORD
$env:INIT_ADMIN_NAME = "E2E Admin"
$env:CORS_ORIGINS = "http://localhost:4173,http://127.0.0.1:4173"
$env:PRODUCTION_CORS_ORIGINS = $env:CORS_ORIGINS
$env:MES_ADAPTER = "null"
$env:DINGTALK_ENABLED = "false"
$env:WORKFLOW_ENABLED = "false"
$env:LLM_ENABLED = "false"

if ([string]::IsNullOrWhiteSpace($env:INIT_ADMIN_USERNAME)) {
  $env:INIT_ADMIN_USERNAME = "admin"
}

if ([string]::IsNullOrWhiteSpace($env:INIT_ADMIN_PASSWORD)) {
  $env:INIT_ADMIN_PASSWORD = "E2eAdmin#2026"
}

Push-Location $BackendDir
try {
  python -m alembic upgrade head
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
} finally {
  Pop-Location
}
