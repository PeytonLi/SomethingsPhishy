$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$demoUrl = "http://127.0.0.1:8080/"
$oneLoginUrl = "https://smccd.onelogin.com/login2/"
$archiveUrl = "https://archive.org/"
$extUrl = "https://ext.to/"
$logitechCheckoutUrl = "https://www.logitechg.com/en-us/checkout"
$elevenLabsUrl = "https://elevenlabs.io/app/subscription/creative"
$profile = Join-Path $env:LOCALAPPDATA "SomethingsPhishy\chrome-profile"

function Test-LocalPort([int]$Port) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        return $client.ConnectAsync("127.0.0.1", $Port).Wait(500)
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

try {
    $demoReady = (Invoke-WebRequest $demoUrl -TimeoutSec 1).StatusCode -eq 200
} catch {
    $demoReady = $false
}
if (-not $demoReady) {
    $server = Start-Process py -ArgumentList @(
        "-3", "-m", "http.server", "8080", "--directory",
        (Join-Path $repo "demo-lab")
    ) -WindowStyle Minimized -PassThru
    $deadline = (Get-Date).AddSeconds(10)
    do {
        Start-Sleep -Milliseconds 200
        try {
            $demoReady = (Invoke-WebRequest $demoUrl -TimeoutSec 1).StatusCode -eq 200
        } catch {
            $demoReady = $false
        }
    } while (-not $demoReady -and (Get-Date) -lt $deadline)
    if (-not $demoReady) {
        Stop-Process -Id $server.Id -ErrorAction SilentlyContinue
        throw "The local demo server did not start on 127.0.0.1:8080."
    }
    Write-Host "Demo server ready (PID $($server.Id))."
} else {
    Write-Host "Demo server already ready on port 8080."
}

$existingMcp = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($existingMcp) {
    Stop-Process -Id $existingMcp.OwningProcess -Force -ErrorAction Stop
    Start-Sleep -Milliseconds 300
    Write-Host "Stopped stale MCP server (PID $($existingMcp.OwningProcess))."
}
$mcp = Start-Process py -ArgumentList @(
    "-3", (Join-Path $repo "server.py"), "--http"
) -WindowStyle Minimized -PassThru
$deadline = (Get-Date).AddSeconds(10)
do {
    Start-Sleep -Milliseconds 200
    $mcpReady = Test-LocalPort 8765
} while (-not $mcpReady -and (Get-Date) -lt $deadline)
if (-not $mcpReady) {
    Stop-Process -Id $mcp.Id -ErrorAction SilentlyContinue
    throw "The MCP server did not start on 127.0.0.1:8765."
}
Write-Host "MCP server ready (PID $($mcp.Id))."

$chrome = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) { throw "Google Chrome is not installed in a standard location." }
New-Item -ItemType Directory -Force -Path $profile | Out-Null
Start-Process $chrome -ArgumentList @(
    "--remote-debugging-port=9222",
    "--user-data-dir=$profile",
    "--new-window",
    $demoUrl,
    $oneLoginUrl,
    $archiveUrl,
    $extUrl,
    $logitechCheckoutUrl,
    $elevenLabsUrl
)
$deadline = (Get-Date).AddSeconds(10)
do {
    Start-Sleep -Milliseconds 200
    try {
        $version = Invoke-RestMethod "http://127.0.0.1:9222/json/version" -TimeoutSec 1
    } catch {
        $version = $null
    }
} while (-not $version -and (Get-Date) -lt $deadline)
if (-not $version) { throw "Chrome started, but CDP did not open on 127.0.0.1:9222." }
Write-Host "Chrome CDP ready: $($version.Browser)"
Write-Host "Demo home opened: $demoUrl"
Write-Host "SMCCCD OneLogin opened: $oneLoginUrl"
Write-Host "Internet Archive opened: $archiveUrl"
Write-Host "EXT opened as an untrusted test surface: $extUrl"
Write-Host "Logitech G checkout opened in a tab: $logitechCheckoutUrl"
Write-Host "ElevenLabs subscription page opened: $elevenLabsUrl"
Write-Host "MCP integration URL: http://127.0.0.1:8765/mcp"
