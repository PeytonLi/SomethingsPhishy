# Registers the MCP server to start at logon and restart if it dies.
# No admin rights needed — the task runs as the current user, in the current
# session, which is exactly what clipboard and Chrome capture require.
#
# Uninstall:  .\scripts\install-autostart.ps1 -Remove

param([switch]$Remove)

$ErrorActionPreference = "Stop"
$taskName = "SomethingsPhishy MCP"
$repo = Split-Path -Parent $PSScriptRoot

if ($Remove) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed scheduled task '$taskName'."
    return
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument (
    "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$(Join-Path $repo 'scripts\run-server.ps1')`""
)
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

# Interactive token: required for clipboard access. RunLevel stays Limited —
# a scam checker has no business running elevated.
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force | Out-Null

Write-Host "Registered '$taskName' (starts at logon, restarts up to 3x on failure)."
Write-Host "Start it now:  Start-ScheduledTask -TaskName '$taskName'"
Write-Host "Logs:          $env:LOCALAPPDATA\SomethingsPhishy\server.log"
