"""Result data types for the acceptance testing framework."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional


class StepStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class ScenarioStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


@dataclass
class LayerResult:
    """Result of a single layer check."""
    layer_name: str
    passed: bool
    message: str = ""
    evidence: Optional[str] = None  # path to screenshot/log file
    details: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        icon = "PASS" if self.passed else "FAIL"
        return f"[{icon}] {self.layer_name}: {self.message}"


@dataclass
class StepResult:
    """Result of a single scenario step execution."""
    step_name: str
    status: StepStatus
    layer_results: List[LayerResult] = field(default_factory=list)
    snapshot_data: Optional[str] = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    diagnostic_snapshot: Optional[str] = None  # FULL snapshot only on failure

    @property
    def passed(self) -> bool:
        return self.status == StepStatus.PASSED

    @property
    def failed_layers(self) -> List[LayerResult]:
        return [lr for lr in self.layer_results if not lr.passed]

    def __str__(self) -> str:
        icon = "+" if self.passed else "x"
        return f"[{icon}] {self.step_name} ({self.duration_ms:.0f}ms)"


@dataclass
class ScenarioResult:
    """Result of running a complete scenario."""
    scenario_name: str
    status: ScenarioStatus
    step_results: List[StepResult] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    finished_at: Optional[str] = None
    error: Optional[str] = None
    report_path: Optional[str] = None

    @property
    def passed(self) -> bool:
        return self.status == ScenarioStatus.PASSED

    @property
    def total_steps(self) -> int:
        return len(self.step_results)

    @property
    def passed_steps(self) -> int:
        return sum(1 for s in self.step_results if s.passed)

    @property
    def failed_steps(self) -> List[StepResult]:
        return [s for s in self.step_results if not s.passed]

    @property
    def duration_ms(self) -> float:
        return sum(s.duration_ms for s in self.step_results)

    @property
    def console_errors(self) -> int:
        return sum(
            len(lr.details.get("error_count", 0) if isinstance(lr.details.get("error_count"), int) else 0)
            for s in self.step_results
            for lr in s.layer_results
            if lr.layer_name == "L3_CONSOLE" and not lr.passed
        )

    def get_summary(self) -> Dict[str, Any]:
        return {
            "scenario": self.scenario_name,
            "status": self.status.value,
            "total_steps": self.total_steps,
            "passed_steps": self.passed_steps,
            "failed_steps": len(self.failed_steps),
            "duration_ms": round(self.duration_ms, 1),
        }

    def __str__(self) -> str:
        icon = "+" if self.passed else "x"
        return f"[{icon}] {self.scenario_name}: {self.passed_steps}/{self.total_steps} steps passed"
