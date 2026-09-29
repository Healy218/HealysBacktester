#!/usr/bin/env python3
"""Bind explicit user approval to the audited exact reference exclusions."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

if __name__=='__main__':
    from nn_meta.v7.reviewed_blackouts import compile_reviewed_blackouts
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['review','prior','approval','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    policy=compile_reviewed_blackouts(a.review,a.prior,a.approval,a.output)
    print(json.dumps(dict(exclusions=len(policy.treatments),identity=policy.fingerprint,full_execution_coverage=False)))
