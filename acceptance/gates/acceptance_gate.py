"""
Acceptance gate - loads and runs scenarios, evaluates quality gates.
Can be called from dev_gate.py as a subprocess.
"""
import argparse
import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from acceptance.scenarios.loader import load_all_scenarios
    from acceptance.scenarios.runner import ScenarioRunner
    from acceptance.core.playwright_manager import PlaywrightManager
    from acceptance.core.config import get_config
    from acceptance.core.reporter import AcceptanceReport
    from acceptance.gates.quality_gates import load_quality_gates, evaluate_gates
    _ACCEPTANCE_DEPS_AVAILABLE = True
except ImportError as _import_err:
    _ACCEPTANCE_DEPS_AVAILABLE = False
    _ACCEPTANCE_IMPORT_ERROR = str(_import_err)

from acceptance.gates.task_scoped_checker import run_task_scoped_acceptance


def run_task_only_gate(task_brief: str, repo_root: str = None):
    """
    Run a task-scoped acceptance checker when one exists.

    The result distinguishes "not applicable" from "failed" so callers can
    safely fall back to the full E2E gate for tasks without a scoped checker.
    """
    root = Path(repo_root) if repo_root else Path.cwd()
    return run_task_scoped_acceptance(task_brief, root)


async def run_acceptance_gate(
    scenario_dir: str,
    env_name: str = "dev",
    report_dir: str = None,
    quality_gates_path: str = None,
    fail_fast: bool = False,
) -> bool:
    """
    Main acceptance gate logic.

    Returns True if all scenarios pass and all blocking quality gates pass.
    """
    config = get_config()
    cfg = {
        "base_url": config.get_env().base_url,
        "api_base_url": config.get_env().api_base_url,
        "timeout": config.get_env().timeout,
    }

    # Load scenarios
    scenarios = load_all_scenarios(scenario_dir)
    if not scenarios:
        print("[WARN] No acceptance scenarios found")
        return True  # No scenarios = pass (nothing to fail)

    print(f"[INFO] Loaded {len(scenarios)} scenarios from {scenario_dir}")

    # Build a scenario-name -> tags mapping for quality gate tag filtering
    scenario_tags_map = {s.name: s.tags for s in scenarios}

    # Run scenarios
    results = []
    async with PlaywrightManager(
        browser_type=config.browser.type,
        headless=config.browser.headless,
        viewport_width=config.browser.viewport_width,
        viewport_height=config.browser.viewport_height,
        screenshot_dir=str(config.get_screenshot_path()),
    ) as manager:
        runner = ScenarioRunner()
        results = await runner.run_all(scenarios, manager, cfg, fail_fast=fail_fast)

    # Generate report
    report_dir = Path(report_dir or config.get_report_path())
    report_file = report_dir / "acceptance.md"
    reporter = AcceptanceReport()
    report_path = reporter.generate(results, report_file, env_name=env_name)
    print(f"[INFO] Report generated: {report_path}")

    # Evaluate quality gates
    all_passed = all(r.passed for r in results)

    if quality_gates_path and Path(quality_gates_path).exists():
        gates = load_quality_gates(quality_gates_path)
        gate_results = evaluate_gates(
            gates,
            results,
            scenario_tags_map=scenario_tags_map,
        )

        for gr in gate_results:
            status = "PASS" if gr["passed"] else "FAIL"
            blocking_tag = " [BLOCKING]" if gr.get("blocking", False) else ""
            print(f"  Gate '{gr['gate_name']}': {status}{blocking_tag}")

            for cr in gr.get("condition_results", []):
                cond_status = "PASS" if cr["passed"] else "FAIL"
                print(f"    {cond_status}: {cr['message']}")

            if not gr["passed"] and gr.get("blocking", False):
                all_passed = False

    # Print summary
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    if failed:
        print("\n[acceptance-gate] Failed scenario diagnostics:")
        for result in results:
            if result.passed:
                continue
            print(f"  - scenario: {result.scenario_name}")
            if getattr(result, "error", None):
                print(f"    error: {result.error}")
                continue
            failed_steps = [
                sr for sr in result.step_results
                if not getattr(sr, "passed", False) and str(getattr(sr, "status", "")).upper().split(".")[-1] != "SKIPPED"
            ]
            if failed_steps:
                first = failed_steps[0]
                print(f"    first_failed_step: {first.step_name}")
                if first.error:
                    print(f"    reason: {first.error}")
            else:
                skipped = [sr for sr in result.step_results if str(getattr(sr, "status", "")).upper().split(".")[-1] == "SKIPPED"]
                if skipped:
                    print(f"    all_steps_skipped: {len(skipped)}")
                    if skipped[0].error:
                        print(f"    skip_reason: {skipped[0].error}")
    print(f"\n{'='*50}")
    print(f"Acceptance Gate: {'PASS' if all_passed else 'FAIL'}")
    print(f"Scenarios: {passed} passed, {failed} failed, {len(results)} total")
    print(f"{'='*50}")

    return all_passed


def main():
    parser = argparse.ArgumentParser(description="Run acceptance scenarios and evaluate quality gates")
    parser.add_argument("--scenario-dir", help="Directory containing YAML scenarios")
    parser.add_argument("--env", default="dev", help="Environment name (default: dev)")
    parser.add_argument("--report-dir", help="Directory for generated reports")
    parser.add_argument("--quality-gates", help="Path to quality-gates.yaml")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failure")
    parser.add_argument("--task-brief", help="Task brief for task-scoped acceptance")
    parser.add_argument("--task-only", action="store_true", help="Run only the task-scoped acceptance checker")
    parser.add_argument("--repo-root", help="Repository root for task-scoped acceptance")
    args = parser.parse_args()

    if args.task_only:
        if not args.task_brief:
            print("[acceptance-gate] FAIL: --task-only requires --task-brief", file=sys.stderr)
            sys.exit(1)
        result = run_task_only_gate(args.task_brief, args.repo_root)
        for message in result.messages:
            print(f"[acceptance-gate] {message}")
        if not result.applicable:
            print("[acceptance-gate] task-scoped acceptance: NOT_APPLICABLE")
            sys.exit(2)
        print(f"[acceptance-gate] task-scoped acceptance: {'PASS' if result.passed else 'FAIL'}")
        sys.exit(0 if result.passed else 1)

    if not args.scenario_dir:
        print("[acceptance-gate] FAIL: --scenario-dir is required unless --task-only is set", file=sys.stderr)
        sys.exit(1)

    if not _ACCEPTANCE_DEPS_AVAILABLE:
        print(
            f"[acceptance-gate] SKIP: acceptance dependencies not available "
            f"({_ACCEPTANCE_IMPORT_ERROR}). Install playwright to enable E2E acceptance.",
            file=sys.stderr,
        )
        sys.exit(0)

    success = asyncio.run(run_acceptance_gate(
        scenario_dir=args.scenario_dir,
        env_name=args.env,
        report_dir=args.report_dir,
        quality_gates_path=args.quality_gates,
        fail_fast=args.fail_fast,
    ))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
