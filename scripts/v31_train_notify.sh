#!/usr/bin/env bash
# Telegram notifier + server dead-man pusher for v3.1 train_meta.
# Launch with setsid nohup after scripts/run_train_v31.sh is up.
cd /home/mrhea/HealysBacktester
TELEGRAM_BOT_TOKEN=$(grep -m1 "^TELEGRAM_BOT_TOKEN=" .env | cut -d= -f2- | tr -d "\"'")
TELEGRAM_CHAT_ID=$(grep -m1 "^TELEGRAM_CHAT_ID=" .env | cut -d= -f2- | tr -d "\"'")
SERVER=mrhea@62.238.20.66
send(){ curl -s -m 20 "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" -d chat_id="${TELEGRAM_CHAT_ID}" --data-urlencode text="$1"; echo; }
progress(){ tail -n 40 v31_train.log 2>/dev/null | grep -oE '\[[0-9]+/[0-9]+\]' | tail -1 | tr -d '[]'; }
push(){ ssh -o BatchMode=yes -o ConnectTimeout=10 "$SERVER" "mkdir -p ~/.deadman && echo '$(date -u +%s) $1 training-$(progress)' > ~/.deadman/v31_build" >/dev/null 2>&1 || true; }
send "v3.1 training watcher armed (server dead-man active)"
push armed
while true; do
  if grep -q "TRAIN-EXIT:0" v31_train.log 2>/dev/null; then
    push disarmed
    send "v3.1 train_meta COMPLETE ($(progress) runs) -> next: select_meta"
    exit 0
  fi
  if grep -q "TRAIN-EXIT:1" v31_train.log 2>/dev/null; then
    push disarmed
    send "v3.1 train_meta FAILED - check v31_train.log tail"
    exit 1
  fi
  if ! pgrep -f "nn_meta.train_meta" >/dev/null; then
    sleep 30
    if ! pgrep -f "nn_meta.train_meta" >/dev/null && ! grep -q "TRAIN-EXIT:" v31_train.log 2>/dev/null; then
      push disarmed
      send "v3.1 training STOPPED without exit marker at $(progress) - check v31_train.log"
      exit 1
    fi
  fi
  push armed
  sleep 300
done
