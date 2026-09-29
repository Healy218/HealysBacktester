"""Immutable, once-validated minute schedule shared by many execution paths."""
from bisect import bisect_left
from itertools import islice


class ReplayClocks:
    __slots__ = ('_values', '_start')

    def __init__(self, values):
        clocks = tuple(values)
        if any(type(t) is not int for t in clocks) or any(a >= b for a,b in zip(clocks,clocks[1:])):
            raise ValueError('Ordered unique minute clocks required')
        object.__setattr__(self, '_values', clocks)
        object.__setattr__(self, '_start', 0)

    def __setattr__(self, name, value):
        raise AttributeError('Replay clocks are immutable')

    def after(self, clock):
        result = object.__new__(type(self))
        object.__setattr__(result, '_values', self._values)
        object.__setattr__(result, '_start', bisect_left(self._values,clock,lo=self._start))
        return result

    def __iter__(self):
        return islice(self._values,self._start,None)

    def __len__(self):
        return len(self._values)-self._start

    def __contains__(self, clock):
        pos = bisect_left(self._values,clock,lo=self._start)
        return pos < len(self._values) and self._values[pos] == clock
