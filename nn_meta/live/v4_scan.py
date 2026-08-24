# nn_meta/live/v4_scan.py
"""The [v4] expert — a second, independent live scanner pass.

Runs ALONGSIDE the deployed v3 scanner (which is untouched): a separate cron
line under ``NN_META_POOL=v31`` scores fresh mechanical entries with the
``model_final_v4/`` bundle and sends Telegram alerts labeled ``[v4]``. Server
cron (UTC):

    */15 * * * *  cd <repo> && NN_META_POOL=v31 venv/bin/python -m nn_meta.live.v4_scan --once --paper

Differences from the v3 pass, by design:

- **Causal candidates, no option fill.** Features come from
  ``v4_candidates.build_candidate_batch`` — the same primitives that built the
  offline v4 dataset — so there is no ``prem_spot`` and parity holds by
  construction. The candidate strike is the ATM target (strike = spot,
  moneyness = 0), matching the executor's TARGET_DELTA 0.5 / MONEYNESS 0.0.
- **Every pool strategy proposes**, not just the symbol's best (the v4 model
  was trained on all of them; its job is to pick).
- **The model picks the DTE**: each fresh signal is scored at every DTE in the
  grid and the best-scoring variant alerts iff it clears the bundle threshold
  (filter mode, reduced to one alert per signal).
- **Own state, own label.** Alert dedupe, an at-least-once outbox, and a
  paper ledger live in ``nn_meta/live/.v4_*.json`` — nothing shared with the
  v3 scanner's state. Alerts are titled ``[v4] …`` and never place orders.

Bundle trust policy: by default the bundle must pass ``verify_bundle()`` and
carry ``eligible: true`` (the Option-B re-finalized bundle satisfies both).
``--paper`` accepts the pre-hashing / pre-eligibility Option A bundle and
tags every alert "paper" — the honest mode for the interim deployment.

Known staleness (shared with the v3 scorer, acceptable for paper mode): the
IV surface and beta come from the daily caches as-of their last row; a
nightly surface refresh removes the gap. Context features that cannot be
computed on the host degrade to NaN (imputed/handled downstream) rather than
failing the pass.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from utils.logging_utils import setup_logging
from options.execution import to_naive_utc
from nn_meta import config
from nn_meta.baseline import load_spec, propose_trades
from nn_meta.build_meta_dataset import rolling_beta_60d
from nn_meta.live.scanner import (TICKER_ALIASES, aliased_bar_loader,
                                  closed_bars, is_rth)
from nn_meta.live.state import (AlertState, Outbox, PaperLedger,
                                atomic_write_json, health_snapshot)
from nn_meta.live.v4_candidates import build_candidate_batch
from nn_meta.live.watchlist import Watchlist, format_digest

# NOTE: nn_meta.v4_loader (→ v4_evaluate → model → tensorflow) is imported
# lazily inside load_trusted_bundle()/selftest() — the cron fires 96×/day and
# most firings exit at the RTH gate before needing a model. Annotations refer
# to V4Bundle as a string (PEP 563 via __future__ annotations).
from typing import TYPE_CHECKING
if TYPE_CHECKING:                                     # pragma: no cover
    from nn_meta.v4_loader import V4Bundle

logger = setup_logging(log_file="logs/backtester.log")

STATE_DIR = config.ROOT / "live"
ALERT_STATE = STATE_DIR / ".v4_alert_state.json"
OUTBOX = STATE_DIR / ".v4_outbox.json"
LEDGER = STATE_DIR / ".v4_paper_ledger.json"
HEALTH = STATE_DIR / ".v4_health.json"
WATCHLIST = STATE_DIR / ".v4_watchlist.json"

# TICKER_ALIASES / aliased_bar_loader moved to nn_meta.live.scanner
# (2026-08-16 review) so the legacy run_live path shares them; re-exported
# here for callers/tests that import them from this module.


# ── detection ─────────────────────────────────────────────────────────────────

def fresh_proposals(symbol: str, bars: pd.DataFrame, spec_entry: dict,
                    strategies: list[str]) -> list[dict]:
    """Fresh (symbol, strategy) entries whose newest simulated trade lands on
    the last closed bar — one dict per firing strategy, all DTE-agnostic."""
    out = []
    if bars is None or len(bars) < 30:
        return out
    for strat in strategies:
        e = spec_entry["strategies"].get(strat)
        if e is None:
            continue
        trades = propose_trades(bars, strat, e["params"],
                                bars.index[0], bars.index[-1])
        if not trades:
            continue
        ent_ts = to_naive_utc(trades[-1][0])
        if ent_ts != bars.index[-1]:
            continue
        # bars since the previous entry of the same strategy (v3 scorer parity)
        entry_pos = bars.index.searchsorted(
            [to_naive_utc(t[0]) for t in trades])
        gap = entry_pos[-1] - entry_pos[-2] if len(entry_pos) > 1 else entry_pos[-1]
        out.append({"symbol": symbol, "strategy": strat,
                    "direction": int(trades[-1][2]),
                    "entry_ts": ent_ts, "bars_since_signal": int(gap),
                    "param_label": e.get("param_label", ""),
                    "spot": float(bars["Close"].iloc[-1])})
    return out


def candidate_frame(fresh: list[dict]) -> pd.DataFrame:
    """Expand fresh signals to one proposal row per DTE-grid variant.
    Strike is the ATM target (= spot): decision-safe, no option fill."""
    rows = [{"symbol": f["symbol"], "strategy": f["strategy"], "dte": dte,
             "direction": f["direction"], "strike": f["spot"],
             "entry_ts": f["entry_ts"], "bars_since_signal": f["bars_since_signal"]}
            for f in fresh for dte in config.DTE_GRID]
    return pd.DataFrame(rows)


# ── context (parity with build_meta_dataset.add_context_features) ─────────────

def fill_context(batch: pd.DataFrame, surface: pd.DataFrame) -> pd.DataFrame:
    """Fill market_iv / rv_iv_spread / beta_60d exactly the way the offline
    ``add_context_features`` does, degrading each source to NaN independently
    (a host without the daily beta cache must still scan)."""
    batch = batch.copy()
    batch["entry_date"] = pd.to_datetime(batch["entry_ts"]).dt.normalize()
    batch = batch.sort_values("entry_date").reset_index(drop=True)
    try:
        spy_iv = surface[surface["underlying"] == "SPY"][["date", "atm_iv_near"]] \
            .rename(columns={"atm_iv_near": "market_iv"}).sort_values("date")
        merged = pd.merge_asof(batch.drop(columns=["market_iv"]), spy_iv,
                               left_on="entry_date", right_on="date",
                               allow_exact_matches=False).drop(columns=["date"])
        batch["market_iv"] = merged["market_iv"].to_numpy()
    except Exception as exc:                              # pragma: no cover
        logger.warning(f"[v4-scan] market_iv unavailable: {exc}")
    batch["rv_iv_spread"] = batch["rvol_21"] - batch["atm_iv_near"]
    try:
        beta = rolling_beta_60d().sort_values("date")
        parts = []
        for sym, grp in batch.groupby("symbol"):
            b = beta[beta["underlying"] == sym].drop(columns=["underlying"])
            if b.empty:
                parts.append(grp)
                continue
            m = pd.merge_asof(grp.sort_values("entry_date").drop(columns=["beta_60d"]),
                              b, left_on="entry_date", right_on="date",
                              allow_exact_matches=False).drop(columns=["date"])
            parts.append(m)
        batch = pd.concat(parts, ignore_index=True)
    except Exception as exc:
        logger.warning(f"[v4-scan] beta_60d unavailable (daily cache?): {exc}")
    return batch.drop(columns=["entry_date"])


# ── selection + alert ─────────────────────────────────────────────────────────

def best_per_signal(batch: pd.DataFrame, scores: np.ndarray,
                    decision: Optional[np.ndarray] = None) -> pd.DataFrame:
    """One row per (symbol, strategy): the DTE variant the bundle's policy
    scores best. ``scores`` is P(win) (always shown in the alert); ``decision``
    is what the policy thresholds on — the EV head's expected return for an
    ``ev``-mode bundle, else the same P(win)."""
    scored = batch.assign(score=scores,
                          decision=scores if decision is None else decision)
    idx = scored.groupby(["symbol", "strategy"])["decision"].idxmax()
    return scored.loc[idx].reset_index(drop=True)


def alert_key(symbol: str, strategy: str, bar_ts: pd.Timestamp) -> str:
    return f"v4|{symbol}|{strategy}|{pd.Timestamp(bar_ts).isoformat()}"


def format_v4_alert(row, fresh: dict, bundle: V4Bundle, paper: bool
                    ) -> tuple[str, str]:
    # direction comes from the fresh-signal dict: the candidate batch only
    # carries it as the dir_short feature.
    right = "C" if fresh["direction"] == 0 else "P"
    action = "BUY CALL" if right == "C" else "BUY PUT"
    expiry = (datetime.now(timezone.utc) + timedelta(days=int(row.dte))).date()
    tag = f"v4-{bundle.family}" + (" · paper" if paper else "")
    shown = TICKER_ALIASES.get(row.symbol, row.symbol)
    if shown != row.symbol:
        shown = f"{shown} (fka {row.symbol})"
    title = f"[v4] {shown} {action}"
    ev_part = (f" · EV {row.decision:+.1%}" if bundle.mode == config.EV_MODE
               and hasattr(row, "decision") else "")
    if bundle.mode == config.EV_MODE and bundle.dd_brake is not None:
        ev_part += f" · DD brake {bundle.dd_brake:.0%}"
    msg = (f"[v4] {shown}: {action} · P(win) {row.score:.0%}{ev_part}\n"
           f"trigger: {row.strategy} ({fresh['param_label']}) · "
           f"DTE {int(row.dte)} (best of grid)\n"
           f"contract: ~ATM {right} near ${fresh['spot']:,.2f}, "
           f"~{int(row.dte)} DTE (≈ {expiry})\n"
           f"bar: {row.entry_ts} UTC · spot ${fresh['spot']:,.2f}\n"
           f"expert: {tag}")
    return title, msg


# ── one pass ──────────────────────────────────────────────────────────────────

def scan_pass(*, bundle: V4Bundle, spec: dict, surface: pd.DataFrame,
              bar_loader: Callable[[str], pd.DataFrame], notifier,
              now: Optional[datetime] = None,
              symbols: Optional[list[str]] = None,
              threshold: Optional[float] = None,
              state_dir: Optional[Path] = None, paper: bool = False) -> dict:
    """Scan → score → alert once. Returns a summary dict (also written as the
    health snapshot). All state I/O is atomic and idempotent."""
    now = now or datetime.now(timezone.utc)
    thr = bundle.threshold if threshold is None else float(threshold)
    sdir = Path(state_dir) if state_dir else STATE_DIR
    alert_state = AlertState(sdir / ALERT_STATE.name)
    outbox = Outbox(sdir / OUTBOX.name)
    ledger = PaperLedger(sdir / LEDGER.name)
    watchlist = Watchlist(sdir / WATCHLIST.name)

    fresh_by_key: dict[str, dict] = {}
    bars_cache: dict[str, pd.DataFrame] = {}
    errors = 0
    scanned = 0
    for sym in (symbols or list(spec["symbols"])):
        try:
            bars = closed_bars(bar_loader(sym), now)
            scanned += 1
            for f in fresh_proposals(sym, bars, spec["symbols"][sym],
                                     config.PROPOSAL_STRATEGIES):
                key = alert_key(f["symbol"], f["strategy"], f["entry_ts"])
                if not alert_state.seen(key):        # dedupe before scoring
                    fresh_by_key[key] = f
                    bars_cache[sym] = bars
        except Exception as exc:
            errors += 1
            logger.error(f"[v4-scan] {sym}: scan error: {exc}")

    alerted = 0
    if fresh_by_key:
        batch = build_candidate_batch(candidate_frame(list(fresh_by_key.values())),
                                      bars_cache, surface, spec)
        batch = fill_context(batch, surface)
        scores = bundle.score(batch)
        decision = bundle.ev(batch) if bundle.mode == config.EV_MODE else scores
        winners = best_per_signal(batch, scores, decision)
        for row in winners.itertuples(index=False):
            key = alert_key(row.symbol, row.strategy, row.entry_ts)
            fresh = fresh_by_key[key]
            # Dual-mode cadence (ROADMAP wave-2 item 5): EVERY scored winner
            # joins the daily watchlist, threshold or no — the digest sends
            # the day's top-N and tracks forward hit-rates.
            watchlist.record(key=key, symbol=row.symbol, strategy=row.strategy,
                             dte=int(row.dte), direction=fresh["direction"],
                             score=float(row.score), decision=float(row.decision),
                             spot=fresh["spot"], entry_ts=row.entry_ts,
                             alerted=bool(row.decision >= thr))
            if row.decision < thr:
                logger.info(f"[v4-scan] {row.symbol}/{row.strategy}: filtered "
                            f"(best {bundle.mode} score {row.decision:.3f} < {thr})")
                alert_state.mark(key)                # don't rescore this bar
                continue
            title, msg = format_v4_alert(row, fresh, bundle, paper)
            # Crash-consistency order (2026-08-16 review): enqueue -> ledger
            # -> mark. A crash at any boundary re-detects next pass (not yet
            # marked); the outbox key dedupes the notification and the ledger
            # dedupes the position (duplicate trade_id is a no-op), so no
            # ordering loses an alert or a paper position.
            outbox.enqueue({"title": title, "message": msg}, key=key)
            try:
                ledger.open(trade_id=f"{key}|{int(row.dte)}", symbol=row.symbol,
                            entry_ts=row.entry_ts, price=fresh["spot"])
            except ValueError:
                pass                        # replayed after a crash — already open
            alert_state.mark(key)
            alerted += 1

    delivered = 0
    for entry in outbox.unacked():                   # incl. replays from crashes
        p = entry["payload"]
        if notifier.send(p["message"], title=p["title"]):
            outbox.mark_sent(entry["id"])
            outbox.acknowledge(entry["id"])
            delivered += 1

    summary = health_snapshot(last_run_ts=now, now=now, error_count=errors,
                              scanned=scanned, alerted=alerted)
    summary["delivered"] = delivered
    summary["open_paper_positions"] = len(ledger.open_positions())
    atomic_write_json(sdir / HEALTH.name, summary)
    return summary


# ── daily watchlist digest (dual-mode cadence, ROADMAP wave-2 item 5) ─────────

PANEL_WATCHLISTS = (("v4", ".v4_watchlist.json"), ("v3", ".v3_watchlist.json"),
                    ("v31", ".v31_watchlist.json"))


def digest_pass(*, bar_loader: Callable[[str], pd.DataFrame], notifier,
                state_dir: Optional[Path] = None, top: int = 10,
                now: Optional[datetime] = None) -> dict:
    """Once daily (cron, after the close): resolve due watchlist outcomes
    against fresh bars and send ONE panel message — a top-N section per
    expert whose watchlist saw signals today (v4 + the legacy v3/v31 seats,
    panel-wide since 2026-08-24), each with its rolling hit-rate. No model
    load — this reads only what the 15-minute passes recorded. Idempotent
    per day via the outbox key."""
    now = now or datetime.now(timezone.utc)
    day = pd.Timestamp(now).date().isoformat()
    sdir = Path(state_dir) if state_dir else STATE_DIR
    outbox = Outbox(sdir / OUTBOX.name)

    resolved, signals, sections, digested = 0, 0, [], []
    for expert, fname in PANEL_WATCHLISTS:
        path = sdir / fname
        if not path.exists():
            continue
        wl = Watchlist(path)
        resolved += wl.resolve(bar_loader, now)
        rows = wl.pending_digest(day)
        if not rows:
            continue
        signals += len(rows)
        ev_mode = any(abs(e["decision"] - e["score"]) > 1e-9 for e in rows)
        _, msg = format_digest(rows, wl.hit_stats(), expert=expert, top=top,
                               aliases=TICKER_ALIASES, ev_mode=ev_mode)
        sections.append(f"── [{expert}] top {min(top, len(rows))} of "
                        f"{len(rows)} ──\n{msg}")
        digested.append((wl, [e["key"] for e in rows]))
    sent = 0
    if sections:
        outbox.enqueue({"title": f"[panel watchlist] {day}",
                        "message": "\n\n".join(sections)},
                       key=f"panel-digest|{day}")
        for wl, keys in digested:
            wl.mark_digested(keys)
    for entry in outbox.unacked():
        p = entry["payload"]
        if notifier.send(p["message"], title=p["title"]):
            outbox.mark_sent(entry["id"])
            outbox.acknowledge(entry["id"])
            sent += 1
    summary = {"signals_today": signals, "outcomes_resolved": resolved,
               "delivered": sent}
    logger.info(f"[panel-digest] {summary}")
    return summary


# ── bundle trust policy ───────────────────────────────────────────────────────

def load_trusted_bundle(bundle_dir: Optional[Path] = None, *,
                        paper: bool = False) -> "V4Bundle":
    """Default: hash-verified AND gate-eligible, else refuse. ``paper=True``
    accepts the pre-hashing Option A bundle (logged loudly)."""
    from nn_meta.v4_loader import load_final_v4, verify_bundle   # lazy: TF chain
    from nn_meta.v4_artifacts import ArtifactValidationError
    try:
        verify_bundle(bundle_dir)
        verified = True
    except ArtifactValidationError as exc:
        if not paper:
            raise SystemExit(f"[v4-scan] bundle verification failed: {exc}\n"
                             f"(re-finalize under Option B, or run --paper)")
        verified = False
        logger.warning(f"[v4-scan] PAPER MODE — unverified bundle: {exc}")
    bundle = load_final_v4(bundle_dir)
    if not bundle.eligible and not paper:
        raise SystemExit("[v4-scan] bundle is not gate-eligible — refuse to "
                         "score live (run --paper to accept for paper alerts)")
    if not bundle.eligible:
        logger.warning("[v4-scan] PAPER MODE — bundle not gate-eligible")
    logger.info(f"[v4-scan] bundle: {bundle.family}/{bundle.mode}/"
                f"thr={bundle.threshold} · {len(bundle.members)} members · "
                f"verified={verified} eligible={bundle.eligible}")
    return bundle


def selftest(bundle_dir: Optional[Path] = None) -> None:
    """Deploy-time check: force-load every member and score a synthetic batch."""
    bundle = load_trusted_bundle(bundle_dir, paper=True)
    rows = pd.DataFrame(0.0, index=range(8), columns=bundle.features)
    scores = bundle.score(rows)
    assert scores.shape == (8,) and np.isfinite(scores).all()
    print(f"SELFTEST OK — {bundle.family} x{len(bundle.members)} members, "
          f"thr={bundle.threshold}, score(0-batch) median {np.median(scores):.3f}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", default=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--symbols", type=str, default=None)
    ap.add_argument("--threshold", type=float, default=None)
    ap.add_argument("--ignore-hours", action="store_true")
    ap.add_argument("--paper", action="store_true",
                    help="accept an unverified/ineligible bundle; tag alerts")
    ap.add_argument("--bundle", type=str, default=None)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--digest", action="store_true",
                    help="send the daily top-N watchlist digest (no model load)")
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()

    if config.POOL != "v31":
        raise SystemExit("[v4-scan] must run with NN_META_POOL=v31 — the v4 "
                         f"bundle/spec live in the v31 dirs (got '{config.POOL}')")
    bundle_dir = Path(args.bundle) if args.bundle else None
    if args.selftest:
        selftest(bundle_dir)
        return

    if args.digest:
        from nn_meta.live.run_live import _bar_loader       # lazy: data loader
        from nn_meta.live.notifier import get_notifier
        s = digest_pass(bar_loader=aliased_bar_loader(_bar_loader),
                        notifier=get_notifier(force_console=args.dry_run),
                        top=args.top)
        print(f"[panel-digest] signals {s['signals_today']} · resolved "
              f"{s['outcomes_resolved']} · delivered {s['delivered']}")
        return

    now = datetime.now(timezone.utc)
    if not args.ignore_hours and not is_rth(now):
        print("Outside RTH — nothing to scan.")
        return

    from nn_meta.live.run_live import _bar_loader           # lazy: data loader
    from nn_meta.live.notifier import get_notifier
    from nn_meta.build_meta_dataset import load_surface_features

    bundle = load_trusted_bundle(bundle_dir, paper=args.paper)
    summary = scan_pass(
        bundle=bundle, spec=load_spec(), surface=load_surface_features(),
        bar_loader=aliased_bar_loader(_bar_loader),
        notifier=get_notifier(force_console=args.dry_run),
        now=now,
        symbols=[s.strip().upper() for s in args.symbols.split(",")]
        if args.symbols else None,
        threshold=args.threshold, paper=args.paper)
    print(f"[v4] scanned {summary['scanned']} · alerted {summary['alerted']} · "
          f"delivered {summary['delivered']} · errors {summary['error_count']}")


if __name__ == "__main__":
    main()
