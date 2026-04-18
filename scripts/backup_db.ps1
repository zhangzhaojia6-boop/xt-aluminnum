param(
  [string[]]$ComposeFiles = @('docker-compose.yml'),
  [string]$ServiceName = 'db',
  [string]$BackupDir = 'backups',
  [string]$OutputFile = ''
)

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $repoRoot

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
if (-not $OutputFile) {
  $OutputFile = Join-Path $BackupDir "postgres-$timestamp.dump"
}

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

$containerFile = "/tmp/postgres-backup-$timestamp.dump"
$dumpCommand = 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f "' + $containerFile + '"'

docker compose @composeArgs exec -T $ServiceName sh -lc $dumpCommand
if ($LASTEXITCODE -ne 0) {
  throw 'pg_dump failed'
}

$containerId = (docker compose @composeArgs ps -q $ServiceName).Trim()
if (-not $containerId) {
  throw "Cannot find running container for service '$ServiceName'"
}

docker cp "${containerId}:$containerFile" $OutputFile
if ($LASTEXITCODE -ne 0) {
  throw 'docker cp failed while copying backup file from container'
}

docker compose @composeArgs exec -T $ServiceName rm -f $containerFile | Out-Null

Write-Host "Backup created: $OutputFile"
