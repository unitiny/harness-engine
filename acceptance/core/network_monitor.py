"""
Network request/response monitor using Playwright page.on('request'),
page.on('response'), and page.on('requestfailed').

Captures all network activity during acceptance testing, classifies errors
by HTTP status code, and provides summaries. Used primarily for L2 verification.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from datetime import datetime


class RequestStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class ErrorSeverity(Enum):
    CRITICAL = "critical"    # 401, 403, 500+
    WARNING = "warning"      # 4xx (not 401/403)
    INFO = "info"            # 3xx redirects


@dataclass
class CapturedRequest:
    """A captured HTTP request."""
    url: str
    method: str
    resource_type: str  # document, xhr, fetch, script, stylesheet, image, etc.
    status: RequestStatus = RequestStatus.PENDING
    status_code: Optional[int] = None
    status_text: Optional[str] = None
    request_headers: Dict[str, str] = field(default_factory=dict)
    response_headers: Dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    duration_ms: Optional[float] = None

    @property
    def is_api_call(self) -> bool:
        """True if this is an XHR or fetch request."""
        return self.resource_type in ("xhr", "fetch")

    @property
    def is_error(self) -> bool:
        """True if the request failed or returned a 4xx/5xx status code."""
        if self.status_code is None:
            return self.status == RequestStatus.FAILED
        return self.status_code >= 400

    @property
    def severity(self) -> ErrorSeverity:
        """Classify error severity based on HTTP status code."""
        if self.status_code is None:
            if self.status == RequestStatus.FAILED:
                return ErrorSeverity.CRITICAL
            return ErrorSeverity.INFO
        if self.status_code in (401, 403) or self.status_code >= 500:
            return ErrorSeverity.CRITICAL
        if 400 <= self.status_code < 500:
            return ErrorSeverity.WARNING
        return ErrorSeverity.INFO

    def __str__(self) -> str:
        if self.status_code:
            return f"{self.method} {self.url} -> {self.status_code}"
        return f"{self.method} {self.url} [{self.status.value}]"


@dataclass
class APIError:
    """An API call that resulted in an error."""
    url: str
    method: str
    status_code: Optional[int]
    severity: ErrorSeverity
    error: Optional[str] = None

    def __str__(self) -> str:
        code = f" {self.status_code}" if self.status_code else ""
        return f"[{self.severity.value.upper()}{code}] {self.method} {self.url}"


# Status codes that are considered failures
FAILURE_STATUS_CODES = {
    400, 401, 403, 404, 405, 408, 409, 422, 429,
    500, 502, 503, 504,
}

# URL patterns to ignore (static assets, extensions, etc.)
IGNORE_URL_PATTERNS = [
    r"\.css$",
    r"\.png$",
    r"\.jpg$",
    r"\.jpeg$",
    r"\.gif$",
    r"\.svg$",
    r"\.ico$",
    r"\.woff2?$",
    r"\.ttf$",
    r"chrome-extension://",
    r"about:blank",
    r"data:",
]


class NetworkMonitor:
    """
    Monitors browser network activity by attaching to Playwright page events.

    Usage::

        monitor = NetworkMonitor()
        monitor.attach(page)
        # ... run tests ...
        if monitor.has_failures:
            print(monitor.get_summary())
        monitor.detach(page)
    """

    def __init__(
        self,
        ignore_patterns: Optional[List[str]] = None,
        track_timing: bool = True,
    ) -> None:
        self._requests: Dict[str, CapturedRequest] = {}  # request_id -> CapturedRequest
        self._request_order: List[str] = []
        self._ignore_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in (ignore_patterns if ignore_patterns is not None else IGNORE_URL_PATTERNS)
        ]
        self._track_timing = track_timing
        self._attached_pages: set[int] = set()
        self._request_start_times: Dict[str, float] = {}

    # ------------------------------------------------------------------
    # Lifecycle: attach / detach
    # ------------------------------------------------------------------

    def attach(self, page) -> None:
        """Attach event listeners to a Playwright Page."""
        if id(page) in self._attached_pages:
            return

        page.on("request", self._on_request)
        page.on("response", self._on_response)
        page.on("requestfailed", self._on_request_failed)
        self._attached_pages.add(id(page))

    def detach(self, page) -> None:
        """Remove event listeners from a Playwright Page."""
        page.remove_listener("request", self._on_request)
        page.remove_listener("response", self._on_response)
        page.remove_listener("requestfailed", self._on_request_failed)
        self._attached_pages.discard(id(page))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _should_ignore(self, url: str) -> bool:
        """Return True if the URL matches any ignore pattern."""
        return any(p.search(url) for p in self._ignore_patterns)

    # ------------------------------------------------------------------
    # Playwright event handlers
    # ------------------------------------------------------------------

    def _on_request(self, request) -> None:
        """Handle Playwright ``request`` event."""
        url = request.url
        if self._should_ignore(url):
            return

        req_id = str(id(request))
        captured = CapturedRequest(
            url=url,
            method=request.method,
            resource_type=request.resource_type,
            status=RequestStatus.PENDING,
        )
        self._requests[req_id] = captured
        self._request_order.append(req_id)
        if self._track_timing:
            self._request_start_times[req_id] = datetime.now().timestamp()

    def _on_response(self, response) -> None:
        """Handle Playwright ``response`` event."""
        request = response.request
        req_id = str(id(request))

        if req_id not in self._requests:
            # Request was filtered out or arrived before attach; still track it
            url = request.url
            if self._should_ignore(url):
                return
            self._requests[req_id] = CapturedRequest(
                url=url,
                method=request.method,
                resource_type=request.resource_type,
            )
            self._request_order.append(req_id)

        captured = self._requests[req_id]
        captured.status_code = response.status
        captured.status_text = response.status_text
        captured.status = RequestStatus.COMPLETED

        if self._track_timing and req_id in self._request_start_times:
            start = self._request_start_times.pop(req_id)
            captured.duration_ms = (datetime.now().timestamp() - start) * 1000

    def _on_request_failed(self, request) -> None:
        """Handle Playwright ``requestfailed`` event."""
        req_id = str(id(request))
        url = request.url

        if req_id in self._requests:
            captured = self._requests[req_id]
            captured.status = RequestStatus.FAILED
            captured.error = request.failure
        elif not self._should_ignore(url):
            self._requests[req_id] = CapturedRequest(
                url=url,
                method=request.method,
                resource_type=request.resource_type,
                status=RequestStatus.FAILED,
                error=request.failure,
            )
            self._request_order.append(req_id)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    @property
    def requests(self) -> List[CapturedRequest]:
        """Return all captured requests in chronological order."""
        return [self._requests[rid] for rid in self._request_order if rid in self._requests]

    @property
    def api_requests(self) -> List[CapturedRequest]:
        """Return only API calls (xhr / fetch)."""
        return [r for r in self.requests if r.is_api_call]

    @property
    def failed_requests(self) -> List[CapturedRequest]:
        """Return requests that failed or had error status codes."""
        return [
            r for r in self.requests
            if r.is_error or r.status == RequestStatus.FAILED
        ]

    @property
    def has_failures(self) -> bool:
        """True if any request failed or returned an error status code."""
        return len(self.failed_requests) > 0

    def get_api_errors(self) -> List[APIError]:
        """Extract API call errors with severity classification."""
        errors: List[APIError] = []
        for req in self.api_requests:
            if req.is_error or req.status == RequestStatus.FAILED:
                errors.append(APIError(
                    url=req.url,
                    method=req.method,
                    status_code=req.status_code,
                    severity=req.severity,
                    error=req.error,
                ))
        return errors

    def get_requests_by_pattern(self, url_pattern: str) -> List[CapturedRequest]:
        """Find requests whose URL matches *url_pattern* (regex, case-insensitive)."""
        compiled = re.compile(url_pattern, re.IGNORECASE)
        return [r for r in self.requests if compiled.search(r.url)]

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Reset all captured requests."""
        self._requests.clear()
        self._request_order.clear()
        self._request_start_times.clear()

    def get_summary(self) -> str:
        """Return a human-readable summary of network activity."""
        lines: List[str] = []
        all_reqs = self.requests
        api_reqs = self.api_requests
        failures = self.failed_requests

        lines.append(
            f"Network: {len(all_reqs)} total, {len(api_reqs)} API, {len(failures)} failures"
        )

        if failures:
            for f in failures[:10]:
                severity_tag = f"[{f.severity.value.upper()}]" if f.status_code else "[FAILED]"
                code = f" {f.status_code}" if f.status_code else ""
                lines.append(f"  {severity_tag}{code} {f.method} {f.url}")
            if len(failures) > 10:
                lines.append(f"  ... and {len(failures) - 10} more failures")
        else:
            lines.append("  All requests successful")

        return "\n".join(lines)
