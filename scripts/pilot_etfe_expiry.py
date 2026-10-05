"""Immutable synthetic lifecycle study, resumable by observation checkpoint."""
import argparse
from decimal import Decimal, ROUND_HALF_EVEN
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nn_meta.etfe.acquisition import save, sha, write_new
from nn_meta.etfe.execution_ledger import OptionLedger
from nn_meta.etfe.expiry_ledger import ExpiryLedger

FIXTURE = 'docs/specs/ETFE_EXPIRY_HAND_FIXTURES_20261005.json'
SOURCES = ['nn_meta/etfe/expiry_ledger.py', 'nn_meta/etfe/execution_ledger.py',
           'nn_meta/etfe/vwap_reference.py', 'nn_meta/etfe/purchase_policy_v2.py',
           'nn_meta/etfe/acquisition.py', 'docs/specs/ETFE_SCOPE_0DTE_20261004.json',
           'docs/specs/ETFE_EXECUTION_20261003.md', 'docs/specs/ETFE_0DTE_NORMALIZATION_20261004.md',
           'docs/specs/ETFE_EXPIRY_COMPONENTS_20261005.md', FIXTURE,
           'scripts/pilot_etfe_expiry.py', 'tests/test_etfe_expiry_ledger.py']


def read(path):
    return json.loads(path.read_text())


def prepare(root):
    plan = dict(schema='etfe-expiry-study-v1', evidence_kind='synthetic', training_admitted=False,
                sources={p: sha((ROOT / p).read_bytes()) for p in SOURCES})
    if not (root / 'PLAN.json').exists():
        root.mkdir(parents=True, exist_ok=True)
        for p in SOURCES:
            target = root / 'sources' / p
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                write_new(target, (ROOT / p).read_bytes())
            assert sha(target.read_bytes()) == plan['sources'][p]
        save(root / 'PLAN.json', plan)
    if read(root / 'PLAN.json') != plan:
        raise ValueError('Frozen source mismatch: successor required')
    for p, digest in plan['sources'].items():
        assert sha((root / 'sources' / p).read_bytes()) == digest
    return read(root / 'sources' / FIXTURE)['cases']


def start(case):
    option = OptionLedger(case['base'])
    for frame in case['prefix']:
        option.step(**frame)
    return ExpiryLedger(option.snapshot(), case['lifecycle'])


def run(root, max_steps=None):
    cases = prepare(root)
    if max_steps is not None and max_steps < 1:
        raise ValueError('Positive step limit required')
    prior, count, results = {}, 0, {}
    for case in cases:
        ledger = start(case)
        for index, frame in enumerate(case['steps'], 1):
            path = root / f"{case['id']}-{index}.json"
            receipt = root / f"{case['id']}-{index}.sha256.json"
            if path.exists():
                digest = sha(path.read_bytes())
                if not receipt.exists():
                    ledger.advance(**frame)
                    assert ledger.snapshot() == read(path), 'Orphan checkpoint differs from replay'
                    save(receipt, dict(sha256=digest))
                if read(receipt)['sha256'] != digest:
                    raise ValueError('Checkpoint corruption')
                ledger = ExpiryLedger.restore(read(path))
                prior[path.name] = digest
                continue
            if max_steps is not None and count >= max_steps:
                return dict(complete=False, new_steps=count, reused=len(prior))
            ledger.advance(**frame)
            save(path, ledger.snapshot())
            save(receipt, dict(sha256=sha(path.read_bytes())))
            count += 1
        results[case['id']] = ledger.outcome()
    result = dict(complete=True, cases=results, training_admitted=False)
    if not (root / 'COMPLETE.json').exists():
        save(root / 'COMPLETE.json', result)
    else:
        assert read(root / 'COMPLETE.json') == result
    if prior:
        assert all(sha((root / p).read_bytes()) == digest for p, digest in prior.items())
        name = root / f'RESUME-{len(prior)}.json'
        if not name.exists():
            save(name, dict(restored_checkpoints=len(prior), unchanged=prior, complete=True))
    return result


def decimal_cents(x):
    return int(x.quantize(Decimal('.01'), rounding=ROUND_HALF_EVEN) * 100)


def reconcile(ledger, case):
    """Cash/assets reconciled from economic events, not kernel cash_changes."""
    buys, capacity = 0, {}
    for event in ledger.events:
        if event['kind'] not in ('fill', 'stock_sale'):
            continue
        option = event['kind'] == 'fill'
        price = event['reference']['price'] if option else event['quote']['bid']
        multiplier = case['base']['contracts'][event['contract']]['multiplier'] if option else 1
        gross = Decimal(event['quantity']) * Decimal(str(price)) * Decimal(str(multiplier))
        fee, slip = gross * Decimal('.001'), gross * Decimal('.0005')
        buy = option and event['side'] == 'buy'
        raw = gross + fee + slip if buy else gross - fee - slip
        assert event['cash_cents'] == decimal_cents(raw)
        for field, expected in [('gross', gross), ('fee', fee), ('slippage', slip),
                                ('rounding_residual', Decimal(event['cash_cents']) / 100 - raw)]:
            assert abs(Decimal(str(event[field])) - expected) < Decimal('1e-8')
        if buy:
            buys += event['cash_cents']
        if option:
            key = event['reference']['key']
            capacity[key] = capacity.get(key, 0) + event['quantity']
            assert capacity[key] <= int(Decimal(str(event['reference']['volume'])) / 100)
        else:
            assert event['quantity'] <= int(Decimal(str(event['quote']['bid_size'])) * Decimal(str(event['quote']['size_to_shares'])))
    exercised_net = 0
    for d in ledger.deliveries:
        terms = case['lifecycle']['terms'][d['contract']]
        q = Decimal(d['quantity'])
        strike = decimal_cents(q * Decimal(str(terms['strike_cash_per_contract'])))
        cash = decimal_cents(q * Decimal(str(terms['cash_per_contract'])))
        fee = decimal_cents(q * Decimal(str(case['lifecycle']['exercise_fee'])))
        assert d['shares'] == d['quantity'] * terms['shares_per_contract']
        assert d['debit_cents'] == (strike if d['right'] == 'C' else cash) + fee
        assert d['credit_cents'] == (cash if d['right'] == 'C' else strike)
        assert d['due'].startswith(case['expected']['exercise_due'])
        if d['settled']:
            exercised_net += d['credit_cents'] - d['debit_cents']
    for r in ledger.receivables:
        if r.get('reason') == 'stock_sale':
            assert r['due'].startswith(case['expected']['stock_sale_due'])
    expected_cash = 10_000_000 - buys + exercised_net + sum(r['cents'] for r in ledger.receivables if r['settled'])
    assert expected_cash == ledger.cash
    delivered = sum(d['shares'] * (1 if d['right']=='C' else -1) for d in ledger.deliveries if d['settled'])
    stock_sold = sum(e['quantity'] for e in ledger.events if e['kind']=='stock_sale')
    assert delivered - stock_sold == sum(s['shares'] for s in ledger.stocks.values())


def audit(root):
    cases = prepare(root)
    results, prefixes = {}, 0
    for case in cases:
        ledger = start(case)
        for index, frame in enumerate(case['steps'], 1):
            ledger.advance(**frame)
            path = root / f"{case['id']}-{index}.json"
            assert sha(path.read_bytes()) == read(root / f"{case['id']}-{index}.sha256.json")['sha256']
            assert read(path) == ledger.snapshot(), 'Uninterrupted replay differs'
            reconcile(ledger, case)
            prefixes += 1
        out, expected = ledger.outcome(), case['expected']
        for key in ('status','cash_cents','available_cash_cents','receivable_cents'):
            assert out[key] == expected[key], (case['id'], key)
        assert sum(s['shares'] for s in ledger.stocks.values()) == expected['shares']
        if 'rolled_contract' in expected:
            assert ledger.positions[expected['rolled_contract']]['quantity'] == expected['rolled_quantity']
        results[case['id']] = out
    assert read(root / 'COMPLETE.json') == dict(complete=True,cases=results,training_admitted=False)
    result = dict(schema='etfe-expiry-independent-audit-v1', cases=len(cases), prefixes=prefixes,
                  checks=['manual_expected_outcomes', 'decimal_fills_costs_rounding', 'cash_and_share_conservation',
                          'option_and_quote_capacity', 'dated_settlement_expectations', 'every_saved_prefix'],
                  results=results, training_admitted=False)
    path = root / 'INDEPENDENT_AUDIT.json'
    if not path.exists():
        save(path, result)
    else:
        assert read(path) == result
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['run','audit'])
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--max-steps',type=int)
    args=parser.parse_args()
    root=args.root.resolve()
    if root.parent != ROOT/'nn_meta/validation' or not root.name.startswith('etfe-expiry-components-'):
        parser.error('Isolated ETFE expiry-components root required')
    result=run(root,args.max_steps) if args.command=='run' else audit(root)
    print(json.dumps(result,indent=2))
