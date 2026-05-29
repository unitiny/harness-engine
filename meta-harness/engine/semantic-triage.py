#!/usr/bin/env python3
"""semantic-triage.py — LLM semantic triage of evidence packets.

Reads evidence packets, builds triage prompts, calls invoke_semantic_role.py
for LLM judgement, parses results, and writes structured semantic reviews.
Falls back to rule-only output if LLM call fails.
Supports offline fixture mode for testing without LLM.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def load_json(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def build_triage_prompt(packet: dict) -> str:
    """Build a strict triage prompt from an evidence packet."""
    return f"""You are a semantic triage judge for a development harness quality system.

AUTHORITY BOUNDARY: You may classify findings and suggest repairs. You may NOT promote
active harness changes, weaken gates, or override human authority.

Your task: Classify this finding as one of:
- true_positive: Real, actionable harness quality issue
- false_positive: Pattern exists but is not actually a problem
- benign_exception: Pattern is real but should not become a patch
- needs_human_review: Cannot confidently classify

FINDING CONTEXT:
- Category: {packet.get('category', 'unknown')}
- Rule trigger: {packet.get('rule_trigger', 'unknown')}
- Task status: {packet.get('task_status', 'unknown')}
- Review verdict: {packet.get('review_verdict', 'unknown')}

EVIDENCE:
{packet.get('evidence_excerpt', '(no evidence)')}

TASK GOAL:
{packet.get('task_goal', '(no goal)')}

GATE EVIDENCE:
{packet.get('gate_evidence_summary', '(no gate evidence)')}

CANDIDATE INTERPRETATION:
{packet.get('candidate_interpretation', '(none)')}

QUESTION: {packet.get('question_for_llm', 'Is this finding a true issue?')}

Respond in this exact YAML format:

```yaml
semantic_verdict: <true_positive|false_positive|benign_exception|needs_human_review>
reason: <one sentence>
better_patch_target: <checker|workflow|eval|memory|template|tool_policy|instruction|none>
is_token_saving_safe: <true|false>
risk_if_promoted: <one sentence>
recommended_action: <one sentence>
confidence: <high|medium|low>
requires_human_approval: true
```

Do not add any other text outside the YAML block."""


def build_fixture_verdict(packet: dict) -> dict:
    """Generate a deterministic fixture verdict for offline testing."""
    category = packet.get("category", "")
    if category == "tool_efficiency_risk":
        return {
            "packet_id": packet["packet_id"],
            "finding_id": packet["finding_id"],
            "source": "offline_fixture",
            "semantic_verdict": "true_positive",
            "reason": "Tool output errors indicate devharness did not steer the agent to a safer, lower-token tool path before the failure",
            "better_patch_target": "tool_policy",
            "is_token_saving_safe": True,
            "risk_if_promoted": "Medium: tool guidance must preserve auditability and not hide useful diagnostics",
            "recommended_action": "Add devharness guidance or a generator/file/checker interface that routes the failing operation through a safer short command and requires future meta scans to verify the error class disappears",
            "confidence": "medium",
            "requires_human_approval": True,
        }

    # Simple heuristic: token waste in repair tasks is often benign
    task_goal = packet.get("task_goal", "").lower()
    if "repair" in task_goal or "blocker" in task_goal:
        if category == "token_waste":
            return {
                "packet_id": packet["packet_id"],
                "finding_id": packet["finding_id"],
                "source": "offline_fixture",
                "semantic_verdict": "benign_exception",
                "reason": "Repair tasks legitimately repeat scope and gate boilerplate",
                "better_patch_target": "none",
                "is_token_saving_safe": True,
                "risk_if_promoted": "Low: extracting boilerplate from repair tasks may not save meaningful tokens",
                "recommended_action": "Document as acceptable pattern for repair task stream",
                "confidence": "medium",
                "requires_human_approval": True,
            }

    return {
        "packet_id": packet["packet_id"],
        "finding_id": packet["finding_id"],
        "source": "offline_fixture",
        "semantic_verdict": "true_positive",
        "reason": "Finding appears to be a genuine harness quality issue",
        "better_patch_target": "template",
        "is_token_saving_safe": True,
        "risk_if_promoted": "Low: proposed change is conservative",
        "recommended_action": "Proceed with proposed repair as candidate",
        "confidence": "medium",
        "requires_human_approval": True,
    }


def check_cache(cache_dir: Path, content_hash: str) -> dict | None:
    """Check if a cached verdict exists for this content hash."""
    if not cache_dir.exists():
        return None
    cache_file = cache_dir / f"{content_hash}.json"
    if cache_file.exists():
        return load_json(cache_file)
    return None


def save_cache(cache_dir: Path, content_hash: str, verdict: dict):
    """Save a verdict to cache."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    save_json(cache_dir / f"{content_hash}.json", verdict)


def parse_llm_response(raw_output: str, packet_id: str, finding_id: str) -> dict:
    """Parse the LLM YAML response into a structured verdict."""
    import re

    raw_output = extract_llm_text(raw_output)

    # Extract YAML block
    yaml_match = re.search(r"```yaml\s*\n(.*?)```", raw_output, re.DOTALL)
    yaml_text = yaml_match.group(1) if yaml_match else raw_output

    # Parse key-value pairs
    def extract(key, default=""):
        m = re.search(rf"{key}:\s*(.+)", yaml_text)
        return m.group(1).strip() if m else default

    verdict = extract("semantic_verdict", "needs_human_review")
    valid_verdicts = {"true_positive", "false_positive", "benign_exception", "needs_human_review"}
    if verdict not in valid_verdicts:
        verdict = "needs_human_review"

    return {
        "packet_id": packet_id,
        "finding_id": finding_id,
        "source": "llm_fresh",
        "semantic_verdict": verdict,
        "reason": extract("reason"),
        "better_patch_target": extract("better_patch_target", "none"),
        "is_token_saving_safe": extract("is_token_saving_safe", "true") == "true",
        "risk_if_promoted": extract("risk_if_promoted"),
        "recommended_action": extract("recommended_action"),
        "confidence": extract("confidence", "low"),
        "requires_human_approval": True,
    }


def extract_llm_text(raw_output: str) -> str:
    """Extract assistant text from Claude stream-json output, or return plain text."""
    texts = []
    result_text = ""
    for line in raw_output.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "assistant":
            for part in event.get("message", {}).get("content", []):
                if part.get("type") == "text" and part.get("text"):
                    texts.append(str(part["text"]))
        elif event.get("type") == "result" and event.get("result"):
            result_text = str(event["result"])
    if result_text.strip():
        return result_text
    if texts:
        return "\n".join(texts)
    return raw_output


def invoke_llm_triage(
    packet: dict,
    prompt_path: Path,
    output_path: Path,
    log_dir: Path,
    config_path: str,
    role_name: str,
) -> dict:
    """Call invoke_semantic_role.py to get LLM judgement."""
    engine_dir = Path(__file__).parent
    invoke_script = engine_dir / "invoke_semantic_role.py"

    cmd = [
        sys.executable,
        str(invoke_script),
        "--ConfigPath", config_path,
        "--RoleName", role_name,
        "--PromptFile", str(prompt_path),
        "--OutputFile", str(output_path),
        "--LogDir", str(log_dir),
    ]

    result = subprocess.run(cmd, timeout=180)

    if result.returncode != 0:
        raise RuntimeError(f"LLM invocation failed with exit code {result.returncode}")

    # Read and parse output
    raw_output = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
    if not raw_output.strip():
        raise RuntimeError("LLM returned empty output")

    return parse_llm_response(raw_output, packet["packet_id"], packet["finding_id"])


def triage_packets(
    packets: list[dict],
    meta_root: Path,
    config: dict,
    offline: bool = False,
    use_cache: bool = False,
) -> list[dict]:
    """Run semantic triage on all packets."""
    sem_cfg = config.get("semantic_triage", {})
    cache_enabled = use_cache and sem_cfg.get("cache", True)
    cache_dir = meta_root / "semantic-reviews" / "cache"
    log_dir = meta_root / "logs" / f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    config_path = sem_cfg.get("config_path", "")
    role_name = sem_cfg.get("role_name", "semantic_triage")
    fallback_role = sem_cfg.get("fallback_role_name", "reviewer")
    allow_fallback = sem_cfg.get("allow_reviewer_fallback", False)

    verdicts = []

    for pkt in packets:
        content_hash = pkt.get("content_hash", "")

        # Check cache
        if cache_enabled:
            cached = check_cache(cache_dir, content_hash)
            if cached:
                cached = dict(cached)
                cached["source"] = "cache"
                print(f"  {pkt['packet_id']}: cached verdict={cached['semantic_verdict']}")
                verdicts.append(cached)
                continue

        if offline:
            verdict = build_fixture_verdict(pkt)
            print(f"  {pkt['packet_id']}: fixture verdict={verdict['semantic_verdict']}")
        else:
            # Build prompt file
            prompt = build_triage_prompt(pkt)
            prompt_dir = meta_root / "evidence-packets" / "latest" / "prompts"
            prompt_dir.mkdir(parents=True, exist_ok=True)
            prompt_path = prompt_dir / f"{pkt['packet_id']}-prompt.txt"
            prompt_path.write_text(prompt, encoding="utf-8")

            output_path = prompt_dir / f"{pkt['packet_id']}-response.txt"
            log_dir_session = log_dir / pkt["packet_id"]

            try:
                verdict = invoke_llm_triage(
                    pkt, prompt_path, output_path, log_dir_session,
                    config_path, role_name,
                )
                print(f"  {pkt['packet_id']}: LLM verdict={verdict['semantic_verdict']}")
            except Exception as e:
                # Try fallback role
                if allow_fallback and role_name != fallback_role:
                    try:
                        verdict = invoke_llm_triage(
                            pkt, prompt_path, output_path, log_dir_session,
                            config_path, fallback_role,
                        )
                        print(f"  {pkt['packet_id']}: fallback verdict={verdict['semantic_verdict']}")
                    except Exception:
                        print(f"  {pkt['packet_id']}: fallback failed, using needs_human_review")
                        verdict = {
                            "packet_id": pkt["packet_id"],
                            "finding_id": pkt["finding_id"],
                            "source": "llm_failed_fallback",
                            "semantic_verdict": "needs_human_review",
                            "reason": f"LLM invocation failed: {str(e)[:200]}",
                            "better_patch_target": "none",
                            "is_token_saving_safe": True,
                            "risk_if_promoted": "Unknown: LLM triage unavailable",
                            "recommended_action": "Review manually",
                            "confidence": "low",
                            "requires_human_approval": True,
                        }
                else:
                    print(f"  {pkt['packet_id']}: LLM failed ({str(e)[:80]}), using needs_human_review")
                    verdict = {
                        "packet_id": pkt["packet_id"],
                        "finding_id": pkt["finding_id"],
                        "source": "llm_failed_fallback",
                        "semantic_verdict": "needs_human_review",
                        "reason": f"LLM invocation failed: {str(e)[:200]}",
                        "better_patch_target": "none",
                        "is_token_saving_safe": True,
                        "risk_if_promoted": "Unknown: LLM triage unavailable",
                        "recommended_action": "Review manually",
                        "confidence": "low",
                        "requires_human_approval": True,
                    }

        # Save cache
        if cache_enabled:
            save_cache(cache_dir, content_hash, verdict)

        verdicts.append(verdict)

    return verdicts


def main():
    parser = argparse.ArgumentParser(description="Semantic triage of evidence packets")
    parser.add_argument("--meta-root", required=True, help="Path to meta-harness root")
    parser.add_argument("--offline", action="store_true", help="Use fixture verdicts instead of LLM")
    parser.add_argument("--use-cache", action="store_true", help="Reuse cached verdicts when content hashes match")
    parser.add_argument("--no-cache", action="store_true", help="Deprecated compatibility flag; cache is disabled by default")
    args = parser.parse_args()

    meta_root = Path(args.meta_root).resolve()

    # Load config
    import yaml
    cfg_path = meta_root / "config.yaml"
    config = {}
    if cfg_path.exists():
        with open(cfg_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

    sem_cfg = config.get("semantic_triage", {})
    enabled = sem_cfg.get("enabled", False)
    out_dir = meta_root / "semantic-reviews" / "latest"

    if not enabled and not args.offline:
        if out_dir.exists():
            shutil.rmtree(out_dir)
        print("Semantic triage is disabled in config. Use --offline for fixture mode or enable in config.yaml.")
        print("Falling back to rule-only report.")
        sys.exit(0)

    # Load packets
    pkt_dir = meta_root / "evidence-packets" / "latest"
    manifest = load_json(pkt_dir / "manifest.json")
    if not manifest or not manifest.get("packets"):
        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        summary = {
            "generated_at": datetime.now().isoformat(),
            "mode": "offline" if args.offline else "LLM",
            "cache_enabled": bool(args.use_cache and sem_cfg.get("cache", True)),
            "total_packets": 0,
            "verdict_counts": {},
            "source_counts": {},
            "verdicts": [],
        }
        save_json(out_dir / "summary.json", summary)
        print("No evidence packets found. Run build-evidence-packets.py first.")
        sys.exit(0)

    packets = []
    for pkt_ref in manifest["packets"]:
        pkt_file = pkt_dir / f"{pkt_ref['packet_id']}.json"
        pkt = load_json(pkt_file)
        if pkt:
            packets.append(pkt)

    if args.no_cache:
        sem_cfg["cache"] = False

    print(
        f"\nSemantic triage: {len(packets)} packets, "
        f"mode={'offline' if args.offline else 'LLM'}, "
        f"cache={'enabled' if args.use_cache and sem_cfg.get('cache', True) else 'disabled'}"
    )

    verdicts = triage_packets(packets, meta_root, config, offline=args.offline, use_cache=args.use_cache)

    # Write results
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Individual verdict files
    for v in verdicts:
        save_json(out_dir / f"{v['packet_id']}.json", v)

    # Summary
    from collections import Counter
    verdict_counts = Counter(v["semantic_verdict"] for v in verdicts)
    source_counts = Counter(v.get("source", "unknown") for v in verdicts)
    summary = {
        "generated_at": datetime.now().isoformat(),
        "mode": "offline" if args.offline else "LLM",
        "cache_enabled": bool(args.use_cache and sem_cfg.get("cache", True)),
        "total_packets": len(packets),
        "verdict_counts": dict(verdict_counts),
        "source_counts": dict(source_counts),
        "verdicts": verdicts,
    }
    save_json(out_dir / "summary.json", summary)

    print(f"\nSemantic triage complete:")
    for vt, count in verdict_counts.most_common():
        print(f"  {vt}: {count}")
    print(f"\nResults written to {out_dir}")


if __name__ == "__main__":
    main()
