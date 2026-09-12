import type { TrainingData, TrainingReport } from "../src/trainingModel";
export function trainingFixture(): TrainingData {
  const versions: TrainingReport[] = (
    ["v2", "v3", "v31", "v4", "v5", "v6"] as const
  ).map((id) => ({
    id,
    label: id === "v31" ? "V3.1" : id.toUpperCase(),
    title: `Report ${id}`,
    status: id === "v6" ? "Training" : "Historical",
    summary: "Synthetic test report, never production metrics.",
    notes: ["Different windows and accounting must remain visible."],
    facts: [{ label: "Universe", value: "Synthetic" }],
    folds: [
      {
        label: "Fold 1",
        period: "2026-03-04 → 2026-05-04",
        policy: "GBT / ev 0.05",
        returnValue: 0.123,
        drawdown: null,
        baseline: null,
        exTop3: null,
        trades: 0,
        basis: "Marked ledger / base costs",
      },
    ],
    tables: [
      {
        title: "Validation diagnostics",
        note: "Validation only.",
        columns: ["Measure", "Result"],
        rows: [
          ["Missing", "—"],
          ["Zero trades", "0"],
        ],
      },
    ],
    sources: [
      {
        path: `reports/${id}.md`,
        sha256: "a".repeat(64),
        excerpt: false,
        content:
          '# Source evidence\n\n| Metric | Value |\n|---|---|\n| Missing | — |\n\n<img src="https://invalid.example/private-report" onerror="alert(1)">',
      },
    ],
  }));
  return {
    observedAt: new Date().toISOString(),
    campaign: "explicit-campaign",
    status: "Training",
    stage: "finalize",
    activity: "finalize: running",
    activeWorkers: 0,
    completedFinalSeeds: 40,
    totalFinalSeeds: 40,
    versions,
    issues: [],
  };
}
