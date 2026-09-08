# nn_meta/live/heartbeat.py
"""Daily health ping for the three-expert scanner panel — so silence always
reads as 'quiet market', never 'is it dead?'.

One digest line per expert (v3 → logs/live_cron.log, [v4] → logs/v4_cron.log,
[v31] → logs/v31_cron.log): completed cron passes, RTH scan passes, alerts,
and — the important part — the number of NEW crashes per log since the last
heartbeat (tracebacks vs a stored per-log baseline). That catches both the
intermittent 'crashes only when a signal fires' failure mode and a
crashlooping expert cron, which a plain uptime check (or the old single-log
heartbeat) would miss.

Counting: the cron logs capture each pass's completion print (run_live:
"Outside RTH — nothing to scan." / "No fresh signals this pass." /
"N signal(s) alerted: …"; v4_scan: "Outside RTH …" / "[v4] scanned N ·
alerted N · …"). Those lines are unstamped, so per-expert counts are DELTAS
against the totals stored at the previous heartbeat — the daily cron makes
that "today". Scanner errors still come from the shared, timestamped
logs/backtester.log (FA-collector lines excluded — their transient 503s
would cry wolf).

State: ``.heartbeat_state.json`` now keys baselines per expert. The legacy
single-log schema ({"tracebacks": N}) is read as the v3 baseline; any log
without a stored baseline starts at its CURRENT counts (no false "NEW crash"
explosion on migration or a fresh host), and a missing log file is "no data
yet", never a crash.

Cron (daily, noon CT summer — the server cron ignores CRON_TZ):  0 17 * * *
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from nn_meta.live.notifier import get_notifier
from nn_meta.live.scanner import is_rth
from nn_meta.live.state import atomic_write_json

BACKTESTER_LOG = Path("logs/backtester.log")
STATE = Path("nn_meta/live/.heartbeat_state.json")

# digest order: the deployed v3 line first, then the paper experts
EXPERT_LOGS = {
    "v3": Path("logs/live_cron.log"),
    "v4": Path("logs/v4_cron.log"),
    "v31": Path("logs/v31_cron.log"),
    "v5": Path("logs/v5_cron.log"),       # 2026-09-05: the v5 wide-pool expert
}

# every expert cron fires */15 — an hour without a single write means the
# cron (not just the scan) is stuck, whatever the pass counters say
STALE_AFTER_MIN = 60

# streamed feeds (nn_meta/live/feeds): heartbeats every ~50 bars / 5 s
FEED_HEARTBEATS = {
    "stocks": Path("nn_meta/live/feeds/data/stock_stream.heartbeat.json"),
    "options": Path("nn_meta/live/feeds/data/option_stream.heartbeat.json"),
}
FEED_STALE_AFTER_MIN = 5

# 2026-09-08 review (fix 8): three conditions the digest reported but never
# escalated — "962 errors today", "feed options: 0 contracts", and a Sunday
# surface refresh that was OOM-killed two days earlier. Each now flips the
# head to ⚠️ so the one message a day cannot read "healthy" over them.
ERRORS_WARN_AFTER = 50                # scanner ERROR lines today before it warns
SURFACE_STALE_DAYS = 8                # weekly refresh + one day of slack
SURFACE_FILES = {                     # pool → the IV-surface file its expert scans on
    "v3": Path("nn_meta/data_cache/surface_daily.parquet"),
    "v31": Path("nn_meta/data_cache_v3/surface_daily.parquet"),
    "v5": Path("nn_meta/data_cache_v5/surface_daily.parquet"),
}
REFRESH_STATUS_DIR = Path("logs/refresh_status")   # scripts/run_refresh.sh writes <pool>.json


def _read_json(path: Path):
    if not path.exists():
        return None
    try:
        import json as _json
        return _json.loads(path.read_text())
    except Exception:
        return None

_ALERTED_RUN_LIVE = re.compile(r"^(\d+) signal\(s\) alerted: ")
_ALERTED_V4 = re.compile(r"^\[v[45]\] scanned \d+ · alerted (\d+)")   # v4_scan prints [v4] or [v5]


def _today_lines() -> tuple[list[str], str]:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not BACKTESTER_LOG.exists():
        return [], today
    lines = [ln for ln in BACKTESTER_LOG.read_text(errors="ignore").splitlines()
             if ln.startswith(today)]
    return lines, today


def _scan_counts(log: Path) -> dict:
    """Life-to-date totals for one cron log (all zeros when it is missing).

    ``passes`` counts every completed invocation (incl. the outside-RTH
    no-ops), ``rth_scans`` only passes that actually scanned; both formats
    (run_live and v4_scan) are recognized so the map stays config-free.
    """
    counts = {"passes": 0, "rth_scans": 0, "alerts": 0, "tracebacks": 0}
    if not log.exists():
        return counts
    text = log.read_text(errors="ignore")
    counts["tracebacks"] = text.count("Traceback")
    for ln in text.splitlines():
        if ln.startswith("Outside RTH"):
            counts["passes"] += 1
        elif ln.startswith("No fresh signals this pass"):
            counts["passes"] += 1
            counts["rth_scans"] += 1
        elif m := (_ALERTED_RUN_LIVE.match(ln) or _ALERTED_V4.match(ln)):
            counts["passes"] += 1
            counts["rth_scans"] += 1
            counts["alerts"] += int(m.group(1))
    return counts


def _load_baselines() -> dict:
    """Per-expert baseline counts from the state file.

    Old single-log schema ({"tracebacks": N, "at": …}) maps to the v3 entry —
    that counter always was live_cron.log's traceback total. Unknown/absent
    entries stay absent: the caller defaults each missing metric to its
    current value, so migration and fresh hosts report 0 new, not the whole
    log history.
    """
    if not STATE.exists():
        return {}
    try:
        state = json.loads(STATE.read_text())
    except Exception:
        return {}
    if isinstance(state.get("logs"), dict):
        return {k: v for k, v in state["logs"].items() if isinstance(v, dict)}
    if "tracebacks" in state:                       # legacy single-log schema
        return {"v3": {"tracebacks": state["tracebacks"]}}
    return {}


def _plural(n: int, word: str, plural: str | None = None) -> str:
    return f"{n} {word if n == 1 else (plural or word + 's')}"


def build_message() -> str:
    lines, today = _today_lines()
    # scanner errors only — the FA collectors (edgar/news/reddit) share this
    # log and have their own transient failures (e.g. EDGAR 503s); counting
    # those here would cry wolf and train the reader to ignore the heartbeat.
    errors_today = sum(" - ERROR - " in ln and "[fa." not in ln for ln in lines)

    now = datetime.now(timezone.utc)
    rth = is_rth()
    baselines = _load_baselines()
    warnings: list[str] = []
    digest: list[str] = []
    totals: dict[str, dict] = {}

    # Live feeds (2026-09-05): a dead stream is silent — the scanners just fall
    # back to REST — so the heartbeat is where it must surface.
    for fname, fpath in FEED_HEARTBEATS.items():
        try:
            hb = _read_json(fpath)
            if not hb:
                # No file = the feed is not deployed on this host (box, tests);
                # only a heartbeat that EXISTS and went stale is a failure.
                digest.append(f"feed {fname}: not deployed here")
                continue
            age_min = (now - datetime.fromisoformat(hb["ts"])).total_seconds() / 60
            extra = (f"{hb.get('symbols', '?')} symbols · last bar {hb.get('last_bar', '—')}"
                     if fname == "stocks" else
                     f"{hb.get('contracts', 0)} contracts · {hb.get('quotes', 0)} quotes")
            digest.append(f"feed {fname}: {extra} · heartbeat {age_min:.0f} min ago"
                          + (f" · {hb['state']}" if hb.get("state") not in (None, "streaming") else ""))
            if rth and age_min > FEED_STALE_AFTER_MIN:
                warnings.append(f"⚠️ feed {fname}: heartbeat {age_min:.0f} min old during "
                                f"market hours — stream DOWN, scanners on REST fallback")
            elif rth and fname == "options" and not hb.get("contracts"):
                warnings.append("⚠️ feed options: 0 contracts subscribed during market "
                                "hours — nothing streams until the alert path registers "
                                "contracts (option_watch.json)")
        except Exception as e:                    # never sink the digest
            digest.append(f"feed {fname}: unreadable ({e})")

    for name, log in EXPERT_LOGS.items():
        # Per-expert isolation (P1-2, 2026-08-16 review): one unreadable log
        # must degrade to ITS ⚠️ line, not silently abort the whole digest.
        try:
            cur = _scan_counts(log)
            totals[name] = cur
            base = baselines.get(name, {})
            grace = "passes" not in base            # no stored pass window yet
            # Rotation/truncation (P1-3): any counter below its baseline means
            # the log was rotated — reset to counting the fresh log instead of
            # clamping deltas to 0 (which masked real crashes AND fired false
            # "0 passes" DOWN warnings on healthy experts).
            rotated = any(v < base.get(k, v) for k, v in cur.items())
            delta = dict(cur) if rotated \
                else {k: v - base.get(k, v) for k, v in cur.items()}

            if not log.exists():
                digest.append(f"{name}: no log yet")
                if rth:
                    warnings.append(f"⚠️ {name}: cron log missing during market "
                                    f"hours — cron may be DOWN ({log})")
                continue

            if grace:
                digest.append(f"{name}: baseline set — counts start next heartbeat")
            else:
                digest.append(
                    f"{name}: {_plural(delta['passes'], 'pass', 'passes')} "
                    f"({delta['rth_scans']} RTH) · "
                    f"{_plural(delta['alerts'], 'alert')} · "
                    f"{delta['tracebacks']} new crash"
                    f"{'' if delta['tracebacks'] == 1 else 'es'}"
                    + (" · log rotated — counters reset" if rotated else ""))

            if rth:
                age_min = (now - datetime.fromtimestamp(
                    log.stat().st_mtime, tz=timezone.utc)).total_seconds() / 60
                if age_min > STALE_AFTER_MIN:
                    warnings.append(f"⚠️ {name}: cron log stale ({age_min:.0f}m "
                                    f"old) during market hours — cron may be DOWN")
                elif not grace and not rotated and delta["rth_scans"] == 0:
                    warnings.append(f"⚠️ {name}: 0 scan passes since the last "
                                    f"heartbeat during market hours — cron or "
                                    f"scanner may be DOWN")
            if delta["tracebacks"] > 0:
                warnings.append(f"⚠️ {name}: {delta['tracebacks']} NEW crash(es) "
                                f"since the last heartbeat — check {log}")
        except Exception as exc:
            totals.pop(name, None)      # keep this expert's old baseline
            digest.append(f"{name}: unreadable ({exc.__class__.__name__})")
            warnings.append(f"⚠️ {name}: could not read {log} "
                            f"({exc.__class__.__name__}: {exc}) — investigate")

    digest.extend(_surface_lines(now, warnings))
    if errors_today > ERRORS_WARN_AFTER:
        warnings.append(f"⚠️ {errors_today} scanner errors today (> {ERRORS_WARN_AFTER}) "
                        f"— check {BACKTESTER_LOG}")

    status = "market open" if rth else "market closed"
    head = (f"⚠️ Scanner heartbeat — {today}" if warnings
            else f"🩺 Scanners healthy — {today}")
    footer = f"{_plural(errors_today, 'error')} today · {status}"
    new_state = {"logs": {**baselines, **totals}, "at": now.isoformat()}
    return "\n".join([head, *warnings, *digest, footer]), new_state


def _surface_lines(now: datetime, warnings: list[str]) -> list[str]:
    """One digest line for surface ages plus the last recorded refresh outcome
    per pool; appends to ``warnings`` when a surface is older than
    SURFACE_STALE_DAYS or the last refresh run exited non-zero."""
    parts = []
    for pool, path in SURFACE_FILES.items():
        try:
            if not path.exists():
                parts.append(f"{pool} —")
                continue
            age_d = (now - datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
                     ).total_seconds() / 86400
            parts.append(f"{pool} {age_d:.0f}d")
            if age_d > SURFACE_STALE_DAYS:
                warnings.append(f"⚠️ {pool}: IV surface is {age_d:.0f} days old "
                                f"(> {SURFACE_STALE_DAYS}) — Sunday refresh failed or "
                                f"never ran; expert scores on stale context")
        except Exception as exc:                  # never sink the digest
            parts.append(f"{pool} unreadable ({exc.__class__.__name__})")
        st = _read_json(REFRESH_STATUS_DIR / f"{pool}.json")
        if isinstance(st, dict) and st.get("exit_code") not in (None, 0):
            warnings.append(f"⚠️ {pool}: last surface refresh exited {st.get('exit_code')} "
                            f"at {st.get('finished', '?')} — see {st.get('log', 'its log')}")
    return [f"surfaces: {' · '.join(parts)}"] if parts else []


def persist_state(state: dict) -> None:
    atomic_write_json(STATE, state)


def main() -> None:
    msg, state = build_message()
    # Persist baselines ONLY after a successful send (P1-1): a failed POST
    # must not consume the deltas — otherwise those crashes are never
    # reported by any future digest.
    if get_notifier().send(msg, title="Scanner heartbeat"):
        persist_state(state)
    else:
        print("⚠️ heartbeat send FAILED — baselines retained, deltas will "
              "re-report next run")
    print(msg)


if __name__ == "__main__":
    main()
