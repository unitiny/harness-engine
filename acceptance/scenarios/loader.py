"""
YAML scenario loader for acceptance testing.

Parses YAML scenario files into structured Scenario objects that can be
executed by the ScenarioRunner. Supports environment variable substitution
using ${VAR} and ${VAR:default} syntax.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional

import yaml


# Regex for ${VAR} and ${VAR:default} patterns
_ENV_VAR_PATTERN = re.compile(r'\$\{([^}:]+)(?::([^}]*))?\}')


def resolve_env_vars(value: str) -> str:
    """Replace ${VAR} and ${VAR:default} with environment variable values."""
    def replacer(match):
        var_name = match.group(1)
        default = match.group(2)  # None if no default specified
        result = os.environ.get(var_name, default if default is not None else match.group(0))
        return result
    return _ENV_VAR_PATTERN.sub(replacer, str(value))


def _resolve_value(obj):
    """Recursively resolve environment variables in a data structure."""
    if isinstance(obj, str):
        return resolve_env_vars(obj)
    elif isinstance(obj, dict):
        return {k: _resolve_value(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_value(item) for item in obj]
    return obj


@dataclass
class MonitoringConfig:
    """Monitoring configuration for a scenario."""
    console: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": True,
        "capture_types": ["error", "warn"],
        "fail_on_error": True,
    })
    network: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": True,
        "capture_types": ["xhr", "fetch"],
        "fail_on_status": [401, 403, 500],
    })


@dataclass
class ScenarioStep:
    """A single step in an acceptance scenario."""
    name: str
    action: str  # navigate, click, fill, wait, verify, verify_api, api_call, assert
    target: str = ""  # CSS selector or URL
    value: Any = None  # text to fill, expected value, etc.
    layers: List[str] = field(default_factory=lambda: ["L1", "L2", "L3", "L4"])
    snapshot_level: str = "summary"  # minimal, summary, full
    timeout_ms: int = 30000
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Scenario:
    """A complete acceptance scenario loaded from YAML."""
    name: str
    description: str = ""
    feature: str = ""
    tags: List[str] = field(default_factory=list)
    environment: str = ""
    preconditions: List[str] = field(default_factory=list)
    steps: List[ScenarioStep] = field(default_factory=list)
    cleanup: List[ScenarioStep] = field(default_factory=list)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    acceptance_criteria: Dict[str, Any] = field(default_factory=dict)
    pass_condition: Dict[str, Any] = field(default_factory=lambda: {
        "min_reward": 0.7,
        "must_pass_all_required": True,
    })
    source_path: str = ""


def _parse_step(step_data: Dict[str, Any]) -> ScenarioStep:
    """Parse a step dictionary into a ScenarioStep."""
    layers = step_data.get("layers", ["L1", "L2", "L3", "L4"])
    # Normalize layer names (accept both "L1" and "L1_ENVIRONMENT")
    normalized = []
    layer_map = {
        "L1": "L1", "L1_ENVIRONMENT": "L1",
        "L2": "L2", "L2_NETWORK": "L2",
        "L3": "L3", "L3_CONSOLE": "L3",
        "L4": "L4", "L4_DOM": "L4",
        "L5": "L5", "L5_PERSISTENCE": "L5",
    }
    for l in layers:
        normalized.append(layer_map.get(l, l))

    return ScenarioStep(
        name=step_data.get("name", "unnamed"),
        action=step_data.get("action", "verify"),
        target=step_data.get("target", ""),
        value=_resolve_value(step_data.get("value")),
        layers=normalized,
        snapshot_level=step_data.get("snapshot_level", "summary"),
        timeout_ms=step_data.get("timeout_ms", 30000),
        metadata={k: v for k, v in step_data.items() if k not in {
            "name", "action", "target", "value", "layers", "snapshot_level", "timeout_ms"
        }},
    )


def _parse_monitoring(data: Dict[str, Any]) -> MonitoringConfig:
    """Parse monitoring configuration."""
    if not data:
        return MonitoringConfig()
    return MonitoringConfig(
        console=data.get("console", MonitoringConfig().console),
        network=data.get("network", MonitoringConfig().network),
    )


def load_scenario(yaml_path: str) -> Scenario:
    """
    Load a single scenario from a YAML file.

    Args:
        yaml_path: Path to the YAML scenario file.

    Returns:
        Scenario object with all steps and configuration.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the YAML structure is invalid.
    """
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"Scenario file not found: {yaml_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Scenario must be a YAML mapping, got {type(data).__name__}")

    # Resolve environment variables in all string values
    data = _resolve_value(data)

    steps = [_parse_step(s) for s in data.get("steps", [])]
    cleanup = [_parse_step(s) for s in data.get("cleanup", [])]

    return Scenario(
        name=data.get("name", path.stem),
        description=data.get("description", ""),
        feature=data.get("feature", ""),
        tags=data.get("tags", []),
        environment=data.get("environment", ""),
        preconditions=data.get("preconditions", []),
        steps=steps,
        cleanup=cleanup,
        monitoring=_parse_monitoring(data.get("monitoring", {})),
        acceptance_criteria=data.get("acceptance_criteria", {}),
        pass_condition=data.get("pass_condition", {"min_reward": 0.7, "must_pass_all_required": True}),
        source_path=str(path),
    )


def load_all_scenarios(directory: str) -> List[Scenario]:
    """
    Load all scenario YAML files from a directory (recursive).

    Returns:
        List of Scenario objects, sorted by filename.
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        return []

    scenarios = []
    for yaml_file in sorted(dir_path.rglob("*.yaml")):
        # Skip template files
        if "template" in yaml_file.name.lower():
            continue
        try:
            scenario = load_scenario(str(yaml_file))
            scenarios.append(scenario)
        except Exception as e:
            # Log warning but don't fail - other scenarios may still work
            print(f"Warning: Failed to load scenario {yaml_file}: {e}")

    return scenarios


def validate_scenario(scenario: Scenario) -> List[str]:
    """
    Validate a scenario structure and return a list of error messages.

    Returns:
        Empty list if valid, otherwise list of human-readable error strings.
    """
    errors = []

    if not scenario.name:
        errors.append("Scenario has no name")

    if not scenario.steps:
        errors.append(f"Scenario '{scenario.name}' has no steps")

    valid_actions = {
        "navigate",
        "click",
        "fill",
        "wait",
        "verify",
        "verify_api",
        "api_call",
        "assert",
        "assert_text_quality",
    }
    for i, step in enumerate(scenario.steps):
        if not step.name:
            errors.append(f"Step {i+1} has no name")
        if step.action not in valid_actions:
            errors.append(f"Step '{step.name}' has invalid action '{step.action}' (valid: {valid_actions})")
        if step.action in ("navigate", "click", "fill", "wait", "verify", "assert", "assert_text_quality") and not step.target:
            errors.append(f"Step '{step.name}' action '{step.action}' requires a target")
        if step.action == "fill" and step.value is None:
            errors.append(f"Step '{step.name}' action 'fill' requires a value")

        valid_levels = {"minimal", "summary", "full"}
        if step.snapshot_level not in valid_levels:
            errors.append(f"Step '{step.name}' has invalid snapshot_level '{step.snapshot_level}'")

    # Validate acceptance criteria
    if scenario.acceptance_criteria:
        must_pass = scenario.acceptance_criteria.get("must_pass", [])
        if must_pass:
            step_names = {s.name for s in scenario.steps}
            for mp in must_pass:
                if mp not in step_names:
                    errors.append(f"acceptance_criteria.must_pass references unknown step '{mp}'")

    return errors
