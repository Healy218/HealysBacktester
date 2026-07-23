JOB_NAME="v3.1 walk-forward"
JOB_ID="v31_walkforward"
JOB_PROC_PATTERN="run_wf_v31|wf_prewarm|walkforward_meta"
# Legacy log-grep done-check, tightened to the SUCCESS marker only (was
# "WF-EXIT:" which also matched a failed "WF-EXIT:1"). Still shares the
# append-only-log staleness caveat; migrating run_wf_v31.sh to write the
# per-run exit marker (like run_v4_*.sh do) is a box-side follow-up.
JOB_DONE_CHECK='grep -q "WF-EXIT:0" v31_wf.log 2>/dev/null'
JOB_PRELAUNCH='
  ts=$(date +%s); bad=0
  for f in nn_meta/artifacts_v31/wf/fold*_spec*.json \
           nn_meta/artifacts_v31/wf/fold*_rows/done_shard*.json \
           nn_meta/artifacts_v31/wf/fold*_rows/done.json; do
    [ -f "$f" ] || continue
    if ! ./venv/bin/python -c "import json,sys; json.load(open(sys.argv[1]))" "$f" >/dev/null 2>&1; then
      mv "$f" "$f.corrupt.$ts"; bad=$((bad+1))
    fi
  done
  echo "${bad} corrupt checkpoint(s) quarantined"
'
JOB_LAUNCH_CMD='
  setsid nohup bash scripts/run_wf_v31.sh 3 >> v31_wf.log 2>&1 < /dev/null &
  sleep 5
  setsid nohup bash scripts/v31_wf_notify.sh >> v31_notify.log 2>&1 < /dev/null &
'
