"""Regular-session expiry clock for V6's standard equity/ETF options.

Nasdaq Options Market Hours, checked 2026-09-14:
https://www.nasdaqtrader.com/Trader.aspx?id=optionshours
The named ETF/ETN classes close at 16:15 ET rather than 16:00.
Eligible options retain the 15-minute extension on scheduled early closes.
https://www.nyse.com/markets/hours-calendars
Index settlement rules are outside the frozen V6 stock/ETF universe.
"""
LATE_CLOSE=frozenset('''DBA DBB DBC DBO DIA DRAM EEM EFA EWY EWZ FXI GLD HYG
IBIT IEF IVV IWM IWN IWO IYR KBE KRE KWEB LQD MDY MOO OEF QQQ RSP SLV SMH
SOXL SOXX SPY SVIX SVXY TIP TLT UNG UUP UVIX UVXY VIXM VIXY VOO VXX VXZ
XHB XLB XLC XLE XLF XLI XLK XLP XLRE XLU XLV XLY XME XOP XRT'''.split())


def expiry_cutoff(contract,calendar):
    from options.data.provider import parse_occ_symbol
    import pandas as pd
    root,expiry,_,_=parse_occ_symbol(contract)
    if root in {'SPX','SPXW','XSP','NDX','NDXP','XND','VIX'}:
        raise ValueError('index expiry settlement is outside the V6 equity/ETF clock')
    day=expiry.isoformat()
    calendar.bounds(day)
    final=max(d for d in calendar.sessions if d<=day)
    close=calendar.bounds(final)[1].tz_localize('UTC')
    if root in LATE_CLOSE: close+=pd.Timedelta(minutes=15)
    return close-pd.Timedelta(minutes=15)
