#!/usr/bin/env bash
# v4 Option A: pick the deployable config on a full-data validation tail,
# train + persist a 40-seed ensemble to nn_meta/model_final_v4/. setsid
# nohup'd so it survives this shell/session ending. NOT crash-resumable
# (v4_finalize.py wipes model_final_v4/ at the start of the persist step,
# same known limitation as v4_evaluate.py) — a crash means restart from
# scratch, which scripts/jobs.d/v4_finalize.sh will do automatically.
cd /home/mrhea/HealysBacktester || exit 1
export NN_META_POOL=v31

echo "=== v4 finalize start: $(date) ==="
FINAL_SEEDS="0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39"
./venv/bin/python -m nn_meta.v4_finalize \
  --select-seeds 0,1,2,3,4 --final-seeds "$FINAL_SEEDS" \
  --epochs 60 --gbt-estimators 600 --embargo 1D
EXIT=$?
echo "=== v4 finalize done: $(date), exit=$EXIT ==="
echo "V4-FINALIZE-EXIT:$EXIT"
# Per-run exit marker for scripts/boot_restart.sh (0 => done, else => retry).
# JOB_EXIT_MARKER is exported by the dispatcher; default the path for manual runs.
echo "$EXIT" > "${JOB_EXIT_MARKER:-scripts/.jobstate/v4_finalize.exit}" 2>/dev/null || true

TOKEN=$(grep -m1 "^TELEGRAM_BOT_TOKEN=" .env | cut -d= -f2- | tr -d "\"'")
CHAT=$(grep -m1 "^TELEGRAM_CHAT_ID=" .env | cut -d= -f2- | tr -d "\"'")
if [ "$EXIT" -eq 0 ]; then
  MSG="v4 finalize COMPLETE: model_final_v4/ saved. Check ensemble_config.json for the winning config."
else
  MSG="v4 finalize FAILED (exit=$EXIT). Check v4_finalize.log for the traceback."
fi
curl -s -m 20 --retry 3 --retry-delay 20 \
  "https://api.telegram.org/bot${TOKEN}/sendMessage" -d chat_id="${CHAT}" \
  --data-urlencode text="$MSG" >/dev/null
exit 0
