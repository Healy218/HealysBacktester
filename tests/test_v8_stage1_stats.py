"""V8.1 statistics: CSCV PBO and deflated Sharpe behave as expected."""
import importlib.util
from pathlib import Path

import numpy as np

_SPEC = importlib.util.spec_from_file_location(
    "run_v8_stage1", Path(__file__).resolve().parent.parent / "scripts" / "run_v8_stage1.py")
st = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(st)


def test_pbo_noise_vs_true_skill():
    rng = np.random.default_rng(1)
    noise = rng.normal(0, 0.01, (200, 1600))
    assert 0.3 < st.pbo_cscv(noise, 8)["pbo"] < 0.8
    skilled = noise.copy()
    skilled[0] += 0.004                                  # one variant has real edge
    assert st.pbo_cscv(skilled, 8)["pbo"] < 0.05


def test_deflated_sharpe_penalizes_many_trials():
    rng = np.random.default_rng(2)
    r = rng.normal(0.002, 0.01, 750)                     # daily SR ~0.2 (ann ~3)
    few = st.deflated_sharpe(r, n_trials=2, sr_var=0.001)["probability"]
    many = st.deflated_sharpe(r, n_trials=5000, sr_var=0.001)["probability"]
    assert few > 0.95 and many < few
