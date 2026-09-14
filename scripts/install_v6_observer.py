"""Install the verified V6 recording observer beside the production checkout."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess

from nn_meta.live.v6_release import sha, verify_release

ROOT = Path(__file__).resolve().parents[1]


def install(args):
    release = ROOT / "deploy/v6/releases/v6-cash-repair-20260913"
    anchor = (release / "release.sha256").read_text().strip()
    verified = verify_release(release, anchor)
    production = args.production.absolute()
    python = production / "venv/bin/python"
    state = ROOT / "nn_meta/live/v6_server"
    command = [str(python), "-m", "scripts.run_v6_server", "--release", str(release),
               "--anchor", anchor, "--state", str(state),
               "--snapshot-index", str(state / "incoming/latest.json"),
               "--feed-heartbeat", str(production / "nn_meta/live/feeds/data/option_stream.heartbeat.json")]
    if any(any(c in arg for c in ('\n', '\r', '%', '"', '\\')) for arg in command):
        raise ValueError("unsupported systemd argument character")
    service = f"""[Unit]
Description=V6 frozen model recording observer (alerts disabled)
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory={ROOT}
Environment=OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 TF_NUM_INTRAOP_THREADS=1 TF_NUM_INTEROP_THREADS=1 TF_CPP_MIN_LOG_LEVEL=2 CUDA_VISIBLE_DEVICES=-1
ExecStart={' '.join(chr(34) + arg + chr(34) for arg in command)}
TimeoutStartSec=720
CPUQuota=100%
MemoryMax=2500M
Nice=10
UMask=0077
"""
    timer = """[Unit]
Description=Check V6 release and available forward inputs every quarter hour

[Timer]
OnCalendar=*-*-* *:06,21,36,51:00
OnBootSec=2min
Persistent=true
Unit=healys-v6-observer.service

[Install]
WantedBy=timers.target
"""
    plan = {"root": str(ROOT), "production": str(production), "model_sha256": verified["model_sha256"],
            "release_sha256": anchor, "alerts_enabled": False, "selftest": [*command, "--selftest"],
            "units": {"healys-v6-observer.service": service, "healys-v6-observer.timer": timer}}
    if not args.run:
        print(json.dumps(plan, indent=2))
        return
    # Run the actual saved-row replay before installing any scheduler.
    env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
    subprocess.run([*command, "--selftest"], cwd=ROOT, env=env, check=True)
    destination = Path.home() / ".config/systemd/user"
    destination.mkdir(parents=True, exist_ok=True)
    backup = state / "installations" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup.mkdir(parents=True)
    for name, content in plan["units"].items():
        target = destination / name
        if target.exists():
            (backup / (name + ".before")).write_bytes(target.read_bytes())
        (backup / name).write_text(content)
    subprocess.run(["systemd-analyze", "--user", "verify", str(backup / "healys-v6-observer.service"),
                    str(backup / "healys-v6-observer.timer")], check=True)
    for name, content in plan["units"].items():
        (destination / name).write_text(content)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", "healys-v6-observer.timer"], check=True)
    subprocess.run(["systemctl", "--user", "start", "healys-v6-observer.service"], check=True)
    (backup / "receipt.json").write_text(json.dumps({**plan, "installed": True}, indent=2) + "\n")
    print(json.dumps({"installed": True, "receipt": str(backup / "receipt.json"), "alerts_enabled": False}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--production", required=True, type=Path)
    ap.add_argument("--run", action="store_true")
    install(ap.parse_args())
