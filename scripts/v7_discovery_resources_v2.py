"""Memory-aware admission for discovery; never terminate an admitted slice."""
from datetime import datetime
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
WORKER_MIB = 3072


def policy(now):
    local = now.astimezone(ZoneInfo('America/Chicago'))
    # Reserve space for the paper scanner before it starts; include daily V6.
    daytime = local.weekday() < 5 and 7 <= local.hour < 21
    return (2, 18432) if daytime else (4, 12288)


def worker_limit(maximum=4, *, now=None, available_mib=None, autosized=None):
    ceiling, reserve = policy(now or datetime.now().astimezone())
    if available_mib is None:
        fields = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
        available_mib = int(fields['MemAvailable'].split()[0]) // 1024
    # autosize has a floor of one; explicitly allow waiting with no new slices.
    if available_mib < reserve + WORKER_MIB:
        return 0
    if autosized is None:
        autosized = int(subprocess.check_output(['bash', '-c',
            'source scripts/lib/autosize.sh; autosize_workers "$1" "$2"',
            'v7-discovery-resources', str(WORKER_MIB), str(reserve)], cwd=ROOT, text=True).strip())
    return min(maximum, ceiling, autosized, (available_mib - reserve) // WORKER_MIB)
