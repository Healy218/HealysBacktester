"""Resolve immutable r3 and ancestral r2 artifacts without changing their seals."""
import json
from pathlib import Path
from incubator.continual.storage import sha,verify
from incubator.recovery_v6.inheritance import ParentArtifacts as R2Artifacts


class ParentArtifacts:
    def __init__(self, config):
        ref=config['inherited_artifacts']
        if sha(ref['path'])!=ref['sha256']:raise ValueError('Daily inheritance census changed')
        self.document=json.loads(Path(ref['path']).read_text())
        self.root=Path(self.document['root']);self.anchors=self.document['anchors']
        self.contract=self.document['contract_identity'];self.checked={}
        self.ancestor=R2Artifacts({'inherited_artifacts':self.document['ancestor']})

    def resolve(self,relative,declaration=None):
        relative=str(relative);anchor=relative+'/complete.json'
        if anchor not in self.anchors:return self.ancestor.resolve(relative,declaration)
        target=self.root/relative
        if relative not in self.checked:
            if sha(target/'complete.json')!=self.anchors[anchor]:raise ValueError('Daily parent seal changed')
            receipt=verify(target)
            files=[target/'complete.json',*(target/name for name in receipt['files'])]
            self.checked[relative]=(receipt['declaration'],{str(p):(p.stat().st_size,p.stat().st_mtime_ns) for p in files})
        actual,stats=self.checked[relative]
        if any((Path(p).stat().st_size,Path(p).stat().st_mtime_ns)!=stamp for p,stamp in stats.items()):
            raise ValueError('Daily parent payload changed during update')
        if declaration is not None and actual!=dict(declaration,contract=self.contract):
            raise ValueError('Daily parent artifact inputs differ')
        return target

    def feature_paths(self,symbol):
        result={self.root/anchor.removesuffix('/complete.json')/'features.parquet'
                for anchor in self.anchors if anchor.startswith(f'features/{symbol}/')}
        result.update(self.ancestor.root/anchor.removesuffix('/complete.json')/'features.parquet'
                      for anchor in self.ancestor.anchors if anchor.startswith(f'features/{symbol}/'))
        return sorted(result)

    def reuse_symbols(self,config,through,run_dir,symbols):
        # Prior dates remain immutable; new daily inventories are reconciled from
        # reused features/labels plus newly completed proposals, never relabeled.
        return None
