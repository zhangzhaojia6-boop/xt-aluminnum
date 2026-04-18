param(
  [Parameter(Mandatory = $true)]
  [string]$BackupFile,
  [string[]]$ComposeFiles = @('docker-compose.yml'),
  [string]$ServiceName = 'db',
  [string]$TargetDatabase = 'aluminum_bypass_restore_check'
)

if ($TargetDatabase -notmatch '^[A-Za-z0-9_]+$') {
  throw 'TargetDatabase may only contain letters, digits, and underscores.'
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $repoRoot

$backupPath = Resolve-Path $BackupFile
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$containerFile = "/tmp/postgres-restore-$timestamp.dump"

$normalizedComposeFiles = @()
foreach ($entry in $ComposeFiles) {
  foreach ($file in ($entry -split ',')) {
    if ($file.Trim()) {
      $normalizedComposeFiles += $file.Trim()
    }
  }
}

$composeArgs = @()
foreach ($file in $normalizedComposeFiles) {
  $composeArgs += '-f'
  $composeArgs += $file
}

$containerId = (docker compose @composeArgs ps -q $ServiceName).Trim()
if (-not $containerId) {
  throw "Cannot find running container for service '$ServiceName'"
}

$postgresUser = (docker compose @composeArgs exec -T $ServiceName printenv POSTGRES_USER).Trim()
if (-not $postgresUser) {
  throw 'Unable to read POSTGRES_USER from running database container'
}

docker cp $backupPath "${containerId}:$containerFile"
if ($LASTEXITCODE -ne 0) {
  throw 'docker cp failed while copying backup file into container'
}

$dropSql = "DROP DATABASE IF EXISTS $TargetDatabase WITH (FORCE);"
$createSql = "CREATE DATABASE $TargetDatabase;"

docker compose @composeArgs exec -T $ServiceName psql -U $postgresUser -d postgres -c $dropSql
if ($LASTEXITCODE -ne 0) {
  throw 'drop database failed'
}

docker compose @composeArgs exec -T $ServiceName psql -U $postgresUser -d postgres -c $createSql
if ($LASTEXITCODE -ne 0) {
  throw 'create database failed'
}

docker compose @composeArgs exec -T $ServiceName pg_restore -U $postgresUser -d $TargetDatabase --no-owner --no-privileges $containerFile
if ($LASTEXITCODE -ne 0) {
  throw 'pg_restore failed'
}

$tableCount = docker compose @composeArgs exec -T $ServiceName psql -U $postgresUser -d $TargetDatabase -t -A -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';"
if ($LASTEXITCODE -ne 0) {
  throw 'restore verification query failed'
}

docker compose @composeArgs exec -T $ServiceName rm -f $containerFile | Out-Null

Write-Host "Restore completed into database: $TargetDatabase"
Write-Host "Public table count after restore: $($tableCount.Trim())"
