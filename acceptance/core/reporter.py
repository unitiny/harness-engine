"""
Acceptance report generator.

Produces Markdown reports from a list of ScenarioResult objects with the
structure:

    Title -> Summary Table -> Per-Scenario Details -> Overall Conclusion

Each scenario detail includes a step-results table, failure diagnostics
(only for failed steps), console-error summaries, and network-error
summaries.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..scenarios.runner import ScenarioResult
from .result import ScenarioStatus, StepResult, StepStatus, LayerResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_SNAPSHOT_EXCERPT_LINES = 40
_MAX_DIAGNOSTIC_SUGGESTIONS = 10

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_duration(ms: float) -> str:
    """Return a human-friendly duration string from milliseconds."""
    if ms < 1_000:
        return f"{ms:.0f}ms"
    return f"{ms / 1_000:.1f}s"


def _status_label(status: ScenarioStatus | StepStatus) -> str:
    """Return a short PASS / FAIL / ERROR / SKIP label."""
    _map = {
        ScenarioStatus.PASSED: "PASS",
        ScenarioStatus.FAILED: "FAIL",
        ScenarioStatus.ERROR: "ERROR",
        StepStatus.PASSED: "PASS",
        StepStatus.FAILED: "FAIL",
        StepStatus.ERROR: "ERROR",
        StepStatus.SKIPPED: "SKIP",
    }
    return _map.get(status, str(status.value))


def _truncate(text: str, max_lines: int = _MAX_SNAPSHOT_EXCERPT_LINES) -> str:
    """Keep only the first *max_lines* lines of *text*."""
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    kept = "\n".join(lines[:max_lines])
    kept += f"\n... ({len(lines) - max_lines} more lines truncated)"
    return kept


# ---------------------------------------------------------------------------
# AcceptanceReport
# ---------------------------------------------------------------------------


class AcceptanceReport:
    """Generates Markdown acceptance-test reports from ScenarioResult lists.

    Usage::

        report = AcceptanceReport()
        path = report.generate(results, Path("reports/acceptance.md"), env_name="staging")
        print(report.generate_summary(results))

    The public API intentionally consists of two methods:

    * ``generate``  -- writes a full Markdown report to disk and returns the Path.
    * ``generate_summary`` -- returns a single-line summary string.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        scenario_results: List[ScenarioResult],
        output_path: Path,
        env_name: str = "dev",
        feature: str = "",
    ) -> Path:
        """Generate a full Markdown report and write it to *output_path*.

        Args:
            scenario_results: Ordered list of scenario results.
            output_path: Destination file path.  Parent directories are created
                         automatically when they do not exist.
            env_name: Environment label (e.g. "dev", "staging").
            feature: Optional feature / test-run name used in the title.

        Returns:
            The absolute Path to the written report file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        markdown = self._build_report(scenario_results, env_name, feature)
        output_path.write_text(markdown, encoding="utf-8")
        return output_path.resolve()

    def generate_summary(self, scenario_results: List[ScenarioResult]) -> str:
        """Return a single-line human-readable summary.

        Example::

            "5 scenarios: 4 passed, 1 failed (FAIL)"
        """
        if not scenario_results:
            return "0 scenarios: no results"

        total = len(scenario_results)
        passed = sum(1 for r in scenario_results if r.passed)
        failed = total - passed
        overall = "PASS" if failed == 0 else "FAIL"

        parts = [f"{total} scenario{'s' if total != 1 else ''}"]
        if passed:
            parts.append(f"{passed} passed")
        if failed:
            parts.append(f"{failed} failed")
        return f"{', '.join(parts)} ({overall})"

    # ------------------------------------------------------------------
    # Internal: report assembly
    # ------------------------------------------------------------------

    def _build_report(
        self,
        results: List[ScenarioResult],
        env_name: str,
        feature: str,
    ) -> str:
        """Assemble the complete Markdown string."""
        sections: List[str] = []

        # -- Header -------------------------------------------------------
        title = feature or "Acceptance Test Run"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        overall_status = "PASS" if failed == 0 else "FAIL"

        sections.append(f"# 验收报告: {title}")
        sections.append("")
        sections.append(f"**时间**: {timestamp}")
        sections.append(f"**环境**: {env_name}")
        sections.append(f"**总场景**: {total} | 通过: {passed} | 失败: {failed}")
        sections.append(f"**结论**: {overall_status}")
        sections.append("")
        sections.append("---")
        sections.append("")

        # -- Empty-results guard ------------------------------------------
        if total == 0:
            sections.append("无场景结果。")
            sections.append("")
            return "\n".join(sections)

        # -- Scenario summary table ---------------------------------------
        sections.append("## 场景结果汇总")
        sections.append("")
        sections.append("| 场景 | 状态 | 步骤通过 | 耗时 |")
        sections.append("|------|------|---------|------|")
        for r in results:
            name = r.scenario_name
            status = _status_label(r.status)
            step_ratio = f"{r.passed_steps}/{r.total_steps}"
            duration = _format_duration(r.duration_ms)
            sections.append(f"| {name} | {status} | {step_ratio} | {duration} |")
        sections.append("")
        sections.append("---")
        sections.append("")

        # -- Per-scenario details -----------------------------------------
        for r in results:
            sections.append(f"## 场景详情: {r.scenario_name}")
            sections.append("")

            # Step results table
            sections.append("| 步骤 | 状态 | 层检查 | 耗时 |")
            sections.append("|------|------|--------|------|")
            for sr in r.step_results:
                step_name = sr.step_name
                step_status = _status_label(sr.status)
                layer_labels = self._format_layer_labels(sr)
                step_dur = _format_duration(sr.duration_ms)
                sections.append(
                    f"| {step_name} | {step_status} | {layer_labels} | {step_dur} |"
                )
            sections.append("")

            # Failure diagnostics for failed / errored steps (not skipped)
            failed_steps = [
                sr for sr in r.step_results
                if sr.status in (StepStatus.FAILED, StepStatus.ERROR)
            ]
            if failed_steps:
                sections.append("### 失败诊断")
                sections.append("")
                for sr in failed_steps:
                    sections.append(f"**步骤**: {sr.step_name}")
                    # Find the first failed layer to report layer info
                    fl = sr.failed_layers
                    if fl:
                        sections.append(f"**层**: {fl[0].layer_name}")
                        if fl[0].message:
                            sections.append(f"**原因**: {fl[0].message}")
                    elif sr.error:
                        sections.append(f"**原因**: {sr.error}")
                    if sr.diagnostic_snapshot:
                        sections.append(
                            f"**诊断快照**: {_truncate(sr.diagnostic_snapshot)}"
                        )
                    elif sr.error and not fl:
                        # Error without layer results (e.g. action execution error)
                        sections.append(f"**错误**: {sr.error}")
                    sections.append("")

            # Console errors (extracted from layer results)
            console_lines = self._extract_console_errors(r)
            if console_lines:
                sections.append("### 控制台错误")
                sections.append("")
                for line in console_lines:
                    sections.append(f"- {line}")
                sections.append("")

            # Network errors (extracted from layer results)
            network_lines = self._extract_network_errors(r)
            if network_lines:
                sections.append("### 网络错误")
                sections.append("")
                for line in network_lines:
                    sections.append(f"- {line}")
                sections.append("")

            sections.append("---")
            sections.append("")

        # -- Overall conclusion -------------------------------------------
        sections.append("## 总结论")
        sections.append("")
        if overall_status == "PASS":
            sections.append("**PASS** - All scenarios passed.")
        else:
            sections.append(
                f"**FAIL** - {failed} scenario{'s' if failed != 1 else ''} failed. "
                "See details above."
            )

        # Suggestions (only on failure)
        if failed > 0:
            suggestions = self._generate_suggestions(results)
            if suggestions:
                sections.append("")
                sections.append("### 建议")
                sections.append("")
                for idx, suggestion in enumerate(suggestions, start=1):
                    sections.append(f"{idx}. {suggestion}")

        sections.append("")
        return "\n".join(sections)

    # ------------------------------------------------------------------
    # Internal: formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_layer_labels(step_result: StepResult) -> str:
        """Return a comma-separated list of passed layer names (e.g. "L1,L2").

        Failed layers are not included in the label -- they appear in the
        diagnostics section instead.  Returns ``-`` when no layers were
        checked.
        """
        if not step_result.layer_results:
            return "-"
        passed_names = [
            lr.layer_name for lr in step_result.layer_results if lr.passed
        ]
        return ",".join(passed_names) if passed_names else "-"

    @staticmethod
    def _extract_console_errors(scenario: ScenarioResult) -> List[str]:
        """Collect console error messages from L3 layer results."""
        lines: List[str] = []
        for sr in scenario.step_results:
            for lr in sr.layer_results:
                if lr.layer_name == "L3_CONSOLE" and not lr.passed:
                    msg = lr.message or "Unknown console error"
                    lines.append(f"[ERROR] {msg}")
                    # Include individual errors from details if available
                    errors = lr.details.get("errors", [])
                    if isinstance(errors, list):
                        for err in errors[:5]:
                            err_str = str(err)
                            if err_str not in msg:
                                lines.append(f"  - {err_str}")
        return lines

    @staticmethod
    def _extract_network_errors(scenario: ScenarioResult) -> List[str]:
        """Collect network error messages from L2 layer results."""
        lines: List[str] = []
        for sr in scenario.step_results:
            for lr in sr.layer_results:
                if lr.layer_name == "L2_NETWORK" and not lr.passed:
                    msg = lr.message or "Network error"
                    lines.append(f"[FAIL] {msg}")
                    # Include individual failures from details if available
                    failures = lr.details.get("failures", [])
                    if isinstance(failures, list):
                        for fail in failures[:5]:
                            fail_str = str(fail)
                            if fail_str not in msg:
                                lines.append(f"  - {fail_str}")
        return lines

    @staticmethod
    def _generate_suggestions(results: List[ScenarioResult]) -> List[str]:
        """Derive actionable suggestions from the failed scenarios.

        This is a best-effort heuristic that inspects common failure
        patterns (timeouts, 401/403, missing elements) and produces
        numbered suggestion items.
        """
        suggestions: List[str] = []
        seen: set[str] = set()

        for r in results:
            if r.passed:
                continue

            for sr in r.step_results:
                if sr.passed or sr.status == StepStatus.SKIPPED:
                    continue

                error_text = (sr.error or "").lower()
                step_label = f"[{r.scenario_name}] {sr.step_name}"

                # Authentication / authorization
                if any(token in error_text for token in ("401", "403", "unauthorized", "token")):
                    suggestion = f"Fix authentication/authorization issue in step {step_label}"
                    if suggestion not in seen:
                        seen.add(suggestion)
                        suggestions.append(suggestion)

                # Element not found / DOM
                elif any(token in error_text for token in ("not found", "no element", "timeout", "waiting for selector")):
                    suggestion = f"Investigate missing element or timeout in step {step_label}"
                    if suggestion not in seen:
                        seen.add(suggestion)
                        suggestions.append(suggestion)

                # Network / fetch
                elif any(token in error_text for token in ("fetch", "network", "cors", "failed to")):
                    suggestion = f"Investigate network or CORS issue in step {step_label}"
                    if suggestion not in seen:
                        seen.add(suggestion)
                        suggestions.append(suggestion)

                # Generic fallback
                else:
                    suggestion = f"Resolve failure in step {step_label}: {sr.error or 'unknown error'}"
                    if suggestion not in seen:
                        seen.add(suggestion)
                        suggestions.append(suggestion)

                if len(suggestions) >= _MAX_DIAGNOSTIC_SUGGESTIONS:
                    return suggestions

        return suggestions
