"""Pure, timestamped option-snapshot resolver for the proposed D1 alert path.

Input is a captured complete Massive option-chain snapshot, including an
``observed_at`` timestamp added when the response was received. This module
does not fetch data, send alerts, subscribe contracts or place orders. It
produces a concrete preview while the existing alert-format decision and
offline selection parity remain pending.

Schema reference: https://massive.com/docs/rest/options/snapshots/option-chain-snapshot
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

RESOLVER_VERSION = "snapshot-delta-preview-v1"
_OCC = re.compile(r"^(?:O:)?([A-Z][A-Z0-9.]*)(\d{6})([CP])(\d{8})$")


def _utc(value: str | datetime) -> datetime:
    if isinstance(value, str):
        fraction = re.search(r"[T ]\d{2}:\d{2}:\d{2}[.,](\d+)", value)
        if fraction and len(fraction.group(1)) > 6:
            raise ValueError("snapshot/decision timestamps support at most microsecond precision")
    result = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if not isinstance(result, datetime) or result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timestamps must include a timezone")
    return result.astimezone(timezone.utc)


def _number(value) -> float:
    if isinstance(value, bool):
        raise ValueError("boolean is not a market measurement")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("non-finite market measurement")
    return result


def _epoch_ns(value: datetime) -> int:
    delta = value - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return ((delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds) * 1000


@dataclass(frozen=True)
class ResolverPolicy:
    max_spread_bps: float
    max_quote_age_s: float = 60.0
    max_snapshot_age_s: float = 60.0
    target_delta: float = 0.50
    min_open_interest: int = 0
    max_dte_distance: int = 10

    def __post_init__(self):
        for name in ("max_spread_bps", "max_quote_age_s", "max_snapshot_age_s"):
            value = _number(getattr(self, name))
            if value <= 0:
                raise ValueError(f"{name} must be positive")
            object.__setattr__(self, name, value)
        target = _number(self.target_delta)
        if not 0 < target < 1:
            raise ValueError("target_delta must be between zero and one")
        object.__setattr__(self, "target_delta", target)
        for name in ("min_open_interest", "max_dte_distance"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")


def resolve_snapshot(snapshot: dict, *, underlying: str, right: str,
                     target_dte: int, decision_at: str | datetime,
                     policy: ResolverPolicy) -> dict:
    """Select nearest expiry, then nearest signed delta among valid quotes.

    Reject incomplete pagination and snapshots received after the decision.
    Quote timestamps alone cannot establish availability of snapshot Greeks.
    Counts of rejected contracts make a no-selection result inspectable.
    Require a reported 100 shares, but this snapshot schema cannot prove the
    absence of additional deliverables. Every preview retains an explicit
    unverified-deliverables flag until contract-reference data is supplied.
    Expiry distance uses the New York session date.
    """
    from zoneinfo import ZoneInfo

    decision = _utc(decision_at)
    observed = _utc(snapshot["observed_at"])
    age = (decision - observed).total_seconds()
    if not 0 <= age <= policy.max_snapshot_age_s:
        raise ValueError("snapshot is stale or was not available at the decision")
    if snapshot.get("next_url"):
        raise ValueError("snapshot pagination is incomplete")
    if snapshot.get("status") not in (None, "OK"):
        raise ValueError("snapshot provider status is not OK")
    if not isinstance(snapshot.get("results"), list):
        raise ValueError("snapshot results must be a complete list")
    underlying = underlying.upper()
    right = right.upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9.]*", underlying) or right not in ("C", "P"):
        raise ValueError("invalid underlying or option right")
    if isinstance(target_dte, bool) or not isinstance(target_dte, int) or target_dte < 1:
        raise ValueError("target_dte must be a positive integer; 0DTE is a separate seat")
    session_day = decision.astimezone(ZoneInfo("America/New_York")).date()
    decision_ns, observed_ns = _epoch_ns(decision), _epoch_ns(observed)
    reasons: Counter = Counter()
    accepted = []
    # A repeated contract can carry conflicting quotes/Greeks. Refuse the
    # complete selection instead of accepting whichever page arrived first.
    seen: set[str] = set()
    for row in snapshot["results"]:
        if isinstance(row, dict) and isinstance(row.get("details"), dict):
            ticker = row["details"].get("ticker")
            if isinstance(ticker, str):
                occ = ticker.removeprefix("O:")
                if occ in seen:
                    raise ValueError(f"snapshot contains duplicate contract: {occ}")
                seen.add(occ)
    for row in snapshot["results"]:
        try:
            details, quote = row["details"], row["last_quote"]
            match = _OCC.fullmatch(details["ticker"])
            if not match:
                raise ValueError("invalid OCC")
            root, expiry_code, code, strike_code = match.groups()
            occ = details["ticker"].removeprefix("O:")
            if root.replace(".", "") != underlying.replace(".", ""):
                reasons["wrong_underlying"] += 1
                continue
            if code != right or details["contract_type"] != {"C": "call", "P": "put"}[right]:
                reasons["wrong_right"] += 1
                continue
            expiry = date.fromisoformat(details["expiration_date"])
            strike = _number(details["strike_price"])
            encoded_expiry = date(2000 + int(expiry_code[:2]), int(expiry_code[2:4]), int(expiry_code[4:]))
            if expiry != encoded_expiry or strike != int(strike_code) / 1000 or strike <= 0:
                raise ValueError("OCC/details mismatch")
            if _number(details["shares_per_contract"]) != 100 or details.get("additional_underlyings"):
                reasons["nonstandard_deliverable"] += 1
                continue
            dte = (expiry - session_day).days
            if dte < 1 or abs(dte - target_dte) > policy.max_dte_distance:
                reasons["expiry_outside_policy"] += 1
                continue
            delta = _number(row["greeks"]["delta"])
            iv = _number(row["implied_volatility"])
            oi = _number(row["open_interest"])
            if not (0 < delta <= 1 if right == "C" else -1 <= delta < 0) or iv <= 0:
                reasons["invalid_greeks"] += 1
                continue
            if oi < policy.min_open_interest or oi < 0 or not oi.is_integer():
                reasons["open_interest"] += 1
                continue
            bid, ask = _number(quote["bid"]), _number(quote["ask"])
            if not 0 < bid <= ask or _number(quote["bid_size"]) <= 0 or _number(quote["ask_size"]) <= 0:
                reasons["invalid_quote"] += 1
                continue
            # Massive snapshot last_updated is Unix nanoseconds.
            timestamp = quote["last_updated"]
            if isinstance(timestamp, bool) or not isinstance(timestamp, int):
                raise ValueError("quote timestamp must be integer Unix nanoseconds")
            if timestamp > observed_ns or not 0 <= decision_ns - timestamp <= policy.max_quote_age_s * 1_000_000_000:
                reasons["quote_unavailable_or_stale"] += 1
                continue
            quoted = datetime.fromtimestamp(timestamp // 1_000_000_000, timezone.utc)
            quoted_text = quoted.strftime("%Y-%m-%dT%H:%M:%S") + f".{timestamp % 1_000_000_000:09d}+00:00"
            spread = (ask - bid) / ((ask + bid) / 2) * 10_000
            if spread > policy.max_spread_bps:
                reasons["spread"] += 1
                continue
            candidate = {"occ": occ, "right": right, "expiration": expiry.isoformat(),
                         "deliverables_verified": False,
                         "strike": strike, "dte": dte, "delta": delta,
                         "implied_volatility": iv, "open_interest": int(oi),
                         "bid": bid, "ask": ask, "spread_bps": spread,
                         "quoted_at": quoted_text, "quote_timestamp_ns": timestamp}
            rank = (abs(dte - target_dte), abs(abs(delta) - policy.target_delta), spread, -oi, occ)
            accepted.append((rank, candidate))
        except (KeyError, TypeError, ValueError, OverflowError, OSError):
            reasons["malformed_contract"] += 1
    selected = min(accepted, key=lambda item: item[0])[1] if accepted else None
    fingerprint = hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return {"resolver_version": RESOLVER_VERSION, "preview_only": True,
            "pending_requirements": ["contract_reference_deliverables", "offline_selection_parity"],
            "underlying": underlying, "decision_at": decision.isoformat(),
            "observed_at": observed.isoformat(), "snapshot_sha256": fingerprint,
            "target_dte": target_dte, "policy": asdict(policy),
            "eligible_contracts": len(accepted), "rejections": dict(sorted(reasons.items())),
            "selected": selected}


def format_preview(result: dict) -> str:
    selected = result["selected"]
    if selected is None:
        return f"PREVIEW {result['underlying']}: no contract passes quote/expiry checks"
    return (f"PREVIEW {result['underlying']} {selected['occ']} | "
            f"bid ${selected['bid']:.2f} / ask ${selected['ask']:.2f} | "
            f"spread {selected['spread_bps']:.0f} bps | delta {selected['delta']:+.2f} | deliverables unverified")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--underlying", required=True)
    parser.add_argument("--right", choices=("C", "P"), required=True)
    parser.add_argument("--dte", type=int, required=True)
    parser.add_argument("--decision-at", required=True)
    parser.add_argument("--max-spread-bps", type=float, required=True)
    args = parser.parse_args()
    result = resolve_snapshot(json.loads(args.snapshot.read_text()), underlying=args.underlying,
                              right=args.right, target_dte=args.dte, decision_at=args.decision_at,
                              policy=ResolverPolicy(max_spread_bps=args.max_spread_bps))
    print(format_preview(result))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
