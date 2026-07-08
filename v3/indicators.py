# v3/indicators.py — Stage 3: vectorized indicator library (pandas/numpy only).
"""Every indicator TradingView's Technical Ratings uses, plus the community
set from V3_SPEC (SuperTrend, Squeeze Momentum). Pure math — the -1/0/+1
scoring rules live in v3/tv_rating.py.

Inputs are OHLCV DataFrames with columns Open/High/Low/Close/Volume (the
repo's standard shape). All rolling logic looks backward only — no leaks.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ── moving averages ──────────────────────────────────────────────────────────

def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rma(s: pd.Series, n: int) -> pd.Series:
    """Wilder's smoothing (TV's ta.rma)."""
    return s.ewm(alpha=1 / n, adjust=False).mean()


def wma(s: pd.Series, n: int) -> pd.Series:
    w = np.arange(1, n + 1, dtype=float)
    return s.rolling(n).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)


def hma(s: pd.Series, n: int = 9) -> pd.Series:
    return wma(2 * wma(s, n // 2) - wma(s, n), int(np.sqrt(n)))


def vwma(close: pd.Series, volume: pd.Series, n: int = 20) -> pd.Series:
    return (close * volume).rolling(n).sum() / volume.rolling(n).sum()


def ichimoku(df: pd.DataFrame) -> pd.DataFrame:
    """conversion/base/span_a/span_b, spans NOT displaced (rating rules
    compare current values, mirroring TV's rating computation)."""
    h, l = df["High"], df["Low"]

    def mid(n):
        return (h.rolling(n).max() + l.rolling(n).min()) / 2

    conv, base = mid(9), mid(26)
    return pd.DataFrame({"conversion": conv, "base": base,
                         "span_a": (conv + base) / 2, "span_b": mid(52)})


# ── oscillators ───────────────────────────────────────────────────────────────

def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = rma(d.clip(lower=0), n)
    dn = rma(-d.clip(upper=0), n)
    # 100*up/(up+dn) ≡ 100 - 100/(1+up/dn), but well-defined when dn == 0
    return 100 * up / (up + dn).replace(0, np.nan)


def stochastic(df: pd.DataFrame, n: int = 14, k: int = 3, d: int = 3) -> pd.DataFrame:
    ll = df["Low"].rolling(n).min()
    hh = df["High"].rolling(n).max()
    raw = 100 * (df["Close"] - ll) / (hh - ll).replace(0, np.nan)
    ks = raw.rolling(k).mean()
    return pd.DataFrame({"k": ks, "d": ks.rolling(d).mean()})


def stoch_rsi(close: pd.Series, rsi_n: int = 14, stoch_n: int = 14,
              k: int = 3, d: int = 3) -> pd.DataFrame:
    r = rsi(close, rsi_n)
    lo = r.rolling(stoch_n).min()
    hi = r.rolling(stoch_n).max()
    raw = 100 * (r - lo) / (hi - lo).replace(0, np.nan)
    ks = raw.rolling(k).mean()
    return pd.DataFrame({"k": ks, "d": ks.rolling(d).mean()})


def cci(df: pd.DataFrame, n: int = 20) -> pd.Series:
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    mad = tp.rolling(n).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    return (tp - sma(tp, n)) / (0.015 * mad.replace(0, np.nan))


def true_range(df: pd.DataFrame) -> pd.Series:
    pc = df["Close"].shift()
    return pd.concat([df["High"] - df["Low"], (df["High"] - pc).abs(),
                      (df["Low"] - pc).abs()], axis=1).max(axis=1)


def adx(df: pd.DataFrame, n: int = 14) -> pd.DataFrame:
    up = df["High"].diff()
    dn = -df["Low"].diff()
    plus_dm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    atr = rma(true_range(df), n)
    plus_di = 100 * rma(plus_dm, n) / atr
    minus_di = 100 * rma(minus_dm, n) / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return pd.DataFrame({"adx": rma(dx, n), "plus_di": plus_di,
                         "minus_di": minus_di})


def awesome_oscillator(df: pd.DataFrame) -> pd.Series:
    mid = (df["High"] + df["Low"]) / 2
    return sma(mid, 5) - sma(mid, 34)


def momentum(close: pd.Series, n: int = 10) -> pd.Series:
    return close - close.shift(n)


def macd(close: pd.Series, fast: int = 12, slow: int = 26,
         signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = ema(line, signal)
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def williams_r(df: pd.DataFrame, n: int = 14) -> pd.Series:
    hh = df["High"].rolling(n).max()
    ll = df["Low"].rolling(n).min()
    return -100 * (hh - df["Close"]) / (hh - ll).replace(0, np.nan)


def bull_bear_power(df: pd.DataFrame, n: int = 13) -> pd.DataFrame:
    e = ema(df["Close"], n)
    return pd.DataFrame({"bull": df["High"] - e, "bear": df["Low"] - e})


def ultimate_oscillator(df: pd.DataFrame, n1: int = 7, n2: int = 14,
                        n3: int = 28) -> pd.Series:
    pc = df["Close"].shift()
    bp = df["Close"] - pd.concat([df["Low"], pc], axis=1).min(axis=1)
    tr = true_range(df)

    def avg(n):
        return bp.rolling(n).sum() / tr.rolling(n).sum().replace(0, np.nan)

    return 100 * (4 * avg(n1) + 2 * avg(n2) + avg(n3)) / 7


# ── community set (V3_SPEC curated list) ─────────────────────────────────────

def supertrend(df: pd.DataFrame, n: int = 10, mult: float = 3.0) -> pd.DataFrame:
    """Classic ATR trailing bands. direction: +1 long regime, -1 short."""
    atr = rma(true_range(df), n)
    mid = (df["High"] + df["Low"]) / 2
    upper = (mid + mult * atr).to_numpy()
    lower = (mid - mult * atr).to_numpy()
    close = df["Close"].to_numpy()

    st = np.full(len(df), np.nan)
    direction = np.zeros(len(df))
    up, lo, dirn = upper[0], lower[0], 1
    for i in range(1, len(df)):
        lo = max(lower[i], lo) if close[i - 1] > lo else lower[i]
        up = min(upper[i], up) if close[i - 1] < up else upper[i]
        if dirn == 1 and close[i] < lo:
            dirn = -1
        elif dirn == -1 and close[i] > up:
            dirn = 1
        st[i] = lo if dirn == 1 else up
        direction[i] = dirn
    return pd.DataFrame({"supertrend": st, "direction": direction},
                        index=df.index)


def squeeze_momentum(df: pd.DataFrame, bb_n: int = 20, bb_mult: float = 2.0,
                     kc_n: int = 20, kc_mult: float = 1.5) -> pd.DataFrame:
    """LazyBear's Squeeze Momentum: BB inside Keltner = squeeze on;
    momentum = linear-regression slope proxy of de-meaned price."""
    close = df["Close"]
    basis = sma(close, bb_n)
    dev = bb_mult * close.rolling(bb_n).std(ddof=0)
    kc_mid = sma(close, kc_n)
    kc_rng = kc_mult * rma(true_range(df), kc_n)
    squeeze_on = ((basis - dev) > (kc_mid - kc_rng)) & \
                 ((basis + dev) < (kc_mid + kc_rng))

    hh = df["High"].rolling(kc_n).max()
    ll = df["Low"].rolling(kc_n).min()
    center = ((hh + ll) / 2 + kc_mid) / 2
    x = np.arange(kc_n) - (kc_n - 1) / 2
    mom = (close - center).rolling(kc_n).apply(
        lambda y: float(np.dot(x, y - y.mean()) / np.dot(x, x)), raw=True)
    return pd.DataFrame({"squeeze_on": squeeze_on, "momentum": mom})
