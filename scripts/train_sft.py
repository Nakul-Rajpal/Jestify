#!/usr/bin/env python3
"""SFT (Supervised Fine-Tuning) training script for Jestify Manim code generation.

Fine-tunes Qwen2.5-Coder-7B-Instruct on the Jestify dataset using QLoRA
(4-bit quantization + LoRA adapters) to fit within 16GB VRAM.

After training, the model can be deployed to Ollama as a local replacement
for Claude Opus in the code generation step.

Requirements:
  pip install -r scripts/requirements_training.txt

Usage:
  # Local training (Quadro RTX 5000 / RTX 5070):
  python scripts/train_sft.py

  # AWS EC2 (larger GPU, faster):
  python scripts/train_sft.py --no-qlora --batch-size 2

  # Quick test run (1 epoch, small subset):
  python scripts/train_sft.py --test-run

  # Custom dataset:
  python scripts/train_sft.py --dataset data/training/combined_dataset.jsonl

  # Resume from checkpoint:
  python scripts/train_sft.py --resume-from ./jestify-manim-coder-v1/checkpoint-500

Options:
  --dataset PATH        Training data JSONL (default: data/training/jestify_dataset.jsonl)
  --output DIR          Output directory (default: ./jestify-manim-coder-v1)
  --model MODEL_ID      Base model (default: Qwen/Qwen2.5-Coder-7B-Instruct)
  --epochs N            Training epochs (default: 3)
  --batch-size N        Per-device batch size (default: 1, use 2 with A100)
  --no-qlora            Disable 4-bit quantization (requires 40GB+ VRAM)
  --test-run            Train on 100 examples for 1 epoch to verify setup
  --resume-from PATH    Resume from a checkpoint directory
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── System prompt for inference (matches what generate_training_data.py uses) ─

SYSTEM_PROMPT = """\
You are an expert ManimCE animation developer generating code for Jestify educational videos.
Output ONLY valid JSON: {"scene_index": N, "manim_code": "from manim import *\\n..."}
NEVER use MathTex() or Tex(). Use Text() with Unicode math symbols (x², π, ∫, Σ, →).
Every self.play() must have run_time=1.0-2.5. End scenes with self.wait(2).
Class name must be Scene{N:03d} (e.g., Scene000, Scene001). Inherit from MovingCameraScene.
Keep all content in safe zone: x in [-6.0, 6.0], y in [-3.2, 3.2].
Axis labels MUST be Text() objects, never plain strings."""


def build_chat_messages(record: dict) -> list[dict]:
    """Convert a JSONL training record into chat messages for the model."""
    idx = record.get("scene_index", 0)
    title = record.get("title", "Untitled")
    stype = record.get("scene_type", "custom")
    dur = record.get("duration_hint_seconds", 22)
    difficulty = record.get("difficulty", "intermediate")
    narration = record.get("narration_text", "")
    visual = record.get("visual_description", "")
    manim_code = record.get("manim_code", "")

    user_content = (
        f"Generate ManimCE code for Scene {idx} of '{title}' ({stype}, {dur}s).\n"
        f"Difficulty: {difficulty}\n\n"
        f"Narration: \"{narration}\"\n"
        f"Visual: \"{visual}\""
    )
    assistant_content = json.dumps({"scene_index": idx, "manim_code": manim_code})

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
        {"role": "assistant", "content": assistant_content},
    ]


def load_and_filter_dataset(dataset_path: Path, test_run: bool = False) -> list[dict]:
    """Load JSONL dataset and filter to only high-quality examples."""
    records = []
    with open(dataset_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Only train on examples that passed rendering and have no violations
            if record.get("render_success") is not True:
                continue
            if record.get("constraint_violations"):
                continue
            if not record.get("manim_code"):
                continue
            # Minimum code quality: at least 10 lines
            if record["manim_code"].count("\n") < 10:
                continue

            records.append(record)

    if test_run:
        records = records[:100]

    return records


def train(args):
    # ── Imports (deferred to avoid slow startup when not training) ────────────
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, TaskType
    from trl import SFTConfig, SFTTrainer
    from datasets import Dataset

    print(f"\n{'='*60}")
    print("JESTIFY MANIM CODER — SFT TRAINING")
    print(f"{'='*60}")
    print(f"Base model:   {args.model}")
    print(f"Dataset:      {args.dataset}")
    print(f"Output:       {args.output}")
    print(f"Epochs:       {args.epochs}")
    print(f"Batch size:   {args.batch_size}")
    print(f"QLoRA:        {'disabled' if args.no_qlora else 'enabled (4-bit)'}")
    print(f"Test run:     {args.test_run}")
    print(f"{'='*60}\n")

    # ── Load and filter dataset ───────────────────────────────────────────────
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Dataset not found: {dataset_path}")
        print("Run generate_training_data.py first.")
        sys.exit(1)

    all_records = load_and_filter_dataset(dataset_path, test_run=args.test_run)
    print(f"Training examples (render_success=True, no violations): {len(all_records)}")

    if len(all_records) < 10:
        print("Too few examples. Run generate_training_data.py to build the dataset first.")
        sys.exit(1)

    # Split 90/10 train/eval
    split_idx = int(len(all_records) * 0.9)
    train_records = all_records[:split_idx]
    eval_records = all_records[split_idx:]
    print(f"Train: {len(train_records)}  |  Eval: {len(eval_records)}")

    # ── Tokenizer ─────────────────────────────────────────────────────────────
    print(f"\nLoading tokenizer: {args.model}")
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    # ── Format dataset for SFTTrainer ─────────────────────────────────────────
    def format_record(record):
        messages = build_chat_messages(record)
        return {"text": tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)}

    train_data = Dataset.from_list([format_record(r) for r in train_records])
    eval_data = Dataset.from_list([format_record(r) for r in eval_records])
    print(f"Dataset formatted. Sample input length: {len(train_data[0]['text'])} chars")

    # ── Model ─────────────────────────────────────────────────────────────────
    print(f"\nLoading model: {args.model}")

    if not args.no_qlora:
        # QLoRA 4-bit config — fits in 16GB VRAM
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
        model = AutoModelForCausalLM.from_pretrained(
            args.model,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
            torch_dtype=torch.bfloat16,
        )
        model = prepare_model_for_kbit_training(model)
    else:
        # Full precision / bf16 for larger GPUs
        model = AutoModelForCausalLM.from_pretrained(
            args.model,
            device_map="auto",
            trust_remote_code=True,
            torch_dtype=torch.bfloat16,
        )

    # ── LoRA adapters ─────────────────────────────────────────────────────────
    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        target_modules=[
            "q_proj", "v_proj", "k_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # ── Training configuration ────────────────────────────────────────────────
    output_dir = args.output

    training_args = SFTConfig(
        output_dir=output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=max(1, 8 // args.batch_size),  # effective batch = 8
        warmup_ratio=0.05,
        learning_rate=2e-4,
        lr_scheduler_type="cosine",
        optim="paged_adamw_32bit",
        bf16=True,
        fp16=False,
        gradient_checkpointing=True,
        max_seq_length=3072,         # covers full scene prompt + Manim code
        dataset_text_field="text",
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=100,
        save_strategy="steps",
        save_steps=200,
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        report_to="tensorboard",     # view with: tensorboard --logdir ./jestify-manim-coder-v1
        run_name="jestify-manim-coder-sft",
    )

    if args.resume_from:
        training_args.resume_from_checkpoint = args.resume_from

    # ── Trainer ───────────────────────────────────────────────────────────────
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        args=training_args,
        train_dataset=train_data,
        eval_dataset=eval_data,
    )

    print(f"\nStarting training...")
    print(f"TensorBoard: tensorboard --logdir {output_dir}")
    print(f"Checkpoints saved to: {output_dir}/\n")

    trainer.train(resume_from_checkpoint=args.resume_from)

    # ── Save final model ──────────────────────────────────────────────────────
    print("\nSaving final model and tokenizer...")
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)

    print(f"\n{'='*60}")
    print("Training complete!")
    print(f"Model saved to: {output_dir}")
    print()
    print("Next steps:")
    print("  1. Evaluate: python scripts/eval_model.py")
    print("  2. A/B test: python scripts/ab_test.py --topic 'Derivatives'")
    print("  3. Convert: bash scripts/convert_to_gguf.sh")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", default=str(ROOT / "data" / "training" / "jestify_dataset.jsonl"))
    parser.add_argument("--output", default=str(ROOT / "jestify-manim-coder-v1"))
    parser.add_argument("--model", default="Qwen/Qwen2.5-Coder-7B-Instruct")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--no-qlora", action="store_true", help="Disable QLoRA (needs 40GB+ VRAM)")
    parser.add_argument("--test-run", action="store_true", help="Quick test: 100 examples, 1 epoch")
    parser.add_argument("--resume-from", default=None, help="Checkpoint directory to resume from")
    args = parser.parse_args()

    if args.test_run:
        args.epochs = 1

    train(args)


if __name__ == "__main__":
    main()
