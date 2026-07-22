#!/usr/bin/env bash
# Generic reboot-recovery dispatcher for long-running background jobs.
# Runs at Windows logon via the "HealysBacktester WF AutoRestart" scheduled
# task — with auto-logon enabled, that means right after ANY reboot,
# including BSODs. Idempotent: safe to run any time, including manually.
#
# To register a new long-running job (current or future), drop a descriptor
# in scripts/jobs.d/*.sh — see scripts/jobs.d/README.md for the format. This
# dispatcher itself never needs to change to add a job.
cd /home/mrhea/HealysBacktester || exit 1
export NN_META_POOL=v31

TOKEN=$(grep -m1 "^TELEGRAM_BOT_TOKEN=" .env | cut -d= -f2- | tr -d "\"'")
CHAT=$(grep -m1 "^TELEGRAM_CHAT_ID=" .env | cut -d= -f2- | tr -d "\"'")
_notify() {
  curl -s -m 20 --retry 3 --retry-delay 20 \
    "https://api.telegram.org/bot${TOKEN}/sendMessage" -d chat_id="${CHAT}" \
    --data-urlencode text="$1" >/dev/null
}

shopt -s nullglob
for job in scripts/jobs.d/*.sh; do
  # each descriptor runs in its own subshell: a bug or a leaked variable in
  # one job's descriptor can't affect any other job's evaluation
  (
    JOB_NAME=""
    JOB_PROC_PATTERN=""     # pgrep -f pattern that means "already running"
    JOB_DONE_CHECK=""       # shell snippet; exit 0 (true) means "already finished"
    JOB_PRELAUNCH=""        # optional shell snippet run before relaunch (e.g.
                             # checkpoint validation); last line of stdout is
                             # folded into the notification text
    JOB_LAUNCH_CMD=""       # shell snippet that (re)starts the job, backgrounded
    # shellcheck disable=SC1090
    . "$job"
    if [ -z "$JOB_NAME" ] || [ -z "$JOB_PROC_PATTERN" ] || [ -z "$JOB_LAUNCH_CMD" ]; then
      echo "skip $job: missing JOB_NAME/JOB_PROC_PATTERN/JOB_LAUNCH_CMD"
      exit 0
    fi

    pgrep -f "$JOB_PROC_PATTERN" >/dev/null 2>&1 && exit 0   # already running
    if [ -n "$JOB_DONE_CHECK" ] && eval "$JOB_DONE_CHECK" >/dev/null 2>&1; then
      exit 0   # finished cleanly before any crash — nothing to do
    fi

    detail=""
    [ -n "$JOB_PRELAUNCH" ] && detail=$(eval "$JOB_PRELAUNCH" 2>&1 | tail -1)

    eval "$JOB_LAUNCH_CMD"
    _notify "AUTO-RESTARTED after reboot: ${JOB_NAME}${detail:+ (${detail})}"
  )
done
exit 0
