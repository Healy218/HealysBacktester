#!/usr/bin/env bash
# v4 full-scale run: ablation (4 treatments) then nested 3-fold walk-forward,
# both against the real 118-symbol v31 dataset (nn_meta/artifacts_v31/).
# setsid nohup'd so it survives this shell/session ending. NOT reboot-of-the-
# box resilient (v4_evaluate.py has no mid-run checkpointing yet) — a crash
# means restart from scratch. WiFi-card fix gave 48h+ clean uptime as of
# 2026-07-21 evening, so treat as low risk, not zero risk.
cd "$(dirname "$(readlink -f "$0")")/.." || exit 1
export NN_META_POOL=v31

# See run_v4_finalize.sh: create the marker empty at start so an interrupted
# run is auto-restartable, and so a job nobody launched here stays untouched.
MARKER="${JOB_EXIT_MARKER:-scripts/.jobstate/v4_full_run.exit}"
mkdir -p "$(dirname "$MARKER")" && : > "$MARKER"

echo "=== v4 ablation start: $(date) ==="
./venv/bin/python -m nn_meta.v4_evaluate --ablation \
  --seeds 0,1,2,3,4 --epochs 60 --gbt-estimators 600 --embargo 1D
ABLATION_EXIT=$?
echo "=== v4 ablation done: $(date), exit=$ABLATION_EXIT ==="

echo "=== v4 nested walk-forward start: $(date) ==="
./venv/bin/python -m nn_meta.v4_evaluate --folds 3 \
  --seeds 0,1,2,3,4 --epochs 60 --gbt-estimators 600 --embargo 1D
WF_EXIT=$?
echo "=== v4 nested walk-forward done: $(date), exit=$WF_EXIT ==="

if [ "$ABLATION_EXIT" -eq 0 ] && [ "$WF_EXIT" -eq 0 ]; then
  RUN_EXIT=0
else
  RUN_EXIT=1
fi
echo "V4-EXIT:$RUN_EXIT"
# Per-run exit marker for scripts/boot_restart.sh (0 => done, else => retry).
echo "$RUN_EXIT" > "$MARKER" 2>/dev/null || true

TOKEN=$(grep -m1 "^TELEGRAM_BOT_TOKEN=" .env | cut -d= -f2- | tr -d "\"'")
CHAT=$(grep -m1 "^TELEGRAM_CHAT_ID=" .env | cut -d= -f2- | tr -d "\"'")
if [ "$ABLATION_EXIT" -eq 0 ] && [ "$WF_EXIT" -eq 0 ]; then
  MSG="v4 full-scale run COMPLETE (ablation + nested walk-forward). Check nn_meta/reports_v31/v4_ablation_report.md and v4_walkforward_report.md"
else
  MSG="v4 full-scale run FAILED (ablation_exit=$ABLATION_EXIT wf_exit=$WF_EXIT). Check v4_v31.log for the traceback."
fi
curl -s -m 20 --retry 3 --retry-delay 20 \
  "https://api.telegram.org/bot${TOKEN}/sendMessage" -d chat_id="${CHAT}" \
  --data-urlencode text="$MSG" >/dev/null
exit 0
