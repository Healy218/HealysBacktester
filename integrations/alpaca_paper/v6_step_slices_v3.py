"""Continue sell slices; allow only explicitly admitted one-time legacy retries.

Each slice is its own bounded ladder. A fully filled displayed-size slice may
leave real owned contracts; only that successful completion permits another.
The existing bridge rechecks ownership, holdings and pending dependencies.
"""
from integrations.alpaca_paper.v6_pricing_v4 import POLICY
from integrations.alpaca_paper.v6_pricing_v3 import POLICY as LEGACY_POLICY
from integrations.alpaca_paper.v6_bridge_v5 import (
    Journal, events_from_fresh_state, reconcile, stamp, process_events as step_orders,
)


def retry_id(base):
    return base + '|retry|' + POLICY


def process_events(events, *, journal, approved_exit_retries=(), **kwargs):
    approved = set(approved_exit_retries)
    chains = journal.chains()
    routed = []
    for source in events:
        event = dict(source)
        if event['kind'] == 'close':
            base = event['event_id']
            ordinal = 0
            candidate = base
            while candidate in chains:
                chain = chains[candidate]
                if chain['state'] != 'done':
                    break
                if chain.get('remaining') != 0:
                    if candidate not in approved:
                        break
                    if (chain['plan']['execution_policy'] != LEGACY_POLICY or
                            chain['event']['kind'] != 'close' or chain.get('remaining', 0) <= 0 or
                            chain['event']['contract'] != event['contract'] or
                            chain['event']['position_key'] != event['position_key']):
                        raise ValueError('Approved retry does not match exhausted legacy exit')
                    # A stable new ID admits exactly one fresh ladder, never a loop.
                    # The bridge rechecks broker ownership, pending orders and quotes.
                    base = retry_id(candidate)
                    candidate = base
                    ordinal = 0
                    continue
                ordinal += 1
                candidate = base + '|slice|' + str(ordinal)
            event['event_id'] = candidate
        routed.append(event)
    return step_orders(routed, journal=journal, **kwargs)
