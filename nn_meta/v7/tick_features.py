"""All-timeframe option tick features from complete causal quote/trade windows."""
from nn_meta.option_tick_dataset import (
    _verify_policy, _eligible_trade, compute_feature_row,
)
from options.tick_features import verified_window_features, window_features


def features(archive, references, *, symbol, contract, decision_ns, minutes,
             session_open_ns, policy):
    if type(minutes) is not int or minutes not in (1, 5, 15, 30):
        raise ValueError('Explicit supported feature timeframe required')
    _verify_policy(policy)
    import pandas as pd
    day = pd.Timestamp(decision_ns, unit='ns', tz='UTC').tz_convert('America/New_York').date().isoformat()
    metadata = references.standard(contract, day)
    if metadata['underlying'] != symbol.replace('.', ''):
        raise ValueError('Tick feature underlying identity mismatch')
    start = decision_ns - minutes * 60_000_000_000
    if start < session_open_ns:
        raise ValueError('Feature window crosses the declared session opening')
    # Seed from the latest possible fresh quote; the book resets at the
    # declared option session opening. There is no future-quote backfill.
    prefix = max(session_open_ns, start - policy['max_quote_age_ns'])
    quotes, qm = archive.window(contract, 'quotes', prefix, decision_ns)
    trades, tm = archive.window(contract, 'trades', prefix, decision_ns)
    kwargs = {'start_ns': start, 'end_ns': decision_ns,
              'max_quote_age_ns': policy['max_quote_age_ns'],
              'allowed_trade_conditions': policy['allowed_trade_conditions'],
              'allow_unconditioned_trades': False}
    reported = verified_window_features(quotes, trades, quote_manifest=qm,
                                       trade_manifest=tm, contract=contract, **kwargs)
    allowed = set(policy['allowed_trade_conditions'])
    eligible = window_features(quotes, [r for r in trades if _eligible_trade(r, allowed)],
                               complete=True, coverage_start_ns=prefix, coverage_end_ns=decision_ns, **kwargs)
    row = compute_feature_row(reported, {'symbol': symbol, 'contract': contract,
        'window_start_ns': start, 'window_end_ns': decision_ns, 'decision_close_ns': decision_ns}, eligible=eligible)
    evidence = {'quote_captures': qm['derived_from_captures'], 'trade_captures': tm['derived_from_captures'],
                'metadata_receipt_sha256': metadata['metadata_receipt_sha256'], 'seed_start_ns': prefix,
                'policy': policy, 'signal_minutes': minutes}
    return row, evidence
