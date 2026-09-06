"""Plan expanded v6 option decisions locally, before option outcomes exist.

Preview validates the sealed context and shows scope. --run performs the exact
underlying TRAIN sweep and writes a candidate request inventory. It never runs
option execution, chooses a winning DTE, reads option bars, or downloads ticks.
Later option-outcome gates may reject a candidate family; this is not a freeze.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
from importlib.metadata import version
import sys

import numpy as np
import pandas as pd

from nn_meta import baseline, config
from nn_meta.decision_contracts import DecisionContractSelector, POLICY_VERSION
from nn_meta.price_basis import load_raw_close_15m, require_raw_close
from nn_meta.v6_expansion import bars_sha256, from_environment, sha256
from nn_meta.weekly_expiry import dte_grid_for, weekly_expiry_symbols
from options.execution import to_naive_utc
from options.data.provider import parse_occ_symbol

SCHEMA = "v6-pre-outcome-option-requests-v1"
ROOT = Path(__file__).resolve().parents[1]


def _bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _hash(value):
    return hashlib.sha256(_bytes(value)).hexdigest()


def _json_value(value):
    """Retain sweep evidence; unavailable diagnostic metrics become JSON null."""
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(v) for v in value]
    if isinstance(value, np.generic):
        return _json_value(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _require_expanded():
    from nn_meta.tradingview_proposals import STRATEGIES
    expected = [*config.PROPOSAL_STRATEGIES_V5, "keltner", "bbw_squeeze", *STRATEGIES]
    if (not config.V6_EXPANDED or config.POOL != "v6" or not config.CAMPAIGN
            or list(config.PROPOSAL_STRATEGIES) != expected or len(expected) != 20):
        raise ValueError("request planning requires the complete named expanded v6 pool of 20 families")


class ChainOnlyProvider:
    """Expose only local prior-date chain methods to the shared selector."""
    def __init__(self, provider):
        if provider.point_in_time_chain is not True:
            raise ValueError("planner requires a point-in-time chain provider")
        self.point_in_time_chain = True
        self._provider = provider

    def get_chain(self, *args, **kwargs):
        return self._provider.get_chain(*args, **kwargs)

    def historical_chain_member(self, *args, **kwargs):
        return self._provider.historical_chain_member(*args, **kwargs)


def plan_symbol(symbol, bars, raw_close, selector, *, weekly_symbols):
    """Exact pre-option freeze eligibility, then the builder's capped timeline.

    TRAIN sweeps and TRAIN/full-window underlying simulations use baseline's
    existing functions. Exceptions propagate: broken context is never a skip.
    No final winning-DTE or option-fill eligibility is inferred.
    """
    _require_expanded()
    symbol = symbol.upper()
    if bars.empty:
        raise ValueError(f"{symbol}: missing underlying history")
    require_raw_close(raw_close)
    index = pd.DatetimeIndex([to_naive_utc(t) for t in bars.index])
    if raw_close.attrs["symbol"] != symbol or not raw_close.index.equals(index):
        raise ValueError("raw spot symbol/timestamps must exactly match technical history")
    # Loading through ExpandedInputs is mandatory even for legacy families.
    if "v6_tradingview_context" not in bars.attrs:
        raise ValueError("sealed TradingView context must be attached before planning")
    dtes = dte_grid_for(symbol, {"weekly_symbols": weekly_symbols})
    requests, families = [], {}
    train_limit = pd.Timestamp(config.TRAIN_END) + pd.Timedelta(days=1)
    cap = config.MAX_SIGNALS_PER_NAME
    for strategy in config.PROPOSAL_STRATEGIES:
        print(json.dumps({"event": "planning_family", "symbol": symbol, "strategy": strategy}), flush=True)
        sweep = baseline.sweep_train_params(symbol, bars, strategy,
                                           config.TRAIN_START, config.TRAIN_END)
        if sweep is None:
            families[strategy] = {"status": "no_freezable_params", "requests": 0}
            continue
        params = sweep["params"]
        train_all = baseline.propose_trades(bars, strategy, params, config.TRAIN_START, config.TRAIN_END)
        train = train_all[:cap]
        record = {"sweep": _json_value(sweep), "params_sha256": _hash(_json_value(params)),
                  "train_events_before_cap": len(train_all), "train_events": len(train),
                  "train_truncated": len(train_all) > cap}
        if not train:
            families[strategy] = {**record, "status": "no_train_events", "requests": 0}
            continue
        if not all(to_naive_utc(trade[1]) <= train_limit for trade in train):
            raise ValueError(f"{symbol}/{strategy}: TRAIN trade leaked beyond TRAIN_END")
        all_trades = baseline.propose_trades(bars, strategy, params, config.WINDOW_START, config.WINDOW_END)
        trades = all_trades[:cap]
        record.update(full_events_before_cap=len(all_trades), full_events=len(trades),
                      full_truncated=len(all_trades) > cap,
                      status="candidate_requests" if trades else "no_full_window_events")
        start = len(requests)
        # Match builder ordering: DTE then capped trade index, preserving duplicates.
        for dte in dtes:
            for trade_index, trade in enumerate(trades):
                stamp, _, direction = trade
                stamp = to_naive_utc(stamp)
                if (isinstance(direction, (bool, np.bool_)) or direction not in (0, 1)
                        or stamp not in raw_close.index):
                    raise ValueError("proposal direction/raw-spot timestamp is invalid")
                request = selector.request(symbol, signal_bar_open=stamp.tz_localize("UTC"),
                    right="P" if direction == 1 else "C", raw_spot=float(raw_close.loc[stamp]),
                    target_dte=int(dte), consumer_ids=[f"{symbol}:{strategy}:{trade_index}:{dte}"])
                requests.append(request)
        record["requests"] = len(requests) - start
        families[strategy] = record
    raw_hash = hashlib.sha256(raw_close.index.as_unit("ns").asi8.astype("<i8").tobytes()
                             + raw_close.to_numpy(dtype="<f8").tobytes()).hexdigest()
    return requests, {"symbol": symbol, "dte_grid": dtes, "families": families,
                      "bars_sha256": bars_sha256(bars), "raw_close_sha256": raw_hash,
                      "raw_close_provenance": _json_value(raw_close.attrs),
                      "requests": len(requests), "requests_sha256": _hash(requests)}


def _source_hashes():
    packages = ("nn_meta", "nn_options_signal", "signals", "indicators", "v3",
                "options", "portfolio", "utils", "scanner")
    paths = {p for package in packages for p in (ROOT / package).rglob("*.py")}
    paths.update(p for p in (ROOT / "indicators" / "tradingview_sources").rglob("*")
                 if p.is_file() and p.suffix in (".pine", ".json"))
    paths.add(Path(__file__))
    paths.add(ROOT / "requirements.txt")
    return {str(p.absolute()): sha256(p) for p in sorted(paths)}


def _root_aliases(requests):
    """Retain renamed roots already verified by the shared prior-date selector."""
    roots = {}
    for request in requests:
        if request["status"] != "selected":
            continue
        root = parse_occ_symbol(request["contract"])[0]
        symbol = request["symbol"]
        if root in roots and roots[root] != symbol:
            raise ValueError("selected OCC root has ambiguous underlying aliases")
        roots[root] = symbol
    return {root: symbol for root, symbol in sorted(roots.items()) if root != symbol}


def _config_record():
    names = ("POOL", "CAMPAIGN", "V6_EXPANDED", "V6_PARITY_POLICY", "V6_INPUTS_SHA256", "INTERVAL",
             "TRAIN_START", "TRAIN_END", "WINDOW_START", "WINDOW_END", "PROPOSAL_STRATEGIES",
             "SWEEP_GRIDS", "SIM_CONFIG", "EXEC_CONFIG", "MIN_TRAIN_TRADES",
             "TRADES_PER_DAY_CEILING", "MAX_SIGNALS_PER_NAME", "DTE_GRID", "DTE_GRID_WEEKLY",
             "WEEKLY_DTE_ENABLED", "ENABLE_SHORTING")
    return _json_value({name: getattr(config, name) for name in names})


def _fresh(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)) or path.exists():
        raise ValueError("output must be a fresh local directory without symlinked parents")
    path = path.resolve()
    if path.is_relative_to(config.DATA_CACHE.resolve()):
        raise ValueError("planner output cannot be inside the immutable input cache")
    return path


def plan(args):
    _require_expanded()
    output = _fresh(args.output)
    expanded = from_environment()  # verifies actual parity/context, not pending tick stores
    symbols = args.symbols.split(",") if args.symbols else list(config.UNDERLYINGS)
    symbols = [symbol.strip().upper() for symbol in symbols]
    if (not symbols or any(not symbol for symbol in symbols) or len(symbols) != len(set(symbols))
            or set(symbols) - set(config.UNDERLYINGS)
            or set(symbols) - set(expanded.document["symbols"])):
        raise ValueError("symbols must be distinct configured names with sealed expanded contexts")
    weekly_input_hash = sha256(config.UNIVERSE_PARQUET)
    weekly = weekly_expiry_symbols(config.UNIVERSE_PARQUET) if config.WEEKLY_DTE_ENABLED else []
    if sha256(config.UNIVERSE_PARQUET) != weekly_input_hash:
        raise ValueError("weekly-expiry catalogue changed during classification")
    result = {"schema": SCHEMA, "symbols": symbols, "strategies": list(config.PROPOSAL_STRATEGIES),
              "weekly_symbols": weekly, "dte_grids": {s: dte_grid_for(s, {"weekly_symbols": weekly}) for s in symbols},
              "output": str(output), "written": False, "inventory_computed": False,
              "option_outcomes_read": False, "downloads_started": False, "freeze_completed": False,
              "model_admission": False, "tick_stores_bound": False}
    if not args.run:
        for symbol in symbols:
            baseline.load_underlying_15m(symbol)  # validates exact sealed history/context
        expanded.assert_unchanged()
        return result
    config_record = _config_record()
    sources = _source_hashes()
    inputs = expanded.input_files()
    inputs.update({str(Path(p).absolute()): sha256(p) for p in
                   (config.UNDERLYING_15M_PARQUET, config.UNDERLYING_15M_RAW_PARQUET, config.UNIVERSE_PARQUET)})
    if inputs[str(Path(config.UNIVERSE_PARQUET).absolute())] != weekly_input_hash:
        raise ValueError("weekly-expiry catalogue changed before request planning")
    from nn_meta.providers import get_provider
    selector = DecisionContractSelector(ChainOnlyProvider(get_provider(allow_fetch=False)),
                                       moneyness=config.EXEC_CONFIG.get("MONEYNESS", 0.0))
    all_requests, selections = [], {}
    for symbol in symbols:
        bars = baseline.load_underlying_15m(symbol)
        raw_close = load_raw_close_15m(symbol, index=bars.index)
        requests, selections[symbol] = plan_symbol(symbol, bars, raw_close, selector, weekly_symbols=weekly)
        all_requests.extend(requests)
        expanded.assert_unchanged()
    if (_source_hashes() != sources or _config_record() != config_record
            or any(sha256(path) != digest for path, digest in inputs.items())):
        raise ValueError("source/config/selection inputs changed during request planning")
    aliases = _root_aliases(all_requests)
    provenance = {**result, "created_at": datetime.now(timezone.utc).isoformat(),
                  "inventory_computed": True, "selection_policy": POLICY_VERSION,
                  "scope": "All pre-option-outcome candidate families; later option execution/DTE gates may reject them.",
                  "train_window": [config.TRAIN_START, config.TRAIN_END],
                  "full_window": [config.WINDOW_START, config.WINDOW_END],
                  "config": config_record, "config_sha256": _hash(config_record),
                  "baseline_config_hash": baseline._config_hash(), "source_sha256": sources,
                  "input_files_sha256": inputs, "symbol_selections": selections,
                  "runtime": {"python": platform.python_version(), **{name: version(name) for name in
                              ("numpy", "pandas", "vectorbt", "numba", "scipy")}},
                  "request_count": len(all_requests), "requests_sha256": _hash(all_requests),
                  "root_aliases": aliases,
                  "selected_count": sum(r["status"] == "selected" for r in all_requests)}
    _bytes(provenance)  # validate JSON before creating output
    output.mkdir(parents=True, exist_ok=False)
    files = (("requests.json", all_requests), ("selection_provenance.json", provenance),
             ("root_aliases.json", aliases))
    for name, value in files:
        (output / name).write_bytes(_bytes(value) + b"\n")
    manifest = {"schema": SCHEMA, "complete": True, "created_at": provenance["created_at"],
                "files_sha256": {name: sha256(output / name) for name, _ in files},
                "request_count": len(all_requests), "model_admission": False,
                "freeze_completed": False, "option_outcomes_read": False, "downloads_started": False}
    (output / "manifest.json").write_bytes(_bytes(manifest) + b"\n")
    return {**result, "written": True, "inventory_computed": True,
            "request_count": len(all_requests), "selected_count": provenance["selected_count"],
            "manifest_sha256": sha256(output / "manifest.json")}


def parser():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--symbols", help="comma-separated configured scope; default full configured universe")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--run", action="store_true", help="perform underlying sweeps and write local request inventory")
    return ap


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = plan(args)
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(f"V6-OPTION-REQUEST-PLAN-FAILED: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
