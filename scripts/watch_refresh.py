"""Hourly progress report for a pool's surface refresh, to Telegram and stdout.

    ./venv/bin/python -m scripts.watch_refresh --pool v5            # every hour until done
    ./venv/bin/python -m scripts.watch_refresh --pool v5 --once     # one report, no send loop
    ./venv/bin/python -m scripts.watch_refresh --pool v5 --dry-run  # console instead of Telegram

Reads what ``scripts/run_refresh.sh`` leaves behind — ``logs/refresh_status/<pool>.json``,
``logs/surface_refresh_<pool>.log`` — plus the live process table (download or
build step, elapsed, RSS) and the surface file's age. Exits after reporting a
finished (or failed) run, or after ``--max-hours``. Never touches the run.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = {"nn_meta.download_universe": "download", "nn_meta.build_surface": "build_surface"}


def _proc_env_pool(pid: int) -> str | None:
    try:
        env = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
    except OSError:
        return None
    for kv in env:
        if kv.startswith(b"NN_META_POOL="):
            return kv.split(b"=", 1)[1].decode(errors="ignore")
    return None


def refresh_processes(pool: str) -> list[dict]:
    """Live download/build processes for ``pool``: [{pid, step, elapsed_s, rss_mb}]."""
    out = []
    try:
        hz = os.sysconf("SC_CLK_TCK")
        btime = next(int(ln.split()[1]) for ln in Path("/proc/stat").read_text().splitlines()
                     if ln.startswith("btime "))
    except Exception:
        return out
    for d in Path("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            cmd = d.joinpath("cmdline").read_bytes().replace(b"\0", b" ").decode(errors="ignore")
        except OSError:
            continue
        step = next((v for k, v in STEPS.items() if f"-m {k}" in cmd), None)
        if step is None or _proc_env_pool(int(d.name)) != pool:
            continue
        try:
            start_ticks = int(d.joinpath("stat").read_text().rsplit(")", 1)[1].split()[19])
            elapsed = time.time() - (btime + start_ticks / hz)
            rss_kb = next(int(ln.split()[1]) for ln in d.joinpath("status").read_text().splitlines()
                          if ln.startswith("VmRSS:"))
        except Exception:
            elapsed, rss_kb = -1, 0
        out.append({"pid": int(d.name), "step": step, "elapsed_s": elapsed, "rss_mb": rss_kb // 1024})
    return out


def gather(pool: str, root: Path = ROOT) -> dict:
    status_p = root / "logs" / "refresh_status" / f"{pool}.json"
    try:
        status = json.loads(status_p.read_text()) if status_p.exists() else None
    except Exception:
        status = None
    from nn_meta import config      # NN_META_POOL is set by main() before import
    surf = config.SURFACE_DATASET_PARQUET
    surface_age_h = ((time.time() - surf.stat().st_mtime) / 3600) if surf.exists() else None
    log = root / "logs" / f"surface_refresh_{pool}.log"
    tail = ""
    if log.exists():
        lines = [ln.strip() for ln in log.read_text(errors="ignore").splitlines()[-40:] if ln.strip()]
        tail = lines[-1] if lines else ""
    return {"pool": pool, "status": status, "processes": refresh_processes(pool),
            "surface_age_h": surface_age_h, "tail": tail[:160],
            "now": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def _hm(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


def verdict(info: dict) -> tuple[str, bool]:
    """(state line, finished?) — finished means nothing is running and the
    status file records a final exit code (or a failure)."""
    procs, st = info["processes"], info["status"] or {}
    code = st.get("exit_code")
    if procs:
        p = max(procs, key=lambda x: x["elapsed_s"])
        return (f"running · {p['step']} {_hm(p['elapsed_s'])} · {p['rss_mb']} MB RSS "
                f"(pid {p['pid']})"), False
    if code == 0:
        return f"FINISHED OK · {st.get('step', '?')} at {st.get('finished', '?')}", True
    if code is None:
        return "no run recorded and nothing running", True
    if code == -1:
        return "NOT RUNNING but status still says in progress — killed? check the log", True
    return f"FAILED · {st.get('step', '?')} exit {code} at {st.get('finished', '?')}", True


def format_report(info: dict) -> tuple[str, bool]:
    state, done = verdict(info)
    age = info["surface_age_h"]
    age_s = "missing" if age is None else (f"{age * 60:.0f} min" if age < 2 else f"{age / 24:.1f} d" if age > 48 else f"{age:.1f} h")
    st = info["status"] or {}
    lines = [f"🧮 {info['pool']} surface refresh — {info['now'][11:16]} UTC",
             state,
             f"surface file: {age_s} old",
             f"started {st.get('started', '?')} · workers {st.get('workers', '?')}" if st else "no status file",
             f"log: {info['tail']}" if info["tail"] else "log: (empty)"]
    return "\n".join(lines), done


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pool", required=True)
    ap.add_argument("--interval", type=float, default=3600.0, help="seconds between reports")
    ap.add_argument("--max-hours", type=float, default=36.0)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="console notifier")
    args = ap.parse_args()
    os.environ["NN_META_POOL"] = args.pool
    os.chdir(ROOT)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    from nn_meta.live.notifier import get_notifier
    notifier = get_notifier(force_console=args.dry_run)
    t0 = time.time()
    while True:
        msg, done = format_report(gather(args.pool))
        print(msg, flush=True); print("---", flush=True)
        notifier.send(msg, title=f"{args.pool} surface refresh")
        if done or args.once or time.time() - t0 > args.max_hours * 3600:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
