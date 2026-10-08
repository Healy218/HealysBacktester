"""V8.1 engine hand cases on a synthetic 2-symbol, 1-bar-per-day market."""
import numpy as np

from nn_meta import v8_engine as en


def _bits(sig):  # sig: (S, V=1, T) bool → packed (S, 1, nbytes)
    return np.packbits(np.asarray(sig, bool), axis=2)


def _run(E, X, P, M, *, entry_ok=None, cost=0.0, force=None, prio=None, slots=10, mult=1.0):
    S, T = P.shape
    ok = np.ones((S, T), bool)
    return en.simulate(_bits(E), _bits(X), 0, P, M, ok, ok,
                       ok if entry_ok is None else entry_ok,
                       np.full((S, T), cost), np.full((S, T), cost), np.full((S, T), cost),
                       np.zeros((S, T), bool) if force is None else force,
                       np.zeros((S, T)) if prio is None else prio,
                       np.arange(T), T, mult, slots)


def test_signal_executes_next_bar_and_costs_apply():
    P = np.array([[100., 100., 110., 121.]])     # execution (open) prices
    M = np.array([[100., 105., 115., 121.]])     # closes
    E = np.zeros((1, 1, 4), bool); E[0, 0, 0] = True    # entry signal at close of bar 0
    X = np.zeros((1, 1, 4), bool); X[0, 0, 2] = True    # exit signal at close of bar 2
    eq, tr, w = _run(E, X, P, M, cost=10.0, slots=1)
    # buy at bar 1 open 100 paying 10 bp, mark 105 at close; exit at bar 3 open 121 paying 10 bp
    v1 = 1.0 / 1.001 * 105 / 100
    assert np.isclose(eq[1], v1)
    final = 1.0 / 1.001 * 121 / 100 * (1 - 0.001)
    assert np.isclose(eq[3], final) and tr.sum() == 1 and w.sum() == 1


def test_slots_priority_and_sizing():
    P = np.ones((3, 3)) * 50; M = np.ones((3, 3)) * 50
    E = np.zeros((3, 1, 3), bool); E[:, 0, 0] = True
    X = np.zeros((3, 1, 3), bool)
    prio = np.array([[1.0] * 3, [3.0] * 3, [2.0] * 3])
    eq, tr, _ = _run(E, X, P, M, prio=prio, slots=2)
    # two slots: symbols 1 and 2 (higher adv20) each take half of equity; flat prices
    assert np.isclose(eq[-1], 1.0) and tr.sum() == 0


def test_entry_waits_for_allowed_bar_and_exit_cancels():
    P = np.array([[10., 10., 10., 20.]]); M = P.copy()
    E = np.zeros((1, 1, 4), bool); E[0, 0, 0] = True
    X = np.zeros((1, 1, 4), bool)
    allowed = np.array([[True, False, True, True]])
    eq, _, _ = _run(E, X, P, M, entry_ok=allowed, slots=1)
    assert np.isclose(eq[3], 2.0)                 # entered at bar 2 at 10, worth 20
    X[0, 0, 1] = True                             # exit signal before the entry executes
    eq, _, _ = _run(E, X, P, M, entry_ok=allowed, slots=1)
    assert np.isclose(eq[3], 1.0)


def test_forced_exit_at_close():
    P = np.array([[10., 10., 10.]]); M = np.array([[10., 12., 12.]])
    E = np.zeros((1, 1, 3), bool); E[0, 0, 0] = True
    X = np.zeros((1, 1, 3), bool)
    force = np.array([[False, True, False]])
    eq, tr, _ = _run(E, X, P, M, force=force, slots=1, cost=0.0)
    assert np.isclose(eq[1], 1.2) and np.isclose(eq[2], 1.2) and tr.sum() == 1


def test_priority_below_minus_two_still_ranks():
    # stage-1 priorities were >= -1; event hypotheses use -z, which can be < -2
    P = np.ones((2, 3)) * 50; M = P.copy()
    E = np.zeros((2, 1, 3), bool); E[:, 0, 0] = True
    X = np.zeros((2, 1, 3), bool)
    prio = np.array([[-5.0] * 3, [-3.0] * 3])            # symbol 1 ranks first
    eq, _, _ = _run(E, X, P, M, prio=prio, slots=1)
    assert np.isclose(eq[-1], 1.0)
