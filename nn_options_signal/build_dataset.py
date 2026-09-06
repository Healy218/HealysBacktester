# nn_options_signal/build_dataset.py
"""Panel construction: (decision date, contract) rows with features + labels.

Multi-underlying: one pooled panel across config.UNDERLYINGS. All features are
spot-normalized (moneyness, IV, premium/spot) so contracts from different
names share one feature space; market-state features are computed per
underlying from its own daily bars. No symbol-identity feature — the model
must generalize cross-sectionally.

Features use only information available at the decision day's close.
Labels: net % return of the contract entered at the NEXT day's open and exited
at the close H trading days later (earlier if DTE <= FORCE_EXIT_DTE), with the
per-side cost haircut applied, winsorized to LABEL_CLIP.

Run:  python -m nn_options_signal.build_dataset
"""
import numpy as np
import pandas as pd
from scipy.special import ndtr  # standard normal CDF, vectorized

from nn_options_signal import config

FEATURES = [
    "moneyness", "dte_frac", "iv", "prem_spot", "log_volume", "log_transactions",
    "vwap_dev", "is_call", "c_ret_1", "c_ret_3",
    "und_ret_1", "und_ret_5", "und_ret_21", "rvol_5", "rvol_21", "gap",
    "atm_iv_near", "atm_iv_far", "term_slope", "iv_chg_5", "pc_ratio", "dow",
]
LABELS = [f"label_h{h}" for h in config.HORIZONS]
DATASET_VERSION = "2026-09-05-exit-purged"


def require_current_panel(panel):
    if panel.attrs.get("options_signal_version") != DATASET_VERSION:
        raise ValueError("stale options signal dataset; rebuild with exit-aware purging")


def purge_label_boundaries(panel):
    """Invalidate future partition outcomes without hiding entry candidates."""
    panel = panel.copy()
    for h in config.HORIZONS:
        exit_col = f"exit_date_h{h}"
        exits = pd.to_datetime(panel[exit_col])
        crosses = (((panel["split"] == "train") & (exits >= pd.Timestamp(config.VAL_START)))
                   | ((panel["split"] == "val") & (exits >= pd.Timestamp(config.TEST_START)))
                   | ((panel["split"] == "test") & (exits > pd.Timestamp(config.TEST_END))))
        panel.loc[crosses, [f"label_h{h}", f"exit_close_h{h}"]] = np.nan
        panel.loc[crosses, exit_col] = pd.NaT
    return panel


# ── Black-Scholes IV (European approx; documented limitation for American) ───
def bs_price(S, K, T, sigma, r, q, is_call):
    sqrtT = np.sqrt(np.maximum(T, 1e-9))
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * sqrtT)
    d2 = d1 - sigma * sqrtT
    call = S * np.exp(-q * T) * ndtr(d1) - K * np.exp(-r * T) * ndtr(d2)
    put = K * np.exp(-r * T) * ndtr(-d2) - S * np.exp(-q * T) * ndtr(-d1)
    return np.where(is_call, call, put)


def implied_vol(price, S, K, T, is_call, r=config.RISK_FREE_RATE,
                q=config.DIVIDEND_YIELD, iters=48):
    lo = np.full_like(price, 0.01, dtype=float)
    hi = np.full_like(price, 5.0, dtype=float)
    intrinsic = np.where(is_call, np.maximum(S * np.exp(-q * T) - K * np.exp(-r * T), 0),
                         np.maximum(K * np.exp(-r * T) - S * np.exp(-q * T), 0))
    solvable = price > intrinsic + 1e-6
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        too_high = bs_price(S, K, T, mid, r, q, is_call) > price
        hi = np.where(too_high, mid, hi)
        lo = np.where(too_high, lo, mid)
    iv = 0.5 * (lo + hi)
    return np.where(solvable, iv, np.nan)


def load_bars() -> pd.DataFrame:
    parts = sorted(config.BARS_DIR.glob("bars_part_*.parquet"))
    if not parts:
        raise SystemExit("no bar files — run download_bars first")
    bars = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
    bars = bars.drop_duplicates(["ticker", "date"])
    meta = pd.read_parquet(config.UNIVERSE_PARQUET)[
        ["ticker", "underlying", "strike", "expiration", "type"]]
    bars = bars.merge(meta, on="ticker", how="inner")
    bars = bars.sort_values(["ticker", "date"]).reset_index(drop=True)
    return bars


def market_features(und: pd.DataFrame) -> pd.DataFrame:
    """Per-(underlying, date) market-state features from underlying bars."""
    frames = []
    for sym, s in und.groupby("underlying"):
        s = s.sort_values("date").set_index("date")
        lr = np.log(s["close"]).diff()
        mkt = pd.DataFrame({
            "und_ret_1": s["close"].pct_change(),
            "und_ret_5": s["close"].pct_change(5),
            "und_ret_21": s["close"].pct_change(21),
            "rvol_5": lr.rolling(5).std() * np.sqrt(252),
            "rvol_21": lr.rolling(21).std() * np.sqrt(252),
            "gap": s["open"] / s["close"].shift(1) - 1,
        })
        mkt["underlying"] = sym
        frames.append(mkt.reset_index())
    return pd.concat(frames, ignore_index=True)


def build_panel(bars: pd.DataFrame, und: pd.DataFrame) -> pd.DataFrame:
    spot = und.rename(columns={"close": "spot"})[["underlying", "date", "spot"]]
    df = bars.merge(spot, on=["underlying", "date"], how="inner")
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)
    df["dte"] = (df["expiration"] - df["date"]).dt.days
    df["moneyness"] = np.log(df["strike"] / df["spot"])
    df["is_call"] = (df["type"] == "call").astype(float)

    # ── labels from the contract's own bar sequence (positional shifts) ──────
    g = df.groupby("ticker", sort=False)
    df["next_open"] = g["open"].shift(-1)
    df["next_date"] = g["date"].shift(-1)
    df["pos"] = g.cumcount()
    ok_dte = df["dte"] >= config.FORCE_EXIT_DTE
    cutoff = df[ok_dte].groupby("ticker")["pos"].max().rename("cutoff_pos")
    df = df.merge(cutoff, on="ticker", how="left")

    own_key = df["ticker"].astype(str) + "_" + df["pos"].astype(str)
    close_lookup = pd.Series(df["close"].values, index=own_key.values)
    date_lookup = pd.Series(df["date"].values, index=own_key.values)
    for h in config.HORIZONS:
        exit_pos = np.minimum(df["pos"] + 1 + h, df["cutoff_pos"])
        key = df["ticker"].astype(str) + "_" + exit_pos.astype("Int64").astype(str)
        exit_close = key.map(close_lookup)
        exit_date = pd.to_datetime(key.map(date_lookup))
        valid = (exit_pos > df["pos"] + 1) & exit_close.notna() & df["next_open"].notna() \
                & (df["next_open"] >= config.MIN_PREMIUM) \
                & ((df["next_date"] - df["date"]).dt.days <= 4) \
                & ((exit_date - df["date"]).dt.days <= (h + 1) * 4)
        c = config.COST_PER_SIDE_PCT
        comm = 2 * config.COMMISSION_PER_CONTRACT / config.CONTRACT_MULTIPLIER
        entry_cost = df["next_open"] * (1 + c)
        net = (exit_close * (1 - c) - entry_cost - comm) / entry_cost
        df[f"label_h{h}"] = np.where(valid, net.clip(*config.LABEL_CLIP), np.nan)
        # raw prices kept so the simulator can replay trades at any cost level
        df[f"exit_close_h{h}"] = np.where(valid, exit_close, np.nan)
        df[f"exit_date_h{h}"] = pd.Series(np.where(valid, exit_date, pd.NaT), index=df.index)
    df["entry_open"] = df["next_open"]

    # ── panel eligibility at the decision close ──────────────────────────────
    m = (df["date"] >= config.WINDOW_START) & (df["date"] <= config.WINDOW_END) \
        & (df["dte"] >= config.DTE_MIN) & (df["dte"] <= config.DTE_MAX) \
        & (df["moneyness"].abs() <= config.MONEYNESS_BAND) \
        & (df["volume"] >= config.MIN_VOLUME) & (df["close"] >= config.MIN_PREMIUM)
    panel = df[m].copy()

    # ── contract features ─────────────────────────────────────────────────────
    panel["iv"] = implied_vol(panel["close"].values, panel["spot"].values,
                              panel["strike"].values, (panel["dte"] / 365.0).values,
                              panel["is_call"].values.astype(bool))
    panel["dte_frac"] = panel["dte"] / config.DTE_MAX
    panel["prem_spot"] = panel["close"] / panel["spot"]
    panel["log_volume"] = np.log1p(panel["volume"])
    panel["log_transactions"] = np.log1p(panel["transactions"].fillna(0))
    panel["vwap_dev"] = (panel["close"] / panel["vwap"] - 1).fillna(0)
    gp = panel.sort_values(["ticker", "date"]).groupby("ticker")
    panel["c_ret_1"] = gp["close"].pct_change().fillna(0).clip(-1, 3)
    panel["c_ret_3"] = gp["close"].pct_change(3).fillna(0).clip(-1, 3)

    # ── market features per (underlying, date) ────────────────────────────────
    mkt = market_features(und)

    atm = panel[panel["moneyness"].abs() < 0.01]
    near = atm[atm["dte"] <= 20].groupby(["underlying", "date"])["iv"].median().rename("atm_iv_near")
    far = atm[atm["dte"] > 20].groupby(["underlying", "date"])["iv"].median().rename("atm_iv_far")
    vol_by_type = panel.pivot_table(index=["underlying", "date"], columns="type",
                                    values="volume", aggfunc="sum")
    pc = (vol_by_type.get("put") / vol_by_type.get("call")).rename("pc_ratio")
    mkt = mkt.merge(near.reset_index(), on=["underlying", "date"], how="left") \
             .merge(far.reset_index(), on=["underlying", "date"], how="left") \
             .merge(pc.reset_index(), on=["underlying", "date"], how="left")
    mkt = mkt.sort_values(["underlying", "date"])
    gm = mkt.groupby("underlying")
    mkt["atm_iv_near"] = gm["atm_iv_near"].ffill()
    mkt["atm_iv_far"] = gm["atm_iv_far"].ffill()
    mkt["term_slope"] = mkt["atm_iv_far"] - mkt["atm_iv_near"]
    mkt["iv_chg_5"] = gm["atm_iv_near"].diff(5)
    mkt["pc_ratio"] = gm["pc_ratio"].transform(lambda s: s.clip(0, 5).ffill())

    panel = panel.merge(mkt, on=["underlying", "date"], how="left")
    panel["dow"] = panel["date"].dt.dayofweek / 4.0
    panel["iv"] = panel["iv"].fillna(panel["atm_iv_near"])

    # ── purged time splits ────────────────────────────────────────────────────
    d = panel["date"]
    panel["split"] = np.select(
        [(d >= config.TRAIN_START) & (d <= config.TRAIN_END),
         (d >= config.VAL_START) & (d <= config.VAL_END),
         (d >= config.TEST_START) & (d <= config.TEST_END)],
        ["train", "val", "test"], default="purged")
    panel = panel[panel["split"] != "purged"]

    # Sparse contract bars can make a nominal H-day label extend beyond the
    # calendar gap. Never expose the next partition's outcomes to fitting or
    # validation. Keep the proposal; a simulator selecting it must explicitly
    # resolve the absent valuation rather than silently substitute a survivor.
    panel = purge_label_boundaries(panel)

    trade_cols = ["entry_open"] + [f"exit_close_h{h}" for h in config.HORIZONS] \
                 + [f"exit_date_h{h}" for h in config.HORIZONS]
    keep = ["date", "ticker", "underlying", "strike", "expiration", "type", "dte",
            "open", "close", "volume", "spot", "split"] + FEATURES + LABELS + trade_cols
    keep = list(dict.fromkeys(keep))          # dedupe, preserve order
    panel = panel[keep].dropna(subset=FEATURES)
    panel.attrs["options_signal_version"] = DATASET_VERSION
    return panel.sort_values(["date", "ticker"]).reset_index(drop=True)


def main() -> None:
    und = pd.read_parquet(config.UNDERLYING_PARQUET)
    bars = load_bars()
    print(f"bars loaded: {len(bars)} rows, {bars['ticker'].nunique()} contracts, "
          f"{bars['underlying'].nunique()} underlyings")
    panel = build_panel(bars, und)
    panel.to_parquet(config.DATASET_PARQUET, index=False)

    print(f"\npanel: {len(panel)} rows, {panel['date'].nunique()} days, "
          f"{panel['ticker'].nunique()} contracts")
    by_und = panel.groupby("underlying").size().sort_values(ascending=False)
    print("  rows by underlying: " + ", ".join(f"{s}={n}" for s, n in by_und.items()))
    for s in ("train", "val", "test"):
        sub = panel[panel["split"] == s]
        print(f"  {s:5s}: {len(sub):7d} rows | {sub['date'].nunique():3d} days | "
              f"{sub['date'].min().date()} → {sub['date'].max().date()}")
    for lab in LABELS:
        v = panel[lab].dropna()
        print(f"  {lab}: n={len(v)} mean={v.mean():+.3f} median={v.median():+.3f} "
              f"p5={v.quantile(.05):+.2f} p95={v.quantile(.95):+.2f} "
              f"| %>0: {(v > 0).mean():.1%}")
    nan_rates = panel[FEATURES].isna().mean()
    bad = nan_rates[nan_rates > 0]
    print(f"  feature NaN rates: {'all zero' if bad.empty else bad.to_dict()}")


if __name__ == "__main__":
    main()
