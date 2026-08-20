$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BuildEnvironment = Join-Path $ProjectRoot ".venv-build"
$BuildPython = Join-Path $BuildEnvironment "Scripts\python.exe"

Set-Location $ProjectRoot

if (-not (Test-Path -LiteralPath $BuildPython)) {
    py -m venv $BuildEnvironment
}

& $BuildPython -m pip install --upgrade pip
& $BuildPython -m pip install ".[build]"
& $BuildPython -m PyInstaller --noconfirm --clean RallyPin.spec

Write-Host "RallyPin is ready at dist\RallyPin.exe"
