JOB_NAME="v4 full-scale ablation + walk-forward"
JOB_PROC_PATTERN="run_v4_v31|v4_evaluate"
JOB_DONE_CHECK='grep -q "V4-EXIT:" v4_v31.log 2>/dev/null'
# No JOB_PRELAUNCH: v4_evaluate.py has no mid-run checkpointing yet, so a
# restart is a genuine from-scratch rerun, not a resume. Worth fixing in the
# evaluator itself eventually; nothing for this dispatcher to validate today.
JOB_LAUNCH_CMD='setsid nohup bash scripts/run_v4_v31.sh >> v4_v31.log 2>&1 < /dev/null &'
