#!/usr/bin/env python3
"""Adapt HuggingFace Manim datasets to Jestify's training format.

Pulls from two key datasets:
  1. bespokelabs/bespoke-manim   (1,000 synthetic examples)
  2. BibbyResearch/3blue1brown-manim  (2,407 real 3B1B examples)

Filtering pipeline per example:
  1. Reject if uses MathTex/Tex (LaTeX not installed in Jestify)
  2. Attempt conversion: replace common LaTeX patterns with Unicode
  3. Apply ManimGL→ManimCE patches
  4. Add MovingCameraScene inheritance if missing
  5. Normalize class name to Scene000
  6. Parse AST to check for syntax errors
  7. (Optional) Run actual Manim render to validate

Usage:
  pip install datasets  (one-time)
  python scripts/adapt_hf_datasets.py
  python scripts/adapt_hf_datasets.py --render-validate  # slower but higher quality
  python scripts/adapt_hf_datasets.py --datasets bespoke  # only one dataset
  python scripts/adapt_hf_datasets.py --limit 100  # quick test run
"""

import argparse
import ast
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = ROOT / "data" / "training"
BESPOKE_OUTPUT = OUTPUT_DIR / "bespoke_manim_adapted.jsonl"
BBB_OUTPUT = OUTPUT_DIR / "3blue1brown_adapted.jsonl"

# ── LaTeX → Unicode conversion mappings ──────────────────────────────────────

LATEX_TO_UNICODE = [
    # Superscripts
    (r'\^2', '²'), (r'\^3', '³'), (r'\^n', 'ⁿ'), (r'\^x', 'ˣ'), (r'\^i', 'ⁱ'),
    (r'\^0', '⁰'), (r'\^1', '¹'), (r'\^4', '⁴'), (r'\^5', '⁵'), (r'\^6', '⁶'),
    # Subscripts
    (r'_0', '₀'), (r'_1', '₁'), (r'_2', '₂'), (r'_3', '₃'), (r'_n', 'ₙ'), (r'_x', 'ₓ'),
    # Greek
    (r'\\pi', 'π'), (r'\\alpha', 'α'), (r'\\beta', 'β'), (r'\\gamma', 'γ'),
    (r'\\theta', 'θ'), (r'\\lambda', 'λ'), (r'\\sigma', 'σ'), (r'\\omega', 'ω'),
    (r'\\mu', 'μ'), (r'\\delta', 'δ'), (r'\\Delta', 'Δ'), (r'\\Sigma', 'Σ'),
    # Operators
    (r'\\times', '×'), (r'\\div', '÷'), (r'\\pm', '±'), (r'\\infty', '∞'),
    (r'\\neq', '≠'), (r'\\leq', '≤'), (r'\\geq', '≥'), (r'\\approx', '≈'),
    (r'\\rightarrow', '→'), (r'\\Rightarrow', '⇒'), (r'\\leftarrow', '←'),
    (r'\\sqrt', '√'), (r'\\int', '∫'), (r'\\sum', 'Σ'), (r'\\prod', 'Π'),
    # Fractions (common ones)
    (r'\\frac\{1\}\{2\}', '½'), (r'\\frac\{1\}\{3\}', '⅓'), (r'\\frac\{1\}\{4\}', '¼'),
]


def _convert_latex_in_string(s: str) -> str:
    """Convert common LaTeX sequences inside a Python string value to Unicode."""
    for pattern, replacement in LATEX_TO_UNICODE:
        s = re.sub(pattern, replacement, s)
    return s


def _convert_mathtex_to_text(code: str) -> str:
    """Replace MathTex("...") / Tex("...") calls with Text("...") after Unicode conversion."""
    def replace_tex(match):
        content = match.group(1)
        converted = _convert_latex_in_string(content)
        # Remove remaining LaTeX commands (best-effort)
        converted = re.sub(r'\\[a-zA-Z]+', '', converted)
        converted = re.sub(r'[{}]', '', converted)
        converted = converted.strip()
        return f'Text("{converted}", font_size=36)'

    code = re.sub(r'\bMathTex\s*\(\s*"([^"]*)"', replace_tex, code)
    code = re.sub(r'\bMathTex\s*\(\s*\'([^\']*)\'', replace_tex, code)
    code = re.sub(r'\bTex\s*\(\s*"([^"]*)"', replace_tex, code)
    code = re.sub(r'\bTex\s*\(\s*\'([^\']*)\'', replace_tex, code)
    return code


def _patch_gl_to_ce(code: str) -> str:
    """Apply ManimGL→ManimCE compatibility patches."""
    replacements = [
        (r'\bShowCreation\b', 'Create'),
        (r'\bUncreate\b', 'Unwrite'),
        (r'\bTransformMatchingTex\b', 'ReplacementTransform'),
        (r'from manimlib(?:\.imports)?\b', 'from manim'),
        (r'import manimlib\b', 'import manim'),
        # CONFIG dict pattern (old ManimGL style)
        (r'CONFIG\s*=\s*\{[^}]*\}', ''),
    ]
    for pattern, replacement in replacements:
        code = re.sub(pattern, replacement, code)
    return code


def _normalize_class_name(code: str, scene_index: int = 0) -> str:
    """Rename any class(Scene/MovingCameraScene) to Scene{index:03d}."""
    target_name = f"Scene{scene_index:03d}"
    # Replace existing class name
    code = re.sub(
        r'class\s+(\w+)\s*\(\s*(Scene|MovingCameraScene|ThreeDScene)\s*\)',
        f'class {target_name}(MovingCameraScene)',
        code,
        count=1,
    )
    return code


def _add_moving_camera(code: str) -> str:
    """Ensure class inherits from MovingCameraScene (not plain Scene)."""
    code = re.sub(
        r'class\s+(\w+)\s*\(\s*Scene\s*\)',
        r'class \1(MovingCameraScene)',
        code,
    )
    return code


def _check_constraints(code: str) -> list[str]:
    """Return list of remaining constraint violations after adaptation."""
    violations = []
    if re.search(r'\bMathTex\s*\(', code):
        violations.append("uses MathTex")
    if re.search(r'\bTex\s*\(', code):
        violations.append("uses Tex")
    if re.search(r'get_x_axis_label\s*\(\s*["\']', code):
        violations.append("axis label with plain string")
    if re.search(r'get_y_axis_label\s*\(\s*["\']', code):
        violations.append("axis label with plain string")
    if re.search(r'labels\s*=\s*True', code):
        violations.append("labels=True on Graph (triggers LaTeX)")
    try:
        ast.parse(code)
    except SyntaxError as e:
        violations.append(f"syntax error: {e}")
    return violations


def _validate_render(code: str, scene_index: int, tmpdir: str) -> dict:
    """Run Manim render and return result dict."""
    scene_file = Path(tmpdir) / f"scene_{scene_index:03d}.py"
    scene_file.write_text(code)
    class_name = f"Scene{scene_index:03d}"
    cmd = ["manim", "render", str(scene_file), class_name, "-ql", "--fps=12",
           "--media_dir", tmpdir, "--disable_caching"]
    t0 = time.perf_counter()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        elapsed = time.perf_counter() - t0
        success = result.returncode == 0
        return {
            "success": success,
            "error": result.stderr[-500:].strip() if not success else None,
            "render_time_s": round(elapsed, 2),
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "timeout", "render_time_s": 90}
    except Exception as exc:
        return {"success": False, "error": str(exc), "render_time_s": 0}


# ── Adaptation pipeline ────────────────────────────────────────────────────────

def adapt_code(code: str, scene_index: int = 0) -> tuple[str, list[str]]:
    """
    Run the full adaptation pipeline on a single Manim code snippet.
    Returns (adapted_code, constraint_violations).
    """
    # 1. GL→CE patches
    code = _patch_gl_to_ce(code)
    # 2. Convert MathTex/Tex to Text with Unicode
    code = _convert_mathtex_to_text(code)
    # 3. Normalize class name and ensure MovingCameraScene
    code = _normalize_class_name(code, scene_index)
    code = _add_moving_camera(code)
    # 4. Fix axis label calls that pass plain strings
    code = re.sub(
        r'(get_[xy]_axis_label\s*\(\s*)(f?"[^"]*")',
        lambda m: m.group(1) + f'Text({m.group(2)}, font_size=28)',
        code,
    )
    # 5. Check remaining violations
    violations = _check_constraints(code)
    return code, violations


# ── Dataset-specific adapters ─────────────────────────────────────────────────

def adapt_bespoke_manim(limit: Optional[int] = None, render_validate: bool = False):
    """
    Adapt bespokelabs/bespoke-manim dataset.
    Schema: {"question": str, "script": str, "manim_code": str}
    """
    try:
        from datasets import load_dataset
    except ImportError:
        logger.error("datasets not installed. Run: pip install datasets")
        return

    logger.info("Loading bespokelabs/bespoke-manim from HuggingFace...")
    ds = load_dataset("bespokelabs/bespoke-manim", split="train")
    if limit:
        ds = ds.select(range(min(limit, len(ds))))
    logger.info("Loaded %d examples", len(ds))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    kept = 0
    skipped = 0

    with open(BESPOKE_OUTPUT, "w") as f, tempfile.TemporaryDirectory() as tmpdir:
        for i, example in enumerate(ds):
            raw_code = example.get("manim_code", "")
            question = example.get("question", "")
            script = example.get("script", "")

            if not raw_code:
                skipped += 1
                continue

            adapted_code, violations = adapt_code(raw_code, scene_index=0)

            # Skip if critical unfixable violations remain
            if any("syntax error" in v for v in violations):
                skipped += 1
                continue

            render_result = {"success": None, "error": None, "render_time_s": None}
            if render_validate and not violations:
                render_result = _validate_render(adapted_code, 0, tmpdir)
                if not render_result["success"]:
                    skipped += 1
                    continue

            record = {
                "id": str(uuid.uuid4()),
                "source": "bespokelabs/bespoke-manim",
                "topic": question,
                "domain": "math",
                "difficulty": "intermediate",
                "character": None,
                "title": question[:80] if question else f"Example {i}",
                "scene_index": 0,
                "scene_type": "custom",
                "duration_hint_seconds": 22,
                "narration_text": script,
                "visual_description": question,
                "manim_code": adapted_code,
                "render_success": render_result["success"],
                "render_error": render_result["error"],
                "render_time_s": render_result["render_time_s"],
                "constraint_violations": violations,
                "model_used": "claude-sonnet-3.7-20250219",
            }
            f.write(json.dumps(record) + "\n")
            kept += 1

            if kept % 50 == 0:
                logger.info("  Processed %d / %d — kept %d, skipped %d", i + 1, len(ds), kept, skipped)

    logger.info("bespoke-manim: kept %d / %d examples → %s", kept, len(ds), BESPOKE_OUTPUT)


def adapt_3blue1brown(limit: Optional[int] = None, render_validate: bool = False):
    """
    Adapt BibbyResearch/3blue1brown-manim dataset.
    Schema varies — typically has "prompt" and "completion" or "code" fields.
    """
    try:
        from datasets import load_dataset
    except ImportError:
        logger.error("datasets not installed. Run: pip install datasets")
        return

    logger.info("Loading BibbyResearch/3blue1brown-manim from HuggingFace...")
    try:
        ds = load_dataset("BibbyResearch/3blue1brown-manim", split="train")
    except Exception as exc:
        logger.error("Failed to load 3blue1brown-manim: %s", exc)
        logger.info("Try: pip install datasets huggingface_hub")
        return

    if limit:
        ds = ds.select(range(min(limit, len(ds))))
    logger.info("Loaded %d examples — columns: %s", len(ds), list(ds.features.keys()))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    kept = 0
    skipped = 0

    with open(BBB_OUTPUT, "w") as f, tempfile.TemporaryDirectory() as tmpdir:
        for i, example in enumerate(ds):
            # Handle multiple possible schema formats
            raw_code = (
                example.get("completion") or
                example.get("code") or
                example.get("manim_code") or
                example.get("output") or ""
            )
            prompt = (
                example.get("prompt") or
                example.get("instruction") or
                example.get("description") or ""
            )

            if not raw_code or len(raw_code) < 100:
                skipped += 1
                continue

            # Skip 3D scenes — they use ThreeDScene which has different rules
            if "ThreeDScene" in raw_code or "ThreeDAxes" in raw_code:
                skipped += 1
                continue

            adapted_code, violations = adapt_code(raw_code, scene_index=0)

            if any("syntax error" in v for v in violations):
                skipped += 1
                continue

            render_result = {"success": None, "error": None, "render_time_s": None}
            if render_validate and not violations:
                render_result = _validate_render(adapted_code, 0, tmpdir)
                if not render_result["success"]:
                    skipped += 1
                    continue

            record = {
                "id": str(uuid.uuid4()),
                "source": "BibbyResearch/3blue1brown-manim",
                "topic": prompt[:200] if prompt else f"3B1B Example {i}",
                "domain": "math",
                "difficulty": "intermediate",
                "character": None,
                "title": prompt[:80] if prompt else f"3B1B Example {i}",
                "scene_index": 0,
                "scene_type": "custom",
                "duration_hint_seconds": 25,
                "narration_text": prompt,
                "visual_description": prompt,
                "manim_code": adapted_code,
                "render_success": render_result["success"],
                "render_error": render_result["error"],
                "render_time_s": render_result["render_time_s"],
                "constraint_violations": violations,
                "model_used": "3blue1brown_original",
            }
            f.write(json.dumps(record) + "\n")
            kept += 1

            if kept % 100 == 0:
                logger.info("  Processed %d / %d — kept %d, skipped %d", i + 1, len(ds), kept, skipped)

    logger.info("3blue1brown-manim: kept %d / %d examples → %s", kept, len(ds), BBB_OUTPUT)


# ── Entry point ────────────────────────────────────────────────────────────────

from typing import Optional


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--datasets", default="bespoke,3blue1brown",
                        help="Comma-separated: bespoke,3blue1brown")
    parser.add_argument("--render-validate", action="store_true",
                        help="Actually run Manim to validate each adapted example (slow)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max examples per dataset (for quick test runs)")
    args = parser.parse_args()

    datasets_to_run = [d.strip() for d in args.datasets.split(",")]

    if "bespoke" in datasets_to_run:
        adapt_bespoke_manim(limit=args.limit, render_validate=args.render_validate)

    if "3blue1brown" in datasets_to_run:
        adapt_3blue1brown(limit=args.limit, render_validate=args.render_validate)

    logger.info("")
    logger.info("Adaptation complete. Merge with synthetic data:")
    logger.info("  cat data/training/*.jsonl > data/training/combined_dataset.jsonl")
    logger.info("Then run: python scripts/inspect_dataset.py --stats")


if __name__ == "__main__":
    main()
