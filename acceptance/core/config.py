"""Configuration system for the acceptance testing framework.

Loads settings from env.yaml and provides typed access to browser, retry,
environment, and path configuration. Supports environment variable
substitution using ${VAR} and ${VAR:default} syntax.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment-variable substitution
# ---------------------------------------------------------------------------

_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def resolve_env_vars(value: str) -> str:
    """Replace ``${VAR}`` and ``${VAR:default}`` patterns with env values.

    * ``${MY_VAR}`` -- replaced with the value of *MY_VAR*, or left as-is
      if the variable is not set.
    * ``${MY_VAR:fallback}`` -- replaced with the value of *MY_VAR*, or
      *fallback* when the variable is not set.

    Parameters
    ----------
    value:
        The string potentially containing ``${...}`` placeholders.

    Returns
    -------
    str
        The string with all placeholders resolved.
    """

    def _replacer(match: re.Match) -> str:
        content = match.group(1)
        if ":" in content:
            var_name, default = content.split(":", 1)
            return os.environ.get(var_name, default)
        return os.environ.get(content, match.group(0))

    # Iteratively resolve nested references (e.g. ${A${B}}) up to 3 levels.
    result = value
    for _ in range(3):
        new_result = _ENV_VAR_PATTERN.sub(_replacer, result)
        if new_result == result:
            break
        result = new_result
    return result


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class BrowserConfig:
    """Browser launch and viewport configuration."""

    type: str = "chromium"  # chromium | firefox | webkit
    headless: bool = True
    slow_mo: int = 0
    viewport_width: int = 1280
    viewport_height: int = 720


@dataclass
class RetryConfig:
    """Retry policy for flaky steps."""

    count: int = 2
    delay_ms: int = 1000


@dataclass
class EnvironmentConfig:
    """Per-environment settings (dev, staging, production, ...)."""

    name: str
    base_url: str
    api_base_url: str = ""
    auth_url: str = ""
    timeout: int = 30000
    credentials: Dict[str, str] = field(default_factory=dict)


@dataclass
class AcceptanceConfig:
    """Main acceptance configuration loaded from env.yaml.

    Use :func:`get_config` to obtain a cached singleton instance or
    :func:`load_config` for explicit loading.
    """

    current_env: str = "dev"
    environments: Dict[str, EnvironmentConfig] = field(default_factory=dict)
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    screenshot_dir: str = "reports/screenshots"
    report_dir: str = "reports"
    scenario_dir: str = "scenarios"

    # -- convenience helpers ------------------------------------------------

    def get_env(self) -> EnvironmentConfig:
        """Return the :class:`EnvironmentConfig` for the active environment."""
        return self.environments.get(
            self.current_env,
            EnvironmentConfig(name=self.current_env, base_url="http://localhost:3000"),
        )

    def get_screenshot_path(self) -> Path:
        """Return a :class:`Path` for the screenshot directory."""
        return Path(self.screenshot_dir)

    def get_report_path(self) -> Path:
        """Return a :class:`Path` for the report directory."""
        return Path(self.report_dir)


# ---------------------------------------------------------------------------
# YAML loading helpers
# ---------------------------------------------------------------------------


def _try_import_yaml() -> Any:
    """Attempt to import a YAML parser (ruamel.yaml > PyYAML)."""
    for mod_name in ("ruamel.yaml", "yaml"):
        try:
            mod = __import__(mod_name)
            return mod
        except ImportError:
            continue
    return None


def _parse_yaml(content: str) -> Dict[str, Any]:
    """Parse a YAML string into a dict.

    Tries ``ruamel.yaml`` first (preserves ordering), then ``PyYAML``.
    Falls back to a minimal line-based parser for simple flat structures if
    neither library is available.
    """
    yaml_mod = _try_import_yaml()
    if yaml_mod is not None:
        # ruamel.yaml
        if hasattr(yaml_mod, "YAML"):
            yml = yaml_mod.YAML()
            yml.preserve_quotes = True
            return yml.load(content) or {}
        # PyYAML
        return yaml_mod.safe_load(content) or {}

    # Minimal fallback parser -- handles simple key: value lines only.
    logger.warning(
        "Neither ruamel.yaml nor PyYAML is installed; "
        "using minimal YAML parser. Install one for full support."
    )
    result: Dict[str, Any] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        result[key] = val
    return result


def _resolve_dict_values(d: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively resolve ``${VAR}`` patterns in all string values."""
    resolved: Dict[str, Any] = {}
    for key, val in d.items():
        if isinstance(val, str):
            resolved[key] = resolve_env_vars(val)
        elif isinstance(val, dict):
            resolved[key] = _resolve_dict_values(val)
        elif isinstance(val, list):
            resolved[key] = [
                resolve_env_vars(v) if isinstance(v, str) else v for v in val
            ]
        else:
            resolved[key] = val
    return resolved


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_config(config_path: str) -> AcceptanceConfig:
    """Load and parse an env.yaml file into an :class:`AcceptanceConfig`.

    Parameters
    ----------
    config_path:
        Absolute or relative path to the YAML configuration file.

    Notes
    -----
    * If the file does not exist, a default configuration is returned and a
      warning is logged.
    * The ``ACCEPTANCE_ENV`` environment variable, when set, overrides the
      ``default_env`` / ``current_env`` value from the file.
    * All string values are processed through :func:`resolve_env_vars`.
    """
    path = Path(config_path)

    if not path.exists():
        logger.warning(
            "Configuration file not found at %s -- using default settings.",
            config_path,
        )
        return AcceptanceConfig()

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot read %s: %s -- using default settings.", config_path, exc)
        return AcceptanceConfig()

    try:
        data = _parse_yaml(raw)
    except Exception as exc:
        logger.error("Failed to parse YAML in %s: %s", config_path, exc)
        raise ValueError(f"Invalid YAML in {config_path}: {exc}") from exc

    if not isinstance(data, dict):
        logger.warning("YAML root in %s is not a mapping -- using defaults.", config_path)
        return AcceptanceConfig()

    data = _resolve_dict_values(data)

    # -- environments -------------------------------------------------------
    environments: Dict[str, EnvironmentConfig] = {}
    for env_name, env_data in data.get("environments", {}).items():
        if not isinstance(env_data, dict):
            continue
        environments[str(env_name)] = EnvironmentConfig(
            name=str(env_name),
            base_url=env_data.get("base_url", ""),
            api_base_url=env_data.get("api_base_url", ""),
            auth_url=env_data.get("auth_url", ""),
            timeout=int(env_data.get("timeout", 30000)),
            credentials=dict(env_data.get("credentials", {})),
        )

    # -- browser ------------------------------------------------------------
    raw_browser = data.get("browser", {})
    if not isinstance(raw_browser, dict):
        raw_browser = {}
    viewport = raw_browser.get("viewport", {})
    browser = BrowserConfig(
        type=raw_browser.get("type", "chromium"),
        headless=bool(raw_browser.get("headless", True)),
        slow_mo=int(raw_browser.get("slow_mo", 0)),
        viewport_width=int(viewport.get("width", 1280) if isinstance(viewport, dict) else 1280),
        viewport_height=int(viewport.get("height", 720) if isinstance(viewport, dict) else 720),
    )

    # -- retry --------------------------------------------------------------
    raw_retry = data.get("retry", {})
    if not isinstance(raw_retry, dict):
        raw_retry = {}
    retry = RetryConfig(
        count=int(raw_retry.get("count", 2)),
        delay_ms=int(raw_retry.get("delay_ms", 1000)),
    )

    # -- paths --------------------------------------------------------------
    raw_paths = data.get("paths", {})
    if not isinstance(raw_paths, dict):
        raw_paths = {}

    # -- determine current_env ----------------------------------------------
    current_env = data.get("default_env", "dev")

    # Environment variable override
    env_override = os.environ.get("ACCEPTANCE_ENV")
    if env_override:
        current_env = env_override
        logger.info("ACCEPTANCE_ENV override: using environment '%s'", current_env)

    return AcceptanceConfig(
        current_env=current_env,
        environments=environments,
        browser=browser,
        retry=retry,
        screenshot_dir=raw_paths.get("screenshot_dir", "reports/screenshots"),
        report_dir=raw_paths.get("report_dir", "reports"),
        scenario_dir=raw_paths.get("scenario_dir", "scenarios"),
    )


# ---------------------------------------------------------------------------
# Singleton accessor (thread-safe)
# ---------------------------------------------------------------------------

_config_lock = threading.Lock()
_cached_config: Optional[AcceptanceConfig] = None


def get_config(config_path: str | None = None) -> AcceptanceConfig:
    """Return the cached :class:`AcceptanceConfig` singleton.

    On the first call the configuration is loaded from *config_path*.  If
    *config_path* is ``None`` a default path relative to this package is
    used (``acceptance/config/env.yaml``).

    Subsequent calls return the same object regardless of *config_path*.
    """
    global _cached_config

    if _cached_config is not None:
        return _cached_config

    with _config_lock:
        # Double-checked locking
        if _cached_config is not None:
            return _cached_config

        if config_path is None:
            # Default: <project_root>/harness-engine/acceptance/config/env.yaml
            config_path = str(
                Path(__file__).resolve().parent.parent / "config" / "env.yaml"
            )

        _cached_config = load_config(config_path)
        return _cached_config


def reset_config() -> None:
    """Clear the cached singleton so the next :func:`get_config` call reloads.

    This is primarily useful for testing.
    """
    global _cached_config
    with _config_lock:
        _cached_config = None
