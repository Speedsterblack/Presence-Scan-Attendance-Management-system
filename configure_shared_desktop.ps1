$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Python environment not found. Create it first with: python -m venv .venv"
}

Write-Host "Presence Scan shared desktop setup" -ForegroundColor Cyan
Write-Host "Database credentials are stored in the current Windows user's environment." -ForegroundColor Yellow

$hostName = Read-Host "PostgreSQL host"
$port = Read-Host "PostgreSQL port (default 5432)"
if ([string]::IsNullOrWhiteSpace($port)) { $port = "5432" }
$dbName = Read-Host "Database name"
$dbUser = Read-Host "Database user"
$dbPassword = Read-Host "Database password" -AsSecureString
$sslMode = Read-Host "SSL mode (default require)"
if ([string]::IsNullOrWhiteSpace($sslMode)) { $sslMode = "require" }
$universityCode = Read-Host "University code for this desktop (for example UG100)"
if ([string]::IsNullOrWhiteSpace($universityCode)) {
    throw "A university code is required so credentials can be scoped to this desktop."
}

$plainPassword = [System.Net.NetworkCredential]::new("", $dbPassword).Password
$settings = @{
    DB_HOST = $hostName
    DB_PORT = $port
    DB_NAME = $dbName
    DB_USER = $dbUser
    DB_PASSWORD = $plainPassword
    DB_SSLMODE = $sslMode
    LOCAL_PRIMARY = "1"
    PRESENCE_SCAN_UNIVERSITY_CODE = $universityCode.Trim()
}

[Environment]::SetEnvironmentVariable("PRESENCE_SCAN_ALL_UNIVERSITIES", $null, "User")
Remove-Item Env:PRESENCE_SCAN_ALL_UNIVERSITIES -ErrorAction SilentlyContinue

foreach ($item in $settings.GetEnumerator()) {
    [Environment]::SetEnvironmentVariable($item.Key, $item.Value, "User")
    Set-Item -Path "Env:$($item.Key)" -Value $item.Value
}

Write-Host "Initializing the shared PostgreSQL schema..." -ForegroundColor Cyan
$env:LOCAL_PRIMARY = "0"
Push-Location (Join-Path $projectRoot "qr_attendance_system")
try {
    & $python -m database.db_init
    if ($LASTEXITCODE -ne 0) {
        throw "Database schema initialization failed."
    }
}
finally {
    Pop-Location
    $env:LOCAL_PRIMARY = "1"
}

Write-Host "Shared desktop setup completed." -ForegroundColor Green
Write-Host "Start the application with launch_university_app.bat."
Write-Host "Each desktop should run this setup separately using the same database."
