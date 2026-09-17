import pandas as pd
import pytest

from nn_meta.v7.source_routes import compile_routes
from nn_meta.v7.security_history import security_history
from tests.test_v7_security_history import fixture


def inputs():
    stock, clock = fixture()
    overlap = stock.iloc[[2]].copy()
    overlap['stock_ticker'] = 'OLD'
    stock = pd.concat([stock, overlap], ignore_index=True)
    aliases = pd.DataFrame(columns=['membership_ticker', 'date', 'stock_ticker',
        'security_id', 'observed_minutes', 'action_id', 'stock_receipt', 'identity_receipt'])
    review = dict(kind='same_security_listing_transfer', date='2022-03-17',
        old_symbol='OLD', stock_ticker='NEW', security_id='security',
        stock_receipt='stock', identity_receipt='identities',
        evidence=[dict(publication_available_at='2022-03-17T12:00Z')])
    return aliases, review, stock, clock


def test_compiled_route_is_consumed_without_changing_prefix_or_raw_observations():
    aliases, review, stock, clock = inputs()
    routes = compile_routes(aliases, [review], stock, stock)
    overrides = [dict(source_date=r.date, stock_ticker=r.stock_ticker,
        security_id=r.security_id, evidence_identity=r.action_id) for r in routes.itertuples()]
    resolved = security_history(stock, clock, security_id='security', source_overrides=overrides)
    unresolved = security_history(stock, clock, security_id='security')
    pd.testing.assert_frame_equal(resolved.iloc[:2], unresolved.iloc[:2])
    assert resolved.identity_span.nunique() == 1
    assert resolved.stock_ticker.tolist() == ['OLD', 'OLD', 'NEW', 'NEW']
    assert resolved.raw_close.tolist() == [100., 101., 102., 103.]
    assert resolved.listed_source_candidates.iloc[2] == 2
    assert resolved.source_selection_evidence.iloc[2].startswith('reviewed-route:')


@pytest.mark.parametrize('change', ['foreign_identity', 'missing_identity', 'late_publication',
    'naive_publication', 'missing_publication', 'no_observations', 'missing_listing',
    'duplicate_review', 'existing_route', 'duplicate_stock'])
def test_route_rejects_unsupported_or_colliding_evidence(change):
    aliases, review, stock, _ = inputs()
    panel = stock.copy()
    reviews = [review]
    if change == 'foreign_identity':
        panel.loc[panel.stock_ticker.eq('OLD'), 'listed_security_id'] = 'other'
    if change == 'missing_identity':
        panel.loc[panel.stock_ticker.eq('OLD'), 'listed_security_id'] = pd.NA
    if change == 'late_publication':
        review['evidence'][0]['publication_available_at'] = '2022-03-17T14:00Z'
    if change == 'naive_publication':
        review['evidence'][0]['publication_available_at'] = '2022-03-17T12:00'
    if change == 'missing_publication':
        review['evidence'] = []
    if change == 'no_observations':
        stock.loc[stock.stock_ticker.eq('NEW'), 'observed_minutes'] = 0
    if change == 'missing_listing':
        panel = panel[panel.stock_ticker.ne('OLD')]
    if change == 'duplicate_review':
        reviews *= 2
    if change == 'existing_route':
        aliases = compile_routes(aliases, [review], stock, stock)
    if change == 'duplicate_stock':
        stock = pd.concat([stock, stock.iloc[:1]])
    with pytest.raises(ValueError):
        compile_routes(aliases, reviews, panel, stock)
