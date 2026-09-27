import { useMemo, useState, type ReactNode } from "react";
import {
  CandlestickChart,
  ClipboardList,
  Search,
  Target,
  Trophy,
  Users,
} from "lucide-react";
import "./sports.css";
import {
  STRATEGIES,
  ema,
  filterBoard,
  lineupsByStrategy,
  searchPlayers,
  trackSummary,
  type BoardRow,
  type BoardSort,
  type HistoryPlayer,
  type Lineup,
  type SportsHistory,
  type SportsLatest,
} from "./sportsModel";

export const sportsTabs = [
  ["Lineups", ClipboardList],
  ["Player chart", CandlestickChart],
  ["Player board", Users],
  ["Track record", Trophy],
  ["Underdog", Target],
] as const;
export type SportsTab = (typeof sportsTabs)[number][0];
export const sportsHeadings: Record<SportsTab, [string, string]> = {
  Lineups: [
    "This week's lineups.",
    "Top DraftKings Classic lineups for each strategy, built on one gated slate.",
  ],
  "Player chart": [
    "Every player, charted.",
    "DraftKings points game by game, with 3- and 8-game moving averages.",
  ],
  "Player board": [
    "The whole slate.",
    "Salary, projection, boom scores, depth-chart role, and every exclusion.",
  ],
  "Track record": [
    "Projected vs. actual.",
    "Forward-logged lineups scored after the games — the only honest scoreboard.",
  ],
  Underdog: [
    "Underdog desk.",
    "Paper-traded pick'em: priced legs, tracked entries, and calibration.",
  ],
};

const f1 = (n: number | null | undefined) =>
  n === null || n === undefined ? "—" : n.toFixed(1);
const f2 = (n: number | null | undefined) =>
  n === null || n === undefined ? "—" : n.toFixed(2);
const pct = (n: number | null | undefined) =>
  n === null || n === undefined ? "—" : `${(n * 100).toFixed(1)}%`;
const usd = (n: number) => `$${n.toLocaleString("en-US")}`;
const REASONS: Record<string, string> = {
  backup_qb: "Backup QB",
  not_on_depth_chart: "Not on depth chart",
  depth_unverified_zero_history: "No history, unverified",
};

function Panel({
  title,
  aside,
  children,
}: {
  title: string;
  aside?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}
function Table({
  label,
  columns,
  rows,
  empty = "Nothing to show yet.",
}: {
  label: string;
  columns: string[];
  rows: ReactNode[][];
  empty?: string;
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
      {!rows.length && <p className="footnote">{empty}</p>}
    </div>
  );
}
function Unavailable({ what }: { what: string }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{what} unavailable</h2>
      </div>
      <p className="footnote">
        Publish from DraftKings-Scripts with{" "}
        <code>python -m dfs.site --publish</code> after{" "}
        <code>python -m dfs.compare</code>.
      </p>
    </section>
  );
}

export function Sports({
  tab,
  latest,
  history,
  onTab,
}: {
  tab: SportsTab;
  latest: SportsLatest | null;
  history: SportsHistory | null;
  onTab: (tab: SportsTab) => void;
}) {
  const [chartId, setChartId] = useState<string | null>(null);
  const openChart = (id: string | null) => {
    if (!id) return;
    setChartId(id);
    onTab("Player chart");
  };
  if (tab === "Player chart")
    return history ? (
      <PlayerChart
        history={history}
        board={latest?.board ?? []}
        selected={chartId}
        onSelect={setChartId}
      />
    ) : (
      <Unavailable what="Player history" />
    );
  if (!latest) return <Unavailable what="Sports summary" />;
  if (tab === "Lineups")
    return <Lineups latest={latest} onPlayer={openChart} />;
  if (tab === "Player board")
    return <Board rows={latest.board} onPlayer={openChart} />;
  if (tab === "Track record") return <Track rows={latest.track} />;
  return <Underdog data={latest.underdog} week={latest.week} />;
}

function Lineups({
  latest,
  onPlayer,
}: {
  latest: SportsLatest;
  onPlayer: (id: string | null) => void;
}) {
  const groups = lineupsByStrategy(latest.lineups);
  const run = latest.run;
  return (
    <>
      <div className="metrics">
        <div className="metric">
          <span>Slate</span>
          <strong>
            {latest.season} · Wk {latest.week}
          </strong>
          <small>DK group {run?.slate ?? "—"}</small>
        </div>
        <div className="metric">
          <span>Built</span>
          <strong className="sports-small">
            {run
              ? new Date(run.createdAt).toLocaleString("en-US", {
                  timeZone: "America/Chicago",
                  weekday: "short",
                  hour: "numeric",
                  minute: "2-digit",
                })
              : "—"}
          </strong>
          <small>Re-run close to lock</small>
        </div>
        <div className="metric">
          <span>Rules</span>
          <strong className="sports-small">
            ≤{run?.maxPerTeam ?? "—"} per team
          </strong>
          <small>
            {run?.minUnique ?? "—"}+ unique players · DST never faces your
            players
          </small>
        </div>
        <div className="metric">
          <span>Players on slate</span>
          <strong>{latest.board.filter((b) => !b.excluded).length}</strong>
          <small>
            {latest.board.filter((b) => b.excluded).length} excluded by depth
            gate
          </small>
        </div>
      </div>
      {!groups.length && <Unavailable what="This week's lineups" />}
      {groups.map(([strategy, lineups]) => (
        <Panel
          key={strategy}
          title={`${strategy} · ${STRATEGIES[strategy] ?? strategy}`}
          aside={
            <span className="muted">
              {strategy === "A"
                ? "Production default"
                : strategy === "C" || strategy === "D"
                  ? "Optimizes P(boom) × points if boom"
                  : "Research"}
            </span>
          }
        >
          <div className="sports-lineups">
            {lineups.map((l) => (
              <LineupCard key={l.rank} lineup={l} onPlayer={onPlayer} />
            ))}
          </div>
        </Panel>
      ))}
    </>
  );
}

function LineupCard({
  lineup,
  onPlayer,
}: {
  lineup: Lineup;
  onPlayer: (id: string | null) => void;
}) {
  return (
    <div className="sports-lineup">
      <div className="sports-lineup-head">
        <b>#{lineup.rank}</b>
        <span>{usd(lineup.salary)}</span>
        <span>proj {f1(lineup.proj)}</span>
        {lineup.status === "settled" ? (
          <span className="sports-actual">actual {f1(lineup.actual)}</span>
        ) : (
          <span className="muted">{lineup.status}</span>
        )}
      </div>
      <ul>
        {lineup.players.map((p) => (
          <li key={`${p.slot}-${p.name}`}>
            <span className="sports-slot">{p.slot}</span>
            <button className="sports-link" onClick={() => onPlayer(p.id)}>
              {p.name}
            </button>
            <span className="muted">{p.team}</span>
            <span className="sports-num">{usd(p.salary)}</span>
            <span className="sports-num">{f1(p.proj)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

const SORTS: [BoardSort, string][] = [
  ["proj", "Projection"],
  ["value", "Pts per $1k"],
  ["boomC", "Boom C"],
  ["boomD", "Boom D"],
  ["ceiling", "Ceiling (B)"],
  ["salary", "Salary"],
];
function Board({
  rows,
  onPlayer,
}: {
  rows: BoardRow[];
  onPlayer: (id: string | null) => void;
}) {
  const [query, setQuery] = useState(""),
    [position, setPosition] = useState("ALL"),
    [showExcluded, setShowExcluded] = useState(false),
    [sort, setSort] = useState<BoardSort>("proj");
  const shown = filterBoard(rows, { query, position, showExcluded }, sort);
  return (
    <Panel
      title={`${shown.length} players`}
      aside={
        <div className="sports-controls">
          <label className="search">
            <Search size={15} />
            <input
              aria-label="Search players"
              placeholder="Player or team"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <select
            aria-label="Position"
            value={position}
            onChange={(e) => setPosition(e.target.value)}
          >
            {["ALL", "QB", "RB", "WR", "TE", "DST"].map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
          <select
            aria-label="Sort by"
            value={sort}
            onChange={(e) => setSort(e.target.value as BoardSort)}
          >
            {SORTS.map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </select>
          <label className="sports-toggle">
            <input
              type="checkbox"
              checked={showExcluded}
              onChange={(e) => setShowExcluded(e.target.checked)}
            />
            Excluded
          </label>
        </div>
      }
    >
      <Table
        label="Player board"
        columns={[
          "Player",
          "Pos",
          "Team",
          "Opp",
          "Salary",
          "Proj",
          "Pts/$1k",
          "Boom C",
          "Boom D",
          "Ceiling",
          "Depth",
          "Status",
        ]}
        rows={shown.slice(0, 250).map((r) => [
          <button className="sports-link" onClick={() => onPlayer(r.id)}>
            {r.name}
          </button>,
          r.position,
          r.team,
          r.opponent ?? "—",
          usd(r.salary),
          f1(r.proj),
          f2(r.value),
          f1(r.boomC),
          f1(r.boomD),
          f1(r.ceiling),
          r.depth ?? "—",
          r.excluded ? (
            <span className="sports-excluded">
              {REASONS[r.excluded] ?? r.excluded}
            </span>
          ) : (
            (r.status ?? "")
          ),
        ])}
        empty="No players match these filters."
      />
      {shown.length > 250 && (
        <p className="footnote">Showing the first 250; narrow the search.</p>
      )}
    </Panel>
  );
}

function Track({ rows }: { rows: SportsLatest["track"] }) {
  const summary = trackSummary(rows);
  return (
    <>
      <Panel title="By strategy (settled lineups)">
        <Table
          label="Track record summary"
          columns={[
            "Source",
            "Lineups",
            "Avg projected",
            "Avg actual",
            "Actual − proj",
          ]}
          rows={summary.map((s) => [
            s.source,
            s.lineups,
            f1(s.proj),
            <b>{f1(s.actual)}</b>,
            <span className={s.actual >= s.proj ? "sports-up" : "sports-down"}>
              {(s.actual - s.proj >= 0 ? "+" : "") + f1(s.actual - s.proj)}
            </span>,
          ])}
          empty="No settled lineups yet — score with python -m dfs.forwardlog after the games."
        />
      </Panel>
      <Panel title="Every logged lineup">
        <Table
          label="Track record detail"
          columns={["Week", "Source", "Projected", "Actual", "Status", "Run"]}
          rows={[...rows]
            .reverse()
            .map((r) => [
              r.week,
              r.source,
              f1(r.proj),
              f1(r.actual),
              r.status,
              <span className="muted">{r.file}</span>,
            ])}
        />
      </Panel>
    </>
  );
}

function Underdog({
  data,
  week,
}: {
  data: SportsLatest["underdog"];
  week: number;
}) {
  const tiles = data.tiles;
  return (
    <>
      <Panel title="Results by week">
        <Table
          label="Underdog results"
          columns={[
            "Week",
            "Priced picks",
            "Hit rate",
            "Predicted",
            "Tracked entries",
            "Entries hit",
            "Expected hits",
          ]}
          rows={data.results.map((r) => [
            r.week,
            r.picks ?? "—",
            pct(r.hitRate),
            pct(r.predicted),
            r.entries ?? "—",
            r.entriesHit ?? "—",
            f2(r.expectedHits),
          ])}
          empty="No scored weeks yet."
        />
        <p className="footnote">
          Paper-trade only until several weeks are scored. A hit rate below
          predicted means the model is overconfident.
        </p>
      </Panel>
      {Object.keys(tiles).length ? (
        <div className="metrics">
          <div className="metric">
            <span>Tracked entries</span>
            <strong>{tiles.entries ?? "—"}</strong>
            <small>{tiles.players ?? "—"} players</small>
          </div>
          <div className="metric">
            <span>Best entry P</span>
            <strong>{pct(tiles.best_p)}</strong>
          </div>
          <div className="metric">
            <span>Expected hits</span>
            <strong>{f2(tiles.expected_hits)}</strong>
          </div>
          <div className="metric">
            <span>Unique legs</span>
            <strong>{tiles.unique_legs ?? "—"}</strong>
            <small>{tiles.consensus_legs ?? "—"} book-backed</small>
          </div>
        </div>
      ) : (
        <section className="panel">
          <p className="footnote">
            No tracked max-multiplier set for week {week} yet (
            <code>python -m dfs.maxmult --track 1000</code>).
          </p>
        </section>
      )}
      {data.frontier.length > 0 && (
        <Panel title="Unique frontier">
          <Table
            label="Frontier entries"
            columns={["#", "Legs", "Multiplier", "P(hit)", "Picks"]}
            rows={data.frontier.map((e) => [
              e.rank,
              e.k,
              `${Math.round(e.mult).toLocaleString()}x`,
              pct(e.p),
              e.legs
                .map((l) => `${l.name} ${l.side} ${l.line} ${l.stat}`)
                .join(" · "),
            ])}
          />
        </Panel>
      )}
      {data.edges.length > 0 && (
        <Panel title="Sharpest single legs">
          <Table
            label="Top edges"
            columns={["Player", "Stat", "Line", "Side", "Model P", "Median"]}
            rows={data.edges.map((e) => [
              e.name,
              e.stat,
              e.line,
              e.side,
              pct(e.p),
              f1(e.q50),
            ])}
          />
        </Panel>
      )}
      {data.td_gaps.length > 0 && (
        <Panel title="Where Underdog pays too much — TD legs">
          <Table
            label="TD gaps"
            columns={["Player", "UD mult", "UD implied", "Books", "Blend"]}
            rows={data.td_gaps.map((t) => [
              t.name,
              `${t.display_mult}x`,
              pct(t.ud),
              pct(t.books),
              pct(t.blend),
            ])}
          />
        </Panel>
      )}
    </>
  );
}

const RANGES = [
  ["This season", 1],
  ["2 seasons", 2],
  ["All", 99],
] as const;
function PlayerChart({
  history,
  board,
  selected,
  onSelect,
}: {
  history: SportsHistory;
  board: BoardRow[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const [query, setQuery] = useState(""),
    [range, setRange] = useState<number>(2);
  const byId = useMemo(
    () => new Map(history.players.map((p) => [p.id, p])),
    [history],
  );
  const boardById = useMemo(() => {
    const m = new Map<string, BoardRow>();
    // DST ids are DST_<nflverse team>, matching the history document
    for (const b of board) if (b.id) m.set(b.id, b);
    return m;
  }, [board]);
  // default: highest-projected player with history, like a watchlist leader
  const fallback =
    board.find((b) => b.id && !b.excluded && byId.has(b.id))?.id ??
    history.players[0]?.id;
  const player = byId.get(selected ?? "") ?? byId.get(fallback ?? "");
  const results = searchPlayers(history.players, query);
  return (
    <>
      <div className="sports-ticker">
        <label className="search">
          <Search size={15} />
          <input
            aria-label="Find a player"
            placeholder="Search a player — name or team"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        {results.length > 0 && (
          <ul className="sports-ticker-results" role="listbox">
            {results.map((p) => (
              <li key={p.id}>
                <button
                  onClick={() => {
                    onSelect(p.id);
                    setQuery("");
                  }}
                >
                  <b>{p.name}</b>
                  <span className="muted">
                    {p.position} · {p.team}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      {player ? (
        <ChartPanel
          player={player}
          row={boardById.get(player.id)}
          season={history.season}
          range={range}
          onRange={setRange}
        />
      ) : (
        <Unavailable what="Player history" />
      )}
    </>
  );
}

function ChartPanel({
  player,
  row,
  season,
  range,
  onRange,
}: {
  player: HistoryPlayer;
  row: BoardRow | undefined;
  season: number;
  range: number;
  onRange: (n: number) => void;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const games = player.games.filter(([s]) => s > season - range);
  const pts = games.map((g) => g[2]);
  // moving averages over the full career window so the first visible
  // points are not cold-started
  const allPts = player.games.map((g) => g[2]);
  const offset = player.games.length - games.length;
  const ma3 = ema(allPts, 3).slice(offset),
    ma8 = ema(allPts, 8).slice(offset);
  const last = pts[pts.length - 1],
    prev = pts[pts.length - 2];
  const seasonPts = player.games.filter(([s]) => s === season).map((g) => g[2]);
  const seasonAvg = seasonPts.length
    ? seasonPts.reduce((a, b) => a + b, 0) / seasonPts.length
    : null;
  const proj = row?.proj ?? null;
  // chart geometry; the projection is plotted one step past the last game
  const W = 900,
    H = 320,
    L = 44,
    R = 18,
    T = 16,
    B = 34;
  const n = pts.length + (proj !== null ? 1 : 0);
  const hi = Math.max(10, ...pts, proj ?? 0) * 1.1,
    lo = Math.min(0, ...pts);
  const x = (i: number) => L + (n <= 1 ? 0 : (i / (n - 1)) * (W - L - R));
  const y = (v: number) => T + ((hi - v) / (hi - lo)) * (H - T - B);
  const line = (vals: number[]) =>
    vals
      .map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`)
      .join(" ");
  const area = pts.length
    ? `${line(pts)} L${x(pts.length - 1).toFixed(1)},${y(lo)} L${x(0).toFixed(1)},${y(lo)} Z`
    : "";
  const up = last !== undefined && prev !== undefined ? last >= prev : true;
  const seasonStarts = games
    .map((g, i) => (i > 0 && g[0] !== games[i - 1][0] ? i : -1))
    .filter((i) => i > 0);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => lo + t * (hi - lo));
  const hovered = hover !== null && hover < games.length ? games[hover] : null;
  return (
    <Panel
      title={player.name}
      aside={
        <div className="sports-range" role="group" aria-label="Range">
          {RANGES.map(([label, value]) => (
            <button
              key={label}
              className={range === value ? "active" : ""}
              onClick={() => onRange(value)}
            >
              {label}
            </button>
          ))}
        </div>
      }
    >
      <div className="sports-quote">
        <div>
          <span className="muted">
            {player.position} · {player.team}
            {row?.opponent ? ` · vs ${row.opponent} this week` : ""}
          </span>
          <strong className={up ? "sports-up" : "sports-down"}>
            {f1(last)} <small>pts last game</small>
          </strong>
          {last !== undefined && prev !== undefined && (
            <span className={up ? "sports-up" : "sports-down"}>
              {up ? "▲" : "▼"} {f1(Math.abs(last - prev))} vs previous game
            </span>
          )}
        </div>
        <dl>
          <div>
            <dt>This week</dt>
            <dd>{f1(proj)}</dd>
          </div>
          <div>
            <dt>{season} avg</dt>
            <dd>{f1(seasonAvg)}</dd>
          </div>
          <div>
            <dt>3-game MA</dt>
            <dd>{f1(ma3[ma3.length - 1])}</dd>
          </div>
          <div>
            <dt>8-game MA</dt>
            <dd>{f1(ma8[ma8.length - 1])}</dd>
          </div>
          <div>
            <dt>Salary</dt>
            <dd>{row ? usd(row.salary) : "—"}</dd>
          </div>
        </dl>
      </div>
      {pts.length ? (
        <div className="sports-chart">
          <svg
            viewBox={`0 0 ${W} ${H}`}
            role="img"
            aria-label={`${player.name} DraftKings points over ${pts.length} games`}
            onMouseLeave={() => setHover(null)}
            onMouseMove={(e) => {
              const box = e.currentTarget.getBoundingClientRect();
              const px = ((e.clientX - box.left) / box.width) * W;
              const i = Math.round(((px - L) / (W - L - R)) * (n - 1));
              setHover(Math.max(0, Math.min(n - 1, i)));
            }}
          >
            <defs>
              <linearGradient id="sports-fill" x1="0" x2="0" y1="0" y2="1">
                <stop
                  offset="0%"
                  stopColor={up ? "#9ce9c5" : "#f28b82"}
                  stopOpacity="0.28"
                />
                <stop
                  offset="100%"
                  stopColor={up ? "#9ce9c5" : "#f28b82"}
                  stopOpacity="0"
                />
              </linearGradient>
            </defs>
            {ticks.map((t) => (
              <g key={t}>
                <line
                  className="sports-grid"
                  x1={L}
                  x2={W - R}
                  y1={y(t)}
                  y2={y(t)}
                />
                <text x={L - 8} y={y(t) + 4} textAnchor="end">
                  {t.toFixed(0)}
                </text>
              </g>
            ))}
            {seasonStarts.map((i) => (
              <g key={i}>
                <line
                  className="sports-season"
                  x1={x(i - 0.5)}
                  x2={x(i - 0.5)}
                  y1={T}
                  y2={H - B}
                />
                <text x={x(i - 0.5) + 4} y={H - B + 16}>
                  {games[i][0]}
                </text>
              </g>
            ))}
            <text x={L} y={H - B + 16}>
              {games[0][0]}
            </text>
            <path d={area} fill="url(#sports-fill)" />
            <path
              className={`sports-line ${up ? "up" : "down"}`}
              d={line(pts)}
            />
            <path className="sports-ma3" d={line(ma3)} />
            <path className="sports-ma8" d={line(ma8)} />
            {proj !== null && (
              <>
                <line
                  className="sports-proj"
                  x1={x(pts.length - 1)}
                  y1={y(pts[pts.length - 1])}
                  x2={x(pts.length)}
                  y2={y(proj)}
                />
                <circle
                  className="sports-proj-dot"
                  cx={x(pts.length)}
                  cy={y(proj)}
                  r="5"
                />
              </>
            )}
            {hover !== null && (
              <line
                className="sports-cross"
                x1={x(hover)}
                x2={x(hover)}
                y1={T}
                y2={H - B}
              />
            )}
          </svg>
          <div className="sports-legend">
            <span className="sports-key line">Actual</span>
            <span className="sports-key ma3">3-game MA</span>
            <span className="sports-key ma8">8-game MA</span>
            {proj !== null && (
              <span className="sports-key proj">This week's projection</span>
            )}
            <span className="sports-hover">
              {hovered
                ? `${hovered[0]} wk ${hovered[1]}: ${f1(hovered[2])} pts · MA3 ${f1(ma3[hover!])} · MA8 ${f1(ma8[hover!])}`
                : hover !== null && proj !== null
                  ? `Week projection: ${f1(proj)} pts`
                  : "Hover the chart for a game"}
            </span>
          </div>
        </div>
      ) : (
        <p className="footnote">No games in this range.</p>
      )}
    </Panel>
  );
}
