JOB_NAME="v4 full-scale ablation + walk-forward"
JOB_ID="v4_full_run"
JOB_PROC_PATTERN="run_v4_v31|v4_evaluate"
# Done semantics come from the per-run exit marker (scripts/.jobstate/
# v4_full_run.exit) written by run_v4_v31.sh; a failed run is retried, a stale
# marker from a previous run no longer blocks a re-run.
# No JOB_PRELAUNCH: v4_evaluate.py has no mid-run checkpointing yet, so a
# restart is a genuine from-scratch rerun, not a resume. Worth fixing in the
# evaluator itself eventually; nothing for this dispatcher to validate today.
JOB_LAUNCH_CMD='setsid nohup bash scripts/run_v4_v31.sh >> v4_v31.log 2>&1 < /dev/null &'
