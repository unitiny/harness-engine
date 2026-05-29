"""
Three-level snapshot model for token-efficient browser acceptance.

Level      | Size         | Use Case
-----------|-------------|-------------------------------------------
MINIMAL    | ~300 chars  | "Which page am I on?" orientation
SUMMARY    | ~1-3K chars | "Is the page structure correct?" verification
FULL       | ~5-50K chars| "What is in table row 3?" diagnosis (failure only)

Key principle: targeted queries instead of full HTML dumps.
This achieves 95-99% token savings compared to document.body.innerHTML.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class SnapshotLevel(Enum):
    MINIMAL = "minimal"
    SUMMARY = "summary"
    FULL = "full"


@dataclass
class PageSnapshot:
    """A captured snapshot of a browser page state."""
    level: SnapshotLevel
    url: str
    title: str
    data: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    char_count: int = 0

    def __post_init__(self):
        self.char_count = len(self.data)

    def __str__(self) -> str:
        return f"[{self.level.value}] {self.url} ({self.char_count} chars)"


# JavaScript templates for targeted DOM queries

_MINIMAL_JS = """() => {
    const url = location.href;
    const title = document.title;
    const buttons = [...document.querySelectorAll('button')].slice(0, 20)
        .map(b => b.textContent.trim()).filter(Boolean).join(', ');
    const links = [...document.querySelectorAll('a[href]')].slice(0, 10)
        .map(a => ({text: a.textContent.trim().slice(0, 30), href: a.href})).filter(a => a.text);
    const forms = document.querySelectorAll('form').length;
    const inputs = document.querySelectorAll('input, textarea, select').length;
    return JSON.stringify({url, title, buttons, links, forms, inputs});
}"""

_SUMMARY_JS = """(selectors) => {
    const result = {};

    // Basic info
    result.url = location.href;
    result.title = document.title;
    result.readyState = document.readyState;

    // Visible text summary (limited)
    const body = document.body;
    if (body) {
        const text = body.innerText || '';
        result.textPreview = text.slice(0, 1500);
        result.textLength = text.length;
    }

    // Form state
    const inputs = [...document.querySelectorAll('input, textarea, select')];
    result.formFields = inputs.slice(0, 30).map(el => ({
        tag: el.tagName.toLowerCase(),
        type: el.type || '',
        name: el.name || '',
        value: (el.type === 'password') ? '***' : (el.value || '').slice(0, 50),
        disabled: el.disabled,
    }));

    // Status indicators (loading, error, success toasts)
    const toasts = [...document.querySelectorAll('[class*="toast"], [class*="message"], [class*="notification"], [role="alert"], [class*="success"], [class*="error"]')]
        .slice(0, 5).map(el => el.textContent.trim().slice(0, 100));
    result.statusIndicators = toasts;

    // Tables
    const tables = [...document.querySelectorAll('table, [class*="table"], [role="table"]')];
    result.tables = tables.slice(0, 5).map(t => ({
        rows: t.querySelectorAll('tr, [role="row"]').length,
        hasData: t.querySelectorAll('td, [role="cell"]').length > 0,
    }));

    // Selectors passed in
    if (selectors) {
        result.selectorResults = {};
        for (const [name, sel] of Object.entries(selectors)) {
            const el = document.querySelector(sel);
            result.selectorResults[name] = el ? {
                visible: el.offsetParent !== null,
                text: (el.textContent || '').trim().slice(0, 100),
            } : null;
        }
    }

    return JSON.stringify(result);
}"""

_MINIMAL_PAGE_JS = """() => {
    const url = location.href;
    const title = document.title;
    const landmarkCount = document.querySelectorAll('header, main, footer, nav, aside').length;
    const interactiveCount = document.querySelectorAll('button, a[href], input, select, textarea').length;
    return JSON.stringify({url, title, landmarkCount, interactiveCount});
}"""


async def take_snapshot(page, level: SnapshotLevel = SnapshotLevel.SUMMARY, selectors: Optional[Dict[str, str]] = None) -> PageSnapshot:
    """
    Capture a page snapshot at the specified detail level.

    Args:
        page: Playwright Page object.
        level: SnapshotLevel.MINIMAL, SUMMARY, or FULL.
        selectors: Optional dict of {name: CSS selector} to query specific elements.
                   Only used with SUMMARY level.

    Returns:
        PageSnapshot with captured data.
    """
    url = page.url
    title = await page.title()

    if level == SnapshotLevel.MINIMAL:
        data = await _take_minimal(page)

    elif level == SnapshotLevel.SUMMARY:
        data = await _take_summary(page, selectors)

    elif level == SnapshotLevel.FULL:
        data = await _take_full(page, selectors)

    else:
        raise ValueError(f"Unknown snapshot level: {level}")

    return PageSnapshot(level=level, url=url, title=title, data=data)


async def _take_minimal(page) -> str:
    """Capture minimal page state: URL, title, element counts."""
    try:
        raw = await page.evaluate(_MINIMAL_PAGE_JS)
        return _format_minimal(raw)
    except Exception as e:
        return f"Minimal snapshot failed: {e}"


async def _take_summary(page, selectors: Optional[Dict[str, str]] = None) -> str:
    """Capture summary: visible text, form state, tables, status indicators."""
    try:
        raw = await page.evaluate(_SUMMARY_JS, selectors or {})
        return _format_summary(raw)
    except Exception as e:
        return f"Summary snapshot failed: {e}"


async def _take_full(page, selectors: Optional[Dict[str, str]] = None) -> str:
    """Capture full page HTML (only for diagnostics on failure)."""
    try:
        html = await page.content()
        summary = await _take_summary(page, selectors)
        return f"{summary}\n\n--- FULL HTML ({len(html)} chars) ---\n{html}"
    except Exception as e:
        return f"Full snapshot failed: {e}"


def _format_minimal(raw: str) -> str:
    """Format minimal snapshot as compact text."""
    try:
        data = json.loads(raw)
        lines = [
            f"URL: {data.get('url', 'unknown')}",
            f"Title: {data.get('title', '')}",
            f"Landmarks: {data.get('landmarkCount', 0)}",
            f"Interactive elements: {data.get('interactiveCount', 0)}",
        ]
        return "\n".join(lines)
    except (json.JSONDecodeError, TypeError):
        return str(raw)


def _format_summary(raw: str) -> str:
    """Format summary snapshot as structured text."""
    try:
        data = json.loads(raw)
        lines = []

        lines.append(f"URL: {data.get('url', 'unknown')}")
        lines.append(f"Title: {data.get('title', '')}")
        lines.append(f"ReadyState: {data.get('readyState', 'unknown')}")

        text_preview = data.get("textPreview", "")
        if text_preview:
            lines.append(f"Text ({data.get('textLength', 0)} chars): {text_preview[:500]}...")

        form_fields = data.get("formFields", [])
        if form_fields:
            lines.append(f"Form fields ({len(form_fields)}):")
            for f in form_fields[:10]:
                lines.append(f"  {f.get('tag', '')} name={f.get('name', '')} value={f.get('value', '')}")

        status_indicators = data.get("statusIndicators", [])
        if status_indicators:
            lines.append(f"Status indicators: {status_indicators}")

        tables = data.get("tables", [])
        if tables:
            lines.append(f"Tables: {len(tables)}")
            for t in tables:
                lines.append(f"  rows={t.get('rows', 0)} hasData={t.get('hasData', False)}")

        selector_results = data.get("selectorResults", {})
        if selector_results:
            lines.append("Selector results:")
            for name, result in selector_results.items():
                if result:
                    lines.append(f"  {name}: visible={result.get('visible')} text={result.get('text', '')[:50]}")
                else:
                    lines.append(f"  {name}: NOT FOUND")

        return "\n".join(lines)
    except (json.JSONDecodeError, TypeError):
        return str(raw)


def format_snapshot_for_llm(snapshot: PageSnapshot) -> str:
    """
    Format a snapshot for LLM consumption.

    Returns compact text optimized for token efficiency.
    """
    header = f"[{snapshot.level.value}|{snapshot.char_count}c] {snapshot.url}"
    if snapshot.level == SnapshotLevel.MINIMAL:
        return f"{header}\n{snapshot.data}"
    return snapshot.data
