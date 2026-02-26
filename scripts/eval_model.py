#!/usr/bin/env python3
"""Evaluate the finetuned Jestify Manim coder model.

Runs a set of test prompts through the model and renders the generated code
to assess quality at each training checkpoint (Checkpoint 4 in the plan).

Usage:
  # Evaluate the latest checkpoint:
  python scripts/eval_model.py

  # Evaluate a specific checkpoint:
  python scripts/eval_model.py --checkpoint ./jestify-manim-coder-v1/checkpoint-500

  # Use Ollama (after convert_to_gguf.sh):
  python scripts/eval_model.py --use-ollama --ollama-model jestify-manim-coder

  # Compare against Claude Opus baseline:
  python scripts/eval_model.py --compare-baseline
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an expert ManimCE animation developer generating code for Jestify educational videos.
Output ONLY valid JSON: {"scene_index": N, "manim_code": "from manim import *\\n..."}
NEVER use MathTex() or Tex(). Use Text() with Unicode math symbols (x², π, ∫, Σ, →).
Every self.play() must have run_time=1.0-2.5. End scenes with self.wait(2).
Class name must be Scene{N:03d}. Inherit from MovingCameraScene."""

# Fixed evaluation prompts — same every run for consistent comparison
EVAL_PROMPTS = [
    {
        "scene_index": 0,
        "title": "Derivatives: The Rate of Change",
        "scene_type": "graph",
        "duration_hint_seconds": 22,
        "difficulty": "beginner",
        "narration_text": "Watch this graph of f of x equals x squared. See that tangent line? It shows the slope right at that point. At x equals 1, the slope is 2. At x equals 2, the slope is 4. That's the derivative tracking how fast things change.",
        "visual_description": "Show axes with f(x) = x² plotted as a blue curve. Animate a yellow tangent line sliding from x=1 to x=2, with a label showing the slope value changing from 2 to 4.",
    },
    {
        "scene_index": 1,
        "title": "Binary Search Trees",
        "scene_type": "diagram",
        "duration_hint_seconds": 22,
        "difficulty": "intermediate",
        "narration_text": "Here's our binary search tree with root 8. Values less than 8 go to the left subtree — that's 3, 1, and 5. Values greater than 8 go right — 12, 10, and 15. Every lookup takes at most log n steps.",
        "visual_description": "Show a binary search tree with root 8, left subtree 3 with children 1 and 5, right subtree 12 with children 10 and 15. Use Graph() with tree layout and Text labels. Highlight the left and right subtrees.",
    },
    {
        "scene_index": 2,
        "title": "Laws of Thermodynamics",
        "scene_type": "concept_reveal",
        "duration_hint_seconds": 24,
        "difficulty": "beginner",
        "narration_text": "The three laws of thermodynamics set the limits of our universe. First: energy cannot be created or destroyed, only converted. Second: entropy always increases — disorder grows over time. Third: absolute zero is unreachable in finite steps.",
        "visual_description": "Show three RoundedRectangle cards appearing one by one with LaggedStart. Each card has the law number and its description. Use BLUE, GREEN, TEAL colors respectively. Final card should be highlighted.",
    },
    {
        "scene_index": 0,
        "title": "Area Between Curves",
        "scene_type": "graph",
        "duration_hint_seconds": 26,
        "difficulty": "intermediate",
        "narration_text": "The integral measures the area under a curve. Here f of x equals x squared and g of x equals x. The shaded region between them from zero to one represents the difference in their integrals. The exact area is one sixth.",
        "visual_description": "Show axes with f(x)=x² in blue and g(x)=x in green. Shade the area between them from x=0 to x=1 using axes.get_area(). Label both curves and show the result formula '∫₀¹(x - x²) dx = 1/6'.",
    },
    {
        "scene_index": 3,
        "title": "Quicksort Algorithm",
        "scene_type": "diagram",
        "duration_hint_seconds": 22,
        "difficulty": "intermediate",
        "narration_text": "Quicksort picks a pivot element and partitions the array. Elements less than the pivot go left, greater go right. Then we recursively sort each partition. The average time complexity is O of n log n.",
        "visual_description": "Show an array of 8 boxes with numbers. Highlight the pivot element. Animate partitioning: elements less than pivot slide left with set_opacity change, elements greater slide right. Show two sub-arrays after partition.",
    },
]


def call_finetuned_model(checkpoint_path: str, prompt_record: dict) -> str:
    """Generate code using the finetuned model via transformers."""
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

    tokenizer = AutoTokenizer.from_pretrained(checkpoint_path, trust_remote_code=True)

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    model = AutoModelForCausalLM.from_pretrained(
        checkpoint_path, quantization_config=bnb_config,
        device_map="auto", trust_remote_code=True,
    )
    model.eval()

    user_msg = (
        f"Generate ManimCE code for Scene {prompt_record['scene_index']} of "
        f"'{prompt_record['title']}' ({prompt_record['scene_type']}, {prompt_record['duration_hint_seconds']}s).\n"
        f"Difficulty: {prompt_record['difficulty']}\n\n"
        f"Narration: \"{prompt_record['narration_text']}\"\n"
        f"Visual: \"{prompt_record['visual_description']}\""
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs, max_new_tokens=2048, temperature=0.3, do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )
    response = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    return response


def call_ollama_model(model_name: str, prompt_record: dict) -> str:
    """Generate code using Ollama."""
    import httpx

    user_msg = (
        f"Generate ManimCE code for Scene {prompt_record['scene_index']} of "
        f"'{prompt_record['title']}' ({prompt_record['scene_type']}, {prompt_record['duration_hint_seconds']}s).\n"
        f"Difficulty: {prompt_record['difficulty']}\n\n"
        f"Narration: \"{prompt_record['narration_text']}\"\n"
        f"Visual: \"{prompt_record['visual_description']}\""
    )
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 2048},
    }
    resp = httpx.post("http://localhost:11434/api/chat", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def call_claude_baseline(prompt_record: dict) -> str:
    """Generate code using Claude Opus for baseline comparison."""
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    user_msg = (
        f"Generate ManimCE code for Scene {prompt_record['scene_index']} of "
        f"'{prompt_record['title']}' ({prompt_record['scene_type']}, {prompt_record['duration_hint_seconds']}s).\n"
        f"Difficulty: {prompt_record['difficulty']}\n\n"
        f"Narration: \"{prompt_record['narration_text']}\"\n"
        f"Visual: \"{prompt_record['visual_description']}\""
    )
    resp = client.messages.create(
        model=os.getenv("CODE_MODEL", "claude-opus-4-6"),
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    return resp.content[0].text


def validate_and_render(code: str, scene_index: int, tmpdir: str) -> dict:
    """Run Manim render and return result."""
    scene_file = Path(tmpdir) / f"eval_scene_{scene_index:03d}.py"
    scene_file.write_text(code)
    class_name = f"Scene{scene_index:03d}"
    cmd = ["manim", "render", str(scene_file), class_name, "-ql", "--fps=12",
           "--media_dir", tmpdir, "--disable_caching"]
    t0 = time.perf_counter()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        elapsed = time.perf_counter() - t0
        return {
            "success": result.returncode == 0,
            "error": result.stderr[-300:].strip() if result.returncode != 0 else None,
            "render_time_s": round(elapsed, 2),
        }
    except Exception as exc:
        return {"success": False, "error": str(exc), "render_time_s": 0}


def extract_code(response_text: str) -> str:
    """Extract manim_code from a JSON response."""
    text = response_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        return data.get("manim_code", "")
    except Exception:
        match = re.search(r'"manim_code"\s*:\s*"(.*?)"(?:\s*,|\s*\})', text, re.DOTALL)
        if match:
            return match.group(1).replace("\\n", "\n").replace('\\"', '"')
    return ""


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--checkpoint", default=str(ROOT / "jestify-manim-coder-v1"),
                        help="Path to trained model checkpoint")
    parser.add_argument("--use-ollama", action="store_true", help="Use Ollama instead of transformers")
    parser.add_argument("--ollama-model", default="jestify-manim-coder", help="Ollama model name")
    parser.add_argument("--compare-baseline", action="store_true", help="Also run Claude Opus for comparison")
    parser.add_argument("--n", type=int, default=5, help="Number of eval prompts to run")
    args = parser.parse_args()

    prompts = EVAL_PROMPTS[:args.n]
    results = {"finetuned": [], "baseline": [] if args.compare_baseline else None}

    with tempfile.TemporaryDirectory() as tmpdir:
        for i, prompt in enumerate(prompts):
            logger.info(f"\n[{i+1}/{len(prompts)}] Evaluating: {prompt['title']} ({prompt['scene_type']})")

            # ── Finetuned model ────────────────────────────────────────────────
            t0 = time.perf_counter()
            try:
                if args.use_ollama:
                    raw = call_ollama_model(args.ollama_model, prompt)
                else:
                    raw = call_finetuned_model(args.checkpoint, prompt)
            except Exception as exc:
                logger.error("Finetuned model call failed: %s", exc)
                raw = ""
            gen_time = round(time.perf_counter() - t0, 2)

            code = extract_code(raw) if raw else ""
            render = validate_and_render(code, prompt["scene_index"], tmpdir) if code else {"success": False, "error": "empty code", "render_time_s": 0}

            status = "✓" if render["success"] else "✗"
            logger.info(f"  Finetuned: {status}  gen={gen_time}s  render={render['render_time_s']}s")
            if not render["success"]:
                logger.info(f"  Error: {(render.get('error') or '')[:200]}")

            results["finetuned"].append({
                "prompt": prompt["title"],
                "success": render["success"],
                "gen_time_s": gen_time,
                "render_time_s": render["render_time_s"],
                "error": render.get("error"),
            })

            # ── Claude Opus baseline ───────────────────────────────────────────
            if args.compare_baseline:
                t0 = time.perf_counter()
                try:
                    raw_b = call_claude_baseline(prompt)
                except Exception as exc:
                    logger.error("Claude baseline call failed: %s", exc)
                    raw_b = ""
                gen_time_b = round(time.perf_counter() - t0, 2)
                code_b = extract_code(raw_b) if raw_b else ""
                render_b = validate_and_render(code_b, prompt["scene_index"], tmpdir) if code_b else {"success": False, "error": "empty", "render_time_s": 0}
                status_b = "✓" if render_b["success"] else "✗"
                logger.info(f"  Baseline:  {status_b}  gen={gen_time_b}s  render={render_b['render_time_s']}s")
                results["baseline"].append({
                    "prompt": prompt["title"],
                    "success": render_b["success"],
                    "gen_time_s": gen_time_b,
                    "render_time_s": render_b["render_time_s"],
                })

    # ── Summary ────────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"{'='*60}")

    ft = results["finetuned"]
    ft_pass = sum(1 for r in ft if r["success"])
    ft_avg_gen = sum(r["gen_time_s"] for r in ft) / len(ft)
    print(f"\nFinetuned model ({args.ollama_model if args.use_ollama else args.checkpoint.split('/')[-1]}):")
    print(f"  Render pass rate: {ft_pass}/{len(ft)} ({100*ft_pass/len(ft):.0f}%)")
    print(f"  Avg gen time:     {ft_avg_gen:.1f}s")

    if results["baseline"]:
        bl = results["baseline"]
        bl_pass = sum(1 for r in bl if r["success"])
        bl_avg_gen = sum(r["gen_time_s"] for r in bl) / len(bl)
        print(f"\nClaude Opus baseline:")
        print(f"  Render pass rate: {bl_pass}/{len(bl)} ({100*bl_pass/len(bl):.0f}%)")
        print(f"  Avg gen time:     {bl_avg_gen:.1f}s")

    print(f"\n{'='*60}")


if __name__ == "__main__":
    main()
