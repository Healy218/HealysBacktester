"""Replay the reviewed AAPL dividend against independently calculated daily returns.

This is real-data causal-return evidence, not full-universe action admission or
market-context validation. No vendor-adjusted series is used as an oracle.
"""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import numpy as np
    import pandas as pd
    from nn_meta.session_calendar import SessionCalendar
    from nn_meta.v7.causal_daily import returns
    from nn_meta.v7.causal_prices import CausalPriceHistory
    from nn_meta.v7.provenance import RunBinding
    from nn_meta.v7.storage import identity, receipt, sha, transaction, verify
    from scripts.pilot_v7_causal_features import action_input

    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'dividends', 'splits', 'alpaca', 'issuer', 'reference', 'stock-daily', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT / 'nn_meta'):
        raise ValueError('Repository artifact disk required')
    summary = args.stock_daily / 'summary'
    binding = json.loads((summary / 'binding.json').read_text())
    verify(summary, expected_identity=identity(binding))
    parents = {**binding['declaration']['inputs'], **binding['declaration']['sources']}
    if any(sha(path) != digest for path, digest in parents.items()):
        raise ValueError('Stock daily parent bindings differ')
    shard = args.stock_daily / 'shards/AAPL/2022'
    verify(shard)
    if binding['shards'].get(str(shard / 'complete.json')) != sha(shard / 'complete.json'):
        raise ValueError('AAPL shard is not bound to this active daily build')
    raw, action, calendar_doc, inputs, facts = action_input(**{name: getattr(args, name) for name in
        ('source', 'dividends', 'splits', 'alpaca', 'issuer', 'reference')})
    # Bind the payloads, not just their receipt files, across the calculation.
    for filename in list(inputs):
        path = Path(filename)
        if path.name == 'complete.json':
            document = verify(path.parent)
            inputs.update({str(path.parent / name): digest for name, digest in document['files'].items()})
    inputs.update(parents)
    for path in (summary / 'complete.json', summary / 'binding.json',
                 shard / 'complete.json', shard / 'daily.parquet'):
        inputs[str(path)] = sha(path)
    start, end = '2022-03-15', '2022-05-10'
    declaration = dict(schema='v7-causal-daily-actual-validation-v1', start=start, end=end,
        symbol='AAPL', action_facts=facts, research_ready=False,
        identity_scope='Reviewed AAPL pilot interval only; no extrapolation outside dates',
        limitations=['Single issuer/dividend; full action/identity inventory still required',
                     'Market, sector and full daily feature integration are separate'])
    if any(sha(path) != digest for path, digest in inputs.items()):
        raise ValueError('Reviewed daily evidence changed before calculation')
    run = RunBinding(ROOT, inputs=inputs, declaration=declaration)
    daily = pd.read_parquet(shard / 'daily.parquet')
    daily = daily[daily.source_date.between(start, end)].reset_index(drop=True)
    daily['identity_span'] = 'reviewed-aapl-pilot-20220315-20220510'
    calendar = SessionCalendar(calendar_doc)

    def calculate(frame, actions):
        return returns(frame, actions, calendar, security_id=facts['security_id'],
            start=start, end=frame.source_date.iloc[-1], action_evidence_identity=action.source_identity)

    result = calculate(daily, [action])
    # Scalar oracle: reconstruct the entire as-of chart at each daily close,
    # then compare the two independently selected observed closing minutes.
    raw = raw[(raw.index >= pd.Timestamp(start, tz='America/New_York')) &
              (raw.index < pd.Timestamp(end, tz='America/New_York') + pd.Timedelta(days=1))]
    history = CausalPriceHistory(raw, [action], security_id=facts['security_id'])
    comparisons, maximum_error = 0, 0.
    for i in range(1, len(daily)):
        view = history.view(pd.Timestamp(daily.available_ns.iloc[i], tz='UTC'))
        clocks = pd.to_datetime(daily.last_observed_ns.iloc[i-1:i+1].astype('int64'), utc=True)
        closes = view.loc[pd.DatetimeIndex(clocks), 'Close'].to_numpy()
        expected = closes[1] / closes[0] - 1
        error = abs(expected - result.simple_return.iloc[i])
        if not np.isfinite(error) or error > 2e-14:
            raise ValueError('Daily causal return differs from independent as-of chart')
        maximum_error = max(maximum_error, error)
        comparisons += 1
    for count in range(1, len(daily) + 1):
        prefix = calculate(daily.iloc[:count], [action])
        pd.testing.assert_frame_equal(result.iloc[:count], prefix)
    before = daily.source_date.lt('2022-05-06')
    plain = calculate(daily[before], [])
    pd.testing.assert_series_equal(plain.simple_return, result.loc[before, 'simple_return'])
    report = dict(sessions=len(daily), independent_return_comparisons=comparisons,
        maximum_absolute_return_error=maximum_error, prefix_checks=len(daily),
        first_rvol_5_source_date=result.loc[result.rvol_5.notna(), 'source_date'].iloc[0],
        first_rvol_21_source_date=result.loc[result.rvol_21.notna(), 'source_date'].iloc[0],
        action_facts=facts, research_ready=False)
    with transaction(args.output) as temporary:
        result.to_parquet(temporary / 'returns.parquet', index=False)
        manifest = run.finish()
        (temporary / 'binding.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (temporary / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        receipt(temporary, dict(identity=manifest['identity'], research_ready=False))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
