"""OCC parsing, session ratio mapping and ATM selection for the spx0 pool.

Facts this leans on (stage-0 audit, `docs/specs/SPX0_SPEC.md`): option rows
are keyed by an OCC string (``SPXW250610P05900000``); 0DTE volume lives in the
``SPXW``/``NDXP`` roots; the index underlying is unavailable, so the proxy
(SPY/QQQ) is mapped onto index strikes with a ratio MEASURED per session from
the archive itself, never a hard-coded constant (the divisor drifts with
dividends).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

ROOTS = ("SPXW", "SPX", "NDXP", "NDX")          # longer roots first
INDEX_OF_ROOT = {"SPXW": "SPX", "SPX": "SPX", "NDXP": "NDX", "NDX": "NDX"}
PROXY_OF_INDEX = {"SPX": "SPY", "NDX": "QQQ"}
_OCC = re.compile(r"^(SPXW|SPX|NDXP|NDX)(\d{6})([CP])(\d{8})$")


@dataclass(frozen=True)
class Contract:
    occ: str
    root: str
    index: str
    expiration: pd.Timestamp     # calendar day, naive
    right: str                   # "C" | "P"
    strike: float


def parse_occ(occ: str) -> Contract:
    m = _OCC.match(occ)
    if not m:
        raise ValueError(f"not an index OCC symbol: {occ!r}")
    root, ymd, right, strike = m.groups()
    return Contract(occ=occ, root=root, index=INDEX_OF_ROOT[root],
                    expiration=pd.Timestamp(f"20{ymd[:2]}-{ymd[2:4]}-{ymd[4:]}"),
                    right=right, strike=int(strike) / 1000.0)


def parse_occ_frame(occ: pd.Series) -> pd.DataFrame:
    """Vectorised parse: columns root, index, expiration, right, strike.
    Unparseable symbols raise — silently dropping rows hides archive drift."""
    parts = occ.astype(str).str.extract(_OCC)
    if parts.isna().any(axis=None):
        bad = occ[parts.isna().any(axis=1)].head(3).tolist()
        raise ValueError(f"unparseable OCC symbols, e.g. {bad}")
    out = pd.DataFrame(index=occ.index)
    out["root"] = parts[0].values
    out["index"] = out["root"].map(INDEX_OF_ROOT)
    out["expiration"] = pd.to_datetime("20" + parts[1], format="%Y%m%d").values
    out["right"] = parts[2].values
    out["strike"] = parts[3].astype(int).values / 1000.0
    return out


def same_day_expiry(frame: pd.DataFrame, session: pd.Timestamp) -> pd.DataFrame:
    """Rows of contracts expiring on ``session`` (the 0DTE pool for that day)."""
    day = pd.Timestamp(session).normalize()
    return frame[frame["expiration"] == day]


def session_ratio(zero_dte: pd.DataFrame, proxy_close_at_open: float, *,
                  index: str, first_bar_ts: pd.Timestamp) -> float:
    """index_proxy_ratio for one session: the volume-weighted strike centre of
    the 0DTE contracts printing at the session's first option bar, divided by
    the proxy's close on that bar. Measured, not assumed.

    Fails closed (``ValueError``) when fewer than 5 contracts print on the first
    bar — a thin open says nothing reliable about the ratio.
    """
    sub = zero_dte[(zero_dte["index"] == index) & (zero_dte["timestamp"] == first_bar_ts)]
    if len(sub) < 5 or not np.isfinite(proxy_close_at_open) or proxy_close_at_open <= 0:
        raise ValueError(f"cannot measure {index} ratio at {first_bar_ts}: "
                         f"{len(sub)} contracts on the first bar")
    w = sub["Volume"].clip(lower=1).to_numpy(dtype=float)
    centre = float(np.average(sub["strike"].to_numpy(dtype=float), weights=w))
    return centre / float(proxy_close_at_open)


def map_spot(proxy_price: float, ratio: float) -> float:
    return float(proxy_price) * float(ratio)


def pick_atm(zero_dte: pd.DataFrame, *, index: str, right: str, mapped_spot: float,
             at: pd.Timestamp, lookback_bars: int = 5) -> Contract | None:
    """The contract to trade: nearest strike to the ratio-mapped spot among
    contracts that PRINTED within the last ``lookback_bars`` minutes up to
    ``at`` (no print → no evidence it is tradeable). Returns ``None`` when
    nothing qualifies; the caller records an unexecuted proposal."""
    lo = at - pd.Timedelta(minutes=lookback_bars)
    sub = zero_dte[(zero_dte["index"] == index) & (zero_dte["right"] == right)
                   & (zero_dte["timestamp"] > lo) & (zero_dte["timestamp"] <= at)]
    if sub.empty:
        return None
    dist = (sub["strike"] - mapped_spot).abs()
    row = sub.loc[dist.idxmin()]
    return parse_occ(str(row["occ"]))


def implied_index_level(zero_dte: pd.DataFrame, *, index: str, at: pd.Timestamp,
                        window_min: int = 10, min_pairs: int = 3) -> float | None:
    """Index level implied by put-call parity on same-strike 0DTE pairs that
    printed in the ``window_min`` minutes up to ``at``: median of K + C - P.
    For a 0DTE at the close, carry is nil, so this is the cash index to a
    fraction of a point — far tighter than any proxy ratio. ``None`` when
    fewer than ``min_pairs`` strikes have both sides printing."""
    lo = at - pd.Timedelta(minutes=window_min)
    sub = zero_dte[(zero_dte["index"] == index) & (zero_dte["timestamp"] > lo)
                   & (zero_dte["timestamp"] <= at)]
    if sub.empty:
        return None
    last = sub.sort_values("timestamp").groupby(["strike", "right"])["Close"].last().unstack()
    if "C" not in last or "P" not in last:
        return None
    both = last.dropna(subset=["C", "P"])
    if len(both) < min_pairs:
        return None
    lvl = both.index.to_numpy(dtype=float) + both["C"].to_numpy() - both["P"].to_numpy()
    # restrict to the strikes nearest the first-pass estimate (deep wings print
    # stale), then take the median.
    est = float(np.median(lvl))
    near = np.argsort(np.abs(both.index.to_numpy(dtype=float) - est))[:max(min_pairs, 7)]
    return float(np.median(lvl[near]))
