#!/usr/bin/env bash
# One-shot Telegram notifier + server dead-man pusher for the v3.1 parallel
# dataset build. Survives independently of any Claude/terminal session
# (launch with setsid nohup). While armed, pushes a heartbeat line to the
# Hetzner server every 5 min; ~/bin/deadman_check.sh there (cron */5) texts
# if pushes go stale >15 min — that covers host death, which this local
# loop cannot report. Disarms on COMPLETE/STOPPED so only host death alerts.
cd "$(dirname "$(readlink -f "$0")")/.."
TELEGRAM_BOT_TOKEN=$(grep -m1 "^TELEGRAM_BOT_TOKEN=" .env | cut -d= -f2- | tr -d "\"'")
TELEGRAM_CHAT_ID=$(grep -m1 "^TELEGRAM_CHAT_ID=" .env | cut -d= -f2- | tr -d "\"'")
SERVER=mrhea@62.238.20.66
send(){ curl -s -m 20 "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" -d chat_id="${TELEGRAM_CHAT_ID}" --data-urlencode text="$1"; echo; }
done_count(){ ls nn_meta/artifacts_v31/meta_rows 2>/dev/null | wc -l; }
push(){ ssh -o BatchMode=yes -o ConnectTimeout=10 "$SERVER" "mkdir -p ~/.deadman && echo '$(date -u +%s) $1 $(done_count)/118' > ~/.deadman/v31_build" >/dev/null 2>&1 || true; }
send "v3.1 build watcher armed: $(done_count)/118 symbols done (server dead-man active)"
push armed
while true; do
  if grep -q "PARALLEL-BUILD-DONE" v31_build_parallel.log 2>/dev/null; then
    push disarmed
    send "v3.1 dataset build COMPLETE: $(done_count) symbol files assembled -> meta dataset ready for train_meta"
    exit 0
  fi
  if ! pgrep -f "build_meta_dataset" >/dev/null; then
    sleep 30
    if ! pgrep -f "build_meta_dataset" >/dev/null; then
      push disarmed
      send "v3.1 build STOPPED at $(done_count)/118 symbols. Check v31_build_*.log; rerun scripts/run_build_parallel.sh 3 to resume."
      exit 1
    fi
  fi
  push armed
  sleep 300
done
