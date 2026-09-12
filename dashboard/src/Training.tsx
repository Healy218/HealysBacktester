import { useState, type ReactNode } from "react";
import {
  ArrowDownToLine,
  BookOpen,
  Check,
  ChevronRight,
  CircleDot,
  Clock3,
  Layers3,
} from "lucide-react";
import { fresh } from "./model";
import {
  reportMarkdown,
  trainingPercent as pct,
  type TrainingData,
  type TrainingReport,
} from "./trainingModel";
const count = (value: number | null) =>
  value === null ? "—" : value.toLocaleString("en-US");
const clean = (text: string) => text.replace(/\*\*/g, "").replace(/`/g, "");
function Table({
  columns,
  rows,
  label,
}: {
  columns: string[];
  rows: ReactNode[][];
  label: string;
}) {
  return (
    <div
      className="table-wrap training-table"
      tabIndex={0}
      role="region"
      aria-label={label}
    >
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c} scope="col">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((v, j) => (
                <td key={j}>{v}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function Return({ value }: { value: number | null }) {
  return (
    <span
      className={
        value === null
          ? "muted"
          : value < 0
            ? "return-negative"
            : "return-positive"
      }
    >
      {pct(value)}
    </span>
  );
}
function FoldTable({ reports }: { reports: TrainingReport[] }) {
  return (
    <Table
      label="Out-of-sample comparison"
      columns={[
        "Generation / fold",
        "Test period",
        "Policy",
        "Return",
        "Max drawdown",
        "Trades",
        "Accounting",
      ]}
      rows={reports.flatMap((r) =>
        r.folds.map((f) => [
          <span>
            <b>{r.label}</b>
            <small>{f.label}</small>
          </span>,
          f.period,
          f.policy,
          <Return value={f.returnValue} />,
          f.drawdown === null ? "—" : `${(f.drawdown * 100).toFixed(1)}%`,
          count(f.trades),
          f.basis,
        ]),
      )}
    />
  );
}
function download(report: TrainingReport) {
  const url = URL.createObjectURL(
    new Blob([reportMarkdown(report)], { type: "text/markdown;charset=utf-8" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = `${report.id}-training-summary.md`;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
// Intentionally limited Markdown: React text only, no HTML or remote resources.
function SourceText({ content }: { content: string }) {
  const lines = content.split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.startsWith("```")) {
      const code: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```"))
        code.push(lines[i++]);
      i++;
      blocks.push(<pre key={i}>{code.join("\n")}</pre>);
      continue;
    }
    if (
      line.trim().startsWith("|") &&
      /^\s*\|[\s:|\-]+\|\s*$/.test(lines[i + 1] ?? "")
    ) {
      const cells = (s: string) =>
        s
          .trim()
          .replace(/^\||\|$/g, "")
          .split("|")
          .map((v) => clean(v.trim()));
      const columns = cells(line);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().startsWith("|"))
        rows.push(cells(lines[i++]));
      blocks.push(
        <Table
          key={i}
          columns={columns}
          rows={rows}
          label="Archived source table"
        />,
      );
      continue;
    }
    const heading = line.match(/^#{1,6}\s+(.+)/);
    if (heading) blocks.push(<h4 key={i}>{clean(heading[1])}</h4>);
    else if (line.trim()) blocks.push(<p key={i}>{clean(line)}</p>);
    i++;
  }
  return <div className="training-source-text">{blocks}</div>;
}
export function Training({
  data,
  now,
}: {
  data: TrainingData | null | undefined;
  now: number;
}) {
  const [selected, setSelected] = useState("v6");
  if (!data)
    return (
      <section className="panel training-empty">
        <BookOpen />
        <h2>Training reports are not available yet.</h2>
        <p>
          The home publisher will supply the library when its training source is
          configured. Missing results are never treated as zero.
        </p>
      </section>
    );
  const current = data.versions.find((r) => r.id === "v6");
  const report = data.versions.find((r) => r.id === selected);
  const isFresh = fresh(data.observedAt, 180, now);
  const completed = data.status.startsWith("Complete");
  const progress = data.totalFinalSeeds
    ? Math.min(
        100,
        (100 * (data.completedFinalSeeds ?? 0)) / data.totalFinalSeeds,
      )
    : 0;
  return (
    <div className="training-library">
      <section className="training-live panel">
        <div className="training-live-main">
          <div className="training-kicker">
            <CircleDot size={15} />
            {isFresh ? "LATEST CAMPAIGN" : "LAST CAPTURE · STALE"}
          </div>
          <h2>{data.campaign}</h2>
          <p>{data.activity}</p>
          <div className="training-stages">
            {["assemble", "experiments", "evaluate", "finalize"].map(
              (stage, i) => {
                const index = [
                  "assemble",
                  "experiments",
                  "evaluate",
                  "finalize",
                ].indexOf(data.stage);
                const done = completed || (index >= 0 && i < index);
                return (
                  <span
                    key={stage}
                    className={
                      done ? "done" : stage === data.stage ? "current" : ""
                    }
                  >
                    {done ? <Check size={14} /> : <Clock3 size={14} />}
                    {stage === "experiments"
                      ? "Compare objectives"
                      : stage[0].toUpperCase() + stage.slice(1)}
                    {i !== 3 && <ChevronRight size={13} />}
                  </span>
                );
              },
            )}
          </div>
        </div>
        <div className="training-seeds">
          <span className="tag neutral">{data.status}</span>
          <div>
            <strong>{count(data.completedFinalSeeds)}</strong>
            <span> / {count(data.totalFinalSeeds)} final seeds</span>
          </div>
          <div
            className="training-progress"
            role="progressbar"
            aria-label="Final ensemble seed completion"
            aria-valuenow={data.completedFinalSeeds ?? 0}
            aria-valuemax={data.totalFinalSeeds ?? 40}
            aria-valuemin={0}
          >
            <i style={{ width: `${progress}%` }} />
          </div>
          <small>
            {count(data.activeWorkers)} seed workers at capture · gate checks
            may run with zero
          </small>
        </div>
        <div className="training-capture">
          Captured{" "}
          {new Date(data.observedAt).toLocaleString("en-US", {
            timeZone: "America/Chicago",
          })}{" "}
          CT · refreshes with the home publisher
        </div>
      </section>
      <nav className="training-tabs" aria-label="Training generations">
        <button
          aria-pressed={selected === "compare"}
          onClick={() => setSelected("compare")}
        >
          <Layers3 size={16} />
          Compare
        </button>
        {data.versions.map((r) => (
          <button
            key={r.id}
            aria-pressed={selected === r.id}
            onClick={() => setSelected(r.id)}
          >
            {r.label}
            <span>{r.id === "v6" ? "Current" : "Archive"}</span>
          </button>
        ))}
      </nav>
      {selected === "compare" ? (
        <>
          <div className="training-notice">
            <BookOpen size={20} />
            <div>
              <b>Compare the evidence, with its context.</b>
              <p>
                V2–V5 predate the September audit. Test windows, universes and
                accounting differ. These tables preserve each result; they are
                not a ranking on a common benchmark. Fold returns are not added
                or averaged.
              </p>
            </div>
          </div>
          <section className="panel">
            <div className="panel-heading">
              <h2>Generation overview</h2>
            </div>
            <Table
              label="Generation overview"
              columns={[
                "Generation",
                "Research focus",
                "Status",
                "Recorded folds",
              ]}
              rows={data.versions.map((r) => [
                <button
                  className="training-link"
                  onClick={() => setSelected(r.id)}
                >
                  {r.label}
                  <ChevronRight size={14} />
                </button>,
                r.title,
                r.status,
                r.folds.length ? String(r.folds.length) : "Unavailable",
              ])}
            />
          </section>
          <section className="panel">
            <div className="panel-heading">
              <h2>Out-of-sample folds</h2>
              <span className="muted">Each window stands alone</span>
            </div>
            <FoldTable reports={data.versions} />
            <p className="footnote">
              — means unreported. V4 values are rounded in the preserved
              archive. Marked returns include changes in open positions; legacy
              simulations use their original accounting.
            </p>
          </section>
        </>
      ) : (
        report && (
          <>
            <section className="panel training-report-heading">
              <div className="training-report-title">
                <div>
                  <div className="training-kicker">
                    {report.label} / TRAINING REPORT
                  </div>
                  <h2>{report.title}</h2>
                </div>
                <button
                  className="button small"
                  onClick={() => download(report)}
                >
                  <ArrowDownToLine size={16} />
                  Download summary
                </button>
              </div>
              <p className="training-summary">{report.summary}</p>
              <div className="training-facts">
                {report.facts.map((f) => (
                  <div key={f.label}>
                    <small>{f.label}</small>
                    <b>{f.value}</b>
                  </div>
                ))}
              </div>
            </section>
            {!!report.notes.length && (
              <div className="training-notice">
                <BookOpen size={20} />
                <div>
                  <b>
                    {report.id === "v6" ? "Research scope" : "Archive context"}
                  </b>
                  {report.notes.map((n, i) => (
                    <p key={i}>{n}</p>
                  ))}
                </div>
              </div>
            )}
            {report.folds.length > 0 && (
              <section className="panel">
                <div className="panel-heading">
                  <h2>Out-of-sample results</h2>
                  <span className="muted">Base costs / individual folds</span>
                </div>
                <FoldTable reports={[report]} />
                <p className="footnote">
                  Returns and drawdowns share the accounting basis shown.
                  Validation eligibility is not a held-out performance gate. —
                  means unreported.
                </p>
                {report.folds.some(
                  (f) => f.baseline !== null || f.exTop3 !== null,
                ) && (
                  <Table
                    label="Legacy baseline and outlier comparison"
                    columns={[
                      "Fold",
                      "Model return",
                      "Baseline return",
                      "Model ex-top3",
                    ]}
                    rows={report.folds.map((f) => [
                      f.label,
                      pct(f.returnValue),
                      pct(f.baseline),
                      pct(f.exTop3),
                    ])}
                  />
                )}
              </section>
            )}
            {report.tables.map((t, i) => (
              <details
                className="panel training-section"
                key={`${report.id}-${t.title}`}
                open={i < 2 || t.title.startsWith("Final ensemble")}
              >
                <summary>
                  <span>{t.title}</span>
                  <span className="muted">{t.rows.length} rows</span>
                </summary>
                {t.note && <p className="footnote">{t.note}</p>}
                <Table columns={t.columns} rows={t.rows} label={t.title} />
              </details>
            ))}
            <section className="panel training-sources">
              <div className="panel-heading">
                <h2>Source reports</h2>
                <span className="muted">Preserved wording & provenance</span>
              </div>
              <p className="footnote">
                Archived conclusions are shown as written. The context above
                records later corrections. Source hashes identify the local
                files used; historical files are not newly validated backtests.
              </p>
              {report.sources.map((s, i) => (
                <details key={`${report.id}-${i}`}>
                  <summary>
                    <BookOpen size={16} />
                    <span>{s.path}</span>
                    <span className="muted">
                      {s.excerpt ? "Excerpt" : "Full text"}
                    </span>
                  </summary>
                  <div className="training-source-hash">
                    SHA-256 · {s.sha256}
                  </div>
                  <SourceText content={s.content} />
                </details>
              ))}
            </section>
          </>
        )
      )}
      {!current?.folds.length && data.status !== "Training" && (
        <p className="footnote">
          V6 results are unavailable until their stage receipts and report
          hashes can be verified.
        </p>
      )}
    </div>
  );
}
