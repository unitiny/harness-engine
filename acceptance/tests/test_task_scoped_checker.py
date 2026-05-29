import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from acceptance.gates.acceptance_gate import run_task_only_gate
from acceptance.gates.task_scoped_checker import run_task_scoped_acceptance


def write_cockpit_gateway_fixture(repo_root: Path, *, include_authorize: bool = True) -> Path:
    tool_path = repo_root / "openclacky" / "lib" / "clacky" / "tools" / "cockpit_gateway.rb"
    spec_path = repo_root / "openclacky" / "spec" / "clacky" / "tools" / "cockpit_gateway_spec.rb"
    agent_path = repo_root / "openclacky" / "lib" / "clacky" / "agent.rb"
    task_path = repo_root / "harness-engine" / ".dev-harness" / "task-briefs" / "013-2026-05-26-cockpit-gateway.md"

    tool_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    agent_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.parent.mkdir(parents=True, exist_ok=True)

    authorize_path = 'post_json("/api/v1/gateway/authorize", {}, jwt)' if include_authorize else ""
    tool_path.write_text(
        f"""
module Clacky
  module Tools
    class CockpitGateway < Base
      self.tool_name = "cockpit_gateway"
      self.tool_category = "data"

      def execute(query:, tool_id: "rental_occupancy_query", **kwargs)
        jwt = Thread.current[:cockpit_context]&.fetch(:jwt, nil)
        return {{ error: "login required" }} unless jwt
        {authorize_path}
        post_json("/api/v1/gateway/invoke", {{}}, jwt)
        denied_fields = []
      end

      def post_json(path, body, jwt)
        http.open_timeout = 10
        http.read_timeout = 10
        request["Authorization"] = "Bearer #{{jwt}}"
      rescue Errno::ECONNREFUSED, SocketError, Net::OpenTimeout, Net::ReadTimeout
        {{ "error" => "gateway unavailable" }}
      end
    end
  end
end
""",
        encoding="utf-8",
    )
    spec_path.write_text(
        """
RSpec.describe Clacky::Tools::CockpitGateway do
  it("returns full data for authorized decision") {}
  it("returns data with [FILTERED] markers and warning for partial decision") {}
  it("returns denial message when decision is denied") {}
  it("returns login-required error when JWT is nil") {}
  it("returns connection error when cockpit-api is unreachable") {}
  it("has correct tool_name") {}
end
""",
        encoding="utf-8",
    )
    agent_path.write_text("@tool_registry.register(Tools::CockpitGateway.new)\n", encoding="utf-8")
    task_path.write_text(
        """
# cockpit_gateway Tool

## Task Status
Task Status: BLOCKED

## Goal
Create the cockpit_gateway Tool.
""",
        encoding="utf-8",
    )
    return task_path


def test_cockpit_gateway_task_checker_passes_without_servers(tmp_path):
    task_path = write_cockpit_gateway_fixture(tmp_path)

    result = run_task_scoped_acceptance(task_path, tmp_path)

    assert result.applicable
    assert result.passed
    assert result.checker == "cockpit_gateway"
    assert any("no browser or app server required" in message for message in result.messages)


def test_cockpit_gateway_task_checker_fails_when_required_marker_missing(tmp_path):
    task_path = write_cockpit_gateway_fixture(tmp_path, include_authorize=False)

    result = run_task_scoped_acceptance(task_path, tmp_path)

    assert result.applicable
    assert not result.passed
    assert any("/api/v1/gateway/authorize" in message for message in result.messages)


def test_task_only_gate_returns_not_applicable_for_unmatched_task(tmp_path):
    task_path = tmp_path / "harness-engine" / ".dev-harness" / "task-briefs" / "014-2026-05-26-other.md"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text("# Other task\n", encoding="utf-8")

    result = run_task_only_gate(str(task_path), str(tmp_path))

    assert not result.applicable
    assert not result.passed


def test_task_scoped_checker_never_matches_frontend_web_ui_tasks(tmp_path):
    task_path = tmp_path / "harness-engine" / ".dev-harness" / "task-briefs" / "011-2026-05-26-dashboard.md"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        """
# Dashboard Web UI

## Layer

frontend

## Goal

Implement OpenClacky Dashboard panel in openclacky/lib/clacky/web.
""",
        encoding="utf-8",
    )

    result = run_task_scoped_acceptance(task_path, tmp_path)

    assert not result.applicable
    assert not result.passed
    assert any("frontend" in message.lower() for message in result.messages)
