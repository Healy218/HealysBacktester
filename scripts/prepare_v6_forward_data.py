"""Prepare V6's full-history stock and prior-session option context separately.

Runs on the home data host. The completed manifest is written last; a reader
never accepts an incomplete refresh. Completed training inputs stay immutable.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import gzip
import io
import hashlib

import pandas as pd
from dotenv import load_dotenv

from nn_meta.live.v6_market import alpaca_bars, read, save, utcnow
from nn_meta.live.v6_release import sha, verify_release
from nn_meta.price_basis import raw_spot_provenance, require_raw_panel
from nn_meta.session_calendar import SessionCalendar


def daily_frame_from_minutes(frame, symbols):
    """Associative daily OHLCV equivalent to minute→15m→daily aggregation.

    Avoid 200,000 Python resampler instances per date. The option volume
    contract is integral, so the existing per-15m integer conversion cannot
    change the sum. Reject fractional input rather than change that contract.
    """
    roots = frame.ticker.str.extract(r'^O:([A-Z]+)\d{6}[CP]\d+$', expand=False)
    frame = frame.loc[roots.isin(symbols)].copy()
    if ((frame.volume < 0) | (frame.volume % 1 != 0)).any():
        raise ValueError("option aggregate volume must be integral and nonnegative")
    frame = frame.sort_values(['ticker', 'window_start'], kind='stable')
    daily = frame.groupby('ticker', sort=True).agg(open=('open','first'), high=('high','max'),
        low=('low','min'), close=('close','last'), volume=('volume','sum')).dropna(subset=['close']).reset_index()
    daily['occ'] = daily.ticker.str.removeprefix('O:')
    return daily.rename(columns={c:c.capitalize() for c in ('open','high','low','close','volume')})[['occ','Open','High','Low','Close','Volume']]


def context_day(client, day, output, symbols):
    old = output / 'flatfiles_15m' / f'{day}.parquet'
    if old.exists():
        return old
    path = output / 'option_daily' / f'{day}.parquet'
    if path.exists():
        return path
    year, month, _ = day.split('-')
    key = f'us_options_opra/minute_aggs_v1/{year}/{month}/{day}.csv.gz'
    response = client.get_object(Bucket='flatfiles', Key=key)
    raw = response['Body'].read()
    frame = daily_frame_from_minutes(pd.read_csv(io.BytesIO(gzip.decompress(raw))), set(symbols))
    if frame.empty:
        raise ValueError(f'empty whole-market option aggregate session {day}')
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path.with_suffix('.tmp'), index=False)
    path.with_suffix('.tmp').replace(path)
    save(path.with_suffix('.receipt.json'), {'provider':'massive_flatfiles', 'key':key,
        'download_sha256':hashlib.sha256(raw).hexdigest(), 'output_sha256':sha(path),
        'received_at':utcnow().isoformat(), 'transformation':'minute_to_daily_associative_OHLCV'})
    return path


def daily_schema(panel):
    frame = panel.rename(columns={"symbol": "underlying", "timestamp": "date", **{k: k.lower() for k in ("Open", "High", "Low", "Close", "Volume")}})
    frame["date"] = pd.to_datetime(frame.date).dt.normalize()
    frame["vwap"], frame["transactions"] = float("nan"), float("nan")
    return frame


def stock_history(source, output, symbols, calendar, through):
    target_end = pd.Timestamp(through, tz="America/New_York") + pd.Timedelta(days=1)
    source_tech = pd.read_parquet(source / "underlying_15m.parquet")
    source_raw = require_raw_panel(pd.read_parquet(source / "underlying_15m_raw.parquet"), "15m")
    origin = source_tech.timestamp.min()
    last = source_tech.timestamp.max().normalize()
    start = last.tz_localize("UTC")
    histories = {}
    def fetch(kind):
        interval, adjustment = kind
        # Daily closes are refreshed from the original origin, retaining the
        # rolling-beta adjustment vintage rather than splicing adjusted levels.
        beginning = pd.Timestamp(origin).tz_localize("UTC").normalize() if interval == "1Day" else start
        return kind, alpaca_bars(symbols, beginning, target_end, timeframe=interval, adjustment=adjustment)
    with ThreadPoolExecutor(max_workers=2) as pool:
        for kind, frame in pool.map(fetch, [("15Min", "all"), ("15Min", "raw"), ("1Day", "all"), ("1Day", "raw")]):
            histories[kind] = frame
            print(json.dumps({"stock_refresh": list(kind), "rows": len(frame), "symbols": frame.symbol.nunique()}), flush=True)
    fresh_tech = histories[("15Min", "all")]
    # A split/dividend can restate technical history. Detect overlap changes
    # and fetch the full affected series rather than joining price vintages.
    old = source_tech[source_tech.timestamp >= last][["symbol", "timestamp", "Close"]]
    overlap = old.merge(fresh_tech[["symbol", "timestamp", "Close"]], on=["symbol", "timestamp"], suffixes=("_old", "_new"))
    revised = sorted(set(overlap.loc[(overlap.Close_old / overlap.Close_new - 1).abs() > 1e-7, "symbol"]))
    replacements = None
    if revised:
        replacements = alpaca_bars(revised, pd.Timestamp(origin).tz_localize("UTC").normalize(), target_end, timeframe="15Min", adjustment="all")
        print(json.dumps({"full_history_restatement": revised, "rows": len(replacements)}), flush=True)
    directory = output / "stocks"
    directory.mkdir(exist_ok=True)
    inventory = {}
    for symbol in symbols:
        fields = {}
        for adjustment, original in [("all", source_tech), ("raw", source_raw)]:
            base = original[original.symbol == symbol].copy()
            fresh = histories[("15Min", adjustment)]
            fresh = fresh[fresh.symbol == symbol].copy()
            if adjustment == "all" and symbol in revised:
                panel = replacements[replacements.symbol == symbol].copy()
            else:
                base.attrs = {}; fresh.attrs = {}
                panel = pd.concat([base[base.timestamp < last], fresh], ignore_index=True)
            bars = calendar.filter(panel.set_index("timestamp")).drop(columns="symbol")
            if bars.empty or bars.index[0] != original.loc[original.symbol == symbol, "timestamp"].min():
                raise ValueError(f"{symbol}: original history origin is missing after refresh")
            if bars.index.has_duplicates:
                raise ValueError(f"{symbol}: duplicate refreshed stock timestamps")
            fields[adjustment] = bars
        if not fields["all"].index.equals(fields["raw"].index):
            raise ValueError(f"{symbol}: raw and technical timelines differ")
        refs = {}
        for adjustment, bars in fields.items():
            bars.attrs = dict(raw_spot_provenance("15m", provider="alpaca", feed="sip"), symbol=symbol) if adjustment == "raw" else dict(provider="alpaca", feed="sip", adjustment="all")
            path = directory / f"{symbol}.{adjustment}.parquet"
            bars.to_parquet(path)
            refs[adjustment] = {"path": str(path.relative_to(output)), "sha256": sha(path)}
        inventory[symbol] = {"files": refs, "history_origin": fields["all"].index[0].isoformat(),
                             "last_bar": fields["all"].index[-1].isoformat(), "rows": len(fields["all"])}
    for adjustment in ("all", "raw"):
        daily = daily_schema(histories[("1Day", adjustment)])
        if adjustment == "raw":
            daily.attrs = raw_spot_provenance("1d", provider="alpaca", feed="sip")
        daily.to_parquet(output / f"daily.{adjustment}.parquet", index=False)
    return inventory, revised


def surface_context(source, output, symbols, calendar, through):
    from nn_meta import config
    from nn_meta.build_surface import build_surface
    from nn_meta.price_basis import raw_daily_for_roots
    from v3.derive_contracts import daily_from_frame, parse_occ
    from v3.flatfiles import _client
    # Preserve every prior option observation/filter; append the identical
    # raw-spot derivation on new whole-market MASSIVE aggregate files.
    meta = pd.read_parquet(source / "universe.parquet", columns=["ticker", "underlying", "strike", "expiration", "type"])
    frames = []
    for path in sorted((source / "bars_daily").glob("bars_part_*.parquet")):
        part = pd.read_parquet(path, columns=["ticker", "date", "close", "volume"])
        frames.append(part.merge(meta, on="ticker", how="inner"))
    old = pd.concat(frames, ignore_index=True).drop_duplicates(["ticker", "date"])
    del frames, meta
    last = pd.to_datetime(old.date).max().date().isoformat()
    raw = require_raw_panel(pd.read_parquet(output / "daily.raw.parquet"), "1d")
    # Some historical OCC roots renamed; the training surface binds these
    # aliases too. Retain old raw history for roots absent from today's spec.
    original_raw = pd.read_parquet(source / "underlying_daily_raw.parquet")
    attrs = dict(raw.attrs)
    raw.attrs = {}; original_raw.attrs = {}
    raw = pd.concat([original_raw, raw], ignore_index=True).drop_duplicates(["underlying", "date"], keep="last")
    raw.attrs = attrs
    spots = raw_daily_for_roots(raw, config.TICKER_ALIASES).set_index(["underlying", "date"])["close"]
    extra, receipts = [], []
    client = _client()
    for day in calendar.sessions:
        if not last < day <= through:
            continue
        path = context_day(client, day, output, symbols)
        if path is None:
            raise ValueError(f"missing MASSIVE option aggregate session {day}")
        daily, observed = daily_from_frame(pd.read_parquet(path), pd.Timestamp(day), spots)
        parsed = daily.ticker.str.removeprefix("O:").map(parse_occ)
        daily["underlying"] = parsed.map(lambda v: v[0])
        daily["expiration"] = parsed.map(lambda v: v[1])
        daily["type"] = parsed.map(lambda v: v[2])
        daily["strike"] = parsed.map(lambda v: v[3])
        extra.append(daily[["ticker", "date", "close", "volume", "underlying", "strike", "expiration", "type"]])
        receipts.append({"path": str(path.relative_to(output)), "sha256": sha(path), "rows": len(daily), "observed_contracts": len(observed)})
        print(json.dumps({"option_context_day": day, "contracts": len(observed), "surface_rows": len(daily)}), flush=True)
    for frame in [old, *extra]:
        frame.attrs = {}
    bars = pd.concat([old, *extra], ignore_index=True)
    daily = pd.read_parquet(output / "daily.all.parquet")
    surface = build_surface(bars, daily, raw_spot=raw, root_aliases=config.TICKER_ALIASES)
    surface.to_parquet(output / "surface.parquet", index=False)
    close = daily.pivot(index="date", columns="underlying", values="close").sort_index()
    ret = close.pct_change(fill_method="pad")
    beta = ret.rolling(60).cov(ret["SPY"]).div(ret["SPY"].rolling(60).var(), axis=0).stack().rename("beta_60d").reset_index()
    ctx = surface[["underlying", "date", "rvol_21", "atm_iv_near"]].copy()
    spy = surface[surface.underlying == "SPY"].set_index("date").atm_iv_near
    ctx["market_iv"] = ctx.date.map(spy)
    ctx["rv_iv_spread"] = ctx.rvol_21 - ctx.atm_iv_near
    ctx = ctx.drop(columns=["rvol_21", "atm_iv_near"]).merge(beta, on=["date", "underlying"], how="left")
    ctx.to_parquet(output / "context.parquet", index=False)
    return receipts


def prepare(args):
    load_dotenv(args.env)
    release = verify_release(args.release, args.anchor)
    spec = read(args.release / "baseline_spec.json")
    symbols = sorted(spec["symbols"])
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output / "manifest.json").exists():
        raise ValueError("completed forward data is immutable; use a new output directory")
    calendar_doc = read(args.source / "exchange_calendar.json")
    calendar = SessionCalendar(calendar_doc)
    if not calendar.bounds(args.through):
        raise ValueError("through must be a completed exchange session")
    if calendar.bounds(args.through)[1].tz_localize("UTC") > utcnow():
        raise ValueError("cannot refresh a future session")
    save(args.output / "calendar.json", calendar_doc)
    stock_manifest = args.output / "stock-progress.json"
    if stock_manifest.exists():
        stocks = read(stock_manifest)
    else:
        inventory, revised = stock_history(args.source, args.output, symbols, calendar, args.through)
        stocks = {"inventory": inventory, "revised": revised}
        save(stock_manifest, stocks)
    receipts = surface_context(args.source, args.output, symbols, calendar, args.through)
    files = {str(path.relative_to(args.output)): sha(path) for path in args.output.glob("*.parquet")}
    files["calendar.json"] = sha(args.output / "calendar.json")
    result = {"schema": "v6-forward-data-v1", "through": args.through, "completed_at": utcnow().isoformat(),
        "release_sha256": args.anchor, "model_sha256": release["model_sha256"],
        "symbols": stocks["inventory"], "technical_restatement_symbols": stocks["revised"],
        "files": files, "new_option_daily": receipts,
        "sources": {name: sha(args.source / name) for name in ["underlying_15m.parquet", "underlying_15m_raw.parquet", "underlying_daily.parquet", "underlying_daily_raw.parquet", "surface_daily.parquet", "universe.parquet", "option_derivation_manifest.json"]}}
    save(args.output / "manifest.json", result)
    print(json.dumps({"complete": True, "through": args.through, "symbols": len(symbols), "manifest_sha256": sha(args.output / "manifest.json")}), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--release", type=Path, required=True)
    ap.add_argument("--anchor", required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--through", required=True)
    ap.add_argument("--env", type=Path, default=Path(".env"))
    prepare(ap.parse_args())
