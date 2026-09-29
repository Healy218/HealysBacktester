"""Compile approved, audited packed-reference exclusions into the finite policy."""
import json
from pathlib import Path

from nn_meta.v7.contract_blackouts import BlackoutPolicy, SCHEMA, TREATMENT, validate_declaration
from nn_meta.v7.storage import identity, receipt, sha, transaction, verify


def compile_reviewed_blackouts(review, prior, approval_path, output):
    review, approval_path, output = map(lambda p: Path(p).resolve(), (review, approval_path, output))
    verify(review)
    old = BlackoutPolicy(prior)
    proposal = json.loads((review/'proposed-exclusions.json').read_text())
    report = json.loads((review/'report.json').read_text())
    approval = json.loads(approval_path.read_text())
    rows = proposal['exclusions']
    if (approval.get('decision') != 'approve_exact_exclusions'
            or approval.get('proposal_sha256') != sha(review/'proposed-exclusions.json')
            or approval.get('count') != len(rows) or not approval.get('user_answer')
            or not approval.get('observed_at') or not approval.get('policy_id')):
        raise ValueError('Explicit approval must bind this exact proposed list')
    if (proposal.get('schema') != 'v7-reference-exclusion-review-v1'
            or report.get('full_alternate_recovery_capture') is not True
            or report.get('exact_matches') != 0
            or report.get('proposed_exact_exclusions') != len(rows)):
        raise ValueError('Incomplete reference recovery audit')
    inputs = dict(json.loads((review/'binding.json').read_text())['inputs'])
    inputs.update(old.inputs)
    for path in [approval_path, Path(__file__).resolve(), review/'complete.json']:
        inputs[str(path)] = sha(path)
    # Verify sealed evidence now; retain receipt bindings for subsequent consumers.
    for path, digest in inputs.items():
        if sha(path) != digest:
            raise ValueError('Reference evidence changed before approval compilation')
        if Path(path).name == 'complete.json':
            verify(Path(path).parent)
    keys = [(r['contract'], r['date']) for r in rows]
    if len(set(keys)) != len(keys) or set(keys) & set(old.treatments):
        raise ValueError('Duplicate or broadened exclusion scope')
    reasons = {'missing_from_detail_and_both_exact_lists', 'unsupported_cash_deliverable'}
    if any(r.get('reason') not in reasons for r in rows):
        raise ValueError('Unreviewed exclusion reason')
    declaration = {k: proposal[k] for k in ('scope', 'treatment', 'automatic_extension',
        'changes_exchange_calendar', 'rerank_or_replace_contract', 'creates_terms_or_outcomes',
        'historically_known_eligibility')}
    declaration.update(schema=SCHEMA, policy_id=approval['policy_id'], authorization=approval,
        exclusions=[dict(contract=c, date=d) for c, d in sorted(set(keys) | set(old.treatments))])
    validate_declaration(declaration)
    treatments = []
    evidence = {(r['contract'], r['date']): r for r in rows}
    for entry in declaration['exclusions']:
        key = entry['contract'], entry['date']
        term = dict(entry, treatment=TREATMENT, policy_id=approval['policy_id'], study_admitted=False,
            creates_terms_or_outcomes=False, changes_exchange_calendar=False, rerank_or_replace_contract=False)
        if key in old.treatments:
            term['prior_treatment'] = old.treatments[key]
        else:
            term['reviewed_evidence'] = evidence[key]
        treatments.append(dict(term, treatment_id=identity(term)))
    binding = dict(inputs=inputs, declaration_identity=identity(declaration))
    if any(sha(path) != digest for path, digest in inputs.items()):
        raise ValueError('Exclusion inputs changed during compilation')
    with transaction(output) as temp:
        for name, value in [('declaration.json', declaration), ('treatments.json', treatments), ('binding.json', binding)]:
            (temp/name).write_text(json.dumps(value, sort_keys=True, indent=2)+'\n')
        receipt(temp, dict(identity=identity(binding), schema=SCHEMA, exclusions=len(treatments), research_ready=False))
    return BlackoutPolicy(output)


def exclusion_phase(result):
    """Separate entries rejected before purchase from paths with actual prior fills."""
    if result['status'] != 'excluded_contract_reference_blackout':
        return None
    replay = result['replay']
    if replay['label_complete'] or replay['net_return'] is not None or result['pending']:
        raise ValueError('Excluded path must retain an incomplete, non-numerical outcome')
    return 'held_or_roll' if replay['fills'] else 'entry'
