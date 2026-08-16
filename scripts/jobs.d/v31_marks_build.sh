# v3.1 marks dataset build (rows + mark streams + assemble) — resumable via
# per-symbol checkpoints; a reboot loses only in-flight symbols.
JOB_NAME="v31 marks dataset build"
JOB_ID="v31_marks_build"
JOB_PROC_PATTERN="nn_meta.build_meta_dataset"
JOB_LAUNCH_CMD='setsid nohup bash scripts/run_build_parallel.sh > v31_marks_build.log 2>&1 < /dev/null &'
