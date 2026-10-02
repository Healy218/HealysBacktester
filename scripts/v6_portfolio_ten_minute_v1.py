"""Versioned PAPER allocation deadline; all other portfolio behavior inherited.

Loaded from the verified frozen checkout by the admitted scanner consumer.
"""
import json
import pandas as pd
from nn_meta.live.v6_portfolio import (
    ForwardPortfolio as FrozenPortfolio, choose, key_of, checked_quote, canonical,
    MIDPOINT_POLICY, COST, option_midpoint, V6_OPTION_RISK, asdict,
)

class ForwardPortfolio(FrozenPortfolio):
    def allocate(self, rows, *, bar, now, quote_loader, contexts, clock, alerts=False):
        """One immutable complete-universe allocation per closed signal bar.

        A selected but unfillable idea is recorded, not replaced by a lower-EV
        idea. Its quote rejection cannot silently change the model ranking.
        """
        bar = pd.Timestamp(bar)
        now = pd.Timestamp(now)
        close = bar.tz_localize("UTC") + pd.Timedelta(minutes=15) if bar.tzinfo is None else bar + pd.Timedelta(minutes=15)
        if not close <= now <= close + pd.Timedelta(minutes=10):
            raise ValueError("entry decision missed the ten-minute signal-close deadline")
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
                    if decision_at > close + pd.Timedelta(minutes=10):
                        raise ValueError("entry deadline elapsed before quote retrieval")
                    if not row.get("decision_contract") or row.get("option_tick_status") != "covered":
                        raise ValueError("selected candidate lacks complete contract tick inputs")
                    quote = quote_loader(row["decision_contract"], after=close)
                    filled = clock()
                    bid, ask = checked_quote(quote, row["decision_contract"], filled, close)
                    basis = option_midpoint(quote)
                    if pd.Timestamp(quote["received_at"]) < decision_at:
                        raise ValueError("execution quote was not retrieved for this decision")
                    if filled > close + pd.Timedelta(minutes=10):
                        raise ValueError("entry quote arrived after ten-minute deadline")
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
