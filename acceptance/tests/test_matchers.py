"""Tests for acceptance.scenarios.matchers module."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from acceptance.scenarios.matchers import (
    MatchMode,
    MatcherRegistry,
    find_text_quality_issues,
    json_matches,
    network_call_succeeded,
    text_matches,
)


class TestTextMatches:
    """Tests for the text_matches function."""

    def test_text_matches_exact(self):
        assert text_matches("hello", "hello", MatchMode.EXACT) is True

    def test_text_matches_exact_fail(self):
        assert text_matches("hello", "Hello", MatchMode.EXACT) is False

    def test_text_matches_contains(self):
        assert text_matches("hello world", "world", MatchMode.CONTAINS) is True

    def test_text_matches_contains_fail(self):
        assert text_matches("hello world", "xyz", MatchMode.CONTAINS) is False

    def test_text_matches_regex(self):
        assert text_matches("error-404", r"error-\d+", MatchMode.REGEX) is True

    def test_text_matches_regex_fail(self):
        assert text_matches("error-abc", r"error-\d+", MatchMode.REGEX) is False

    def test_text_matches_starts_with(self):
        assert text_matches("hello world", "hello", MatchMode.STARTS_WITH) is True

    def test_text_matches_starts_with_fail(self):
        assert text_matches("hello world", "world", MatchMode.STARTS_WITH) is False

    def test_text_matches_ends_with(self):
        assert text_matches("hello world", "world", MatchMode.ENDS_WITH) is True

    def test_text_matches_ends_with_fail(self):
        assert text_matches("hello world", "hello", MatchMode.ENDS_WITH) is False

    def test_text_matches_case_insensitive(self):
        """Contains mode ignores case."""
        assert text_matches("Hello World", "hello", MatchMode.CONTAINS) is True
        assert text_matches("Hello World", "WORLD", MatchMode.CONTAINS) is True

    def test_text_matches_invalid_regex(self):
        """Invalid regex returns False instead of crashing."""
        assert text_matches("some text", r"[invalid", MatchMode.REGEX) is False


class TestNetworkCallSucceeded:
    """Tests for the network_call_succeeded function."""

    def test_200_succeeded(self):
        assert network_call_succeeded(200) is True

    def test_201_succeeded(self):
        assert network_call_succeeded(201) is True

    def test_301_succeeded(self):
        assert network_call_succeeded(301) is True

    def test_404_failed(self):
        assert network_call_succeeded(404) is False

    def test_500_failed(self):
        assert network_call_succeeded(500) is False

    def test_none_failed(self):
        assert network_call_succeeded(None) is False


class TestJsonMatches:
    """Tests for the json_matches function."""

    def test_json_matches_subset(self):
        actual = {"a": 1, "b": 2}
        expected = {"a": 1}
        assert json_matches(actual, expected, mode="subset") is True

    def test_json_matches_subset_fail(self):
        actual = {"a": 1}
        expected = {"b": 2}
        assert json_matches(actual, expected, mode="subset") is False

    def test_json_matches_subset_nested(self):
        actual = {"user": {"name": "Alice", "age": 30, "email": "alice@test.com"}}
        expected = {"user": {"name": "Alice"}}
        assert json_matches(actual, expected, mode="subset") is True

    def test_json_matches_exact(self):
        assert json_matches({"a": 1}, {"a": 1}, mode="exact") is True

    def test_json_matches_exact_fail(self):
        assert json_matches({"a": 1}, {"a": 2}, mode="exact") is False

    def test_json_matches_contains(self):
        actual = {"key": "hello world"}
        expected = "hello"
        assert json_matches(actual, expected, mode="contains") is True

    def test_json_matches_contains_fail(self):
        actual = {"key": "hello world"}
        expected = "xyz"
        assert json_matches(actual, expected, mode="contains") is False


class TestTextQualityIssues:
    """Tests for visible UI text quality checks."""

    def test_flags_i18n_keys_and_english_placeholders(self):
        text = "dashboard.title\nsidebar.dashboard\nPlease log in first"
        issues = find_text_quality_issues(
            text,
            forbidden_patterns=[r"\bdashboard\.[a-zA-Z0-9_.-]+", r"\bsidebar\.[a-zA-Z0-9_.-]+"],
            forbidden_text=["Please log in first"],
        )

        assert "dashboard.title" in issues
        assert "sidebar.dashboard" in issues
        assert "Please log in first" in issues

    def test_requires_expected_chinese_labels(self):
        text = "对话\n任务管理\n技能管理"
        issues = find_text_quality_issues(
            text,
            required_text=["仪表盘", "退出登录"],
        )

        assert "missing required text: 仪表盘" in issues
        assert "missing required text: 退出登录" in issues


class TestMatcherRegistry:
    """Tests for the MatcherRegistry class."""

    def test_matcher_registry_has_defaults(self):
        registry = MatcherRegistry()
        names = registry.list_matchers()
        assert len(names) > 0
        # Verify key matchers are registered
        assert "text" in names
        assert "network_ok" in names
        assert "json" in names

    def test_matcher_registry_get_unknown(self):
        registry = MatcherRegistry()
        result = registry.get("nonexistent_matcher_xyz")
        assert result is None

    def test_matcher_registry_register_custom(self):
        registry = MatcherRegistry()
        registry.register("custom", lambda x: x > 0)
        assert registry.get("custom") is not None
        assert "custom" in registry.list_matchers()
