"""Complete causal daily context using the exact sealed V7 catalog admissions.

This orchestrator adds immutable context alongside the catalog. Numerical
contracts remain in causal_daily; historical catalog receipts are never edited.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from nn_meta.session_calendar import SessionCalendar
from nn_meta.v7.causal_daily import FEATURES, context, missingness, returns, timeline
from nn_meta.v7.ordinary_actions import price_action
from nn_meta.v7.provenance import runtime_manifest
from nn_meta.v7.storage import identity, receipt, sha, transaction, verify

ROOT = Path(__file__).resolve().parents[1]
START, END = '2022-03-15', '2026-09-14'
RESERVE = 100 * 1024**3


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


class Bindings:
    def __init__(self):
        self.inputs = {}
        self.stats = {}

    def add(self, path, expected=None):
        path = Path(path).resolve()
        stat = path.stat()
        signature = (stat.st_size, stat.st_mtime_ns)
        name = str(path)
        if name in self.inputs:
            if self.stats[name] != signature:
                raise ValueError(f'Input changed during build: {name}')
            digest = self.inputs[name]
        else:
            digest = sha(path)
            self.inputs[name], self.stats[name] = digest, signature
        if expected is not None and digest != expected:
            raise ValueError(f'Input hash differs: {name}')
        return digest

    def store(self, path):
        path = Path(path).resolve()
        document = verify(path)
        self.add(path / 'complete.json')
        for name, digest in document['files'].items():
            self.add(path / name, digest)
        return document

    def guard(self):
        for name in self.inputs:
            self.add(name)


def read_catalog(root, gate_path, bindings):
    gate = json.loads(gate_path.read_text())
    if not gate.get('catalog_subgate_passed') or gate.get('store_count') != 1773:
        raise ValueError('Full catalog audit evidence required')
    bindings.add(gate_path)
    reports = {}
    for name, digest in gate['reports'].items():
        path = gate_path.parent / name
        bindings.add(path, digest)
        reports[name] = json.loads(path.read_text())
    deep = reports['v7-2-full-catalog-deep-audit-20260925.json']
    proof = reports['v7-2-historical-loader-equivalence-20260925.json']
    reuse = reports['v7-2-catalog-reuse-20260924.json']
    if (deep['audited_stores'] != 1773 or not deep['technical_store_gate_passed']
            or Path(reuse['output']).resolve() != root.resolve()
            or proof['proved'] != proof['target'] or proof['proved'] != 10):
        raise ValueError('Incomplete catalog historical proof')
    builder = ROOT / 'scripts/build_v7_proposals.py'
    bindings.add(builder, proof['current_loader_sha256'])
    allowed_ids = set(reuse['securities']) | set(proof['security_ids'])
    audited = {(r['security_id'], r['minutes']): r for r in deep['audited_receipts']}
    specs = {}
    checked_paths = {}
    runtime_id = identity(runtime_manifest())
    for sid in sorted({key[0] for key in audited}):
        parts = []
        for minutes in (5, 15, 30):
            base = root / sid / str(minutes)
            checked = audited[sid, minutes]
            bindings.add(base / 'features/summary/complete.json', checked['feature_receipt_sha256'])
            bindings.add(base / 'proposals/summary/complete.json', checked['proposal_receipt_sha256'])
            for kind in ('features', 'proposals'):
                bindings.store(base / kind / 'declaration')
            f = json.loads((base / 'features/declaration/declaration.json').read_text())
            p = json.loads((base / 'proposals/declaration/declaration.json').read_text())
            if identity(f['runtime']) != runtime_id:
                raise ValueError('Frozen catalog runtime changed')
            for name, digest in {**f['inputs'], **f['sources']}.items():
                if name not in checked_paths:
                    checked_paths[name] = bindings.add(name)
                actual = checked_paths[name]
                if actual != digest:
                    old_builder = (Path(name).resolve() == builder and sid in allowed_ids
                                   and digest == proof['old_loader_sha256'])
                    audit_only = (Path(name).resolve() == ROOT / 'nn_meta/v7/catalog_reuse.py'
                                  and digest == '73d241359cea764adcada0d01140f66f392daeb9f62e4551bd1e300e028775bf')
                    if not (old_builder or audit_only):
                        raise ValueError(f'Unproved catalog hash difference: {sid}: {name}')
            part = {k: f[k] for k in ('security_id', 'raw_identity', 'actions', 'action_coverage', 'calendar')}
            part['routing'] = p['symbols_by_date']
            if parts and part != parts[0]:
                raise ValueError(f'Catalog timeframes have different daily inputs: {sid}')
            parts.append(part)
        specs[sid] = parts[0]
    if len(specs) != 591:
        raise ValueError('Exact 591-security catalog required')
    return specs


def prepare_stock(history, routing, clock):
    """Mask explicitly excluded history; retain a row for every source session."""
    frame = history.sort_values('source_date').reset_index(drop=True).copy()
    if frame.source_date.tolist() != clock.source_date.tolist():
        raise ValueError('History must explicitly cover every source session')
    admitted = frame.source_date.isin(routing)
    expected = frame.source_date.map(routing)
    if not frame.loc[admitted, 'stock_ticker'].eq(expected[admitted]).all():
        raise ValueError('Daily history differs from frozen proposal routing')
    frame['history_admitted'] = admitted
    frame.loc[~admitted, 'raw_close'] = np.nan
    frame.loc[~admitted, 'observed_minutes'] = 0
    spans = frame.identity_span.astype(object).where(admitted, None)
    if spans[admitted].isna().any():
        raise ValueError('Admitted daily history lacks a reviewed continuity span')
    # Admission gaps start a new warmup segment even within one legal identity.
    run = (spans.ne(spans.shift()) | spans.isna()).cumsum()
    starts = frame.source_date.groupby(run).transform('first')
    frame['identity_span'] = [f'{span}|admitted-from-{day}' if pd.notna(span) else None
                              for span, day in zip(spans, starts)]
    frame['available_ns'] = clock.stock_available_ns.to_numpy()
    return frame


def align_surfaces(stock, surface, clock, sid):
    wanted = pd.MultiIndex.from_arrays([stock.source_date, stock.stock_ticker],
                                       names=['source_date', 'stock_ticker'])
    selected = surface.reindex(wanted).reset_index()
    admitted = stock.history_admitted.to_numpy()
    if selected.loc[admitted, 'capture_complete'].isna().any():
        raise ValueError(f'Admitted ticker/day lacks a surface receipt: {sid}')
    observed = admitted & stock.observed_minutes.gt(0).to_numpy()
    if (not np.array_equal(stock.loc[admitted, 'observed_minutes'].to_numpy(),
                           selected.loc[admitted, 'observed_minutes'].to_numpy())
            or not np.allclose(stock.loc[observed, 'raw_close'], selected.loc[observed, 'raw_close'],
                               rtol=0, atol=1e-9)
            or not selected.loc[admitted, 'available_ns'].eq(clock.loc[admitted, 'available_ns']).all()):
        raise ValueError(f'Surface spot or clocks differ from admitted history: {sid}')
    for name in ('atm_iv_near', 'atm_iv_far', 'pc_ratio'):
        selected.loc[~admitted, name] = np.nan
    selected.loc[~admitted, 'surface_status'] = 'outside_admitted_history'
    # Every day has a verified whole-market capture; excluded identities select
    # no literal-root surface. Preserve that distinction in surface_status.
    selected['capture_complete'] = True
    selected['security_id'] = sid
    selected['available_ns'] = clock.available_ns.to_numpy()
    return selected


def audit_values(frame, stock, surface, clock, market):
    if (frame.source_date.tolist() != clock.source_date.tolist()
            or frame.index.asi8.tolist() != clock.available_ns.tolist()
            or frame.index.has_duplicates or frame.index.tz is None
            or np.isinf(frame[list(FEATURES)].to_numpy()).any()):
        raise ValueError('Daily row coverage, availability or finite-value audit failed')
    valid = (stock.observed_minutes.gt(0) & stock.observed_minutes.shift(1, fill_value=0).gt(0)
             & stock.identity_span.notna() & stock.identity_span.eq(stock.identity_span.shift()))
    raw = stock.raw_close.to_numpy()
    expected = np.full(len(frame), np.nan)
    for i in range(1, len(frame)):
        if valid.iloc[i]:
            expected[i] = raw[i] / (raw[i-1] * frame.action_factor.iloc[i]) - 1
    np.testing.assert_allclose(frame.simple_return, expected, rtol=2e-12, atol=2e-14, equal_nan=True)
    logs = frame.log_return.to_numpy()
    for window in (5, 21):
        oracle = np.full(len(frame), np.nan)
        for i in range(window-1, len(frame)):
            values = logs[i-window+1:i+1]
            if np.isfinite(values).all():
                oracle[i] = np.std(values, ddof=1) * np.sqrt(252)
        np.testing.assert_allclose(frame[f'rvol_{window}'], oracle, rtol=1e-9, atol=1e-11, equal_nan=True)
    for name in ('atm_iv_near', 'atm_iv_far', 'pc_ratio'):
        values = surface[name].clip(upper=5) if name == 'pc_ratio' else surface[name]
        values = values.where(stock.identity_span.notna())
        np.testing.assert_allclose(frame[name], values, rtol=0, atol=0, equal_nan=True)
    reference = frame if market is None else market
    np.testing.assert_allclose(frame.market_iv, reference.atm_iv_near, rtol=0, atol=0, equal_nan=True)
    beta = np.full(len(frame), np.nan)
    x, y = frame.simple_return.to_numpy(), reference.simple_return.to_numpy()
    for i in range(59, len(frame)):
        a, b = x[i-59:i+1], y[i-59:i+1]
        if np.isfinite(a).all() and np.isfinite(b).all() and np.var(b, ddof=1) > 0:
            beta[i] = np.cov(a, b, ddof=1)[0, 1] / np.var(b, ddof=1)
    np.testing.assert_allclose(frame.beta_60d, beta, rtol=1e-7, atol=1e-9, equal_nan=True)


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from nn_meta.v7.sectors import SectorStore
    from scripts.build_v7_surfaces import availability_calendar
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('catalog', 'gate', 'history', 'actions', 'surfaces', 'calendar', 'sectors', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--limit', type=int, help='Bounded pilot; never writes a full-stage pass')
    args = parser.parse_args()
    args.output = args.output.resolve()
    if not args.output.is_relative_to(ROOT / 'nn_meta'):
        raise ValueError('Repository artifact disk required')
    if shutil.disk_usage(ROOT).free < RESERVE + 2 * 1024**3:
        raise ValueError('Insufficient reserve plus two-GiB context budget')
    bindings = Bindings()
    print(json.dumps({'stage': 'catalog_bindings'}), flush=True)
    specs = read_catalog(args.catalog, args.gate, bindings)
    bindings.store(args.history)
    bindings.store(args.actions)
    bindings.store(args.calendar)
    sectors = SectorStore(args.sectors)
    bindings.store(args.sectors)
    for path, digest in sectors.report['sources'].items():
        bindings.add(path, digest)
    if set(sectors.report['security_ids']) != set(specs):
        raise ValueError('Dated sector census differs from catalog')
    history = pd.read_parquet(args.history / 'history.parquet')
    if set(history.security_id) != set(specs):
        raise ValueError('History census differs from catalog')
    market_ids = [sid for sid, spec in specs.items() if set(spec['routing'].values()) == {'SPY'}]
    if len(market_ids) != 1:
        raise ValueError('One exact SPY market identity required')
    market_id = market_ids[0]
    calendar = availability_calendar(ROOT / 'nn_meta/data_v7/start-20220315/calendar.json', args.calendar)
    for spec in specs.values():
        original = SessionCalendar(spec['calendar'])
        if any(calendar.sessions.get(day) != hours for day, hours in original.sessions.items()):
            raise ValueError('Daily calendar differs from catalog clock')
    clock = timeline(calendar, START, END)
    event_map = {row['action']['event_id']: row for row in json.loads((args.actions / 'actions.json').read_text())}
    bindings.store(args.surfaces / 'summary')
    surface_binding = json.loads((args.surfaces / 'summary/binding.json').read_text())
    for name, digest in {**surface_binding['inputs'], **surface_binding['sources']}.items():
        bindings.add(name, digest)
    frames = []
    surface_receipts = {str(Path(p).resolve()): h for p, h in surface_binding['days'].items()}
    for day in clock.source_date:
        path = args.surfaces / 'days' / day
        expected = surface_receipts.get(str((path / 'complete.json').resolve()))
        if expected is None:
            raise ValueError('Surface day absent from full summary')
        bindings.add(path / 'complete.json', expected)
        bindings.store(path)
        frames.append(pd.read_parquet(path / 'surfaces.parquet'))
    surface = pd.concat(frames, ignore_index=True).set_index(['source_date', 'stock_ticker']).sort_index()
    if not surface.index.is_unique:
        raise ValueError('Duplicate literal surface identity/day')
    source_paths = [Path(__file__).resolve(), ROOT / 'nn_meta/v7/causal_daily.py',
                    ROOT / 'nn_meta/v7/causal_prices.py', ROOT / 'nn_meta/v7/sectors.py',
                    ROOT / 'nn_meta/session_calendar.py', ROOT / 'nn_meta/v7/ordinary_actions.py',
                    ROOT / 'nn_meta/v7/storage.py']
    code = {str(path): bindings.add(path) for path in source_paths}
    ids = [market_id] + sorted(set(specs) - {market_id})
    if args.limit is not None:
        if args.limit < 1: raise ValueError('Positive pilot size required')
        ids = ids[:args.limit]
    args.output.mkdir(parents=True, exist_ok=True)
    common = args.output / 'common'
    common_doc = dict(schema='v7-full-daily-common-v1', catalog=str(args.catalog.resolve()),
                      security_ids=ids, start=START, end=END, market_security_id=market_id,
                      inputs=dict(bindings.inputs), sources=code, runtime=runtime_manifest(), research_ready=False)
    common_id = identity(common_doc)
    if not common.exists():
        with transaction(common) as temp:
            save(temp / 'declaration.json', common_doc)
            save(temp / 'inputs.json', bindings.inputs)
            surface.reset_index().to_parquet(temp / 'surfaces.parquet', index=False)
            receipt(temp, {'identity': common_id, 'research_ready': False})
    else:
        verify(common, expected_identity=common_id)
    print(json.dumps({'stage': 'daily_context', 'securities': len(ids), 'sessions_each': len(clock)}), flush=True)
    common_inputs = {str(p.resolve()): sha(p) for p in (common / 'complete.json', common / 'inputs.json',
                    common / 'surfaces.parquet', args.history / 'history.parquet', args.actions / 'actions.json',
                    args.calendar / 'calendar.json', args.sectors / 'sessions.parquet', args.sectors / 'complete.json')}
    common_inputs.update(code)
    reports, market = [], None
    for ordinal, sid in enumerate(ids):
        spec = specs[sid]
        stock = prepare_stock(history[history.security_id.eq(sid)], spec['routing'], clock)
        surf = align_surfaces(stock, surface, clock, sid)
        actions = []
        for declared in spec['actions']:
            event = event_map.get(declared['event_id'])
            if event is None or event['security_id'] != sid:
                raise ValueError('Frozen action absent from current reviewed inventory')
            action = price_action(event)
            actual = asdict(action)
            for k in ('effective_at', 'available_at'): actual[k] = actual[k].isoformat()
            if actual != declared:
                raise ValueError('Daily actions differ from frozen feature actions')
            day = action.effective_at.tz_convert('America/New_York').date().isoformat()
            if day in spec['routing']: actions.append(action)
        inputs = dict(common_inputs)
        for minutes in (5, 15, 30):
            for kind in ('features', 'proposals'):
                p = args.catalog / sid / str(minutes) / kind / 'declaration/declaration.json'
                inputs[str(p.resolve())] = sha(p)
        if market is not None:
            p = args.output / market_id / 'complete.json'
            inputs[str(p)] = sha(p)
        declaration = dict(schema='v7-full-causal-daily-v1', security_id=sid, start=START, end=END,
            common_identity=common_id, action_coverage=spec['action_coverage'], inputs=inputs,
            return_actions=[action.event_id for action in actions], research_ready=False)
        target = args.output / sid
        fingerprint = identity(declaration)
        if target.exists():
            verify(target, expected_identity=fingerprint)
            daily = pd.read_parquet(target / 'daily.parquet')
            report = json.loads((target / 'report.json').read_text())
        else:
            daily_returns = returns(stock, actions, calendar, security_id=sid, start=START, end=END,
                                    action_evidence_identity=identity(spec['action_coverage']))
            daily = context(daily_returns, surf, market=market, is_market=sid == market_id)
            audit_values(daily, stock, surf, clock, market)
            daily['history_admitted'] = stock.history_admitted.to_numpy()
            daily['stock_ticker'] = stock.stock_ticker.to_numpy()
            daily['surface_status'] = surf.surface_status.to_numpy()
            sector = sectors.for_security(sid)
            dates = daily.index.tz_convert('America/New_York').strftime('%Y-%m-%d')
            sector_rows = [sector.records.get(day) for day in dates]
            daily['sector'] = [r['sector'] if r else None for r in sector_rows]
            daily['sector_status'] = [r['reason'] if r else 'outside_eligible_sessions' for r in sector_rows]
            daily['sector_reference_date'] = [r['reference_date'] if r else None for r in sector_rows]
            report = dict(security_id=sid, sessions=len(daily), admitted_sessions=int(stock.history_admitted.sum()),
                return_status=daily.return_status.value_counts().to_dict(), features=missingness(daily),
                surface_status=daily.surface_status.value_counts().to_dict(), sector_status=daily.sector_status.value_counts().to_dict(),
                independent_return_volatility_beta_audit=True, exact_next_open_availability=True,
                no_forward_fill=True, daily_contract=daily.attrs['daily_contract'], research_ready=False)
            if shutil.disk_usage(args.output).free < RESERVE:
                raise ValueError('Disk reserve reached')
            with transaction(target) as temp:
                daily.to_parquet(temp / 'daily.parquet')
                save(temp / 'declaration.json', declaration)
                save(temp / 'inputs.json', inputs)
                save(temp / 'report.json', report)
                receipt(temp, {'identity': fingerprint, 'research_ready': False})
        if sid == market_id: market = daily
        reports.append({'security_id': sid, 'receipt_sha256': sha(target / 'complete.json'), **report})
        if ordinal % 25 == 0 or ordinal == len(ids)-1:
            print(json.dumps({'completed': ordinal+1, 'target': len(ids)}), flush=True)
    bindings.guard()
    for name, digest in code.items():
        if sha(name) != digest: raise ValueError('Daily numerical source changed')
    report = dict(schema='v7-full-daily-context-summary-v1', securities=len(ids), sessions=sum(r['sessions'] for r in reports),
                  expected_securities=591, sessions_per_security=len(clock), full_scope_passed=len(ids)==591,
                  market_security_id=market_id, calendar_start=START, calendar_end=END,
                  common_receipt_sha256=sha(common / 'complete.json'), security_reports=reports,
                  disk_free_bytes=shutil.disk_usage(args.output).free, research_ready=False)
    summary = args.output / 'summary'
    if not summary.exists():
        with transaction(summary) as temp:
            save(temp / 'report.json', report)
            receipt(temp, {'identity': identity(report), 'research_ready': False})
    else:
        verify(summary)
    print(json.dumps({k: report[k] for k in ('securities', 'sessions', 'full_scope_passed', 'disk_free_bytes')}), flush=True)


if __name__ == '__main__':
    main()
