"""Reusable causal feature epochs and bit-packed full-catalog signal storage.

Features are computed once per action epoch. Proposal simulation reads bounded
variant columns across those epochs, preserving continuous stop state. Inputs
remain explicitly unadmitted until the full research gates validate them.
"""
from dataclasses import asdict
import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from nn_meta.multitimeframe_catalog import registered_catalog
from nn_meta.v7.storage import identity, receipt, sha, transaction, verify


def _json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def _frame_identity(frame):
    return identity(dict(columns=list(frame), dtypes=[str(d) for d in frame.dtypes],
        index_dtype=str(frame.index.dtype), values=__import__('hashlib').sha256(
            pd.util.hash_pandas_object(frame, index=True).to_numpy().tobytes()).hexdigest()))


def _disk(path, reserve_bytes, extra_bytes=0):
    if type(reserve_bytes) is not int or reserve_bytes < 0:
        raise ValueError('Nonnegative explicit disk reserve required')
    if shutil.disk_usage(path).free < reserve_bytes + extra_bytes:
        raise ValueError('Insufficient disk reserve for proposal build')


def build_features(path, chart, variants, *, inputs, reserve_bytes,
                   batch_columns=16, working_bytes=128*1024**2):
    """Checkpoint each epoch; reuse only exact input/code/catalog matches.

    The caller supplies retained parent file hashes, including any unresolved
    action/identity report. These bindings are not a completeness declaration.
    All configured variants are retained, including variants with zero signals.
    """
    from nn_meta.v7.signals import signal_batches
    from nn_meta.v7.rows import FEATURE_NAMES, TECHNICAL
    path = Path(path)
    variants = list(variants)
    catalog = [v for v in registered_catalog(['_store'])['records']
               if v['signal_minutes'] == chart.minutes]
    allowed = {v['variant_id']: v for v in catalog}
    if (not variants or len({v['variant_id'] for v in variants}) != len(variants)
            or any(allowed.get(v['variant_id']) != v for v in variants)
            or type(batch_columns) is not int or batch_columns < 1
            or type(working_bytes) is not int or working_bytes < 1
            or not inputs or any(sha(p) != h for p, h in inputs.items())):
        raise ValueError('Exact catalog, positive budgets and unchanged input bindings required')
    from nn_meta.v7.provenance import runtime_manifest
    root = Path(__file__).resolve().parents[2]
    # Import-time numerical dependencies and dynamically loaded indicators both
    # matter. Limit traversal to source directories; never archived data trees.
    directories = ('indicators', 'signals', 'portfolio', 'utils', 'nn_options_signal', 'options')
    sources = {p for d in directories for p in (root/d).rglob('*.py')}
    sources.update((root/'nn_meta').glob('*.py'))
    sources.update((root/'nn_meta/v7').glob('*.py'))
    sources.update((root/'v3').glob('*.py'))
    sources.update((root/'docs').rglob('*.pine'))
    sources.add(root/'requirements.txt')
    sources.update((root/'docs').rglob('*.json'))
    code = {str(p): sha(p) for p in sorted(sources)}
    actions = []
    for action in chart.history.actions:
        value = asdict(action)
        for key in ('effective_at', 'available_at'):
            value[key] = value[key].isoformat()
        actions.append(value)
    declaration = dict(schema='v7-causal-feature-store-v1', security_id=chart.history.security_id,
        start=chart.begin.isoformat(), end=chart.stop.isoformat(), minutes=chart.minutes,
        minimum_tick=chart.minimum_tick, raw_identity=_frame_identity(chart.history.raw),
        calendar=chart.calendar, actions=actions, variants=variants, inputs=inputs,
        sources=code, runtime=runtime_manifest(), bitorder='little', research_ready=False,
        average_storage='normalized plus exact contemporaneous epoch price units')
    fingerprint = identity(declaration)
    path.mkdir(parents=True, exist_ok=True)
    header = path/'declaration'
    if header.exists():
        verify(header, expected_identity=fingerprint)
    else:
        with transaction(header) as temp:
            _json(temp/'declaration.json', declaration)
            receipt(temp, dict(identity=fingerprint))
    _disk(path, reserve_bytes)
    basis = chart.proposal_basis()
    if basis.empty:
        raise ValueError('No completed proposal bars')
    basis_path = path/'basis'
    basis_identity = identity(dict(parent=fingerprint, frame=_frame_identity(basis)))
    if basis_path.exists():
        verify(basis_path, expected_identity=basis_identity)
    else:
        with transaction(basis_path) as temp:
            basis.to_parquet(temp/'bars.parquet')
            # Fresh raw selection prices stay separate from continuous stop units.
            chart.history.raw.to_parquet(temp/'raw.parquet')
            receipt(temp, dict(identity=basis_identity, execution_price=False))
    variant_positions = {v['variant_id']: i for i, v in enumerate(variants)}
    cuts = chart.history.epochs(start=chart.begin, end=chart.stop)
    ordinals = {bounds: i for i, bounds in enumerate(cuts)}
    completed = []
    for number, bounds in enumerate(cuts):
        destination = path/'epochs'/str(number)
        if destination.exists():
            verify(destination, expected_identity=identity(dict(parent=fingerprint, ordinal=number)))
            completed.append(bounds)
    for epoch in chart.epochs(skip_intervals=completed):
        number = ordinals[epoch.start, epoch.end]
        destination = path/'epochs'/str(number)
        n = len(epoch.observed)
        packed_size = (n+7)//8
        _disk(path, reserve_bytes, 4*len(variants)*packed_size)
        positions = basis.index.get_indexer(epoch.observed)
        if (positions < 0).any() or (np.diff(positions) != 1).any():
            raise ValueError('Epoch observations must be a contiguous proposal-basis slice')
        with transaction(destination) as temp:
            np.save(temp/'positions.npy', positions, allow_pickle=False)
            packed = np.lib.format.open_memmap(temp/'signals.npy', mode='w+', dtype='uint8',
                                              shape=(4, len(variants), packed_size))
            seen = set()
            for records, channels in signal_batches(epoch.bars, variants, sources=epoch.sources,
                    batch_columns=batch_columns, working_bytes=working_bytes):
                ids = [v['variant_id'] for v in records]
                if seen.intersection(ids):
                    raise ValueError('Duplicate signal batch')
                seen.update(ids)
                target = [variant_positions[v] for v in ids]
                for channel, frame in enumerate(channels):
                    values = frame.loc[epoch.observed, ids].to_numpy(dtype=bool).T
                    packed[channel, target, :] = np.packbits(values, axis=1, bitorder='little')
            if seen != set(variant_positions):
                raise ValueError('Incomplete epoch variant coverage')
            packed.flush()
            del packed
            features = epoch.technical.loc[epoch.observed].join(epoch.tv)
            if tuple(features) != (*TECHNICAL, *FEATURE_NAMES):
                raise ValueError('Incomplete causal feature schema')
            features.to_parquet(temp/'features.parquet')
            epoch.bars.loc[epoch.observed].to_parquet(temp/'bars.parquet')
            windows = sorted({v['params'][key] for v in variants if v['strategy']=='ma'
                              for key in ('fast_window', 'slow_window')})
            # Store normalized averages for parameter-specific ma_gap/px_vs_fast.
            # Later actions cannot change the units of these observed outputs.
            raw_averages = pd.DataFrame({str(w): epoch.bars.Close.rolling(w).mean().loc[epoch.observed]
                                        for w in windows},index=epoch.observed)
            raw_averages.to_parquet(temp/'raw_averages.parquet')
            averages = raw_averages.div(epoch.bars.Close.loc[epoch.observed],axis=0)
            averages.to_parquet(temp/'averages.parquet')
            _json(temp/'report.json', dict(ordinal=number, start=epoch.start.isoformat(),
                end=epoch.end.isoformat(), observations=n, first_position=int(positions[0]),
                last_position=int(positions[-1]), action_ids=list(epoch.action_ids),
                variants=len(variants), packed_bytes=4*len(variants)*packed_size))
            receipt(temp, dict(identity=identity(dict(parent=fingerprint, ordinal=number))))
    if any(sha(p) != h for p, h in {**inputs, **code}.items()):
        raise ValueError('Feature source or input changed during build')
    coverage = np.zeros(len(basis), dtype=bool)
    parts = []
    for number in range(len(cuts)):
        destination = path/'epochs'/str(number)
        if not destination.exists():
            continue  # No observations in this action interval; no synthetic bars.
        verify(destination, expected_identity=identity(dict(parent=fingerprint, ordinal=number)))
        positions = np.load(destination/'positions.npy', allow_pickle=False)
        if (positions < 0).any() or (positions >= len(basis)).any() or coverage[positions].any():
            raise ValueError('Overlapping or foreign epoch observations')
        coverage[positions] = True
        parts.append(dict(ordinal=number, receipt_sha256=sha(destination/'complete.json')))
    if not coverage.all():
        raise ValueError('Feature epochs omitted completed observations')
    report = dict(observations=len(basis), variants=len(variants), epochs=parts,
        full_timeframe_catalog=variants==catalog, packed_signal_bytes=sum(
            json.loads((path/'epochs'/str(p['ordinal'])/'report.json').read_text())['packed_bytes'] for p in parts),
        research_ready=False, source_and_input_guard='passed')
    summary_identity = identity(dict(parent=fingerprint, report=report,
                                    basis_receipt_sha256=sha(basis_path/'complete.json')))
    if (path/'summary').exists():
        verify(path/'summary', expected_identity=summary_identity)
    else:
        with transaction(path/'summary') as temp:
            _json(temp/'report.json', report)
            receipt(temp, dict(identity=summary_identity, parent_identity=fingerprint,
                              basis_receipt_sha256=sha(basis_path/'complete.json')))
    return report


class StoredFeatures:
    """Read a bounded number of complete-history boolean variant columns."""
    def __init__(self, path):
        self.path = Path(path)
        header = verify(self.path/'declaration')
        self.declaration = json.loads((self.path/'declaration/declaration.json').read_text())
        self.fingerprint = identity(self.declaration)
        summary = verify(self.path/'summary')
        self.report = json.loads((self.path/'summary/report.json').read_text())
        basis_digest = sha(self.path/'basis/complete.json')
        if (header['identity'] != self.fingerprint or summary['parent_identity'] != self.fingerprint
                or summary['basis_receipt_sha256'] != basis_digest
                or summary['identity'] != identity(dict(parent=self.fingerprint, report=self.report,
                                                        basis_receipt_sha256=basis_digest))):
            raise ValueError('Feature-store declaration or summary binding differs')
        self.verify_bindings()
        verify(self.path/'basis')
        self.basis = pd.read_parquet(self.path/'basis/bars.parquet')
        self.variants = self.declaration['variants']
        if self.report['observations'] != len(self.basis) or self.report['variants'] != len(self.variants):
            raise ValueError('Feature-store dimensions differ')
        self.parts = []
        coverage = np.zeros(len(self.basis), dtype=bool)
        for part in self.report['epochs']:
            destination = self.path/'epochs'/str(part['ordinal'])
            if sha(destination/'complete.json') != part['receipt_sha256']:
                raise ValueError('Epoch receipt differs')
            verify(destination, expected_identity=identity(dict(parent=self.fingerprint, ordinal=part['ordinal'])))
            positions = np.load(destination/'positions.npy', allow_pickle=False)
            packed = np.load(destination/'signals.npy', mmap_mode='r', allow_pickle=False)
            if (positions.ndim != 1 or positions.dtype.kind not in 'iu' or not len(positions)
                    or (positions < 0).any() or (positions >= len(self.basis)).any()
                    or (np.diff(positions) != 1).any() or coverage[positions].any()
                    or packed.dtype != np.dtype('uint8')
                    or packed.shape != (4, len(self.variants), (len(positions)+7)//8)):
                raise ValueError('Invalid packed signal dimensions or epoch positions')
            coverage[positions] = True
            self.parts.append((positions, packed))
        if not coverage.all():
            raise ValueError('Stored signals omit completed observations')

    def verify_bindings(self):
        if any(sha(p) != h for p, h in {**self.declaration['inputs'], **self.declaration['sources']}.items()):
            raise ValueError('Feature-store sources or inputs changed')
        from nn_meta.v7.provenance import runtime_manifest
        if identity(runtime_manifest()) != identity(self.declaration['runtime']):
            raise ValueError('Feature-store runtime changed')

    def signal_batches(self, *, batch_columns=16, working_bytes=128*1024**2):
        if type(batch_columns) is not int or batch_columns < 1 or type(working_bytes) is not int or working_bytes < 1:
            raise ValueError('Positive bounded signal budget required')
        width = min(batch_columns, working_bytes//max(1, len(self.basis)*40))
        if width < 1:
            raise ValueError('Working budget cannot hold one full-history signal column')
        for first in range(0, len(self.variants), width):
            records = self.variants[first:first+width]
            ids = [v['variant_id'] for v in records]
            values = [np.zeros((len(self.basis), len(records)), dtype=bool) for _ in range(4)]
            for positions, packed in self.parts:
                for channel, output in enumerate(values):
                    output[positions] = np.unpackbits(packed[channel, first:first+len(records)],
                        axis=1, count=len(positions), bitorder='little').T
            yield records, tuple(pd.DataFrame(v, index=self.basis.index, columns=ids) for v in values)


def build_proposals(path, store, *, symbol, start, end, reserve_bytes, batch_columns=16,
                    working_bytes=128*1024**2, symbols_by_date=None, eligibility=None, row_batch_size=16384):
    """Checkpoint bounded catalog batches, retaining all open/censored proposals."""
    from nn_meta.v7.proposals import proposals_from_signals
    from nn_meta.v7.compact_proposals import FORMAT, write_proposals
    from options.paper_risk import strategy_only_simulator_config
    from nn_meta.config import SIM_CONFIG
    from nn_meta.v7.scope import require_research_window
    require_research_window(start, end)
    if not symbol or pd.Timestamp(start, tz='America/New_York') < pd.Timestamp(store.declaration['start']) or (
            pd.Timestamp(end, tz='America/New_York')+pd.DateOffset(days=1) > pd.Timestamp(store.declaration['end'])):
        raise ValueError('Explicit symbol and proposal dates within stored feature history required')
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    parent = sha(store.path/'summary/complete.json')
    store.verify_bindings()
    if eligibility is not None:
        if eligibility.binding['security_id'] != store.declaration['security_id']:
            raise ValueError('Entry eligibility belongs to another security')
        if any(store.declaration['inputs'].get(p) != h for p,h in eligibility.binding['sources'].items()):
            raise ValueError('Entry membership sources are absent from the feature input binding')
    declaration = dict(schema=FORMAT, feature_summary_sha256=parent,
        feature_store=str(store.path.resolve()), symbol=symbol, start=start, end=end,
        batch_columns=batch_columns, working_bytes=working_bytes,
        symbols_by_date=symbols_by_date, research_ready=False,
        security_id=store.declaration['security_id'], variants=store.variants,
        simulator_policy=strategy_only_simulator_config(SIM_CONFIG),timezone=str(store.basis.index.tz),
        entry_eligibility=None if eligibility is None else eligibility.binding, row_batch_size=row_batch_size)
    fingerprint = identity(declaration)
    header = path/'declaration'
    if header.exists():
        verify(header, expected_identity=fingerprint)
    else:
        with transaction(header) as temp:
            _json(temp/'declaration.json', declaration)
            receipt(temp, dict(identity=fingerprint))
    reports = []
    for number, (records, channels) in enumerate(store.signal_batches(
            batch_columns=batch_columns, working_bytes=working_bytes)):
        _disk(path, reserve_bytes)
        destination = path/'batches'/str(number)
        part_identity = identity(dict(parent=fingerprint, variants=records))
        if destination.exists():
            verify(destination, expected_identity=part_identity)
            report = json.loads((destination/'report.json').read_text())
        else:
            _, rows = next(proposals_from_signals(symbol, store.basis, [(records, channels)],
                                                  start=start, end=end, stream=True))
            with transaction(destination) as temp:
                counts = write_proposals(temp/'proposals.parquet', rows, declaration,
                                         row_batch_size=row_batch_size, eligibility=eligibility)
                report = dict(batch=number, variants=[v['variant_id'] for v in records], **counts)
                _json(temp/'report.json', report)
                receipt(temp, dict(identity=part_identity))
        reports.append({**report, 'receipt_sha256': sha(destination/'complete.json')})
    store.verify_bindings()
    if sha(store.path/'summary/complete.json') != parent:
        raise ValueError('Feature summary changed during proposal build')
    report = dict(variants=sum(len(p['variants']) for p in reports),
        proposals=sum(p['proposals'] for p in reports), censored=sum(p['censored'] for p in reports),
        generated=sum(p['generated'] for p in reports),
        excluded_not_member=sum(p['excluded_not_member'] for p in reports),
        entry_filter_applied=eligibility is not None,
        batches=reports, research_ready=False, label_status='not_built')
    if report['variants'] != len(store.variants):
        raise ValueError('Proposal build omitted variants')
    summary_identity = identity(dict(parent=fingerprint, report=report))
    if (path/'summary').exists():
        verify(path/'summary', expected_identity=summary_identity)
    else:
        with transaction(path/'summary') as temp:
            _json(temp/'report.json', report)
            receipt(temp, dict(identity=summary_identity))
    return report


class StoredProposals:
    """Verified bounded reads of compact rows and their complete variant catalog."""
    def __init__(self, path, *, features=None):
        from nn_meta.v7.compact_proposals import FORMAT
        self.path = Path(path)
        header = verify(self.path/'declaration')
        self.declaration = json.loads((self.path/'declaration/declaration.json').read_text())
        self.fingerprint = identity(self.declaration)
        if self.declaration.get('schema')!=FORMAT or header['identity']!=self.fingerprint:
            raise ValueError('Unsupported or changed proposal declaration')
        self.features = features or StoredFeatures(self.declaration['feature_store'])
        self.features.verify_bindings()
        if (self.features.path.resolve()!=Path(self.declaration['feature_store']).resolve()
                or sha(self.features.path/'summary/complete.json')!=self.declaration['feature_summary_sha256']
                or self.features.variants!=self.declaration['variants']
                or self.features.declaration['security_id']!=self.declaration['security_id']):
            raise ValueError('Proposal feature parent changed')
        summary = verify(self.path/'summary')
        self.report = json.loads((self.path/'summary/report.json').read_text())
        if summary['identity']!=identity(dict(parent=self.fingerprint, report=self.report)):
            raise ValueError('Proposal summary changed')
        self.parts = []
        seen = []
        for number, part in enumerate(self.report['batches']):
            ids = part['variants']
            records = self.declaration['variants'][len(seen):len(seen)+len(ids)]
            if part['batch']!=number or [r['variant_id'] for r in records]!=ids or not records:
                raise ValueError('Proposal batches omit, duplicate or reorder variants')
            destination = self.path/'batches'/str(number)
            if sha(destination/'complete.json')!=part['receipt_sha256']:
                raise ValueError('Proposal batch receipt changed')
            verify(destination, expected_identity=identity(dict(parent=self.fingerprint, variants=records)))
            actual = json.loads((destination/'report.json').read_text())
            if actual != {k:v for k,v in part.items() if k!='receipt_sha256'}:
                raise ValueError('Proposal batch count binding differs')
            import pyarrow.parquet as pq
            if pq.ParquetFile(destination/'proposals.parquet').metadata.num_rows!=part['proposals']:
                raise ValueError('Compact proposal count differs')
            seen.extend(ids)
            self.parts.append((destination,part))
        if (len(seen)!=len(self.declaration['variants']) or len(seen)!=self.report['variants']
                or any(sum(p[k] for _,p in self.parts)!=self.report[k] for k in
                       ('proposals','censored','generated','excluded_not_member'))
                or self.report['generated']!=self.report['proposals']+self.report['excluded_not_member']):
            raise ValueError('Proposal summary omits rows or variants')

    def rows(self, *, batch_size=16384):
        from nn_meta.v7.compact_proposals import read_proposals
        self.features.verify_bindings()
        for directory, part in self.parts:
            # Recheck content at consumption time, including after an earlier read.
            verify(directory)
            count = censored = 0
            for row in read_proposals(directory/'proposals.parquet',self.declaration,batch_size=batch_size):
                if row['variant_id'] not in part['variants']:
                    raise ValueError('Compact row belongs to a foreign variant batch')
                count += 1
                censored += not row['proposal_closed']
                yield row
            if count!=part['proposals'] or censored!=part['censored']:
                raise ValueError('Compact proposal census differs')
