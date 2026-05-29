"""Shared utilities for harness Python scripts."""

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


LOCAL_WORKSPACE_PREFIXES = (
    ".claude/",
    "cockpit-api/tmp/",
    "harness-engine/.dev-harness/automation/auto_state.json",
    "harness-engine/.dev-harness/automation/program-state.json",
    "harness-engine/.dev-harness/automation/logs/",
    "harness-engine/.dev-harness/memory/indexes/",
    "harness-engine/meta-harness/evidence-packets/latest/",
    "harness-engine/meta-harness/experience/latest/",
    "harness-engine/meta-harness/replays/results/replay-latest.json",
    "harness-engine/meta-harness/reports/contract-replay-latest.md",
    "harness-engine/meta-harness/reports/meta-review-latest.md",
    "harness-engine/meta-harness/semantic-reviews/latest/",
    "harness-engine/meta-harness/signals/latest/",
    "openclacky",
)


LOCAL_WORKSPACE_PATTERNS = (
    re.compile(r"^harness-engine/meta-harness/replays/results/replay-\d{8}-\d{6}\.json$"),
    re.compile(r"^harness-engine/meta-harness/reports/(?:contract-replay|meta-review)-\d{8}-\d{6}\.md$"),
)


def find_repo_root() -> Path:
    """Find repository root by walking up from script location."""
    script_dir = Path(__file__).resolve().parent
    for parent in [script_dir, *script_dir.parents]:
        if (parent / ".git").exists() or (parent / "Cargo.toml").exists():
            return parent
    raise RuntimeError("[harness] cannot find repository root")


def find_harness_root() -> Path:
    return find_repo_root() / "harness-engine" / ".dev-harness"


def normalize_repo_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def is_local_workspace_path(path: str) -> bool:
    normalized = normalize_repo_path(path)
    if any(
        normalized == prefix.rstrip("/") or normalized.startswith(prefix)
        for prefix in LOCAL_WORKSPACE_PREFIXES
    ):
        return True
    return any(pattern.search(normalized) for pattern in LOCAL_WORKSPACE_PATTERNS)


def filter_local_workspace_paths(paths: List[str]) -> List[str]:
    return [p for p in paths if not is_local_workspace_path(p)]


def get_field_value(content: str, field: str) -> str:
    m = re.search(
        rf"(?im)^\s*(?:-\s*)?(?:\*\*)?{re.escape(field)}(?:\*\*)?\s*:\s*(.+?)\s*$", content
    )
    return m.group(1).strip() if m else ""


def get_section_text(content: str, heading: str) -> str:
    m = re.search(
        rf"(?ms)^##\s+{re.escape(heading)}\s*\r?\n(?P<body>.*?)(?=^##\s+|\Z)",
        content,
    )
    return m.group("body").strip() if m else ""


def get_task_status(content: str) -> str:
    m = re.search(r"(?im)^\s*Task Status:\s*(?P<status>[A-Z_]+)\s*$", content)
    return m.group("status").strip() if m else "UNKNOWN"


def get_task_number(file: Path) -> Optional[int]:
    m = re.match(r"^(\d{3})-", file.name)
    return int(m.group(1)) if m else None


def to_slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return slug.strip("-")


def normalize_inline_value(value: str) -> str:
    if not value:
        return ""
    return value.strip().strip("`").strip('"').strip("'").strip()


def get_leading_token(value: str) -> str:
    normalized = normalize_inline_value(value)
    m = re.match(r"^(?P<token>[A-Za-z0-9_.-]+)", normalized)
    return m.group("token") if m else normalized


def format_bullets(items: Optional[List[str]], fallback: str = "none") -> List[str]:
    if not items:
        return [f"- {fallback}"]
    return [f"- {item}" for item in items]


def format_checklist(items: Optional[List[str]], fallback: str = "Not specified.") -> List[str]:
    if not items:
        return [f"- [ ] {fallback}"]
    return [f"- [ ] {item}" for item in items]


def get_list_after_label(content: str, label: str) -> List[str]:
    items: List[str] = []
    in_list = False
    for line in content.splitlines():
        if not in_list:
            if line.strip() == label:
                in_list = True
            continue
        if re.match(r"^##\s+", line):
            break
        if line.strip() and not line.strip().startswith("-") and re.match(r"^\S", line):
            break
        m = re.match(r"^\s*-\s+(.*)", line)
        if m:
            item = m.group(1).strip().strip("`").strip()
            if item and item != "none":
                items.append(item)
    return items


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def today_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


class HarnessError(Exception):
    """Raise with message to trigger exit code 1 and printed error."""
    pass


def die(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(1)
