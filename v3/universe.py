# v3/universe.py — Stage 1: universe selection.
"""BOOTSTRAP_UNIVERSE is the v3.0 candidate list (~200 liquid, optionable
US names + ETFs): the current 56-name universe plus large-cap/high-volume
extensions.

KNOWN LIMITATION (documented in V3_SPEC risk register): this is a
present-day list, so it carries survivorship bias for backtests reaching
2017 — names that died on the way (and would have been tradeable then) are
missing. True point-in-time selection with annual reconstitution
(select_universe below) needs a historical constituents source and stays
TODO; until then, results on the bootstrap universe must be read as
"survivors only" and the bias called out in every report.
"""
from nn_meta.config import UNDERLYINGS as V2_UNIVERSE

# ~150 extensions, grouped for review. All currently listed, liquid options.
_EXTENSIONS = [
    # mega/large tech & growth
    "GOOGL", "ADBE", "PANW", "SNOW", "CRWD", "NOW", "INTU", "AMAT", "LRCX",
    "KLAC", "ADI", "TXN", "MRVL", "ON", "SNPS", "CDNS", "ANET", "DELL",
    "IBM", "CSCO", "TEAM", "DDOG", "NET", "ZS", "MDB", "SHOP", "SQ",
    "PYPL", "ADSK", "WDAY", "FTNT", "ABNB", "DASH", "TTD", "APP",
    # consumer / retail / travel
    "NKE", "SBUX", "MCD", "TGT", "LOW", "TJX", "DG", "DLTR", "ROST", "LULU",
    "CMG", "YUM", "DPZ", "BKNG", "MAR", "HLT", "DAL", "UAL", "AAL", "LUV",
    "CCL", "RCL", "NCLH", "EXPE", "EBAY", "ETSY", "W", "CHWY",
    # financials
    "WFC", "C", "MS", "SCHW", "BLK", "AXP", "V", "MA", "COF", "DFS",
    "USB", "PNC", "TFC", "BK", "AIG", "MET", "PRU", "ALL", "TRV", "CB",
    "ICE", "CME", "SPGI", "MCO",
    # healthcare / pharma / biotech
    "JNJ", "ABBV", "MRK", "BMY", "AMGN", "GILD", "BIIB", "REGN", "VRTX",
    "MRNA", "CVS", "CI", "HUM", "ELV", "ISRG", "SYK", "BSX", "MDT", "ABT",
    "TMO", "DHR", "ZTS",
    # industrials / energy / materials
    "CAT", "DE", "HON", "GE", "MMM", "LMT", "RTX", "NOC", "GD", "UPS",
    "FDX", "UNP", "CSX", "EMR", "ETN", "PH", "COP", "SLB", "HAL", "OXY",
    "DVN", "EOG", "MPC", "VLO", "PSX", "KMI", "WMB", "FCX", "NEM", "NUE",
    "CLF", "AA",
    # staples / utilities / REITs
    "PG", "KO", "PEP", "PM", "MO", "CL", "KMB", "GIS", "K", "KR",
    "NEE", "DUK", "SO", "D", "EXC", "AMT", "PLD", "SPG", "O",
    # high-IV / retail favorites / crypto-adjacent
    "RIOT", "CLSK", "SOFI", "LCID", "RIVN", "NIO", "XPEV", "LI", "CHPT",
    "AFRM", "UPST", "RBLX", "U", "SNAP", "PINS", "ROKU", "ZM", "DKNG",
    "PENN", "CZR", "MGM", "WYNN", "LVS", "BYND", "CVNA", "AI", "IONQ",
    "RXRX", "SMR", "OKLO", "ACHR", "JOBY",
    # ETFs (sector / factor / vol / rates / commodities / intl)
    "XLK", "XLV", "XLI", "XLP", "XLU", "XLY", "XLB", "XLRE", "XBI", "XOP",
    "XRT", "XHB", "KRE", "KWEB", "FXI", "EEM", "EFA", "EWZ", "EWJ", "INDA",
    "GDX", "GDXJ", "SLV", "USO", "UNG", "URA", "LIT", "TAN", "ICLN",
    "HYG", "LQD", "IEF", "SHY", "TIP", "UVXY", "SQQQ", "TQQQ", "SOXL",
    "SOXX", "IBIT", "BITO",
]

BOOTSTRAP_UNIVERSE = sorted(set(V2_UNIVERSE) | set(_EXTENSIONS))


def select_universe(as_of: str, size: int) -> list[str]:
    """TRUE point-in-time liquidity-ranked constituents as of `as_of`.
    Needs a historical constituents dataset — see module docstring."""
    raise NotImplementedError("Stage 1 (point-in-time) — see V3_SPEC.md")
