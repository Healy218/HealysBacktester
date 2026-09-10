"""Replay saved underlying policy for user-confirmed trades; notifications only."""
from datetime import datetime, timezone, timedelta
import json


def evaluate(context, bars, now):
    """Use closed trade status, never mistake vectorbt's open mark for an exit."""
    import pandas as pd
    from nn_meta import proposals
    from nn_meta.live.scanner import closed_bars, require_recent_bars
    from portfolio.simulator import run_backtest
    from utils.runner_utils import sim_kwargs
    bars = require_recent_bars(closed_bars(bars, now), now)
    start, entry = pd.Timestamp(context['sim_start']), pd.Timestamp(context['entry_ts'])
    oldest_allowed = start + pd.Timedelta(days=7) if context.get('warmup_date_only') else start
    if bars.index[0] > oldest_allowed or entry not in bars.index:
        raise ValueError('Missing entry/warmup history; exit cannot be verified.')
    bars = bars.loc[start:]
    entry_close = float(bars.loc[entry, 'Close'])
    tolerance = .005001 if context.get('entry_spot_rounded') else max(.0001, abs(context['spot']) * .00001)
    if abs(entry_close - context['spot']) > tolerance:
        raise ValueError('Entry bar changed since the alert; exit cannot be verified.')
    # Legacy messages printed two decimal places; replay still uses the
    # original bar's full precision, including its stop reference.
    context = dict(context, spot=entry_close)
    signals = proposals.single_signals(context['strategy'], bars, context['params'])
    pf = run_backtest(price_df=bars, entries_series=signals[0], exits_series=signals[1],
                      short_entries_series=signals[2], short_exits_series=signals[3],
                      frequency='15min', **sim_kwargs(context['sim_config']))
    if pf is None:
        raise ValueError('Strategy replay failed.')
    columns = pf.wrapper.columns
    single = pf[columns[0]] if len(columns) else pf
    records = single.trades.records
    records = records if isinstance(records, pd.DataFrame) else pd.DataFrame(single.trades.records_arr)
    matches = [r for r in records.itertuples() if pd.Timestamp(single.wrapper.index[int(r.entry_idx)]) == entry and int(r.direction) == context['direction']]
    if len(matches) != 1:
        raise ValueError('Original entry could not be reproduced; exit cannot be verified.')
    trade = matches[0]
    if int(trade.status) == 0:  # Open: exit_idx is only its latest mark.
        return None, str(bars.index[-1])
    stamp = pd.Timestamp(single.wrapper.index[int(trade.exit_idx)])
    bar = bars.loc[stamp]
    cfg = context['sim_config']
    reason = 'strategy exit / opposite signal'
    fraction = cfg.get('STOP_LOSS_PERCENT')
    if cfg.get('USE_STOP_LOSS') and fraction and not cfg.get('ATR_SL_WINDOW'):
        level = context['spot'] * (1 + fraction if context['direction'] else 1 - fraction)
        hit = bar['High'] >= level if context['direction'] else bar['Low'] <= level
        if hit:
            reason = f'underlying stop ${level:,.2f}'
    return dict(reason=reason, bar=str(stamp), stock_close=float(bar['Close'])), str(bars.index[-1])


def scan(queue, expert, loader, now=None, evaluator=evaluate, quote_loader=None):
    """Persist trigger before sending; a retry never loses a detected exit."""
    now = now or datetime.now(timezone.utc)
    with queue.connect() as db:
        rows = db.execute("SELECT * FROM taken_trades WHERE status='open'").fetchall()
    checked = 0
    for row in rows:
        ctx = json.loads(row['context'])
        if ctx['expert'] != expert:
            continue
        try:
            bars = loader(ctx, now)
            from nn_meta.live.scanner import closed_bars, require_recent_bars
            bars = require_recent_bars(closed_bars(bars, now), now)
            if row['last_checked'] == str(bars.index[-1]):
                continue
            event, latest = evaluator(ctx, bars, now)
            # A held contract requires a user decision at expiry, not an
            # automatic book entry in a replacement option.
            if event is None:
                from options.data.provider import parse_occ_symbol
                expiry = parse_occ_symbol(ctx['contract'])[1]
                et = now.astimezone(__import__('zoneinfo').ZoneInfo('America/New_York'))
                if expiry < et.date() or (expiry == et.date() and (et.hour, et.minute) >= (15, 45)):
                    event = dict(reason='contract expiry — close or roll the option', bar=str(bars.index[-1]), stock_close=float(bars['Close'].iloc[-1]))
            notice = None
            if event:
                from nn_meta.live.scanner import alert_quote
                from nn_meta.live.feeds.quotes import contract_lines
                q = (quote_loader or alert_quote)(ctx['contract'])
                from nn_meta.live.broker_fees import quote_pnl_line
                pnl = quote_pnl_line(ctx, row['quantity'], row['fill_price'], q, now)
                notice = (f"🔴 SELL WATCH — [{expert}] {ctx['symbol']}\n"
                          + contract_lines(ctx['contract'], q, '')
                          + f"\nexit: {event['reason']}\nbar: {event['bar']} UTC · spot ${event['stock_close']:,.2f}"
                          + ('\n' + pnl if pnl else '')
                          + f"\nTrade ID: {row['id']}\nAfter closing: /sold {row['id']}")
            with queue.connect() as db:
                if notice:
                    db.execute("UPDATE taken_trades SET status='exit_due',exit_notice=?,notice_sent=0,last_checked=?,monitor_error=NULL,monitor_error_sent=0 WHERE id=? AND status='open'", (notice, latest, row['id']))
                else:
                    db.execute("UPDATE taken_trades SET last_checked=?,monitor_error=NULL,monitor_error_sent=0 WHERE id=? AND status='open'", (latest, row['id']))
            checked += 1
        except Exception as exc:
            # Store a bounded operational error; never make up an exit.
            with queue.connect() as db:
                db.execute("UPDATE taken_trades SET monitor_error=? WHERE id=? AND status='open'", (f'{type(exc).__name__}: exit check failed', row['id']))
    return checked


def send_pending(queue, api):
    with queue.connect() as db:
        pending = db.execute("SELECT id FROM taken_trades WHERE status='exit_due' AND notice_sent=0").fetchall()
    for item in pending:
        with queue.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT * FROM taken_trades WHERE id=? AND status='exit_due' AND notice_sent=0", (item['id'],)).fetchone()
            if row:
                api.call('sendMessage', chat_id=api.chat, text=row['exit_notice'])
                db.execute('UPDATE taken_trades SET notice_sent=1 WHERE id=?', (row['id'],))


    with queue.connect() as db:
        errors = db.execute("SELECT id FROM taken_trades WHERE status='open' AND monitor_error IS NOT NULL AND monitor_error_sent=0").fetchall()
    for item in errors:
        with queue.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT * FROM taken_trades WHERE id=? AND status='open' AND monitor_error IS NOT NULL AND monitor_error_sent=0", (item['id'],)).fetchone()
            if row:
                ctx = json.loads(row['context'])
                api.call('sendMessage', chat_id=api.chat, text=(
                    f"⚠️ Exit watch needs attention — {ctx['symbol']} ({row['id']})\n"
                    "Market data or the saved strategy could not be verified. "
                    "The trade remains on your sell list; checks will retry."))
                db.execute('UPDATE taken_trades SET monitor_error_sent=1 WHERE id=?', (row['id'],))


def load_bars(context, now):
    from nn_meta.live import run_live
    from nn_meta import config
    import pandas as pd
    # Keep the original scan's warmup window instead of sliding it forward.
    run_live._LOOKBACK_DAYS = max(60, (now.date() - pd.Timestamp(context['sim_start']).date()).days + 1)
    symbol = config.TICKER_ALIASES.get(context['symbol'], context['symbol'])
    return run_live._bar_loader(symbol, now=now)


def main():
    import argparse
    from dotenv import load_dotenv
    from nn_meta.live.alert_batches import Batches
    from nn_meta.live.scanner import is_rth
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expert', required=True)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    if not is_rth(now - timedelta(minutes=3)):
        return
    q = Batches()
    print(f'Taken trades checked [{args.expert}]: {scan(q, args.expert, load_bars, now)}', flush=True)


if __name__ == '__main__':
    main()
