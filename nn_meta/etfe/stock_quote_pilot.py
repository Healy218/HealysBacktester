"""Finite quote windows and lossless diagnostic normalization, without size admission."""
from collections import Counter
from io import BytesIO
import json
import math
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from nn_meta.etfe import stock_quote_capture as q
from nn_meta.etfe.expansion import read_calendar

DAYS = ('2024-01-19', '2024-11-29', '2025-04-04', '2025-10-31', '2025-11-03', '2026-10-02')
SCHEMA = pa.schema([
    ('occurrence_id', pa.string()), ('symbol', pa.string()), ('timestamp_ns', pa.int64()),
    ('timestamp_raw', pa.string()), ('bid', pa.float64()), ('ask', pa.float64()),
    ('bid_size_raw', pa.string()), ('ask_size_raw', pa.string()),
    ('bid_size_shares', pa.int64()), ('ask_size_shares', pa.int64()),
    ('size_unit_status', pa.string()), ('diagnostic_mid', pa.float64()),
    ('quality_flags', pa.list_(pa.string())), ('raw_json', pa.string()),
    ('job_id', pa.string()), ('page', pa.int32()), ('ordinal', pa.int32()),
    ('body_sha256', pa.string()), ('received_at', pa.string())])


def jobs(calendar):
    sessions = {s['date']:s for s in calendar}
    result = []
    for day in DAYS:
        session = sessions[day]
        opening = pd.Timestamp(day+' '+session['open'], tz='America/New_York')
        closing = pd.Timestamp(day+' '+session['close'], tz='America/New_York')
        for name, anchor in [('open', opening), ('stock_close_minus_15', closing-pd.Timedelta(minutes=15)),
                             ('stock_close', closing)]:
            start = (anchor-pd.Timedelta(seconds=30)).tz_convert('UTC')
            end = (anchor+pd.Timedelta(minutes=2)-pd.Timedelta(nanoseconds=1)).tz_convert('UTC')
            for symbol in q.SYMBOLS:
                result.append(q.job('stock_quotes', dict(symbols=symbol, start=start.isoformat(),
                    end=end.isoformat(), feed='sip', asof='-', sort='asc', limit=10000),
                    f'quote_density:{day}:{name}:{symbol}'))
    return result


def prepare(root, calendar_root):
    calendar_root = Path(calendar_root).resolve()
    return q.prepare(root, jobs(read_calendar(calendar_root)), parent=dict(
        calendar_root=str(calendar_root), calendar_sha256=q.sha((calendar_root/'CALENDAR.json').read_bytes()),
        study='six_day_stock_quote_density', option_class_cutoffs_admitted=False,
        quote_size_shares_admitted=False, official_exercise_reference_admitted=False))


def verify(root):
    plan = q.load_plan(root)
    parent = plan['parent']
    calendar_root = Path(parent['calendar_root'])
    if q.sha((calendar_root/'CALENDAR.json').read_bytes()) != parent['calendar_sha256']:
        raise ValueError('Quote calendar changed')
    if plan['jobs'] != jobs(read_calendar(calendar_root)):
        raise ValueError('Quote pilot windows changed')
    return plan


def typed(symbol, raw, item, page, ordinal, receipt, plan_sha):
    flags = []
    def price(field):
        try:
            value = float(raw[field])
            if isinstance(raw[field], bool) or not math.isfinite(value) or value <= 0:
                raise ValueError()
            return value
        except (ValueError, TypeError, OverflowError):
            flags.append('invalid_'+field)
            return None
    bid, ask = price('bp'), price('ap')
    for field in ('bs', 'as'):
        try:
            value = Decimal(str(raw[field]))
            if not value.is_finite() or value <= 0 or value != value.to_integral_value() or not math.isfinite(float(value)):
                raise ValueError()
        except (ValueError, TypeError, OverflowError, InvalidOperation):
            flags.append('invalid_'+field)
    if bid is not None and ask is not None and bid > ask:
        flags.append('crossed_quote')
    return dict(occurrence_id=q.digest([plan_sha, item['id'], page, ordinal]), symbol=symbol,
        timestamp_ns=pd.Timestamp(raw['t']).value, timestamp_raw=raw['t'], bid=bid, ask=ask,
        bid_size_raw=json.dumps(raw['bs']), ask_size_raw=json.dumps(raw['as']),
        bid_size_shares=None, ask_size_shares=None, size_unit_status='historical_representation_unverified',
        diagnostic_mid=(bid+ask)/2 if not flags else None, quality_flags=flags,
        raw_json=json.dumps(raw, sort_keys=True, separators=(',', ':')), job_id=item['id'],
        page=page, ordinal=ordinal, body_sha256=receipt['body_sha256'], received_at=receipt['received_at'])


def normalize(root):
    root = Path(root)
    plan = verify(root)
    output = root/'normalized'
    output.mkdir(exist_ok=True)
    receipts, windows, total, payload = {}, [], 0, 0
    for item in plan['jobs']:
        history, _, complete = q.committed(root, item)
        if not complete:
            raise ValueError('Complete quote transport required before normalization')
        count = raw_bytes = 0
        for page, (receipt, body, _) in enumerate(history):
            q.guard(root, plan['limits'])
            records = [typed(symbol, raw, item, page, ordinal, receipt, plan['sha256'])
                       for ordinal, (symbol, raw) in enumerate(q.rows(body, item))]
            buffer = BytesIO()
            pq.write_table(pa.Table.from_pylist(records, schema=SCHEMA), buffer, compression='zstd')
            data = buffer.getvalue()
            key = f'{item["id"]}-{page:06d}'
            target = output/(key+'.parquet')
            if target.exists():
                if q.sha(target.read_bytes()) != q.sha(data):
                    raise ValueError('Quote normalized payload changed')
            else:
                q.write_new(target, data)
            meta = dict(data=str(target.relative_to(root)), sha256=q.sha(data), rows=len(records),
                        job_id=item['id'], page=page, body_sha256=receipt['body_sha256'])
            pointer = output/(key+'.json')
            if pointer.exists():
                if json.loads(pointer.read_text()) != meta:
                    raise ValueError('Quote normalized receipt changed')
            else:
                q.save(pointer, meta)
            receipts[key] = q.sha(pointer.read_bytes())
            count += len(records)
            raw_bytes += receipt['bytes']
        minutes = (pd.Timestamp(item['params']['end'])+pd.Timedelta(nanoseconds=1)-pd.Timestamp(item['params']['start'])).total_seconds()/60
        windows.append(dict(job_id=item['id'], purpose=item['purpose'], symbol=item['params']['symbols'],
            rows=count, payload_bytes=raw_bytes, pages=len(history), minutes=minutes,
            rows_per_minute=count/minutes, disposition='observed' if count else 'empty_unresolved'))
        total += count
        payload += raw_bytes
    report = dict(schema='etfe-stock-quote-diagnostics-v1', plan_sha256=plan['sha256'],
        rows=total, raw_payload_bytes=payload, page_receipts=receipts, windows=windows,
        shares_conversion_admitted=False, official_exercise_reference_admitted=False,
        ready_for_build=False, ready_for_training=False)
    seal = root/'NORMALIZED.json'
    if seal.exists():
        if json.loads(seal.read_text()) != report:
            raise ValueError('Quote normalization seal changed')
    else:
        q.save(seal, report)
    return report


def audit(root):
    root = Path(root)
    plan = verify(root)
    report = json.loads((root/'NORMALIZED.json').read_text())
    if report['plan_sha256'] != plan['sha256']:
        raise ValueError('Quote normalization binding changed')
    count = 0
    flags = Counter()
    seen = set()
    for item in plan['jobs']:
        history, _, complete = q.committed(root, item)
        if not complete:
            raise ValueError('Incomplete quote capture')
        for page, (receipt, body, _) in enumerate(history):
            key = f'{item["id"]}-{page:06d}'
            seen.add(key)
            path = root/'normalized'/(key+'.json')
            if q.sha(path.read_bytes()) != report['page_receipts'][key]:
                raise ValueError('Quote page receipt changed')
            meta = json.loads(path.read_text())
            data = root/meta['data']
            if q.sha(data.read_bytes()) != meta['sha256']:
                raise ValueError('Quote parquet changed')
            actual = pq.read_table(data).to_pylist()
            expected = list(q.rows(body, item))
            if len(actual) != len(expected) or len(actual) != meta['rows']:
                raise ValueError('Quote row count changed')
            for ordinal, (row, (symbol, raw)) in enumerate(zip(actual, expected)):
                # Independent source/sequence/time/raw-size check; no shares conversion.
                if (row['symbol'] != symbol or json.loads(row['raw_json']) != raw or
                    row['timestamp_ns'] != pd.Timestamp(raw['t']).value or
                    row['timestamp_raw'] != raw['t'] or row['ordinal'] != ordinal or
                    row['page'] != page or row['job_id'] != item['id'] or
                    row['body_sha256'] != receipt['body_sha256'] or
                    row['received_at'] != receipt['received_at'] or
                    row['occurrence_id'] != q.digest([plan['sha256'], item['id'], page, ordinal]) or
                    json.loads(row['bid_size_raw']) != raw['bs'] or json.loads(row['ask_size_raw']) != raw['as'] or
                    row['bid_size_shares'] is not None or row['ask_size_shares'] is not None):
                    raise ValueError('Quote occurrence/size audit failed')
                flags.update(row['quality_flags'])
                values, expected_flags = {}, []
                for field in ('bp', 'ap', 'bs', 'as'):
                    try:
                        value = Decimal(str(raw[field]))
                        if not value.is_finite() or value <= 0 or not math.isfinite(float(value)):
                            raise ValueError()
                        if field in ('bs', 'as') and value != value.to_integral_value():
                            raise ValueError()
                        values[field] = value
                    except (ValueError, InvalidOperation, OverflowError):
                        expected_flags.append('invalid_'+field)
                        values[field] = None
                if values['bp'] is not None and values['ap'] is not None and values['bp'] > values['ap']:
                    expected_flags.append('crossed_quote')
                midpoint = float((values['bp']+values['ap'])/2) if not expected_flags else None
                if (row['quality_flags'] != expected_flags or
                    row['bid'] != (float(values['bp']) if values['bp'] is not None else None) or
                    row['ask'] != (float(values['ap']) if values['ap'] is not None else None) or
                    row['size_unit_status'] != 'historical_representation_unverified' or
                    (row['diagnostic_mid'] is None) != (midpoint is None) or
                    (midpoint is not None and not math.isclose(row['diagnostic_mid'], midpoint, rel_tol=1e-12, abs_tol=1e-12))):
                    raise ValueError('Quote numeric audit failed')
            count += len(actual)
    if seen != set(report['page_receipts']) or count != report['rows']:
        raise ValueError('Quote normalized census mismatch')
    return dict(plan_sha256=plan['sha256'], rows=count, pages=len(seen), raw_occurrences_preserved=True,
        quality_counts=dict(flags), shares_conversion_admitted=False, ready_for_build=False,
        audit_source_sha256=q.sha(Path(__file__).read_bytes()))
