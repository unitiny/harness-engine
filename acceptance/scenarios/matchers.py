"""
Matchers for acceptance test verification.

Provides text, DOM, network, JSON, and storage matching functions
used by verify and assert steps in acceptance scenarios.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Callable


class MatchMode:
    EXACT = "exact"
    CONTAINS = "contains"
    REGEX = "regex"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"


def text_matches(actual: str, expected: str, mode: str = MatchMode.EXACT) -> bool:
    """Match text using the specified mode."""
    if not isinstance(actual, str):
        actual = str(actual)
    if not isinstance(expected, str):
        expected = str(expected)

    if mode == MatchMode.EXACT:
        return actual.strip() == expected.strip()
    elif mode == MatchMode.CONTAINS:
        return expected.lower() in actual.lower()
    elif mode == MatchMode.REGEX:
        try:
            return bool(re.search(expected, actual, re.IGNORECASE))
        except re.error:
            return False
    elif mode == MatchMode.STARTS_WITH:
        return actual.strip().lower().startswith(expected.strip().lower())
    elif mode == MatchMode.ENDS_WITH:
        return actual.strip().lower().endswith(expected.strip().lower())
    return False


def find_text_quality_issues(
    actual: str,
    required_text: Optional[List[str]] = None,
    forbidden_text: Optional[List[str]] = None,
    forbidden_patterns: Optional[List[str]] = None,
) -> List[str]:
    """Return visible-copy issues such as leaked i18n keys or missing labels."""
    text = actual or ""
    issues: List[str] = []

    for required in required_text or []:
        if required not in text:
            issues.append(f"missing required text: {required}")

    for forbidden in forbidden_text or []:
        if forbidden in text:
            issues.append(forbidden)

    for pattern in forbidden_patterns or []:
        try:
            for match in re.findall(pattern, text):
                issues.append(match if isinstance(match, str) else "".join(match))
        except re.error:
            issues.append(f"invalid forbidden pattern: {pattern}")

    return issues


async def element_visible(page, selector: str) -> bool:
    """Check if element exists and is visible."""
    element = await page.query_selector(selector)
    if element is None:
        return False
    return await element.is_visible()


async def element_count(page, selector: str, expected: int) -> bool:
    """Check if the number of matching elements equals expected."""
    elements = await page.query_selector_all(selector)
    return len(elements) == expected


async def element_count_at_least(page, selector: str, minimum: int) -> bool:
    """Check if at least N matching elements exist."""
    elements = await page.query_selector_all(selector)
    return len(elements) >= minimum


def network_call_succeeded(status_code: Optional[int]) -> bool:
    """Check if HTTP status code indicates success (2xx or 3xx)."""
    if status_code is None:
        return False
    return 200 <= status_code < 400


def json_matches(actual: Any, expected: Any, mode: str = "subset") -> bool:
    """
    Match JSON data structures.

    Modes:
        subset: expected keys/values must exist in actual (nested)
        exact: structures must be identical
        contains: expected must be a substring of actual when stringified
    """
    if mode == "exact":
        return actual == expected

    if mode == "contains":
        return str(expected) in str(actual)

    # subset mode
    return _json_subset(actual, expected)


def _json_subset(actual: Any, expected: Any) -> bool:
    """Check if expected is a subset of actual (recursive)."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(
            key in actual and _json_subset(actual[key], val)
            for key, val in expected.items()
        )
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False
        if len(expected) > len(actual):
            return False
        # For lists, check if each expected item exists somewhere in actual
        for exp_item in expected:
            if not any(_json_subset(act_item, exp_item) for act_item in actual):
                return False
        return True
    return actual == expected


async def storage_contains(
    page, key: str, expected: Optional[str] = None, storage_type: str = "localStorage"
) -> bool:
    """Check if browser storage contains a key (and optionally value)."""
    try:
        value = await page.evaluate(
            f"""(key) => {{
                const storage = window.{storage_type};
                return storage.getItem(key);
            }}""",
            key,
        )
        if expected is None:
            return value is not None
        return value == expected
    except Exception:
        return False


async def page_title_matches(
    page, expected: str, mode: str = MatchMode.CONTAINS
) -> bool:
    """Check if page title matches expected pattern."""
    title = await page.title()
    return text_matches(title, expected, mode)


async def url_matches(page, expected: str, mode: str = MatchMode.CONTAINS) -> bool:
    """Check if current URL matches expected pattern."""
    url = page.url
    return text_matches(url, expected, mode)


async def text_content_matches(
    page, selector: str, expected: str, mode: str = MatchMode.CONTAINS
) -> bool:
    """Check if element's text content matches expected."""
    element = await page.query_selector(selector)
    if element is None:
        return False
    text = await element.text_content()
    if text is None:
        return False
    return text_matches(text, expected, mode)


class MatcherRegistry:
    """Registry for named matchers, allowing dynamic lookup."""

    def __init__(self):
        self._matchers: Dict[str, Callable] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register built-in matchers."""
        self._matchers = {
            "text": text_matches,
            "visible": element_visible,
            "count": element_count,
            "count_at_least": element_count_at_least,
            "network_ok": network_call_succeeded,
            "json": json_matches,
            "storage": storage_contains,
            "title": page_title_matches,
            "url": url_matches,
            "text_content": text_content_matches,
        }

    def register(self, name: str, matcher: Callable) -> None:
        """Register a custom matcher function."""
        self._matchers[name] = matcher

    def get(self, name: str) -> Optional[Callable]:
        """Look up a matcher by name."""
        return self._matchers.get(name)

    def list_matchers(self) -> List[str]:
        """Return all registered matcher names."""
        return list(self._matchers.keys())

    async def match(self, name: str, *args, **kwargs) -> bool:
        """Execute a named matcher with given arguments."""
        matcher = self.get(name)
        if matcher is None:
            raise ValueError(f"Unknown matcher: {name}")
        result = matcher(*args, **kwargs)
        if hasattr(result, "__await__"):
            return await result
        return result
