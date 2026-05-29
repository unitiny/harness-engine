"""
Closed-loop scenario runner.

Executes acceptance scenarios using the four-phase pattern:
  Pre-check → Execute → Verify → Diagnose (failure only)

Key design decisions:
- FULL snapshots are only captured on failure (token optimization)
- Cleanup steps run even when main steps fail
- Each step checks specified layers independently
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional

from ..core.layers import Layer, get_checker, L1EnvironmentChecker, L2NetworkChecker, L3ConsoleChecker, L4DOMChecker, L5PersistenceChecker
from ..core.snapshot import SnapshotLevel, take_snapshot, format_snapshot_for_llm
from ..core.result import StepResult, ScenarioResult, StepStatus, ScenarioStatus, LayerResult
from ..core.playwright_manager import PlaywrightManager
from .loader import Scenario, ScenarioStep
from .steps import get_step_executor


# Layer name to enum mapping
_LAYER_MAP = {
    "L1": Layer.L1_ENVIRONMENT,
    "L2": Layer.L2_NETWORK,
    "L3": Layer.L3_CONSOLE,
    "L4": Layer.L4_DOM,
    "L5": Layer.L5_PERSISTENCE,
}

_SNAPSHOT_LEVEL_MAP = {
    "minimal": SnapshotLevel.MINIMAL,
    "summary": SnapshotLevel.SUMMARY,
    "full": SnapshotLevel.FULL,
}


class ScenarioRunner:
    """
    Runs acceptance scenarios against a Playwright page using
    the closed-loop verification pattern.
    """

    def __init__(self, console_monitor=None, network_monitor=None):
        self._console_monitor = console_monitor
        self._network_monitor = network_monitor

    async def run(self, scenario: Scenario, page, config: Dict[str, Any] = None) -> ScenarioResult:
        """
        Execute a single scenario against the given page.

        For each step:
          1. Pre-check: take MINIMAL snapshot, verify page state
          2. Execute: perform the action (navigate/click/fill/etc.)
          3. Verify: run layer checkers for each specified layer
          4. Diagnose (failure only): take FULL snapshot, collect diagnostics

        Cleanup steps always run, even if main steps fail.
        """
        cfg = config or {}
        result = ScenarioResult(
            scenario_name=scenario.name,
            status=ScenarioStatus.PASSED,
            started_at=datetime.now().isoformat(),
        )

        # Run main steps
        main_failed = False
        for step in scenario.steps:
            step_result = await self._run_step(step, page, cfg)

            # Clear monitors between steps to isolate errors
            if self._console_monitor:
                self._console_monitor.clear()
            if self._network_monitor:
                self._network_monitor.clear()

            if not step_result.passed:
                main_failed = True
                # Check if this step is in must_pass - if so, stop main execution
                must_pass = scenario.acceptance_criteria.get("must_pass", [])
                if must_pass and step.name in must_pass:
                    # Must-pass step failed, skip remaining main steps
                    for remaining_step in scenario.steps[scenario.steps.index(step) + 1:]:
                        result.step_results.append(StepResult(
                            step_name=remaining_step.name,
                            status=StepStatus.SKIPPED,
                            error="Skipped: must-pass step failed",
                        ))
                    break

            result.step_results.append(step_result)

        # Run cleanup steps regardless of main step results
        for cleanup_step in scenario.cleanup:
            try:
                cleanup_result = await self._run_step(cleanup_step, page, cfg, is_cleanup=True)
                # We don't fail the scenario for cleanup failures, just log them
            except Exception as e:
                pass  # Cleanup failures don't affect scenario result

        # Determine final status
        if main_failed:
            result.status = ScenarioStatus.FAILED
        else:
            result.status = ScenarioStatus.PASSED

        result.finished_at = datetime.now().isoformat()
        return result

    async def _run_step(
        self,
        step: ScenarioStep,
        page,
        config: Dict[str, Any],
        is_cleanup: bool = False,
    ) -> StepResult:
        """Execute a single step with the closed-loop pattern."""
        start_time = time.monotonic()
        step_result = StepResult(
            step_name=step.name,
            status=StepStatus.PASSED,
        )

        # Phase 1: Pre-check (MINIMAL snapshot)
        try:
            pre_snapshot = await take_snapshot(page, SnapshotLevel.MINIMAL)
            step_result.snapshot_data = format_snapshot_for_llm(pre_snapshot)
        except Exception:
            pass  # Pre-check snapshot is optional

        # Phase 2: Execute action
        executor = get_step_executor(step.action)
        if executor is None:
            step_result.status = StepStatus.ERROR
            step_result.error = f"Unknown action: {step.action}"
            step_result.duration_ms = (time.monotonic() - start_time) * 1000
            return step_result

        try:
            action_result = await executor(page, step.target, step.value, config)
            if isinstance(action_result, dict) and action_result.get("verified") is False:
                step_result.status = StepStatus.FAILED
                step_result.error = action_result.get("reason", "Verification returned False")
                step_result.duration_ms = (time.monotonic() - start_time) * 1000
                # Diagnose on failure
                await self._diagnose_failure(page, step_result)
                return step_result
            if isinstance(action_result, dict) and action_result.get("assertion") is False:
                step_result.status = StepStatus.FAILED
                step_result.error = action_result.get("reason", f"Assertion failed: expected '{action_result.get('expected')}' in '{action_result.get('actual', '')[:50]}'")
                step_result.duration_ms = (time.monotonic() - start_time) * 1000
                await self._diagnose_failure(page, step_result)
                return step_result
        except Exception as e:
            step_result.status = StepStatus.ERROR
            step_result.error = f"Action execution error: {e}"
            step_result.duration_ms = (time.monotonic() - start_time) * 1000
            await self._diagnose_failure(page, step_result)
            return step_result

        # Phase 3: Verify layers
        for layer_name in step.layers:
            layer_enum = _LAYER_MAP.get(layer_name)
            if layer_enum is None:
                continue

            # Build context for the checker
            context = {
                "console_monitor": self._console_monitor,
                "network_monitor": self._network_monitor,
                **config,
            }

            # Add expected_selectors for L4 if specified
            if layer_enum == Layer.L4_DOM and step.metadata.get("expected_selectors"):
                context["expected_selectors"] = step.metadata["expected_selectors"]
            if layer_enum == Layer.L5_PERSISTENCE and step.metadata.get("persistence_endpoints"):
                context["persistence_endpoints"] = step.metadata["persistence_endpoints"]

            try:
                if layer_enum == Layer.L2_NETWORK:
                    checker = L2NetworkChecker(self._network_monitor)
                elif layer_enum == Layer.L3_CONSOLE:
                    checker = L3ConsoleChecker(self._console_monitor)
                elif layer_enum == Layer.L4_DOM:
                    checker = L4DOMChecker(step.metadata.get("expected_selectors"))
                elif layer_enum == Layer.L5_PERSISTENCE:
                    checker = L5PersistenceChecker()
                else:
                    checker = get_checker(layer_enum)

                layer_result = await checker.check(page, context)
                step_result.layer_results.append(layer_result)

                if not layer_result.passed:
                    step_result.status = StepStatus.FAILED
                    step_result.error = f"Layer {layer_name} failed: {layer_result.message}"
                    break

            except Exception as e:
                layer_result = LayerResult(
                    layer_name=layer_name,
                    passed=False,
                    message=f"Checker error: {e}",
                )
                step_result.layer_results.append(layer_result)
                step_result.status = StepStatus.ERROR
                step_result.error = f"Layer {layer_name} error: {e}"
                break

        # Phase 4: Diagnose (only on failure)
        if not step_result.passed:
            await self._diagnose_failure(page, step_result)

        step_result.duration_ms = (time.monotonic() - start_time) * 1000
        return step_result

    async def _diagnose_failure(self, page, step_result: StepResult) -> None:
        """Capture FULL snapshot and diagnostics for a failed step."""
        try:
            full_snapshot = await take_snapshot(page, SnapshotLevel.FULL)
            step_result.diagnostic_snapshot = format_snapshot_for_llm(full_snapshot)
        except Exception as e:
            step_result.diagnostic_snapshot = f"Diagnostic snapshot failed: {e}"

        # Append monitor summaries
        if self._console_monitor and self._console_monitor.has_errors:
            step_result.error = (step_result.error or "") + f"\nConsole: {self._console_monitor.get_error_summary()}"

        if self._network_monitor and self._network_monitor.has_failures:
            step_result.error = (step_result.error or "") + f"\nNetwork: {self._network_monitor.get_summary()}"

    async def run_all(
        self,
        scenarios: List[Scenario],
        manager: PlaywrightManager,
        config: Dict[str, Any] = None,
        fail_fast: bool = False,
    ) -> List[ScenarioResult]:
        """
        Run multiple scenarios using the given PlaywrightManager.

        Args:
            scenarios: List of Scenario objects to execute.
            manager: PlaywrightManager with active browser.
            config: Shared configuration dict.
            fail_fast: If True, stop on first scenario failure.

        Returns:
            List of ScenarioResult objects.
        """
        results = []
        cfg = config or {}

        for scenario in scenarios:
            page = await manager.new_page()

            # Get monitors attached to this page
            self._console_monitor = manager.get_console_monitor(page)
            self._network_monitor = manager.get_network_monitor(page)

            try:
                result = await self.run(scenario, page, cfg)
                results.append(result)

                if fail_fast and not result.passed:
                    break
            except Exception as e:
                results.append(ScenarioResult(
                    scenario_name=scenario.name,
                    status=ScenarioStatus.ERROR,
                    error=str(e),
                    finished_at=datetime.now().isoformat(),
                ))
                if fail_fast:
                    break
            finally:
                await page.close()

        return results
