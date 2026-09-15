"""Exact, bounded reuse of identical numerical calls within one V6 symbol.

The default path is untouched. An explicit context enables reuse; argument
bytes include the complete bars, timestamps, parameters and context inputs.
Serialized results detach every returned object, including nested columns.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import hashlib
import inspect
import pickle

_scope=ContextVar('v6_numerical_reuse',default=None)


@contextmanager
def reuse_identical_sources():
    scope={'values':{},'hits':0,'misses':0}
    token=_scope.set(scope)
    try: yield scope
    finally: _scope.reset(token)


def argument_digest(value):
    # Bind pandas values and labels, independent of BlockManager layout and
    # internal index caches. Include dtypes, timezone, frequency and attrs;
    # adapters receive the original objects, never these fingerprint values.
    import numpy as np
    import pandas as pd
    frame=type(value) is pd.DataFrame
    series=type(value) is pd.Series
    if (frame or series) and isinstance(value.index,pd.DatetimeIndex):
        columns=[value.iloc[:,i] for i in range(value.shape[1])] if frame else [value]
        if all(c.dtype.kind in 'bifu' for c in columns):
            parts=[b'dataframe' if frame else b'series',str(value.index.dtype).encode(),
                value.index.as_unit('ns').asi8.tobytes(),str(value.index.tz).encode(),
                pickle.dumps(value.index.names,protocol=5),str(value.index.freqstr).encode(),
                pickle.dumps(value.attrs,protocol=5),str(value.flags.allows_duplicate_labels).encode()]
            if frame: parts.append(pickle.dumps(value.columns.names,protocol=5))
            for column in columns:
                parts.extend([pickle.dumps(column.name,protocol=5),str(column.dtype).encode(),
                    np.ascontiguousarray(column.to_numpy()).tobytes()])
            digest=hashlib.sha256()
            for part in parts: digest.update(len(part).to_bytes(8,'little'));digest.update(part)
            return digest.digest()
    return hashlib.sha256(pickle.dumps(value,protocol=5)).digest()


def memoized_source(function):
    signature=inspect.signature(function)
    @wraps(function)
    def call(*args,**kwargs):
        scope=_scope.get()
        if scope is None: return function(*args,**kwargs)
        bound=signature.bind(*args,**kwargs); bound.apply_defaults()
        key=(function.__module__,function.__name__,
            tuple((name,argument_digest(value)) for name,value in bound.arguments.items()))
        if key not in scope['values']:
            scope['misses']+=1
            scope['values'][key]=pickle.dumps(function(*args,**kwargs),protocol=5)
        else: scope['hits']+=1
        return pickle.loads(scope['values'][key])
    return call
