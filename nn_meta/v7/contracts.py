"""Bind dated standard equity-option deliverables before a V7 purchase or mark."""
from functools import lru_cache
import json
from pathlib import Path
from types import MappingProxyType

from nn_meta.v7.storage import verify, sha
from options.data.provider import parse_occ_symbol


class ContractReferences:
    def __init__(self, root):
        self.root = Path(root)

    @lru_cache(maxsize=4096)
    def standard(self, contract, day):
        contract = contract.removeprefix('O:')
        root, expiry, right, strike = parse_occ_symbol(contract)
        path = self.root / contract / day
        receipt = verify(path)
        expected = {'path': '/v3/reference/options/contracts/O:' + contract, 'params': {'as_of': day}}
        if receipt.get('query') != expected or receipt.get('http_status') != 200:
            raise ValueError('Dated contract metadata is unavailable or has a different scope')
        body = json.loads((path / 'response.json').read_text())
        row = body.get('results', {})
        if (body.get('status') != 'OK' or row.get('ticker') != 'O:' + contract
                or str(row.get('underlying_ticker', '')).replace('.', '') != root or row.get('expiration_date') != expiry.isoformat()
                or row.get('contract_type') != ('call' if right == 'C' else 'put')
                or row.get('strike_price') != strike or row.get('shares_per_contract') != 100
                or row.get('exercise_style') != 'american' or row.get('additional_underlyings')
                or not row.get('primary_exchange')):
            raise ValueError('Contract is not the verified standard 100-share American instrument')
        return MappingProxyType({'contract': contract, 'date': day, 'underlying': root, 'expiry': expiry,
                'right': right, 'strike': strike, 'multiplier': 100,
                'metadata_receipt_sha256': sha(path / 'complete.json')})
