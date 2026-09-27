import { useEffect, useState, type ReactNode } from "react";
import {
  Activity,
  ArrowUpRight,
  Bell,
  ChevronRight,
  Database,
  FlaskConical,
  LayoutDashboard,
  LogOut,
  Radio,
  RefreshCw,
  Search,
  ShieldCheck,
  Wallet,
  X,
  Upload,
  Clock3,
  BookOpen,
} from "lucide-react";
import {
  sendEmailVerification,
  signInWithEmailAndPassword,
  signOut,
} from "firebase/auth";
import { auth, authReady, configured } from "./firebase";
import { useDashboard } from "./useDashboard";
import { Forward } from "./Forward";
import { Training } from "./Training";
import {
  Sports,
  sportsHeadings,
  sportsTabs,
  type SportsTab,
} from "./Sports";
import { useSports } from "./useSports";
import {
  sportsHistorySchema,
  sportsLatestSchema,
  type SportsHistory,
  type SportsLatest,
} from "./sportsModel";
import {
  ageSeconds,
  displayNumber as num,
  filteredSignals,
  fresh,
  homeSchema,
  scannerState,
  serverSchema,
  type HomeData,
  type ServerData,
  type Signal,
} from "./model";
const tabs = [
  ["Overview", LayoutDashboard],
  ["Signals", Radio],
  ["Positions", Wallet],
  ["V6 Paper", Activity],
  ["Research", FlaskConical],
  ["Training", BookOpen],
  ["FA", Database],
] as const;
const money = (n: number | null) =>
  n === null
    ? "—"
    : new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
      }).format(n);
const pct = (n: number | null) =>
  n === null ? "—" : `${(n * 100).toFixed(1)}%`;
function time(value: string | null | undefined) {
  return value
    ? new Date(value).toLocaleString("en-US", {
        timeZone: "America/Chicago",
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      })
    : "Not reported";
}
function ago(value: string | null | undefined, now: number) {
  const a = ageSeconds(value, now);
  return a === null
    ? "Unknown"
    : a < 60
      ? "Just now"
      : a < 3600
        ? `${Math.floor(a / 60)}m ago`
        : a < 86400
          ? `${Math.floor(a / 3600)}h ago`
          : `${Math.floor(a / 86400)}d ago`;
}
function Tag({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return (
    <span className={`tag ${tone}`}>
      <i />
      {children}
    </span>
  );
}
function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="empty">
      <Database size={24} />
      <p>{children}</p>
    </div>
  );
}
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
function Metric({
  label,
  value,
  detail,
}: {
  label: string;
  value: ReactNode;
  detail: string;
}) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}
function Signals({
  rows,
  onSelect,
  compact = false,
}: {
  rows: Signal[];
  onSelect: (s: Signal) => void;
  compact?: boolean;
}) {
  const [query, setQuery] = useState(""),
    [expert, setExpert] = useState("all"),
    [status, setStatus] = useState("all");
  const filtered = filteredSignals(rows, query, expert, status);
  const visible = compact ? filtered.slice(0, 5) : filtered;
  return (
    <>
      {!compact && (
        <div className="filters">
          <label className="search">
            <Search size={16} />
            <input
              aria-label="Search signals"
              placeholder="Symbol, strategy or trade ID"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <select
            aria-label="Expert"
            value={expert}
            onChange={(e) => setExpert(e.target.value)}
          >
            <option value="all">All experts</option>
            {["v3", "v31", "v4", "v5", "v6"].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
          <select
            aria-label="Delivery status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="all">All statuses</option>
            {[...new Set(rows.map((r) => r.status))].sort().map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
          <span className="muted">{filtered.length} records</span>
        </div>
      )}
      {visible.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Symbol / strategy</th>
                <th>Direction</th>
                <th>Expert</th>
                <th>Score</th>
                <th>Delivery</th>
                <th>Candidate time · CT</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {visible.map((r) => (
                <tr key={r.id}>
                  <td>
                    <b>{r.symbol}</b>
                    <small>{r.strategy || r.id}</small>
                  </td>
                  <td>{r.side}</td>
                  <td>
                    <span className="expert">{r.expert}</span>
                  </td>
                  <td className="numeric">{pct(r.score)}</td>
                  <td>
                    <Tag
                      tone={
                        r.status === "sent"
                          ? "good"
                          : r.status.startsWith("suppressed")
                            ? "neutral"
                            : "warn"
                      }
                    >
                      {r.status.replaceAll("_", " ")}
                    </Tag>
                  </td>
                  <td className="muted">{time(r.candidateAt)}</td>
                  <td>
                    <button
                      className="icon-button"
                      aria-label={`Inspect ${r.symbol} ${r.id}`}
                      onClick={() => onSelect(r)}
                    >
                      <ChevronRight size={18} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty>
          {rows.length
            ? "No signals match these filters."
            : "No candidate records in the reported window."}
        </Empty>
      )}
    </>
  );
}
export default function App() {
  const live = useDashboard();
  const [tab, setTab] = useState("Overview"),
    [now, setNow] = useState(Date.now());
  // Stocks and Sports are separate workspaces with separate data documents.
  const [workspace, setWorkspace] = useState<"stocks" | "sports">("stocks"),
    [sportsTab, setSportsTab] = useState<SportsTab>("Lineups");
  const sports = useSports(live.user, workspace === "sports");
  const [preview, setPreview] = useState<{
      server: ServerData | null;
      home: HomeData | null;
      sports?: { latest: SportsLatest | null; history: SportsHistory | null };
    } | null>(null),
    [previewError, setPreviewError] = useState("");
  const [selected, setSelected] = useState<Signal | null>(null),
    [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [loginError, setLoginError] = useState(""),
    [signing, setSigning] = useState(false),
    [faQuery, setFaQuery] = useState("");
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 15000);
    return () => clearInterval(id);
  }, []);
  useEffect(() => {
    setSelected(null);
  }, [live.user]);
  useEffect(() => {
    if (!selected) return;
    const esc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelected(null);
    };
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [selected]);
  const server = preview ? preview.server : live.server,
    home = preview ? preview.home : live.home;
  const sportsLatest = preview ? (preview.sports?.latest ?? null) : sports.latest,
    sportsHistory = preview ? (preview.sports?.history ?? null) : sports.history;
  const isSports = workspace === "sports",
    activeTab = isSports ? sportsTab : tab;
  async function importPreview(file: File | undefined) {
    if (!file) return;
    try {
      if (file.size > 3000000) throw Error();
      const raw = JSON.parse(await file.text());
      setPreview({
        server: raw.server ? serverSchema.parse(raw.server) : null,
        home: raw.home ? homeSchema.parse(raw.home) : null,
        sports: raw.sports
          ? {
              latest: raw.sports.latest
                ? sportsLatestSchema.parse(raw.sports.latest)
                : null,
              history: raw.sports.history
                ? sportsHistorySchema.parse(raw.sports.history)
                : null,
            }
          : undefined,
      });
      setPreviewError("");
    } catch {
      setPreviewError("This file is not a valid dashboard snapshot.");
    }
  }
  const previewControl = import.meta.env.DEV ? (
    <label className="button secondary file">
      <Upload size={16} />
      Open local snapshot
      <input
        aria-label="Open local snapshot"
        type="file"
        accept="application/json"
        onChange={(e) => void importPreview(e.target.files?.[0])}
      />
    </label>
  ) : null;
  if (!live.user && !preview)
    return (
      <main className="login-page">
        <div className="login-brand">
          <span className="brand-mark">
            <Activity />
          </span>
          HEALY<span>LABS</span>
        </div>
        <div className="login-card">
          <div className="eyebrow">YOUR TRADING OBSERVATORY</div>
          <h1>
            The whole picture.
            <br />
            <span>One place.</span>
          </h1>
          <p>Signals, positions, research, and the systems behind them.</p>
          {configured ? (
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                setSigning(true);
                setLoginError("");
                try {
                  await authReady;
                  await signInWithEmailAndPassword(auth!, email, password);
                } catch {
                  setLoginError(
                    "Could not sign in. Check your credentials and connection.",
                  );
                } finally {
                  setSigning(false);
                }
              }}
            >
              <label>
                Email
                <input
                  type="email"
                  autoComplete="username"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </label>
              <label>
                Password
                <input
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </label>
              <button
                className="button primary"
                disabled={signing || live.authLoading}
              >
                {signing ? "Signing in…" : "Sign in"}
                <ArrowUpRight size={17} />
              </button>
              {loginError && <p role="alert">{loginError}</p>}
            </form>
          ) : (
            <div className="setup-note">
              <ShieldCheck size={20} />
              <div>
                <b>Firebase connection pending</b>
                <p>
                  The app is ready for your private project. Configure the web
                  app settings to enable sign-in.
                </p>
              </div>
            </div>
          )}
          {previewControl}
          {previewError && <p role="alert">{previewError}</p>}
          <small className="login-foot">
            Private access · Read-only monitoring
          </small>
        </div>
      </main>
    );
  const serverFresh = !!server && fresh(server.observedAt, 180, now),
    homeFresh = !!home && fresh(home.observedAt, 180, now);
  const reporting = server?.scanners.filter(
    (s) => scannerState(s, server.market, now) === "reporting",
  ).length;
  const counts = server?.queueCounts ?? {};
  const sent = server?.queueAvailable ? (counts.sent ?? 0) : null;
  const queued = server?.queueAvailable
    ? (counts.pending ?? 0) + (counts.selected ?? 0)
    : null;
  const suppressed = server?.queueAvailable
    ? Object.entries(counts)
        .filter(([k]) => k.startsWith("suppressed"))
        .reduce((a, [, n]) => a + n, 0)
    : null;
  const issues = [
    ...(!serverFresh ? ["Server summary is missing or stale."] : []),
    ...(!homeFresh ? ["Home summary is missing or stale."] : []),
    ...(server?.issues ?? []),
    ...(home?.issues ?? []),
    ...(!preview ? live.errors : []),
  ];
  const faRows =
    home?.fa.rows.filter((r) =>
      r.ticker.toLowerCase().includes(faQuery.toLowerCase()),
    ) ?? [];
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            if (isSports) setSportsTab("Lineups");
            else setTab("Overview");
          }}
        >
          <span className="brand-mark">
            <Activity size={22} />
          </span>
          <span>
            HEALY<b>LABS</b>
          </span>
        </a>
        <div className="sidebar-caption">
          {isSports ? "SPORTS · DRAFTKINGS" : "OBSERVATORY"}
        </div>
        <nav aria-label="Main navigation">
          {(isSports ? sportsTabs : tabs).map(([name, Icon]) => (
            <button
              key={name}
              className={activeTab === name ? "active" : ""}
              onClick={() =>
                isSports ? setSportsTab(name as SportsTab) : setTab(name)
              }
            >
              <Icon size={19} />
              <span>{name}</span>
              {activeTab === name && <i />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <ShieldCheck size={17} />
          <span>
            Read-only workspace<small>Trading controls stay separate</small>
          </span>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <span className="breadcrumb">
            {isSports ? "Sports" : "Stocks"} <ChevronRight size={14} />{" "}
            <b>{activeTab}</b>
          </span>
          <div className="workspace-switch" role="group" aria-label="Workspace">
            <button
              className={!isSports ? "active" : ""}
              aria-pressed={!isSports}
              onClick={() => setWorkspace("stocks")}
            >
              Stocks
            </button>
            <button
              className={isSports ? "active" : ""}
              aria-pressed={isSports}
              onClick={() => setWorkspace("sports")}
            >
              Sports
            </button>
          </div>
          <div className="top-actions">
            <span className="clock">
              <Clock3 size={14} />
              {new Date(now).toLocaleTimeString("en-US", {
                timeZone: "America/Chicago",
                hour: "numeric",
                minute: "2-digit",
              })}{" "}
              CT
            </span>
            <button
              className="icon-button"
              aria-label="Refresh data"
              disabled={(isSports ? sports.loading : live.loading) || !!preview}
              onClick={isSports ? sports.refresh : live.refresh}
            >
              <RefreshCw
                size={17}
                className={
                  (isSports ? sports.loading : live.loading) ? "spinning" : ""
                }
              />
            </button>
            {preview ? (
              <button
                className="button small"
                onClick={() => {
                  setPreview(null);
                  setSelected(null);
                }}
              >
                Exit preview
              </button>
            ) : (
              <button
                className="icon-button"
                aria-label="Sign out"
                onClick={() => void signOut(auth!)}
              >
                <LogOut size={17} />
              </button>
            )}
          </div>
        </header>
        <main className="content">
          {isSports ? (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">
                    HEALYLABS / SPORTS / {sportsTab.toUpperCase()}
                  </div>
                  <h1>{sportsHeadings[sportsTab][0]}</h1>
                  <p>{sportsHeadings[sportsTab][1]}</p>
                </div>
                <Tag tone={sportsLatest ? "good" : "neutral"}>
                  {sportsLatest
                    ? `${sportsLatest.season} · Week ${sportsLatest.week}`
                    : "No DFS capture"}
                </Tag>
              </div>
              {[
                ...(sportsLatest?.issues ?? []),
                ...(!preview ? sports.errors : []),
              ].length > 0 && (
                <details className="banner issues">
                  <summary>
                    <Bell size={17} />
                    Sports items to review
                  </summary>
                  <ul>
                    {[
                      ...(sportsLatest?.issues ?? []),
                      ...(!preview ? sports.errors : []),
                    ].map((x, i) => (
                      <li key={i}>{x}</li>
                    ))}
                  </ul>
                </details>
              )}
              <Sports
                tab={sportsTab}
                latest={sportsLatest}
                history={sportsHistory}
                onTab={setSportsTab}
              />
            </>
          ) : (
          <>
          <div className="page-heading">
            <div>
              <div className="eyebrow">HEALYLABS / {tab.toUpperCase()}</div>
              <h1>
                {tab === "Overview"
                  ? "Your market, in view."
                  : tab === "Signals"
                    ? "Follow every signal."
                    : tab === "V6 Paper"
                      ? "V6 paper portfolio"
                    : tab === "Positions"
                      ? "Your taken trades."
                      : tab === "Research"
                        ? "From build to evidence."
                        : tab === "Training"
                          ? "Every generation, on record."
                          : "Fundamentals in focus."}
              </h1>
              <p>
                {tab === "Overview"
                  ? "A clear view of your trading systems and the activity they report."
                  : tab === "Signals"
                    ? "Follow candidates through ranking and actual delivery."
                    : tab === "V6 Paper"
                      ? "Positions, paper exits, and operating evidence."
                    : tab === "Positions"
                      ? "Recorded fills and observed quotes, with accounting gaps visible."
                      : tab === "Research"
                        ? "Progress receipts and completed artifacts from the home machine."
                        : tab === "Training"
                          ? "Training summaries, evaluation results, and the evidence behind each model."
                          : "Point-in-time news, sentiment, and company data."}
              </p>
            </div>
            <Tag
              tone={
                serverFresh && server?.market === "open" ? "good" : "neutral"
              }
            >
              {!serverFresh
                ? "Session at last capture"
                : server?.market === "open"
                  ? "Market open"
                  : server?.market === "closed"
                    ? "Market closed"
                    : "Session unknown"}
            </Tag>
          </div>
          {live.user && !live.user.emailVerified && !preview && (
            <div className="banner">
              <p>Verify your email before accessing private observations.</p>
              <button
                className="button small"
                onClick={() =>
                  void sendEmailVerification(live.user!)
                    .then(() =>
                      setLoginError(
                        "Verification email sent. After verifying, sign out and sign in again.",
                      ),
                    )
                    .catch(() =>
                      setLoginError(
                        "Could not send verification email. Please try again later.",
                      ),
                    )
                }
              >
                Send verification email
              </button>
              <p>{loginError}</p>
            </div>
          )}
          {preview && (
            <div className="banner preview">
              <FlaskConical size={17} />
              <span>
                <b>Local snapshot preview.</b> These are captured observations,
                not a live connection.
              </span>
            </div>
          )}
          {issues.length > 0 && (
            <details className="banner issues">
              <summary>
                <Bell size={17} />
                {issues.length} item{issues.length === 1 ? "" : "s"} to review
              </summary>
              <ul>
                {issues.map((x, i) => (
                  <li key={i}>{x}</li>
                ))}
              </ul>
            </details>
          )}
          {tab === "Overview" && (
            <>
              <div className="metrics">
                <Metric
                  label="Scanners reporting"
                  value={
                    server?.market === "open"
                      ? `${reporting} / ${server.scanners.length}`
                      : server?.market === "closed"
                        ? "Off session"
                        : "—"
                  }
                  detail={
                    server?.market === "closed"
                      ? "Off-session · see last completions"
                      : "Completion within 25 minutes during RTH"
                  }
                />
                <Metric
                  label="Alerts sent"
                  value={num(sent)}
                  detail="Delivery status · today’s candidate cohorts"
                />
                <Metric
                  label="Awaiting delivery"
                  value={num(queued)}
                  detail="Pending or selected candidates"
                />
                <Metric
                  label="Open positions"
                  value={
                    server?.positionsAvailable
                      ? num(server.openPositionCount)
                      : "—"
                  }
                  detail="User-confirmed taken trades"
                />
              </div>
              <div className="overview-grid">
                <Panel
                  title="Scanner activity"
                  aside={<span className="muted">Latest completed pass</span>}
                >
                  {server ? (
                    <div className="scanner-list">
                      {server.scanners.map((s) => {
                        const state = scannerState(s, server.market, now);
                        return (
                          <div className="scanner-row" key={s.id}>
                            <span className="scanner-id">{s.id}</span>
                            <div className="scanner-copy">
                              <b>
                                {s.id === "v3"
                                  ? "Baseline expert"
                                  : s.id === "v31"
                                    ? "Expanded expert"
                                    : s.id === "v4"
                                      ? "Meta ensemble"
                                      : "Live ensemble"}
                              </b>
                              <small>
                                {s.scanned === null
                                  ? s.note
                                  : `${num(s.scanned)} scanned · ${num(s.queued)} queued · ${num(s.errors)} errors`}
                              </small>
                            </div>
                            <div className="scanner-state">
                              <Tag
                                tone={
                                  state === "reporting"
                                    ? "good"
                                    : state === "stale"
                                      ? "warn"
                                      : "neutral"
                                }
                              >
                                {state}
                              </Tag>
                              <small title={time(s.lastCompletionAt)}>
                                {ago(s.lastCompletionAt, now)}
                              </small>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <Empty>Waiting for the server publisher.</Empty>
                  )}
                  <p className="footnote">
                    Queue counts from scanner logs do not prove delivery.
                    Completion times use the preceding UTC log timestamp.
                  </p>
                </Panel>
                <Panel title="Data connections" aside={<Activity size={17} />}>
                  {server?.feeds.map((f) => (
                    <div className="connection" key={f.id}>
                      <div>
                        <b>
                          {f.id === "stocks" ? "Stock feed" : "Option feed"}
                        </b>
                        <small>
                          {num(f.count)}{" "}
                          {f.id === "stocks" ? "symbols" : "contracts"} ·{" "}
                          {f.state}
                        </small>
                      </div>
                      <Tag
                        tone={fresh(f.observedAt, 180, now) ? "good" : "warn"}
                      >
                        {ago(f.observedAt, now)}
                      </Tag>
                    </div>
                  ))}
                  {!server && <Empty>Feed heartbeats unavailable.</Empty>}
                  <div className="connection">
                    <div>
                      <b>FA feature snapshot</b>
                      <small>
                        {num(home?.fa.symbols)} symbols ·{" "}
                        {time(home?.fa.cutoff)}
                      </small>
                    </div>
                    <Tag
                      tone={
                        fresh(home?.fa.cutoff, 48 * 3600, now) ? "good" : "warn"
                      }
                    >
                      {ago(home?.fa.cutoff, now)}
                    </Tag>
                  </div>
                  <div className="connection">
                    <div>
                      <b>Summary publishers</b>
                      <small>
                        Server {ago(server?.observedAt, now)} · Home{" "}
                        {ago(home?.observedAt, now)}
                      </small>
                    </div>
                  </div>
                </Panel>
              </div>
              <Panel
                title="Recent candidates"
                aside={
                  <button
                    className="text-button"
                    onClick={() => setTab("Signals")}
                  >
                    View signals <ArrowUpRight size={16} />
                  </button>
                }
              >
                {server?.queueAvailable ? (
                  <Signals
                    rows={server.signals}
                    compact
                    onSelect={setSelected}
                  />
                ) : (
                  <Empty>Alert queue unavailable.</Empty>
                )}
              </Panel>
            </>
          )}
          {tab === "Signals" && (
            <>
              <div className="metrics three">
                <Metric
                  label="Confirmed sent"
                  value={num(sent)}
                  detail="Queue status is sent"
                />
                <Metric
                  label="Pending / selected"
                  value={num(queued)}
                  detail="Queued, not confirmed sent"
                />
                <Metric
                  label="Suppressed"
                  value={num(suppressed)}
                  detail="Ranking, probability or late-arrival suppression"
                />
              </div>
              <Panel
                title="Candidate ledger"
                aside={<span className="muted">Today · Chicago</span>}
              >
                {server?.queueAvailable ? (
                  <Signals rows={server.signals} onSelect={setSelected} />
                ) : (
                  <Empty>Waiting for alert queue records.</Empty>
                )}
                <p className="footnote">
                  {server?.scope ||
                    "Bounded recent records from the server alert queue."}{" "}
                  Scores retain each expert’s meaning; they are not a universal
                  confidence measure. Rejected model candidates may never enter
                  this queue.
                </p>
              </Panel>
            </>
          )}
          {tab === "Positions" && (
            <Panel
              title="Taken positions"
              aside={<span className="muted">Latest 100 · recorded fills</span>}
            >
              {server?.positionsAvailable ? (
                server.positions.length ? (
                  <div className="position-grid">
                    {server.positions.map((p) => (
                      <article className="position" key={p.id}>
                        <div className="position-title">
                          <h2>{p.symbol}</h2>
                          <Tag
                            tone={
                              p.status === "exit_due"
                                ? "warn"
                                : p.status === "open"
                                  ? "good"
                                  : "neutral"
                            }
                          >
                            {p.status}
                          </Tag>
                        </div>
                        <div className="contract">{p.contract}</div>
                        <dl>
                          <div>
                            <dt>Remaining by fills</dt>
                            <dd>
                              {num(p.remaining)} / {num(p.quantity)}
                            </dd>
                          </div>
                          <div>
                            <dt>Entry premium</dt>
                            <dd>{money(p.entry)}</dd>
                          </div>
                          <div>
                            <dt>Observed bid / ask</dt>
                            <dd>
                              {money(p.bid)} / {money(p.ask)}
                            </dd>
                          </div>
                          <div>
                            <dt>Realized net P&amp;L</dt>
                            <dd>{money(p.realizedNet)}</dd>
                          </div>
                        </dl>
                        <small className="muted">
                          Quote {time(p.quoteAt)} ·{" "}
                          {fresh(p.quoteAt, 120, now)
                            ? "recent"
                            : "stale or unavailable"}
                        </small>
                        {p.realizedNet === null && (
                          <p className="footnote">
                            Net P&amp;L unavailable until required fills and
                            fees are recorded.
                          </p>
                        )}
                        {p.status === "closed" && p.remaining !== 0 && (
                          <p className="position-warning">
                            Marked closed; sale accounting is incomplete.
                          </p>
                        )}
                        {p.exitNotice && (
                          <p className="position-warning">{p.exitNotice}</p>
                        )}
                        {p.monitorError && (
                          <p className="position-warning">
                            Monitor: {p.monitorError}
                          </p>
                        )}
                        <footer>Last checked {time(p.checkedAt)}</footer>
                      </article>
                    ))}
                  </div>
                ) : (
                  <Empty>No taken positions were reported.</Empty>
                )
              ) : (
                <Empty>Position ledger unavailable.</Empty>
              )}
            </Panel>
          )}
          {tab === "Research" && (
            <>
              <Panel
                title="Campaign progress"
                aside={<Tag>Observed evidence</Tag>}
              >
                {home?.research ? (
                  <>
                    <div className="research-heading">
                      <h2>{home.research.campaign}</h2>
                      <p>
                        {home.research.stages.length
                          ? home.research.stages.join(" · ")
                          : "No active stage reported at observation"}
                      </p>
                      <small>
                        Observed {time(home.research.observedAt)} ·{" "}
                        {ago(home.research.observedAt, now)}
                      </small>
                    </div>
                    <div className="count-grid">
                      {Object.entries(home.research.counts).map(([k, v]) => (
                        <Metric
                          key={k}
                          label={k.replaceAll("_", " ")}
                          value={num(v)}
                          detail="Recorded progress count"
                        />
                      ))}
                    </div>
                    <div className="evidence-list">
                      {Object.entries(home.research.evidence).map(([k, v]) => (
                        <div key={k}>
                          <span>{k.replaceAll("_", " ")}</span>
                          <Tag tone={v ? "good" : "neutral"}>
                            {v ? "Present" : "Not yet present"}
                          </Tag>
                        </div>
                      ))}
                    </div>
                    <p className="footnote">
                      Artifact presence indicates progress. It does not
                      establish passing evaluation or readiness to deploy.
                    </p>
                  </>
                ) : (
                  <Empty>
                    Configure an explicit campaign progress receipt to show this
                    build.
                  </Empty>
                )}
              </Panel>
              <Panel title="Automation receipts">
                {home?.jobs.length ? (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Job</th>
                          <th>Last result</th>
                          <th>Observed · CT</th>
                        </tr>
                      </thead>
                      <tbody>
                        {home.jobs.map((j) => (
                          <tr key={j.id}>
                            <td>{j.id}</td>
                            <td>
                              <Tag
                                tone={
                                  j.state === "success"
                                    ? "good"
                                    : j.state === "failed"
                                      ? "warn"
                                      : "neutral"
                                }
                              >
                                {j.state}
                              </Tag>
                            </td>
                            <td>{time(j.observedAt)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <Empty>No job receipts available.</Empty>
                )}
              </Panel>
            </>
          )}
          {tab === "V6 Paper" && <Forward data={home?.v6Forward} broker={home?.v6Broker} delivery={server?.v6Delivery} now={now} />}
          {tab === "Training" && (
            <Training
              key={live.user?.uid ?? "preview"}
              data={home?.training}
              now={now}
            />
          )}
          {tab === "FA" && (
            <>
              <div className="metrics three">
                <Metric
                  label="Symbols captured"
                  value={num(home?.fa.symbols)}
                  detail={time(home?.fa.cutoff)}
                />
                <Metric
                  label="Unique news stories"
                  value={num(home?.fa.uniqueNews)}
                  detail="Seven-day window · syndicated copies deduplicated"
                />
                <Metric
                  label="Forward labeled rows"
                  value={num(home?.fa.labeledRows)}
                  detail={
                    home?.fa.evaluationStatus.replaceAll("-", " ") ||
                    "Evaluation not reported"
                  }
                />
              </div>
              <div className="overview-grid">
                <Panel
                  title="Source coverage"
                  aside={<span className="muted">Symbols with data</span>}
                >
                  <div className="coverage">
                    {Object.entries(home?.fa.coverage ?? {}).map(([k, v]) => (
                      <div key={k}>
                        <div>
                          <span>{k.replaceAll("_", " ")}</span>
                          <b>
                            {v} / {num(home?.fa.symbols)}
                          </b>
                        </div>
                        <div className="bar">
                          <i
                            style={{
                              width: `${Math.min(100, (v / (home?.fa.symbols || 1)) * 100)}%`,
                            }}
                          />
                        </div>
                      </div>
                    ))}
                    {!home && <Empty>Waiting for the home publisher.</Empty>}
                  </div>
                </Panel>
                <Panel title="Forward evaluation">
                  <div className="evaluation">
                    <FlaskConical size={28} />
                    <h3>
                      {home?.fa.evaluationStatus === "awaiting-forward-outcomes"
                        ? "Collecting the next chapter."
                        : home?.fa.evaluationStatus.replaceAll("-", " ") ||
                          "Awaiting evaluation"}
                    </h3>
                    <p>
                      Features are preserved as they were observed. The
                      comparison needs 40 training sessions and 10 test sessions
                      before reporting results.
                    </p>
                    <Tag>Experimental features</Tag>
                  </div>
                </Panel>
              </div>
              <Panel
                title="Company snapshot"
                aside={
                  <label className="search">
                    <Search size={15} />
                    <input
                      aria-label="Search FA symbols"
                      placeholder="Find a symbol"
                      value={faQuery}
                      onChange={(e) => setFaQuery(e.target.value)}
                    />
                  </label>
                }
              >
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Symbol</th>
                        <th>News · 7d</th>
                        <th>Sentiment</th>
                        <th>Revenue YoY</th>
                        <th>Short interest</th>
                        <th>Free float</th>
                      </tr>
                    </thead>
                    <tbody>
                      {faRows.map((r) => (
                        <tr key={r.ticker}>
                          <td>
                            <b>{r.ticker}</b>
                          </td>
                          <td>{num(r.newsCount)}</td>
                          <td>{num(r.sentiment, 2)}</td>
                          <td>{pct(r.revenueGrowth)}</td>
                          <td>{num(r.shortInterest)}</td>
                          <td>
                            {r.floatPercent === null
                              ? "—"
                              : `${num(r.floatPercent, 1)}%`}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {!faRows.length && (
                    <Empty>No matching company snapshots.</Empty>
                  )}
                </div>
                <p className="footnote">
                  Sentiment ranges from −1 to +1 using Massive’s ticker-specific
                  categories. Missing values are shown as —. These experimental
                  features do not change live ranking weights.
                </p>
              </Panel>
            </>
          )}
          <footer className="page-footer">
            <span>
              <ShieldCheck size={14} />
              Private observations · Chicago time
            </span>
            <span>
              Server {time(server?.observedAt)} · Home {time(home?.observedAt)}
            </span>
          </footer>
          </>
          )}
        </main>
      </div>
      {selected && (
        <div className="modal-backdrop" onClick={() => setSelected(null)}>
          <section
            role="dialog"
            aria-modal="true"
            aria-label="Signal evidence"
            className="modal"
            onKeyDown={(e) => {
              if (e.key === "Tab") {
                e.preventDefault();
                e.currentTarget
                  .querySelector<HTMLButtonElement>("button")
                  ?.focus();
              }
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              autoFocus
              className="icon-button close"
              aria-label="Close signal evidence"
              onClick={() => setSelected(null)}
            >
              <X />
            </button>
            <div className="eyebrow">SIGNAL EVIDENCE</div>
            <h2>
              {selected.symbol} · {selected.side}
            </h2>
            <dl>
              {Object.entries(selected).map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd>{v === null ? "Unavailable" : String(v)}</dd>
                </div>
              ))}
            </dl>
            <p className="footnote">
              Candidate time is the cohort’s opening time, not the exact send
              time. A sent status confirms the queue recorded successful
              delivery.
            </p>
          </section>
        </div>
      )}
    </div>
  );
}
