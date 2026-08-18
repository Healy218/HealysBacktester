# Home-box systemd units (CachyOS)

These replace the Windows Scheduled Tasks that ran on the pre-2026-07-24 WSL2 box.

| Old Windows task | Replacement | Status |
|---|---|---|
| HealysBacktester StockTwits (hourly) | `healys-stocktwits.timer` | here |
| HealysBacktester Live Scan | — | intentionally absent; the Hetzner server owns live scanning, and re-enabling here would double the Telegram alerts |
| HealysBacktester WF AutoRestart (logon) | `healys-boot-restart.service` | here (added 2026-07-30); **not installed yet** — see below |
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

### Reboot recovery (`healys-boot-restart.service`)

```sh
sudo cp deploy/systemd/healys-boot-restart.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable healys-boot-restart.service
sudo systemctl start healys-boot-restart.service   # verify without rebooting
tail logs/boot_restart.log
```

Enabled but not started, this does nothing until the next boot — which is the
point. Starting it by hand is the safe way to confirm it dispatches correctly,
because with an empty `scripts/.jobstate/` every job reports
`SKIP|<name>|never started on this machine`. That is the expected output on a
box where nothing has been launched yet, **not** a failure.

These are **system** units (not `--user`) on purpose: the old setup needed
Windows auto-logon to fire its tasks, and a system timer removes that
dependency — it runs after a reboot whether or not anyone logs in.

The paths are absolute and assume the repo at
`/home/healy/Coding/HealysBacktester`; edit `WorkingDirectory`/`ExecStart`
if that changes. The collector script itself derives its own repo root, so it
is path-independent.
