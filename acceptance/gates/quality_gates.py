"""
Quality gate evaluator for acceptance testing.

Loads quality gate definitions from YAML and evaluates them against
scenario results.  Each gate has one or more conditions that compare
a computed metric against a threshold using a comparison operator.

Supported metrics:
  - scenario_pass_rate:  ratio of passed scenarios (optionally tag-filtered)
  - max_console_errors:  worst console-error count across scenarios
  - max_network_errors:  worst network-error count across scenarios
  - max_step_duration_ms: longest individual step duration in milliseconds

Supported operators: gte, lte, eq, gt, lt
"""
from __future__ import annotations

import operator as _operator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import yaml

# Re-export ScenarioResult so callers don't need to know the exact import path.
from ..core.result import ScenarioResult

# ---------------------------------------------------------------------------
# Comparison operator mapping
# ---------------------------------------------------------------------------

_OP_MAP = {
    "gte": _operator.ge,
    "lte": _operator.le,
    "eq": _operator.eq,
    "gt": _operator.gt,
    "lt": _operator.lt,
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class GateCondition:
    """A single condition inside a quality gate.

    Attributes:
        metric: Name of the metric to compute.
        tags: Optional list of tags used to filter scenarios (only
              meaningful for ``scenario_pass_rate``).
        operator: Comparison operator string (gte / lte / eq / gt / lt).
        threshold: Value to compare the computed metric against.
    """

    metric: str
    tags: Optional[List[str]] = None
    operator: str = "gte"
    threshold: Any = None


@dataclass
class QualityGate:
    """A named quality gate consisting of one or more conditions.

    Attributes:
        name: Human-readable gate identifier.
        description: Short explanation of what the gate checks.
        conditions: List of :class:`GateCondition` objects.
        blocking: When ``True`` a failure marks the overall acceptance
                  gate as failed.
    """

    name: str
    description: str = ""
    conditions: List[GateCondition] = field(default_factory=list)
    blocking: bool = False


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------


def load_quality_gates(yaml_path: str) -> List[QualityGate]:
    """Load quality gate definitions from a YAML file.

    Expected structure::

        gates:
          - name: "my_gate"
            description: "..."
            blocking: true
            conditions:
              - metric: "scenario_pass_rate"
                operator: "gte"
                threshold: 0.8

    Parameters
    ----------
    yaml_path:
        Absolute or relative path to the YAML file.

    Returns
    -------
    list[QualityGate]
        Parsed gate objects.  Returns an empty list if the file does not
        exist or contains no gates.

    Raises
    ------
    ValueError
        If the YAML structure is invalid or a condition references an
        unknown metric or operator.
    """

    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"Quality gates file not found: {yaml_path}")

    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {yaml_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Quality gates file must be a YAML mapping, got {type(data).__name__}")

    raw_gates = data.get("gates", [])
    if not isinstance(raw_gates, list):
        raise ValueError("'gates' key must be a list")

    valid_metrics = {"scenario_pass_rate", "max_console_errors", "max_network_errors", "max_step_duration_ms"}
    valid_operators = set(_OP_MAP.keys())

    gates: List[QualityGate] = []
    for idx, raw in enumerate(raw_gates):
        if not isinstance(raw, dict):
            raise ValueError(f"Gate at index {idx} must be a mapping")

        name = raw.get("name", f"gate_{idx}")
        conditions: List[GateCondition] = []

        for ci, rc in enumerate(raw.get("conditions", [])):
            if not isinstance(rc, dict):
                raise ValueError(f"Condition {ci} in gate '{name}' must be a mapping")

            metric = rc.get("metric")
            if metric not in valid_metrics:
                raise ValueError(
                    f"Unknown metric '{metric}' in gate '{name}' condition {ci}. "
                    f"Valid metrics: {valid_metrics}"
                )

            op = rc.get("operator", "gte")
            if op not in valid_operators:
                raise ValueError(
                    f"Unknown operator '{op}' in gate '{name}' condition {ci}. "
                    f"Valid operators: {valid_operators}"
                )

            threshold = rc.get("threshold")
            if threshold is None:
                raise ValueError(
                    f"Missing 'threshold' in gate '{name}' condition {ci}"
                )

            conditions.append(GateCondition(
                metric=metric,
                tags=rc.get("tags"),
                operator=op,
                threshold=threshold,
            ))

        gates.append(QualityGate(
            name=name,
            description=raw.get("description", ""),
            conditions=conditions,
            blocking=bool(raw.get("blocking", False)),
        ))

    return gates


# ---------------------------------------------------------------------------
# Metric computation helpers
# ---------------------------------------------------------------------------


def _compute_scenario_pass_rate(
    results: Sequence[ScenarioResult],
    tags: Optional[List[str]] = None,
    *,
    scenario_tags_map: Optional[Dict[str, List[str]]] = None,
) -> float:
    """Compute the ratio of passed scenarios.

    Parameters
    ----------
    results:
        Scenario results to evaluate.
    tags:
        If provided, only scenarios whose names appear in *scenario_tags_map*
        with at least one matching tag are considered.
    scenario_tags_map:
        Mapping from scenario name to list of tag strings.

    Returns
    -------
    float
        Value in ``[0.0, 1.0]``.  Returns ``1.0`` when no scenarios match
        (nothing to fail).
    """

    if tags and scenario_tags_map:
        filtered = [
            r for r in results
            if scenario_tags_map.get(r.scenario_name) and
               any(t in scenario_tags_map[r.scenario_name] for t in tags)
        ]
    else:
        filtered = list(results)

    if not filtered:
        return 1.0  # No matching scenarios => nothing to fail

    passed = sum(1 for r in filtered if r.passed)
    return passed / len(filtered)


def _compute_max_console_errors(results: Sequence[ScenarioResult]) -> int:
    """Return the maximum console-error count across all scenarios."""

    if not results:
        return 0

    counts: List[int] = []
    for r in results:
        counts.append(r.console_errors)

    return max(counts)


def _compute_max_network_errors(results: Sequence[ScenarioResult]) -> int:
    """Return the maximum network-error count across all scenarios.

    Network errors are derived from L2_NETWORK layer results whose
    ``passed`` flag is ``False``.  The ``details`` dict may contain an
    ``error_count`` key; otherwise each failed layer result counts as one.
    """

    if not results:
        return 0

    counts: List[int] = []
    for r in results:
        scenario_network_errors = 0
        for step in r.step_results:
            for lr in step.layer_results:
                if lr.layer_name == "L2_NETWORK" and not lr.passed:
                    ec = lr.details.get("error_count")
                    scenario_network_errors += ec if isinstance(ec, int) else 1
        counts.append(scenario_network_errors)

    return max(counts)


def _compute_max_step_duration_ms(results: Sequence[ScenarioResult]) -> float:
    """Return the maximum individual step duration in milliseconds."""

    if not results:
        return 0.0

    max_duration = 0.0
    for r in results:
        for step in r.step_results:
            if step.duration_ms > max_duration:
                max_duration = step.duration_ms
    return max_duration


_METRIC_COMPUTERS = {
    "scenario_pass_rate": _compute_scenario_pass_rate,
    "max_console_errors": _compute_max_console_errors,
    "max_network_errors": _compute_max_network_errors,
    "max_step_duration_ms": _compute_max_step_duration_ms,
}


# ---------------------------------------------------------------------------
# Condition evaluation
# ---------------------------------------------------------------------------


def evaluate_condition(
    condition: GateCondition,
    results: Sequence[ScenarioResult],
    *,
    scenario_tags_map: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Any]:
    """Evaluate a single gate condition against scenario results.

    Parameters
    ----------
    condition:
        The condition to evaluate.
    results:
        Scenario results to compute the metric from.
    scenario_tags_map:
        Optional mapping from scenario name to tags, used when the
        condition specifies ``tags`` for filtering.

    Returns
    -------
    dict
        Keys: ``metric``, ``passed``, ``actual``, ``threshold``, ``message``.
    """

    op_func = _OP_MAP.get(condition.operator)
    if op_func is None:
        return {
            "metric": condition.metric,
            "passed": False,
            "actual": None,
            "threshold": condition.threshold,
            "message": f"Unknown operator: {condition.operator}",
        }

    # Compute metric value
    if condition.metric == "scenario_pass_rate":
        actual = _compute_scenario_pass_rate(
            results,
            tags=condition.tags,
            scenario_tags_map=scenario_tags_map,
        )
    elif condition.metric == "max_console_errors":
        actual = _compute_max_console_errors(results)
    elif condition.metric == "max_network_errors":
        actual = _compute_max_network_errors(results)
    elif condition.metric == "max_step_duration_ms":
        actual = _compute_max_step_duration_ms(results)
    else:
        return {
            "metric": condition.metric,
            "passed": False,
            "actual": None,
            "threshold": condition.threshold,
            "message": f"Unknown metric: {condition.metric}",
        }

    passed = op_func(actual, condition.threshold)

    tag_info = ""
    if condition.tags:
        tag_info = f" (tags: {condition.tags})"

    message = (
        f"{condition.metric}{tag_info}: "
        f"actual={actual}, threshold={condition.threshold}, "
        f"operator={condition.operator} -> "
        f"{'PASS' if passed else 'FAIL'}"
    )

    return {
        "metric": condition.metric,
        "passed": passed,
        "actual": actual,
        "threshold": condition.threshold,
        "message": message,
    }


# ---------------------------------------------------------------------------
# Gate evaluation
# ---------------------------------------------------------------------------


def evaluate_gates(
    gates: List[QualityGate],
    results: Sequence[ScenarioResult],
    *,
    scenario_tags_map: Optional[Dict[str, List[str]]] = None,
) -> List[Dict[str, Any]]:
    """Evaluate all quality gates against scenario results.

    Parameters
    ----------
    gates:
        Quality gate definitions loaded from YAML.
    results:
        Scenario execution results.
    scenario_tags_map:
        Optional mapping from scenario name to list of tag strings.
        Required when conditions use ``tags`` to filter scenarios.

    Returns
    -------
    list[dict]
        Each dict has keys: ``gate_name``, ``passed``, ``blocking``,
        ``condition_results`` (list of dicts from :func:`evaluate_condition`).
    """

    gate_results: List[Dict[str, Any]] = []

    for gate in gates:
        condition_results: List[Dict[str, Any]] = []
        all_conditions_passed = True

        for condition in gate.conditions:
            cr = evaluate_condition(
                condition,
                results,
                scenario_tags_map=scenario_tags_map,
            )
            condition_results.append(cr)
            if not cr["passed"]:
                all_conditions_passed = False

        gate_results.append({
            "gate_name": gate.name,
            "passed": all_conditions_passed,
            "blocking": gate.blocking,
            "condition_results": condition_results,
        })

    return gate_results
