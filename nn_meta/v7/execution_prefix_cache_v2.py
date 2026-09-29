"""Share observed pre-roll stops/gaps only when a later signal cannot affect them."""
from copy import deepcopy
from nn_meta.v7.storage import identity

from nn_meta.v7.entry_demand import selection_id


def reusable(result, proposal):
    replay=result.get('replay')
    if replay is None or replay['rolls'] != 0:
        return False
    status=result['status']
    if status=='observed_unfilled_entry':
        return True
    if status=='option_midpoint_stop':
        boundary=replay['label_end_ns']
        if not replay['label_complete'] or boundary is None:return False
    elif status=='capture_incomplete':
        if (not result['pending'] or replay.get('risk_exit') is not None
                or any(a.get('action') in ('signal_exit','expiry_exit','roll_buy') for a in replay['attempts'])
                or any(r.get('purpose') in ('exit_sale','roll_purchase','expiry_itm_classification') for r in result['pending'])):
            return False
        boundary=max([proposal['decision_ns'],
                      *(a['clock_ns'] for a in replay['attempts']),
                      *(m['clock_ns'] for m in replay['marks'])])
    else:
        return False
    exit_at=proposal.get('exit_decision_ns')
    return exit_at is None or exit_at>boundary


class SharedExecutionWorker:
    """Private immutable payload cache for the factorized writer; nested lists are read-only."""
    def __init__(self, worker):
        self.worker=worker
        self.entry=None
        self.cache={}
        self.hits=0

    @property
    def inputs(self):return self.worker.inputs

    def run(self,proposal,target):
        entry=(proposal['symbol'],proposal['decision_ns'],proposal['right'])
        if entry!=self.entry:
            self.entry=entry;self.cache.clear()
        key=selection_id(*entry,target)
        selection=self.worker.db.execute('SELECT status,contract FROM selections WHERE selection_id=?',(key,)).fetchone()
        if selection and selection[0]=='selected':
            contract=selection[1]
            cached=self.cache.get(contract)
            if cached is not None and reusable(cached,proposal):
                # Every target must still agree with the frozen selector. Only a
                # path ending before any target-dependent roll can be shared.
                if self.worker.select(entry[0],entry[2],target,entry[1])!=contract:
                    raise ValueError('Cached prefix selector differs')
                result=dict(cached,replay=dict(cached['replay']))
                result['proposal_id']=proposal['proposal_id']
                result['replay']['proposal_id']=proposal['proposal_id']
                result['selection_id']=key
                self.hits+=1
                return result
        result=self.worker.run(proposal,target)
        if selection and selection[0]=='selected' and reusable(result,proposal):
            result['shared_result_id']=identity(dict(proposal_id=proposal['proposal_id'],selection_id=key))
            self.cache[selection[1]]=deepcopy(result)
        return result

    def close(self):
        self.cache.clear();self.worker.close()
