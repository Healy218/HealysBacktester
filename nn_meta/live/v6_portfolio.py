"""Persistent V6 experimental paper portfolio and transactional alert outbox.

Frozen EV selection, five slots and 10% caps precede midpoint paper pricing.
These are fractional research positions, never broker orders or user fills.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

from nn_meta.live.v6_shadow import canonical
from options.paper_pricing import MIDPOINT_POLICY, option_midpoint
from options.paper_risk import V6_OPTION_RISK
from dataclasses import asdict

COST = .0015


def key_of(row):
    return f"v6|{row['symbol']}|{row['strategy']}|{pd.Timestamp(row['entry_ts']).isoformat()}"


def choose(rows, occupied, *, slots=5, fraction=.1):
    """Match ev_candidate_rows / ev_weighted_portfolio without future exits."""
    if rows.empty:
        return rows.assign(size_fraction=pd.Series(dtype=float))
    if not np.isfinite(rows[["decision", "score"]].to_numpy(dtype=float)).all():
        raise ValueError("nonfinite V6 prediction")
    accepted = rows[rows.decision >= .05].sort_values("decision", ascending=False).drop_duplicates(["symbol", "strategy", "entry_ts"])
    seen = set(occupied)
    free, picks = slots - len(seen), []
    for i, row in accepted.sort_values("decision", ascending=False).iterrows():
        if len(picks) >= free:
            break
        if row.symbol in seen:
            continue
        seen.add(row.symbol)
        picks.append(i)
    selected = accepted.loc[picks].copy()
    selected["size_fraction"] = np.minimum(selected.decision / selected.decision.sum() * (slots * fraction), fraction)
    return selected


def checked_quote(quote, contract, now, after):
    if quote["contract"] != contract:
        raise ValueError("execution quote belongs to another contract")
    bid, ask = float(quote["bid"]), float(quote["ask"])
    sip = pd.Timestamp(int(quote["sip_timestamp_ns"]), tz="UTC")
    received = pd.Timestamp(quote["received_at"])
    now, after = pd.Timestamp(now), pd.Timestamp(after)
    if (not math.isfinite(bid + ask) or not 0 < bid <= ask or
            quote.get("ask_size", 0) <= 0 or quote.get("bid_size", 0) <= 0 or
            not after <= sip <= received <= now or (now - sip).total_seconds() > 30):
        raise ValueError("invalid, stale or pre-decision paper quote")
    return bid, ask


class ForwardPortfolio:
    def __init__(self, path, *, scope):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS cycles(bar TEXT PRIMARY KEY, recorded_at TEXT, payload TEXT);
                CREATE TABLE IF NOT EXISTS positions(key TEXT PRIMARY KEY, symbol TEXT, state TEXT, payload TEXT);
                CREATE UNIQUE INDEX IF NOT EXISTS one_open_symbol ON positions(symbol) WHERE state!='closed';
                CREATE TABLE IF NOT EXISTS events(key TEXT PRIMARY KEY, recorded_at TEXT, kind TEXT, payload TEXT);
                CREATE TABLE IF NOT EXISTS outbox(key TEXT PRIMARY KEY, kind TEXT, created_at TEXT, payload TEXT, status TEXT DEFAULT 'pending');
            """)
            saved = db.execute("SELECT value FROM metadata WHERE key='scope'").fetchone()
            if saved and saved[0] != canonical(scope):
                raise ValueError("portfolio model/rules changed; use a new experiment state")
            db.execute("INSERT OR IGNORE INTO metadata VALUES ('scope',?)", (canonical(scope),))
            db.execute("INSERT OR IGNORE INTO metadata VALUES ('equity','1.0')")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def open_positions(self):
        with self.connect() as db:
            return [json.loads(r[0]) for r in db.execute("SELECT payload FROM positions WHERE state!='closed' ORDER BY key")]

    def migrate_midpoint(self, *, at, apply=False):
        """Audit the open paper-leg transition; completed history stays intact.

        The retained entry quote supplies the same midpoint basis as future
        exits. This rebases simulated open-leg units, never broker fills, prior
        closed legs, realized equity, allocation amounts or signal state.
        """
        stamp = pd.Timestamp(at)
        if pd.isna(stamp) or stamp.tzinfo is None:
            raise ValueError('Aware pricing transition time required')
        changes = []
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE' if apply else 'BEGIN')
            for row in db.execute("SELECT payload FROM positions WHERE state!='closed' ORDER BY key").fetchall():
                p = json.loads(row[0])
                if p.get('pricing_policy') == MIDPOINT_POLICY:
                    continue
                if p.get('pricing_policy') not in (None, 'legacy-ask-bid'):
                    raise ValueError('Unknown existing paper price policy')
                before = p['entry_price']
                basis = option_midpoint(p['entry_quote'])
                if not math.isclose(before, p['entry_quote']['ask'] * (1 + COST), rel_tol=1e-12):
                    raise ValueError('Legacy entry does not reconcile to its retained ask')
                if p['state'] not in ('open', 'exit_due', 'roll_due', 'roll_pending'):
                    raise ValueError('Unknown position state during pricing transition')
                # roll_pending holds cash from an already completed legacy leg.
                after = before if p['state'] == 'roll_pending' else basis['price'] * (1 + COST)
                audit = dict(key=p['key'], at=stamp.isoformat(), state=p['state'],
                    old_policy='legacy-ask-bid', new_policy=MIDPOINT_POLICY,
                    old_entry_price=before, new_entry_price=after, entry_reference=basis,
                    completed_legs_preserved=len(p['legs']), realized_equity_unchanged=True)
                changes.append(audit)
                if apply:
                    p.update(pricing_policy=MIDPOINT_POLICY, entry_price=after,
                             pricing_transition=audit)
                    if p['state'] != 'roll_pending':p['entry_reference'] = basis
                    db.execute('UPDATE positions SET payload=? WHERE key=?', (canonical(p), p['key']))
                    db.execute('INSERT INTO events VALUES (?,?,?,?)',
                        (p['key']+'|pricing|'+MIDPOINT_POLICY, stamp.isoformat(), 'pricing_change', canonical(audit)))
            if apply:
                db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)', ('pricing_policy', MIDPOINT_POLICY))
        return dict(pricing_policy=MIDPOINT_POLICY, applied=apply, changes=changes)

    def cycle_seen(self, bar):
        with self.connect() as db:
            return bool(db.execute("SELECT 1 FROM cycles WHERE bar=?", (str(bar),)).fetchone())

    def allocate(self, rows, *, bar, now, quote_loader, contexts, clock, alerts=False):
        """One immutable complete-universe allocation per closed signal bar.

        A selected but unfillable idea is recorded, not replaced by a lower-EV
        idea. Its quote rejection cannot silently change the model ranking.
        """
        bar = pd.Timestamp(bar)
        now = pd.Timestamp(now)
        close = bar.tz_localize("UTC") + pd.Timedelta(minutes=15) if bar.tzinfo is None else bar + pd.Timedelta(minutes=15)
        if not close <= now <= close + pd.Timedelta(minutes=5):
            raise ValueError("entry decision missed the five-minute signal-close deadline")
        if not rows.empty and not (pd.to_datetime(rows.entry_ts) == bar).all():
            raise ValueError("allocation contains another signal bar")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM cycles WHERE bar=?", (str(bar),)).fetchone():
                return {"duplicate": True, "opened": 0}
            positions = [json.loads(r[0]) for r in db.execute("SELECT payload FROM positions WHERE state!='closed'")]
            if any(p.get('pricing_policy') != MIDPOINT_POLICY for p in positions):
                raise ValueError('Open legacy paper positions require audited midpoint migration')
            if any(p["state"] != "open" for p in positions):
                raise ValueError("unresolved paper exit/roll prevents new allocation")
            occupied = {p["symbol"] for p in positions}
            selected = choose(rows.reset_index(drop=True), occupied)
            equity = float(db.execute("SELECT value FROM metadata WHERE key='equity'").fetchone()[0])
            outcomes, opened = [], 0
            for row in selected.to_dict("records"):
                key = key_of(row)
                try:
                    decision_at = clock()
                    if decision_at > close + pd.Timedelta(minutes=5):
                        raise ValueError("entry deadline elapsed before quote retrieval")
                    if not row.get("decision_contract") or row.get("option_tick_status") != "covered":
                        raise ValueError("selected candidate lacks complete contract tick inputs")
                    quote = quote_loader(row["decision_contract"], after=close)
                    filled = clock()
                    bid, ask = checked_quote(quote, row["decision_contract"], filled, close)
                    basis = option_midpoint(quote)
                    if pd.Timestamp(quote["received_at"]) < decision_at:
                        raise ValueError("execution quote was not retrieved for this decision")
                    if filled > close + pd.Timedelta(minutes=5):
                        raise ValueError("entry quote arrived after five-minute deadline")
                    if equity <= 0:
                        raise ValueError("paper equity is nonpositive")
                    amount = float(row["size_fraction"]) * equity
                    position = dict(row, key=key, state="open", initial_amount=amount,
                        amount=amount, entry_price=basis['price'] * (1 + COST), opened_at=filled.isoformat(),
                        entry_reference=basis, pricing_policy=MIDPOINT_POLICY,
                        option_risk_policy=asdict(V6_OPTION_RISK),
                        decision_at=decision_at.isoformat(), entry_quote=quote, contract=row["decision_contract"],
                        context=contexts[key], rolls=0, return_factor=1., legs=[])
                    db.execute("INSERT INTO positions VALUES (?,?,?,?)", (key, row["symbol"], "open", canonical(position)))
                    payload = self.entry_payload(position, close)
                    if alerts:
                        self._outbox(db, key, "entry", filled, payload)
                    outcomes.append({"key": key, "status": "opened", "fraction": row["size_fraction"]})
                    opened += 1
                except (ValueError, RuntimeError) as exc:
                    outcomes.append({"key": key, "status": "unfilled", "reason": str(exc)})
            payload = {"candidates": rows.to_dict("records"), "outcomes": outcomes,
                "occupied_before": sorted(occupied), "equity_before": equity,
                "recorded_at": clock().isoformat(), "alerts_requested": alerts}
            db.execute("INSERT INTO cycles VALUES (?,?,?)", (str(bar), clock().isoformat(), canonical(payload)))
            return {"opened": opened, "selected": len(selected), "unfilled": len(selected) - opened, "duplicate": False}

    @staticmethod
    def _outbox(db, key, kind, now, payload):
        db.execute("INSERT OR IGNORE INTO outbox(key,kind,created_at,payload) VALUES (?,?,?,?)",
                   (key, kind, pd.Timestamp(now).isoformat(), canonical(payload)))

    @staticmethod
    def entry_payload(p, close):
        from options.data.provider import parse_occ_symbol
        _, expiry, right, strike = parse_occ_symbol(p["contract"])
        side = "BUY PUT" if right == "P" else "BUY CALL"
        title = f"[v6] {p['symbol']} {side}"
        quote = p["entry_quote"]
        message = (f"{title} · EXPERIMENTAL PAPER\n"
            f"{p['contract']} · ${strike:g} · expiry {expiry} · actual DTE {(expiry - pd.Timestamp(close).date()).days}\n"
            f"trigger: {p['strategy']} · target DTE {p['dte']}\n"
            f"EV {p['decision']:+.1%} · excess-return classifier {p['score']:.1%}\n"
            f"paper allocation {p['size_fraction']:.1%} · ask ${quote['ask']:.2f} / bid ${quote['bid']:.2f}\n"
            f"signal close {close.isoformat()} · quote received {quote['received_at']}\n"
            f"simulated midpoint ${p['entry_reference']['price']:.4f} · cost {COST:.2%} per side\n"
            "Five-slot V6 experiment; midpoint paper prices, no broker execution.")
        return {"expert": "v6", "probability": p["score"], "alert_cycle": int(close.timestamp()),
                "symbol": p["symbol"], "side": side, "contract": p["contract"], "title": title, "message": message}

    def trigger(self, key, *, kind, reason, at, alerts=False, evidence=None, expected_leg=None):
        if kind not in ("exit", "roll"):
            raise ValueError("unknown portfolio event")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state,payload FROM positions WHERE key=?", (key,)).fetchone()
            if not row or row[0] == "closed":
                return False
            p = json.loads(row[1])
            if expected_leg is not None and any(p.get(k) != expected_leg.get(k)
                    for k in ('contract','rolls','entry_price','entry_quote')):
                return False
            if evidence is not None:
                p['trigger_evidence'] = evidence
            if kind == "exit" and p["state"] == "roll_pending":
                equity = float(db.execute("SELECT value FROM metadata WHERE key='equity'").fetchone()[0])
                equity += p["initial_amount"] * (p["return_factor"] - 1)
                db.execute("UPDATE metadata SET value=? WHERE key='equity'", (str(equity),))
                p.update(state="closed", trigger_at=pd.Timestamp(at).isoformat(), trigger_reason=reason)
                db.execute("UPDATE positions SET state='closed',payload=? WHERE key=?", (canonical(p), key))
                if alerts:
                    title=f"[v6] {p['symbol']} PAPER EXIT"
                    self._outbox(db, key+'|cash-exit', 'notice', at, {'title':title,
                        'message':f"{title}\nStrategy exited while waiting for a replacement. Paper roll cash released; no new option opened."})
                return True
            if kind == "exit" and p["state"] == "roll_due":
                p.update(state="exit_due", trigger_at=pd.Timestamp(at).isoformat(), trigger_reason=reason)
                db.execute("UPDATE positions SET state='exit_due',payload=? WHERE key=?", (canonical(p), key))
                return True
            if p["state"] != "open":
                return False
            p.update(state=kind + "_due", trigger_at=pd.Timestamp(at).isoformat(), trigger_reason=reason)
            db.execute("UPDATE positions SET state=?,payload=? WHERE key=?", (p["state"], canonical(p), key))
            return True

    def settle(self, key, *, quote_loader, clock, replacement=None, alerts=False):
        """Persist each leg before attempting a replacement; crashes cannot resell."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM positions WHERE key=? AND state!='closed'", (key,)).fetchone()
            if row is None:
                return None
            p = json.loads(row[0])
            if p["state"] not in ("exit_due", "roll_due", "roll_pending"):
                return None
            if p.get('pricing_policy') != MIDPOINT_POLICY:
                raise ValueError('Open legacy paper position requires audited midpoint migration')
            if p["state"] in ("exit_due", "roll_due"):
                decision = clock()
                after = pd.Timestamp(p["trigger_at"])
                quote = quote_loader(p["contract"], after=after)
                checked_quote(quote, p["contract"], clock(), after)
                basis = option_midpoint(quote)
                factor = basis['price'] * (1 - COST) / p["entry_price"]
                p["return_factor"] *= factor
                p["amount"] *= factor
                p["legs"].append({"contract": p["contract"], "entry_price": p["entry_price"], "exit_quote": quote,
                    'exit_reference': basis, 'entry_reference': p['entry_reference'], 'pricing_policy': MIDPOINT_POLICY,
                    "reason": p["trigger_reason"], "trigger_at": p["trigger_at"], "return_factor": factor})
                closed = p["state"] == "exit_due" or p["rolls"] >= 60
                p["state"] = "closed" if closed else "roll_pending"
                if closed:
                    equity = float(db.execute("SELECT value FROM metadata WHERE key='equity'").fetchone()[0])
                    equity += p["initial_amount"] * (p["return_factor"] - 1)
                    db.execute("UPDATE metadata SET value=? WHERE key='equity'", (str(equity),))
                db.execute("UPDATE positions SET state=?,payload=? WHERE key=?", (p["state"], canonical(p), key))
                event = f"{key}|leg-close|{len(p['legs'])}"
                db.execute("INSERT OR IGNORE INTO events VALUES (?,?,?,?)", (event, clock().isoformat(), "close", canonical(p["legs"][-1])))
                if alerts:
                    title = f"[v6] {p['symbol']} PAPER {'EXIT' if closed else 'ROLL CLOSE'}"
                    message = (f"{title}\n{p['contract']} · {p['trigger_reason']}\n"
                        f"paper midpoint ${basis['price']:.4f} · cumulative paper option return {p['return_factor'] - 1:+.1%}\n"
                        f"quote received {quote['received_at']} · no broker execution")
                    self._outbox(db, event, "notice", clock(), {"title": title, "message": message})
        # Closing transaction has committed. A failed opening quote leaves
        # roll_pending cash and never repeats the original sale on retry.
        if p["state"] == "roll_pending" and replacement:
            with self.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                p = json.loads(db.execute("SELECT payload FROM positions WHERE key=?", (key,)).fetchone()[0])
                if p["state"] != "roll_pending":
                    return p
                if replacement == p["contract"]:
                    raise ValueError("roll replacement must differ from expiring contract")
                decision = clock()
                after = pd.Timestamp(p["trigger_at"])
                quote = quote_loader(replacement, after=after)
                checked_quote(quote, replacement, clock(), after)
                basis = option_midpoint(quote)
                p.update(state="open", contract=replacement, entry_price=basis['price'] * (1 + COST), rolls=p["rolls"] + 1,
                         entry_reference=basis, pricing_policy=MIDPOINT_POLICY,
                         entry_quote=quote)
                db.execute("UPDATE positions SET state='open',payload=? WHERE key=?", (canonical(p), key))
                if alerts:
                    title = f"[v6] {p['symbol']} PAPER ROLL OPEN"
                    self._outbox(db, f"{key}|roll-open|{p['rolls']}", "notice", clock(),
                        {"title": title, "message": f"{title}\n{replacement} · simulated midpoint ${basis['price']:.4f}\nOriginal strategy and target DTE retained; no broker execution."})
        return p

    def summary(self):
        with self.connect() as db:
            return {"equity": float(db.execute("SELECT value FROM metadata WHERE key='equity'").fetchone()[0]),
                "positions": dict(db.execute("SELECT state,count(*) FROM positions GROUP BY state").fetchall()),
                "cycles": db.execute("SELECT count(*) FROM cycles").fetchone()[0],
                "outbox": dict(db.execute("SELECT status,count(*) FROM outbox GROUP BY status").fetchall()),
                "execution": "experimental fractional midpoint paper; 0.15% cost per side; completed legacy records preserved"}

    def export(self, directory):
        """Atomic immutable spool files; export retries survive process crashes."""
        import fcntl
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        with (directory/'.export.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            return self._export_locked(directory)

    def _export_locked(self, directory):
        from nn_meta.live.v6_market import save
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            rows = db.execute("SELECT * FROM outbox WHERE status IN ('pending','exported') ORDER BY key").fetchall()
        for row in rows:
            event = {"schema": "v6-forward-alert-v1", "experimental": True, "key": row["key"],
                "kind": row["kind"], "created_at": row["created_at"], "payload": json.loads(row["payload"])}
            path = directory / (hashlib.sha256(row["key"].encode()).hexdigest() + ".json")
            if path.exists():
                if json.loads(path.read_text()) != event:
                    raise ValueError("exported V6 event changed")
            else:
                save(path, event)
            with self.connect() as db:
                db.execute("UPDATE outbox SET status='exported' WHERE key=?", (row["key"],))
        return len(rows)
