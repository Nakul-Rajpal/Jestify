#!/usr/bin/env python3
"""Inspect and browse the training dataset.

Usage:
  # Print summary statistics (Checkpoint 3):
  python scripts/inspect_dataset.py --stats

  # Browse first N examples with pretty-printing:
  python scripts/inspect_dataset.py --n 10

  # Browse examples that failed rendering:
  python scripts/inspect_dataset.py --failed --n 10

  # Browse examples of a specific scene type:
  python scripts/inspect_dataset.py --scene-type graph --n 5

  # Show examples from a specific topic:
  python scripts/inspect_dataset.py --topic "Derivatives"

  # Export first N rendered MP4 paths (for manual video review):
  python scripts/inspect_dataset.py --export-videos --n 10
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
DEFAULT_DATASET = ROOT / "data" / "training" / "jestify_dataset.jsonl"


def load_dataset(path: Path) -> list[dict]:
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def print_stats(records: list[dict]):
    total = len(records)
    if total == 0:
        print("Dataset is empty.")
        return

    successes = [r for r in records if r.get("render_success") is True]
    failures = [r for r in records if r.get("render_success") is False]
    unknown = [r for r in records if r.get("render_success") is None]

    print("=" * 60)
    print("DATASET STATISTICS")
    print("=" * 60)
    print(f"Total records:    {total}")
    print(f"Render success:   {len(successes)} ({100*len(successes)/total:.1f}%)")
    print(f"Render failure:   {len(failures)} ({100*len(failures)/total:.1f}%)")
    print(f"Not validated:    {len(unknown)} ({100*len(unknown)/total:.1f}%)")
    print()

    # Scene type distribution
    scene_types = Counter(r.get("scene_type", "unknown") for r in records)
    print("Scene type distribution:")
    for stype, count in sorted(scene_types.items(), key=lambda x: -x[1]):
        bar = "█" * (count * 30 // max(scene_types.values()))
        print(f"  {stype:<20} {count:4d}  {bar}")
    print()

    # Difficulty distribution
    difficulties = Counter(r.get("difficulty", "unknown") for r in records)
    print("Difficulty distribution:")
    for diff, count in sorted(difficulties.items()):
        print(f"  {diff:<15} {count:4d}")
    print()

    # Domain distribution
    domains = Counter(r.get("domain", "unknown") for r in records)
    print("Domain distribution:")
    for domain, count in sorted(domains.items(), key=lambda x: -x[1]):
        print(f"  {domain:<15} {count:4d}")
    print()

    # Character distribution
    chars = Counter(r.get("character") or "n/a" for r in records)
    print("Character distribution:")
    for char, count in sorted(chars.items(), key=lambda x: -x[1]):
        print(f"  {char:<15} {count:4d}")
    print()

    # Model distribution
    models = Counter(r.get("model_used", "unknown") for r in records)
    print("Model used:")
    for model, count in sorted(models.items(), key=lambda x: -x[1]):
        print(f"  {model:<45} {count:4d}")
    print()

    # Top violation types
    all_violations = []
    for r in records:
        all_violations.extend(r.get("constraint_violations", []))
    if all_violations:
        viol_counts = Counter(all_violations)
        print("Top constraint violations:")
        for viol, count in viol_counts.most_common(10):
            print(f"  {count:4d}x  {viol}")
        print()

    # Average code length for successful renders
    if successes:
        avg_code_len = sum(len(r.get("manim_code", "")) for r in successes) / len(successes)
        avg_render_time = sum(r.get("render_time_s", 0) or 0 for r in successes) / len(successes)
        print(f"Avg code length (success): {avg_code_len:.0f} chars")
        print(f"Avg render time (success): {avg_render_time:.1f}s")
        print()

    # Common failure reasons
    if failures:
        fail_errors = Counter()
        for r in failures:
            err = r.get("render_error", "") or ""
            # Extract key error type from stderr
            if "LaTeX" in err or "MathTex" in err or "latex" in err:
                fail_errors["LaTeX error"] += 1
            elif "NameError" in err:
                fail_errors["NameError (undefined variable)"] += 1
            elif "AttributeError" in err:
                fail_errors["AttributeError"] += 1
            elif "timeout" in err.lower():
                fail_errors["Render timeout"] += 1
            elif "IndexError" in err:
                fail_errors["IndexError"] += 1
            elif "TypeError" in err:
                fail_errors["TypeError"] += 1
            elif err:
                fail_errors["Other"] += 1
            else:
                fail_errors["Empty code"] += 1

        print("Render failure breakdown:")
        for error_type, count in fail_errors.most_common():
            print(f"  {count:4d}x  {error_type}")
        print()

    print("=" * 60)
    print("Gate check (target: render_success rate > 70%):")
    if total > 0:
        rate = len(successes) / total
        status = "✓ PASS" if rate >= 0.70 else "✗ FAIL — consider filtering more aggressively"
        print(f"  {rate:.1%}  {status}")
    print("=" * 60)


def print_record(record: dict, verbose: bool = False):
    idx = record.get("scene_index", "?")
    title = record.get("title", "untitled")
    stype = record.get("scene_type", "?")
    diff = record.get("difficulty", "?")
    success = record.get("render_success")
    violations = record.get("constraint_violations", [])
    render_time = record.get("render_time_s")

    status_icon = "✓" if success is True else ("✗" if success is False else "?")

    print("-" * 60)
    print(f"{status_icon} [{diff}] {title} — Scene {idx} ({stype})")
    print(f"  Topic:    {record.get('topic', '')}")
    print(f"  Domain:   {record.get('domain', '')}  |  Character: {record.get('character') or 'n/a'}")
    print(f"  Duration: {record.get('duration_hint_seconds', '?')}s  |  Render time: {render_time}s")
    if violations:
        print(f"  Violations: {', '.join(violations)}")
    if success is False:
        err = record.get("render_error", "")
        if err:
            print(f"  Error: {err[:200]}")

    print()
    print("  NARRATION:")
    print(f"  {record.get('narration_text', '')[:300]}")
    print()
    print("  VISUAL DESCRIPTION:")
    print(f"  {record.get('visual_description', '')[:200]}")

    if verbose:
        print()
        print("  MANIM CODE:")
        code = record.get("manim_code", "")
        for line in code.split("\n")[:40]:
            print(f"    {line}")
        if code.count("\n") > 40:
            remaining = code.count("\n") - 40
            print(f"    ... ({remaining} more lines)")


def browse_records(
    records: list[dict],
    n: int = 10,
    only_failed: bool = False,
    scene_type: str = None,
    topic_filter: str = None,
    verbose: bool = False,
):
    filtered = records
    if only_failed:
        filtered = [r for r in filtered if r.get("render_success") is False]
    if scene_type:
        filtered = [r for r in filtered if r.get("scene_type") == scene_type]
    if topic_filter:
        filtered = [r for r in filtered if topic_filter.lower() in r.get("topic", "").lower()]

    print(f"\nShowing {min(n, len(filtered))} of {len(filtered)} matching records")
    for record in filtered[:n]:
        print_record(record, verbose=verbose)
    print()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET), help="Path to JSONL dataset file")
    parser.add_argument("--stats", action="store_true", help="Print summary statistics")
    parser.add_argument("--n", type=int, default=10, help="Number of examples to show")
    parser.add_argument("--failed", action="store_true", help="Show only failed renders")
    parser.add_argument("--scene-type", help="Filter by scene type (graph, equation, diagram, etc.)")
    parser.add_argument("--topic", help="Filter by topic (substring match)")
    parser.add_argument("--verbose", action="store_true", help="Show full Manim code")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Dataset not found: {dataset_path}")
        print("Run generate_training_data.py first.")
        sys.exit(1)

    records = load_dataset(dataset_path)
    print(f"Loaded {len(records)} records from {dataset_path}")

    if args.stats:
        print_stats(records)
    else:
        browse_records(
            records, n=args.n, only_failed=args.failed,
            scene_type=args.scene_type, topic_filter=args.topic,
            verbose=args.verbose,
        )


if __name__ == "__main__":
    main()
