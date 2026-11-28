<#
.SYNOPSIS
  Start CreatorShield on Windows: migrations, API, worker and frontend.

.DESCRIPTION
  The Windows counterpart of scripts/dev.sh. It expects PostgreSQL and Redis to be
  running and these tools on PATH: ffmpeg, ffprobe, tesseract, fpcalc, node, and a
  Python 3.13 virtual environment in backend\.venv (create it with `uv sync` or
  `python -m venv .venv` + `pip install -e .`).

  If your tools are not on PATH, pass a script that puts them there:
    scripts\dev.ps1 -ToolsEnv C:\path\to\env.ps1

  Logs: var\logs\{api,worker,frontend}.log    Stop: scripts\stop.ps1

.PARAMETER ToolsEnv
  Optional .ps1 file dot-sourced first (sets PATH, TESSDATA_PREFIX and so on).

.PARAMETER NoFrontend
  Start only the API and the worker.
#>
[CmdletBinding()]
param(
    [string]$ToolsEnv = "",
    [switch]$NoFrontend
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Logs = Join-Path $Root "var\logs"
$Pids = Join-Path $Root "var\pids"
New-Item -ItemType Directory -Force $Logs, $Pids | Out-Null

if ($ToolsEnv) {
    if (-not (Test-Path $ToolsEnv)) { throw "ToolsEnv not found: $ToolsEnv" }
    . $ToolsEnv
}

$Python = Join-Path $Root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "backend\.venv is missing. In backend\ run: uv sync   (or: python -m venv .venv; .venv\Scripts\pip install -e .)"
}

foreach ($tool in "ffmpeg", "ffprobe", "tesseract", "fpcalc", "node") {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "$tool is not on PATH. Install it, or pass -ToolsEnv with a script that adds it."
    }
}

# ---- backend\.env ------------------------------------------------------------
$EnvFile = Join-Path $Root "backend\.env"
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $Root ".env.example") $EnvFile
    Write-Host "- created backend\.env from .env.example"
}
$envText = Get-Content $EnvFile -Raw
if ($envText -notmatch "(?m)^TOKEN_ENCRYPTION_KEY=.+") {
    $key = & $Python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    if ($envText -match "(?m)^TOKEN_ENCRYPTION_KEY=") {
        $envText = $envText -replace "(?m)^TOKEN_ENCRYPTION_KEY=.*$", "TOKEN_ENCRYPTION_KEY=$key"
    } else {
        $envText = $envText.TrimEnd() + "`nTOKEN_ENCRYPTION_KEY=$key`n"
    }
    # UTF-8 without a byte-order mark; the settings loader reads the first key literally.
    [System.IO.File]::WriteAllText($EnvFile, $envText, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "- generated TOKEN_ENCRYPTION_KEY in backend\.env (keep it; changing it invalidates stored connections)"
}
$FrontEnv = Join-Path $Root "frontend\.env.local"
if (-not (Test-Path $FrontEnv)) {
    [System.IO.File]::WriteAllText($FrontEnv, "NEXT_PUBLIC_API_URL=http://localhost:8000`n", (New-Object System.Text.UTF8Encoding($false)))
}

# ---- migrations ----------------------------------------------------------------
$env:PYTHONUTF8 = "1"
Push-Location (Join-Path $Root "backend")
try {
    Write-Host "- applying database migrations"
    & $Python -m alembic upgrade head | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Migrations failed. Is PostgreSQL running and DATABASE_URL in backend\.env correct?"
    }
} finally {
    Pop-Location
}

function Start-Part {
    param([string]$Name, [string]$Exe, [string[]]$Arguments, [string]$WorkingDir)
    $pidFile = Join-Path $Pids "$Name.pid"
    if (Test-Path $pidFile) {
        $old = Get-Content $pidFile -ErrorAction SilentlyContinue
        if ($old -and (Get-Process -Id $old -ErrorAction SilentlyContinue)) {
            Write-Host "- $Name already running (pid $old)"
            return
        }
    }
    $proc = Start-Process -FilePath $Exe -ArgumentList $Arguments -WorkingDirectory $WorkingDir `
        -RedirectStandardOutput (Join-Path $Logs "$Name.log") `
        -RedirectStandardError (Join-Path $Logs "$Name.err.log") `
        -WindowStyle Hidden -PassThru
    Set-Content -Path $pidFile -Value $proc.Id
    Write-Host "- started $Name (pid $($proc.Id), log var\logs\$Name.log)"
}

$Backend = Join-Path $Root "backend"
Start-Part -Name "api" -Exe $Python -WorkingDir $Backend `
    -Arguments @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000")
Start-Part -Name "worker" -Exe $Python -WorkingDir $Backend -Arguments @("-m", "app.worker")
if (-not $NoFrontend) {
    $Frontend = Join-Path $Root "frontend"
    if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
        throw "frontend\node_modules is missing. In frontend\ run: npm install"
    }
    Start-Part -Name "frontend" -Exe "cmd.exe" -WorkingDir $Frontend `
        -Arguments @("/c", "npm", "run", "dev", "--", "--hostname", "127.0.0.1", "--port", "3000")
}

Write-Host "- waiting for services"
$deadline = (Get-Date).AddSeconds(90)
while ((Get-Date) -lt $deadline) {
    $apiUp = $false
    $webUp = [bool]$NoFrontend
    try { $apiUp = (Invoke-WebRequest "http://127.0.0.1:8000/api/health/live" -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 } catch { }
    if (-not $webUp) {
        try { $webUp = (Invoke-WebRequest "http://127.0.0.1:3000/" -UseBasicParsing -TimeoutSec 5).StatusCode -eq 200 } catch { }
    }
    if ($apiUp -and $webUp) {
        Write-Host ""
        if (-not $NoFrontend) { Write-Host "CreatorShield is running:  http://localhost:3000" }
        Write-Host "API docs:                  http://localhost:8000/docs"
        exit 0
    }
    Start-Sleep -Seconds 1
}
Write-Error "Services did not become healthy in 90 s. Check var\logs\*.log"
exit 1
