"""Date reviewed noncash exclusions using prior issuer and exact listing evidence."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    from bs4 import BeautifulSoup
    from nn_meta.v7.listed_evidence import ListedEvidence
    from nn_meta.v7.storage import identity, receipt, sha, transaction, verify

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--noncash', type=Path, required=True)
    parser.add_argument('--reviews', type=Path, required=True)
    parser.add_argument('--listed-captures', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT / 'nn_meta'):
        raise ValueError('Repository artifact disk required')
    parent = verify(args.noncash)
    source = json.loads(args.reviews.read_text())
    if (source.get('schema') != 'v7-reviewed-noncash-effective-dates-v1'
            or not source.get('reviews') or len({r['old_symbol'] for r in source['reviews']})
            != len(source['reviews'])):
        raise ValueError('Finite unique reviewed noncash dates required')
    inputs = {str(args.noncash / 'complete.json'): sha(args.noncash / 'complete.json'),
              str(args.reviews): sha(args.reviews), str(Path(__file__)): sha(__file__)}
    inputs.update({str(args.noncash / name): digest for name, digest in parent['files'].items()})
    reader = ListedEvidence(args.listed_captures)
    treatments = deepcopy(json.loads((args.noncash / 'treatments.json').read_text()))
    changes = []
    for review in source['reviews']:
        if (review.get('conclusion') != 'admit_selected_history_before_boundary_only'
                or date.fromisoformat(review['publication_date']) >=
                    date.fromisoformat(review['effective_date'])):
            raise ValueError('Prior published date and conservative conclusion required')
        matching = [t for t in treatments if t['kind'] == 'name_changes'
                    and t['scoped_symbols'] == [review['old_symbol']]
                    and t['effective_date'] is None]
        if len(matching) != 1:
            raise ValueError('Exactly one undated original treatment required')
        old = matching[0]
        notice = ROOT / review['notice']
        doc = verify(notice)
        if not doc['final_url'].startswith('https://'):
            raise ValueError('Published issuer notice URL required')
        inputs[str(notice / 'complete.json')] = sha(notice / 'complete.json')
        inputs.update({str(notice / name): digest for name, digest in doc['files'].items()})
        plain = BeautifulSoup((notice / 'response.bin').read_bytes(), 'html.parser').get_text(' ', strip=True)
        normalized = lambda s: re.sub(r'\s+', ' ', s).casefold()
        if normalized(review['notice_phrase']) not in normalized(plain):
            raise ValueError('Published effective-date phrase absent')
        before = reader.record(review['old_symbol'], review['prior_date'])
        after = reader.record(review['new_symbol'], review['effective_date'])
        if (not before or not after or review['prior_date'] >= review['effective_date']
                or any(row.get('composite_figi') != review['security_id'] for row in (before, after))
                or not before.get('share_class_figi')
                or before['share_class_figi'] != after.get('share_class_figi')
                or before.get('type') != 'CS' or after.get('type') != 'CS'
                or before.get('active') is not True or after.get('active') is not True):
            raise ValueError('Exact same-share listed boundary required')
        proof = dict(review=review, original_treatment=old['review_identity'],
                     notice_receipt=sha(notice / 'complete.json'),
                     prior_listing_identity=identity(before), effective_listing_identity=identity(after),
                     exclusion_starts=review['effective_date'],
                     held_position_treatment='reject_crossing_position')
        old['effective_date'] = review['effective_date']
        old['review_identity'] = identity(proof)
        old['boundary_review'] = proof
        old['rationale'] = ('Issuer notice published before the exact same-share listed ticker change; '
                            'admit only selected history before that date. Exclude the boundary and '
                            'all later dates; reject held positions crossing it.')
        changes.append(proof)
    inputs.update(reader.inputs)
    if any(sha(path) != digest for path, digest in inputs.items()):
        raise ValueError('Noncash date review input changed')
    with transaction(args.output) as temp:
        (temp / 'treatments.json').write_text(json.dumps(treatments, indent=2) + '\n')
        (temp / 'reviews.json').write_text(json.dumps(changes, indent=2) + '\n')
        (temp / 'inputs.json').write_text(json.dumps(inputs, indent=2) + '\n')
        (temp / 'report.json').write_text(json.dumps(dict(
            original_records=len(treatments), dated_boundaries=len(changes),
            held_position_admitted=False, research_ready=False), indent=2) + '\n')
        if any(sha(path) != digest for path, digest in inputs.items()):
            raise ValueError('Noncash date review input changed during sealing')
        receipt(temp, dict(identity=identity(inputs), research_ready=False))
    print(json.dumps(dict(original_records=len(treatments), dated_boundaries=len(changes))))


if __name__ == '__main__':
    main()
