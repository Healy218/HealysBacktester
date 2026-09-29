#!/usr/bin/env python3
"""Re-run exact failed entry prefixes with isolated cache writes and complete receipts."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    from scripts.run_v6_continual_v3 import configure
    from incubator.continual.storage import sha,seal,verify,write
    config=json.loads((ROOT/'deploy/incubator-continual-v6-r3.json').read_text());configure(config)
    import logging
    from utils.logging_utils import setup_logging
    setup_logging(log_level=logging.ERROR)
    import pandas as pd
    import numpy as np
    from incubator.recovery_v6.data import load_symbol,proposal_records,candidate_batch,candidate_key
    from incubator.recovery_v6.market import ResearchMarket
    from nn_meta.live.v6_forward_inputs import attach_context
    a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=True)
    parent=Path(config['lineage']['previous_root']);run=parent/'runs'/config['bootstrap_snapshot']['through']
    failures=json.loads((parent/'latest-run.json').read_text())['errors']
    symbols=[e['symbol'] for e in failures if 'HTTP 502' in e['error']]
    reports=[];deadline=time.monotonic()+1800
    features=json.loads((Path(config['release'])/'model/ensemble_config.json').read_text())['features']
    class OverlayMarket(ResearchMarket):
        def __init__(self,symbol,root):
            super().__init__(root,deadline=deadline);self.saved=Path(config['market_root'])/symbol
        def get_chain(self,symbol,**kwargs):
            rel=Path('chains')/str(kwargs['as_of'])/(symbol+'.json')
            if (self.saved/rel).exists() and not (self.root/rel).exists():
                (self.root/rel).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(self.saved/rel,self.root/rel)
            return super().get_chain(symbol,**kwargs)
        def tick_features(self,request,policy):
            rel=Path('ticks')/str(pd.Timestamp(int(request['window_end_ns']),tz='UTC').date())/request['request_id']
            for name in ['quotes.json.gz','quotes.manifest.json','trades.json.gz','trades.manifest.json']:
                src=self.saved/rel/name;dest=self.root/rel/name
                # Existing manifests bind their payload; copy only complete pairs.
                manifest=src if name.endswith('manifest.json') else src.with_name(name.replace('.json.gz','.manifest.json'))
                if src.exists() and manifest.exists() and not dest.exists():
                    dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
            return super().tick_features(request,policy)
    for symbol in symbols:
        output=a.output/symbol;meter=run/'progress'/f'{symbol}.json'
        binding=dict(symbol=symbol,old_failure_meter_sha256=sha(meter),snapshot_sha256=config['bootstrap_snapshot']['sha256'],
            script_sha256=sha(__file__),sources={str(p):sha(p) for p in sorted((ROOT/'incubator/recovery_v6').glob('*.py'))})
        if (output/'complete.json').exists():
            verify(output,binding);reports.append(json.loads((output/'report.json').read_text()));continue
        ts=pd.Timestamp(json.loads(meter.read_text())['entry_ts'])
        obj=load_symbol(Path(config['bootstrap_snapshot']['path']),Path(config['release']),symbol)
        bars=obj.bars[symbol];attach_context(symbol,bars,obj.training,obj.calendar_doc)
        proposals=proposal_records(symbol,bars,obj.spec['symbols'][symbol],config['append_start'],config['bootstrap_snapshot']['through'])
        fresh=[r for r in proposals if r['entry_ts']==ts]
        if not fresh:raise ValueError('Original failed prefix disappeared')
        obj.bars[symbol]=bars.loc[:ts].copy();obj.raw[symbol]=obj.raw[symbol].loc[:ts].copy()
        market=OverlayMarket(symbol,a.output/'market'/symbol)
        batch,_=candidate_batch(obj,fresh,market,output/'context')
        if np.isinf(batch[features].to_numpy(float)).any():raise ValueError('Infinite features')
        keys=[candidate_key(r) for r in batch.to_dict('records')]
        if len(keys)!=len(set(keys)):raise ValueError('Candidate collision')
        report=dict(symbol=symbol,entry_ts=ts.isoformat(),rows=len(batch),original_tick_failure_resolved=True,
            market_evidence=market.evidence,full_symbol_complete=False)
        output.mkdir(parents=True,exist_ok=True);batch.to_parquet(output/'features.parquet',index=False)
        write(output/'report.json',report);seal(output,binding,['report.json','features.parquet'])
        reports.append(report)
        print(json.dumps(dict(symbol=symbol,rows=len(batch),resolved=True)),flush=True)
        del obj,bars,batch,market
    write(a.output/'report.json',dict(symbols=symbols,resolved=len(reports),all_original_tick_frontiers_resolved=True,
          full_update_complete=False))
    print((a.output/'report.json').read_text())

if __name__=='__main__':main()
