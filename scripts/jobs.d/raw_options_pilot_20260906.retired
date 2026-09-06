# Sourced by the existing recovery dispatcher; this descriptor starts nothing itself.
JOB_NAME="Raw options v6 pilot 2026-09-06 r2 (SPY, IBKR)"
JOB_ID="raw_options_pilot_20260906"
JOB_PROC_PATTERN='[r]un_raw_options_pilot_20260906[.]sh|[s]cripts[.]research_local.*--campaign raw-options-20260906-r2'
JOB_LAUNCH_CMD='
mkdir -p logs
setsid nohup bash scripts/run_raw_options_pilot_20260906.sh >> logs/raw-options-20260906-r2-pilot.log 2>&1 < /dev/null &
'
