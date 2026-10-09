import importlib.util
import sys

import numpy as np

spec = importlib.util.spec_from_file_location("run_v9_oee_j", "scripts/run_v9_oee_j.py")
j = importlib.util.module_from_spec(spec)
sys.modules["run_v9_oee_j"] = j
spec.loader.exec_module(j)


def test_variant_states_follow_last_signal():
    E = np.array([[0, 1, 0, 0, 0, 1, 0]], bool)
    X = np.array([[0, 0, 0, 1, 0, 1, 0]], bool)
    assert j.variant_states(E, X).tolist() == [[0, 1, 1, -1, -1, 0, 0]]


def test_family_votes_weight_each_family_once():
    s = np.array([[1, 1], [1, -1], [1, -1], [-1, -1]], np.int8)
    v = j.family_votes(s, {"big": np.array([0, 1, 2]), "small": np.array([3])})
    assert np.allclose(v, [[1.0, -1 / 3], [-1.0, -1.0]])
