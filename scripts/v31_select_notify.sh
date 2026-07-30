#!/usr/bin/env bash
# Telegram notifier + server dead-man pusher for v3.1 select_meta.
# Launch with setsid nohup after scripts/run_select_v31.sh is up.
cd "$(dirname "$(readlink -f "$0")")/.."
TELEGRAM_BOT_TOKEN=$(grep -m1 "^TELEGRAM_BOT_TOKEN=" .env | cut -d= -f2- | tr -d "\"'")
TELEGRAM_CHAT_ID=$(grep -m1 "^TELEGRAM_CHAT_ID=" .env | cut -d= -f2- | tr -d "\"'")
SERVER=mrhea@62.238.20.66
send(){ curl -s -m 20 "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" -d chat_id="${TELEGRAM_CHAT_ID}" --data-urlencode text="$1"; echo; }
progress(){ echo "$(grep -c '^  val ' v31_select.log 2>/dev/null)/320"; }
push(){ ssh -o BatchMode=yes -o ConnectTimeout=10 "$SERVER" "mkdir -p ~/.deadman && echo '$(date -u +%s) $1 select-$(progress)' > ~/.deadman/v31_build" >/dev/null 2>&1 || true; }
send "v3.1 selection watcher armed (server dead-man active)"
push armed
while true; do
  if grep -q "SELECT-EXIT:0" v31_select.log 2>/dev/null; then
    push disarmed
    RESULT=$(grep -E 'TEST \(|NO ELIGIBLE|winner:' v31_select.log | tail -2 | tr '\n' ' ')
    send "v3.1 select_meta COMPLETE: ${RESULT:-see meta_report.md}"
    exit 0
  fi
  if grep -q "SELECT-EXIT:1" v31_select.log 2>/dev/null; then
    push disarmed
    send "v3.1 select_meta FAILED - check v31_select.log"
    exit 1
  fi
  if ! pgrep -f "nn_meta.select_meta" >/dev/null; then
    sleep 30
    if ! pgrep -f "nn_meta.select_meta" >/dev/null && ! grep -q "SELECT-EXIT:" v31_select.log 2>/dev/null; then
      push disarmed
      send "v3.1 selection STOPPED without exit marker at $(progress) - check v31_select.log"
      exit 1
    fi
  fi
  push armed
  sleep 300
done
