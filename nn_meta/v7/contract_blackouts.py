"""Explicit user-approved option-contract/date blackouts, without changing calendars.

A blackout excludes the affected research path. It never supplies standard
terms, selects a replacement, skips an actual held session, or invents a return.
Original proposals, demands, market observations and failure receipts remain.
"""
from copy import copy, deepcopy
from datetime import date
import json
from pathlib import Path

from nn_meta.v7.execution import CaptureUnavailable
from nn_meta.v7.storage import identity, receipt, sha, transaction, verify
from options.data.provider import parse_occ_symbol

SCHEMA = 'v7-contract-date-blackouts-v1'
STATUS = 'excluded_contract_reference_blackout'
TREATMENT = 'exclude_affected_research_path'


def normalized(contract, day):
    contract = contract.removeprefix('O:')
    parse_occ_symbol(contract)
    if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
        raise ValueError('Exact ISO contract reference date required')
    return contract, day


def validate_declaration(doc):
    if (doc.get('schema') != SCHEMA or not doc.get('policy_id')
            or not doc.get('authorization') or doc.get('scope') != 'exact_contract_date'
            or doc.get('treatment') != TREATMENT or doc.get('automatic_extension') is not False
            or doc.get('changes_exchange_calendar') is not False
            or doc.get('rerank_or_replace_contract') is not False
            or doc.get('creates_terms_or_outcomes') is not False
            or doc.get('historically_known_eligibility') is not False):
        raise ValueError('Explicit finite retrospective blackout policy required')
    entries = doc.get('exclusions')
    if not isinstance(entries, list) or not entries:
        raise ValueError('Named contract/date exclusions required')
    keys = []
    for entry in entries:
        if set(entry) != {'contract', 'date'}:
            raise ValueError('Blackouts require exact contracts and dates, not stock-wide rules')
        key = normalized(entry['contract'], entry['date'])
        if key != (entry['contract'], entry['date']):
            raise ValueError('Canonical contract ticker required in declaration')
        keys.append(key)
    if len(set(keys)) != len(keys):
        raise ValueError('Duplicate contract/date blackout')
    return keys


def _bind(root, inputs):
    root = Path(root).resolve()
    doc = verify(root)
    inputs[str(root/'complete.json')] = sha(root/'complete.json')
    for name, digest in doc['files'].items():
        inputs[str(root/name)] = digest
    return doc


def compile_blackouts(declaration_path, references, probes, output):
    """Seal exact missing-reference evidence; never broaden the declaration."""
    declaration_path = Path(declaration_path).resolve()
    doc = json.loads(declaration_path.read_text())
    keys = validate_declaration(doc)
    inputs = {str(declaration_path): sha(declaration_path), str(Path(__file__).resolve()): sha(__file__)}
    treatments = []
    for contract, day in keys:
        root, expiry, right, strike = parse_occ_symbol(contract)
        reference = Path(references)/contract/day
        missing = _bind(reference, inputs)
        expected = dict(path='/v3/reference/options/contracts/O:'+contract, params=dict(as_of=day))
        response = json.loads((reference/'response.json').read_text())
        if (missing.get('query') != expected or missing.get('http_status') != 404
                or response.get('status') != 'NOT_FOUND'):
            raise ValueError('Blackout lacks exact retained missing contract metadata')
        missing_digest = sha(reference/'complete.json')
        probe_digests = {}
        for expired in ('false', 'true'):
            probe = Path(probes)/contract/expired
            header = _bind(probe, inputs)
            binding = json.loads((probe/'binding.json').read_text())
            body = json.loads((probe/'response.json').read_text())
            query = dict(path='/v3/reference/options/contracts', params=dict(
                underlying_ticker=root, expiration_date=expiry.isoformat(), strike_price=strike,
                contract_type='call' if right == 'C' else 'put', as_of=day, expired=expired, limit=1000))
            results = body.get('results', [])
            if (binding.get('query') != query or binding.get('missing_receipt_sha256') != missing_digest
                    or header.get('http_status') != 200 or header.get('pagination_complete') is not True
                    or body.get('status') != 'OK' or body.get('next_url') or not isinstance(results, list)
                    or any(r.get('ticker') == 'O:'+contract for r in results)):
                raise ValueError('Blackout alternate reference evidence is incomplete or has a match')
            probe_digests[expired] = sha(probe/'complete.json')
        term = dict(contract=contract, date=day, treatment=TREATMENT, policy_id=doc['policy_id'],
                    missing_reference_sha256=missing_digest, alternative_receipts=probe_digests,
                    study_admitted=False, creates_terms_or_outcomes=False,
                    changes_exchange_calendar=False, rerank_or_replace_contract=False)
        treatments.append(dict(term, treatment_id=identity(term)))
    binding = dict(inputs=inputs, declaration_identity=identity(doc))
    output = Path(output)
    if output.exists():
        verify(output, expected_identity=identity(binding))
        return BlackoutPolicy(output)
    if any(sha(path) != digest for path, digest in inputs.items()):
        raise ValueError('Blackout evidence changed during compilation')
    with transaction(output) as temp:
        for name, value in [('declaration.json', doc), ('treatments.json', treatments), ('binding.json', binding)]:
            (temp/name).write_text(json.dumps(value, sort_keys=True, indent=2)+'\n')
        receipt(temp, dict(identity=identity(binding), schema=SCHEMA, exclusions=len(keys), research_ready=False))
    return BlackoutPolicy(output)


class BlackoutPolicy:
    def __init__(self, path):
        self.path = Path(path).resolve()
        header = verify(self.path)
        self.declaration = json.loads((self.path/'declaration.json').read_text())
        keys = validate_declaration(self.declaration)
        binding = json.loads((self.path/'binding.json').read_text())
        rows = json.loads((self.path/'treatments.json').read_text())
        if (header.get('schema') != SCHEMA or header.get('identity') != identity(binding)
                or binding.get('declaration_identity') != identity(self.declaration)
                or header.get('exclusions') != len(keys) or len(rows) != len(keys)):
            raise ValueError('Blackout declaration or census drift')
        self.treatments = {}
        for row in rows:
            key = normalized(row['contract'], row['date'])
            if (key not in keys or key in self.treatments or row.get('treatment') != TREATMENT
                    or row.get('policy_id') != self.declaration['policy_id']
                    or row.get('study_admitted') is not False
                    or row.get('treatment_id') != identity({k:v for k,v in row.items() if k != 'treatment_id'})):
                raise ValueError('Invalid or broadened blackout treatment')
            self.treatments[key] = row
        self.inputs = dict(binding['inputs'])
        _bind(self.path, self.inputs)
        self.fingerprint = header['identity']
        self.verify_bindings()

    def verify_bindings(self):
        if any(sha(path) != digest for path, digest in self.inputs.items()):
            raise ValueError('Blackout declaration, source or retained evidence changed')

    def at(self, contract, day):
        row = self.treatments.get(normalized(contract, day))
        return deepcopy(row) if row is not None else None

    def require_path(self, contract, source_dates):
        """Explicit held/physical path guard; never move settlement across a blackout."""
        hits = [hit for day in source_dates if (hit := self.at(contract, day)) is not None]
        if hits:
            raise ReferenceBlackout(hits[0])


class ReferenceBlackout(CaptureUnavailable):
    def __init__(self, treatment):
        self.treatment = deepcopy(treatment)
        super().__init__(f'Explicit contract reference blackout: {treatment["contract"]} {treatment["date"]}')


class BlackoutReferences:
    """The same dated reference interface, with explicit finite exclusions."""
    def __init__(self, parent, policy):
        self.parent, self.policy = parent, policy
        self.root = parent.root
        self.hits = {}

    def standard(self, contract, day):
        treatment = self.policy.at(contract, day)
        if treatment is not None:
            self.hits[treatment['treatment_id']] = treatment
            raise ReferenceBlackout(treatment)
        return self.parent.standard(contract, day)


class BlackoutObservedOptions:
    """Assembly adapter using actual feature/replay consumers without altering freezes."""
    def __init__(self, observations, policy):
        # Independent instance: inherited cached tick methods bind to this copy.
        self.engine = copy(observations)
        self.guard = BlackoutReferences(observations.references, policy)
        self.engine.references = self.guard
        self.policy = policy
        self.inputs = dict(observations.inputs)
        extra = dict(policy.inputs)
        for name in ('contract_blackouts.py', 'contracts.py', 'dataset_inputs.py', 'replay.py'):
            path = Path(__file__).with_name(name).resolve()
            extra[str(path)] = sha(path)
        for path, digest in extra.items():
            if path in self.inputs and self.inputs[path] != digest:
                raise ValueError('Conflicting blackout observation input binding')
            self.inputs[path] = digest
        self.declaration = dict(schema='v7-blackout-observations-v1', inputs=self.inputs,
            parent_observations=deepcopy(observations.declaration), blackout_identity=policy.fingerprint,
            treatment=TREATMENT, historically_known_eligibility=False, research_ready=False)
        self.verify_bindings()

    def verify_bindings(self):
        self.engine.verify_bindings()
        self.policy.verify_bindings()
        if any(sha(path) != digest for path, digest in self.inputs.items()):
            raise ValueError('Blackout consumer source or input changed')

    def observe(self, proposal, target):
        self.guard.hits.clear()
        result = self.engine.observe(proposal, target)
        if not self.guard.hits:
            return result
        # ObservedOptions/replay caught CaptureUnavailable and kept the partial
        # ledger. Retain that evidence, but omit numerical features/targets from
        # assembly admission. A held position is never converted to closed cash.
        result = {k:v for k,v in result.items() if k != 'ticks'}
        result['prior_status'] = result['status']
        result['status'] = STATUS
        result['admission'] = dict(study_admitted=False, policy_identity=self.policy.fingerprint,
            treatments=deepcopy(list(self.guard.hits.values())), historically_known_eligibility=False,
            changes_exchange_calendar=False, portfolio_admission=False)
        if result.get('replay') is not None:
            path = result['replay']
            if path.get('label_complete') or path.get('label_end_ns') is not None or path.get('net_return') is not None:
                raise ValueError('Excluded reference path unexpectedly produced a complete label')
            result['replay'] = dict(path, prior_status=path['status'], status=STATUS,
                                    study_admitted=False, portfolio_admission=False)
        return result
