#!/usr/bin/env python3
"""DPO (Direct Preference Optimization) training for Jestify Manim code generation.

Trains on preference pairs extracted from the dataset:
  - chosen:   Manim code that rendered successfully with no constraint violations
  - rejected: Failed or constraint-violating code for the same scene input

Run AFTER SFT training (train_sft.py). DPO refines the model to further
prefer valid, Jestify-rule-following code.

Requirements:
  pip install -r scripts/requirements_training.txt

Usage:
  python scripts/train_dpo.py
  python scripts/train_dpo.py --sft-checkpoint ./jestify-manim-coder-v1
  python scripts/train_dpo.py --test-run  # quick test
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

SYSTEM_PROMPT = """\
You are an expert ManimCE animation developer generating code for Jestify educational videos.
Output ONLY valid JSON: {"scene_index": N, "manim_code": "from manim import *\\n..."}
NEVER use MathTex() or Tex(). Use Text() with Unicode math symbols (x², π, ∫, Σ, →).
Every self.play() must have run_time=1.0-2.5. End scenes with self.wait(2).
Class name must be Scene{N:03d}. Inherit from MovingCameraScene."""


def build_prompt(record: dict) -> str:
    """Build the user message (prompt) for a training record."""
    idx = record.get("scene_index", 0)
    title = record.get("title", "Untitled")
    stype = record.get("scene_type", "custom")
    dur = record.get("duration_hint_seconds", 22)
    difficulty = record.get("difficulty", "intermediate")
    narration = record.get("narration_text", "")
    visual = record.get("visual_description", "")
    return (
        f"Generate ManimCE code for Scene {idx} of '{title}' ({stype}, {dur}s).\n"
        f"Difficulty: {difficulty}\n\n"
        f"Narration: \"{narration}\"\n"
        f"Visual: \"{visual}\""
    )


def build_dpo_pairs(dataset_path: Path) -> list[dict]:
    """Extract DPO preference pairs from the dataset.

    Strategy: For each (topic, difficulty, character, scene_index) group,
    pair the best rendering result as "chosen" against the worst as "rejected".
    """
    # Group records by their input identity
    from collections import defaultdict
    groups = defaultdict(list)
    with open(dataset_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not record.get("manim_code"):
                continue
            key = (
                record.get("topic", ""),
                record.get("difficulty", ""),
                record.get("character", ""),
                record.get("scene_index", 0),
            )
            groups[key].append(record)

    pairs = []
    for key, records in groups.items():
        # Need at least 2 records for the same scene to form a pair
        # (This happens when the same scene was generated multiple times with retries)
        successes = [r for r in records if r.get("render_success") is True and not r.get("constraint_violations")]
        failures = [r for r in records if r.get("render_success") is False or r.get("constraint_violations")]

        if successes and failures:
            chosen = successes[0]
            rejected = failures[0]
            pairs.append({
                "prompt": build_prompt(chosen),
                "chosen": json.dumps({"scene_index": chosen.get("scene_index", 0), "manim_code": chosen.get("manim_code", "")}),
                "rejected": json.dumps({"scene_index": rejected.get("scene_index", 0), "manim_code": rejected.get("manim_code", "")}),
            })

    return pairs


def train(args):
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, PeftModel, TaskType
    from trl import DPOConfig, DPOTrainer
    from datasets import Dataset

    print(f"\n{'='*60}")
    print("JESTIFY MANIM CODER — DPO TRAINING")
    print(f"{'='*60}")
    print(f"SFT checkpoint: {args.sft_checkpoint}")
    print(f"Dataset:        {args.dataset}")
    print(f"Output:         {args.output}")
    print(f"{'='*60}\n")

    # ── Build preference pairs ────────────────────────────────────────────────
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Dataset not found: {dataset_path}")
        sys.exit(1)

    pairs = build_dpo_pairs(dataset_path)
    print(f"DPO preference pairs found: {len(pairs)}")

    if len(pairs) < 10:
        print(
            "Too few preference pairs. DPO needs multiple attempts at the same scene.\n"
            "Generate more data or use --dataset with a larger JSONL that has retries."
        )
        print("\nAlternative: run train_sft.py only — SFT alone is usually sufficient.")
        sys.exit(1)

    if args.test_run:
        pairs = pairs[:50]

    split_idx = int(len(pairs) * 0.9)
    train_pairs = pairs[:split_idx]
    eval_pairs = pairs[split_idx:]
    train_ds = Dataset.from_list(train_pairs)
    eval_ds = Dataset.from_list(eval_pairs)
    print(f"Train pairs: {len(train_pairs)}  |  Eval pairs: {len(eval_pairs)}")

    # ── Load tokenizer and model ──────────────────────────────────────────────
    sft_path = args.sft_checkpoint
    print(f"\nLoading SFT checkpoint: {sft_path}")
    tokenizer = AutoTokenizer.from_pretrained(sft_path, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        sft_path,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )
    model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # ── DPO training config ───────────────────────────────────────────────────
    dpo_config = DPOConfig(
        output_dir=args.output,
        num_train_epochs=1 if args.test_run else 1,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=5e-5,
        warmup_ratio=0.05,
        lr_scheduler_type="cosine",
        bf16=True,
        gradient_checkpointing=True,
        max_length=3072,
        max_prompt_length=1024,
        beta=0.1,                    # DPO temperature — controls preference strength
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=50,
        save_strategy="steps",
        save_steps=100,
        report_to="tensorboard",
        run_name="jestify-manim-coder-dpo",
    )

    trainer = DPOTrainer(
        model=model,
        ref_model=None,              # None with PEFT uses implicit reference
        tokenizer=tokenizer,
        args=dpo_config,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
    )

    print("\nStarting DPO training...")
    trainer.train()

    print("\nSaving DPO model...")
    trainer.save_model(args.output)
    tokenizer.save_pretrained(args.output)

    print(f"\n{'='*60}")
    print("DPO training complete!")
    print(f"Model saved to: {args.output}")
    print("\nNext steps:")
    print("  1. A/B test: python scripts/ab_test.py --topic 'Derivatives'")
    print("  2. Convert:  bash scripts/convert_to_gguf.sh")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", default=str(ROOT / "data" / "training" / "jestify_dataset.jsonl"))
    parser.add_argument("--sft-checkpoint", default=str(ROOT / "jestify-manim-coder-v1"),
                        help="Path to SFT-trained model checkpoint")
    parser.add_argument("--output", default=str(ROOT / "jestify-manim-coder-v1-dpo"))
    parser.add_argument("--test-run", action="store_true", help="Quick test: 50 pairs, 1 epoch")
    args = parser.parse_args()
    train(args)


if __name__ == "__main__":
    main()
