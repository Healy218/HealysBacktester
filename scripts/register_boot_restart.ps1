# scripts/register_boot_restart.ps1
#
# Registers (or re-registers) the Windows Scheduled Task that runs the reboot
# dispatcher scripts/boot_restart.sh at every logon. With auto-logon enabled
# this fires right after any reboot, including a BSOD.
#
# This file exists because the task registration used to live ONLY in the
# operator's head / the live Task Scheduler — nothing in the repo proved it was
# ever registered, and the 2026-07-22 reboot test could not distinguish "task
# never fired" from "dispatcher ran and correctly did nothing." Commit the
# exact command so the registration is reproducible and reviewable.
#
# Run from an elevated PowerShell on the Windows box:
#     powershell -ExecutionPolicy Bypass -File scripts\register_boot_restart.ps1
#
# Then TEST the trigger for real (do not trust manual test-firing alone — the
# logon trigger path is what actually matters):
#     1. schtasks /Run  /TN "HealysBacktester WF AutoRestart"   # manual fire
#     2. reboot the box and confirm a "🔄 boot_restart @ ..." Telegram arrives
#        and logs/boot_restart.log gained a "dispatcher START/END" pair.

param(
  [string]$TaskName = "HealysBacktester WF AutoRestart",
  [string]$WslDistro = "Ubuntu",                       # `wsl -l -v` to confirm
  [string]$RepoDir   = "~/HealysBacktester",           # path INSIDE the WSL distro
  [string]$RunAsUser = "$env:USERNAME"
)

# Runs the dispatcher inside WSL as a login shell (so PATH/venv resolve), and
# tees the task-side stdout to a log distinct from the dispatcher's own log.
$inner  = "cd $RepoDir && bash scripts/boot_restart.sh >> logs/boot_restart_task.log 2>&1"
$action = "wsl.exe -d $WslDistro -e bash -lc `"$inner`""

Write-Host "Registering '$TaskName' -> $action"
schtasks /Create `
  /TN  "$TaskName" `
  /TR  "$action" `
  /SC  ONLOGON `
  /RU  "$RunAsUser" `
  /RL  HIGHEST `
  /F

if ($LASTEXITCODE -eq 0) {
  Write-Host "Registered. Verify with:  schtasks /Query /TN `"$TaskName`" /V /FO LIST"
} else {
  Write-Error "schtasks /Create failed with exit code $LASTEXITCODE"
}
