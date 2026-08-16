# nn_meta/build_surface.py
"""Daily option-surface features per (underlying, date) → surface_daily.parquet.

The meta/student feature builders consume rvol_5/21, atm_iv_near/far,
term_slope, iv_chg_5, pc_ratio. v1 borrowed these from nn_options_signal's
dataset.parquet; v2 computes them from nn_meta's own daily bar cache using the
same primitives (implied_vol, market_features imported from
nn_options_signal.build_dataset — pure functions, no config coupling).

Run:  python -m nn_meta.build_surface
"""
import numpy as np
import pandas as pd

from nn_options_signal.build_dataset import implied_vol, market_features
from nn_meta import config


def load_daily_bars() -> pd.DataFrame:
    parts = sorted(config.BARS_DAILY_DIR.glob("bars_part_*.parquet"))
    if not parts:
        raise SystemExit("no daily bar files — run nn_meta.download_universe first")
    bars = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
    bars = bars.drop_duplicates(["ticker", "date"])
    meta = pd.read_parquet(config.UNIVERSE_PARQUET)[
        ["ticker", "underlying", "strike", "expiration", "type"]]
    return bars.merge(meta, on="ticker", how="inner")


def build_surface(bars: pd.DataFrame, und: pd.DataFrame) -> pd.DataFrame:
    spot = und.rename(columns={"close": "spot"})[["underlying", "date", "spot"]]
    df = bars.merge(spot, on=["underlying", "date"], how="inner")
    df["dte"] = (df["expiration"] - df["date"]).dt.days
    df = df[(df["dte"] >= 1) & (df["dte"] <= config.DTE_MAX)
            & (df["close"] >= config.MIN_PREMIUM)]
    df["moneyness"] = np.log(df["strike"] / df["spot"])

    # IV only where it feeds a feature: near-ATM rows (same band as v1)
    atm = df[df["moneyness"].abs() < 0.01].copy()
    atm["iv"] = implied_vol(atm["close"].values, atm["spot"].values,
                            atm["strike"].values, (atm["dte"] / 365.0).values,
                            (atm["type"] == "call").values)
    near = atm[atm["dte"] <= 20].groupby(["underlying", "date"])["iv"] \
        .median().rename("atm_iv_near")
    far = atm[atm["dte"] > 20].groupby(["underlying", "date"])["iv"] \
        .median().rename("atm_iv_far")
    vol_by_type = df.pivot_table(index=["underlying", "date"], columns="type",
                                 values="volume", aggfunc="sum")
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


def main() -> None:
    und = pd.read_parquet(config.UNDERLYING_DAILY_PARQUET)
    bars = load_daily_bars()
    print(f"daily bars: {len(bars)} rows, {bars['ticker'].nunique()} contracts, "
          f"{bars['underlying'].nunique()} underlyings")
    surf = build_surface(bars, und)
    tmp = config.SURFACE_DATASET_PARQUET.with_suffix(".tmp")   # atomic: the
    surf.to_parquet(tmp, index=False)                          # live scanner
    tmp.replace(config.SURFACE_DATASET_PARQUET)                # reads this
    print(f"surface: {len(surf)} (underlying, date) rows → "
          f"{config.SURFACE_DATASET_PARQUET}")
    nan_rates = surf.drop(columns=["underlying", "date"]).isna().mean()
    print("  NaN rates: " + ", ".join(f"{c}={v:.1%}" for c, v in nan_rates.items()))


if __name__ == "__main__":
    main()
