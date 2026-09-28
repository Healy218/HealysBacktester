"""Continue successfully filled sell liquidity slices without restarting failures.

Each slice is its own bounded ladder. A fully filled displayed-size slice may
leave real owned contracts; only that successful completion permits another.
The existing bridge rechecks ownership, holdings and pending dependencies.
"""
from integrations.alpaca_paper.v6_bridge_v3 import (
    Journal, events_from_fresh_state, reconcile, stamp, process_events as step_orders,
)


def process_events(events, *, journal, **kwargs):
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
                if chain['state'] != 'done' or chain.get('remaining') != 0:
                    break
                ordinal += 1
                candidate = base + '|slice|' + str(ordinal)
            event['event_id'] = candidate
        routed.append(event)
    return step_orders(routed, journal=journal, **kwargs)
