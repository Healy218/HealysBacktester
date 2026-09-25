"""Reopen and audit the full daily context before admitting the V7-3 stage."""
from pathlib import Path
import argparse
import json
import shutil

import numpy as np
import pandas as pd

from nn_meta.v7.causal_daily import FEATURES, context, returns, timeline, missingness
from nn_meta.v7.sectors import SectorStore
from nn_meta.v7.storage import sha, verify, identity
from scripts.build_v7_full_daily_context import (
    Bindings, read_catalog, prepare_stock, align_surfaces, audit_values, save, START, END, RESERVE,
)
from scripts.build_v7_surfaces import availability_calendar
from nn_meta.v7.ordinary_actions import price_action


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('daily', 'catalog', 'gate', 'history', 'actions', 'calendar', 'sectors', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    binding = Bindings()
    specs = read_catalog(args.catalog, args.gate, binding)
    binding.store(args.daily / 'common')
    binding.store(args.daily / 'summary')
    summary = json.loads((args.daily / 'summary/report.json').read_text())
    common = json.loads((args.daily / 'common/declaration.json').read_text())
    if (set(common['security_ids']) != set(specs) or summary['securities'] != 591
            or summary['sessions'] != 667239 or not summary['full_scope_passed']):
        raise ValueError('Incomplete full-scope daily census')
    if sha(args.daily / 'common/complete.json') != summary['common_receipt_sha256']:
        raise ValueError('Common receipt changed')
    for name, digest in common['inputs'].items():
        binding.add(name, digest)
    history = pd.read_parquet(args.history / 'history.parquet')
    surfaces = pd.read_parquet(args.daily / 'common/surfaces.parquet').set_index(['source_date', 'stock_ticker'])
    calendar = availability_calendar(Path('nn_meta/data_v7/start-20220315/calendar.json'), args.calendar)
    clock = timeline(calendar, START, END)
    sectors = SectorStore(args.sectors)
    events = {r['action']['event_id']: r for r in json.loads((args.actions / 'actions.json').read_text())}
    market_id = summary['market_security_id']
    market = pd.read_parquet(args.daily / market_id / 'daily.parquet')
    reports = {r['security_id']: r for r in summary['security_reports']}
    if set(reports) != set(specs):
        raise ValueError('Summary security reports differ')
    missing = {name: 0 for name in FEATURES}
    admitted = 0
    prefixes = 0
    action_count = 0
    sector_counts = {}
    for ordinal, (sid, spec) in enumerate(sorted(specs.items())):
        root = args.daily / sid
        declaration = json.loads((root / 'declaration.json').read_text())
        verify(root, expected_identity=identity(declaration))
        if sha(root / 'complete.json') != reports[sid]['receipt_sha256']:
            raise ValueError('Daily shard receipt changed')
        for name, digest in json.loads((root / 'inputs.json').read_text()).items():
            binding.add(name, digest)
        frame = pd.read_parquet(root / 'daily.parquet')
        if frame.attrs.get('daily_contract') != 'v7-causal-daily-v1' or not frame.security_id.eq(sid).all():
            raise ValueError('Wrong daily contract or security')
        original = history[history.security_id.eq(sid)].sort_values('source_date').reset_index(drop=True)
        # Raw completed-session facts are available at close; the resulting
        # daily model context is deliberately delayed until the next open.
        if (not original.available_ns.eq(clock.stock_available_ns).all()
                or not original.session_open_ns.eq(clock.session_open_ns).all()):
            raise ValueError('Identity-history session clocks changed')
        stock = prepare_stock(original, spec['routing'], clock)
        surface = align_surfaces(stock, surfaces, clock, sid)
        audit_values(frame, stock, surface, clock, None if sid == market_id else market)
        if not np.array_equal(frame.history_admitted, stock.history_admitted):
            raise ValueError('Daily admission mask differs')
        pd.testing.assert_series_equal(frame.raw_close.reset_index(drop=True), stock.raw_close,
                                       check_names=False, check_dtype=False)
        if missingness(frame) != reports[sid]['features']:
            raise ValueError('Persisted missingness differs from report')
        # Additional independent arithmetic for features not covered by the
        # build-time NumPy return/volatility/beta oracle.
        np.testing.assert_allclose(frame.term_slope, frame.atm_iv_far-frame.atm_iv_near, equal_nan=True)
        np.testing.assert_allclose(frame.rv_iv_spread, frame.rvol_21-frame.atm_iv_near, equal_nan=True)
        change = np.full(len(frame), np.nan)
        spans = frame.identity_span.to_numpy()
        for i in range(5, len(frame)):
            if pd.notna(spans[i]) and all(v == spans[i] for v in spans[i-5:i+1]):
                change[i] = frame.atm_iv_near.iloc[i]-frame.atm_iv_near.iloc[i-5]
        np.testing.assert_allclose(frame.iv_chg_5, change, equal_nan=True)
        selected = [price_action(events[e]) for e in declaration['return_actions']]
        expected_factors = {a.effective_at.tz_convert('America/New_York').date().isoformat(): a.price_factor for a in selected}
        np.testing.assert_allclose(frame.action_factor, [expected_factors.get(d, 1.) for d in frame.source_date], rtol=0, atol=0)
        action_count += len(selected)
        # Prefix replay starts from raw facts and excludes all later source
        # sessions/surfaces. Every security is checked at two cutoffs.
        for length in (90, 565):
            cutoff = stock.source_date.iloc[length-1]
            ret = returns(stock.iloc[:length], selected, calendar, security_id=sid,
                          start=START, end=cutoff, action_evidence_identity=identity(spec['action_coverage']))
            partial = context(ret, surface.iloc[:length], is_market=sid == market_id,
                              market=None if sid == market_id else market.iloc[:length])
            np.testing.assert_allclose(partial[list(FEATURES)], frame.iloc[:length][list(FEATURES)],
                                       rtol=1e-10, atol=1e-12, equal_nan=True)
            prefixes += 1
        dated = sectors.for_security(sid)
        for timestamp, row in frame.iterrows():
            day = timestamp.tz_convert('America/New_York').date().isoformat()
            record = dated.records.get(day)
            expected = record['sector'] if record else None
            actual = row.sector if pd.notna(row.sector) else None
            if expected != actual or row.sector_status != (record['reason'] if record else 'outside_eligible_sessions'):
                raise ValueError('Dated sector join differs')
            if row.source_date >= day:
                raise ValueError('Daily context visible before completed source date')
        for name in FEATURES: missing[name] += int(frame[name].isna().sum())
        admitted += int(frame.history_admitted.sum())
        for name, count in frame.sector_status.value_counts().items():
            sector_counts[name] = sector_counts.get(name, 0) + int(count)
        if ordinal % 50 == 0:
            print(json.dumps({'audited': ordinal+1, 'target': 591}), flush=True)
    binding.guard()
    disk = shutil.disk_usage(args.daily).free
    if disk < RESERVE: raise ValueError('Disk reserve failed')
    report = dict(schema='v7-full-daily-audit-v1', full_scope_passed=True,
                  securities=len(specs), sessions=summary['sessions'], admitted_sessions=admitted,
                  features=list(FEATURES), missing_counts=missing, sector_status=sector_counts,
                  action_events=action_count, prefix_replays=prefixes,
                  source_start=START, source_end=END, exact_next_open_availability=True,
                  independent_arithmetic_passed=True, receipt_input_source_hashes_passed=True,
                  daily_summary_receipt_sha256=sha(args.daily / 'summary/complete.json'),
                  catalog_gate_sha256=sha(args.gate), daily_root=str(args.daily.resolve()),
                  audit_source_sha256=sha(__file__), disk_free_bytes=disk,
                  research_ready=False, option_tick_row_integration='awaits V7-3 captures')
    save(args.output, report)
    print(json.dumps({k: report[k] for k in ('full_scope_passed', 'securities', 'sessions', 'prefix_replays')}), flush=True)


if __name__ == '__main__':
    main()
