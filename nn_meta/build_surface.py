# nn_meta/build_surface.py
"""Daily option-surface features per (underlying, date) → surface_daily.parquet.

The meta/student feature builders consume rvol_5/21, atm_iv_near/far,
term_slope, iv_chg_5, pc_ratio. v1 borrowed these from nn_options_signal's
dataset.parquet; v2 computes them from nn_meta's own daily bar cache using the
same primitives (implied_vol, market_features imported from
nn_options_signal.build_dataset — pure functions, no config coupling).

Run:  python -m nn_meta.build_surface   (streams the bar parts; see
      build_surface_streaming — the in-memory build_surface() is kept for
      tests and small pools)
"""
import numpy as np
import pandas as pd

from nn_options_signal.build_dataset import implied_vol, market_features
from nn_meta import config


def load_daily_bars() -> pd.DataFrame:
    """Load the per-contract daily bars, filtered per part.

    Streaming matters (2026-08-16 review finding): concatenating every raw
    part before filtering peaked past the 8 GB deploy host's RAM once the
    weekly refresh grew the v31 cache (the build was silently OOM-killed).
    Reading only the needed columns and applying the meta join + dte/premium
    filters per part keeps the peak at one part plus the survivors — the
    same rows the old path produced (identical filters, order-independent
    dedupe on identical values)."""
    parts = sorted(config.BARS_DAILY_DIR.glob("bars_part_*.parquet"))
    if not parts:
        raise SystemExit("no daily bar files — run nn_meta.download_universe first")
    meta = pd.read_parquet(config.UNIVERSE_PARQUET)[
        ["ticker", "underlying", "strike", "expiration", "type"]]
    meta["expiration"] = pd.to_datetime(meta["expiration"])
    # Index the universe ONCE (2026-09-08): ``merge(on="ticker")`` re-factorized
    # the whole universe for every part — 2,978 parts × 3.6M tickers on v5 took
    # hours at 100 % CPU before the first print. ``join`` on a prebuilt index
    # reuses its hash engine, so each part costs its own size only. Duplicate
    # universe rows would only have been removed by the final dedupe anyway.
    meta = meta.drop_duplicates("ticker").set_index("ticker")
    frames = []
    kept = 0
    for i, p in enumerate(parts, 1):
        b = pd.read_parquet(p, columns=["ticker", "date", "close", "volume"])
        if b.empty:
            continue
        b = b.join(meta, on="ticker", how="inner")
        if b.empty:
            continue
        dte = (b["expiration"] - b["date"]).dt.days
        b = b[(dte >= 1) & (dte <= config.DTE_MAX)
              & (b["close"] >= config.MIN_PREMIUM)]
        if not b.empty:
            frames.append(b)
            kept += len(b)
        if i % 500 == 0 or i == len(parts):
            print(f"  bars: {i}/{len(parts)} parts read, {kept} rows kept", flush=True)
    if not frames:
        raise SystemExit("no bars survived the universe join/filters")
    return pd.concat(frames, ignore_index=True).drop_duplicates(["ticker", "date"])


def _spot_table(und: pd.DataFrame) -> pd.DataFrame:
    return und.rename(columns={"close": "spot"})[["underlying", "date", "spot"]]


def _surface_inputs(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """From filtered bars already joined with spot: the near-ATM rows that
    feed IV, and the (underlying, date, type) volume sums that feed pc_ratio.
    These two small tables are everything the surface needs."""
    df = df.assign(moneyness=np.log(df["strike"] / df["spot"]))
    atm = df[df["moneyness"].abs() < 0.01][
        ["ticker", "underlying", "date", "close", "spot", "strike", "dte", "type"]]
    vol = df.groupby(["underlying", "date", "type"])["volume"].sum()
    return atm, vol


def _surface_from_inputs(atm: pd.DataFrame, vol: pd.Series, und: pd.DataFrame) -> pd.DataFrame:
    atm = atm.copy()
    atm["iv"] = implied_vol(atm["close"].values, atm["spot"].values,
                            atm["strike"].values, (atm["dte"] / 365.0).values,
                            (atm["type"] == "call").values)
    near = atm[atm["dte"] <= 20].groupby(["underlying", "date"])["iv"] \
        .median().rename("atm_iv_near")
    far = atm[atm["dte"] > 20].groupby(["underlying", "date"])["iv"] \
        .median().rename("atm_iv_far")
    vol_by_type = vol.groupby(level=["underlying", "date", "type"]).sum().unstack("type")
    pc = (vol_by_type.get("put") / vol_by_type.get("call")).rename("pc_ratio")

    mkt = market_features(und)
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

    cols = ["underlying", "date", "rvol_5", "rvol_21", "atm_iv_near",
            "atm_iv_far", "term_slope", "iv_chg_5", "pc_ratio"]
    return mkt[cols]


def build_surface(bars: pd.DataFrame, und: pd.DataFrame) -> pd.DataFrame:
    """In-memory path: all filtered bars at once (tests, small pools)."""
    df = bars.merge(_spot_table(und), on=["underlying", "date"], how="inner")
    df["dte"] = (df["expiration"] - df["date"]).dt.days
    df = df[(df["dte"] >= 1) & (df["dte"] <= config.DTE_MAX)
            & (df["close"] >= config.MIN_PREMIUM)]
    atm, vol = _surface_inputs(df)
    return _surface_from_inputs(atm, vol, und)


def build_surface_streaming(und: pd.DataFrame) -> pd.DataFrame:
    """Same result as ``build_surface(load_daily_bars(), und)`` without ever
    holding the bars: each part is joined, filtered and reduced to its
    near-ATM rows and volume sums, so the peak is one part plus two small
    tables. Needed on the 8 GB server — the v5 cache (27.8M rows) was
    OOM-killed (exit 137) in the in-memory path on 2026-09-09.

    Exactness across parts relies on ``download_universe.compact_bars_daily``
    (every refresh runs it before this): after compaction no ticker spans two
    parts, so per-part (ticker, date) dedupe equals the old global dedupe.
    ATM rows are additionally deduped across parts; volume sums cannot be,
    so an uncompacted cache with duplicate contracts would double-count
    pc_ratio volume — run compaction first."""
    parts = sorted(config.BARS_DAILY_DIR.glob("bars_part_*.parquet"))
    if not parts:
        raise SystemExit("no daily bar files — run nn_meta.download_universe first")
    meta = pd.read_parquet(config.UNIVERSE_PARQUET)[
        ["ticker", "underlying", "strike", "expiration", "type"]]
    meta["expiration"] = pd.to_datetime(meta["expiration"])
    meta = meta.drop_duplicates("ticker").set_index("ticker")
    spot = _spot_table(und)
    atm_parts, vol_parts = [], []
    rows_kept = 0
    for i, p in enumerate(parts, 1):
        b = pd.read_parquet(p, columns=["ticker", "date", "close", "volume"])
        if b.empty:
            continue
        b = b.drop_duplicates(["ticker", "date"]).join(meta, on="ticker", how="inner")
        if b.empty:
            continue
        dte = (b["expiration"] - b["date"]).dt.days
        b = b[(dte >= 1) & (dte <= config.DTE_MAX) & (b["close"] >= config.MIN_PREMIUM)]
        if b.empty:
            continue
        b = b.merge(spot, on=["underlying", "date"], how="inner")
        if b.empty:
            continue
        b["dte"] = (b["expiration"] - b["date"]).dt.days
        rows_kept += len(b)
        atm, vol = _surface_inputs(b)
        if not atm.empty:
            atm_parts.append(atm)
        if not vol.empty:
            vol_parts.append(vol)
        if i % 500 == 0 or i == len(parts):
            print(f"  bars: {i}/{len(parts)} parts read, {rows_kept} rows kept, "
                  f"{sum(len(a) for a in atm_parts)} near-ATM rows", flush=True)
    if not vol_parts:
        raise SystemExit("no bars survived the universe join/filters")
    atm = (pd.concat(atm_parts, ignore_index=True).drop_duplicates(["ticker", "date"])
           if atm_parts else pd.DataFrame(columns=["ticker", "underlying", "date", "close",
                                                   "spot", "strike", "dte", "type"]))
    vol = pd.concat(vol_parts)
    print(f"daily bars: {rows_kept} rows kept across {len(parts)} parts, "
          f"{len(atm)} near-ATM rows, {vol.groupby(level=[0, 1]).ngroups} (underlying, date) volume cells",
          flush=True)
    return _surface_from_inputs(atm, vol, und)


def main() -> None:
    und = pd.read_parquet(config.UNDERLYING_DAILY_PARQUET)
    surf = build_surface_streaming(und)
    tmp = config.SURFACE_DATASET_PARQUET.with_suffix(".tmp")   # atomic: the
    surf.to_parquet(tmp, index=False)                          # live scanner
    tmp.replace(config.SURFACE_DATASET_PARQUET)                # reads this
    print(f"surface: {len(surf)} (underlying, date) rows → "
          f"{config.SURFACE_DATASET_PARQUET}", flush=True)
    nan_rates = surf.drop(columns=["underlying", "date"]).isna().mean()
    print("  NaN rates: " + ", ".join(f"{c}={v:.1%}" for c, v in nan_rates.items()))


if __name__ == "__main__":
    main()
