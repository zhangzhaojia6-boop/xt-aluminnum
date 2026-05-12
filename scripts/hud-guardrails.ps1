# HUD guardrails — PowerShell flavor. Works on Windows without WSL/git-bash.
# Mirror of scripts/hud-guardrails.sh.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Fail($msg) {
    Write-Host "FAIL: $msg" -ForegroundColor Red
    exit 1
}

Write-Host "[1/6] scope guard"
$hudCss = Get-Content 'frontend/src/design/xt-hud.css' -Raw
if (-not ($hudCss -match '\[data-xt-theme="hud"\]')) {
    Fail 'xt-hud.css missing scope selector'
}
if ($hudCss -match '(?m)^(\.el-card|\.el-dialog|\.el-drawer)\s*\{') {
    Fail 'xt-hud.css contains global Element Plus override (scope violation)'
}
if ($hudCss -match '!important') { Fail '!important present in xt-hud.css' }

Write-Host "[2/6] forbidden lexicon (user-facing code only)"
$pattern = '(?i)cyberpunk|palantir|quantum|sci-?fi'
$codeFiles = @(
    (Get-ChildItem 'frontend/src' -Recurse -Include '*.vue','*.js','*.ts','*.css' -ErrorAction SilentlyContinue),
    (Get-ChildItem 'backend/app'  -Recurse -Include '*.py' -ErrorAction SilentlyContinue)
) | ForEach-Object { $_ } | Where-Object { $_ -ne $null }
foreach ($f in $codeFiles) {
    $content = Get-Content $f.FullName -Raw
    if ($content -match $pattern) {
        Fail "forbidden product lexicon in $($f.FullName)"
    }
}

Write-Host "[3/6] frontend unit tests"
Push-Location 'frontend'
try {
    $null = npm run --silent test
    if ($LASTEXITCODE -ne 0) { Fail 'frontend tests failed' }
} finally { Pop-Location }

Write-Host "[4/6] frontend build + three chunk"
Push-Location 'frontend'
try {
    $null = npm run --silent build
    if ($LASTEXITCODE -ne 0) { Fail 'frontend build failed' }
} finally { Pop-Location }
if (-not (Get-ChildItem 'frontend/dist/assets' -Filter 'vendor-three*' -ErrorAction SilentlyContinue)) {
    Fail 'three.js not code-split into vendor-three chunk'
}

Write-Host "[5/6] backend preferences tests"
if (Test-Path 'backend/tests/test_user_preferences.py') {
    Push-Location 'backend'
    try {
        $null = python -m pytest tests/test_user_preferences.py -q
        if ($LASTEXITCODE -ne 0) { Fail 'backend user_preferences tests failed' }
    } finally { Pop-Location }
} else {
    Write-Host '  skipped (Task 6 not merged yet)'
}

Write-Host "[6/6] docs guard"
$plan = Get-Content 'docs/superpowers/plans/2026-05-10-aesthetic-dynamic-landing.md' -Raw
if (-not ($plan -match 'SUPERSEDED')) {
    Fail 'aesthetic-dynamic-landing plan must be marked SUPERSEDED'
}

Write-Host 'ALL HUD GUARDRAILS PASS' -ForegroundColor Green
