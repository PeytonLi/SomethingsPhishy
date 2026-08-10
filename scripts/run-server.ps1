# Long-running wrapper for the MCP server. Kept separate from start-demo.ps1 so
# the scheduled task has one stable entry point that also captures logs.
#
# MUST run in the interactive session. A Windows Service would run in Session 0,
# which cannot read the logged-in user's clipboard — that silently kills
# CLIPBOARD_PAYLOAD, the highest-value check in the product.

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $env:LOCALAPPDATA "SomethingsPhishy"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir "server.log"

# Roll the log so a crash loop can't fill the disk overnight.
if ((Test-Path $log) -and ((Get-Item $log).Length -gt 5MB)) {
    Move-Item $log "$log.1" -Force
}

# Free the port if a previous run is still holding it, otherwise the new
# process exits instantly and the task looks like it "won't stay up".
$stale = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($stale) {
    Stop-Process -Id $stale.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 300
}

"[$(Get-Date -Format o)] starting MCP server" | Add-Content $log
& py -3 (Join-Path $repo "server.py") --http *>> $log
"[$(Get-Date -Format o)] server exited with code $LASTEXITCODE" | Add-Content $log
exit $LASTEXITCODE
