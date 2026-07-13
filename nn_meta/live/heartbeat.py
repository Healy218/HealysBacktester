# nn_meta/live/heartbeat.py
"""Daily scanner health ping to Telegram — so silence always reads as 'quiet
market', never 'is it dead?'.

Reports today's scan passes and signals, and — the important part — the
number of NEW crashes since the last heartbeat (tracebacks in the cron log
vs a stored baseline). That catches the intermittent 'crashes only when a
signal fires' failure mode, which a plain uptime check would miss.

Cron (noon Central, daily):  CRON_TZ=America/Chicago ; 0 12 * * *
"""
import json
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from nn_meta.live.notifier import get_notifier
from nn_meta.live.scanner import is_rth

BACKTESTER_LOG = Path("logs/backtester.log")
CRON_LOG = Path("logs/live_cron.log")
STATE = Path("nn_meta/live/.heartbeat_state.json")


def _today_lines() -> tuple[list[str], str]:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not BACKTESTER_LOG.exists():
        return [], today
    lines = [ln for ln in BACKTESTER_LOG.read_text(errors="ignore").splitlines()
             if ln.startswith(today)]
    return lines, today


def _new_crashes() -> int:
    """Tracebacks in the cron log since the last heartbeat (0 on first run)."""
    total = (CRON_LOG.read_text(errors="ignore").count("Traceback")
             if CRON_LOG.exists() else 0)
    prev = total
    if STATE.exists():
        try:
            prev = json.loads(STATE.read_text()).get("tracebacks", total)
        except Exception:
            pass
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"tracebacks": total,
                                 "at": datetime.now(timezone.utc).isoformat()}))
    return max(0, total - prev)


def build_message() -> str:
    lines, today = _today_lines()
    passes = sum("NN filter enabled" in ln for ln in lines)
    signals = sum("notify:telegram] sent:" in ln
                  and ("BUY CALL" in ln or "BUY PUT" in ln) for ln in lines)
    # scanner errors only — the FA collectors (edgar/news/reddit) share this
    # log and have their own transient failures (e.g. EDGAR 503s); counting
    # those here would cry wolf and train the reader to ignore the heartbeat.
    errors_today = sum(" - ERROR - " in ln and "[fa." not in ln for ln in lines)
    new_crashes = _new_crashes()
    rth = is_rth()
    status = "market open" if rth else "market closed"

    if passes == 0 and rth:
        return (f"⚠️ Scanner: 0 passes recorded today ({today}) during market "
                f"hours — the cron or scanner may be DOWN. Check the server.")
    if new_crashes > 0:
        return (f"⚠️ Scanner: {new_crashes} NEW crash(es) since the last "
                f"heartbeat — check logs. ({passes} passes, {signals} signals "
                f"today · {status})")
    sig = f"{signals} signal{'s' if signals != 1 else ''}"
    return (f"🩺 Scanner healthy — {today}\n"
            f"{passes} passes · {errors_today} errors · {sig} today\n"
            f"({status})")


def main() -> None:
    msg = build_message()
    get_notifier().send(msg, title="Scanner heartbeat")
    print(msg)


if __name__ == "__main__":
    main()
