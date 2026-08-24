# nn_meta/live/scanner.py
"""Detect fresh frozen-strategy entries on the last CLOSED 15m bar.

The scanner never looks at the forming bar (no lookahead): a 15-minute bar
labelled T closes at T+15m, so it is only actionable once ``now >= T+15m``.
For each frozen symbol it re-fires the symbol's train-best proposal strategy
over recent bars and alerts iff the newest simulated entry lands exactly on
the last closed bar.

NN filtering is a pluggable ``scorer`` seam: with none, every mechanical entry
alerts (baseline mode — plumbing/validation); the NN ensemble scorer wires in
once the v2 model_final bundle is trained.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from utils.logging_utils import setup_logging
from options.execution import to_naive_utc
from nn_meta import config
from nn_meta.baseline import load_spec, propose_trades

logger = setup_logging(log_file="logs/backtester.log")

_BAR = timedelta(minutes=15)
_LOOKBACK_DAYS = 60                       # enough warmup for the slowest windows
# v2/v3 keep the original path byte-for-byte (the deployed server mutates it
# live). Big-run pools (v31+) get their own file: two experts sharing one
# dedupe dict keyed by symbol would silently suppress each other's alerts.
_STATE_PATH = config.ROOT / "live" / (
    ".alert_state.json" if config.POOL in ("v2", "v3")
    else f".alert_state_{config.POOL}.json")

# scorer(signal, bars) -> P(win) in [0,1], or None to keep (baseline mode)
Scorer = Callable[["Signal", pd.DataFrame], Optional[float]]

# Renamed-listing aliases live in config (constants-only home, 2026-08-16
# review P2 — the offline crawler needs them without importing this module's
# logging side effects); re-exported here for existing callers/tests.
TICKER_ALIASES = config.TICKER_ALIASES


def aliased_bar_loader(loader: Callable[[str], pd.DataFrame]
                       ) -> Callable[[str], pd.DataFrame]:
    """Wrap a bar loader so renamed tickers fetch under their new symbol.
    Inert for v2/v3 (their specs contain no renamed tickers)."""
    return lambda sym: loader(TICKER_ALIASES.get(sym, sym))


@dataclass
class Signal:
    symbol: str
    strategy: str
    direction: int          # 0 long / 1 short
    right: str              # "C" / "P"
    bar_ts: pd.Timestamp    # the closed bar the entry fired on (tz-naive UTC)
    dte: int
    spot: float
    param_label: str
    score: Optional[float] = None    # NN P(win), None in baseline mode

    @property
    def action(self) -> str:
        return "BUY CALL" if self.right == "C" else "BUY PUT"


# ── market hours ──────────────────────────────────────────────────────────────

def is_rth(now: Optional[datetime] = None) -> bool:
    """True during regular US equity hours (Mon-Fri 09:30-16:00 America/New_York)."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    et = now.astimezone(_ny_tz())
    if et.weekday() >= 5:
        return False
    minutes = et.hour * 60 + et.minute
    return 9 * 60 + 30 <= minutes < 16 * 60


def _ny_tz():
    from zoneinfo import ZoneInfo
    return ZoneInfo("America/New_York")


def closed_bars(bars: pd.DataFrame, now: Optional[datetime] = None) -> pd.DataFrame:
    """Drop the still-forming bar: keep bars whose 15m interval has fully closed."""
    if bars.empty:
        return bars
    now = now or datetime.now(timezone.utc)
    now_naive = pd.Timestamp(now).tz_convert("UTC").tz_localize(None) \
        if pd.Timestamp(now).tzinfo else pd.Timestamp(now)
    return bars[bars.index + _BAR <= now_naive]


# ── detection ─────────────────────────────────────────────────────────────────

def detect_fresh_signal(symbol: str, bars: pd.DataFrame, spec_entry: dict
                        ) -> Optional[Signal]:
    """A Signal iff the newest simulated entry lands on the last closed bar."""
    if bars is None or len(bars) < 30:
        return None
    strat = spec_entry["best_strategy"]
    e = spec_entry["strategies"][strat]
    trades = propose_trades(bars, strat, e["params"],
                            bars.index[0], bars.index[-1])
    if not trades:
        return None
    ent_ts, _exit_ts, direction = trades[-1]
    ent_ts = to_naive_utc(ent_ts)
    if ent_ts != bars.index[-1]:          # newest entry isn't on the last closed bar
        return None
    return Signal(
        symbol=symbol, strategy=strat, direction=int(direction),
        right="C" if direction == 0 else "P",
        bar_ts=bars.index[-1], dte=int(e["dte"]),
        spot=float(bars["Close"].iloc[-1]),
        param_label=e.get("param_label", ""),
    )


def suggest_contract(sig: Signal, now: Optional[datetime] = None) -> str:
    """Advisory contract string (alert-only: the human picks the live listing)."""
    now = now or datetime.now(timezone.utc)
    target_exp = (now + timedelta(days=sig.dte)).date()
    return (f"~ATM {sig.right} near ${sig.spot:,.2f} strike, "
            f"~{sig.dte} DTE (nearest listed expiry ≈ {target_exp})")


def format_alert(sig: Signal) -> tuple[str, str]:
    # v2/v3 alert text is unchanged; big-run pools (v31+) run as ADDITIONAL
    # experts next to the v3 line, so their alerts carry the pool label.
    tag = "" if config.POOL in ("v2", "v3") else f"[{config.POOL}] "
    title = f"{tag}{sig.symbol} {sig.action}"
    conv = f" · conviction {sig.score:.0%}" if sig.score is not None else ""
    msg = (f"{tag}{sig.symbol}: {sig.action}{conv}\n"
           f"trigger: {sig.strategy} ({sig.param_label})\n"
           f"contract: {suggest_contract(sig)}\n"
           f"bar: {sig.bar_ts} UTC · spot ${sig.spot:,.2f}")
    if tag:
        msg += f"\nexpert: {config.POOL}-nn · paper"
    return title, msg


# ── dedup state ───────────────────────────────────────────────────────────────

def _load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        return {}


def _save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))


# ── scanner ───────────────────────────────────────────────────────────────────

class Scanner:
    """Ties detection + dedup + (optional) NN scoring together for one pass."""

    def __init__(self, bar_loader, scorer: Optional[Scorer] = None,
                 threshold: float = 0.5, state_path: Path = _STATE_PATH,
                 spec: Optional[dict] = None,
                 watchlist_path: Optional[Path] = None):
        # bar_loader(symbol) -> recent 15m OHLCV incl. possibly-forming last bar
        self._load = bar_loader
        self._scorer = scorer
        self._threshold = threshold
        self._state_path = state_path
        self._spec = spec or load_spec()
        # Dual-mode cadence (ROADMAP wave-2 item 5, panel-wide 2026-08-24):
        # every SCORED signal — above or below threshold — joins the pool's
        # daily watchlist; the panel digest sends the top-N and tracks
        # forward hit-rates. Pool-keyed file beside the other live state.
        self._watchlist_path = watchlist_path or (
            config.ROOT / "live" / f".{config.POOL}_watchlist.json")

    def scan_once(self, symbols: Optional[list[str]] = None,
                  now: Optional[datetime] = None) -> list[Signal]:
        now = now or datetime.now(timezone.utc)
        state = _load_state(self._state_path)
        fired: list[Signal] = []
        for sym in (symbols or list(self._spec["symbols"])):
            try:
                bars = closed_bars(self._load(sym), now)
                sig = detect_fresh_signal(sym, bars, self._spec["symbols"][sym])
            except Exception as e:
                logger.error(f"[live] {sym}: scan error: {e}")
                continue
            if sig is None:
                continue
            bar_iso = sig.bar_ts.isoformat()
            if state.get(sym) == bar_iso:          # already alerted this bar
                continue
            if self._scorer is not None:
                sig.score = self._scorer(sig, bars)
                if sig.score is not None:
                    from nn_meta.live.watchlist import Watchlist   # lazy, cheap
                    Watchlist(self._watchlist_path).record(
                        key=f"{config.POOL}|{sym}|{sig.strategy}|{bar_iso}",
                        symbol=sym, strategy=sig.strategy, dte=int(sig.dte),
                        direction=int(sig.direction), score=float(sig.score),
                        decision=float(sig.score), spot=float(sig.spot),
                        entry_ts=sig.bar_ts,
                        alerted=bool(sig.score >= self._threshold))
                if sig.score is None or sig.score < self._threshold:
                    logger.info(f"[live] {sym}: mechanical entry filtered out "
                                f"(score={sig.score})")
                    continue
            fired.append(sig)
            state[sym] = bar_iso
        _save_state(self._state_path, state)
        return fired
