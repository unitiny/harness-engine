"""Tests for acceptance.core.console_monitor module."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from acceptance.core.console_monitor import (
    CRITICAL_PATTERNS,
    IGNORE_PATTERNS,
    ConsoleMessage,
    ConsoleMonitor,
    MessageLevel,
    PageError,
)


class TestConsoleMessage:
    """Tests for the ConsoleMessage dataclass."""

    def test_console_message_creation(self):
        msg = ConsoleMessage(level=MessageLevel.ERROR, text="test")
        assert msg.level == MessageLevel.ERROR
        assert msg.text == "test"

    def test_console_message_is_error(self):
        error_msg = ConsoleMessage(level=MessageLevel.ERROR, text="something broke")
        assert error_msg.is_error is True

    def test_console_message_warning_is_error(self):
        """WARNING level is also considered an error condition."""
        warn_msg = ConsoleMessage(level=MessageLevel.WARNING, text="deprecated call")
        assert warn_msg.is_error is True

    def test_console_message_info_not_error(self):
        info_msg = ConsoleMessage(level=MessageLevel.INFO, text="just info")
        assert info_msg.is_error is False

    def test_console_message_debug_not_error(self):
        debug_msg = ConsoleMessage(level=MessageLevel.DEBUG, text="debug output")
        assert debug_msg.is_error is False


class TestPageError:
    """Tests for the PageError dataclass."""

    def test_page_error_creation(self):
        err = PageError(message="uncaught TypeError")
        assert err.message == "uncaught TypeError"

    def test_page_error_str(self):
        err = PageError(message="uncaught TypeError")
        text = str(err)
        assert "PAGE_ERROR" in text
        assert "uncaught TypeError" in text


class TestConsoleMonitor:
    """Tests for the ConsoleMonitor class."""

    def test_monitor_initial_state(self):
        monitor = ConsoleMonitor()
        assert monitor.has_errors is False
        assert len(monitor.errors) == 0
        assert len(monitor.warnings) == 0
        assert len(monitor.page_errors) == 0
        assert len(monitor.all_messages) == 0

    def test_monitor_critical_patterns(self):
        assert isinstance(CRITICAL_PATTERNS, list)
        assert len(CRITICAL_PATTERNS) > 0

    def test_monitor_ignore_patterns(self):
        assert isinstance(IGNORE_PATTERNS, list)
        assert len(IGNORE_PATTERNS) > 0

    def test_monitor_clear(self):
        monitor = ConsoleMonitor()
        # Simulate adding messages by directly appending to internal lists
        monitor._messages.append(
            ConsoleMessage(level=MessageLevel.ERROR, text="test error")
        )
        monitor._page_errors.append(PageError(message="page error"))
        assert monitor.has_errors is True

        monitor.clear()
        assert monitor.has_errors is False
        assert len(monitor.errors) == 0
        assert len(monitor.page_errors) == 0

    def test_monitor_error_summary_clean(self):
        monitor = ConsoleMonitor()
        summary = monitor.get_error_summary()
        assert "CLEAN" in summary

    def test_monitor_error_summary_with_warnings(self):
        monitor = ConsoleMonitor()
        monitor._messages.append(
            ConsoleMessage(level=MessageLevel.WARNING, text="a warning")
        )
        summary = monitor.get_error_summary()
        assert "warning" in summary.lower()

    def test_monitor_error_summary_with_errors(self):
        monitor = ConsoleMonitor()
        monitor._messages.append(
            ConsoleMessage(level=MessageLevel.ERROR, text="an error")
        )
        summary = monitor.get_error_summary()
        assert "error" in summary.lower()
        assert "an error" in summary
