"""Monthly equity eligibility keyed by dated security identities, not static aliases."""
from __future__ import annotations
import gzip
import json
from pathlib import Path
import pandas as pd
from nn_meta.v7.storage import verify,sha

EQUITY_TYPES=frozenset({'CS','ADRC','ETF','ETV','ETN','FUND'})


def security_masters(root):
    result={};sources={}
    for path in sorted(Path(root).glob('*/complete.json')):
        doc=verify(path.parent);day=doc['query']['date'];records=[]
        for page in sorted(path.parent.glob('page-*.json.gz')):
            records.extend(json.loads(gzip.decompress(page.read_bytes()))['results'])
        if len(records)!=doc['records']:raise ValueError('Security master count mismatch')
        good={}
        for r in records:
            if r.get('market')!='stocks' or r.get('type') not in EQUITY_TYPES or not r.get('active') or not r.get('composite_figi'):continue
            key=r['ticker'].replace('.','')
            if key in good and good[key]['composite_figi']!=r['composite_figi']:raise ValueError('Ambiguous OCC-to-stock identity')
            good[key]=r
        result[day]=good;sources[day]=sha(path)
    return result,sources


def daily_identity_overrides(root, requests):
    """Exact queried days only; absence and uncaptured data are different."""
    result, sources = {}, {}
    for request in requests:
        symbol, day = request['symbol'], request['date']
        path = Path(root) / symbol / day
        if not path.exists():
            continue
        doc = verify(path)
        expected = {'path': f'/v3/reference/tickers/{symbol}', 'params': {'date': day}}
        if doc.get('query') != expected:
            raise ValueError('Dated identity query changed')
        body = json.loads((path / 'response.json').read_text())
        if doc['http_status'] == 404:
            value = None
        elif doc['http_status'] == 200:
            record = body.get('results', {})
            if record.get('ticker') != symbol:
                raise ValueError('Dated identity response changed the requested ticker')
            if not record.get('composite_figi'):
                # Capture success is not identity resolution. Retain its hash,
                # leaving this day unresolved wherever option observations
                # actually need an identity; never infer from the name.
                sources[str(path)] = sha(path / 'complete.json')
                continue
            value = record['composite_figi']
        else:
            raise ValueError('Unsuccessful dated identity capture')
        key = (symbol.replace('.', ''), day)
        if key in result and result[key] != value:
            raise ValueError('Conflicting exact-day identities')
        result[key] = value
        sources[str(path)] = sha(path / 'complete.json')
    return result, sources


def membership(daily,masters,calendar,*,through='2026-08',window=63,min_active=50,enter=270,exit=330,
               identity_days=None, excluded_sessions=()):
    identity_days = {} if identity_days is None else identity_days
    if daily.empty or daily[['date', 'root']].duplicated().any():
        raise ValueError('Nonempty unique option root/day history required')
    if not 1 <= min_active <= window or not 1 <= enter <= exit:
        raise ValueError('Invalid membership lookback/rank policy')
    days=sorted(daily.date.unique())
    calendar_days=[s['date'] for s in calendar['sessions']]
    if calendar_days != sorted(set(calendar_days)):
        raise ValueError('Ordered unique calendar sessions required')
    excluded=set(excluded_sessions)
    if not excluded.issubset(calendar_days) or excluded.intersection(days):
        raise ValueError('Excluded sessions must remain in calendar and be absent from inputs')
    expected=[d for d in calendar_days if days[0]<=d<=days[-1]]
    if days!=[d for d in expected if d not in excluded]:
        raise ValueError('PIT daily history has missing captured sessions')
    month_days={}
    for day in days:month_days.setdefault(day[:7],[]).append(day)
    mapped=[];known={};members=set();output=[];unknown=[];root_identities={};unresolved=[];resolved=[];windows=[]
    for month,current_days in sorted(month_days.items()):
        if month>through:break
        end=current_days[-1]
        if end not in masters:raise ValueError('Missing month-end dated security master')
        current=masters[end]
        active={r['composite_figi']:r['ticker'] for r in current.values()}
        for root,r in current.items():
            identity=r['composite_figi']
            root_identities.setdefault(root,set()).add(identity)
        # Preserve known old symbols for ticker changes. They may contribute
        # only to an identity that is still active in this month's snapshot.
        changed = {root for root, r in current.items() if root in known
                   and known[root]['composite_figi'] != r['composite_figi']}
        for root in sorted(changed):
            observed_days = set(daily.loc[daily.root.eq(root) & daily.date.isin(current_days), 'date'])
            missing = [day for day in current_days if day in observed_days and (root, day) not in identity_days]
            (unresolved if missing else resolved).append({'root': root, 'month': month,
                                                        'required_observed_days': len(observed_days),
                                                        'uncaptured_days': missing})
        known.update(current)
        block=daily[daily.date.str.startswith(month)].copy()
        block['security_id']=block.root.map({k:r['composite_figi'] for k,r in known.items()})
        # Every observed day in a transition month uses its own provider
        # identity. Missing transition evidence stays an explicit blocker.
        for root in changed:
            mask = block.root.eq(root)
            block.loc[mask, 'security_id'] = [identity_days.get((root, day)) for day in block.loc[mask, 'date']]
        absent=block[block.security_id.isna()]
        unknown.extend({'month':month,'root':r} for r in sorted(absent.root.unique()))
        block=block.dropna(subset=['security_id'])
        mapped.append(block)
        past=pd.concat(mapped,ignore_index=True)
        calendar_window=[d for d in expected if d<=end][-window:]
        if len(calendar_window)<window:continue
        # Deleted sessions consume calendar lookback, but are neither zeros
        # nor replaced by older observations. Activity retains its absolute
        # minimum; median ranks are recalculated over the retained sessions.
        trailing=[d for d in calendar_window if d not in excluded]
        windows.append({'month':month,'calendar_sessions':len(calendar_window),
                        'retained_sessions':len(trailing),
                        'excluded_sessions':sorted(excluded.intersection(calendar_window))})
        history=past[past.date.isin(trailing)].groupby(['date','security_id']).opt_dollar_vol.sum().unstack('security_id').reindex(trailing)
        score=history.fillna(0).median();activity=history.notna().sum()
        score=score[(activity>=min_active)&(score>0)&score.index.isin(active)]
        ranked=score.rename('score').reset_index().sort_values(['score','security_id'],ascending=[False,True])
        ranked['rank']=range(1,len(ranked)+1);ranks=dict(zip(ranked.security_id,ranked['rank']));scores=dict(zip(ranked.security_id,ranked.score))
        members={i for i in members if ranks.get(i,float('inf'))<=exit}|{i for i,r in ranks.items() if r<=enter}
        following=[s['date'] for s in calendar['sessions'] if s['date']>end]
        if not following:raise ValueError('Calendar lacks next membership availability session')
        for identity in sorted(members):output.append({'month':month,'ticker':active[identity],'security_id':identity,
            'rank':ranks[identity],'score':float(scores[identity]),'available_at':following[0]})
    conflicts={r:sorted(ids) for r,ids in root_identities.items() if len(ids)>1}
    # Monthly snapshots do not establish an exact mid-month reused-ticker
    # boundary. Keep this explicit blocker for day-level identity resolution.
    return pd.DataFrame(output),{'unmapped_root_months':unknown,'reused_roots':conflicts,
                                'resolved_transitions': resolved, 'unresolved_transitions': unresolved,
                                'lookback_policy': {'window':window,'min_active':min_active,
                                    'enter':enter,'exit':exit,'excluded_sessions':sorted(excluded),
                                    'deletion_treatment':'consume calendar lookback; omit from median and activity; no backfill'},
                                'lookback_windows':windows,
                                'identity_boundaries_verified':not unresolved,'research_ready':False}
