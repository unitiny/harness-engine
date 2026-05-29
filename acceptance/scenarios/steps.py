"""
Step executors for acceptance scenario actions.

Each executor is an async function that takes a Playwright page, target, value,
and config, then performs the specified action. Used by the scenario runner.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, Optional

from .matchers import find_text_quality_issues


async def execute_navigate(page, target: str, value: Any = None, config: Dict = None) -> Dict[str, Any]:
    """Navigate to a URL and wait for network idle."""
    url = target
    # Support relative URLs
    if url.startswith("/"):
        base = (config or {}).get("base_url", "")
        url = f"{base}{url}"

    response = await page.goto(url, wait_until="networkidle", timeout=(config or {}).get("timeout", 30000))

    status = response.status if response else None
    return {"url": page.url, "status": status, "title": await page.title()}


async def execute_click(page, target: str, value: Any = None, config: Dict = None) -> Dict[str, Any]:
    """Click on an element identified by selector."""
    timeout = (config or {}).get("timeout", 30000)
    await page.click(target, timeout=timeout)
    # Brief wait for any response
    await page.wait_for_timeout(500)
    return {"clicked": target}


async def execute_fill(page, target: str, value: Any = None, config: Dict = None) -> Dict[str, Any]:
    """Fill an input field (clears existing content first)."""
    timeout = (config or {}).get("timeout", 30000)
    await page.fill(target, str(value), timeout=timeout)
    return {"filled": target, "value_length": len(str(value))}


async def execute_wait(page, target: str, value: Any = None, config: Dict = None) -> Dict[str, Any]:
    """Wait for an element or URL.

    If target starts with '/' or 'http', waits for URL.
    Otherwise waits for selector.
    """
    timeout = (config or {}).get("timeout", 30000)

    if target.startswith("/") or target.startswith("http"):
        await page.wait_for_url(f"**{target}*" if not target.startswith("http") else target, timeout=timeout)
        return {"waited_for_url": target}
    else:
        await page.wait_for_selector(target, timeout=timeout)
        return {"waited_for_selector": target}


async def execute_verify(page, target: str, value: Any = None, config: Dict = None) -> Dict[str, Any]:
    """Verify an element exists and is visible."""
    element = await page.query_selector(target)
    if element is None:
        return {"verified": False, "reason": "Element not found", "selector": target}

    is_visible = await element.is_visible()
    text = await element.text_content() if is_visible else None

    return {
        "verified": is_visible,
        "selector": target,
        "text": (text or "").strip()[:100] if text else None,
    }


async def execute_verify_api(page, target: str, value: Any = None, config: Dict = None) -> Dict[str, Any]:
    """Verify an API endpoint returns expected response by fetching from the browser."""
    url = target
    if url.startswith("/"):
        base = (config or {}).get("api_base_url", "")
        url = f"{base}{url}"

    expected = value or {}

    result = await page.evaluate("""async ([url, expected]) => {
        try {
            const resp = await fetch(url);
            const status = resp.status;
            const contentType = resp.headers.get('content-type') || '';
            let body = null;
            if (contentType.includes('json')) {
                body = await resp.json();
            } else {
                body = await resp.text();
            }
            return {ok: resp.ok, status, contentType, body};
        } catch (e) {
            return {ok: false, error: e.message};
        }
    }""", [url, expected])

    verified = result.get("ok", False)
    if expected.get("status"):
        verified = verified and result.get("status") == expected["status"]

    return {
        "verified": verified,
        "url": url,
        "status": result.get("status"),
        "has_data": bool(result.get("body")),
    }


async def execute_api_call(page, target: str, value: Any = None, config: Dict = None) -> Dict[str, Any]:
    """Make a direct API call (method specified in value.method, body in value.body)."""
    cfg = config or {}
    url = target
    if url.startswith("/"):
        base = cfg.get("api_base_url", "")
        url = f"{base}{url}"

    params = value or {}
    method = params.get("method", "GET")
    body = params.get("body")
    headers = params.get("headers", {"Content-Type": "application/json"})

    result = await page.evaluate("""async ([url, method, body, headers]) => {
        try {
            const opts = {method, headers};
            if (body && method !== 'GET') {
                opts.body = JSON.stringify(body);
            }
            const resp = await fetch(url, opts);
            const contentType = resp.headers.get('content-type') || '';
            let responseBody = null;
            if (contentType.includes('json')) {
                responseBody = await resp.json();
            } else {
                responseBody = await resp.text();
            }
            return {status: resp.status, ok: resp.ok, body: responseBody, headers: Object.fromEntries(resp.headers.entries())};
        } catch (e) {
            return {ok: false, error: e.message};
        }
    }""", [url, method, body, headers])

    return {
        "url": url,
        "method": method,
        "status": result.get("status"),
        "ok": result.get("ok", False),
        "body": result.get("body"),
    }


async def execute_assert(page, target: str, value: Any = None, config: Dict = None) -> Dict[str, Any]:
    """Assert element's text content matches expected value."""
    element = await page.query_selector(target)
    if element is None:
        return {"assertion": False, "reason": "Element not found", "selector": target}

    text = await element.text_content()
    text = (text or "").strip()

    expected = str(value) if value is not None else ""
    passed = expected.lower() in text.lower()

    return {
        "assertion": passed,
        "selector": target,
        "actual": text[:200],
        "expected": expected,
    }


async def execute_assert_text_quality(page, target: str, value: Any = None, config: Dict = None) -> Dict[str, Any]:
    """Assert visible UI copy contains required labels and no forbidden leaks."""
    selector = target or "body"
    element = await page.query_selector(selector)
    if element is None:
        return {"assertion": False, "reason": "Element not found", "selector": selector}

    text = await element.inner_text()
    rules = value or {}
    issues = find_text_quality_issues(
        text,
        required_text=rules.get("required_text", []),
        forbidden_text=rules.get("forbidden_text", []),
        forbidden_patterns=rules.get("forbidden_patterns", []),
    )

    return {
        "assertion": not issues,
        "selector": selector,
        "actual": (text or "").strip()[:500],
        "expected": "visible text quality rules",
        "reason": "; ".join(issues) if issues else "",
    }


# Registry: action name -> executor function
_STEP_EXECUTORS: Dict[str, Callable] = {
    "navigate": execute_navigate,
    "click": execute_click,
    "fill": execute_fill,
    "wait": execute_wait,
    "verify": execute_verify,
    "verify_api": execute_verify_api,
    "api_call": execute_api_call,
    "assert": execute_assert,
    "assert_text_quality": execute_assert_text_quality,
}


def get_step_executor(action_name: str) -> Optional[Callable]:
    """Look up step executor by action name. Returns None if not found."""
    return _STEP_EXECUTORS.get(action_name)


def register_step_executor(action_name: str, executor: Callable) -> None:
    """Register a custom step executor."""
    _STEP_EXECUTORS[action_name] = executor


def list_executors() -> list[str]:
    """Return all registered action names."""
    return list(_STEP_EXECUTORS.keys())
