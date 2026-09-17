"""Join stored causal observations to daily, sector and selected-option context."""
from bisect import bisect_right
import json

import pandas as pd

from nn_meta.v7.rows import FeatureRows, TECHNICAL, FEATURE_NAMES
from nn_meta.v7.sectors import DatedSectors
from nn_meta.v7.storage import sha, verify, identity
from nn_meta.v7.proposal_store import _frame_identity


class StoredFeatureRows:
    """One action epoch resident; callers should process rows by epoch for reuse."""
    def __init__(self, proposals, daily, *, sectors, inputs):
        self.proposals = proposals
        self.features = proposals.features
        security = self.features.declaration['security_id']
        if not isinstance(sectors,DatedSectors) or sectors.security_id!=security or not inputs:
            raise ValueError('Bound dated sector and daily inputs required')
        self.daily, self.sectors = daily, sectors
        self.binding = dict(schema='v7-stored-feature-row-join-v1',
            proposal_summary_sha256=sha(proposals.path/'summary/complete.json'),
            inputs=dict(inputs),daily_identity=_frame_identity(daily),
            sector_identity=_frame_identity(pd.DataFrame(list(sectors.records.values())).sort_values('date').reset_index(drop=True)))
        self.fingerprint = identity(self.binding)
        self.verify_bindings()
        self.raw = pd.read_parquet(self.features.path/'basis/raw.parquet')
        self.raw_available = pd.DatetimeIndex(self.raw.available_at)
        if not self.raw_available.is_monotonic_increasing or self.raw_available.has_duplicates:
            raise ValueError('Unique causal raw selection clocks required')
        self.epochs = self.features.report['epochs']
        self.first = [int(positions[0]) for positions,_ in self.features.parts]
        self.variants = {v['variant_id']:v for v in self.features.variants}
        self.cached = None

    def verify_bindings(self):
        self.features.verify_bindings()
        if any(sha(p)!=h for p,h in self.binding['inputs'].items()):
            raise ValueError('Stored row context inputs changed')
        if (sha(self.proposals.path/'summary/complete.json')!=self.binding['proposal_summary_sha256']
                or _frame_identity(self.daily)!=self.binding['daily_identity']
                or _frame_identity(pd.DataFrame(list(self.sectors.records.values())).sort_values('date').reset_index(drop=True))
                   !=self.binding['sector_identity']):
            raise ValueError('Stored row context or proposal summary changed')

    def row(self, proposal, *, ticks, target_dte):
        variant = self.variants[proposal['variant_id']]
        decision = pd.Timestamp(proposal['decision_ns'],unit='ns',tz='UTC')
        key = {k:proposal[k] for k in ('symbol','variant_id','decision_ns','right')}
        if (proposal['security_id']!=self.features.declaration['security_id']
                or proposal['proposal_id']!=identity(dict(schema='v7-proposal-v1',**key))
                or pd.Timestamp(proposal['decision_at'])!=decision):
            raise ValueError('Proposal identity differs from stored row inputs')
        routing = self.proposals.declaration['symbols_by_date']
        symbol = (routing.get(decision.tz_convert('America/New_York').date().isoformat())
                  if routing is not None else self.proposals.declaration['symbol'])
        if proposal['symbol']!=symbol:raise ValueError('Proposal uses a different dated stock ticker')
        bar_at = decision-pd.Timedelta(minutes=variant['signal_minutes'])
        position = self.features.basis.index.get_indexer([bar_at])[0]
        if position < 0:raise ValueError('Proposal has no stored completed feature observation')
        epoch = bisect_right(self.first,position)-1
        part = self.epochs[epoch]
        cache_key = epoch,symbol
        if self.cached is None or self.cached[0]!=cache_key:
            path = self.features.path/'epochs'/str(part['ordinal'])
            if sha(path/'complete.json')!=part['receipt_sha256']:
                raise ValueError('Stored causal epoch receipt changed')
            verify(path)
            bars = pd.read_parquet(path/'bars.parquet')
            features = pd.read_parquet(path/'features.parquet')
            builder = FeatureRows(bars,{'minutes':self.features.declaration['minutes']},
                features[list(TECHNICAL)],features[list(FEATURE_NAMES)],self.daily,
                symbol=symbol,security_id=proposal['security_id'],sector=self.sectors)
            averages = pd.read_parquet(path/'raw_averages.parquet')
            if not averages.index.equals(bars.index):raise ValueError('Stored parameter averages are misaligned')
            builder.averages = {int(w):averages[w] for w in averages}
            self.cached = cache_key,builder,json.loads((path/'report.json').read_text())
        _, builder, epoch_report = self.cached
        if variant['strategy']=='ma' and any(variant['params'][k] not in builder.averages
                                            for k in ('fast_window','slow_window')):
            raise ValueError('Missing saved causal parameter average; do not recompute from a truncated epoch')
        raw_position = self.raw_available.searchsorted(decision,side='right')-1
        if raw_position < 0:raise ValueError('No completed raw selection price')
        row = builder.row(variant=variant,bar_at=bar_at,right=proposal['right'],target_dte=target_dte,
            bars_since_previous_signal=proposal['bars_since_previous_signal'],ticks=ticks,
            raw_spot=float(self.raw.Close.iloc[raw_position]),
            raw_spot_available_ns=int(self.raw_available[raw_position].value))
        row.attrs.update(stored_join_identity=self.fingerprint,epoch_ordinal=part['ordinal'],
                         action_ids=epoch_report['action_ids'])
        return row
