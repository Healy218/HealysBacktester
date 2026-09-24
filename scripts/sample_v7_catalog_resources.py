#!/usr/bin/env python3
"""Record one read-only V7 build resource sample outside the active catalog."""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import os
import shutil
from pathlib import Path


def _integer(path: Path) -> int | None:
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def _cpu_temperature_c() -> float | None:
    for directory in Path("/sys/class/hwmon").glob("hwmon*"):
        try:
            if (directory / "name").read_text().strip() == "k10temp":
                value = _integer(directory / "temp1_input")
                return value / 1000 if value is not None else None
        except OSError:
            continue
    return None


def sample(output: Path, latest: Path, *, cgroup: Path) -> dict:
    if not output.is_dir():
        raise ValueError("active catalog output is unavailable")
    progress = json.loads(latest.read_text())
    observed = dt.datetime.now(dt.timezone.utc)
    prior = dt.datetime.fromisoformat(progress["observed_at"])
    if prior.tzinfo is None:
        raise ValueError("V7 progress timestamp lacks timezone")
    disk = shutil.disk_usage(output)
    cpu_stat = {}
    try:
        for line in (cgroup / "cpu.stat").read_text().splitlines():
            key, value = line.split()
            cpu_stat[key] = int(value)
    except (OSError, ValueError):
        pass
    return {
        "schema": "v7-catalog-resource-sample-v1",
        "observed_at": observed.isoformat(), "catalog": str(output.resolve()),
        "progress_observed_at": prior.isoformat(),
        "progress_age_seconds": (observed - prior).total_seconds(),
        "complete_securities": progress.get("complete_securities"),
        "proposal_stores": progress.get("proposals"),
        "output_bytes": progress.get("output_bytes"),
        "disk_free_bytes": disk.free,
        "disk_reserve_100gib_passed": disk.free >= 100 * 1024**3,
        "cgroup": str(cgroup), "memory_current_bytes": _integer(cgroup / "memory.current"),
        "memory_peak_bytes": _integer(cgroup / "memory.peak"),
        "cpu_usage_usec": cpu_stat.get("usage_usec"),
        "cpu_throttled_usec": cpu_stat.get("throttled_usec"),
        "cpu_temperature_c": _cpu_temperature_c(),
        "read_only_catalog": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--latest", type=Path, required=True)
    uid = os.getuid()
    default_cgroup = (Path("/sys/fs/cgroup/user.slice") / f"user-{uid}.slice" /
                      f"user@{uid}.service/app.slice/healys-v7-catalog-build.service")
    parser.add_argument("--cgroup", type=Path, default=default_cgroup)
    parser.add_argument("--append", type=Path, help="JSONL evidence log outside the catalog")
    args = parser.parse_args()
    result = sample(args.output, args.latest, cgroup=args.cgroup)
    if args.append:
        target = args.append.resolve()
        if target.is_relative_to(args.output.resolve()):
            parser.error("resource log cannot be written inside the active catalog")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            handle.write(json.dumps(result, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
