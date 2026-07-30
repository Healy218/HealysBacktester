#!/usr/bin/env bash
# Telegram notifier + server dead-man pusher for the v3.1 walk-forward.
# Launch with setsid nohup after scripts/run_wf_v31.sh is up.
cd "$(dirname "$(readlink -f "$0")")/.."
TELEGRAM_BOT_TOKEN=$(grep -m1 "^TELEGRAM_BOT_TOKEN=" .env | cut -d= -f2- | tr -d "\"'")
TELEGRAM_CHAT_ID=$(grep -m1 "^TELEGRAM_CHAT_ID=" .env | cut -d= -f2- | tr -d "\"'")
SERVER=mrhea@62.238.20.66
send(){ curl -s -m 20 "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" -d chat_id="${TELEGRAM_CHAT_ID}" --data-urlencode text="$1"; echo; }
progress(){ tail -q -n 40 v31_wf.log wf_prewarm_f*_s*.log 2>/dev/null | grep -E "froze |rows |PHASE|seed |fold " | tail -1 | tr -cd "A-Za-z0-9 ()/:.,+%=_-" | cut -c1-70; }
push(){ ssh -o BatchMode=yes -o ConnectTimeout=10 "$SERVER" "mkdir -p ~/.deadman && echo '$(date -u +%s) $1 wf: $(progress)' > ~/.deadman/v31_build" >/dev/null 2>&1 || true; }
send "v3.1 walk-forward watcher armed (server dead-man active)"
push armed
while true; do
  if grep -q "WF-EXIT:0" v31_wf.log 2>/dev/null; then
    push disarmed
    VERDICT=$(grep -E "ROBUST|NOT robust" v31_wf.log | tail -1 | cut -c1-160)
    send "v3.1 WALK-FORWARD COMPLETE: ${VERDICT:-see reports_v31/meta_report.md}"
    exit 0
  fi
  if grep -q "WF-EXIT:1" v31_wf.log 2>/dev/null; then
    push disarmed
    send "v3.1 walk-forward FAILED in the canonical stage - check v31_wf.log"
    exit 1
  fi
  if ! pgrep -f "wf_prewarm|walkforward_meta|run_wf" >/dev/null; then
    sleep 30
    if ! pgrep -f "wf_prewarm|walkforward_meta|run_wf" >/dev/null && ! grep -q "WF-EXIT:" v31_wf.log 2>/dev/null; then
      push disarmed
      send "v3.1 walk-forward STOPPED at: $(progress) - check v31_wf.log + wf_prewarm logs"
      exit 1
    fi
  fi
  push armed
  sleep 300
done
