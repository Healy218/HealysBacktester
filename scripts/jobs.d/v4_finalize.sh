JOB_NAME="v4 finalize (train + persist model_final_v4)"
JOB_PROC_PATTERN="run_v4_finalize|v4_finalize"
JOB_DONE_CHECK='grep -q "V4-FINALIZE-EXIT:" v4_finalize.log 2>/dev/null'
# No JOB_PRELAUNCH: v4_finalize.py wipes model_final_v4/ at the start of its
# persist step, so a restart is a genuine from-scratch rerun, same known
# limitation as v4_full_run.sh.
JOB_LAUNCH_CMD='setsid nohup bash scripts/run_v4_finalize.sh >> v4_finalize.log 2>&1 < /dev/null &'
