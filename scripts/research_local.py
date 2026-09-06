"""Preview/run explicitly selected local stages in a named v5/v6 campaign.

No cloud transport, old-output reuse or notifications. A preview imports only
configuration and reads selection metadata; it creates no files. --run checks
the pinned raw-data window in both directions before creating derived outputs.
The cross-archive check cannot establish sessions missing from both archives.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
import fcntl
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

STAGES = ("freeze", "build", "assemble", "evaluate", "finalize")
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
SYMBOL = re.compile(r"[A-Z0-9][A-Z0-9._-]{0,24}\Z")
SOURCE_TREES = ("nn_meta", "nn_options_signal", "options", "signals", "indicators",
                "v3", "utils", "config", "data", "portfolio", "scanner", "fa")
RUNTIME_PACKAGES = ("numpy", "pandas", "pyarrow", "numba", "vectorbt", "scipy",
                    "scikit-learn", "lightgbm", "tensorflow")


class CampaignError(ValueError):
    pass


def name(value: str) -> str:
    if not NAME.fullmatch(value):
        raise argparse.ArgumentTypeError("campaign must be a simple 1–64 character name")
    return value


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected a positive integer") from exc
    if number < 1:
        raise argparse.ArgumentTypeError("expected a positive integer")
    return number


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", required=True, type=name)
    parser.add_argument("--pool", required=True, choices=("v5", "v6"))
    parser.add_argument("--stage", required=True, action="append", choices=STAGES,
                        help="repeat to select stages; no other stages run implicitly")
    parser.add_argument("--symbols", help="comma-separated pilot/subset; default frozen PIT union")
    parser.add_argument("--workers", type=positive_int,
                        default=positive_int(os.environ.get("RESEARCH_WORKERS_DEFAULT", "1")))
    parser.add_argument("--folds", type=positive_int, default=3)
    parser.add_argument("--run", action="store_true", help="execute selected stages (default: preview)")
    args = parser.parse_args(argv)
    if len(set(args.stage)) != len(args.stage):
        parser.error("each stage may be selected only once")
    if args.stage != sorted(args.stage, key=STAGES.index):
        parser.error("select stages in freeze/build/assemble/evaluate/finalize order")
    return args


def load_config(args):
    os.environ["NN_META_POOL"] = args.pool
    os.environ["NN_META_CAMPAIGN"] = args.campaign
    from nn_meta import config
    if config.POOL != args.pool or config.CAMPAIGN != args.campaign:
        raise CampaignError("configuration already loaded for another campaign; use a new process")
    return config


def selected_symbols(value, defaults) -> list[str]:
    symbols = list(defaults) if value is None else [s.strip().upper() for s in value.split(",")]
    if not symbols or any(not SYMBOL.fullmatch(s) for s in symbols):
        raise CampaignError("symbols must be nonempty simple ticker names without paths")
    if len(symbols) != len(set(symbols)):
        raise CampaignError("duplicate symbols are not allowed")
    return sorted(symbols)


def safe_outputs(config) -> Path:
    """Refuse symlink redirection as well as lexical traversal before writes."""
    if not NAME.fullmatch(config.CAMPAIGN) or config.POOL not in ("v5", "v6"):
        raise CampaignError("a named v5/v6 campaign is required")
    base = config.ROOT / "campaigns" / config.CAMPAIGN / config.POOL
    for kind, path in (("artifacts", config.ARTIFACTS), ("runs", config.RUNS_DIR),
                       ("reports", config.REPORTS_DIR), ("model_final", config.MODEL_FINAL_DIR)):
        if path != base / kind:
            raise CampaignError(f"{kind} output escapes the named campaign")
    for path in (base, *[base / k for k in ("artifacts", "runs", "reports", "model_final")]):
        for ancestor in (path, *path.parents):
            if ancestor == config.ROOT:
                break
            if ancestor.is_symlink():
                raise CampaignError(f"campaign output is a symlink: {ancestor}")
    if config.V4_MODEL_FINAL_DIR != base / "model_final":
        raise CampaignError("final bundle path escapes the named campaign")
    # Existing nested output symlinks could redirect subprocess writes too.
    if base.exists() and any(p.is_symlink() for p in base.rglob("*")):
        raise CampaignError("campaign contains a symlink; use plain output directories")
    return base


def coverage_gaps(cache: Path, start: str, end: str) -> dict:
    from nn_meta.cache_preflight import flatfile_days, trading_days
    options = {d for d in flatfile_days(cache) if start <= d <= end}
    underlying = {d for d in trading_days(cache) if start <= d <= end}
    return {"window": [start, end], "option_days": len(options),
            "underlying_days": len(underlying),
            "missing_options": sorted(underlying - options),
            "missing_underlying": sorted(options - underlying)}


def require_coverage(config) -> dict:
    report = coverage_gaps(config.DATA_CACHE, config.WINDOW_START, config.WINDOW_END)
    print("Pinned-window two-way coverage: " + json.dumps(report, sort_keys=True), flush=True)
    if (not report["option_days"] or not report["underlying_days"]
            or report["missing_options"] or report["missing_underlying"]):
        raise CampaignError("raw archive coverage gaps block campaign execution")
    if getattr(config, "DATA_CANDIDATE", ""):
        manifest_path = config.DATA_CACHE / "repair_manifest.json"
        if not manifest_path.exists():
            raise CampaignError("data candidate lacks a repair manifest")
        manifest = json.loads(manifest_path.read_text())
        if not manifest.get("coverage_result", {}).get("passed") or manifest.get("context_status") != "refreshed_raw_spot":
            raise CampaignError("data candidate coverage or daily/surface context repair is incomplete")
        if not manifest.get("options_daily_raw_filter_verified"):
            raise CampaignError("data candidate option daily bars have not been rederived with raw stock spot")
        if manifest.get("unresolved_model_gates"):
            raise CampaignError("data candidate has unresolved model price-basis gates")
    return report


def _omit_input(path: Path) -> bool:
    """Exclude transient writes and credentials, never market-data extensions."""
    names = [part.lower() for part in path.parts]
    if any(part == ".env" or part.startswith(".env.") for part in names):
        return True
    filename = names[-1]
    return (filename.endswith((".tmp", ".lock", ".part", ".partial", "~", ".pyc"))
            or any(word in filename for word in ("credential", "secret", "token"))
            or path.suffix.lower() in (".pem", ".key", ".p12", ".pfx"))


def _sha256(path: Path) -> str:
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
            after.st_size, after.st_mtime_ns, after.st_ino):
        raise CampaignError(f"input changed while fingerprinting: {path.name}")
    return digest.hexdigest()


def input_fingerprint(config) -> dict:
    """Bind raw bytes, PIT/universe, research source and runtime versions.

    The entire selected DATA_CACHE is bound, excluding temporary/lock and
    credential files. Any added/removed/repaired cache input requires a new
    campaign, even if an individual symbol appears unaffected. Python research
    packages, pinned Pine sources/manifests, launcher/requirements files and
    frozen universe inputs are also bound. Tests/docs and campaign outputs are
    excluded. This runs only for --run, never for fast command previews.
    """
    cache = config.DATA_CACHE
    if not cache.is_dir():
        raise CampaignError("raw cache is missing; cannot bind campaign inputs")
    repo = config.ROOT.parent
    files: dict[str, Path] = {}
    if getattr(config, "V6_EXPANDED", False):
        from nn_meta.v6_expansion import from_environment
        expanded = from_environment()
        expanded.assert_unchanged()
        for path in expanded.input_files():
            files["expanded/" + path] = Path(path)

    def include(label, path):
        if _omit_input(path):
            return
        if path.is_symlink():
            raise CampaignError(f"fingerprinted input is a symlink: {label}")
        if path.is_file():
            files[label] = path

    for path in cache.rglob("*"):
        include("cache/" + str(path.relative_to(cache)), path)
    for package in SOURCE_TREES:
        for path in (repo / package).rglob("*.py"):
            relative = path.relative_to(repo)
            # Runtime packages may also contain generated/cached output trees.
            if any(part.startswith(("artifacts", "data_cache", "model_final", "reports"))
                   or part in ("campaigns", "runs", "__pycache__") for part in relative.parts):
                continue
            include("source/" + str(relative), path)
    for path in (repo / "indicators" / "tradingview_sources").rglob("*"):
        if path.suffix in (".pine", ".json"):
            include("source/" + str(path.relative_to(repo)), path)
    for relative in ("scripts/research_local.py", "scripts/run_research_local.sh",
                     "scripts/lib/autosize.sh", "requirements.txt", "requirements.lock.txt",
                     "pyproject.toml", "uv.lock"):
        include("source/" + relative, repo / relative)
    universe = repo / "v3" / "artifacts"
    for path in list(universe.glob("universe*.json")) + list((universe / "universe_pit").rglob("*")):
        include("universe/" + str(path.relative_to(universe)), path)
    records = [{"path": label, "sha256": _sha256(path)} for label, path in sorted(files.items())]
    versions = {}
    for package in RUNTIME_PACKAGES:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = "not-installed"
    payload = {"version": 1, "files": records,
               "runtime": {"python": sys.version, "packages": versions}}
    payload["sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return payload


def validate_candidate_seal(config, fingerprint: dict) -> None:
    """Check repair claims against the same bytes bound to this campaign."""
    if not getattr(config, "DATA_CANDIDATE", ""):
        return
    manifest = json.loads((config.DATA_CACHE / "repair_manifest.json").read_text())
    expected = manifest.get("sealed_cache_sha256")
    if not isinstance(expected, dict) or not expected:
        raise CampaignError("data candidate is not sealed; finish data validation before launch")
    current = {row["path"].removeprefix("cache/"): row["sha256"] for row in fingerprint["files"]
               if row["path"].startswith("cache/") and row["path"] != "cache/repair_manifest.json"}
    if current != expected:
        raise CampaignError("sealed data candidate bytes or file list changed; repair and seal a new candidate")


def command_plan(config, symbols: list[str], stages: list[str], folds: int) -> list[dict]:
    python = str(config.ROOT.parent / "venv" / "bin" / "python")
    artifacts, reports = config.ARTIFACTS, config.REPORTS_DIR
    marks = artifacts / "meta_dataset.marks.parquet"
    shards = [artifacts / "freeze_shards" / f"{symbol}.json" for symbol in symbols]
    plan = []
    for stage in stages:
        if stage == "freeze":
            commands = [[python, "-m", "nn_meta.freeze_baseline", "--symbols", symbol,
                         "--out", str(path)] for symbol, path in zip(symbols, shards)]
            merge = [python, "-m", "nn_meta.freeze_baseline", "--merge",
                     ",".join(map(str, shards)), "--out", str(artifacts / "baseline_spec.json")]
        elif stage == "build":
            commands = [[python, "-m", "nn_meta.build_meta_dataset", "--symbols", symbol,
                         "--marks", "--partial-dir", str(artifacts / "partials")]
                        for symbol in symbols]
            merge = None
        elif stage == "assemble":
            commands = [[python, "-m", "nn_meta.build_meta_dataset", "--assemble", "--membership"]]
            merge = None
        elif stage == "evaluate":
            commands = [[python, "-m", "nn_meta.v4_evaluate", "--dataset",
                         str(artifacts / "meta_dataset.parquet"), "--marks", str(marks),
                         "--folds", str(folds), "--output", str(reports / "evaluate")]]
            merge = None
        else:
            commands = [[python, "-m", "nn_meta.v4_finalize", "--marks", str(marks)]]
            merge = None
        plan.append({"stage": stage, "commands": commands, "merge": merge})
    return plan


def validate_shards(paths, symbols, contract):
    for path, symbol in zip(paths, symbols, strict=True):
        data = json.loads(path.read_text())
        if data.get("feature_contract_version") != contract:
            raise CampaignError(f"stale freeze shard: {path}")
        frozen, skipped = set(data.get("symbols", {})), set(data.get("skipped", []))
        if frozen & skipped or frozen | skipped != {symbol}:
            raise CampaignError(f"freeze shard does not cover exactly {symbol}: {path}")
    # merge_specs independently validates current config hashes and matching
    # windows/grids/execution. Its input is this exact list, never a glob.


def run_command(command, *, environment, cwd, log):
    with log.open("a") as output:
        output.write("\n" + shlex.join(command) + "\n")
        output.flush()
        result = subprocess.run(command, env=environment, cwd=cwd,
                                stdout=output, stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise CampaignError(f"command failed ({result.returncode}); inspect {log}")


def parallel_commands(commands, *, workers, environment, cwd, log_dir, labels):
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(run_command, command, environment=environment,
                                   cwd=cwd, log=log_dir / f"{label}.log")
                   for command, label in zip(commands, labels, strict=True)]
        try:
            for future in as_completed(futures):
                future.result()
        except BaseException:
            for future in futures:
                future.cancel()
            raise


@contextmanager
def campaign_lock(path):
    with path.open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise CampaignError("another launcher owns this campaign/pool") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def run_plan(config, symbols, plan, workers, report):
    from nn_meta.feature_contract import CONTRACT_VERSION
    if getattr(config, "V6_EXPANDED", False):
        from nn_meta.v6_expansion import from_environment
        from_environment().bind_tick_stores(symbols)
    base = safe_outputs(config)
    config.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    with campaign_lock(config.RUNS_DIR / ".launcher.lock"):
        fingerprint = input_fingerprint(config)
        validate_candidate_seal(config, fingerprint)
        scope = {"campaign": config.CAMPAIGN, "pool": config.POOL, "symbols": symbols,
                 "data_candidate": getattr(config, "DATA_CANDIDATE", ""),
                 "window": [config.WINDOW_START, config.WINDOW_END],
                 "strategies": config.PROPOSAL_STRATEGIES,
                 "feature_contract_version": CONTRACT_VERSION,
                 "inputs": fingerprint}
        scope_path = base / "campaign_scope.json"
        if scope_path.exists() and json.loads(scope_path.read_text()) != scope:
            raise CampaignError("campaign scope changed (selection/source/raw inputs); choose a new campaign name")
        if not scope_path.exists():
            with scope_path.open("x") as output:
                json.dump(scope, output, indent=2, sort_keys=True)
                output.write("\n")
        for folder in (config.ARTIFACTS, config.REPORTS_DIR, config.MODEL_FINAL_DIR):
            folder.mkdir(parents=True, exist_ok=True)
        (config.RUNS_DIR / "coverage.json").write_text(json.dumps(report, indent=2) + "\n")
        environment = dict(os.environ, NN_META_POOL=config.POOL, NN_META_CAMPAIGN=config.CAMPAIGN)
        environment["NN_META_DATA_CANDIDATE"] = getattr(config, "DATA_CANDIDATE", "")
        for stage_number, stage in enumerate(plan):
            # Earlier stages or another process may have altered shared raw
            # caches/code. Recheck before any following stage can consume them.
            if stage_number and input_fingerprint(config) != scope["inputs"]:
                raise CampaignError("campaign inputs changed between stages; choose a new campaign name")
            label = stage["stage"]
            log_dir = config.RUNS_DIR / "logs" / label
            log_dir.mkdir(parents=True, exist_ok=True)
            print(f"Running {label}: {len(stage['commands'])} command(s)", flush=True)
            if label in ("freeze", "build"):
                if label == "freeze":
                    (config.ARTIFACTS / "freeze_shards").mkdir(exist_ok=True)
                parallel_commands(stage["commands"], workers=workers, environment=environment,
                                  cwd=config.ROOT.parent, log_dir=log_dir, labels=symbols)
                if label == "freeze":
                    if input_fingerprint(config) != scope["inputs"]:
                        raise CampaignError("campaign inputs changed during freeze; refusing merge")
                    paths = [config.ARTIFACTS / "freeze_shards" / f"{s}.json" for s in symbols]
                    validate_shards(paths, symbols, CONTRACT_VERSION)
                    run_command(stage["merge"], environment=environment, cwd=config.ROOT.parent,
                                log=log_dir / "merge.log")
            else:
                run_command(stage["commands"][0], environment=environment, cwd=config.ROOT.parent,
                            log=log_dir / "stage.log")
            if input_fingerprint(config) != scope["inputs"]:
                raise CampaignError(f"campaign inputs changed during {label}; outputs are ineligible for reuse")
            print(f"Completed {label}", flush=True)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        config = load_config(args)
        base = safe_outputs(config)
        symbols = selected_symbols(args.symbols, config.UNDERLYINGS)
        plan = command_plan(config, symbols, args.stage, args.folds)
        print(f"{'RUN' if args.run else 'PREVIEW'} {args.campaign}/{args.pool}: "
              f"{len(symbols)} symbols; {args.workers} workers; outputs {base}")
        print(f"Required preflight: two-way option/underlying day coverage "
              f"{config.WINDOW_START} .. {config.WINDOW_END}; "
              "does not detect sessions absent from both archives.")
        candidate = getattr(config, "DATA_CANDIDATE", "")
        selector = [f"NN_META_DATA_CANDIDATE={candidate}"] if candidate else []
        if candidate:
            print(f"Data candidate: {config.DATA_CACHE}; calendar, raw-price and derived-context gates required.")
        for stage in plan:
            for command in stage["commands"] + ([stage["merge"]] if stage["merge"] else []):
                print(shlex.join(["env", f"NN_META_POOL={args.pool}",
                                  f"NN_META_CAMPAIGN={args.campaign}", *selector, *command]))
        if not args.run:
            print("Preview only. --run executes exactly the selected stages after preflight.")
            return 0
        report = require_coverage(config)
        run_plan(config, symbols, plan, args.workers, report)
        return 0
    except (CampaignError, OSError, ValueError) as exc:
        print(f"RESEARCH-FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
