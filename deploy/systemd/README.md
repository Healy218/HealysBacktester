# Home-box systemd units (CachyOS)

These replace the Windows Scheduled Tasks that ran on the pre-2026-07-24 WSL2 box.

| Old Windows task | Replacement | Status |
|---|---|---|
| HealysBacktester StockTwits (hourly) | `healys-stocktwits.timer` | here |
| HealysBacktester Live Scan | — | intentionally absent; the Hetzner server owns live scanning, and re-enabling here would double the Telegram alerts |
| HealysBacktester WF AutoRestart (logon) | `healys-boot-restart.service` | committed template; verify host installation separately |
| HealysBacktester VSCode AutoOpen (logon) | — | obsolete (was the Windows auto-logon remote-control chain) |
| — (new 2026-08-25) | `healys-cache-backup.timer` | weekly one-way push of the irreplaceable data caches to GCS (`scripts/backup_caches.sh`) — install like the stocktwits pair |

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

## Verification boundaries

These files describe committed unit templates, not the currently installed
host state. Check the relevant system or user timer explicitly; the server
dead-man may be installed as a user timer with linger. No unit was installed,
enabled or restarted by the 2026-09-05 review fixes.

The long-job launchers propagate worker failures. Scanner state transactions
serialize overlapping processes using advisory file locks, and scanner dry
runs use a temporary state snapshot. The 16:00 ET cron invocation processes
the final closed bar; feeds more than 30 minutes behind their bar timestamp
are refused. A dry-run does not acknowledge production notifications.

After deploying the causal-feature correction, existing specs and bundles
must be rebuilt and validated under the current feature contract before
promotion; installing a timer is not a model-validation step.
