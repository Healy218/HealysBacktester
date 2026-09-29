#!/usr/bin/env python3
"""Measure exact entry-selection impact of captured, unadmitted references."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ['audit', 'entry-audit', 'review', 'output']:
        parser.add_argument('--' + key, type=Path, required=True)
    args = parser.parse_args()
    from nn_meta.v7.storage import verify, sha, identity, transaction, receipt
    import pandas as pd
    inputs = {str(Path(__file__).resolve()): sha(__file__)}
    for path in [args.audit, args.entry_audit, args.review]:
        verify(path)
        inputs[str((path / 'complete.json').resolve())] = sha(path / 'complete.json')
    parent = json.loads((args.entry_audit / 'binding.json').read_text())
    census = json.loads((args.entry_audit / 'report.json').read_text())
    reviewed = {(r['contract'], r['date']) for r in json.loads((args.review / 'entries.json').read_text())}
    failures = sqlite3.connect((args.audit / 'coverage.sqlite3').resolve().as_uri() + '?mode=ro', uri=True)
    totals, dates = Counter(), Counter()
    with transaction(args.output) as temp:
        with sqlite3.connect(temp / 'impact.sqlite3') as out:
            out.executescript('''CREATE TABLE pairs(security_id,contract,date,disposition,selection_rows,proposal_target_rows,
                PRIMARY KEY(security_id,contract,date)) WITHOUT ROWID;
                CREATE TABLE securities(security_id PRIMARY KEY, affected_selection_rows, affected_proposals,
                affected_proposal_target_rows);''')
            for sid in parent['securities']:
                rows = []
                for contract, day, status in failures.execute(
                        'SELECT contract,date,admission FROM observed WHERE security_id=? AND admission NOT IN ("standard","approved_blackout")', (sid,)):
                    if (contract, day) in reviewed:
                        totals['reviewed_rename_pairs'] += 1
                        continue
                    lower = pd.Timestamp(day, tz='America/New_York')
                    upper = lower + pd.DateOffset(days=1)
                    rows.append((contract, day, status, int(lower.value), int(upper.value)))
                    dates[day] += 1
                if not rows:
                    continue
                source = Path(parent['demand_root']) / 'demand' / sid
                anchor = str(source / 'complete.json')
                if sha(anchor) != census['inputs'][anchor]:
                    raise ValueError('Frozen entry demand changed')
                verify(source)
                inputs[anchor] = sha(anchor)
                with sqlite3.connect((source / 'demand.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
                    db.execute('PRAGMA cache_size=-4096')
                    db.execute('CREATE TEMP TABLE failures(contract,date,disposition,lo,hi, PRIMARY KEY(contract,date)) WITHOUT ROWID')
                    db.executemany('INSERT INTO failures VALUES(?,?,?,?,?)', rows)
                    db.execute('CREATE TEMP TABLE affected AS SELECT s.*,f.date,f.disposition FROM selections s JOIN failures f '
                               'ON s.contract=f.contract AND s.decision_ns>=f.lo AND s.decision_ns<f.hi WHERE s.status="selected"')
                    db.execute('CREATE TEMP TABLE weights AS SELECT symbol,decision_ns,right,SUM(proposals) AS n FROM decisions '
                               'WHERE (symbol,decision_ns,right) IN (SELECT symbol,decision_ns,right FROM affected) GROUP BY symbol,decision_ns,right')
                    pairs = {(c,d): (n,p) for c,d,n,p in db.execute('SELECT a.contract,a.date,COUNT(*),SUM(w.n) FROM affected a '
                             'JOIN weights w USING(symbol,decision_ns,right) GROUP BY a.contract,a.date')}
                    selected = db.execute('SELECT COUNT(*) FROM affected').fetchone()[0]
                    proposals = db.execute('SELECT COALESCE(SUM(n),0) FROM weights').fetchone()[0]
                    expanded = sum(p for n,p in pairs.values())
                    out.execute('INSERT INTO securities VALUES(?,?,?,?)', (sid,selected,proposals,expanded))
                    for c,d,status,lo,hi in rows:
                        n,p = pairs.get((c,d),(0,0))
                        out.execute('INSERT INTO pairs VALUES(?,?,?,?,?,?)', (sid,c,d,status,n,p))
                        totals[status + '_pairs'] += 1
                    totals.update(affected_securities=1, affected_selection_rows=selected,
                                  affected_proposals=proposals, affected_proposal_target_rows=expanded)
                out.commit()
                print(json.dumps(dict(security_id=sid, affected_securities=totals['affected_securities'])), flush=True)
        report = dict(schema='v7-reference-entry-impact-v1', counts=dict(totals), failures_by_date=dict(sorted(dates.items())),
                      measured_at=datetime.now(timezone.utc).isoformat(), scope='Entry selections only; held crossings are measured by execution discovery.',
                      exclusions_authorized=False, reference_admission_complete=False, full_execution_coverage=False, research_ready=False)
        if any(sha(path) != digest for path,digest in inputs.items()):
            raise ValueError('Impact source changed')
        binding = dict(inputs=inputs)
        for name, doc in [('binding.json',binding),('report.json',report)]:
            (temp / name).write_text(json.dumps(doc, sort_keys=True, indent=2) + '\n')
        receipt(temp, dict(identity=identity(binding), research_ready=False))
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
