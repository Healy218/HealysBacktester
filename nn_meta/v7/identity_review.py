"""Narrow, evidence-bound corrections for captured-but-missing daily identities."""
import json
from pathlib import Path
from nn_meta.v7.storage import verify, sha


def reviewed_overrides(path, *, masters, reference_root, known):
    path = Path(path)
    document = json.loads(path.read_text())
    if document.get('schema') != 'v7-reviewed-identity-boundaries-v1':
        raise ValueError('Unknown identity review schema')
    evidence = Path(document['evidence_path'])
    if sha(evidence) != document['evidence_sha256']:
        raise ValueError('Reviewed identity evidence changed')
    result, sources = {}, {str(path): sha(path), str(evidence): sha(evidence)}
    for row in document['resolutions']:
        root, anchor = row['root'], row['anchor_month_end']
        record = masters[anchor][root]
        if record['composite_figi'] != row['old_figi']:
            raise ValueError('Reviewed identity differs from captured monthly anchor')
        dates = row['dates']
        if (not dates or dates != sorted(set(dates))
                or any(not anchor < d < row['successor_first_trading_date'] for d in dates)):
            raise ValueError('Identity date falls outside the reviewed old-security interval')
        for day in dates:
            key = root, day
            if key in known or key in result:
                raise ValueError('Review cannot replace an existing dated identity')
            capture = Path(reference_root) / root / day
            receipt = verify(capture)
            expected = {'path': '/v3/reference/tickers/' + root, 'params': {'date': day}}
            body = json.loads((capture / 'response.json').read_text()).get('results', {})
            if (receipt.get('query') != expected or receipt.get('http_status') != 200
                    or body.get('ticker') != root or body.get('composite_figi')):
                raise ValueError('Review requires an exact captured response with missing FIGI')
            result[key] = row['old_figi']
            sources[str(capture / 'complete.json')] = sha(capture / 'complete.json')
    return result, sources
