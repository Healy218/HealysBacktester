"""Comparable, dependency-light metrics for incubator outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


class MetricsError(ValueError):
    """Raised when a result record cannot be scored."""


def score_records(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Score records containing ``prediction`` and numeric ``outcome``.

    Outcomes are interpreted as directional when they are -1/0/1. A numeric
    outcome can also represent a forward return; ``mean_outcome`` is always
    reported, while directional metrics are reported only when applicable.
    """
    rows = list(records)
    if not rows:
        raise MetricsError("no result records")
    usable = []
    for row in rows:
        if not isinstance(row, dict) or "prediction" not in row or "outcome" not in row:
            raise MetricsError("each result record needs prediction and outcome")
        try:
            prediction = float(row["prediction"])
            outcome = float(row["outcome"])
        except (TypeError, ValueError) as exc:
            raise MetricsError("prediction and outcome must be numeric") from exc
        usable.append((prediction, outcome))
    predictions = [row[0] for row in usable]
    outcomes = [row[1] for row in usable]
    result: dict[str, Any] = {
        "metrics_schema_version": 1,
        "n": len(usable),
        "mean_prediction": sum(predictions) / len(predictions),
        "mean_outcome": sum(outcomes) / len(outcomes),
        "mean_squared_error": sum((p - o) ** 2 for p, o in usable) / len(usable),
    }
    directional = all(value in (-1.0, 0.0, 1.0) for value in outcomes)
    if directional:
        result["directional_accuracy"] = sum(
            1 for prediction, outcome in usable if (prediction > 0) == (outcome > 0)
        ) / len(usable)
        result["signed_hit_rate"] = sum(
            1 for prediction, outcome in usable if prediction * outcome > 0
        ) / len(usable)
    return result


def score_jsonl(path: Path) -> dict[str, Any]:
    records = []
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MetricsError(f"invalid JSONL at line {line_number}") from exc
        records.append(record)
    return score_records(records)
