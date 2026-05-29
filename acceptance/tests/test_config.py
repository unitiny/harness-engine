"""Tests for acceptance.core.config module."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from acceptance.core.config import AcceptanceConfig, load_config, resolve_env_vars


class TestAcceptanceConfig:
    """Tests for AcceptanceConfig dataclass defaults."""

    def test_default_config(self):
        config = AcceptanceConfig()
        assert config.browser.type == "chromium"
        assert config.browser.headless is True
        assert config.current_env == "dev"
        assert config.retry.count == 2
        assert config.retry.delay_ms == 1000
        assert config.screenshot_dir == "reports/screenshots"
        assert config.report_dir == "reports"
        assert config.scenario_dir == "scenarios"


class TestResolveEnvVars:
    """Tests for the resolve_env_vars function."""

    def test_resolve_env_vars_existing(self):
        """${HOME} resolves to the actual HOME environment variable."""
        home = os.environ.get("HOME")
        if home is None:
            # On Windows, HOME may not be set; use USERPROFILE instead
            home = os.environ.get("USERPROFILE")
            if home is None:
                pytest.skip("Neither HOME nor USERPROFILE is set in environment")
            result = resolve_env_vars("${USERPROFILE}")
        else:
            result = resolve_env_vars("${HOME}")
        assert result == home

    def test_resolve_env_vars_default(self):
        """${MISSING:default_value} resolves to the default when var is not set."""
        result = resolve_env_vars("${MISSING_VAR_FOR_TEST_12345:default}")
        assert result == "default"

    def test_resolve_env_vars_no_default(self):
        """${NO_DEFAULT} stays as-is when the variable is not set."""
        result = resolve_env_vars("${NO_DEFAULT_VAR_FOR_TEST_12345}")
        assert result == "${NO_DEFAULT_VAR_FOR_TEST_12345}"


class TestLoadConfig:
    """Tests for the load_config function."""

    def test_load_config_missing_file(self):
        """Loading a non-existent file returns default config without crashing."""
        config = load_config("/nonexistent/path/env.yaml")
        assert isinstance(config, AcceptanceConfig)
        assert config.browser.type == "chromium"
        assert config.browser.headless is True

    def test_load_config_valid_yaml(self, tmp_path):
        """Loading a valid YAML file populates the config correctly."""
        yaml_content = """
default_env: staging
browser:
  type: firefox
  headless: false
retry:
  count: 3
  delay_ms: 500
"""
        yaml_file = tmp_path / "env.yaml"
        yaml_file.write_text(yaml_content, encoding="utf-8")
        config = load_config(str(yaml_file))
        assert config.current_env == "staging"
        assert config.browser.type == "firefox"
        assert config.browser.headless is False
        assert config.retry.count == 3
        assert config.retry.delay_ms == 500


class TestEnvOverride:
    """Tests for ACCEPTANCE_ENV environment variable override."""

    def test_env_override(self, tmp_path):
        """Setting ACCEPTANCE_ENV overrides the current_env in the loaded config."""
        yaml_content = """
default_env: dev
"""
        yaml_file = tmp_path / "env.yaml"
        yaml_file.write_text(yaml_content, encoding="utf-8")
        old = os.environ.get("ACCEPTANCE_ENV")
        try:
            os.environ["ACCEPTANCE_ENV"] = "production"
            config = load_config(str(yaml_file))
            assert config.current_env == "production"
        finally:
            if old is None:
                os.environ.pop("ACCEPTANCE_ENV", None)
            else:
                os.environ["ACCEPTANCE_ENV"] = old
