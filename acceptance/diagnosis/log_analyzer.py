"""
LogSage-inspired log analysis for acceptance testing failures.

Classifies errors by category (AUTH, DATABASE, NETWORK, RUNTIME, etc.),
extracts context windows around errors, and optionally uses LLM for
deep root cause analysis.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional, Callable


class LogSource(Enum):
    DJANGO = "django"
    VITE = "vite"
    BROWSER = "browser"
    AGENT = "agent"
    UNKNOWN = "unknown"


class ErrorCategory(Enum):
    AUTH = "auth"
    DATABASE = "database"
    NETWORK = "network"
    RUNTIME = "runtime"
    SYNTAX = "syntax"
    PERMISSION = "permission"
    RESOURCE = "resource"
    CONFIG = "config"
    UNKNOWN = "unknown"


@dataclass
class AnalyzedError:
    """An error extracted and classified from logs."""
    message: str
    category: ErrorCategory
    severity: str  # critical, warning, info
    source: LogSource
    timestamp: Optional[str] = None
    context: List[str] = field(default_factory=list)  # surrounding lines
    root_cause: Optional[str] = None
    suggestion: Optional[str] = None

    def __str__(self):
        return f"[{self.severity.upper()}/{self.category.value}] {self.message}"


@dataclass
class LogAnalysisResult:
    """Complete log analysis result."""
    timestamp: str = ""
    total_logs: int = 0
    error_count: int = 0
    warning_count: int = 0
    critical_errors: List[AnalyzedError] = field(default_factory=list)
    warnings: List[AnalyzedError] = field(default_factory=list)
    summary: str = ""
    recommendations: List[str] = field(default_factory=list)
    passed: bool = True
    raw_analysis: Optional[Dict] = None


# Error pattern detection rules
ERROR_PATTERNS: List[tuple] = [
    # AUTH errors
    (r"token_not_valid|Token is invalid|Unauthorized", ErrorCategory.AUTH),
    (r"\b401\b|\b403\b|Permission denied|access denied", ErrorCategory.AUTH),
    # DATABASE errors
    (r"IntegrityError|DatabaseError|OperationalError", ErrorCategory.DATABASE),
    (r"no such table|column.*not found|relation.*does not exist", ErrorCategory.DATABASE),
    (r"connection.*refused|connection.*timeout|deadlock", ErrorCategory.DATABASE),
    # NETWORK errors
    (r"Failed to fetch|NetworkError|CORS|ECONNREFUSED", ErrorCategory.NETWORK),
    (r"\b500\b|\b502\b|\b503\b|\b504\b|Service Unavailable", ErrorCategory.NETWORK),
    (r"timeout.*exceeded|request.*aborted|socket hang up", ErrorCategory.NETWORK),
    # RUNTIME errors
    (r"Traceback \(most recent call last\)", ErrorCategory.RUNTIME),
    (r"TypeError|ValueError|KeyError|AttributeError|IndexError", ErrorCategory.RUNTIME),
    (r"Error:|Exception:|FATAL|CRITICAL", ErrorCategory.RUNTIME),
    # PERMISSION errors
    (r"forbidden|insufficient permissions|not authorized", ErrorCategory.PERMISSION),
    # RESOURCE errors
    (r"ENOENT|not found|does not exist|No such file", ErrorCategory.RESOURCE),
    (r"out of memory|disk full|quota exceeded", ErrorCategory.RESOURCE),
    # SYNTAX errors
    (r"SyntaxError|IndentationError|Unexpected token", ErrorCategory.SYNTAX),
    # CONFIG errors
    (r"ConfigurationError|Missing.*setting|Invalid.*config", ErrorCategory.CONFIG),
]

WARNING_PATTERNS = [
    r"Warning:|DeprecationWarning|UserWarning",
    r"deprecated|obsolete|legacy",
    r"WARN\b",
]

IGNORE_PATTERNS = [
    r"inpage\.js",
    r"content\.js",
    r"chrome-extension://",
    r"node_modules",
]

CONTEXT_BEFORE = 4
CONTEXT_AFTER = 6


def _detect_category(message: str) -> ErrorCategory:
    """Detect error category from message text."""
    for pattern, category in ERROR_PATTERNS:
        if re.search(pattern, message, re.IGNORECASE):
            return category
    return ErrorCategory.UNKNOWN


def _detect_severity(category: ErrorCategory, message: str) -> str:
    """Determine severity based on category and content."""
    critical_categories = {ErrorCategory.AUTH, ErrorCategory.DATABASE, ErrorCategory.RUNTIME}
    if category in critical_categories:
        return "critical"
    if any(re.search(p, message, re.IGNORECASE) for p in [r"\b5\d{2}\b", r"FATAL", r"CRITICAL"]):
        return "critical"
    if any(re.search(p, message, re.IGNORECASE) for p in WARNING_PATTERNS):
        return "warning"
    return "info"


def _is_ignored(message: str) -> bool:
    return any(re.search(p, message, re.IGNORECASE) for p in IGNORE_PATTERNS)


def _extract_context(logs: List[Dict], error_index: int) -> List[str]:
    """Extract context window around an error."""
    start = max(0, error_index - CONTEXT_BEFORE)
    end = min(len(logs), error_index + CONTEXT_AFTER + 1)
    result = []
    for i in range(start, end):
        prefix = ">>> " if i == error_index else "    "
        msg = logs[i].get("message", "") or logs[i].get("text", "")
        result.append(f"{prefix}{msg}")
    return result


def _get_suggestion(category: ErrorCategory) -> str:
    suggestions = {
        ErrorCategory.AUTH: "检查 JWT Token 是否有效，是否过期，或尝试重新登录获取新 Token",
        ErrorCategory.DATABASE: "检查数据库连接配置、表结构是否正确、是否存在迁移未执行",
        ErrorCategory.NETWORK: "检查服务是否正常运行、URL 是否正确、是否存在 CORS 配置问题",
        ErrorCategory.RUNTIME: "检查代码逻辑，确认变量存在且类型正确",
        ErrorCategory.PERMISSION: "检查用户权限配置和角色分配",
        ErrorCategory.RESOURCE: "检查文件路径是否正确，资源是否存在",
        ErrorCategory.SYNTAX: "检查代码语法错误",
        ErrorCategory.CONFIG: "检查配置文件是否完整、环境变量是否设置",
        ErrorCategory.UNKNOWN: "查看详细日志获取更多信息",
    }
    return suggestions.get(category, "查看详细日志")


class LogAnalyzer:
    """
    Analyzes log entries to classify errors and generate recommendations.
    """

    def __init__(self, llm_client: Optional[Callable] = None):
        self._llm_client = llm_client

    def analyze(self, logs: List[Dict], source: LogSource = LogSource.UNKNOWN,
                use_llm: bool = False) -> LogAnalysisResult:
        """
        Analyze a list of log entries.

        Each log entry should be a dict with at least 'message' key.
        Optional keys: 'level', 'timestamp', 'source'.
        """
        result = LogAnalysisResult()
        result.total_logs = len(logs)

        # Filter noise
        filtered = [log for log in logs if not _is_ignored(log.get("message", ""))]

        for i, log in enumerate(filtered):
            message = log.get("message", "") or log.get("text", "")
            level = log.get("level", "").lower()

            # Check if this is an error or warning
            is_error = (level in ("error", "critical", "fatal")
                        or _detect_category(message) != ErrorCategory.UNKNOWN)
            is_warning = (level == "warning"
                          or any(re.search(p, message, re.IGNORECASE) for p in WARNING_PATTERNS))

            if is_error:
                category = _detect_category(message)
                severity = _detect_severity(category, message)
                context = _extract_context(filtered, i)

                analyzed = AnalyzedError(
                    message=message, category=category, severity=severity,
                    source=source, timestamp=log.get("timestamp"),
                    context=context, suggestion=_get_suggestion(category),
                )

                if severity == "critical":
                    result.critical_errors.append(analyzed)
                else:
                    result.warnings.append(analyzed)

                result.error_count += 1
            elif is_warning:
                category = _detect_category(message)
                analyzed = AnalyzedError(
                    message=message, category=category, severity="warning",
                    source=source, timestamp=log.get("timestamp"),
                )
                result.warnings.append(analyzed)
                result.warning_count += 1

        # Generate summary
        parts = []
        if result.critical_errors:
            parts.append(f"{len(result.critical_errors)} critical errors")
        if result.warnings:
            parts.append(f"{len(result.warnings)} warnings")
        if not parts:
            result.summary = "日志分析完成，未发现错误"
        else:
            result.summary = f"发现: {', '.join(parts)}"

        # Generate recommendations
        seen_categories = set()
        for err in result.critical_errors:
            if err.category not in seen_categories:
                seen_categories.add(err.category)
                result.recommendations.append(f"[{err.category.value}] {err.suggestion}")

        # Determine pass/fail: only AUTH and DATABASE errors block acceptance
        blocking_errors = [e for e in result.critical_errors
                           if e.category in (ErrorCategory.AUTH, ErrorCategory.DATABASE)]
        result.passed = len(blocking_errors) == 0

        # Optional LLM deep analysis
        if use_llm and self._llm_client and result.critical_errors:
            try:
                llm_result = self._llm_deep_analysis(result)
                result.raw_analysis = llm_result
            except Exception:
                pass  # LLM analysis failure doesn't affect result

        return result

    def _llm_deep_analysis(self, result: LogAnalysisResult) -> Dict:
        """Use LLM for deep root cause analysis (RCA)."""
        error_texts = [f"[{e.category.value}] {e.message}"
                       for e in result.critical_errors[:10]]
        context = "\n".join(
            line
            for e in result.critical_errors[:3]
            for line in e.context[:5]
        )

        prompt = f"""作为日志分析专家，分析以下错误并给出根因分析和修复建议。

错误列表:
{chr(10).join(error_texts)}

上下文:
{context}

请以 JSON 格式返回:
{{
    "root_causes": ["根因1", "根因2"],
    "overall_assessment": "整体评估",
    "blocking": true/false,
    "fix_suggestions": ["建议1", "建议2"]
}}"""

        response = self._llm_client(prompt)
        if isinstance(response, str):
            try:
                import json
                return json.loads(response)
            except (json.JSONDecodeError, ValueError):
                return {"raw_response": response}
        return response or {}


class MultiSourceLogAnalyzer:
    """Analyze logs from multiple sources simultaneously."""

    def __init__(self, llm_client: Optional[Callable] = None):
        self._analyzer = LogAnalyzer(llm_client=llm_client)

    def analyze_all(self, backend_logs: List[Dict] = None, frontend_logs: List[Dict] = None,
                    browser_logs: List[Dict] = None) -> Dict[str, LogAnalysisResult]:
        results = {}
        if backend_logs:
            results["backend"] = self._analyzer.analyze(backend_logs, LogSource.DJANGO)
        if frontend_logs:
            results["frontend"] = self._analyzer.analyze(frontend_logs, LogSource.VITE)
        if browser_logs:
            results["browser"] = self._analyzer.analyze(browser_logs, LogSource.BROWSER)
        return results

    def generate_combined_report(self, results: Dict[str, LogAnalysisResult]) -> Dict:
        overall_passed = all(r.passed for r in results.values())
        all_recommendations = []
        for source, result in results.items():
            for rec in result.recommendations:
                prefixed = f"[{source}] {rec}"
                if prefixed not in all_recommendations:
                    all_recommendations.append(prefixed)

        return {
            "overall_passed": overall_passed,
            "sources": {
                source: {"passed": r.passed, "errors": r.error_count, "warnings": r.warning_count}
                for source, r in results.items()
            },
            "combined_summary": "; ".join(r.summary for r in results.values()),
            "combined_recommendations": all_recommendations,
        }


def analyze_logs_quick(logs: List[Dict]) -> LogAnalysisResult:
    """One-liner convenience function for log analysis."""
    return LogAnalyzer().analyze(logs)
