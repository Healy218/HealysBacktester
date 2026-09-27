"""Compact, source-bound historical regular option sessions (no calendar mutation)."""
from bisect import bisect_right
from collections.abc import Mapping
from datetime import date
import json
from pathlib import Path

from nn_meta.session_calendar import SessionCalendar
from nn_meta.v7.execution import CaptureUnavailable
from nn_meta.v7.storage import identity, sha, verify, receipt, transaction

SCHEMA = 'v7-dated-option-hours-v2'
MINUTE = 60_000_000_000


def validate_rules(doc):
    if doc.get('schema') != SCHEMA or doc.get('timezone') != 'America/New_York':
        raise ValueError('Versioned New York option-hours rules required')
    start, end = doc['start'], doc['end']
    if any(date.fromisoformat(d).isoformat() != d for d in (start,end)) or start > end:
        raise ValueError('Exact ordered dated scope required')
    if not doc.get('methodology') or not doc.get('scope_roots') or not doc.get('default_sources'):
        raise ValueError('Explicit finite roots and historical source methodology required')
    roots = doc['scope_roots']
    if roots != sorted(set(roots)) or any(not r.isalnum() or r.upper()!=r for r in roots):
        raise ValueError('Canonical distinct option roots required')
    if doc.get('default_close_extension_minutes') != 0 or doc.get('early_close_extension') != 'same_as_regular':
        raise ValueError('Unsupported regular or early-close policy')
    if not doc.get('early_close_sources') or not doc.get('opening_sources'):
        raise ValueError('Opening and early-close source evidence required')
    for root, rows in doc['exceptions'].items():
        if root not in roots or not rows or rows[0]['start'] != start:
            raise ValueError('Exception must cover its finite root from scope start')
        starts = [r['start'] for r in rows]
        if starts != sorted(set(starts)):
            raise ValueError('Overlapping or unordered historical rules')
        for row in rows:
            if (not start <= row['start'] <= end or date.fromisoformat(row['start']).isoformat()!=row['start']
                    or type(row['extension_minutes']) is not int or row['extension_minutes'] not in (0,15)
                    or not row.get('sources') or not row.get('description')):
                raise ValueError('Unsupported/unbound dated close rule')
    return doc


def source_files(doc):
    result = dict(doc['default_sources'])
    for group in [doc['early_close_sources'],doc['opening_sources'],
                  *(r['sources'] for rows in doc['exceptions'].values() for r in rows)]:
        for path,digest in group.items():
            if path in result and result[path] != digest:
                raise ValueError('Conflicting historical-hour evidence')
            result[path]=digest
    return result


def compile_hours(declaration, calendar, output, *, extra_inputs=None):
    declaration, calendar, output = map(Path,(declaration,calendar,output))
    doc = validate_rules(json.loads(declaration.read_text()))
    cal = json.loads(calendar.read_text())
    SessionCalendar(cal)
    if not cal['coverage_start'] <= doc['start'] <= doc['end'] <= cal['coverage_end']:
        raise ValueError('Captured stock calendar must cover the hours declaration')
    inputs = dict(extra_inputs or {})
    inputs.update(source_files(doc))
    for path in (declaration,calendar,Path(__file__),Path(__file__).parents[1]/'session_calendar.py'):
        inputs[str(path.resolve())]=sha(path)
    if any(sha(p)!=h for p,h in inputs.items()):raise ValueError('Hours evidence changed')
    binding = dict(inputs=inputs,declaration_identity=identity(doc),calendar_identity=identity(cal))
    if output.exists():verify(output,expected_identity=identity(binding));return DatedHours(output)
    with transaction(output) as temp:
        for name,data in [('rules.json',doc),('calendar.json',cal),('binding.json',binding)]:
            (temp/name).write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')
        receipt(temp,dict(identity=identity(binding),schema=SCHEMA,research_ready=False))
    return DatedHours(output)


class _SessionView(Mapping):
    def __init__(self,parent):self.parent=parent
    def __getitem__(self,key):
        try:return self.parent.at(*key)
        except CaptureUnavailable as exc:raise KeyError(key) from exc
    def __iter__(self):
        return ((root,day) for root in sorted(self.parent.roots) for day in self.parent.days)
    def __len__(self):return len(self.parent.roots)*len(self.parent.days)


class DatedHours:
    """DatedOptionSessions-compatible reader; only resolves explicitly scoped roots."""
    def __init__(self,path):
        self.path=Path(path).resolve()
        header=verify(self.path)
        self.rules=validate_rules(json.loads((self.path/'rules.json').read_text()))
        cal=json.loads((self.path/'calendar.json').read_text())
        binding=json.loads((self.path/'binding.json').read_text())
        if (header.get('schema')!=SCHEMA or header['identity']!=identity(binding)
                or binding['declaration_identity']!=identity(self.rules)
                or binding['calendar_identity']!=identity(cal)):
            raise ValueError('Dated hours binding drift')
        self.inputs=dict(binding['inputs'])
        self.inputs[str(self.path/'complete.json')]=sha(self.path/'complete.json')
        self.inputs.update({str(self.path/n):h for n,h in header['files'].items()})
        self.verify_bindings()
        self.calendar=SessionCalendar(cal)
        self.roots=set(self.rules['scope_roots'])
        self.days=sorted(d for d in self.calendar.sessions if self.rules['start']<=d<=self.rules['end'])
        self.starts={r:[row['start'] for row in rows] for r,rows in self.rules['exceptions'].items()}
        self.sessions=_SessionView(self)

    def verify_bindings(self):
        if any(sha(p)!=h for p,h in self.inputs.items()):raise ValueError('Historical hours source changed')

    def at(self,symbol,day):
        symbol=symbol.replace('.','')
        if symbol not in self.roots or not self.rules['start']<=day<=self.rules['end']:
            raise CaptureUnavailable(f'Unreviewed option hours: {symbol} {day}')
        bounds=self.calendar.bounds(day)
        if bounds is None:raise CaptureUnavailable(f'No regular option session on {day}')
        opening,closing=bounds
        ext=0;rule='ordinary-regular-close'
        if symbol in self.starts:
            pos=bisect_right(self.starts[symbol],day)-1
            row=self.rules['exceptions'][symbol][pos]
            ext=row['extension_minutes'];rule=f'{symbol}:{row["start"]}'
        return dict(symbol=symbol,date=day,open_ns=opening.tz_localize('UTC').value,
                    close_ns=closing.tz_localize('UTC').value+ext*MINUTE,rule_id=rule,
                    extension_minutes=ext)

    def cutoff(self,contract):
        from options.data.provider import parse_occ_symbol
        root,expiry,_,_=parse_occ_symbol(contract)
        day=expiry.isoformat()
        if not self.rules['start']<=day<=self.rules['end']:
            raise CaptureUnavailable('Expiry outside dated-hours scope')
        pos=bisect_right(self.days,day)-1
        if pos<0:raise CaptureUnavailable('Expiry precedes dated-hours sessions')
        return self.at(root,self.days[pos])['close_ns']-15*MINUTE
