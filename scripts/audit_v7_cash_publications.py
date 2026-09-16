"""Match full active cash inventory to verified captured headlines and body text."""
from pathlib import Path
import argparse
from collections import Counter, defaultdict
import gzip
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from nn_meta.session_calendar import SessionCalendar
    from nn_meta.v7.action_publications import cash_publication
    from nn_meta.v7.publication_body import cash_body_publication
    from nn_meta.v7.storage import verify, sha, identity, receipt, transaction
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('inventory', 'news', 'calendar', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT/'nn_meta'):
        raise ValueError('Repository artifact disk required')
    verify(args.inventory)
    declaration = json.loads((args.inventory/'declaration.json').read_text())
    inputs = {**declaration['inputs'], **declaration['sources']}
    for path in (args.inventory/'complete.json', args.inventory/'candidates.json', args.calendar,
                 args.news/'acquisition.json', Path(__file__), ROOT/'nn_meta/v7/publication_body.py',
                 ROOT/'nn_meta/v7/action_publications.py', ROOT/'nn_meta/v7/storage.py', ROOT/'nn_meta/session_calendar.py'):
        inputs[str(path)] = sha(path)
    acquisition = json.loads((args.news/'acquisition.json').read_text())
    inputs.update(acquisition['sources'])
    actions = [r['record'] for r in json.loads((args.inventory/'candidates.json').read_text())
               if r['provider'] == 'massive' and r['kind'] == 'dividends']
    grouped = defaultdict(list)
    for action in actions:
        grouped[action['ticker']].append(action)
    calendar = SessionCalendar(json.loads(args.calendar.read_text()))
    seen, matches, body_ids, headline_ids = {}, {}, set(), set()
    observations = 0
    for query in acquisition['requests']['queries']:
        path = args.news/query['id']; document = verify(path)
        if document['query']['params']['symbols'] != ','.join(sorted(query['symbols'])):
            raise ValueError('News query differs from frozen acquisition')
        inputs[str(path/'complete.json')] = sha(path/'complete.json')
        inputs.update({str(path/name): digest for name, digest in document['files'].items()})
        count = 0
        for page in sorted(path.glob('*.gz')):
            for article in json.loads(gzip.decompress(page.read_bytes()))['news']:
                count += 1
                fingerprint = identity(article)
                if article['id'] in seen:
                    if seen[article['id']] != fingerprint:
                        raise ValueError('Conflicting captured article versions')
                    continue
                seen[article['id']] = fingerprint
                if len(article.get('symbols', [])) != 1:
                    continue
                for action in grouped.get(article['symbols'][0], []):
                    bounds = calendar.bounds(action['ex_dividend_date'])
                    if bounds is None:
                        continue
                    effective = bounds[0].tz_localize('UTC')
                    headline = cash_publication(action, article, effective)
                    body = cash_body_publication(action, article, effective)
                    if headline:
                        headline_ids.add(action['id'])
                    if body:
                        body_ids.add(action['id'])
                    match = body or headline
                    if match is None:
                        continue
                    match.setdefault('match_basis', 'headline_amount_only')
                    match.setdefault('original_issuer_document', False)
                    match.update(news_receipt=str(path/'complete.json'),
                        news_receipt_sha256=inputs[str(path/'complete.json')],
                        news_payload=str(page), news_payload_sha256=document['files'][page.name],
                        article_sha256=fingerprint)
                    key = action['id'], article['id']
                    matches[key] = match
        if count != document['articles']:
            raise ValueError('News capture count differs')
        observations += count
    matched = {k[0] for k in matches}
    report = dict(candidate_actions=len(actions), matched_actions=len(matched),
        headline_matched_actions=len(headline_ids), body_matched_actions=len(body_ids),
        additional_body_actions=len(body_ids-headline_ids), unmatched_actions=len(actions)-len(matched),
        publication_records=len(matches), captured_article_observations=observations,
        unique_articles=len(seen), match_bases=dict(Counter(m['match_basis'] for m in matches.values())),
        original_issuer_documents_verified=False, research_ready=False,
        remaining='Full publication coverage, original exceptions, identity and combined/effective semantics remain gated')
    if any(sha(path) != digest for path, digest in inputs.items()):
        raise ValueError('Publication inputs or source changed')
    with transaction(args.output) as temporary:
        for name, value in [('report', report), ('inputs', inputs),
            ('publications', list(matches.values())),
            ('unmatched_actions', [a for a in actions if a['id'] not in matched])]:
            (temporary/(name+'.json')).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
        receipt(temporary, dict(identity=identity(inputs), research_ready=False))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
