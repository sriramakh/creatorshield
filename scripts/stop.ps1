<#
.SYNOPSIS
  Stop the CreatorShield processes started by scripts\dev.ps1 (API, worker, frontend).
  PostgreSQL and Redis are left running.
#>
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
$Pids = Join-Path $Root "var\pids"

foreach ($name in "frontend", "worker", "api") {
    $pidFile = Join-Path $Pids "$name.pid"
    if (-not (Test-Path $pidFile)) { continue }
    $id = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($id -and (Get-Process -Id $id -ErrorAction SilentlyContinue)) {
        # /T also stops child processes (npm starts node; uvicorn may start helpers).
        & taskkill /PID $id /T /F | Out-Null
        Write-Host "- stopped $name (pid $id)"
    }
    Remove-Item $pidFile -ErrorAction SilentlyContinue
}
