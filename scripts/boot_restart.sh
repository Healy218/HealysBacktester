#!/usr/bin/env bash
# Generic reboot-recovery dispatcher for long-running background jobs.
# Idempotent: safe to run any time, including manually
# (`bash scripts/boot_restart.sh`).
#
# NOT CURRENTLY WIRED TO ANYTHING (2026-07-30). On the retired Windows box this
# ran at logon via the "HealysBacktester WF AutoRestart" scheduled task plus
# auto-logon, so it fired after any reboot including a BSOD. The Pop!_OS
# migration ported the hourly StockTwits job to a systemd timer but never
# replaced this trigger — /etc/systemd/system/ has only the healys-stocktwits
# units. Until a unit exists, nothing restarts an interrupted long job after a
# crash, and this box still crashes. See the never-started guard below: an
# arming unit is safe to add, because a job nobody has launched here stays
# SKIPped rather than being started by the dispatcher.
#
# OBSERVABILITY (2026-07-22, revised 2026-08-28): every run appends to
# logs/boot_restart.d.log; the per-boot Telegram summary now defaults OFF
# (BOOT_RESTART_HEARTBEAT=1 re-enables) — it earned its keep on the crashy
# i5 build, but on the stable Ryzen box a ping every routine boot is noise
# (user decision 2026-08-28). Relaunch notices still send. The 2026-07-22
# ambiguity note below predates that revision: back then a reboot test
# inconclusive.
#
# DONE SEMANTICS (2026-07-22): a job is "done" only when its per-run exit
# marker (scripts/.jobstate/<JOB_ID>.exit) contains 0. The marker is created
# (empty) by the launch script at start and filled with the exit code on
# completion, so:
#   - NO marker file -> never started on this machine -> SKIP (see below)
#   - empty marker   -> started but never completed (crash) -> relaunch
#   - "0"            -> finished cleanly                    -> skip
#   - non-zero       -> finished with an ERROR              -> relaunch (retry)
# This replaces `grep -q "X-EXIT:" some.log`, which (a) matched failure markers
# too and (b) matched a STALE marker from a previous run forever, permanently
# blocking the restart of any re-run. A descriptor may still set JOB_DONE_CHECK
# to override with its own legacy check.
#
# NEVER-STARTED GUARD (2026-07-27, Pop!_OS): an ABSENT marker is not the same
# as an empty one. This dispatcher RESTARTS work that was interrupted; it must
# never START work nobody asked for. That distinction had no teeth while the
# state lived on one long-lived Windows box, and the migration proved why it
# matters: run logs and scripts/.jobstate/ are both gitignored, so on the
# restored box every registered job looked "not done" and a single dispatcher
# run fired all three multi-hour jobs at once. A job becomes eligible for
# auto-restart only once something has actually launched it here.
#
# To register a new job, drop a descriptor in scripts/jobs.d/*.sh — see
# scripts/jobs.d/README.md. This dispatcher never needs to change to add a job.
cd "$(dirname "$(readlink -f "$0")")/.." || exit 1
export NN_META_POOL=v31

STATE_DIR="scripts/.jobstate"
# NOT boot_restart.log: systemd's StandardOutput=append: creates that file
# as root, so this script (User=healy) can never append to it — every _log
# was silently failing with Permission denied until 2026-08-28.
RUN_LOG="logs/boot_restart.d.log"
mkdir -p "$STATE_DIR" logs
STAMP="$(date '+%Y-%m-%d %H:%M:%S')"

TOKEN=$(grep -m1 "^TELEGRAM_BOT_TOKEN=" .env 2>/dev/null | cut -d= -f2- | tr -d "\"'")
CHAT=$(grep -m1 "^TELEGRAM_CHAT_ID=" .env 2>/dev/null | cut -d= -f2- | tr -d "\"'")
_notify() {
  [ -n "$TOKEN" ] && [ -n "$CHAT" ] || { echo "$STAMP notify skipped (no .env creds)" >> "$RUN_LOG"; return 0; }
  curl -s -m 20 --retry 3 --retry-delay 20 \
    "https://api.telegram.org/bot${TOKEN}/sendMessage" -d chat_id="${CHAT}" \
    --data-urlencode text="$1" >/dev/null
}
_log() { echo "$STAMP $1" >> "$RUN_LOG"; }

_log "dispatcher START (pid $$)"
relaunched=0 running=0 done_clean=0 failed=0 skipped=0

shopt -s nullglob
for job in scripts/jobs.d/*.sh; do
  # each descriptor runs in its own subshell so a leaked variable in one can't
  # affect another; it prints exactly one KIND|name|detail status line.
  result=$(
    JOB_NAME=""
    JOB_ID=""                # slug for the exit marker (defaults to file name)
    JOB_PROC_PATTERN=""      # pgrep -f pattern meaning "already running"
    JOB_DONE_CHECK=""        # optional legacy override; exit 0 == "already done"
    JOB_PRELAUNCH=""         # optional; last stdout line folds into the notice
    JOB_LAUNCH_CMD=""        # (re)start command; must background itself
    # shellcheck disable=SC1090
    . "$job"
    if [ -z "$JOB_NAME" ] || [ -z "$JOB_PROC_PATTERN" ] || [ -z "$JOB_LAUNCH_CMD" ]; then
      echo "SKIP|$(basename "$job")|missing JOB_NAME/JOB_PROC_PATTERN/JOB_LAUNCH_CMD"; exit 0
    fi

    pgrep -f "$JOB_PROC_PATTERN" >/dev/null 2>&1 && { echo "RUNNING|$JOB_NAME|"; exit 0; }

    marker="$STATE_DIR/${JOB_ID:-$(basename "$job" .sh)}.exit"
    # Nothing has ever launched this job on this machine — restarting it would
    # be starting it, which is not this dispatcher's job. Checked ahead of
    # JOB_DONE_CHECK so legacy log-grep descriptors get the guard too: a
    # missing (gitignored) run log otherwise reads as "not done" on a fresh box.
    [ -e "$marker" ] || { echo "SKIP|$JOB_NAME|never started on this machine (no $marker)"; exit 0; }
    if [ -n "$JOB_DONE_CHECK" ]; then
      eval "$JOB_DONE_CHECK" >/dev/null 2>&1 && { echo "DONE|$JOB_NAME|legacy done-check"; exit 0; }
    else
      code=$(cat "$marker" 2>/dev/null)
      [ "$code" = "0" ] && { echo "DONE|$JOB_NAME|exit 0"; exit 0; }
      [ -n "$code" ] && failed_prev="exit $code" || failed_prev=""
    fi

    # (Re)launch. Empty the marker first so an interrupted run reads as "not
    # done" next boot; the launch script writes its real exit code here.
    : > "$marker"
    export JOB_EXIT_MARKER="$PWD/$marker"
    detail=""
    [ -n "$JOB_PRELAUNCH" ] && detail=$(eval "$JOB_PRELAUNCH" 2>&1 | tail -1)
    eval "$JOB_LAUNCH_CMD"
    echo "RELAUNCH|$JOB_NAME|${failed_prev:+retry after ${failed_prev}; }${detail}"
  )
  IFS='|' read -r kind name extra <<< "$(printf '%s\n' "$result" | tail -1)"
  case "$kind" in
    RELAUNCH) relaunched=$((relaunched+1)); _log "RELAUNCHED $name — $extra"
              _notify "AUTO-RESTARTED after reboot: ${name}${extra:+ (${extra})}" ;;
    RUNNING)  running=$((running+1));   _log "already running: $name" ;;
    DONE)     done_clean=$((done_clean+1)); _log "already done: $name ($extra)" ;;
    SKIP)     skipped=$((skipped+1));   _log "SKIP $name: $extra" ;;
    *)        _log "unparsed job result: $result" ;;
  esac
done

summary="boot_restart @ ${STAMP}: ${relaunched} relaunched, ${running} running, ${done_clean} done, ${skipped} skipped"
_log "dispatcher END — $summary"
# Heartbeat default OFF since 2026-08-28 (user decision): the Ryzen box is
# stable and a ping on every routine boot is noise. Relaunch notices above
# still fire when something was actually restarted. Re-enable per-boot
# pings with BOOT_RESTART_HEARTBEAT=1 in the unit's Environment=.
[ "${BOOT_RESTART_HEARTBEAT:-0}" = "1" ] && _notify "🔄 $summary"
exit 0
