"""Tests for acceptance.scenarios.loader module."""
import os
import re
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from acceptance.scenarios.loader import (
    Scenario,
    ScenarioStep,
    load_all_scenarios,
    load_scenario,
    resolve_env_vars,
    validate_scenario,
)

FIXTURE_YAML = """
name: "测试场景"
description: "用于单元测试的场景"
feature: "test"
tags: ["smoke", "test"]
environment: "dev"
preconditions:
  - "前置条件1"
steps:
  - name: "步骤1"
    action: navigate
    target: "/test"
    layers: [L1, L2]
  - name: "步骤2"
    action: fill
    target: "input[name='q']"
    value: "test query"
  - name: "步骤3"
    action: verify
    target: ".result"
    layers: [L3, L4]
    snapshot_level: summary
cleanup:
  - name: "清理"
    action: click
    target: ".reset"
acceptance_criteria:
  must_pass: ["步骤1", "步骤3"]
pass_condition:
  min_reward: 0.7
  must_pass_all_required: true
"""


@pytest.fixture
def fixture_yaml_file(tmp_path):
    """Create a temporary YAML scenario file."""
    yaml_path = tmp_path / "test_scenario.yaml"
    yaml_path.write_text(FIXTURE_YAML, encoding="utf-8")
    return str(yaml_path)


class TestLoadScenario:
    """Tests for the load_scenario function."""

    def test_load_scenario(self, fixture_yaml_file):
        scenario = load_scenario(fixture_yaml_file)
        assert isinstance(scenario, Scenario)
        assert scenario.name == "测试场景"

    def test_load_scenario_description(self, fixture_yaml_file):
        scenario = load_scenario(fixture_yaml_file)
        assert scenario.description == "用于单元测试的场景"

    def test_load_scenario_steps(self, fixture_yaml_file):
        scenario = load_scenario(fixture_yaml_file)
        assert len(scenario.steps) == 3
        assert isinstance(scenario.steps[0], ScenarioStep)
        assert scenario.steps[0].name == "步骤1"
        assert scenario.steps[0].action == "navigate"
        assert scenario.steps[1].name == "步骤2"
        assert scenario.steps[1].action == "fill"
        assert scenario.steps[2].name == "步骤3"
        assert scenario.steps[2].action == "verify"

    def test_load_scenario_cleanup(self, fixture_yaml_file):
        scenario = load_scenario(fixture_yaml_file)
        assert len(scenario.cleanup) == 1
        assert scenario.cleanup[0].name == "清理"
        assert scenario.cleanup[0].action == "click"

    def test_load_scenario_tags(self, fixture_yaml_file):
        scenario = load_scenario(fixture_yaml_file)
        assert scenario.tags == ["smoke", "test"]

    def test_load_scenario_acceptance(self, fixture_yaml_file):
        scenario = load_scenario(fixture_yaml_file)
        assert scenario.acceptance_criteria["must_pass"] == ["步骤1", "步骤3"]

    def test_load_scenario_pass_condition(self, fixture_yaml_file):
        scenario = load_scenario(fixture_yaml_file)
        assert scenario.pass_condition["min_reward"] == 0.7
        assert scenario.pass_condition["must_pass_all_required"] is True

    def test_load_scenario_preconditions(self, fixture_yaml_file):
        scenario = load_scenario(fixture_yaml_file)
        assert scenario.preconditions == ["前置条件1"]

    def test_load_scenario_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_scenario("/nonexistent/path/scenario.yaml")


class TestResolveEnvVars:
    """Tests for the loader's resolve_env_vars function."""

    def test_resolve_env_vars(self):
        """${HOME} resolves to os.environ['HOME']."""
        home = os.environ.get("HOME")
        if home is None:
            # On Windows, try USERPROFILE
            home = os.environ.get("USERPROFILE")
            if home is None:
                pytest.skip("Neither HOME nor USERPROFILE is set")
            result = resolve_env_vars("${USERPROFILE}")
        else:
            result = resolve_env_vars("${HOME}")
        assert result == home

    def test_resolve_env_vars_default(self):
        result = resolve_env_vars("${MISSING_VAR_FOR_TEST_12345:fallback}")
        assert result == "fallback"


class TestValidateScenario:
    """Tests for the validate_scenario function."""

    def test_validate_scenario_valid(self, fixture_yaml_file):
        scenario = load_scenario(fixture_yaml_file)
        errors = validate_scenario(scenario)
        assert errors == []

    def test_validate_scenario_no_steps(self):
        scenario = Scenario(name="empty", steps=[])
        errors = validate_scenario(scenario)
        assert len(errors) > 0
        assert any("no steps" in e.lower() for e in errors)

    def test_validate_scenario_invalid_action(self):
        scenario = Scenario(
            name="bad action",
            steps=[
                ScenarioStep(name="step1", action="invalid_action", target="/test")
            ],
        )
        errors = validate_scenario(scenario)
        assert len(errors) > 0
        assert any("invalid action" in e.lower() for e in errors)

    def test_validate_scenario_accepts_text_quality_action(self):
        scenario = Scenario(
            name="copy quality",
            steps=[
                ScenarioStep(
                    name="visible copy is localized",
                    action="assert_text_quality",
                    target="body",
                    value={"required_text": ["仪表盘"], "forbidden_text": ["dashboard.title"]},
                )
            ],
        )

        assert validate_scenario(scenario) == []

    def test_frontend_dashboard_scenario_requires_auth_ui_and_i18n_quality(self):
        scenario = load_scenario("harness-engine/acceptance/scenarios/dashboard.yaml")
        step_names = [step.name for step in scenario.steps]
        required_steps = {
            "验证侧边栏与标题没有文案键泄漏",
            "验证仪表盘是一级侧边栏菜单",
            "验证右上角用户头像可见",
            "验证退出登录入口可见",
        }

        assert required_steps.issubset(set(step_names))
        assert required_steps.issubset(set(scenario.acceptance_criteria["must_pass"]))

        avatar_step = next(step for step in scenario.steps if step.name == "验证右上角用户头像可见")
        logout_step = next(step for step in scenario.steps if step.name == "验证退出登录入口可见")
        assert avatar_step.target == "#top-header #header-right > #user-identity .user-menu-avatar"
        assert logout_step.target == "#top-header #header-right > #user-identity .logout-button:has-text('退出登录')"

        top_level_step = next(step for step in scenario.steps if step.name == "验证仪表盘是一级侧边栏菜单")
        assert top_level_step.target == "#config-nav-items > #dashboard-sidebar-item #dashboard-sidebar-label"
        assert top_level_step.value == "仪表盘"

    def test_dashboard_sidebar_markup_is_top_level_and_localized(self):
        web_root = Path("openclacky/lib/clacky/web")
        html = (web_root / "index.html").read_text(encoding="utf-8")
        i18n = (web_root / "i18n.js").read_text(encoding="utf-8")

        config_nav = re.search(
            r'<div id="config-nav-items">(?P<body>.*?)\n\s*</div>\s*\n\s*</div>\s*\n\s*<!-- My Data Group',
            html,
            re.DOTALL,
        )
        assert config_nav, "config sidebar group should be parseable"

        direct_item_ids = re.findall(r'\n\s{10}<div id="([^"]+)" class="task-item task-item-summary">', config_nav.group("body"))
        assert direct_item_ids == [
            "tasks-sidebar-item",
            "skills-sidebar-item",
            "channels-sidebar-item",
            "dashboard-sidebar-item",
        ]
        assert 'id="dashboard-sidebar-label" data-i18n="sidebar.dashboard">仪表盘</span>' in html
        assert '"sidebar.dashboard": "Dashboard"' in i18n
        assert '"sidebar.dashboard": "仪表盘"' in i18n

    def test_header_identity_controls_do_not_depend_on_reading_httponly_cookie(self):
        web_root = Path("openclacky/lib/clacky/web")
        html = (web_root / "index.html").read_text(encoding="utf-8")
        app_js = (web_root / "app.js").read_text(encoding="utf-8")
        http_server = Path("openclacky/lib/clacky/server/http_server.rb").read_text(encoding="utf-8")
        patch_app_js = Path("patches/openclacky/app.js").read_text(encoding="utf-8")
        patch_http_server = Path("patches/openclacky/http_server.rb").read_text(encoding="utf-8")
        design = Path("docs/m4-dashboard-agent/design.md").read_text(encoding="utf-8")

        assert "HttpOnly" in design
        assert 'id="header-right"' in html
        assert 'id="user-identity"' in html
        assert 'class="user-menu-avatar"' in html
        assert 'class="logout-button" onclick="CockpitAuth.logout()">退出登录</button>' in html
        assert app_js.count("COCKPIT_USER_CONTEXT") >= 1
        assert patch_app_js.count("COCKPIT_USER_CONTEXT") >= 1
        assert "function getCookie" not in app_js
        assert "getCookie('cockpit_jwt')" not in app_js
        assert "function getCookie" not in patch_app_js
        assert "getCookie('cockpit_jwt')" not in patch_app_js
        assert "window.COCKPIT_USER_CONTEXT" in http_server
        assert "window.COCKPIT_USER_CONTEXT" in patch_http_server
        assert "cockpit.jwt" not in re.search(
            r"window\.COCKPIT_USER_CONTEXT.*?</script>",
            http_server,
            re.DOTALL,
        ).group(0)

    def test_validate_scenario_no_name(self):
        scenario = Scenario(name="", steps=[ScenarioStep(name="s1", action="verify", target=".x")])
        errors = validate_scenario(scenario)
        assert any("no name" in e.lower() for e in errors)


class TestLoadAllScenarios:
    """Tests for the load_all_scenarios function."""

    def test_load_all_scenarios(self, tmp_path):
        # Create multiple scenario files
        yaml1 = tmp_path / "scenario_a.yaml"
        yaml1.write_text(
            """
name: "Scenario A"
steps:
  - name: "Go"
    action: navigate
    target: "/a"
""",
            encoding="utf-8",
        )
        yaml2 = tmp_path / "scenario_b.yaml"
        yaml2.write_text(
            """
name: "Scenario B"
steps:
  - name: "Go"
    action: navigate
    target: "/b"
""",
            encoding="utf-8",
        )
        scenarios = load_all_scenarios(str(tmp_path))
        assert len(scenarios) == 2
        names = [s.name for s in scenarios]
        assert "Scenario A" in names
        assert "Scenario B" in names

    def test_load_all_scenarios_skips_templates(self, tmp_path):
        # Create a normal file and a template file
        normal = tmp_path / "normal_scenario.yaml"
        normal.write_text(
            """
name: "Normal"
steps:
  - name: "Go"
    action: navigate
    target: "/test"
""",
            encoding="utf-8",
        )
        template = tmp_path / "template_scenario.yaml"
        template.write_text(
            """
name: "Template"
steps:
  - name: "Go"
    action: navigate
    target: "/template"
""",
            encoding="utf-8",
        )
        scenarios = load_all_scenarios(str(tmp_path))
        assert len(scenarios) == 1
        assert scenarios[0].name == "Normal"

    def test_load_all_scenarios_missing_dir(self):
        scenarios = load_all_scenarios("/nonexistent/directory/path")
        assert scenarios == []
