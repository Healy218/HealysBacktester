"""Match original cash-amount announcements against the active V7 action inventory."""
from pathlib import Path
import argparse
from collections import defaultdict
import gzip
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import pandas as pd
    from nn_meta.session_calendar import SessionCalendar
    from nn_meta.v7.action_publications import cash_publication
    from nn_meta.v7.storage import verify, sha, identity, receipt, transaction
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('universe', 'dividends', 'news', 'calendar', 'output'):
        parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args()
    verify(args.universe); verify(args.dividends)
    manifest = json.loads((args.news/'acquisition.json').read_text())
    for filename, digest in manifest['sources'].items():
        if sha(filename) != digest:
            raise ValueError('News acquisition source changed')
    inputs = {str(p): sha(p) for p in (args.universe/'complete.json', args.dividends/'complete.json',
               args.news/'acquisition.json', args.calendar, Path(__file__), ROOT/'nn_meta/v7/action_publications.py')}
    calendar = SessionCalendar(json.loads(args.calendar.read_text()))
    membership = pd.read_parquet(args.universe/'membership.parquet')
    symbols = set(membership.loc[membership.month >= '2022-02', 'ticker'])
    actions, grouped, matches = {}, defaultdict(list), {}
    for page in sorted(args.dividends.glob('*.gz')):
        for row in json.loads(gzip.decompress(page.read_bytes()))['results']:
            if row['ticker'] in symbols and '2022-03-15' <= row['ex_dividend_date'] <= '2026-09-14':
                if row['id'] in actions:
                    raise ValueError('Duplicate dividend action identity')
                actions[row['id']] = row
                grouped[row['ticker']].append(row)
    news_ids, article_count = {}, 0
    for query in manifest['requests']['queries']:
        path = args.news/query['id']; doc = verify(path)
        if doc['query']['params']['symbols'] != ','.join(sorted(query['symbols'])):
            raise ValueError('Captured announcement symbols differ')
        inputs[str(path/'complete.json')] = sha(path/'complete.json')
        count = 0
        for page in sorted(path.glob('*.gz')):
            for article in json.loads(gzip.decompress(page.read_bytes()))['news']:
                count += 1
                headline = article.get('headline', '').lower()
                if 'dividend' not in headline and 'distribution' not in headline:
                    continue
                fingerprint = identity(article)
                if article['id'] in news_ids and news_ids[article['id']] != fingerprint:
                    raise ValueError('Conflicting captured versions of an announcement')
                news_ids[article['id']] = fingerprint
                for symbol in article.get('symbols', []):
                    for action in grouped.get(symbol, []):
                        bounds = calendar.bounds(action['ex_dividend_date'])
                        if bounds is None:
                            continue
                        result = cash_publication(action, article, bounds[0].tz_localize('UTC'))
                        if result is not None:
                            result['news_receipt'] = str(path/'complete.json')
                            result['news_receipt_sha256'] = inputs[result['news_receipt']]
                            prior = matches.get(action['id'])
                            if prior is None or pd.Timestamp(result['available_at']) < pd.Timestamp(prior['available_at']):
                                matches[action['id']] = result
        if count != doc['articles']:
            raise ValueError('Captured article count differs')
        article_count += count
    report = dict(candidate_actions=len(actions), matched_original_amounts=len(matches),
                  unmatched_actions=len(actions)-len(matches), capture_article_observations=article_count,
                  unique_dividend_articles=len(news_ids), sources=inputs, research_ready=False,
                  remaining='Security/effective-date/combined-action evidence and unmatched publications remain gated')
    with transaction(args.output) as temp:
        (temp/'amount_publications.json').write_text(json.dumps(list(matches.values()), indent=2)+'\n')
        (temp/'unmatched_actions.json').write_text(json.dumps([r for k,r in actions.items() if k not in matches], indent=2)+'\n')
        (temp/'report.json').write_text(json.dumps(report, indent=2)+'\n')
        if any(sha(p) != digest for p,digest in inputs.items()):
            raise ValueError('Announcement evidence changed during audit')
        receipt(temp, dict(identity=identity(inputs), research_ready=False))
    print(json.dumps({k:v for k,v in report.items() if k!='sources'}))


if __name__ == '__main__': main()
