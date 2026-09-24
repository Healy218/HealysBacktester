"""Read-only hourly Telegram/status observer for the V7 full catalog."""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINUTES = (5, 15, 30)
LOG_DIRS = (
    Path("/tmp/v7-2-full-catalog-20260922-rebuild-5-15-30-logs"),
)
CURRENT_COVERAGE = (
    ROOT / "nn_meta/validation/v7-action-coverage-20260921-7-2-repaired",
    ROOT / "nn_meta/validation/v7-action-coverage-20260924-reviewed-v2",
)


def snapshot(output: Path, history: Path) -> dict:
    import pandas as pd
    selected = pd.read_parquet(history / "history.parquet",
                               columns=["security_id", "source_date", "source_status"])
    ids = sorted(selected.security_id.unique())
    observed = selected[selected.source_status.eq("observed")][["security_id", "source_date"]]
    deferred = None
    if all((path / "coverage.parquet").exists() for path in CURRENT_COVERAGE):
        admitted = set()
        for path in CURRENT_COVERAGE:
            panel = pd.read_parquet(path / "coverage.parquet",
                                    columns=["security_id", "source_date", "history_admitted"])
            matching = observed.merge(panel[panel.history_admitted.astype(bool)],
                                      on=["security_id", "source_date"], how="inner",
                                      validate="one_to_one")
            admitted.update(matching.security_id)
        deferred = len(set(ids) - admitted)
    timeframe_total = len(ids) * len(MINUTES)
    proposals = features = feature_stores = complete_securities = 0
    active = []
    now = time.time()
    for security_id in ids:
        security_done = True
        logs = [directory / f"{security_id}.log" for directory in LOG_DIRS]
        if any(log.exists() and now - log.stat().st_mtime < 900 for log in logs):
            active.append(security_id)
        for minutes in MINUTES:
            base = output / security_id / str(minutes)
            features += sum((base / "features" / name / "complete.json").exists()
                            for name in ("declaration", "basis"))
            feature_stores += int((base / "features" / "summary" / "complete.json").exists())
            proposal_done = (base / "proposals" / "summary" / "complete.json").exists()
            proposals += int(proposal_done)
            security_done &= proposal_done
        complete_securities += int(security_done)
    usage = shutil.disk_usage(output)
    service = subprocess.run(
        ["systemctl", "--user", "show", "healys-v7-catalog-build.service",
         "-p", "ActiveState", "-p", "ExecMainStatus", "-p", "NRestarts"],
        capture_output=True, text=True, timeout=10, check=False)
    state = dict(line.split("=", 1) for line in service.stdout.splitlines() if "=" in line)
    recovery = output.parent / "v7-2-catalog-reuse-20260924.json"
    recovery_id = hashlib.sha256(recovery.read_bytes()).hexdigest() if recovery.is_file() else None
    return {
        "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "securities": len(ids), "complete_securities": complete_securities,
        "deferred_unadmitted": deferred,
        "features_receipts": features, "feature_stores": feature_stores,
        "proposals": proposals, "timeframe_total": timeframe_total,
        "active_logs": active,
        "build_state": state.get("ActiveState", "unknown"),
        "build_exit_status": state.get("ExecMainStatus", "unknown"),
        "build_restarts": state.get("NRestarts", "unknown"),
        "recovery_id": recovery_id,
        "disk_free_bytes": usage.free,
    }


def estimate_eta(current: dict, history_path: Path) -> str:
    """Estimate completion from the observer's own persisted snapshots."""
    total = current["securities"]
    done = current["complete_securities"]
    deferred = current.get("deferred_unadmitted") or 0
    runnable = total - deferred
    if done >= total:
        return "ETA: complete"
    if deferred and done >= runnable:
        return f"Runnable build complete; {deferred} input-blocked securities remain"
    snapshots = []
    if history_path.exists():
        for line in history_path.read_text().splitlines():
            try:
                item = json.loads(line)
                if (item.get("securities") == total
                        and item.get("deferred_unadmitted") == current.get("deferred_unadmitted")
                        and item.get("recovery_id") == current.get("recovery_id")):
                    snapshots.append(item)
            except (json.JSONDecodeError, TypeError):
                continue
    if snapshots:
        try:
            first_at = dt.datetime.fromisoformat(snapshots[0]["observed_at"])
            current_at = dt.datetime.fromisoformat(current["observed_at"])
            elapsed_hours = (current_at - first_at).total_seconds() / 3600
            prior_done = int(snapshots[0]["complete_securities"])
            rate = (done - prior_done) / elapsed_hours if elapsed_hours > 0 else 0
            # A few freshly sealed stores can make the first minutes look
            # unrealistically fast. Wait for a full hour of this exact run.
            if elapsed_hours >= 1 and rate > 0:
                hours_left = (runnable - done) / rate
                finish = dt.datetime.now().astimezone() + dt.timedelta(hours=hours_left)
                label = "Runnable ETA" if deferred else "ETA"
                return f"{label}: ~{hours_left:.1f}h (around {finish:%Y-%m-%d %H:%M %Z})"
        except (KeyError, TypeError, ValueError):
            pass
    return ("Runnable ETA: waiting for one hour of completed-security rate" if deferred
            else "ETA: calculating from completed-security rate")


def render(s: dict, eta: str) -> str:
    total = s["timeframe_total"]
    pct = 100.0 * s["proposals"] / total if total else 100.0
    active = ", ".join(s["active_logs"][:4]) or "none observed"
    gib = lambda n: n / 1024**3
    build_state = s.get("build_state", "unknown")
    return (
        "V7 catalog hourly update\n"
        f"Proposal stores: {s['proposals']}/{total} ({pct:.2f}%)\n"
        f"Feature receipts: {s['features_receipts']} "
        f"(sealed feature stores: {s['feature_stores']})\n"
        f"Complete securities: {s['complete_securities']}/{s['securities']}\n"
        + (f"Input-blocked in this run: {s['deferred_unadmitted']} securities\n"
           if s.get('deferred_unadmitted') is not None else "") +
        f"Build service: {build_state} (exit {s.get('build_exit_status', 'unknown')}; "
        f"restarts {s.get('build_restarts', 'unknown')})\n"
        f"Active workers/logs: {active}\n"
        f"Disk free: {gib(s['disk_free_bytes']):.1f} GiB\n"
        "Research-ready: no; catalog build is validation-only.\n"
        f"{eta}"
    )


def send_telegram(root: Path, message: str) -> None:
    from dotenv import dotenv_values
    env = dotenv_values(root / ".env")
    token, chat = env.get("TELEGRAM_BOT_TOKEN"), env.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        raise RuntimeError("Telegram credentials missing")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps({"chat_id": chat, "text": message}).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            if json.load(response).get("ok") is not True:
                raise RuntimeError("Telegram rejected update")
    except Exception:
        raise RuntimeError("Telegram delivery failed; local report retained") from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "nn_meta/validation/v7-2-full-catalog-20260922-rebuild-5-15-30")
    parser.add_argument("--history", type=Path,
                        default=ROOT / "nn_meta/validation/v7-security-history-20260918-7-2-current")
    parser.add_argument("--telegram", action="store_true")
    parser.add_argument("--follow", action="store_true",
                        help="Keep refreshing in the foreground until the catalog completes")
    parser.add_argument("--interval", type=float, default=5.0,
                        help="Seconds between --follow snapshots")
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("--interval must be positive")
    out = ROOT / "logs/v7-progress" / args.output.name
    out.mkdir(parents=True, exist_ok=True)
    while True:
        with (out / ".lock").open("a") as lock:
            # A foreground --follow viewer must release this between refreshes
            # so the scheduled hourly observer can still publish its report.
            fcntl.flock(lock, fcntl.LOCK_EX)
            current = snapshot(args.output, args.history)
            history_path = out / "history.jsonl"
            message = render(current, estimate_eta(current, history_path))
            (out / "latest.json.tmp").write_text(json.dumps(current, indent=2) + "\n")
            (out / "latest.json.tmp").replace(out / "latest.json")
            (out / "progress.txt").write_text(message + "\n")
            with history_path.open("a") as history:
                history.write(json.dumps(current) + "\n")
        print("\033[2J\033[H" + message if args.follow else message, flush=True)
        if args.telegram:
            send_telegram(ROOT, message)
            print("Telegram update delivered.", flush=True)
        if (not args.follow or current["complete_securities"] == current["securities"]
                or current["build_state"] in ("failed", "inactive")):
            break
        time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
