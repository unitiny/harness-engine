"""Tests for acceptance.core.network_monitor module."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from acceptance.core.network_monitor import (
    APIError,
    CapturedRequest,
    ErrorSeverity,
    NetworkMonitor,
    RequestStatus,
)


class TestCapturedRequest:
    """Tests for the CapturedRequest dataclass."""

    def test_captured_request_creation(self):
        req = CapturedRequest(
            url="http://test", method="GET", resource_type="fetch"
        )
        assert req.url == "http://test"
        assert req.method == "GET"
        assert req.resource_type == "fetch"
        assert req.status == RequestStatus.PENDING

    def test_request_is_api_xhr(self):
        req = CapturedRequest(
            url="http://test/api", method="GET", resource_type="xhr"
        )
        assert req.is_api_call is True

    def test_request_is_api_fetch(self):
        req = CapturedRequest(
            url="http://test/api", method="POST", resource_type="fetch"
        )
        assert req.is_api_call is True

    def test_request_is_not_api_document(self):
        req = CapturedRequest(
            url="http://test/page", method="GET", resource_type="document"
        )
        assert req.is_api_call is False

    def test_request_is_not_api_script(self):
        req = CapturedRequest(
            url="http://test/app.js", method="GET", resource_type="script"
        )
        assert req.is_api_call is False

    def test_request_is_error_404(self):
        req = CapturedRequest(
            url="http://test", method="GET", resource_type="fetch", status_code=404
        )
        assert req.is_error is True

    def test_request_is_error_500(self):
        req = CapturedRequest(
            url="http://test", method="GET", resource_type="fetch", status_code=500
        )
        assert req.is_error is True

    def test_request_is_not_error_200(self):
        req = CapturedRequest(
            url="http://test", method="GET", resource_type="fetch", status_code=200
        )
        assert req.is_error is False

    def test_request_severity_401(self):
        req = CapturedRequest(
            url="http://test", method="GET", resource_type="fetch", status_code=401
        )
        assert req.severity == ErrorSeverity.CRITICAL

    def test_request_severity_403(self):
        req = CapturedRequest(
            url="http://test", method="GET", resource_type="fetch", status_code=403
        )
        assert req.severity == ErrorSeverity.CRITICAL

    def test_request_severity_404(self):
        req = CapturedRequest(
            url="http://test", method="GET", resource_type="fetch", status_code=404
        )
        assert req.severity == ErrorSeverity.WARNING

    def test_request_severity_500(self):
        req = CapturedRequest(
            url="http://test", method="GET", resource_type="fetch", status_code=500
        )
        assert req.severity == ErrorSeverity.CRITICAL

    def test_request_severity_200(self):
        req = CapturedRequest(
            url="http://test", method="GET", resource_type="fetch", status_code=200
        )
        assert req.severity == ErrorSeverity.INFO


class TestAPIError:
    """Tests for the APIError dataclass."""

    def test_api_error_creation(self):
        err = APIError(
            url="http://test/api",
            method="POST",
            status_code=500,
            severity=ErrorSeverity.CRITICAL,
        )
        assert err.url == "http://test/api"
        assert err.method == "POST"
        assert err.status_code == 500
        assert err.severity == ErrorSeverity.CRITICAL

    def test_api_error_str(self):
        err = APIError(
            url="http://test/api",
            method="POST",
            status_code=500,
            severity=ErrorSeverity.CRITICAL,
        )
        text = str(err)
        assert "CRITICAL" in text
        assert "500" in text
        assert "POST" in text
        assert "http://test/api" in text


class TestNetworkMonitor:
    """Tests for the NetworkMonitor class."""

    def test_monitor_initial_state(self):
        monitor = NetworkMonitor()
        assert monitor.has_failures is False
        assert len(monitor.requests) == 0
        assert len(monitor.api_requests) == 0
        assert len(monitor.failed_requests) == 0

    def test_monitor_clear(self):
        monitor = NetworkMonitor()
        # Simulate adding a request
        req_id = "test_req_1"
        monitor._requests[req_id] = CapturedRequest(
            url="http://test", method="GET", resource_type="fetch", status_code=500
        )
        monitor._request_order.append(req_id)
        assert monitor.has_failures is True

        monitor.clear()
        assert monitor.has_failures is False
        assert len(monitor.requests) == 0

    def test_monitor_summary_no_failures(self):
        monitor = NetworkMonitor()
        summary = monitor.get_summary()
        assert "0 failures" in summary

    def test_monitor_summary_with_failures(self):
        monitor = NetworkMonitor()
        req_id = "test_req_1"
        monitor._requests[req_id] = CapturedRequest(
            url="http://test/api",
            method="GET",
            resource_type="fetch",
            status_code=500,
        )
        monitor._request_order.append(req_id)
        summary = monitor.get_summary()
        assert "1 failures" in summary
