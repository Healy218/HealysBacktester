import { z } from "zod";
const metric = z.number().finite().nullable();
const cell = z.string().max(12000);
export const trainingReportSchema = z.object({
  id: z.enum(["v2", "v3", "v31", "v4", "v5", "v6"]),
  label: z.string(),
  title: z.string(),
  status: z.string(),
  summary: z.string(),
  notes: z.array(z.string()).max(20),
  facts: z.array(z.object({ label: z.string(), value: cell })).max(30),
  folds: z
    .array(
      z.object({
        label: z.string(),
        period: z.string(),
        policy: z.string(),
        returnValue: metric,
        drawdown: metric,
        baseline: metric,
        exTop3: metric,
        trades: metric,
        basis: z.string(),
      }),
    )
    .max(20),
  tables: z
    .array(
      z.object({
        title: z.string(),
        note: z.string(),
        columns: z.array(z.string()).max(12),
        rows: z.array(z.array(cell).max(12)).max(300),
      }),
    )
    .max(20),
  sources: z
    .array(
      z.object({
        path: z.string(),
        sha256: z.string().regex(/^[a-f0-9]{64}$/),
        content: z.string().max(120000),
        excerpt: z.boolean(),
      }),
    )
    .max(8),
});
export const trainingSchema = z.object({
  observedAt: z.string().datetime({ offset: true }),
  campaign: z.string(),
  status: z.string(),
  stage: z.string(),
  activity: z.string(),
  activeWorkers: metric,
  completedFinalSeeds: metric,
  totalFinalSeeds: metric,
  versions: z.array(trainingReportSchema).max(6),
  issues: z.array(z.string()).max(20),
});
export type TrainingData = z.infer<typeof trainingSchema>;
export type TrainingReport = z.infer<typeof trainingReportSchema>;
export const trainingPercent = (value: number | null) =>
  value === null ? "—" : `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
const escapeCell = (value: string) =>
  value.replaceAll("|", "\\|").replaceAll("\n", " ");
export function reportMarkdown(report: TrainingReport) {
  const lines = [
    `# ${report.label} — ${report.title}`,
    "",
    `Status: ${report.status}`,
    "",
    report.summary,
    "",
    ...report.notes.map((note) => `> ${note}\n`),
    "## Training facts",
    "",
    ...report.facts.map((f) => `- **${f.label}:** ${f.value}`),
    "",
    "## Out-of-sample folds",
    "",
    "| Fold | Test period | Policy | Return | Max drawdown | Accounting |",
    "|---|---|---|---|---|---|",
    ...report.folds.map(
      (f) =>
        `| ${[f.label, f.period, f.policy, trainingPercent(f.returnValue), trainingPercent(f.drawdown), f.basis].map(escapeCell).join(" | ")} |`,
    ),
    "",
  ];
  for (const table of report.tables)
    lines.push(
      `## ${table.title}`,
      "",
      table.note,
      "",
      `| ${table.columns.map(escapeCell).join(" | ")} |`,
      `| ${table.columns.map(() => "---").join(" | ")} |`,
      ...table.rows.map((row) => `| ${row.map(escapeCell).join(" | ")} |`),
      "",
    );
  for (const source of report.sources)
    lines.push(
      `## Source: ${source.path}`,
      "",
      `SHA-256 (whole source): ${source.sha256}`,
      "",
      source.excerpt
        ? "Selected excerpt follows."
        : "Preserved source follows.",
      "",
      source.content,
      "",
    );
  return lines.join("\n");
}
