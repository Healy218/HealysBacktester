# Home-box systemd units (Pop!_OS)

These replace the Windows Scheduled Tasks that ran on the pre-2026-07-24 WSL2 box.

| Old Windows task | Replacement | Status |
|---|---|---|
| HealysBacktester StockTwits (hourly) | `healys-stocktwits.timer` | here |
| HealysBacktester Live Scan | — | intentionally absent; the Hetzner server owns live scanning, and re-enabling here would double the Telegram alerts |
| HealysBacktester WF AutoRestart (logon) | `scripts/boot_restart.sh` | not yet wired; needs a `systemd` unit when a long unattended run is next launched |
| HealysBacktester VSCode AutoOpen (logon) | — | obsolete (was the Windows auto-logon remote-control chain) |

## Install

```sh
sudo cp deploy/systemd/healys-stocktwits.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now healys-stocktwits.timer
```

Verify:

```sh
systemctl list-timers healys-stocktwits.timer
sudo systemctl start healys-stocktwits.service   # run once now
tail -f logs/stocktwits.log
```

These are **system** units (not `--user`) on purpose: the old setup needed
Windows auto-logon to fire its tasks, and a system timer removes that
dependency — it runs after a reboot whether or not anyone logs in.

The paths are absolute and assume the repo at
`/home/healylabs/Coding/HealysBacktester`; edit `WorkingDirectory`/`ExecStart`
if that changes. The collector script itself derives its own repo root, so it
is path-independent.
