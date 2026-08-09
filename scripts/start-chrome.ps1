$ErrorActionPreference = "Stop"
$profile = Join-Path $env:LOCALAPPDATA "SomethingsPhishy\chrome-profile"
$chrome = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) { throw "Google Chrome is not installed in a standard location." }
New-Item -ItemType Directory -Force -Path $profile | Out-Null
Start-Process $chrome -ArgumentList @(
    "--remote-debugging-port=9222",
    "--user-data-dir=$profile"
)
$deadline = (Get-Date).AddSeconds(10)
do {
    Start-Sleep -Milliseconds 200
    try {
        $version = Invoke-RestMethod "http://127.0.0.1:9222/json/version" -TimeoutSec 1
    } catch { $version = $null }
} while (-not $version -and (Get-Date) -lt $deadline)
if (-not $version) { throw "Chrome started, but CDP did not open on 127.0.0.1:9222." }
Write-Host "Chrome CDP ready: $($version.Browser)"
