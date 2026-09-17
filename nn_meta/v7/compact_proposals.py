"""Lossless typed proposal rows; strategy metadata and policy live in the header."""
from itertools import islice

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from nn_meta.v7.storage import identity

FORMAT = 'v7-compact-proposals-v2'
ROW_FIELDS = {'proposal_id','symbol','variant_id','decision_ns','right','decision_at',
              'exit_decision_at','proposal_closed','signal_minutes','strategy','params',
              'bars_since_previous_signal','simulator_policy','censored_at'}
SCHEMA = pa.schema([
    pa.field('variant_index', pa.uint16(), nullable=False),
    pa.field('decision_ns', pa.int64(), nullable=False),
    pa.field('exit_decision_ns', pa.int64()),
    pa.field('censored_ns', pa.int64()),
    pa.field('is_put', pa.bool_(), nullable=False),
    pa.field('bars_since_previous_signal', pa.uint32(), nullable=False),
    pa.field('symbol', pa.dictionary(pa.int16(), pa.string()), nullable=False),
    pa.field('exit_stock_ticker', pa.dictionary(pa.int16(), pa.string())),
])


def write_proposals(path, rows, declaration, *, row_batch_size=16384, eligibility=None):
    if type(row_batch_size) is not int or row_batch_size < 1:
        raise ValueError('Positive bounded proposal write batch required')
    catalog = declaration['variants']
    if not catalog or len(catalog)>65536 or len({r['variant_id'] for r in catalog})!=len(catalog):
        raise ValueError('Distinct uint16 proposal variant dictionary required')
    positions = {v['variant_id']:i for i,v in enumerate(catalog)}
    routing = declaration['symbols_by_date']
    counts = dict(proposals=0,censored=0,generated=0,excluded_not_member=0)
    # Convert only one bounded slice of Python records at a time. In particular,
    # full-history simulations must not materialize millions of repeated dicts.
    rows = iter(rows)
    with pq.ParquetWriter(path, SCHEMA, compression='zstd', use_dictionary=True) as writer:
        while batch := list(islice(rows, row_batch_size)):
            packed = []
            for row in batch:
                if set(row)!=ROW_FIELDS:
                    raise ValueError('Proposal fields changed; update the compact contract before writing')
                counts['generated'] += 1
                variant = catalog[positions[row['variant_id']]]
                if (row['strategy'] != variant['strategy'] or row['params'] != variant['params']
                        or row['signal_minutes'] != variant['signal_minutes']
                        or row['simulator_policy'] != declaration['simulator_policy']):
                    raise ValueError('Proposal metadata differs from its factorized dictionary')
                decision = pd.Timestamp(row['decision_at'])
                closed = bool(row['proposal_closed'])
                exit_at, censored = pd.Timestamp(row['exit_decision_at']), pd.Timestamp(row['censored_at'])
                if (decision.tzinfo is None or decision.value != row['decision_ns']
                        or (closed and (pd.isna(exit_at) or not pd.isna(censored)))
                        or (not closed and (not pd.isna(exit_at) or pd.isna(censored)))
                        or row['right'] not in ('C','P')):
                    raise ValueError('Invalid proposal clocks or censored state')
                ending = exit_at if closed else censored
                if ending.tzinfo is None or ending < decision:
                    raise ValueError('Proposal horizon precedes its decision')
                gap = row['bars_since_previous_signal']
                if type(gap) is not int or not 0 <= gap < 2**32:
                    raise ValueError('Signal gap cannot be represented without loss')
                symbol, exit_symbol = row['symbol'], None
                if routing is not None:
                    symbol = routing.get(decision.tz_convert('America/New_York').date().isoformat())
                    if closed:
                        exit_symbol = routing.get(exit_at.tz_convert('America/New_York').date().isoformat())
                    if not isinstance(symbol,str) or not symbol or (closed and (not isinstance(exit_symbol,str) or not exit_symbol)):
                        raise ValueError('Proposal lacks exact dated entry/exit stock source')
                expected_id = identity(dict(schema='v7-proposal-v1',symbol=row['symbol'],
                    variant_id=row['variant_id'],decision_ns=row['decision_ns'],right=row['right']))
                if row['proposal_id'] != expected_id:
                    raise ValueError('Proposal identity does not reconstruct exactly')
                if eligibility is not None and not eligibility.admits(row['decision_ns'],symbol):
                    counts['excluded_not_member'] += 1
                    continue
                packed.append(dict(variant_index=positions[row['variant_id']],decision_ns=row['decision_ns'],
                    exit_decision_ns=int(exit_at.value) if closed else None,
                    censored_ns=None if closed else int(censored.value),is_put=row['right']=='P',
                    bars_since_previous_signal=gap,symbol=symbol,exit_stock_ticker=exit_symbol))
                counts['proposals'] += 1
                counts['censored'] += not closed
            if packed:
                writer.write_table(pa.Table.from_pylist(packed,schema=SCHEMA),row_group_size=row_batch_size)
    return counts


def read_proposals(path, declaration, *, batch_size=16384):
    """Reconstruct the exact public proposal fields from bounded Parquet batches."""
    if type(batch_size) is not int or batch_size < 1:
        raise ValueError('Positive bounded proposal read batch required')
    source = pq.ParquetFile(path)
    if not source.schema_arrow.equals(SCHEMA):
        raise ValueError('Compact proposal schema differs')
    variants = declaration['variants']
    timezone = declaration['timezone']
    def stamp(value):
        return None if value is None else pd.Timestamp(value,unit='ns',tz='UTC').tz_convert(timezone).isoformat()
    for batch in source.iter_batches(batch_size=batch_size):
        for compact in batch.to_pylist():
            number = compact['variant_index']
            if number is None or not 0 <= number < len(variants):
                raise ValueError('Foreign proposal variant index')
            variant = variants[number]
            closed = compact['exit_decision_ns'] is not None
            if closed == (compact['censored_ns'] is not None):
                raise ValueError('Invalid compact proposal horizon')
            row = dict(symbol=compact['symbol'],variant_id=variant['variant_id'],
                decision_ns=compact['decision_ns'],right='P' if compact['is_put'] else 'C')
            row = dict(proposal_id=identity(dict(schema='v7-proposal-v1',**row)),**row,
                decision_at=stamp(compact['decision_ns']),exit_decision_at=stamp(compact['exit_decision_ns']),
                exit_decision_ns=compact['exit_decision_ns'],censored_at=stamp(compact['censored_ns']),
                proposal_closed=closed,signal_minutes=variant['signal_minutes'],strategy=variant['strategy'],
                params=dict(variant['params']),bars_since_previous_signal=compact['bars_since_previous_signal'],
                simulator_policy=dict(declaration['simulator_policy']),security_id=declaration['security_id'])
            if declaration['symbols_by_date'] is not None and closed:
                if not compact['exit_stock_ticker']:raise ValueError('Missing dated exit stock ticker')
                row['exit_stock_ticker'] = compact['exit_stock_ticker']
            yield row
