import json
from pathlib import Path

import pytest

from nn_meta.v7.contract_blackouts import BlackoutReferences, ReferenceBlackout
from nn_meta.v7.reviewed_blackouts import compile_reviewed_blackouts, exclusion_phase
from nn_meta.v7.storage import identity, receipt, sha
from tests.test_v7_contract_blackouts import policy_at


def fixture(tmp_path):
    prior=policy_at(tmp_path/'prior')
    review=tmp_path/'review';review.mkdir()
    proposal={k:v for k,v in prior.declaration.items() if k not in ('policy_id','authorization')}
    proposal.update(schema='v7-reference-exclusion-review-v1',authorization=None,
        exclusions=[dict(contract='SPY220318C00400000',date='2022-03-17',reason='unsupported_cash_deliverable')])
    report=dict(full_alternate_recovery_capture=True,exact_matches=0,proposed_exact_exclusions=1)
    for name,value in [('proposed-exclusions.json',proposal),('report.json',report),('binding.json',dict(inputs={}))]:
        (review/name).write_text(json.dumps(value))
    receipt(review,dict(identity=identity(proposal)))
    approval=tmp_path/'approval.json'
    approval.write_text(json.dumps(dict(decision='approve_exact_exclusions',proposal_sha256=sha(review/'proposed-exclusions.json'),
        count=1,user_answer='Approve exact exclusions',observed_at='2026-09-28T22:00:00-05:00',policy_id='test-approved-v2')))
    return prior,review,approval


def test_exact_union_preserves_prior_and_does_not_broaden(tmp_path):
    prior,review,approval=fixture(tmp_path)
    combined=compile_reviewed_blackouts(review,prior.path,approval,tmp_path/'combined')
    assert len(combined.treatments)==len(prior.treatments)+1
    for key,term in prior.treatments.items():
        assert combined.at(*key)['prior_treatment']==term
    assert combined.at('SPY220318C00400000','2022-03-17')
    assert combined.at('SPY220318C00400000','2022-03-18') is None
    class Parent:
        root=tmp_path
        def standard(self,*args):return args
    guarded=BlackoutReferences(Parent(),combined)
    with pytest.raises(ReferenceBlackout):guarded.standard('SPY220318C00400000','2022-03-17')
    assert guarded.standard('SPY220318C00400000','2022-03-18')==('SPY220318C00400000','2022-03-18')


@pytest.mark.parametrize('field,value',[('proposal_sha256','wrong'),('count',2),('decision','pending')])
def test_approval_cannot_transfer_to_another_scope(tmp_path,field,value):
    prior,review,approval=fixture(tmp_path)
    doc=json.loads(approval.read_text());doc[field]=value;approval.write_text(json.dumps(doc))
    with pytest.raises(ValueError,match='Explicit approval'):
        compile_reviewed_blackouts(review,prior.path,approval,tmp_path/'combined')
    assert not (tmp_path/'combined').exists()


def test_entry_and_held_exclusions_keep_no_label():
    result=dict(status='excluded_contract_reference_blackout',pending=[],replay=dict(fills=[],label_complete=False,net_return=None))
    assert exclusion_phase(result)=='entry'
    result['replay']['fills']=[dict(side='buy')]
    assert exclusion_phase(result)=='held_or_roll'
    result['replay']['net_return']=0
    with pytest.raises(ValueError):exclusion_phase(result)
