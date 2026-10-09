# nn_meta/v9_alt.py — V9 ALT-0: alternative-data parsers for earnings direction.
"""Point-in-time parsers over data already on disk (Benzinga headlines from the
Alpaca news archive, SEC Form 4, Wikipedia page views).

parse_analyst(headline)   -> (action, firm, new price target) or None
    action: pt_raise, pt_cut, upgrade, downgrade, initiate, maintain
parse_earnings(headline)  -> dict(eps_act, eps_est, sales_act, sales_est) or None
    e.g. "Teradyne Q1 Adj. EPS $0.98 Beats $0.88 Estimate, Sales $755.00M Beat
    $740.98M Estimate"; negative amounts are written $(0.10)
"""
from __future__ import annotations

import re

import numpy as np

_MONEY = r"\$\(?-?[\d,]*\.?\d+\)?(?:[KMB])?"
_PT = re.compile(r"price target to \$([\d,]*\.?\d+)", re.I)
_RAISE = re.compile(r"(raises|boosts|lifts|increases|bumps up)\b.{0,30}price target", re.I)
_CUT = re.compile(r"(lowers|cuts|reduces|trims|slashes)\b.{0,30}price target", re.I)
_UP = re.compile(r"\bupgrades?\b", re.I)
_DOWN = re.compile(r"\bdowngrades?\b", re.I)
_INIT = re.compile(r"\binitiates?\b|\bassumes\b|\breinstates\b", re.I)
_MAINT = re.compile(r"\bmaintains\b|\breiterates\b", re.I)
_FIRM = re.compile(r"^(.*?)\s+(Maintains|Upgrades|Downgrades|Initiates|Reiterates|Assumes|Reinstates|Raises|Lowers|Cuts|Boosts)\b")
_EPS = re.compile(r"EPS\s+(" + _MONEY + r")\s+(?:Beats|Misses|In-Line With|Up From|Down From|vs\.?)?\s*(?:by .*? )?(" + _MONEY + r")\s+Estimate", re.I)
_SALES = re.compile(r"(?:Sales|Revenue)\s+(" + _MONEY + r")\s+(?:Beat|Miss|Misses|Beats|In-Line With|vs\.?)?\s*(" + _MONEY + r")\s+Estimate", re.I)


def money(s: str) -> float:
    neg = "(" in s or "-" in s
    mult = {"K": 1e3, "M": 1e6, "B": 1e9}.get(s[-1].upper(), 1.0) if s[-1].isalpha() else 1.0
    v = float(re.sub(r"[^\d.]", "", s)) * mult
    return -v if neg else v


def parse_analyst(h: str):
    if not h or "price target" not in h.lower() and not (_UP.search(h) or _DOWN.search(h) or _INIT.search(h)):
        return None
    if _UP.search(h):
        action = "upgrade"
    elif _DOWN.search(h):
        action = "downgrade"
    elif _RAISE.search(h):
        action = "pt_raise"
    elif _CUT.search(h):
        action = "pt_cut"
    elif _INIT.search(h):
        action = "initiate"
    elif _MAINT.search(h):
        action = "maintain"
    else:
        return None
    m = _PT.search(h)
    pt = float(m.group(1).replace(",", "")) if m else np.nan
    f = _FIRM.search(h)
    return action, (f.group(1).strip() if f else ""), pt


def parse_earnings(h: str):
    if not h or "estimate" not in h.lower():
        return None
    e = _EPS.search(h)
    s = _SALES.search(h)
    if not e and not s:
        return None
    out = {"eps_act": np.nan, "eps_est": np.nan, "sales_act": np.nan, "sales_est": np.nan}
    if e:
        out["eps_act"], out["eps_est"] = money(e.group(1)), money(e.group(2))
    if s:
        out["sales_act"], out["sales_est"] = money(s.group(1)), money(s.group(2))
    return out


def surprise(act: float, est: float) -> float:
    if not (np.isfinite(act) and np.isfinite(est)) or est == 0:
        return np.nan
    return (act - est) / abs(est)
