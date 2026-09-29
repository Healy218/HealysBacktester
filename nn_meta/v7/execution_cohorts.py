"""Cover later signal horizons by the same observed pre-roll execution prefix.

This changes representation, not which original proposals are accounted for.
Each bucket binds its exact membership digest back to the frozen horizon queue.
"""
from collections import defaultdict
from itertools import groupby

from nn_meta.v7.execution_jobs import proposal_from_key
from nn_meta.v7.execution_prefix_cache_v2 import reusable
from nn_meta.v7.storage import identity


def cohorts(rows):
    for (symbol,decision),group in groupby(rows,key=lambda r:r[:2]):
        sides=defaultdict(list)
        for row in group:
            sides[row[4]].append(row)
            if len(sides[row[4]])>20000:raise ValueError('Unbounded entry horizon cohort')
        for side,values in sorted(sides.items()):
            yield (symbol,decision,side),values


def cover_horizons(rows,security_id,target,run):
    """Replay a real latest horizon, then only earlier branches it cannot cover."""
    remaining={tuple(r[:6]):r[6] for r in rows}
    if len(remaining)!=len(rows):raise ValueError('Duplicate factored horizon')
    ordinal=0
    while remaining:
        key=max(remaining,key=lambda k:(k[2]==-1,k[2],k))
        source=proposal_from_key(key,security_id)
        result=run(source,target)
        if reusable(result,source):
            selected=[k for k in remaining if reusable(result,proposal_from_key(k,security_id))]
            mode='same_entry_pre_roll_prefix'
        else:
            selected=[key];mode='exact_horizon'
        if key not in selected:raise ValueError('Observed prefix does not cover its source horizon')
        selected.sort()
        membership=[[list(k),remaining[k]] for k in selected]
        bucket=dict(target_dte=target,ordinal=ordinal,source_horizon=source,source_key=list(key),
                    coverage_mode=mode,members=len(selected),proposal_weight=sum(remaining[k] for k in selected),
                    membership_sha256=identity(membership),result=result)
        yield bucket
        for k in selected:del remaining[k]
        ordinal+=1


def members_for_bucket(bucket,rows,security_id,already=()):
    excluded=set(already)
    selected=[]
    for row in rows:
        key=tuple(row[:6])
        if key in excluded:continue
        admitted=(list(key)==bucket['source_key'] if bucket['coverage_mode']=='exact_horizon'
                  else reusable(bucket['result'],proposal_from_key(key,security_id)))
        if admitted:selected.append(row)
    selected.sort(key=lambda r:tuple(r[:6]))
    if (len(selected)!=bucket['members'] or sum(r[6] for r in selected)!=bucket['proposal_weight']
            or identity([[list(r[:6]),r[6]] for r in selected])!=bucket['membership_sha256']):
        raise ValueError('Execution bucket membership differs from frozen horizons')
    return selected
