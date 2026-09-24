import { useState, type ReactNode } from "react";
import { fresh } from "./model";
import {
  filterPositions,
  recentBrokerTrades,
  realizedPnlSeries,
  type ForwardData,
  type DeliveryData,
  type BrokerData,
} from "./forwardModel";
const pct = (n: number | null) =>
  n === null ? "—" : `${(n * 100).toFixed(2)}%`;
const time = (t: string | null) =>
  t
    ? new Date(t).toLocaleString("en-US", { timeZone: "America/Chicago" }) +
      " CT"
    : "—";
function Table({
  label,
  columns,
  rows,
}: {
  label: string;
  columns: string[];
  rows: ReactNode[][];
}) {
  return (
    <div className="table-wrap" role="region" aria-label={label} tabIndex={0}>
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {r.map((v, j) => (
                <td key={j}>{v}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && (
        <p className="footnote">No matching records in this capture.</p>
      )}
    </div>
  );
}
export function Forward({
  data,
  delivery,
  broker,
  now,
}: {
  data: ForwardData | null | undefined;
  delivery: DeliveryData | null | undefined;
  broker: BrokerData | null | undefined;
  now: number;
}) {
  const [state, setState] = useState("active"),
    [query, setQuery] = useState("");
  if (!data)
    return (
      <section className="panel">
        <h2>V6 paper evidence unavailable</h2>
        <p>The home publisher has not supplied a valid paper ledger capture.</p>
      </section>
    );
  const rows = filterPositions(data.positions, state, query);
  const active = Object.entries(data.counts).reduce(
    (n, [s, c]) => n + (s === "closed" ? 0 : c),
    0,
  );
  const current = fresh(data.observedAt, 180, now),
    delivered = delivery && fresh(delivery.observedAt, 180, now);
  const exportRows = () => {
    const content = {
      observedAt: data.observedAt,
      modelSha256: data.modelSha256,
      filter: { state, query },
      positions: rows,
      limitations: data.limitations,
    };
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(content, null, 2)], {
        type: "application/json",
      }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "v6-paper-positions.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return (
    <div className="forward-view">
      <section className="panel forward-status">
        <div className="panel-heading">
          <h2>Experimental paper</h2>
          <span className="tag neutral">
            {current ? data.phase.replaceAll("_", " ") : "Stale capture"}
          </span>
        </div>
        <p>
          Fractional positions · ask to buy, bid to sell · 0.15% modeled cost
          per side · no broker orders
        </p>
        <p className="footnote">
          Captured {time(data.observedAt)} · last scanner check{" "}
          {time(data.checkedAt)} · data through {data.dataThrough ?? "—"}
        </p>
        {!!data.issues.length && (
          <ul>
            {data.issues.map((i) => (
              <li key={i}>{i}</li>
            ))}
          </ul>
        )}
      </section>
      {broker && <BrokerAccount data={broker} />}
      <div className="forward-metrics">
        {[
          ["Active positions", `${active} / 5`],
          ["Closed positions", data.counts.closed ?? 0],
          ["Realized contribution", pct(data.realizedContribution)],
          ["Completed rolls", data.totalRolls],
        ].map(([label, value]) => (
          <section className="panel" key={label}>
            <small>{label}</small>
            <strong>{value}</strong>
          </section>
        ))}
      </div>
      <p className="footnote">
        Realized contribution is closed-position P&amp;L divided by starting
        portfolio capital. Open positions have no current valuation.
      </p>
      <section className="panel">
        <div className="panel-heading">
          <h2>Paper positions</h2>
          <button className="button small" onClick={exportRows}>
            Export filtered positions
          </button>
        </div>
        <div className="forward-controls">
          <label>
            Position state{" "}
            <select value={state} onChange={(e) => setState(e.target.value)}>
              <option value="active">Active</option>
              <option value="closed">Closed</option>
              <option value="all">All</option>
            </select>
          </label>
          <label>
            Symbol or contract{" "}
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search positions"
            />
          </label>
          <button
            className="button small"
            onClick={() => {
              setState("active");
              setQuery("");
            }}
          >
            Reset
          </button>
        </div>
        <Table
          label="Paper positions"
          columns={[
            "Symbol / strategy",
            "Contract",
            "State",
            "Allocation at entry",
            "Entry ask",
            "Opened",
            "Rolls",
            "Closed return",
          ]}
          rows={rows.map((p) => [
            <span>
              <b>{p.symbol}</b>
              <small>{p.strategy.replaceAll("_", " ")}</small>
            </span>,
            p.contract,
            p.state.replaceAll("_", " "),
            pct(p.allocation),
            p.entryAsk === null ? "—" : `$${p.entryAsk.toFixed(2)}`,
            time(p.openedAt),
            p.rolls,
            pct(p.realizedReturn),
          ])}
        />
        <p className="footnote">
          {rows.length} shown from {data.positions.length} retained records;{" "}
          {data.totalPositions} positions in the full ledger. Entry asks are
          historical observations.
        </p>
      </section>
      <div className="forward-grid">
        <section className="panel">
          <h2>Relay and delivery</h2>
          <dl>
            <dt>Home relay</dt>
            <dd>
              {data.relay.status} · {time(data.relay.at)}
            </dd>
            <dt>Relayed event files</dt>
            <dd>{data.relay.events ?? "—"}</dd>
            <dt>Confirmed server sends</dt>
            <dd>
              {delivered ? (delivery.counts.sent ?? 0) : "Unavailable / stale"}
            </dd>
            <dt>Pending server notices</dt>
            <dd>{delivered ? (delivery.counts.pending ?? 0) : "Unknown"}</dd>
          </dl>
          <p className="footnote">
            A successful relay confirms transfer to the server. Send counts
            require a fresh server dispatcher capture.
          </p>
        </section>
        <section className="panel">
          <h2>Recorded execution evidence</h2>
          <dl>
            <dt>Quote records checked</dt>
            <dd>
              {data.quoteCoverage.valid} / {data.quoteCoverage.observed}
            </dd>
            <dt>With provider receipts</dt>
            <dd>
              {data.quoteCoverage.withReceipts} / {data.quoteCoverage.observed}
            </dd>
            <dt>Archived unique quote records</dt>
            <dd>{data.history?.uniqueQuotes ?? "Unavailable"}</dd>
            <dt>Observed failed passes</dt>
            <dd>{data.history?.failedPassesObserved ?? "Unavailable"}</dd>
          </dl>
          <p className="footnote">
            Current-entry and recent close quotes only. Receipt presence does
            not establish raw-page integrity or complete roll history.
          </p>
        </section>
      </div>
      <section className="panel">
        <h2>Recent paper exits and roll closes</h2>
        <Table
          label="Paper exits"
          columns={[
            "Contract",
            "Reason",
            "Trigger",
            "Quote received",
            "Quote age",
            "Bid",
            "Leg return",
          ]}
          rows={data.events.map((e) => [
            e.contract,
            e.reason,
            time(e.triggerAt),
            time(e.quoteReceivedAt),
            e.quoteAgeSeconds === null
              ? "—"
              : `${e.quoteAgeSeconds.toFixed(2)}s`,
            e.bid === null ? "—" : `$${e.bid.toFixed(2)}`,
            pct(e.legReturn),
          ])}
        />
      </section>
      <details className="panel">
        <summary>Allocation cycles · {data.cycles} total</summary>
        <Table
          label="Allocation cycles"
          columns={["Recorded", "Selected", "Opened", "Unfilled"]}
          rows={data.recentCycles.map((c) => [
            time(c.at),
            c.selected,
            c.opened,
            c.unfilled,
          ])}
        />
      </details>
      <details className="panel">
        <summary>Operating observations</summary>
        <p className="footnote">
          Collection began {time(data.history?.firstObservedAt ?? null)}.
          Samples can miss brief transitions between refreshes.
        </p>
        <Table
          label="Operating observations"
          columns={["Scanner check", "Status", "Phase"]}
          rows={(data.history?.recent ?? []).map((r) => [
            time(r.at),
            r.status,
            r.phase.replaceAll("_", " "),
          ])}
        />
      </details>
      <details className="panel">
        <summary>Scope and provenance</summary>
        <p className="footnote">
          Frozen model SHA-256: {data.modelSha256 ?? "Unavailable"}
        </p>
        <ul>
          {data.limitations.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </details>
    </div>
  );
}

function BrokerAccount({ data }: { data: BrokerData }) {
  const s = data.summary;
  const trades = recentBrokerTrades(data.trades);
  const series = realizedPnlSeries(data.trades);
  const usd = (n: number | null) =>
    n === null
      ? "—"
      : new Intl.NumberFormat("en-US", {
          style: "currency",
          currency: "USD",
        }).format(n);
  const pnl = (n: number | null) => {
    if (n === null) return "—";
    return <span className={n >= 0 ? "pnl-positive" : "pnl-negative"}>{usd(n)}</span>;
  };
  return (
    <>
      <section className="panel broker-account">
        <div className="panel-heading">
          <div>
            <h2>Broker-style paper account</h2>
            <p className="footnote">$10,000 starting capital · retroactive projection · no broker orders</p>
          </div>
          <span className="tag neutral">Read-only</span>
        </div>
        <div className="forward-metrics broker-metrics">
          {[
            ["Marked equity", usd(s.equity_usd_marked)],
            ["Realized P/L", pnl(s.realized_pnl_usd)],
            ["Marked open P/L", pnl(s.unrealized_pnl_usd_marked)],
            ["Marked total P/L", pnl(s.total_pnl_usd_marked)],
          ].map(([label, value]) => (
            <section className="panel" key={label as string}>
              <small>{label}</small>
              <strong>{value}</strong>
            </section>
          ))}
        </div>
        <p className="footnote">
          Entry pricing uses midpoint plus 0.15% modeled cost; open marks use midpoint minus 0.15%.
          {s.unmarked_open_trades ? ` ${s.unmarked_open_trades} open position lacks a fresh quote, so marked equity is incomplete.` : " All open positions are marked."}
        </p>
      </section>
      <section className="panel broker-chart">
        <div className="panel-heading">
          <div>
            <h2>Realized P/L over time</h2>
            <p className="footnote">Cumulative closed-trade P/L from the $10,000 paper account</p>
          </div>
          <strong className={s.realized_pnl_usd >= 0 ? "pnl-positive" : "pnl-negative"}>{usd(s.realized_pnl_usd)}</strong>
        </div>
        <RealizedPnlChart series={series} />
        <p className="footnote">Open-position marks are current snapshots and are excluded from this history. The chart uses dated closed trades supplied by the broker projection.</p>
      </section>
      <section className="panel">
        <div className="panel-heading">
          <h2>Broker-style trade history</h2>
          <span className="muted">{s.closed_trades} closed · {s.open_trades} open · captured {time(s.snapshot_at)}</span>
        </div>
        <Table
          label="Broker-style V6 trade history"
          columns={["Symbol / strategy", "State", "Opened", "Closed", "Allocation", "Entry net", "Mark net", "Realized P/L", "Unrealized P/L"]}
          rows={trades.map((t) => [
            <span><b>{t.symbol}</b><small>{t.strategy.replaceAll("_", " ")} · {t.contract}</small></span>,
            <span className={`tag ${t.state === "open" ? "good" : "neutral"}`}><i />{t.state}</span>,
            time(t.opened_at),
            time(t.closed_at),
            usd(t.allocation_usd),
            usd(t.entry_price_net),
            usd(t.mark_price_net),
            pnl(t.realized_pnl_usd),
            pnl(t.unrealized_pnl_usd),
          ])}
        />
        <p className="footnote">The research ledger remains unchanged. This account is a separately calculated broker-style projection, not a live brokerage account.</p>
      </section>
    </>
  );
}

function RealizedPnlChart({ series }: { series: ReturnType<typeof realizedPnlSeries> }) {
  if (series.length < 2) return <p className="footnote">No dated closed trades yet.</p>;
  const width = 800, height = 260, left = 64, right = 18, top = 16, bottom = 34;
  const minTime = series[0].at, maxTime = series[series.length - 1].at;
  const values = series.map((point) => point.pnl);
  const minimum = Math.min(0, ...values), maximum = Math.max(0, ...values);
  const pad = Math.max((maximum - minimum) * 0.1, 1);
  const low = minimum - pad, high = maximum + pad;
  const x = (at: number) => left + (maxTime === minTime ? 0 : (at - minTime) / (maxTime - minTime)) * (width - left - right);
  const y = (value: number) => top + (high - value) / (high - low) * (height - top - bottom);
  const path = series.map((point, index) => `${index ? "L" : "M"}${x(point.at).toFixed(1)},${y(point.pnl).toFixed(1)}`).join(" ");
  const currency = (value: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
  const date = (at: number) => new Date(at).toLocaleDateString("en-US", { timeZone: "America/Chicago", month: "short", day: "numeric", year: "numeric" });
  return (
    <div className="broker-chart-wrap">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Realized P/L from ${date(minTime)} to ${date(maxTime)}, ending at ${currency(series[series.length - 1].pnl)}`}>
        <line className="broker-chart-zero" x1={left} x2={width - right} y1={y(0)} y2={y(0)} />
        <path className="broker-chart-line" d={path} />
        <circle className="broker-chart-end" cx={x(maxTime)} cy={y(series[series.length - 1].pnl)} r="5" />
        <text x={left - 8} y={y(maximum)} textAnchor="end">{currency(maximum)}</text>
        <text x={left - 8} y={y(0) + 4} textAnchor="end">$0</text>
        <text x={left - 8} y={y(minimum) + 4} textAnchor="end">{currency(minimum)}</text>
        <text x={left} y={height - 5}>{date(minTime)}</text>
        <text x={width - right} y={height - 5} textAnchor="end">{date(maxTime)}</text>
      </svg>
    </div>
  );
}
