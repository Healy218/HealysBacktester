"""Exact primary-reviewed same-share split terms for funded stock accounting."""
import math

import pandas as pd

from nn_meta.v7.action_inventory import number
from nn_meta.v7.ordinary_actions import price_action


def stock_split_terms(event, calendar):
    """Reject unreviewed ratios, other instruments and non-session clocks."""
    action=price_action(event)
    ratio=number(event.get('new_shares_per_old_share'))
    day=event.get('effective_date')
    bounds=calendar.bounds(day)
    if (event.get('category')!='split' or event.get('admission_basis')!='reviewed_publication'
            or event.get('publication_verified') is not True
            or not event.get('review_identity') or not event.get('evidence_identity')
            or event.get('review_identity')!=action.source_identity
            or action.event_id!='reviewed-split:'+event['review_identity']
            or not event.get('security_id') or not event.get('symbol')
            or ratio<=1 or ratio!=ratio.to_integral_value() or not math.isfinite(float(ratio))
            or action.price_factor!=1/float(ratio) or action.volume_factor!=float(ratio)
            or event.get('cash_amount') is not None or event.get('cash_units') is not None
            or bounds is None or action.effective_at!=bounds[0].tz_localize('UTC')
            or pd.Timestamp(event.get('publication_available_at'))!=action.available_at):
        raise ValueError('Exact reviewed same-share split at its captured session open required')
    return action.event_id,action.effective_at.value,float(ratio)
