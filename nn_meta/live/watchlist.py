# nn_meta/live/watchlist.py
"""Dual-mode cadence, mode two: the daily top-N watchlist (ROADMAP wave-2
item 5, user decision 2026-08-16).

The conviction pings stay threshold-gated; this records EVERY scored winner
(one best-DTE row per fresh signal, above or below the threshold) during the
scanner's normal passes, and a once-daily digest sends the day's top-N as
"flow to browse". Each entry's forward outcome is resolved later against the
underlying's bars over the variant's DTE horizon, so the digest can carry a
rolling hit-rate and the threshold dial becomes data-driven.

Honesty note: the hit-rate is DIRECTIONAL ON THE UNDERLYING (did spot move
the signal's way by resolution time), not option P&L — the scanner never
prices contracts. The digest says so.

State: one JSON file per expert (``.v4_watchlist.json``), same atomic-write
idiom as the other live state; entries pruned after ``KEEP_DAYS``.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from nn_meta.live.state import _load_json, atomic_write_json, refreshed

KEEP_DAYS = 21          # bounded state: old resolved entries age out
MAX_HOLD_DAYS = 7       # resolution horizon cap (a 30-DTE variant's watchlist
                        # verdict shouldn't wait a month to score the dial)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Watchlist:
    """Per-expert watchlist state: record -> digest -> resolve -> stats."""

    def __init__(self, path):
        self.path = Path(path)
        self._entries: dict[str, dict] = _load_json(self.path, {})

    def _save(self) -> None:
        atomic_write_json(self.path, self._entries)

    # ── recording (every scan pass) ──────────────────────────────────────────
    @refreshed("_entries", dict)
    def record(self, *, key: str, symbol: str, strategy: str, dte: int,
               direction: int, score: float, decision: float, spot: float,
               entry_ts, alerted: bool) -> None:
        """Record one scored winner; idempotent on ``key`` except that a
        replayed pass may upgrade ``alerted`` False -> True (crash replay)."""
        e = self._entries.get(key)
        if e is not None:
            if alerted and not e.get("alerted"):
                e["alerted"] = True
                self._save()
            return
        self._entries[key] = {
            "date": pd.Timestamp(entry_ts).date().isoformat(),
            "symbol": symbol, "strategy": strategy, "dte": int(dte),
            "direction": int(direction), "score": float(score),
            "decision": float(decision), "spot": float(spot),
            "entry_ts": pd.Timestamp(entry_ts).isoformat(),
            "alerted": bool(alerted), "digested": False, "outcome": None,
        }
        self._prune()
        self._save()

    def _prune(self) -> None:
        cutoff = (_utcnow() - timedelta(days=KEEP_DAYS)).date().isoformat()
        self._entries = {k: e for k, e in self._entries.items()
                         if e["date"] >= cutoff}

    # ── digest (once daily) ──────────────────────────────────────────────────
    def pending_digest(self, day: Optional[str] = None) -> list[dict]:
        """Today's undigested entries, best decision first."""
        day = day or _utcnow().date().isoformat()
        rows = [dict(e, key=k) for k, e in self._entries.items()
                if e["date"] == day and not e["digested"]]
        return sorted(rows, key=lambda e: -e["decision"])

    @refreshed("_entries", dict)
    def mark_digested(self, keys: list[str]) -> None:
        for k in keys:
            if k in self._entries:
                self._entries[k]["digested"] = True
        self._save()

    # ── resolution (ride along with the digest run) ──────────────────────────
    def unresolved(self) -> list[dict]:
        return [dict(e, key=k) for k, e in self._entries.items()
                if e["outcome"] is None]

    @refreshed("_entries", dict)
    def resolve(self, bar_loader: Callable[[str], pd.DataFrame],
                now: Optional[datetime] = None) -> int:
        """Resolve every entry whose horizon (min(dte, MAX_HOLD_DAYS) calendar
        days) has elapsed: hit = the underlying closed in the signal's
        direction at the first bar at/after the horizon. Entries whose symbol
        has no bar past the horizon yet stay unresolved (never guessed)."""
        now = now or _utcnow()
        due = [e for e in self.unresolved()
               if pd.Timestamp(e["entry_ts"])
               + timedelta(days=min(int(e["dte"]), MAX_HOLD_DAYS))
               <= pd.Timestamp(now).tz_localize(None)]
        n = 0
        bars_cache: dict[str, Optional[pd.DataFrame]] = {}
        for e in due:
            sym = e["symbol"]
            if sym not in bars_cache:
                try:
                    bars_cache[sym] = bar_loader(sym)
                except Exception:
                    bars_cache[sym] = None
            bars = bars_cache[sym]
            if bars is None or bars.empty:
                continue
            horizon = pd.Timestamp(e["entry_ts"]) + timedelta(
                days=min(int(e["dte"]), MAX_HOLD_DAYS))
            after = bars[bars.index >= horizon]
            if after.empty:
                continue                      # horizon bar not printed yet
            end_spot = float(after["Close"].iloc[0])
            moved = end_spot - e["spot"]
            hit = moved > 0 if e["direction"] == 0 else moved < 0
            self._entries[e["key"]]["outcome"] = {
                "resolved_ts": pd.Timestamp(after.index[0]).isoformat(),
                "spot_end": end_spot, "hit": bool(hit),
            }
            n += 1
        if n:
            self._save()
        return n

    # ── the scoreboard line ──────────────────────────────────────────────────
    def hit_stats(self, days: int = 7) -> dict:
        cutoff = (_utcnow() - timedelta(days=days)).date().isoformat()
        res = [e for e in self._entries.values()
               if e["outcome"] is not None
               and e["outcome"]["resolved_ts"][:10] >= cutoff]
        al = [e for e in res if e["alerted"]]
        return {
            "window_days": days,
            "resolved": len(res),
            "hits": sum(e["outcome"]["hit"] for e in res),
            "alerted_resolved": len(al),
            "alerted_hits": sum(e["outcome"]["hit"] for e in al),
        }


def format_digest(rows: list[dict], stats: dict, *, expert: str = "v4",
                  top: int = 10, aliases: Optional[dict] = None,
                  ev_mode: bool = False) -> tuple[str, str]:
    """One Telegram message: today's top-N flow + the rolling scoreboard."""
    aliases = aliases or {}
    title = f"[{expert} watchlist] top {min(top, len(rows))} of {len(rows)} signals"
    lines = []
    for i, e in enumerate(rows[:top], 1):
        shown = aliases.get(e["symbol"], e["symbol"])
        side = "CALL" if e["direction"] == 0 else "PUT"
        dec = (f"EV {e['decision']:+.1%}" if ev_mode
               else f"P(win) {e['decision']:.0%}")
        mark = " ⚡" if e["alerted"] else ""
        lines.append(f"{i:>2}. {shown} {side} · {dec} · P(win) {e['score']:.0%}"
                     f" · {e['strategy']} · DTE {e['dte']}{mark}")
    if not lines:
        lines.append("(no fresh signals today)")
    if stats["resolved"]:
        rate = stats["hits"] / stats["resolved"]
        score = (f"\n{stats['window_days']}d resolved watchlist hit-rate "
                 f"(underlying-direction): {rate:.0%} "
                 f"({stats['hits']}/{stats['resolved']})")
        if stats["alerted_resolved"]:
            score += (f" · alerted subset: {stats['alerted_hits']}"
                      f"/{stats['alerted_resolved']}")
    else:
        score = f"\n{stats['window_days']}d hit-rate: no resolved entries yet"
    msg = "\n".join(lines) + score + "\n⚡ = cleared the conviction threshold"
    return title, msg
