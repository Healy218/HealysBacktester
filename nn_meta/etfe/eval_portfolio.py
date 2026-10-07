"""ETFE portfolio-replay evaluation (approximation of the declared shared ledger).

Policy (ETFE_EVALUATION_20261003): at each signal close keep candidates whose score passes the trial
threshold, rank by score (then the execution tie key), deduplicate to the best candidate per
underlying, and allocate 10% of current equity to each free underlying. One open position per
underlying (SPY, QQQ), so at most two concurrent positions; an underlying stays occupied until the
path's final cash settlement.

Approximation: P&L = the labeled path's dollar P&L, scaled down pro rata when 10% of equity cannot
afford its quantity and never scaled up (participation caps fills). An earlier R x 10%-of-equity
version overstated compounding. The exact ledger must confirm any passing result. Paths without a label
(unfilled / size-ineligible) occupy nothing. Funding/input-unresolved or censored selections are
counted as `blocked`: the declared evaluation cannot pass while any exist.
"""
import numpy as np
import pandas as pd

TIE=['signal_at_ns','ticker','minutes','right','target_dte','chart_row']


def replay(rows,score_col,threshold,start_equity=100_000.0,fraction=.10):
    """rows: one evaluation window with score, status, target_return, terminal_ns, ticker, signal_at_ns."""
    c=rows[rows[score_col]>=threshold] if threshold is not None else rows
    c=c.sort_values(['signal_at_ns',score_col,'ticker','minutes','right','target_dte','chart_row'],
                    ascending=[True,False,True,True,True,True,True],kind='stable')
    c=c.drop_duplicates(['signal_at_ns','ticker'],keep='first')  # best candidate per underlying per clock
    equity=start_equity;busy={};open_pos=[];curve=[];trades=0;blocked=0;wins=0
    for r in c.itertuples(index=False):
        t=r.signal_at_ns
        # settle positions whose final cash settlement is at or before this clock
        still=[]
        for end,pnl,tk in open_pos:
            if end<=t:equity+=pnl;curve.append((end,equity))
            else:still.append((end,pnl,tk))
        open_pos=still
        if busy.get(r.ticker,-1)>t:continue
        if r.status in ('observed_unfilled','size_ineligible'):continue
        if r.status!='settled':blocked+=1;continue  # counted; any blocked selection fails the declared rule
        # Dollar P&L of the labeled path (sized by $10k budget and the 1% participation cap), scaled DOWN
        # when 10% of current equity cannot afford the labeled quantity, never UP past what the market filled.
        unit=r.debit_cents/100/r.quantity;q=min(r.quantity,int(fraction*equity//unit))
        pnl=r.pnl_cents/100*q/r.quantity if q>0 else 0.0
        open_pos.append((int(r.terminal_ns),pnl,r.ticker));busy[r.ticker]=int(r.terminal_ns);trades+=1;wins+=r.target_return>0
    for end,pnl,tk in sorted(open_pos):equity+=pnl;curve.append((end,equity))
    eq=np.array([start_equity]+[e for _,e in sorted(curve)])
    peak=np.maximum.accumulate(eq);dd=float(((peak-eq)/peak).max()) if len(eq) else 0.0
    return dict(trades=trades,blocked=blocked,win_rate=wins/trades if trades else None,
        total_return=equity/start_equity-1,max_drawdown=dd)
