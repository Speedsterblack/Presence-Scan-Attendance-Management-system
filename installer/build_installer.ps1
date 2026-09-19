$ErrorActionPreference = 'Stop'

Write-Host "Building Presence Scan GUI installer..." -ForegroundColor Cyan

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    throw "Python was not found on PATH. Install Python and activate the project environment first."
}

Push-Location (Join-Path $projectRoot "qr_attendance_system")
$buildErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $pyInstallerVersion = & $python.Source -m PyInstaller --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller is not installed. Run: python -m pip install -r requirements-dev.txt"
    }

    Write-Host "Building main application executable..." -ForegroundColor Cyan
    $mainBuildOutput = & $python.Source -m PyInstaller --noconfirm --clean .\PresenceScan.spec 2>&1
    $mainBuildOutput | Write-Host
    if ($LASTEXITCODE -ne 0) {
        throw "The main application executable build failed."
    }

    Write-Host "Building developer application executable..." -ForegroundColor Cyan
    $developerBuildOutput = & $python.Source -m PyInstaller --noconfirm --clean .\DeveloperPresenceScan.spec 2>&1
    $developerBuildOutput | Write-Host
    if ($LASTEXITCODE -ne 0) {
        throw "The developer application executable build failed."
    }
}
finally {
    $ErrorActionPreference = $buildErrorActionPreference
    Pop-Location
}

$candidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
)

$iscc = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $iscc) {
    Write-Host "Inno Setup compiler (ISCC.exe) not found." -ForegroundColor Yellow
    Write-Host "Install Inno Setup 6, then rerun this script." -ForegroundColor Yellow
    Write-Host "Download: https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
    exit 1
}

foreach ($issName in @("presence_scan.iss", "presence_scan_developer.iss")) {
    $issPath = Join-Path $PSScriptRoot $issName
    if (-not (Test-Path $issPath)) {
        throw "Inno Setup script not found: $issPath"
    }

    Write-Host "Building installer from $issName..." -ForegroundColor Cyan
    & $iscc $issPath
    if ($LASTEXITCODE -ne 0) {
        throw "Installer build failed for $issName."
    }
}

Write-Host "Installer build complete. Check .\\dist for both installer executables." -ForegroundColor Green
