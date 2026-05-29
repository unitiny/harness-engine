"""
Console error monitor using Playwright page.on('console') and page.on('pageerror').

Captures console.log, console.error, console.warn, and unhandled exceptions
from the browser page during acceptance testing. Used primarily for L3 verification.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, List, Optional


class MessageLevel(Enum):
    """Severity level for browser console messages."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ConsoleMessage:
    """A captured console message from the browser."""

    level: MessageLevel
    text: str
    url: Optional[str] = None
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())

    @property
    def is_error(self) -> bool:
        """True if this message represents an error or warning condition."""
        return self.level in (MessageLevel.ERROR, MessageLevel.WARNING)

    def __str__(self) -> str:
        loc = f" ({self.url}:{self.line_number})" if self.url else ""
        return f"[{self.level.value.upper()}]{loc} {self.text}"


@dataclass
class PageError:
    """An unhandled exception in the browser page."""

    message: str
    stack: Optional[str] = None
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())

    def __str__(self) -> str:
        return f"[PAGE_ERROR] {self.message}"


# Patterns that indicate critical errors (authentication failures, network
# issues, JavaScript runtime errors) that should block a test run.
CRITICAL_PATTERNS: List[str] = [
    r"token_not_valid",
    r"Token is invalid",
    r"Unauthorized",
    r"\b401\b",
    r"\b403\b",
    r"Failed to fetch",
    r"NetworkError",
    r"CORS",
    r"TypeError",
    r"ReferenceError",
    r"SyntaxError",
]

# Patterns to ignore — browser extensions, wallets, and other noise that
# is injected outside the application under test.
IGNORE_PATTERNS: List[str] = [
    r"inpage\.js",
    r"content\.js",
    r"chrome-extension://",
    r"toncenter",
    r"wallet",
    r"node_modules",
]


class ConsoleMonitor:
    """
    Monitors browser console output by attaching to Playwright page events.

    Listens for ``console`` and ``pageerror`` events on every attached
    :class:`playwright.async_api.Page`.  Messages are classified by severity,
    filtered against ignore patterns, and checked against critical patterns
    so that acceptance tests can decide whether to fail.

    Usage::

        monitor = ConsoleMonitor()
        monitor.attach(page)
        # ... run tests ...
        if monitor.has_errors:
            print(monitor.get_error_summary())
        monitor.detach(page)

    Args:
        critical_patterns: Optional list of regex patterns that mark an error
            as critical.  Defaults to :data:`CRITICAL_PATTERNS`.
        ignore_patterns: Optional list of regex patterns whose matching
            messages are silently dropped.  Defaults to :data:`IGNORE_PATTERNS`.
    """

    def __init__(
        self,
        critical_patterns: Optional[List[str]] = None,
        ignore_patterns: Optional[List[str]] = None,
    ) -> None:
        self._messages: List[ConsoleMessage] = []
        self._page_errors: List[PageError] = []
        self._critical_patterns: List[re.Pattern] = [
            re.compile(p, re.IGNORECASE)
            for p in (critical_patterns or CRITICAL_PATTERNS)
        ]
        self._ignore_patterns: List[re.Pattern] = [
            re.compile(p, re.IGNORECASE)
            for p in (ignore_patterns or IGNORE_PATTERNS)
        ]
        self._attached_pages: set[int] = set()

    # ------------------------------------------------------------------
    # Attachment lifecycle
    # ------------------------------------------------------------------

    def attach(self, page) -> None:  # noqa: ANN001 – Playwright Page type
        """
        Attach event listeners to a Playwright Page.

        Safe to call multiple times on the same page — duplicate attachments
        are silently ignored.
        """
        if id(page) in self._attached_pages:
            return

        page.on("console", self._on_console)
        page.on("pageerror", self._on_page_error)
        self._attached_pages.add(id(page))

    def detach(self, page) -> None:  # noqa: ANN001
        """
        Remove event listeners from a Playwright Page.

        Should be called during teardown to avoid leaking references.
        """
        page.remove_listener("console", self._on_console)
        page.remove_listener("pageerror", self._on_page_error)
        self._attached_pages.discard(id(page))

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_console(self, msg) -> None:  # noqa: ANN001
        """Handle a ``console`` event from Playwright.

        Playwright's ``ConsoleMessage.type`` returns one of:
        ``"error"``, ``"warning"``, ``"log"``, ``"info"``, ``"debug"``.
        """
        text = msg.text or ""

        # Drop messages matching ignore patterns (browser extensions, etc.)
        if any(p.search(text) for p in self._ignore_patterns):
            return

        level_map = {
            "error": MessageLevel.ERROR,
            "warning": MessageLevel.WARNING,
            "info": MessageLevel.INFO,
            "log": MessageLevel.INFO,
            "debug": MessageLevel.DEBUG,
        }
        level = level_map.get(msg.type, MessageLevel.INFO)

        # Best-effort source location extraction
        url: Optional[str] = None
        line_number: Optional[int] = None
        column_number: Optional[int] = None
        if hasattr(msg, "location") and msg.location:
            url = msg.location.get("url")
            line_number = msg.location.get("lineNumber")
            column_number = msg.location.get("columnNumber")

        self._messages.append(
            ConsoleMessage(
                level=level,
                text=text,
                url=url,
                line_number=line_number,
                column_number=column_number,
            )
        )

    def _on_page_error(self, error) -> None:  # noqa: ANN001
        """Handle an unhandled ``pageerror`` event from Playwright."""
        self._page_errors.append(
            PageError(
                message=str(error),
            )
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    @property
    def errors(self) -> List[ConsoleMessage]:
        """Return only error-level console messages."""
        return [m for m in self._messages if m.level == MessageLevel.ERROR]

    @property
    def warnings(self) -> List[ConsoleMessage]:
        """Return only warning-level console messages."""
        return [m for m in self._messages if m.level == MessageLevel.WARNING]

    @property
    def page_errors(self) -> List[PageError]:
        """Return captured unhandled page errors."""
        return list(self._page_errors)

    @property
    def all_messages(self) -> List[ConsoleMessage]:
        """Return all captured messages (all levels)."""
        return list(self._messages)

    @property
    def has_errors(self) -> bool:
        """True if any error-level console messages or unhandled page errors were captured."""
        return len(self.errors) > 0 or len(self._page_errors) > 0

    @property
    def has_critical_errors(self) -> bool:
        """
        True if any captured error matches a critical pattern.

        Critical errors are those whose text matches one of
        :data:`CRITICAL_PATTERNS` — authentication failures, network errors,
        or uncaught JavaScript runtime errors.
        """
        for err in self.errors:
            if any(p.search(err.text) for p in self._critical_patterns):
                return True
        for pe in self._page_errors:
            if any(p.search(pe.message) for p in self._critical_patterns):
                return True
        return False

    def get_critical_errors(self) -> List[ConsoleMessage]:
        """Return error-level messages whose text matches a critical pattern."""
        return [
            e
            for e in self.errors
            if any(p.search(e.text) for p in self._critical_patterns)
        ]

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Reset all captured messages and page errors."""
        self._messages.clear()
        self._page_errors.clear()

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_error_summary(self) -> str:
        """Format a human-readable summary of captured errors and warnings.

        Limits output to the first 10 errors and 5 page errors to keep
        summaries readable in test logs.
        """
        lines: List[str] = []

        error_count = len(self.errors)
        warning_count = len(self.warnings)
        page_error_count = len(self._page_errors)

        if error_count == 0 and page_error_count == 0:
            if warning_count > 0:
                lines.append(f"Console: {warning_count} warnings (no errors)")
            else:
                lines.append("Console: CLEAN (no errors or warnings)")
            return "\n".join(lines)

        lines.append(
            f"Console: {error_count} errors, {warning_count} warnings, "
            f"{page_error_count} page errors"
        )

        for err in self.errors[:10]:
            lines.append(f"  {err}")
        if len(self.errors) > 10:
            lines.append(f"  ... and {len(self.errors) - 10} more errors")

        for pe in self._page_errors[:5]:
            lines.append(f"  {pe}")
        if len(self._page_errors) > 5:
            lines.append(f"  ... and {len(self._page_errors) - 5} more page errors")

        return "\n".join(lines)
