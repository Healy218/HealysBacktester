#!/usr/bin/env bash
# Shared worker/shard sizing for the parallel launchers.
#
# Every launcher used to carry a hardcoded constant chosen to fit the retired
# WSL2 box's 12GB .wslconfig cap. Native Pop!_OS has no such cap, but it does
# have a desktop competing for the same 15.5GB — so the right count is not a
# bigger constant, it is whatever fits right now. Measured 2026-07-30 with
# VS Code + Claude Desktop + Firefox open: MemAvailable was 9.3GB of 15.5GB,
# i.e. the desktop alone can cost more headroom than the old WSL cap did.
#
# NOTE ON SWAP: this box shows ~19GB of swap, but 15.5GB of that is zram —
# compressed RAM carved out of the same 15.5GB, not extra capacity, and close
# to worthless for the incompressible float arrays these workers hold. Only
# the 4GB disk partition is real, and hitting it is ruinously slow. So size
# against MemAvailable and never count swap as headroom.

# autosize_workers <per_worker_mb> [reserve_mb]
#   Echoes a worker count that fits current free memory, floor 1, capped at
#   the thread count. MemAvailable (not MemFree) because it accounts for
#   reclaimable page cache, which is most of what a finished build leaves.
autosize_workers(){
  local per_worker_mb=$1 reserve_mb=${2:-2048} avail_mb n cpus
  avail_mb=$(awk '/^MemAvailable:/{print int($2/1024)}' /proc/meminfo)
  n=$(( (avail_mb - reserve_mb) / per_worker_mb ))
  [ "$n" -lt 1 ] && n=1
  cpus=$(nproc)
  [ "$n" -gt "$cpus" ] && n=$cpus
  echo "$n"
}

# autosize_report <label> <n>
#   One line so a run log records WHY it picked that count.
autosize_report(){
  printf '%s: %s workers (MemAvailable %.1fGB, %s threads)\n' \
    "$1" "$2" "$(awk '/^MemAvailable:/{print $2/1048576}' /proc/meminfo)" "$(nproc)"
}
