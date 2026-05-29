"""
Five-layer acceptance verification model.

Layer 1 (Environment): Backend/frontend services running, page accessible
Layer 2 (Network): API status codes correct, response format valid
Layer 3 (Console): No JS errors, no 401/403 in console
Layer 4 (DOM): Elements visible, forms interactive, data rendered
Layer 5 (Persistence): Data truly persisted, survives page refresh

Each layer is implemented as an independent checker that can be run
against a Playwright Page object.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional

from .result import LayerResult
from .console_monitor import ConsoleMonitor
from .network_monitor import NetworkMonitor


class Layer(Enum):
    """The five verification layers, ordered by check sequence."""
    L1_ENVIRONMENT = "L1_Environment"
    L2_NETWORK = "L2_Network"
    L3_CONSOLE = "L3_Console"
    L4_DOM = "L4_DOM"
    L5_PERSISTENCE = "L5_Persistence"

    @property
    def order(self) -> int:
        return {
            Layer.L1_ENVIRONMENT: 1,
            Layer.L2_NETWORK: 2,
            Layer.L3_CONSOLE: 3,
            Layer.L4_DOM: 4,
            Layer.L5_PERSISTENCE: 5,
        }[self]


class LayerChecker(ABC):
    """Abstract base class for layer checkers."""

    @property
    @abstractmethod
    def layer(self) -> Layer:
        ...

    @abstractmethod
    async def check(self, page, context: Dict[str, Any] = None) -> LayerResult:
        """
        Run the layer check against the given Playwright page.

        Args:
            page: Playwright Page object.
            context: Optional dict with shared state (e.g., console_monitor,
                     network_monitor, expected_selectors, api_endpoints).

        Returns:
            LayerResult with pass/fail status and diagnostic information.
        """
        ...


class L1EnvironmentChecker(LayerChecker):
    """Verify the environment is ready: page accessible, services running."""

    @property
    def layer(self) -> Layer:
        return Layer.L1_ENVIRONMENT

    async def check(self, page, context: Dict[str, Any] = None) -> LayerResult:
        ctx = context or {}
        try:
            url = page.url
            # Check if page has loaded (not about:blank)
            if url == "about:blank":
                return LayerResult(
                    layer_name=self.layer.value,
                    passed=False,
                    message="Page is still at about:blank, navigation may have failed",
                )

            # Check basic page health via readyState
            ready_state = await page.evaluate("() => document.readyState")
            if ready_state not in ("interactive", "complete"):
                return LayerResult(
                    layer_name=self.layer.value,
                    passed=False,
                    message=f"Page readyState is '{ready_state}', expected 'interactive' or 'complete'",
                )

            # Check for basic HTML structure
            has_body = await page.evaluate("() => !!document.body")
            if not has_body:
                return LayerResult(
                    layer_name=self.layer.value,
                    passed=False,
                    message="Page has no body element",
                )

            return LayerResult(
                layer_name=self.layer.value,
                passed=True,
                message=f"Environment OK: page at {url}, readyState={ready_state}",
                details={"url": url, "ready_state": ready_state},
            )
        except Exception as e:
            return LayerResult(
                layer_name=self.layer.value,
                passed=False,
                message=f"Environment check failed: {e}",
            )


class L2NetworkChecker(LayerChecker):
    """Verify network requests: no 4xx/5xx on critical API calls."""

    def __init__(self, network_monitor: Optional[NetworkMonitor] = None):
        self._network_monitor = network_monitor

    @property
    def layer(self) -> Layer:
        return Layer.L2_NETWORK

    async def check(self, page, context: Dict[str, Any] = None) -> LayerResult:
        ctx = context or {}
        monitor = self._network_monitor or ctx.get("network_monitor")

        if monitor is None:
            return LayerResult(
                layer_name=self.layer.value,
                passed=True,
                message="No network monitor attached, skipping network checks",
            )

        api_errors = monitor.get_api_errors()
        if not api_errors:
            api_reqs = monitor.api_requests
            return LayerResult(
                layer_name=self.layer.value,
                passed=True,
                message=f"Network OK: {len(api_reqs)} API calls, all successful",
                details={"api_call_count": len(api_reqs)},
            )

        critical_errors = [e for e in api_errors if e.severity.value == "critical"]
        if critical_errors:
            error_summary = "; ".join(str(e) for e in critical_errors[:5])
            return LayerResult(
                layer_name=self.layer.value,
                passed=False,
                message=f"Network FAIL: {len(critical_errors)} critical API errors: {error_summary}",
                details={
                    "critical_count": len(critical_errors),
                    "error_count": len(api_errors),
                    "errors": [str(e) for e in api_errors[:10]],
                },
            )

        # Only warnings (non-critical 4xx)
        warning_summary = "; ".join(str(e) for e in api_errors[:5])
        return LayerResult(
            layer_name=self.layer.value,
            passed=True,
            message=f"Network OK with warnings: {warning_summary}",
            details={"warning_count": len(api_errors), "errors": [str(e) for e in api_errors[:10]]},
        )


class L3ConsoleChecker(LayerChecker):
    """Verify console: no JS errors, no critical console messages."""

    def __init__(self, console_monitor: Optional[ConsoleMonitor] = None):
        self._console_monitor = console_monitor

    @property
    def layer(self) -> Layer:
        return Layer.L3_CONSOLE

    async def check(self, page, context: Dict[str, Any] = None) -> LayerResult:
        ctx = context or {}
        monitor = self._console_monitor or ctx.get("console_monitor")

        if monitor is None:
            return LayerResult(
                layer_name=self.layer.value,
                passed=True,
                message="No console monitor attached, skipping console checks",
            )

        error_count = len(monitor.errors)
        page_error_count = len(monitor.page_errors)
        warning_count = len(monitor.warnings)

        if monitor.has_critical_errors:
            critical = monitor.get_critical_errors()
            return LayerResult(
                layer_name=self.layer.value,
                passed=False,
                message=f"Console FAIL: {len(critical)} critical errors, {error_count} total errors, {page_error_count} page errors",
                details={
                    "critical_count": len(critical),
                    "error_count": error_count,
                    "page_error_count": page_error_count,
                    "warning_count": warning_count,
                    "critical_errors": [str(e) for e in critical[:10]],
                },
            )

        if error_count > 0 or page_error_count > 0:
            return LayerResult(
                layer_name=self.layer.value,
                passed=False,
                message=f"Console FAIL: {error_count} errors, {page_error_count} page errors",
                details={
                    "error_count": error_count,
                    "page_error_count": page_error_count,
                    "warning_count": warning_count,
                },
            )

        return LayerResult(
            layer_name=self.layer.value,
            passed=True,
            message=f"Console OK: no errors{f', {warning_count} warnings' if warning_count > 0 else ''}",
            details={"error_count": 0, "warning_count": warning_count},
        )


class L4DOMChecker(LayerChecker):
    """Verify DOM: elements visible, forms interactive, data rendered."""

    def __init__(self, selectors: Optional[Dict[str, str]] = None):
        """
        Args:
            selectors: Dict mapping name -> CSS selector. Each selector
                       is checked for visibility. E.g.:
                       {"main_content": ".main-content", "data_table": ".data-table"}
        """
        self._selectors = selectors or {}

    @property
    def layer(self) -> Layer:
        return Layer.L4_DOM

    async def check(self, page, context: Dict[str, Any] = None) -> LayerResult:
        ctx = context or {}
        selectors = {**self._selectors, **ctx.get("expected_selectors", {})}

        if not selectors:
            return LayerResult(
                layer_name=self.layer.value,
                passed=True,
                message="No selectors specified for DOM verification",
            )

        missing = []
        invisible = []
        found = []

        for name, selector in selectors.items():
            try:
                element = await page.query_selector(selector)
                if element is None:
                    missing.append(f"{name}({selector})")
                    continue
                is_visible = await element.is_visible()
                if not is_visible:
                    invisible.append(f"{name}({selector})")
                else:
                    found.append(name)
            except Exception as e:
                missing.append(f"{name}({selector}): {e}")

        if missing or invisible:
            parts = []
            if missing:
                parts.append(f"not found: {', '.join(missing)}")
            if invisible:
                parts.append(f"not visible: {', '.join(invisible)}")
            return LayerResult(
                layer_name=self.layer.value,
                passed=False,
                message=f"DOM FAIL: {'; '.join(parts)}",
                details={"missing": missing, "invisible": invisible, "found": found},
            )

        return LayerResult(
            layer_name=self.layer.value,
            passed=True,
            message=f"DOM OK: {len(found)} elements visible ({', '.join(found)})",
            details={"found": found},
        )


class L5PersistenceChecker(LayerChecker):
    """Verify persistence: data persisted to backend/storage, survives refresh."""

    def __init__(self, check_fn=None):
        """
        Args:
            check_fn: Optional async callable(page, context) -> bool
                      that performs custom persistence verification.
        """
        self._check_fn = check_fn

    @property
    def layer(self) -> Layer:
        return Layer.L5_PERSISTENCE

    async def check(self, page, context: Dict[str, Any] = None) -> LayerResult:
        ctx = context or {}

        if self._check_fn:
            try:
                result = await self._check_fn(page, ctx)
                if result:
                    return LayerResult(
                        layer_name=self.layer.value,
                        passed=True,
                        message="Persistence OK: custom check passed",
                    )
                else:
                    return LayerResult(
                        layer_name=self.layer.value,
                        passed=False,
                        message="Persistence FAIL: custom check returned False",
                    )
            except Exception as e:
                return LayerResult(
                    layer_name=self.layer.value,
                    passed=False,
                    message=f"Persistence check error: {e}",
                )

        # Default: check if there's data in localStorage or verify via API
        api_endpoints = ctx.get("persistence_endpoints", [])
        if not api_endpoints:
            return LayerResult(
                layer_name=self.layer.value,
                passed=True,
                message="No persistence endpoints specified, skipping",
            )

        failed_checks = []
        for endpoint in api_endpoints:
            try:
                result = await page.evaluate(
                    """async (url) => {
                        const resp = await fetch(url);
                        if (!resp.ok) return {ok: false, status: resp.status};
                        const data = await resp.json();
                        return {ok: true, hasData: Array.isArray(data) ? data.length > 0 : !!data};
                    }""",
                    endpoint,
                )
                if not result.get("ok"):
                    failed_checks.append(f"{endpoint}: HTTP {result.get('status')}")
                elif not result.get("hasData"):
                    failed_checks.append(f"{endpoint}: no data returned")
            except Exception as e:
                failed_checks.append(f"{endpoint}: {e}")

        if failed_checks:
            return LayerResult(
                layer_name=self.layer.value,
                passed=False,
                message=f"Persistence FAIL: {'; '.join(failed_checks)}",
                details={"failed_checks": failed_checks},
            )

        return LayerResult(
            layer_name=self.layer.value,
            passed=True,
            message=f"Persistence OK: {len(api_endpoints)} endpoints verified",
        )


# Registry of all layer checkers for easy lookup
LAYER_CHECKERS = {
    Layer.L1_ENVIRONMENT: L1EnvironmentChecker,
    Layer.L2_NETWORK: L2NetworkChecker,
    Layer.L3_CONSOLE: L3ConsoleChecker,
    Layer.L4_DOM: L4DOMChecker,
    Layer.L5_PERSISTENCE: L5PersistenceChecker,
}


def get_checker(layer: Layer, **kwargs) -> LayerChecker:
    """Factory function to create a layer checker."""
    checker_cls = LAYER_CHECKERS.get(layer)
    if checker_cls is None:
        raise ValueError(f"No checker registered for layer {layer}")
    return checker_cls(**kwargs)
