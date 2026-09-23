"""Explicit resource and time budgets for incubator campaigns."""

from __future__ import annotations

from dataclasses import asdict, dataclass


class BudgetError(ValueError):
    """Raised when a resource budget is invalid."""


@dataclass(frozen=True)
class ResourceBudget:
    """Hard upper bounds; ``None`` disables an OS-level limit."""

    campaign_seconds: float = 3600.0
    artifact_seconds: int = 120
    memory_bytes: int | None = 2 * 1024**3
    output_bytes: int = 16 * 1024**2
    max_artifacts: int = 64

    def validate(self) -> "ResourceBudget":
        if self.campaign_seconds <= 0 or self.artifact_seconds <= 0:
            raise BudgetError("campaign and artifact budgets must be positive")
        if self.memory_bytes is not None and self.memory_bytes <= 0:
            raise BudgetError("memory budget must be positive or None")
        if self.output_bytes <= 0 or self.max_artifacts <= 0:
            raise BudgetError("output and artifact-count budgets must be positive")
        return self

    def as_dict(self) -> dict[str, object]:
        return asdict(self)
