from dataclasses import dataclass
from pathlib import Path


@dataclass
class TaskScopedResult:
    applicable: bool
    passed: bool
    checker: str
    messages: list[str]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _contains_any(content: str, needles: list[str]) -> bool:
    return any(needle in content for needle in needles)


def _require_path(repo_root: Path, relative_path: str, messages: list[str]) -> Path | None:
    path = repo_root / relative_path
    if not path.exists():
        messages.append(f"FAIL missing required file: {relative_path}")
        return None
    messages.append(f"PASS required file exists: {relative_path}")
    return path


def _require_marker(content: str, marker: str, label: str, messages: list[str]) -> None:
    if marker in content:
        messages.append(f"PASS {label}")
    else:
        messages.append(f"FAIL missing marker: {marker} ({label})")


def _require_any_marker(content: str, markers: list[str], label: str, messages: list[str]) -> None:
    if _contains_any(content, markers):
        messages.append(f"PASS {label}")
    else:
        messages.append(f"FAIL missing one of {markers} ({label})")


def _is_cockpit_gateway_task(task_text: str) -> bool:
    text = task_text.lower()
    return "cockpit_gateway" in text and "cockpit" in text


def _is_frontend_task(task_text: str) -> bool:
    text = task_text.lower()
    return (
        "frontend" in text
        or "web ui" in text
        or "openclacky/lib/clacky/web" in text
        or "harness-engine/acceptance/scenarios" in text
    )


def _check_cockpit_gateway(task_brief: Path, repo_root: Path) -> TaskScopedResult:
    messages = [
        f"task-scoped checker: cockpit_gateway",
        f"task brief: {task_brief}",
        "scope: static task acceptance; no browser or app server required",
    ]
    tool_path = _require_path(repo_root, "openclacky/lib/clacky/tools/cockpit_gateway.rb", messages)
    spec_path = _require_path(repo_root, "openclacky/spec/clacky/tools/cockpit_gateway_spec.rb", messages)
    agent_path = _require_path(repo_root, "openclacky/lib/clacky/agent.rb", messages)

    if tool_path:
        tool = _read(tool_path)
        _require_marker(tool, "class CockpitGateway < Base", "CockpitGateway subclasses tool base", messages)
        _require_marker(tool, 'self.tool_name = "cockpit_gateway"', "tool_name is cockpit_gateway", messages)
        _require_marker(tool, "Thread.current[:cockpit_context]&.fetch(:jwt, nil)", "JWT read from thread cockpit context", messages)
        _require_marker(tool, "/api/v1/gateway/authorize", "authorize endpoint is called", messages)
        _require_marker(tool, "/api/v1/gateway/invoke", "invoke endpoint is called", messages)
        _require_marker(tool, "Authorization", "Authorization header is set", messages)
        _require_marker(tool, "Bearer", "Bearer token is used", messages)
        _require_marker(tool, "open_timeout = 10", "open timeout is bounded to 10s", messages)
        _require_marker(tool, "read_timeout = 10", "read timeout is bounded to 10s", messages)
        _require_marker(tool, "denied_fields", "partial result handles denied/filtered fields", messages)
        _require_any_marker(tool, ["Errno::ECONNREFUSED", "SocketError", "Net::OpenTimeout", "Net::ReadTimeout"], "connection failures are handled", messages)

    if spec_path:
        spec = _read(spec_path).lower()
        for label, markers in [
            ("authorized scenario spec", ["authorized"]),
            ("partial scenario spec", ["partial", "[filtered]"]),
            ("denied scenario spec", ["denied"]),
            ("missing JWT spec", ["jwt", "login"]),
            ("unreachable gateway spec", ["unreachable", "econnrefused", "timeout"]),
            ("registration/name spec", ["tool_name", "registered", "registration"]),
        ]:
            _require_any_marker(spec, markers, label, messages)

    if agent_path:
        agent = _read(agent_path)
        _require_marker(agent, "Tools::CockpitGateway.new", "CockpitGateway registered in agent tools", messages)

    passed = not any(message.startswith("FAIL ") for message in messages)
    return TaskScopedResult(applicable=True, passed=passed, checker="cockpit_gateway", messages=messages)


def run_task_scoped_acceptance(task_brief: str | Path, repo_root: str | Path) -> TaskScopedResult:
    task_path = Path(task_brief)
    root = Path(repo_root)
    if not task_path.exists():
        return TaskScopedResult(False, False, "", [f"FAIL missing task brief: {task_path}"])

    task_text = _read(task_path)
    if _is_frontend_task(task_text):
        return TaskScopedResult(
            False,
            False,
            "",
            [f"frontend task requires full Playwright five-layer acceptance: {task_path.name}"],
        )
    if _is_cockpit_gateway_task(task_text):
        return _check_cockpit_gateway(task_path, root)

    return TaskScopedResult(False, False, "", [f"no task-scoped checker matched: {task_path.name}"])
