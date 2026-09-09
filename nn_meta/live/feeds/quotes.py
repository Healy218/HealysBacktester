"""Live quote for an alert's resolved contract, and the two alert lines.

Order of preference (2026-09-09, user decision "option 1"):
  1. the OPRA stream's latest NBBO (``QuoteStore``) when it is fresh enough;
  2. a Massive REST snapshot (also carries delta / IV) — the stream only
     subscribes to a contract once the alert path registers it, so the very
     first alert on a name would otherwise go out without numbers.
Both are best effort: any failure yields None and the alert falls back to
the old advisory text. Nothing here touches a model's decision.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from utils.logging_utils import setup_logging
from nn_meta.live.feeds.quotestore import QuoteStore, _to_occ

logger = setup_logging(log_file="logs/backtester.log")
STREAM_MAX_AGE_S = 180.0          # a streamed NBBO older than this is not "live"


def live_quote(occ: str, *, max_age_s: float = STREAM_MAX_AGE_S, allow_rest: bool = True,
               store_path=None) -> Optional[dict]:
    occ = _to_occ(occ)
    q = QuoteStore.get(occ, *( [store_path] if store_path is not None else [] ), max_age_s=max_age_s)
    if q is not None:
        return {**q, "source": "stream"}
    if not allow_rest:
        return None
    try:
        from options.data.massive_provider import MassiveProvider
        return MassiveProvider().get_contract_snapshot(occ)
    except Exception as exc:                          # no key, network, unknown contract
        logger.warning(f"[quotes] {occ}: REST snapshot unavailable: {exc}")
        return None


def format_contract(occ: str) -> str:
    """'MARA 2026-10-09 $11.50 CALL (MARA261009C00011500)'."""
    from options.data.provider import parse_occ_symbol
    root, exp, right, strike = parse_occ_symbol(occ)
    kind = "CALL" if right == "C" else "PUT"
    strike_s = f"${int(strike):,}" if strike == int(strike) else f"${strike:,.2f}"
    return f"{root} {exp:%Y-%m-%d} {strike_s} {kind} ({occ})"


def format_quote_line(q: Optional[dict], now: Optional[datetime] = None) -> str:
    if not q:
        return "quote: unavailable"
    bid, ask = float(q["bid"]), float(q["ask"])
    mid = (bid + ask) / 2
    spread = f"{(ask - bid) / mid:.1%}" if mid > 0 else "n/a"
    try:
        age = (( now or datetime.now(timezone.utc)) - datetime.fromisoformat(q["ts"])).total_seconds()
        age_s = f"{age:.0f}s old" if age < 120 else f"{age / 60:.0f}m old"
    except Exception:
        age_s = "age ?"
    parts = [f"quote: bid {bid:.2f} / ask {ask:.2f} · mid {mid:.2f} · spread {spread}",
             f"{q.get('bid_size', 0):.0f}x{q.get('ask_size', 0):.0f}", age_s]
    if q.get("delta") is not None:
        parts.append(f"Δ {float(q['delta']):.2f}")
    if q.get("iv") is not None:
        parts.append(f"IV {float(q['iv']):.0%}")
    parts.append(q.get("source", "stream"))
    return " · ".join(parts)


def contract_lines(occ: Optional[str], q: Optional[dict], fallback: str) -> str:
    """The alert's contract block: resolved contract + quote, or the legacy
    advisory line when no contract could be resolved."""
    if not occ:
        return f"contract: {fallback}"
    return f"contract: {format_contract(occ)}\n{format_quote_line(q)}"
