"""
AWI (Agent-Friendly Interface) compliance checker.

Verifies that web UI follows agent-friendly conventions:
- Semantic HTML elements (header, main, footer, nav)
- ARIA labels on interactive elements
- data-testid attributes for reliable targeting
- Consistent error/response formats
- Accessible form labels
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any


class ComplianceLevel(Enum):
    MANDATORY = "mandatory"    # Must pass
    RECOMMENDED = "recommended"  # Should pass
    OPTIONAL = "optional"       # Nice to have


class ViolationType(Enum):
    MISSING_SEMANTIC_HTML = "missing_semantic_html"
    MISSING_ARIA_LABEL = "missing_aria_label"
    MISSING_DATA_TESTID = "missing_data_testid"
    MISSING_FORM_LABEL = "missing_form_label"
    INCONSISTENT_ERROR_FORMAT = "inconsistent_error_format"
    MISSING_ALT_TEXT = "missing_alt_text"
    MISSING_HEADING_HIERARCHY = "missing_heading_hierarchy"
    INACCESSIBLE_INTERACTIVE = "inaccessible_interactive"


@dataclass
class Violation:
    """A single AWI compliance violation."""
    type: ViolationType
    level: ComplianceLevel
    element: str  # CSS selector or description
    description: str
    suggestion: str
    details: Dict[str, Any] = field(default_factory=dict)

    def __str__(self):
        level_tag = f"[{self.level.value.upper()}]"
        return f"{level_tag} {self.type.value}: {self.description} ({self.element})"


@dataclass
class ComplianceResult:
    """Complete AWI compliance check result."""
    url: str
    violations: List[Violation] = field(default_factory=list)
    checked_elements: int = 0
    compliance_score: float = 1.0  # 0-1, 1 = fully compliant

    @property
    def passed(self) -> bool:
        """True if no mandatory violations."""
        return not any(v.level == ComplianceLevel.MANDATORY for v in self.violations)

    @property
    def mandatory_violations(self) -> List[Violation]:
        return [v for v in self.violations if v.level == ComplianceLevel.MANDATORY]

    @property
    def recommended_violations(self) -> List[Violation]:
        return [v for v in self.violations if v.level == ComplianceLevel.RECOMMENDED]

    def get_summary(self) -> str:
        mandatory = len(self.mandatory_violations)
        recommended = len(self.recommended_violations)
        status = "PASS" if self.passed else "FAIL"
        return f"AWI [{status}] Score: {self.compliance_score:.0%} | Mandatory: {mandatory} | Recommended: {recommended} | Elements checked: {self.checked_elements}"


# JavaScript snippets for checking various AWI aspects

CHECK_SEMANTIC_HTML = """() => {
    const landmarks = ['header', 'main', 'footer', 'nav', 'aside'];
    const missing = landmarks.filter(tag => !document.querySelector(tag));
    const found = landmarks.filter(tag => !!document.querySelector(tag));
    return JSON.stringify({missing, found});
}"""

CHECK_ARIA_LABELS = """() => {
    const interactive = document.querySelectorAll('button, a[href], input, select, textarea');
    const withoutLabel = [...interactive].filter(el => {
        const hasAria = el.hasAttribute('aria-label') || el.hasAttribute('aria-labelledby');
        const hasText = el.textContent.trim().length > 0;
        const hasTitle = el.hasAttribute('title');
        const hasAlt = el.hasAttribute('alt') && el.getAttribute('alt').trim();
        return !(hasAria || hasText || hasTitle || hasAlt);
    }).map(el => {
        const tag = el.tagName.toLowerCase();
        const text = el.textContent.trim().slice(0, 30);
        const type = el.getAttribute('type') || '';
        return {tag, text, type, selector: tag + (type ? `[type="${type}"]` : '')};
    });
    return JSON.stringify({
        total: interactive.length,
        withoutLabel: withoutLabel.slice(0, 20)
    });
}"""

CHECK_DATA_TESTID = """() => {
    const interactive = document.querySelectorAll('button, a[href], input, select, textarea');
    const withoutTestId = [...interactive].filter(el => !el.hasAttribute('data-testid')).map(el => {
        return {tag: el.tagName.toLowerCase(), text: el.textContent.trim().slice(0, 30)};
    });
    return JSON.stringify({
        total: interactive.length,
        withoutTestId: withoutTestId.slice(0, 20),
        withTestId: interactive.length - withoutTestId.length
    });
}"""

CHECK_FORM_LABELS = """() => {
    const inputs = document.querySelectorAll('input, select, textarea');
    const withoutLabel = [...inputs].filter(input => {
        const id = input.getAttribute('id');
        const hasLabel = id && document.querySelector(`label[for="${id}"]`);
        const hasAria = input.hasAttribute('aria-label') || input.hasAttribute('aria-labelledby');
        const parentLabel = input.closest('label');
        return !(hasLabel || hasAria || parentLabel);
    }).map(el => ({
        tag: el.tagName.toLowerCase(),
        type: el.getAttribute('type') || '',
        name: el.getAttribute('name') || '',
        id: el.getAttribute('id') || ''
    }));
    return JSON.stringify({total: inputs.length, withoutLabel: withoutLabel.slice(0, 20)});
}"""

CHECK_HEADING_HIERARCHY = """() => {
    const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
    const h1s = document.querySelectorAll('h1');
    return JSON.stringify({
        total: headings.length,
        hasH1: h1s.length > 0,
        h1Count: h1s.length,
        levels: [...headings].map(h => parseInt(h.tagName[1])).slice(0, 20),
        firstH1Text: h1s.length > 0 ? h1s[0].textContent.trim().slice(0, 50) : null
    });
}"""

CHECK_ALT_TEXT = """() => {
    const images = document.querySelectorAll('img');
    const withoutAlt = [...images].filter(img => !img.hasAttribute('alt') || img.getAttribute('alt').trim() === '').map(img => ({
        src: (img.getAttribute('src') || '').slice(0, 50),
        alt: img.getAttribute('alt') || ''
    }));
    return JSON.stringify({total: images.length, withoutAlt: withoutAlt.slice(0, 10)});
}"""


class AWIComplianceChecker:
    """
    Checks web pages for Agent-Friendly Interface compliance.

    Runs multiple checks:
    1. Semantic HTML landmarks (mandatory)
    2. ARIA labels on interactive elements (recommended)
    3. data-testid attributes (recommended)
    4. Form labels (mandatory)
    5. Heading hierarchy (recommended)
    6. Image alt text (recommended)
    """

    def __init__(self, mandatory_checks: List[str] = None):
        """
        Args:
            mandatory_checks: List of check names that are mandatory.
                            Default: ['semantic_html', 'form_labels']
        """
        self._mandatory = set(mandatory_checks or ['semantic_html', 'form_labels'])

    async def check(self, page) -> ComplianceResult:
        """Run all AWI compliance checks on the given page."""
        result = ComplianceResult(url=page.url)
        result.checked_elements = 0

        await self._check_semantic_html(page, result)
        await self._check_aria_labels(page, result)
        await self._check_data_testids(page, result)
        await self._check_form_labels(page, result)
        await self._check_heading_hierarchy(page, result)
        await self._check_alt_text(page, result)

        # Calculate compliance score
        total_checks = 6
        failed_checks = len(set(v.type.value for v in result.violations))
        result.compliance_score = max(0.0, 1.0 - (failed_checks / total_checks))

        return result

    async def _check_semantic_html(self, page, result: ComplianceResult):
        level = ComplianceLevel.MANDATORY if 'semantic_html' in self._mandatory else ComplianceLevel.RECOMMENDED
        try:
            raw = await page.evaluate(CHECK_SEMANTIC_HTML)
            import json
            data = json.loads(raw)
            result.checked_elements += len(data.get("found", [])) + len(data.get("missing", []))

            for tag in data.get("missing", []):
                result.violations.append(Violation(
                    type=ViolationType.MISSING_SEMANTIC_HTML,
                    level=level,
                    element=tag,
                    description=f"Missing semantic <{tag}> element",
                    suggestion=f"Add a <{tag}> element for better accessibility and agent targeting",
                ))
        except Exception as e:
            result.violations.append(Violation(
                type=ViolationType.MISSING_SEMANTIC_HTML, level=level,
                element="page", description=f"Check failed: {e}",
                suggestion="Ensure page is fully loaded before checking",
            ))

    async def _check_aria_labels(self, page, result: ComplianceResult):
        try:
            raw = await page.evaluate(CHECK_ARIA_LABELS)
            import json
            data = json.loads(raw)
            result.checked_elements += data.get("total", 0)

            for el in data.get("withoutLabel", []):
                result.violations.append(Violation(
                    type=ViolationType.MISSING_ARIA_LABEL,
                    level=ComplianceLevel.RECOMMENDED,
                    element=f"{el['tag']}" + (f"[type={el['type']}]" if el.get('type') else ''),
                    description=f"Interactive {el['tag']} without accessible label (text: '{el.get('text', '')}')",
                    suggestion=f"Add aria-label, aria-labelledby, or visible text content to this {el['tag']}",
                ))
        except Exception:
            pass

    async def _check_data_testids(self, page, result: ComplianceResult):
        try:
            raw = await page.evaluate(CHECK_DATA_TESTID)
            import json
            data = json.loads(raw)
            result.checked_elements += data.get("total", 0)

            for el in data.get("withoutTestId", []):
                result.violations.append(Violation(
                    type=ViolationType.MISSING_DATA_TESTID,
                    level=ComplianceLevel.RECOMMENDED,
                    element=el.get("tag", ""),
                    description=f"{el.get('tag', 'element')} without data-testid (text: '{el.get('text', '')}')",
                    suggestion="Add data-testid attribute for reliable test targeting",
                ))
        except Exception:
            pass

    async def _check_form_labels(self, page, result: ComplianceResult):
        level = ComplianceLevel.MANDATORY if 'form_labels' in self._mandatory else ComplianceLevel.RECOMMENDED
        try:
            raw = await page.evaluate(CHECK_FORM_LABELS)
            import json
            data = json.loads(raw)
            result.checked_elements += data.get("total", 0)

            for el in data.get("withoutLabel", []):
                result.violations.append(Violation(
                    type=ViolationType.MISSING_FORM_LABEL,
                    level=level,
                    element=f"{el['tag']}[name={el.get('name', '')}]",
                    description=f"Form {el['tag']} without associated label (name: '{el.get('name', '')}')",
                    suggestion="Add a <label> element with 'for' attribute matching the input's 'id', or use aria-label",
                ))
        except Exception:
            pass

    async def _check_heading_hierarchy(self, page, result: ComplianceResult):
        try:
            raw = await page.evaluate(CHECK_HEADING_HIERARCHY)
            import json
            data = json.loads(raw)
            result.checked_elements += data.get("total", 0)

            if not data.get("hasH1"):
                result.violations.append(Violation(
                    type=ViolationType.MISSING_HEADING_HIERARCHY,
                    level=ComplianceLevel.RECOMMENDED,
                    element="h1",
                    description="Page has no H1 heading",
                    suggestion="Add a descriptive H1 heading for page identification",
                ))
            elif data.get("h1Count", 0) > 1:
                result.violations.append(Violation(
                    type=ViolationType.MISSING_HEADING_HIERARCHY,
                    level=ComplianceLevel.RECOMMENDED,
                    element="h1",
                    description=f"Page has {data['h1Count']} H1 headings (should have exactly 1)",
                    suggestion="Use only one H1 per page for proper document outline",
                ))
        except Exception:
            pass

    async def _check_alt_text(self, page, result: ComplianceResult):
        try:
            raw = await page.evaluate(CHECK_ALT_TEXT)
            import json
            data = json.loads(raw)
            result.checked_elements += data.get("total", 0)

            for img in data.get("withoutAlt", []):
                result.violations.append(Violation(
                    type=ViolationType.MISSING_ALT_TEXT,
                    level=ComplianceLevel.RECOMMENDED,
                    element=f"img[src={img.get('src', '')}]",
                    description="Image without alt text",
                    suggestion="Add descriptive alt attribute to image, or alt='' for decorative images",
                ))
        except Exception:
            pass
