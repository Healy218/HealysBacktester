"""Rebuild real frozen probe rows through the new forward candidate builder."""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import numpy as np
import pandas as pd

from scripts.run_v6_forward import configure
from nn_meta.live.v6_market import read, save
from nn_meta.live.v6_release import sha


def validate(args):
    configure(args.release, args.anchor)
    from nn_meta.live.v6_forward_inputs import ForwardData
    from nn_meta.live.v6_release import FrozenGBT
    from nn_meta.v6_expansion import ExpandedInputs
    from options.data.hybrid_provider import HybridCachedProvider
    original = ExpandedInputs(args.inputs, sha(args.inputs), parity_policy="deferred")
    provider = HybridCachedProvider(universe_parquet=args.source / "universe.parquet", allow_fetch=False,
        bars_cache_dir=args.output / "unused-option-bars")
    class OriginalCaptures:
        point_in_time_chain = True
        def get_chain(self,*a,**k): return provider.get_chain(*a,**k)
        def historical_chain_member(self,*a,**k): return provider.historical_chain_member(*a,**k)
        def tick_features(self, request, policy):
            if policy != original.document["tick_feature_policy"]:
                raise ValueError("frozen tick policy changed")
            frame = original.join_ticks(pd.DataFrame([request]), symbol=request["symbol"])
            return frame.iloc[0].to_dict()
    model = FrozenGBT(args.release, args.anchor)
    probe = pd.read_parquet(args.release / "prediction_probe.parquet")
    cases = probe.iloc[[0, 2, 4]]
    data = ForwardData.__new__(ForwardData)
    data.root = args.output
    args.output.mkdir(parents=True, exist_ok=True)
    data.training = read(args.release / "training-inputs.json")
    data.spec = read(args.release / "baseline_spec.json")
    data.calendar_doc = read(args.source / "exchange_calendar.json")
    save(args.output / "calendar.json", data.calendar_doc)
    data.surface = pd.read_parquet(args.source / "surface_daily.parquet")
    daily = pd.read_parquet(args.source / "underlying_daily.parquet")
    px = daily.pivot(index="date", columns="underlying", values="close").sort_index()
    rets = px.pct_change(fill_method="pad")
    beta = rets.rolling(60).cov(rets.SPY).div(rets.SPY.rolling(60).var(), axis=0).stack().rename("beta_60d").reset_index()
    ctx = data.surface[["underlying", "date", "rvol_21", "atm_iv_near"]].copy()
    ctx["market_iv"] = ctx.date.map(data.surface[data.surface.underlying == "SPY"].set_index("date").atm_iv_near)
    ctx["rv_iv_spread"] = ctx.rvol_21 - ctx.atm_iv_near
    data.context = ctx.drop(columns=["rvol_21", "atm_iv_near"]).merge(beta, on=["underlying", "date"], how="left")
    tech = pd.read_parquet(args.source / "underlying_15m.parquet", filters=[("symbol", "in", cases.symbol.tolist())])
    raw = pd.read_parquet(args.source / "underlying_15m_raw.parquet", filters=[("symbol", "in", cases.symbol.tolist())])
    results = []
    for number, expected in cases.iterrows():
        symbol = expected.symbol
        fields = ["Open", "High", "Low", "Close", "Volume"]
        data.bars = {symbol: tech[tech.symbol == symbol].set_index("timestamp")[fields].sort_index()}
        data.raw = {symbol: raw[raw.symbol == symbol].set_index("timestamp")[fields].sort_index()}
        fresh = dict(symbol=symbol, strategy=expected.strategy, direction=int(expected.dir_short),
            entry_ts=expected.entry_ts, bars_since_signal=int(round(np.expm1(expected.bars_since_signal))),
            spot=float(data.bars[symbol].loc[expected.entry_ts, "Close"]))
        batch, _ = data.candidates([fresh], OriginalCaptures(), args.output / f"case-{number}")
        actual = batch[batch.dte == expected.dte]
        if len(actual) != 1:
            raise ValueError("forward DTE identity differs")
        a = actual[model.features].iloc[0].to_numpy(float)
        e = expected[model.features].to_numpy(float)
        difference = np.abs(a - e)
        bad = ~(np.isclose(a, e, rtol=1e-10, atol=1e-10, equal_nan=True))
        if bad.any():
            save(args.output / "failure.json", {"symbol":symbol,"strategy":expected.strategy,
                "mismatches": [{"feature": name,"actual":float(x) if np.isfinite(x) else None,"expected":float(y) if np.isfinite(y) else None}
                    for name,x,y,fail in zip(model.features,a,e,bad) if fail]})
            raise ValueError(f"{symbol}: {bad.sum()} rebuilt feature(s) differ")
        pred, ev = float(model.score(actual)[0]), float(model.ev(actual)[0])
        np.testing.assert_allclose([pred, ev], [expected.pred_ensemble, expected.ev_ensemble], rtol=1e-9, atol=1e-10)
        results.append({"symbol":symbol,"strategy":expected.strategy,"dte":int(expected.dte),
            "entry_ts":str(expected.entry_ts),"features":len(model.features),
            "max_feature_absolute_error":float(np.nanmax(difference)),
            "classifier_error":abs(pred-expected.pred_ensemble),"ev_error":abs(ev-expected.ev_ensemble)})
        print(json.dumps(results[-1]),flush=True)
    report = {"status":"passed","release_sha256":args.anchor,"cases":results,
        "validation":"Full forward feature construction against saved actual historical rows; original captured MASSIVE bytes and original stock vintage",
        "live_entitlement_verified":False}
    save(args.output / "report.json", report)
    return report


if __name__ == "__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--release",type=Path,required=True)
    ap.add_argument("--anchor",required=True)
    ap.add_argument("--source",type=Path,required=True)
    ap.add_argument("--inputs",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    args.release=args.release.absolute(); args.source=args.source.absolute(); args.output=args.output.absolute()
    validate(args)
