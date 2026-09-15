"""Expanded, inspectable source/runtime bindings with an end-of-run mutation guard."""
from importlib.metadata import distributions
from pathlib import Path
import platform
import sys

from nn_meta.v7.storage import sha, identity


def source_manifest(root):
    root = Path(root).resolve()
    directories = ('nn_meta', 'nn_options_signal', 'options', 'portfolio', 'signals',
                   'indicators', 'utils', 'v3', 'scripts')
    paths = {p for name in directories for p in (root / name).rglob('*.py')
             if '__pycache__' not in p.parts}
    paths.update(p for p in (root / 'requirements.txt',) if p.exists())
    # Pine inputs/defaults are read dynamically, so Python alone is insufficient.
    paths.update(p for p in (root / 'docs').rglob('*')
                 if p.is_file() and p.suffix in ('.pine', '.json'))
    return {str(p.relative_to(root)): sha(p) for p in sorted(paths)}


def runtime_manifest():
    return {'python': sys.version, 'executable': sys.executable, 'platform': platform.platform(),
            'packages': sorted((d.metadata['Name'], d.version) for d in distributions())}


class RunBinding:
    def __init__(self, root, *, inputs, declaration):
        self.root = Path(root)
        self.paths = [Path(p).resolve() for p in inputs]
        self.document = {'sources': source_manifest(root), 'runtime': runtime_manifest(),
                         'inputs': {str(p): sha(p) for p in self.paths}, 'declaration': declaration}

    def finish(self):
        if source_manifest(self.root) != self.document['sources']:
            raise ValueError('Source changed during the run; output cannot be sealed')
        if {str(p): sha(p) for p in self.paths} != self.document['inputs']:
            raise ValueError('Input changed during the run; output cannot be sealed')
        return {**self.document, 'identity': identity(self.document), 'source_and_input_guard': 'passed'}
