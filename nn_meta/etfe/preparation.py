"""Immutable ETFE scope/catalog preparation, without loading any V7 artifacts."""
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from nn_meta.multitimeframe_catalog import canonical, parameter_variants

ROOT = Path(__file__).resolve().parents[2]
SCOPE = ROOT / 'docs/specs/ETFE_SCOPE_20261003.json'
SYMBOLS = ('SPY', 'QQQ', 'VOO')
TIMEFRAMES = (1, 5, 15)
FAMILIES = frozenset(('bbands', 'bbw_squeeze', 'elliott', 'keltner', 'ma',
    'macd', 'rsi', 'squeeze', 'stoch', 'supertrend', 'tv_amd', 'tv_fibonacci',
    'tv_gaussian', 'tv_msb', 'tv_rating', 'tv_rsi_probability', 'tv_setup',
    'tv_sr', 'tv_uptrick', 'volume'))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save_new(path, value):
    """Exclusive creation: an interrupted run remains evidence, never a new run."""
    with Path(path).open('x') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def validate_scope(scope):
    if scope.get('schema') != 'etfe-research-scope-v1' or scope.get('expert') != 'etfe':
        raise ValueError('Expected independent ETFE scope')
    if scope.get('symbols') != list(SYMBOLS) or scope.get('signal_minutes') != list(TIMEFRAMES):
        raise ValueError('ETFE requires exactly SPY/QQQ/VOO and 1/5/15-minute signals')
    history = scope['history']
    if (history.get('start_policy') != 'earliest_alpaca_options_history'
            or history.get('verified_start_utc') is not None
            or history.get('end_date_inclusive') != '2026-10-02'):
        raise ValueError('Scope must preserve the requested, not yet verified history start and fixed end')
    if (scope.get('options_provider') != 'alpaca' or scope.get('options_feed') != 'opra'
            or scope.get('allow_massive_quotes') is not False
            or scope.get('reuse_model_weights') is not False
            or scope.get('reuse_v7_checkpoints') is not False):
        raise ValueError('ETFE requires independent artifacts and Alpaca OPRA only')
    if scope.get('ready_for_build') is not False or scope.get('training_authorized') is not False:
        raise ValueError('Preparation cannot authorize dataset building or training')
    # Hash-bind all settings in the plan; risk values are checked against the
    # accepted amendment by preparation, not silently inherited from live V6.


def end_exclusive_utc(scope):
    final = date.fromisoformat(scope['history']['end_date_inclusive'])
    midnight = datetime.combine(final + timedelta(days=1), time(), ZoneInfo('America/New_York'))
    return midnight.astimezone(timezone.utc).isoformat()


def build_catalog(scope, legacy_grids, source_grids):
    validate_scope(scope)
    variants = list(parameter_variants(legacy_grids, source_grids))
    families = dict(sorted(Counter(s for s, _ in variants).items()))
    if set(families) != FAMILIES or len(variants) != 2817:
        raise ValueError('Registered grid changed; reconcile ETFE scope before preparing')
    records = []
    for minutes in TIMEFRAMES:
        for strategy, params in variants:
            identity = dict(expert='etfe', strategy=strategy, signal_minutes=minutes, params=params)
            records.append({**identity, 'variant_id': digest(identity)})
    if len({r['variant_id'] for r in records}) != len(records):
        raise ValueError('Duplicate strategy variants')
    payload = dict(schema='etfe-parameter-catalog-v1', expert='etfe',
        symbols=list(SYMBOLS), signal_minutes=list(TIMEFRAMES),
        families=families, parameter_variants_per_timeframe=len(variants),
        variants_per_symbol=len(records), ticker_variant_combinations=len(SYMBOLS)*len(records),
        records=records, ready_for_build=False,
        count_excludes=['direction', 'DTE target', 'contract', 'signal event', 'model trial'])
    return {**payload, 'catalog_sha256': digest(payload)}


def prepare(output, scope_path=SCOPE):
    scope = json.loads(Path(scope_path).read_text())
    validate_scope(scope)
    # Only enumerate grids. Do not call old planners, adapters or live launchers.
    from nn_meta import config
    from nn_meta.tradingview_proposals import SWEEP_GRIDS as source_grids
    if config.POOL != 'etfe':
        raise ValueError('Preparation requires NN_META_POOL=etfe before importing registry config')
    legacy = {k: v for k, v in config.SWEEP_GRIDS.items() if k not in source_grids}
    catalog = build_catalog(scope, legacy, source_grids)
    risk_path = ROOT / 'docs/specs/V7_OPTION_RISK_20260916.json'
    risk = json.loads(risk_path.read_text())
    if scope['quote_policy'] != risk['quote_policy']:
        raise ValueError('ETFE quote policy differs from the accepted inherited policy')
    for key in ('premium_stop_fraction', 'expiry_exit_before_close_minutes', 'price_basis'):
        if scope['risk_policy'][key] != risk['option_risk_policy'][key]:
            raise ValueError('ETFE risk policy differs from the accepted inherited policy')
    sources = ['nn_meta/etfe/preparation.py', 'nn_meta/etfe/alpaca_probe.py',
        'scripts/prepare_etfe.py', 'scripts/probe_etfe_alpaca.py',
        'nn_meta/multitimeframe_catalog.py', 'nn_meta/config.py',
        'nn_meta/tradingview_proposals.py', 'v3/tv_setup_scanner.py',
        'docs/specs/V7_OPTION_RISK_20260916.json']
    output = Path(output).resolve()
    base = ROOT / 'nn_meta/validation'
    if output.parent != base or not output.name.startswith('etfe-'):
        raise ValueError('ETFE setup must use a fresh direct nn_meta/validation/etfe-* directory')
    plan = dict(schema='etfe-setup-plan-v1', expert='etfe', scope=scope,
        scope_sha256=file_sha(scope_path), catalog_sha256=catalog['catalog_sha256'],
        runtime=dict(pool='etfe', state_root=str(output), provider='alpaca', feed='opra'),
        history_end_exclusive_utc=end_exclusive_utc(scope),
        endpoint_conversion='Alpaca inclusive-end requests use one nanosecond before this day boundary; session hours require calendar evidence.',
        source_bindings={name:file_sha(ROOT/name) for name in sources},
        readiness=dict(ready_for_build=False, ready_for_training=False,
            blockers=['exact_alpaca_history_boundary', 'historical_quote_windows',
                'dated_contract_reference_coverage', 'minute_and_feature_coverage',
                'strategy_timeframe_parity', 'execution_and_label_coverage',
                'etfe_schema_folds_and_trials', 'measured_resources_and_recovery']))
    plan['plan_sha256'] = digest(plan)
    output.mkdir(exist_ok=False)
    save_new(output/'scope.json', scope)
    save_new(output/'catalog.json', catalog)
    save_new(output/'plan.json', plan)
    result = dict(schema='etfe-preparation-receipt-v1', status='prepared_not_admitted',
        expert='etfe', plan_sha256=plan['plan_sha256'],
        files={name:file_sha(output/name) for name in ('scope.json','catalog.json','plan.json')},
        families=len(catalog['families']), variants_per_symbol=catalog['variants_per_symbol'],
        ticker_variant_combinations=catalog['ticker_variant_combinations'], ready_for_build=False)
    save_new(output/'PREPARED.json', result)
    return result
