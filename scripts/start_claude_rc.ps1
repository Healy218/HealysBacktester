# Start a remote-controllable Claude Code session for this repo unless one is
# already running. Launched by .vscode/tasks.json on folder open, so both a
# post-reboot auto-logon and a normal "open the project" arm remote access.
$existing = Get-CimInstance Win32_Process -Filter "Name='claude.exe'" |
    Where-Object { $_.CommandLine -match 'remote-control' }
if ($existing) {
    Write-Host "Claude remote-control session already running (PID $(@($existing)[0].ProcessId)); not starting another."
    Write-Host "Find it at https://claude.ai/code."
    exit 0
}
Set-Location (Split-Path $PSScriptRoot -Parent)
& claude --remote-control
