# v3/derive_contracts.py — universe listing + daily option bars from day-frames.
"""One scan over the flat-file 15m day-frames produces the two remaining
inputs the pipeline needs, entirely offline (no REST):

1. universe.parquet — every contract seen, with life_start (first date it
   traded) and OCC-parsed underlying/expiration/strike/type. Used by the
   provider for chain selection, so it must be COMPLETE (all strikes), not
   filtered.
2. bars_daily/bars_part_*.parquet — per-contract daily OHLCV (15m aggregated),
   filtered to tradeable premium/DTE. Feeds build_surface (ATM IV, pc_ratio).

Run: python -m v3.derive_contracts --cache INPUT_CACHE --output-cache FRESH_OUTPUT

The input cache must contain explicitly sourced underlying_daily_raw.parquet.
Output is a NEW directory, never mixed with previous adjusted-filtered parts.
Promote the completed artifacts only after coverage validation; this command
does not replace the input universe, daily parts, or flat files.
"""
import argparse
import re
import hashlib
import json
from pathlib import Path

import pandas as pd

from nn_meta import config as nn_config
from nn_meta.price_basis import require_raw_panel, raw_daily_for_roots, RAW_SPOT_SCHEMA_VERSION

_OCC = re.compile(r"^([A-Z]+)(\d{6})([CP])(\d{8})$")
_CHUNK = 40                                    # day-frames per bars_part file
_1D = {"Open": "first", "High": "max", "Low": "min", "Close": "last",
       "Volume": "sum"}

# ~5.2M contracts / 441 underlyings ≈ 12k rows per underlying: 20k-row groups
# keep a one-underlying predicate read to a handful of groups.
UNIVERSE_ROW_GROUP = 20_000


def _sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_occ(occ: str):
    m = _OCC.match(occ)
    if not m:
        return None
    root, ymd, cp, strike = m.groups()
    exp = pd.Timestamp(f"20{ymd[:2]}-{ymd[2:4]}-{ymd[4:6]}")
    return root, exp, ("call" if cp == "C" else "put"), int(strike) / 1000.0


def daily_from_frame(frame, day, spot, *, min_premium=.05, max_dte=70, moneyness_band=.15):
    """Daily surface rows use raw spot; return every observed OCC separately."""
    import numpy as np
    d = frame.groupby("occ").agg(_1D)
    d["date"] = day
    d = d.reset_index()
    observed = d["occ"].tolist()
    parsed = d["occ"].map(parse_occ)
    ok = parsed.notna()
    d, parsed = d[ok].copy(), parsed[ok]
    d["underlying"] = parsed.map(lambda p: p[0])
    exp = parsed.map(lambda p: p[1])
    d["strike"] = parsed.map(lambda p: p[3])
    dte = (exp - day).dt.days
    eligible = (d["Close"] >= min_premium) & dte.between(1, max_dte)
    sp = pd.to_numeric(d["underlying"].map(lambda u: spot.get((u, day))), errors="coerce")
    missing = eligible & sp.isna()
    if missing.any():
        symbols = sorted(d.loc[missing, "underlying"].unique())
        raise ValueError(f"raw daily spot missing on {day.date()} for eligible option roots {symbols[:12]}; refusing silent contract drop")
    mny = np.log(d["strike"].astype(float) / sp)
    d = d[eligible & (mny.abs() <= moneyness_band)].copy()
    d["ticker"] = "O:" + d["occ"]
    return (d.rename(columns=str.lower)[["ticker", "date", "open", "high", "low", "close", "volume"]], observed)


def derive_cache(cache: Path, output: Path, *, min_premium=.05, max_dte=70, moneyness_band=.15,
                 root_aliases: dict | None = None):
    """Derive a complete isolated candidate; no mutation of the input cache."""
    import math
    cache, output = Path(cache), Path(output)
    if output.exists():
        raise ValueError("output-cache must be a fresh directory; stale daily parts cannot be mixed")
    if not math.isfinite(min_premium) or min_premium < 0 or not math.isfinite(moneyness_band) or moneyness_band < 0:
        raise ValueError("premium and moneyness filters must be finite and nonnegative")
    if isinstance(max_dte, bool) or not isinstance(max_dte, int) or max_dte < 1:
        raise ValueError("max_dte must be a positive integer")
    raw_path = cache / "underlying_daily_raw.parquet"
    und = require_raw_panel(pd.read_parquet(raw_path, columns=["underlying", "date", "close"]), "1d")
    und = raw_daily_for_roots(und, root_aliases)
    spot = {(r.underlying, r.date): r.close for r in und.itertuples()}
    frames = sorted((cache / "flatfiles_15m").glob("*.parquet"))
    if not frames:
        raise ValueError("no flat-file15m day frames to derive")
    inventory = [{"name": p.name, "bytes": p.stat().st_size, "mtime_ns": p.stat().st_mtime_ns} for p in frames]
    inventory_sha = hashlib.sha256(json.dumps(inventory, sort_keys=True).encode()).hexdigest()
    source = {"raw_daily_sha256": _sha256_file(raw_path),
              "flatfile_inventory_sha256": inventory_sha, "flatfile_count": len(frames),
              "input_cache": str(cache.resolve()),
              "explicit_root_aliases": dict(root_aliases or {}),
              "resolved_root_aliases": und.attrs["resolved_root_aliases"],
              "inventory_semantics": "name/size/mtime identity; full input hashes are held by the campaign manifest"}
    output.mkdir(parents=True)
    bars_dir = output / "bars_daily"
    bars_dir.mkdir()
    manifest = {"schema_version": RAW_SPOT_SCHEMA_VERSION, "status": "building",
                "derivation_provenance": source, "input_inventory": inventory,
                "daily_filters": {"minimum_premium": min_premium, "max_dte": max_dte,
                                  "absolute_log_moneyness": moneyness_band, "spot_basis": "raw"},
                "universe_scope": "all_observed_contracts; no strike filter"}
    manifest_path = output / "derivation_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"scanning {len(frames)} day-frames into fresh {output}…", flush=True)
    first_seen = {}
    daily_buf, part, daily_count = [], 0, 0
    for i, fp in enumerate(frames, 1):
        day = pd.Timestamp(fp.stem)
        df = pd.read_parquet(fp)
        daily, observed = daily_from_frame(df, day, spot, min_premium=min_premium,
                                          max_dte=max_dte, moneyness_band=moneyness_band)
        for occ in observed:
            if occ not in first_seen:
                first_seen[occ] = day
        daily_buf.append(daily)
        daily_count += len(daily)
        if i % _CHUNK == 0 or i == len(frames):
            panel = pd.concat(daily_buf, ignore_index=True)
            panel.attrs.update(daily_price_basis_schema=RAW_SPOT_SCHEMA_VERSION,
                               moneyness_filter_spot_basis="raw", source="flatfiles_15m",
                               derivation_provenance=source, daily_filters=manifest["daily_filters"])
            panel.to_parquet(bars_dir / f"bars_part_{part:04d}.parquet", index=False)
            daily_buf, part = [], part + 1
            print(f"  [{i}/{len(frames)}] {day.date()} · {len(first_seen):,} contracts seen", flush=True)
    rows = []
    for occ, life in first_seen.items():
        parsed = parse_occ(occ)
        if parsed:
            root, exp, typ, strike = parsed
            rows.append({"ticker": "O:" + occ, "underlying": root, "expiration": exp,
                         "life_start": life, "strike": strike, "type": typ})
    uni = pd.DataFrame(rows, columns=["ticker", "underlying", "expiration", "life_start", "strike", "type"])
    uni = uni.sort_values("underlying", kind="stable").reset_index(drop=True)
    uni.attrs.update(universe_price_basis_schema=RAW_SPOT_SCHEMA_VERSION,
                     contract_scope="all_observed_contracts", source="flatfiles_15m",
                     strike_filter="none", derivation_provenance=source)
    for filename in ("universe.parquet", "contracts.parquet"):
        uni.to_parquet(output / filename, index=False, row_group_size=UNIVERSE_ROW_GROUP)
    manifest.update(status="complete", universe_contracts=len(uni), daily_rows=daily_count, daily_parts=part,
                    output_sha256={p.relative_to(output).as_posix(): _sha256_file(p)
                                   for p in sorted(output.rglob("*.parquet"))})
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"complete: {len(uni):,} all-observed contracts; {daily_count:,} raw-filtered daily rows / {part} parts", flush=True)
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default="nn_meta/data_cache_v3")
    ap.add_argument("--output-cache", required=True, help="fresh isolated output directory; never overwrite/mix existing parts")
    ap.add_argument("--use-config-root-aliases", action="store_true",
                    help="explicitly use frozen nn_meta.config.TICKER_ALIASES for missing exact-root raw dates; record every mapping")
    ap.add_argument("--min-premium", type=float, default=0.05)
    ap.add_argument("--max-dte", type=int, default=70)
    ap.add_argument("--moneyness-band", type=float, default=0.15,
                    help="|log(strike/spot)| kept in the daily bars (surface "
                         "input); the universe listing stays complete")
    args = ap.parse_args()
    derive_cache(Path(args.cache), Path(args.output_cache), min_premium=args.min_premium,
                 max_dte=args.max_dte, moneyness_band=args.moneyness_band,
                 root_aliases=nn_config.TICKER_ALIASES if args.use_config_root_aliases else None)


if __name__ == "__main__":
    main()
