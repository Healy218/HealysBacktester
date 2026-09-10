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
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from utils.logging_utils import setup_logging
from options.execution import to_naive_utc
from nn_meta import config
from nn_meta.live.state import Outbox, atomic_write_json, serialized
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

    params: dict = field(default_factory=dict)

    @property
    def action(self) -> str:
        return "BUY CALL" if self.right == "C" else "BUY PUT"


# ── market hours ──────────────────────────────────────────────────────────────

def is_rth(now: Optional[datetime] = None) -> bool:
    """True during regular US equity hours (Mon-Fri 09:30 through the staggered 16:03 close pass, America/New_York)."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    from nn_meta.session_calendar import configured_calendar
    calendar = configured_calendar()
    if calendar is not None:
        return calendar.scan_open(now)
    et = now.astimezone(_ny_tz())
    if et.weekday() >= 5:
        return False
    minutes = et.hour * 60 + et.minute
    return 9 * 60 + 30 <= minutes <= 16 * 60 + 3


def _ny_tz():
    from zoneinfo import ZoneInfo
    return ZoneInfo("America/New_York")


def closed_bars(bars: pd.DataFrame, now: Optional[datetime] = None) -> pd.DataFrame:
    """Drop the still-forming bar: keep bars whose 15m interval has fully closed."""
    if bars is None or bars.empty:
        return bars
    now = now or datetime.now(timezone.utc)
    now_naive = pd.Timestamp(now).tz_convert("UTC").tz_localize(None) \
        if pd.Timestamp(now).tzinfo else pd.Timestamp(now)
    return bars[bars.index + _BAR <= now_naive]


class NoBarsError(ValueError):
    """The loader returned nothing at all for a symbol (delisted, renamed, or
    never listed) — a skip, not a scan error (2026-09-08 review, fix 5)."""


class StaleBarsError(ValueError):
    """The feed is more than one closed interval behind the session."""


class NoBarsMemo:
    """Names that returned no bars at all, remembered per expert so the loader
    is not hit for them every 15 minutes (each attempt costs two REST calls
    and four ERROR lines). Rechecked after ``RECHECK_DAYS`` in case of a
    re-listing or rename. File beside the expert's other live state."""
    RECHECK_DAYS = 7

    def __init__(self, path):
        self.path = Path(path)
        try:
            self._data = json.loads(self.path.read_text()) if self.path.exists() else {}
        except Exception:
            self._data = {}
        if not isinstance(self._data, dict):
            self._data = {}

    def active(self, now) -> set[str]:
        stamp = pd.Timestamp(now)
        stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
        out = set()
        for sym, ts in self._data.items():
            try:
                if stamp - pd.Timestamp(ts).tz_convert("UTC") < pd.Timedelta(days=self.RECHECK_DAYS):
                    out.add(sym)
            except Exception:
                continue
        return out

    def mark(self, sym: str, now) -> None:
        stamp = pd.Timestamp(now)
        stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
        self._data[sym] = stamp.isoformat()

    def save(self) -> None:
        atomic_write_json(self.path, self._data)


def expected_last_closed_bar(now) -> Optional[pd.Timestamp]:
    """Start (tz-naive UTC) of the latest RTH 15m bar that has fully closed at
    ``now``, walking back across weekends and holidays.

    Session-aware staleness (2026-09-08 review, fix 4): the first pass after a
    long weekend fires at 09:31 ET, before today's first bar has closed, so the
    newest closed bar really is Friday's 15:45 — a wall-clock age would call
    every symbol stale. Uses the captured exchange calendar when configured
    (holidays, early closes), else the Mon-Fri 09:30-16:00 ET rule.
    Returns None only when no session is found within two weeks.
    """
    stamp = pd.Timestamp(now)
    stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
    from nn_meta.session_calendar import configured_calendar
    calendar = configured_calendar()
    et = stamp.tz_convert(_ny_tz())
    for back in range(15):
        day = (et - pd.Timedelta(days=back)).normalize()
        if calendar is not None:
            try:
                starts = calendar.closed_starts(day.strftime("%Y-%m-%d"), stamp)
            except ValueError:            # outside the captured coverage
                starts = None
            if starts is not None:
                if len(starts):
                    return pd.Timestamp(starts[-1])
                continue                  # holiday / not yet open today
        if day.weekday() >= 5:
            continue
        opening = day + pd.Timedelta(hours=9, minutes=30)
        closing = day + pd.Timedelta(hours=16)
        starts = pd.date_range(opening, closing, freq="15min", inclusive="left")
        starts = starts[starts + _BAR <= et]
        if len(starts):
            return starts[-1].tz_convert("UTC").tz_localize(None)
    return None


def require_recent_bars(bars, now):
    """Refuse a feed more than one interval behind the expected closed bar.

    "Expected" is the latest bar the session calendar says has closed (see
    ``expected_last_closed_bar``), not ``now`` minus a fixed age — so Friday's
    last bar is current at 09:31 ET on Tuesday after a holiday Monday, and a
    feed stuck at 14:00 while 14:30 has closed is stale mid-session.
    """
    if bars is None or bars.empty:
        raise NoBarsError("no closed market bars")
    stamp = pd.Timestamp(now)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert("UTC").tz_localize(None)
    last = pd.Timestamp(bars.index[-1])
    expected = expected_last_closed_bar(now)
    if expected is None:                  # no session known: legacy wall-clock rule
        age = stamp - last
        if age > pd.Timedelta(minutes=30):
            raise StaleBarsError(f"stale market bars: last bar {last}, age {age}")
        return bars
    if last < expected - _BAR:
        raise StaleBarsError(f"stale market bars: last bar {last}, "
                             f"expected closed bar {expected}")
    return bars


def register_alert_contract(symbol: str, right: str, spot: float, dte: int, now) -> Optional[str]:
    """Best-effort: resolve the alert's ~ATM contract to a listed OCC symbol and
    register it with the OPRA quote stream's watch list (2026-09-08, fix 1).
    Never raises — a missing contracts table just means no quotes for it."""
    try:
        from nn_meta.live.feeds.contracts import resolve_occ
        from nn_meta.live.feeds.option_stream import add_to_watch
        occ = resolve_occ(symbol, right, spot, dte, now)
        if occ:
            add_to_watch([occ])
        return occ
    except Exception as exc:                       # pragma: no cover - defensive
        logger.warning(f"[live] {symbol}: could not register contract for quotes: {exc}")
        return None


def alert_quote(occ: Optional[str], allow_rest: bool = True) -> Optional[dict]:
    """Best-effort live NBBO for a resolved contract (stream first, then the
    Massive REST snapshot). Never raises."""
    if not occ:
        return None
    try:
        from nn_meta.live.feeds.quotes import live_quote
        return live_quote(occ, allow_rest=allow_rest)
    except Exception as exc:                       # pragma: no cover - defensive
        logger.warning(f"[live] {occ}: quote lookup failed: {exc}")
        return None


def _mid(q: Optional[dict]) -> Optional[float]:
    try:
        return round((float(q["bid"]) + float(q["ask"])) / 2, 4) if q else None
    except Exception:
        return None


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
        params=dict(e["params"]),
    )


def suggest_contract(sig: Signal, now: Optional[datetime] = None) -> str:
    """Advisory contract string (alert-only: the human picks the live listing)."""
    now = now or datetime.now(timezone.utc)
    target_exp = (now + timedelta(days=sig.dte)).date()
    return (f"~ATM {sig.right} near ${sig.spot:,.2f} strike, "
            f"~{sig.dte} DTE (nearest listed expiry ≈ {target_exp})")


def format_alert(sig: Signal, contract: Optional[str] = None,
                 quote: Optional[dict] = None) -> tuple[str, str]:
    # v2/v3 alert text is unchanged; big-run pools (v31+) run as ADDITIONAL
    # experts next to the v3 line, so their alerts carry the pool label.
    # 2026-09-08 (fix 6): v3 carries its tag too, so every phone alert and
    # every top-five slot reads the same way; only the legacy v2 line is bare.
    # 2026-09-09: with a resolved ``contract`` the advisory "~ATM near $spot"
    # line becomes the listed contract plus its live NBBO (see feeds/quotes).
    from nn_meta.live.exit_rules import format_exit_line
    from nn_meta.live.feeds.quotes import contract_lines
    tag = "" if config.POOL == "v2" else f"[{config.POOL}] "
    title = f"{tag}{sig.symbol} {sig.action}"
    conv = f" · conviction {sig.score:.0%}" if sig.score is not None else ""
    msg = (f"{tag}{sig.symbol}: {sig.action}{conv}\n"
           f"trigger: {sig.strategy} ({sig.param_label})\n"
           f"{contract_lines(contract, quote, suggest_contract(sig))}\n"
           f"{format_exit_line(sig.strategy, sig.params, sig.direction, sig.symbol, sig.spot, quote)}\n"
           f"bar: {sig.bar_ts} UTC · spot ${sig.spot:,.2f}")
    if config.POOL not in ("v2", "v3"):
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
    atomic_write_json(path, state)


# ── scanner ───────────────────────────────────────────────────────────────────

class Scanner:
    """Ties detection + dedup + (optional) NN scoring together for one pass."""

    def __init__(self, bar_loader, scorer: Optional[Scorer] = None,
                 threshold: float = 0.5, state_path: Path = _STATE_PATH,
                 spec: Optional[dict] = None,
                 watchlist_path: Optional[Path] = None,
                 workers: int = 1):
        # workers > 1 (2026-09-05): detection in a spawn process pool with the
        # REAL loader (nn_meta.live.parallel); the injected bar_loader is then
        # only used by the serial path. Scoring/dedupe/watchlist stay here.
        self._workers = max(1, int(workers))
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
            self._state_path.parent / f".{config.POOL}_watchlist.json")
        self._outbox_path = self._state_path.with_name(self._state_path.stem + "_outbox.json")

    @serialized(lambda self, *args, **kwargs: self._state_path.parent / ".live.lock")
    def scan_once(self, symbols: Optional[list[str]] = None,
                  now: Optional[datetime] = None) -> list[Signal]:
        now = now or datetime.now(timezone.utc)
        state = _load_state(self._state_path)
        fired: list[Signal] = []
        outbox = Outbox(self._outbox_path)
        syms = list(symbols or list(self._spec["symbols"]))
        memo = NoBarsMemo(self._state_path.parent / f".{config.POOL}_no_bars.json")
        known_dead = sorted(set(syms) & memo.active(now))
        if known_dead:
            logger.info(f"[live] skipping {len(known_dead)} known no-bars name(s) "
                        f"(rechecked after {memo.RECHECK_DAYS} days): {', '.join(known_dead)}")
            syms = [s for s in syms if s not in known_dead]
        results = None
        if self._workers > 1:
            from nn_meta.live.parallel import detect_many, _legacy_detect_one
            results = detect_many(_legacy_detect_one, syms,
                                  lambda s: (self._spec["symbols"][s], now),
                                  workers=self._workers)
        skipped: list[str] = []
        for sym in syms:
            try:
                if results is not None:
                    res, err = results[sym]
                    if err:
                        raise RuntimeError(err.splitlines()[0])
                    bars, sig = res
                    require_recent_bars(closed_bars(bars, now), now)
                else:
                    bars = require_recent_bars(closed_bars(self._load(sym), now), now)
                    sig = detect_fresh_signal(sym, bars, self._spec["symbols"][sym])
            except NoBarsError:
                skipped.append(sym)                # delisted/renamed: not an error
                memo.mark(sym, now)
                continue
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
            occ = register_alert_contract(sym, sig.right, float(sig.spot), int(sig.dte), now)
            quote = alert_quote(occ)
            title, message = format_alert(sig, occ, quote)
            from nn_meta.live.alert_batches import cycle
            from nn_meta.live.taken_trades import context_for
            outbox.enqueue({"title": title, "message": message,
                            "probability": sig.score, "expert": config.POOL, "alert_cycle": cycle(now),
                            "symbol": sym, "side": sig.action, "contract": occ,
                            "entry_mid": _mid(quote),
                            "trade_context": context_for(sym, strategy=sig.strategy, params=sig.params, direction=sig.direction, spot=sig.spot, entry_ts=sig.bar_ts, sim_start=bars.index[0]),
                            "summary": f"[{config.POOL}] {sym} | {sig.strategy} | {sig.action} | {sig.dte} DTE"},
                           key=f"{config.POOL}|{sym}|{sig.strategy}|{bar_iso}")
            fired.append(sig)
            state[sym] = bar_iso
        if skipped:
            logger.info(f"[live] skipped {len(skipped)} name(s) with no bars "
                        f"(delisted?): {', '.join(skipped)}")
            memo.save()
        _save_state(self._state_path, state)
        return fired

    @serialized(lambda self, *args, **kwargs: self._state_path.parent / ".live.lock")
    def deliver_pending(self, notifier):
        outbox = Outbox(self._outbox_path)
        sent = 0
        for entry in outbox.unacked():
            p = entry["payload"]
            from nn_meta.live.alert_batches import deliver
            if deliver(p, entry.get("key") or entry["id"], notifier):
                outbox.acknowledge(entry["id"])
                sent += 1
        return sent
