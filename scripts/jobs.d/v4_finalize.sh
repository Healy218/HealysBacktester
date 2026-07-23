JOB_NAME="v4 finalize (train + persist model_final_v4)"
JOB_ID="v4_finalize"
JOB_PROC_PATTERN="run_v4_finalize|v4_finalize"
# Done semantics come from the per-run exit marker (scripts/.jobstate/
# v4_finalize.exit) written by run_v4_finalize.sh — a FAILED run (non-zero,
# or v4_finalize's own exit 1 when no config clears the gate) is retried, not
# treated as done. No JOB_DONE_CHECK grep, which used to match both success
# and failure and never reset across re-runs.
# No JOB_PRELAUNCH: v4_finalize.py now trains into a .staging dir and atomic-
# swaps, so a crash leaves the previous bundle intact; a restart is a clean
# from-scratch rerun with nothing to quarantine.
JOB_LAUNCH_CMD='setsid nohup bash scripts/run_v4_finalize.sh >> v4_finalize.log 2>&1 < /dev/null &'
