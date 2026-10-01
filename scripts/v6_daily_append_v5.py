"""Reuse sealed occurrence batches and append newly observed trade occurrences."""
from collections import defaultdict
import json
from pathlib import Path
import time
import shutil

import numpy as np
import pandas as pd
from incubator.continual.storage import sha, verify, write, seal
from incubator.recovery_v6.data import (
    KEYS, candidate_key, terminal_label, proposal_records, load_symbol, candidate_batch,
)


def occurrence(proposal):
    return proposal['strategy'], int(proposal.get('proposal_ordinal', 0))


def normalized(proposal):
    return dict(proposal, proposal_ordinal=int(proposal.get('proposal_ordinal', 0)))


def matching_occurrences(actual, expected):
    """A parent may lack new occurrences, but none of its inputs may change."""
    a = {k:v for k,v in actual.items() if k not in {'contract', 'proposals'}}
    b = {k:v for k,v in expected.items() if k not in {'contract', 'proposals'}}
    if a != b:
        raise ValueError('Inherited feature prefix or scope differs')
    wanted = {occurrence(p):normalized(p) for p in expected['proposals']}
    if len(wanted) != len(expected['proposals']):
        raise ValueError('Duplicate requested occurrence')
    found = {}
    for p in actual['proposals']:
        key = occurrence(p)
        if key in found:
            raise ValueError('Duplicate inherited occurrence')
        if key not in wanted or normalized(p) != wanted[key]:
            raise ValueError('Inherited proposal changed or disappeared')
        found[key] = wanted[key]
    return set(found)


class ParentArtifacts:
    def __init__(self, config):
        self.layers = []
        ref = config['inherited_artifacts']
        while ref:
            if sha(ref['path']) != ref['sha256']:
                raise ValueError('Inheritance census changed')
            document = json.loads(Path(ref['path']).read_text())
            self.layers.append(document)
            ref = document.get('ancestor')
        self.checked = {}
        self.digests = {}
        self.feature_index = {}
        for layer in self.layers:
            index = defaultdict(list)
            for anchor in layer['anchors']:
                if anchor.startswith('features/'):
                    entry = '/'.join(anchor.split('/')[:3])
                    index[entry].append(anchor.removesuffix('/complete.json'))
            self.feature_index[layer['root']] = index

    def at(self, layer, relative):
        relative = str(relative)
        digest = layer['anchors'].get(relative + '/complete.json')
        if digest is None:
            return None
        path = Path(layer['root']) / relative
        if path not in self.checked:
            if sha(path/'complete.json') != digest:
                raise ValueError('Inherited seal changed')
            receipt = verify(path)
            if receipt['declaration']['contract'] != layer['contract_identity']:
                raise ValueError('Inherited producer contract differs')
            files = [path/'complete.json', *(path/name for name in receipt['files'])]
            self.checked[path] = (receipt['declaration'], {
                p:(p.stat().st_size,p.stat().st_mtime_ns) for p in files})
            self.digests[path] = digest
        _, stats = self.checked[path]
        if any((p.stat().st_size,p.stat().st_mtime_ns) != stamp for p,stamp in stats.items()):
            raise ValueError('Inherited payload changed during reuse')
        return path

    def bound_path(self, path):
        path = Path(path)
        for layer in self.layers:
            root = Path(layer['root'])
            if path.is_relative_to(root):
                resolved = self.at(layer, path.relative_to(root))
                if resolved is not None:
                    return resolved
        raise ValueError('Inventory refers to an unbound artifact: ' + str(path))

    def resolve(self, relative, declaration=None):
        for layer in self.layers:
            path = self.at(layer, relative)
            if path is None:
                continue
            if declaration is not None:
                actual = self.checked[path][0]
                expected = dict(declaration, contract=layer['contract_identity'])
                if actual != expected:
                    raise ValueError('Inherited label identity or feature lineage differs')
            return path
        return None

    def feature_parts(self, root, relative, declaration):
        """Select each occurrence once, retaining its original feature seal."""
        selected = set()
        parts = []
        local = Path(root) / relative
        candidates = []
        local_parts = ([local] if (local/'complete.json').exists() else [])
        local_parts += [p.parent for p in sorted(local.glob('*/complete.json'))]
        for part in local_parts:
            receipt = verify(part)
            if receipt['declaration']['contract'] != declaration['contract']:
                raise ValueError('Local feature contract differs')
            candidates.append((part, receipt['declaration']))
        for layer in self.layers:
            for name in self.feature_index[layer['root']].get(str(relative), []):
                path = self.at(layer, name)
                candidates.append((path, self.checked[path][0]))
        for path, actual in candidates:
            # A newer sealed batch owns overlapping occurrences; older r2 batches
            # may have been superseded by r3's explicit collision recovery.
            available = {occurrence(p) for p in actual['proposals']}
            if available <= selected:
                continue
            keys = matching_occurrences(actual, declaration) - selected
            frame = pd.read_parquet(path/'features.parquet')
            if 'proposal_ordinal' not in frame:
                frame['proposal_ordinal'] = 0
            frame = frame.loc[[occurrence(r) in keys for r in frame.to_dict('records')]].copy()
            if {occurrence(r) for r in frame.to_dict('records')} != keys:
                raise ValueError('Inherited batch does not cover its declared occurrences')
            parts.append((path, frame))
            selected.update(keys)
        missing = [p for p in declaration['proposals'] if occurrence(p) not in selected]
        return parts, missing

    def feature_paths(self, symbol):
        return sorted({Path(layer['root'])/anchor.removesuffix('/complete.json')/'features.parquet'
                       for layer in self.layers for anchor in layer['anchors']
                       if anchor.startswith(f'features/{symbol}/')})

    def reuse_symbols(self, config, through, run_dir, symbols):
        layer = self.layers[0]
        ref = config['reuse_contract']
        contract_path = Path(layer['root'])/'contract.json'
        if sha(contract_path) != ref['sha256']:
            raise ValueError('Inherited producer contract changed')
        old = json.loads(contract_path.read_text())
        from scripts.run_v6_continual_v4 import runtime_sources
        if old['sources'] != runtime_sources():
            raise ValueError('Inherited r4 runtime changed')
        for key in ['release_sha256','base_dataset_sha256','append_start','validation_days',
                    'embargo_days','frozen_training_contract','prefix_snapshot','comparison_candidate']:
            if old[key] != config[key]:
                raise ValueError('Inherited symbol semantics changed: ' + key)
        for symbol in symbols:
            target = Path(run_dir)/'symbols'/symbol
            parent = self.at(layer, f'runs/{through}/symbols/{symbol}')
            if parent is None:
                continue
            expected = dict(symbol=symbol, through=through,
                snapshot_sha256=config['bootstrap_snapshot']['sha256'], contract=layer['contract_identity'])
            if self.checked[parent][0] != expected:
                raise ValueError('Inherited complete symbol scope differs')
            if target.exists():
                if target.resolve() != parent.resolve():
                    raise ValueError('Inherited symbol destination differs')
                continue
            inventory = json.loads((parent/'inventory.json').read_text())
            for item in inventory['candidates']:
                feature = self.bound_path(item['feature_root'])
                if item['status'] != 'pending':
                    label = self.bound_path(item['label_root'])
                    actual = self.checked[label][0]
                    if actual['candidate_id'] != item['candidate_id'] or actual['feature_sha256'] != self.digests[feature]:
                        raise ValueError('Inherited label feature binding differs')
            history = Path(layer['root'])/'history'/f'{symbol}.json'
            if sha(history) != layer['history'][symbol]:
                raise ValueError('Inherited stock history changed')
            write(Path(config['root'])/'history'/history.name, json.loads(history.read_text()))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(parent, target_is_directory=True)


def new_occurrence_batch(obj, fresh, market, output):
    # The old helper's unique-strategy fast path assumes ordinal zero. Preserve
    # the real ordinal when the new shard contains only an additional occurrence.
    frames = []
    for proposal in fresh:
        batch, _ = candidate_batch(obj, [proposal], market,
                                   Path(output)/proposal['strategy']/str(proposal['proposal_ordinal']))
        frames.append(batch.assign(proposal_ordinal=proposal['proposal_ordinal']))
    return pd.concat(frames, ignore_index=True)


def build_symbol(config, snapshot, symbol, root, through, run_dir, deadline):
    from nn_meta.live.v6_forward_inputs import attach_context
    from nn_meta.v6_expansion import bars_sha256
    from nn_meta.baseline import execute_at_dte
    from nn_meta.price_basis import raw_spot_provenance
    from nn_meta.weekly_expiry import dte_grid_for
    from incubator.recovery_v6.market import ResearchMarket
    inherited = ParentArtifacts(config)
    started = time.monotonic(); root = Path(root); run_dir = Path(run_dir)
    def budget():
        if time.monotonic() > deadline:
            raise TimeoutError('nightly build deadline reached')
        if shutil.disk_usage(root).free < 12_000_000_000:
            raise ValueError('research disk reserve reached')
    budget()
    release = Path(config['release']); obj = load_symbol(Path(snapshot), release, symbol)
    bars = obj.bars[symbol].loc[:through].copy(); raw = obj.raw[symbol].loc[:through].copy()
    history = root/'history'/f'{symbol}.json'
    if history.exists():
        prior = json.loads(history.read_text())
        for name, frame in [('all', bars), ('raw', raw)]:
            if bars_sha256(frame.loc[:prior['last_bar']]) != prior[name]:
                raise ValueError('Previously consumed stock history revised')
    attach_context(symbol, bars, obj.training, obj.calendar_doc)
    proposals = proposal_records(symbol, bars, obj.spec['symbols'][symbol], config['append_start'], through)
    expected = []; counts = dict(proposals=len(proposals), candidates=0, new_features=0, matured=0, pending=0, unfilled=0)
    groups = defaultdict(list)
    for p in proposals:
        groups[p['entry_ts']].append(p)
    market = ResearchMarket(Path(config.get('market_root', root/'market'))/symbol, deadline=deadline)
    raw_close = raw.Close.copy()
    raw_close.attrs = dict(raw_spot_provenance('15m', provider='alpaca', feed='sip'), symbol=symbol)
    features = json.loads((release/'model/ensemble_config.json').read_text())['features']
    for ts, fresh in sorted(groups.items()):
        budget()
        write(run_dir/'progress'/f'{symbol}.json', dict(symbol=symbol, entry_ts=ts.isoformat(), counts=counts,
              elapsed_seconds=time.monotonic()-started))
        prefix = bars.loc[:ts].copy(); obj.bars = {symbol:prefix}; obj.raw = {symbol:raw.loc[:ts].copy()}
        relative = Path('features')/symbol/ts.strftime('%Y%m%dT%H%M%S')
        declaration = dict(schema='v6-continual-features-v1', release_sha256=config['release_sha256'],
            symbol=symbol, entry_ts=ts.isoformat(), all_prefix=bars_sha256(prefix),
            raw_prefix=bars_sha256(raw.loc[:ts]), contract=config['contract_identity'],
            proposals=[{k:(v.isoformat() if isinstance(v, pd.Timestamp) else v)
                        for k,v in p.items() if k not in {'exit_ts','closed'}} for p in fresh])
        parts, missing = inherited.feature_parts(root, relative, declaration)
        if missing:
            target = root/relative
            if (target/'complete.json').exists():
                # A later daily run may add another occurrence at an existing
                # prefix; keep each new batch in a distinct immutable shard.
                target = root/relative/through
                if (target/'complete.json').exists():
                    receipt = verify(target, dict(declaration, proposals=missing))
                    batch = pd.read_parquet(target/'features.parquet')
                else:
                    batch = None
            else:
                batch = None
            if batch is None:
                keys = {occurrence(p) for p in missing}
                additions = [p for p in fresh if occurrence(p) in keys]
                batch = new_occurrence_batch(obj, additions, market, run_dir/'context'/symbol/ts.strftime('%Y%m%dT%H%M%S'))
                if len(batch) != len(additions)*len(dte_grid_for(symbol, obj.spec)) or not set(features) <= set(batch):
                    raise ValueError('candidate coverage/schema mismatch')
                if batch.duplicated(KEYS+['proposal_ordinal']).any() or np.isinf(batch[features].to_numpy(float)).any():
                    raise ValueError('duplicate proposal occurrence or infinite features')
                target.mkdir(parents=True, exist_ok=True); batch.to_parquet(target/'features.parquet', index=False)
                seal(target, dict(declaration, proposals=missing), ['features.parquet'], rows=len(batch),
                     snapshot=str(snapshot), snapshot_sha256=sha(Path(snapshot)/'manifest.json'),
                     market_evidence=list(market.evidence), inherited_batches=[str(p) for p,_ in parts])
                counts['new_features'] += len(batch)
            parts.append((target, batch))
        by_strategy = {occurrence(p):p for p in fresh}
        seen = set()
        for entry_root, batch in parts:
            counts['candidates'] += len(batch)
            feature_digest = sha(entry_root/'complete.json')
            for row in batch.to_dict('records'):
                budget(); key = candidate_key(row)
                if key in seen:
                    raise ValueError('Duplicate candidate across inherited/new batches')
                seen.add(key); p = by_strategy[occurrence(row)]
                target = root/'labels'/symbol/key
                if not (target/'complete.json').exists():
                    parent = inherited.resolve(target.relative_to(root), dict(candidate_id=key,
                        feature_sha256=feature_digest, contract=config['contract_identity']))
                    if parent is not None:
                        target = parent
                if (target/'complete.json').exists():
                    receipt = verify(target)
                    if receipt['declaration']['feature_sha256'] != feature_digest:
                        raise ValueError('label feature lineage differs')
                    label = json.loads((target/'label.json').read_text())
                elif not p['closed']:
                    label = dict(status='pending', candidate_id=key)
                else:
                    records, meta = execute_at_dte(symbol, [(ts,p['exit_ts'],p['direction'])], bars,
                        int(row['dte']), market, through, raw_close=raw_close)
                    if meta['capped'] or len(records) != 1:
                        raise ValueError('incomplete candidate execution')
                    r = records[0]
                    if not terminal_label(r, p['exit_ts']):
                        counts['pending'] += 1
                        expected.append(dict(candidate_id=key, feature_root=str(entry_root), label_root=str(target),
                                             status='pending', reason='execution_path_not_terminal'))
                        continue
                    label = dict(status='matured' if r['executed'] else 'unfilled', candidate_id=key,
                        entry_ts=ts.isoformat(), exit_ts=pd.Timestamp(p['exit_ts']).isoformat(),
                        net_return=r['net_return'], executed=r['executed'],
                        und_period_return=float(bars.loc[p['exit_ts'],'Close']/bars.loc[ts,'Close']-1),
                        fill_exit_ts=pd.Timestamp(r['fill_exit_ts']).isoformat() if r['executed'] else None)
                    if r['executed']:
                        if not np.isfinite(r['net_return']):
                            raise ValueError('non-finite completed label')
                        label['label_excess'] = int(r['net_return'] > label['und_period_return'])
                    target.mkdir(parents=True, exist_ok=True); write(target/'label.json', label)
                    seal(target, dict(candidate_id=key, feature_sha256=feature_digest, contract=config['contract_identity']),
                         ['label.json'], snapshot=str(snapshot), snapshot_sha256=sha(Path(snapshot)/'manifest.json'),
                         market_evidence=list(market.evidence))
                counts[label['status']] += 1
                expected.append(dict(candidate_id=key, feature_root=str(entry_root), label_root=str(target), status=label['status']))
        if len(seen) != len(fresh)*len(dte_grid_for(symbol,obj.spec)):
            raise ValueError('Occurrence batches do not cover current candidates')
    previous = set()
    paths = list((root/'features'/symbol).rglob('features.parquet')) + inherited.feature_paths(symbol)
    for path in paths:
        previous.update(candidate_key(r) for r in pd.read_parquet(path).to_dict('records'))
    if previous != {r['candidate_id'] for r in expected}:
        raise ValueError('candidate history changed or disappeared')
    write(history, dict(last_bar=bars.index[-1].isoformat(), all=bars_sha256(bars), raw=bars_sha256(raw)))
    directory = run_dir/'symbols'/symbol
    directory.mkdir(parents=True, exist_ok=True)
    write(directory/'inventory.json', dict(candidates=expected, counts=counts, seconds=time.monotonic()-started))
    seal(directory, dict(symbol=symbol, through=through, snapshot_sha256=sha(Path(snapshot)/'manifest.json'),
         contract=config['contract_identity']), ['inventory.json'])
    return counts
