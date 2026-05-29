#!/usr/bin/env python3
"""run_meta_review.py — Meta-Harness v0.3 runner with optional semantic triage."""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-MetaRoot", "--MetaRoot", default="")
    parser.add_argument("-Limit", "--Limit", type=int, default=0)
    parser.add_argument("-All", "--All", action="store_true")
    parser.add_argument("-Semantic", "--Semantic", action="store_true")
    parser.add_argument("-Offline", "--Offline", action="store_true")
    parser.add_argument("-SkipReplay", "--SkipReplay", action="store_true")
    parser.add_argument(
        "-UseSemanticCache",
        "--UseSemanticCache",
        action="store_true",
        help="Reuse cached semantic triage verdicts. By default -Semantic performs fresh AI calls.",
    )
    args = parser.parse_args()

    meta_root = args.MetaRoot
    if not meta_root:
        script_dir = Path(__file__).resolve().parent
        meta_root = str(script_dir.parent)

    meta_root = Path(meta_root).resolve()
    if not meta_root.exists():
        print(f"Cannot resolve meta-harness root: {meta_root}", file=sys.stderr)
        sys.exit(1)

    engine_dir = meta_root / "engine"
    signals_dir = meta_root / "signals" / "latest"
    semantic_mode = "offline" if args.Offline else ("llm" if args.Semantic else "none")

    print("")
    print("=== Meta-Harness v0.4-seed ===")
    print(f"Root: {meta_root}")
    if args.Offline:
        print("Mode: offline fixture (no LLM)")
    elif args.Semantic:
        print("Mode: LLM semantic triage")
    else:
        print("Mode: rule-only")
    print("")

    # Step 1: Collect signals
    print("--- Step 1: Signal Collection ---")
    collect_args = ["--meta-root", str(meta_root)]
    if args.Limit > 0:
        collect_args.extend(["--limit", str(args.Limit)])
    if args.All:
        collect_args.append("--all")

    r = subprocess.run([sys.executable, str(engine_dir / "collect-signals.py")] + collect_args)
    if r.returncode != 0:
        print("Signal collection failed", file=sys.stderr)
        sys.exit(1)
    print("")

    # Step 2: Rule analysis
    print("--- Step 2: Gap Analysis ---")
    r = subprocess.run([sys.executable, str(engine_dir / "analyze-gaps.py"), "--signals-dir", str(signals_dir)])
    if r.returncode != 0:
        print("Gap analysis failed", file=sys.stderr)
        sys.exit(1)
    print("")

    # Step 3: Build evidence packets
    print("--- Step 3: Evidence Packets ---")
    r = subprocess.run([sys.executable, str(engine_dir / "build-evidence-packets.py"), "--signals-dir", str(signals_dir), "--meta-root", str(meta_root)])
    if r.returncode != 0:
        print("Evidence packet build failed", file=sys.stderr)
        sys.exit(1)
    print("")

    # Step 4: Semantic triage (optional)
    if args.Offline or args.Semantic:
        print("--- Step 4: Semantic Triage ---")
        triage_args = ["--meta-root", str(meta_root)]
        if args.Offline:
            triage_args.append("--offline")
        if args.UseSemanticCache:
            triage_args.append("--use-cache")
        r = subprocess.run([sys.executable, str(engine_dir / "semantic-triage.py")] + triage_args)
        if r.returncode != 0:
            print("Semantic triage failed, falling back to rule-only report")
        print("")
    else:
        print("--- Step 4: Semantic Triage (skipped, use -Offline or -Semantic) ---")
        semantic_latest = meta_root / "semantic-reviews" / "latest"
        if semantic_latest.exists():
            shutil.rmtree(semantic_latest)
        print("")

    # Step 5: Propose repairs
    print("--- Step 5: Repair Proposals ---")
    r = subprocess.run([sys.executable, str(engine_dir / "propose-repairs.py"), "--signals-dir", str(signals_dir), "--meta-root", str(meta_root), "--semantic-mode", semantic_mode])
    if r.returncode != 0:
        print("Repair proposal failed", file=sys.stderr)
        sys.exit(1)
    print("")

    # Step 6: Contract replay (optional)
    if not args.SkipReplay:
        print("--- Step 6: Contract Replay ---")
        r = subprocess.run([sys.executable, str(engine_dir / "replay-contracts.py"), "--meta-root", str(meta_root)])
        if r.returncode != 0:
            print("Contract replay skipped or failed")
        print("")
    else:
        print("--- Step 6: Contract Replay (skipped) ---")
        print("")

    # Step 7: Experience archive
    print("--- Step 7: Experience Archive ---")
    r = subprocess.run([sys.executable, str(engine_dir / "build_experience_archive.py"), "--signals-dir", str(signals_dir), "--meta-root", str(meta_root)])
    if r.returncode != 0:
        print("Experience archive build failed", file=sys.stderr)
        sys.exit(1)
    print("")

    # Step 8: Render report
    print("--- Step 8: Report Rendering ---")
    r = subprocess.run([sys.executable, str(engine_dir / "render-report.py"), "--signals-dir", str(signals_dir), "--meta-root", str(meta_root), "--semantic-mode", semantic_mode])
    if r.returncode != 0:
        print("Report rendering failed", file=sys.stderr)
        sys.exit(1)
    print("")

    # Done
    latest_report = meta_root / "reports" / "meta-review-latest.md"
    print("=== Meta-Harness v0.4-seed Complete ===")
    print(f"Report (latest): {latest_report}")
    print("")

    if latest_report.exists():
        print("--- Report Preview (first 50 lines) ---")
        lines = latest_report.read_text(encoding="utf-8").splitlines()
        for line in lines[:50]:
            print(line)
        print("...")
        print("")
        print(f"Full report: {latest_report}")
        print("Timestamped copies saved in reports/")


if __name__ == "__main__":
    main()
