"""Read parent seals by reference; never relabel an old artifact as newly built."""
import json
from pathlib import Path
from incubator.continual.storage import sha, verify, write, seal


class ParentArtifacts:
    def __init__(self, config):
        reference = config['inherited_artifacts']
        self.path = Path(reference['path'])
        if sha(self.path) != reference['sha256']:
            raise ValueError('Inherited artifact census changed')
        self.document = json.loads(self.path.read_text())
        self.root = Path(self.document['root'])
        self.contract = self.document['contract_identity']
        self.anchors = self.document['anchors']
        self.checked = {}

    def resolve(self, relative, declaration=None):
        relative = str(relative)
        anchor = relative+'/complete.json'
        if anchor not in self.anchors:
            return None
        root = self.root/relative
        if relative not in self.checked:
            if sha(root/'complete.json') != self.anchors[anchor]:
                raise ValueError('Inherited receipt changed')
            header = verify(root)
            # Store only the small declaration and file stats, not the potentially
            # large historical market-evidence lists repeated in r2 receipts.
            paths = [root/'complete.json', *(root/name for name in header['files'])]
            self.checked[relative] = (header['declaration'], {
                str(p): (p.stat().st_size, p.stat().st_mtime_ns) for p in paths})
        actual, stats = self.checked[relative]
        if any((Path(p).stat().st_size,Path(p).stat().st_mtime_ns)!=stamp for p,stamp in stats.items()):
            raise ValueError('Inherited payload changed during continuation')
        if declaration is not None:
            expected = dict(declaration, contract=self.contract)
            # r2 stored no ordinal; only unambiguous existing prefixes are reusable.
            if 'proposals' in expected:
                proposals = expected['proposals']
                if any(p.get('proposal_ordinal', 0) for p in proposals):
                    return None
                expected['proposals'] = [{k:v for k,v in p.items() if k!='proposal_ordinal'} for p in proposals]
            if actual != expected:
                raise ValueError('Inherited artifact inputs differ')
        return root

    def reuse_symbols(self, config, through, run_dir, symbols):
        expected_snapshot = config['bootstrap_snapshot']['sha256']
        for symbol in symbols:
            destination = Path(run_dir)/'symbols'/symbol
            if (destination/'complete.json').exists():
                continue
            parent = self.resolve(Path('runs')/through/'symbols'/symbol)
            if parent is None:
                continue
            header = verify(parent)
            expected = dict(symbol=symbol, through=through, snapshot_sha256=expected_snapshot, contract=self.contract)
            if header['declaration'] != expected:
                raise ValueError('Inherited symbol has different scope or snapshot')
            inventory = json.loads((parent/'inventory.json').read_text())
            for item in inventory['candidates']:
                feature = Path(item['feature_root'])
                if self.resolve(feature.relative_to(self.root)) is None:
                    raise ValueError('Inherited inventory refers to an unbound feature')
                if item['status'] != 'pending':
                    label = Path(item['label_root'])
                    label_declaration=dict(candidate_id=item['candidate_id'],
                        feature_sha256=self.anchors[str(feature.relative_to(self.root))+'/complete.json'],
                        contract=self.contract)
                    if self.resolve(label.relative_to(self.root),label_declaration) is None:
                        raise ValueError('Inherited inventory refers to an unbound label')
            write(destination/'inventory.json', inventory)
            seal(destination, dict(expected, contract=config['contract_identity']), ['inventory.json'],
                 inherited_from=str(parent), parent_receipt_sha256=sha(parent/'complete.json'))
            history = self.root/'history'/f'{symbol}.json'
            if sha(history) != self.document['history'][symbol]:
                raise ValueError('Inherited stock history binding changed')
            write(Path(config['root'])/'history'/f'{symbol}.json', json.loads(history.read_text()))
