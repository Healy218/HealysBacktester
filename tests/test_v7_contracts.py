import json
import pytest
from nn_meta.v7.contracts import ContractReferences
from nn_meta.v7.storage import receipt


CONTRACT = 'SPY220311C00420000'


def capture(root, **changes):
    day = '2022-03-07'
    path = root / CONTRACT / day
    path.mkdir(parents=True)
    row = {'ticker': 'O:' + CONTRACT, 'underlying_ticker': 'SPY', 'expiration_date': '2022-03-11',
           'contract_type': 'call', 'strike_price': 420., 'shares_per_contract': 100,
           'exercise_style': 'american', 'primary_exchange': 'XCBO'}
    row.update(changes)
    (path / 'response.json').write_text(json.dumps({'status': 'OK', 'results': row}))
    receipt(path, {'query': {'path': '/v3/reference/options/contracts/O:' + CONTRACT,
                            'params': {'as_of': day}}, 'http_status': 200})
    return ContractReferences(root), path


def test_dated_standard_metadata_is_bound_to_contract_and_immutable(tmp_path):
    refs, path = capture(tmp_path)
    row = refs.standard(CONTRACT, '2022-03-07')
    assert row['strike'] == 420 and row['multiplier'] == 100
    with pytest.raises(TypeError):
        row['multiplier'] = 10
    with pytest.raises(FileNotFoundError):
        refs.standard(CONTRACT, '2022-03-08')
    (path / 'response.json').write_text('{}')
    with pytest.raises(ValueError, match='integrity'):
        ContractReferences(tmp_path).standard(CONTRACT, '2022-03-07')


@pytest.mark.parametrize('changes', [{'shares_per_contract': 10}, {'underlying_ticker': 'QQQ'},
    {'additional_underlyings': [{'amount': 5}]}, {'expiration_date': '2022-03-10'},
    {'strike_price': 421}, {'exercise_style': 'european'}])
def test_adjusted_or_mismatched_deliverables_are_not_standard_contracts(tmp_path, changes):
    refs, _ = capture(tmp_path, **changes)
    with pytest.raises(ValueError, match='standard'):
        refs.standard(CONTRACT, '2022-03-07')
