"""Source-bound synthetic ETFE option ledger study and independent cash audit."""
import argparse
from decimal import Decimal, ROUND_HALF_EVEN
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nn_meta.etfe.acquisition import save, sha, write_new
from nn_meta.etfe.execution_ledger import OptionLedger

FIXTURE = 'docs/specs/ETFE_EXECUTION_HAND_FIXTURE_20261005.json'
SOURCES = ['nn_meta/etfe/execution_ledger.py', 'nn_meta/etfe/vwap_reference.py',
           'nn_meta/etfe/purchase_policy_v2.py', 'nn_meta/etfe/acquisition.py',
           'docs/specs/ETFE_SCOPE_0DTE_20261004.json',
           'docs/specs/ETFE_EXECUTION_20261003.md',
           'docs/specs/ETFE_0DTE_NORMALIZATION_20261004.md',
           'docs/specs/ETFE_EXECUTION_COMPONENTS_20261005.md', FIXTURE,
           'scripts/pilot_etfe_execution.py', 'tests/test_etfe_execution_ledger.py']


def read(path):
    return json.loads(path.read_text())


def prepare(root):
    expected = dict(schema='etfe-execution-component-study-v1', evidence_kind='synthetic',
                    sources={p: sha((ROOT / p).read_bytes()) for p in SOURCES},
                    training_admitted=False)
    if not (root / 'PLAN.json').exists():
        root.mkdir(parents=True, exist_ok=True)
        (root / 'sources').mkdir(exist_ok=True)
        for p in SOURCES:
            dest = root / 'sources' / p
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                write_new(dest, (ROOT / p).read_bytes())
            if sha(dest.read_bytes()) != expected['sources'][p]:
                raise ValueError('Preparation source mismatch')
        save(root / 'PLAN.json', expected)
    if read(root / 'PLAN.json') != expected:
        raise ValueError('Frozen source mismatch: use a successor')
    for p, digest in expected['sources'].items():
        if sha((root / 'sources' / p).read_bytes()) != digest:
            raise ValueError('Source snapshot mismatch')
    return read(root / 'sources' / FIXTURE)


def run(root, stop_after=None):
    inputs = prepare(root)
    prior = []
    for index in range(len(inputs['steps'])):
        checkpoint = root / f'checkpoint-{index + 1}.json'
        receipt = root / f'checkpoint-{index + 1}.sha256.json'
        if not checkpoint.exists():
            break
        digest = sha(checkpoint.read_bytes())
        # An interrupted receipt publication is recoverable only after a replay.
        if not receipt.exists():
            replay = OptionLedger(inputs['fixture'])
            for step in inputs['steps'][:index + 1]:
                replay.step(**step)
            if replay.snapshot() != read(checkpoint):
                raise ValueError('Uncommitted checkpoint replay mismatch')
            save(receipt, dict(sha256=digest))
        if read(receipt)['sha256'] != digest:
            raise ValueError('Checkpoint corruption')
        prior.append(dict(path=checkpoint.name, sha256=digest))
    ledger = OptionLedger.restore(read(root / prior[-1]['path'])) if prior else OptionLedger(inputs['fixture'])
    count = len(prior)
    if stop_after is not None and not 1 <= stop_after <= len(inputs['steps']):
        raise ValueError('Invalid stop count')
    limit = stop_after or len(inputs['steps'])
    for index in range(count, limit):
        ledger.step(**inputs['steps'][index])
        checkpoint = root / f'checkpoint-{index + 1}.json'
        save(checkpoint, ledger.snapshot())
        save(root / f'checkpoint-{index + 1}.sha256.json', dict(sha256=sha(checkpoint.read_bytes())))
    complete = limit == len(inputs['steps']) or count == len(inputs['steps'])
    result = dict(complete=complete, checkpoints=max(count, limit), outcome=ledger.outcome())
    if complete and not (root / 'COMPLETE.json').exists():
        save(root / 'COMPLETE.json', result)
    if prior:
        for p in prior:
            assert sha((root / p['path']).read_bytes()) == p['sha256']
        receipt = root / f'RESUME-{count}-{max(count, limit)}.json'
        if not receipt.exists():
            save(receipt, dict(restored_checkpoint=count, prior_files_unchanged=prior,
                               complete=complete, source_bound=True))
    return result


def audit(root):
    inputs = prepare(root)
    ledger = OptionLedger(inputs['fixture'])
    for index, step in enumerate(inputs['steps'], 1):
        ledger.step(**step)
        checkpoint = root / f'checkpoint-{index}.json'
        assert sha(checkpoint.read_bytes()) == read(root / f'checkpoint-{index}.sha256.json')['sha256']
        assert ledger.snapshot() == read(checkpoint), 'Uninterrupted prefix differs from saved/resumed state'
    # Independent Decimal audit: do not call kernel cash/fee/capacity functions.
    cash, outstanding, quantities, capacity, amounts = 10_000_000, [], {}, {}, []
    for event in ledger.events:
        if event['kind'] == 'settlement':
            cash += event['cents']
            outstanding.remove(event['cents'])
        if event['kind'] != 'fill':
            continue
        q, ref, contract = event['quantity'], event['reference'], event['contract']
        multiplier = inputs['fixture']['contracts'][contract]['multiplier']
        gross = Decimal(q) * Decimal(str(ref['price'])) * Decimal(str(multiplier))
        fee, slip = gross * Decimal('.001'), gross * Decimal('.0005')
        raw = gross + fee + slip if event['side'] == 'buy' else gross - fee - slip
        amount = int(raw.quantize(Decimal('.01'), rounding=ROUND_HALF_EVEN) * 100)
        assert amount == event['cash_cents']
        for name, expected in [('gross', gross), ('fee', fee), ('slippage', slip)]:
            assert abs(Decimal(str(event[name])) - expected) < Decimal('1e-9')
        assert abs(Decimal(str(event['rounding_residual'])) - (Decimal(amount) / 100 - raw)) < Decimal('1e-9')
        key = ref['key']
        capacity[key] = capacity.get(key, 0) + q
        assert capacity[key] <= int(Decimal(str(ref['volume'])) * Decimal('.01'))
        quantities[contract] = quantities.get(contract, 0) + (q if event['side'] == 'buy' else -q)
        assert quantities[contract] >= 0
        if event['side'] == 'buy':
            cash -= amount
        else:
            outstanding.append(amount)
        assert cash >= 0
        amounts.append(amount)
    assert amounts == [200300, 67898, 125811]
    assert cash == ledger.cash == 9_993_409 and not outstanding and not any(quantities.values())
    result = dict(schema='etfe-execution-independent-audit-v1', evidence_kind='synthetic',
                  checks=['all_prefixes_replayed', 'cash_and_quantity_conservation',
                          'decimal_fee_slippage_rounding', 'shared_bar_capacity', 'hand_expected_cashflows'],
                  fills=3, checkpoints=5, cashflows_cents=amounts, final_cash_cents=cash,
                  pnl_cents=-6591, training_admitted=False,
                  complete_sha256=sha((root / 'COMPLETE.json').read_bytes()))
    if not (root / 'INDEPENDENT_AUDIT.json').exists():
        save(root / 'INDEPENDENT_AUDIT.json', result)
    else:
        assert read(root / 'INDEPENDENT_AUDIT.json') == result
    assert read(root / 'COMPLETE.json') == dict(complete=True, checkpoints=5, outcome=ledger.outcome())
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['run', 'audit'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--stop-after', type=int)
    args = parser.parse_args()
    root = args.root.resolve()
    if root.parent != ROOT / 'nn_meta/validation' or not root.name.startswith('etfe-execution-components-'):
        parser.error('An isolated ETFE execution-components root is required')
    print(json.dumps(run(root, args.stop_after) if args.command == 'run' else audit(root), indent=2))
