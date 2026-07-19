#!/usr/bin/env bash
# Idempotent auto-restart of the v3.1 walk-forward. Runs at Windows logon
# (which, with auto-logon enabled, means right after any reboot including
# BSODs). Safe to run any time: exits if the wf is already running or done.
# Validates checkpoint JSONs first and quarantines any corrupt shard state,
# because a half-written state file wedges the shard retry loop forever.
cd /home/mrhea/HealysBacktester || exit 1
export NN_META_POOL=v31

pgrep -f "run_wf_v31|wf_prewarm|walkforward_meta" >/dev/null && exit 0
grep -q "WF-EXIT:" v31_wf.log 2>/dev/null && exit 0

ts=$(date +%s)
bad=0
for f in nn_meta/artifacts_v31/wf/fold*_spec*.json \
         nn_meta/artifacts_v31/wf/fold*_rows/done_shard*.json \
         nn_meta/artifacts_v31/wf/fold*_rows/done.json; do
  [ -f "$f" ] || continue
  if ! ./venv/bin/python -c "import json,sys; json.load(open(sys.argv[1]))" "$f" >/dev/null 2>&1; then
    mv "$f" "$f.corrupt.$ts"
    bad=$((bad+1))
  fi
done

setsid nohup bash scripts/run_wf_v31.sh 3 >> v31_wf.log 2>&1 < /dev/null &
sleep 5
setsid nohup bash scripts/v31_wf_notify.sh >> v31_notify.log 2>&1 < /dev/null &

TOKEN=$(grep -m1 "^TELEGRAM_BOT_TOKEN=" .env | cut -d= -f2- | tr -d "\"'")
CHAT=$(grep -m1 "^TELEGRAM_CHAT_ID=" .env | cut -d= -f2- | tr -d "\"'")
curl -s -m 20 --retry 3 --retry-delay 20 \
  "https://api.telegram.org/bot${TOKEN}/sendMessage" -d chat_id="${CHAT}" \
  --data-urlencode text="v3.1 wf AUTO-RESTARTED after reboot (${bad} corrupt checkpoint(s) quarantined)" \
  >/dev/null
exit 0
