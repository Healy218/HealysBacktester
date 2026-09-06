"""Facade for separately attributed/licensed TradingView trend adaptations.

Exact upstream sources and versions: indicators/tradingview_sources/trend_manifest.json.
Functions consume completed bars only. Numerical TradingView fixture parity
remains pending; source-backed local tests do not certify cross-platform parity.
"""
from copy import deepcopy

import pandas as pd

from v3._tv_trend_support import validate_bars
from v3.tv_fibonacci import FIB_LEVELS, fibonacci_trend_continuation
from v3.tv_gaussian import gaussian_filter_trend
from v3.tv_uptrick import uptrick_adaptive_trend

__all__ = ["FIB_LEVELS", "fibonacci_trend_continuation", "gaussian_filter_trend",
           "uptrick_adaptive_trend", "TrendReplay"]


class TrendReplay:
    """Append-only replay retaining the exact initialization history.

    This reference implementation recomputes the accepted prefix on each
    append. It prioritizes auditable restart equivalence over bounded-memory
    live performance; callers should use batch functions for research builds.
    The snapshot is a local Python object, not a model/artifact admission token.
    """

    _calculators = {
        "gaussian_filter_trend": gaussian_filter_trend,
        "fibonacci_trend_continuation": fibonacci_trend_continuation,
        "uptrick_adaptive_trend": uptrick_adaptive_trend,
    }

    def __init__(self, name: str, parameters: dict | None = None,
                 history: pd.DataFrame | None = None):
        if name not in self._calculators:
            raise ValueError(f"unknown trend indicator: {name}")
        self.name = name
        self.parameters = deepcopy(parameters or {})
        self._history = None
        if history is not None:
            validate_bars(history)
            self._calculators[name](history, **self.parameters)
            self._history = history.copy(deep=True)

    def append(self, completed_bars: pd.DataFrame) -> pd.DataFrame:
        validate_bars(completed_bars)
        if (self._history is not None and len(self._history) and len(completed_bars)
                and completed_bars.index[0] <= self._history.index[-1]):
            raise ValueError("replay requires strictly newer completed bars")
        candidate = (completed_bars.copy(deep=True) if self._history is None
                     else pd.concat([self._history, completed_bars]))
        result = self._calculators[self.name](candidate, **self.parameters)
        self._history = candidate
        return result.loc[completed_bars.index].copy()

    def snapshot(self) -> dict:
        return {"name": self.name, "parameters": deepcopy(self.parameters),
                "history": None if self._history is None else self._history.copy(deep=True)}
