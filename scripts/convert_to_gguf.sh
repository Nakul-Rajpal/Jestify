#!/usr/bin/env bash
# Convert the finetuned Jestify model to GGUF format and load into Ollama.
#
# Prerequisites:
#   1. llama.cpp installed: https://github.com/ggerganov/llama.cpp
#      (build it: git clone https://github.com/ggerganov/llama.cpp && cd llama.cpp && make)
#   2. Ollama installed and running: https://ollama.com
#   3. Training complete: jestify-manim-coder-v1/ directory exists
#
# Usage:
#   bash scripts/convert_to_gguf.sh
#   bash scripts/convert_to_gguf.sh --model-dir ./jestify-manim-coder-v1-dpo  # use DPO model
#   bash scripts/convert_to_gguf.sh --skip-merge  # if already have merged model

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_DIR="${ROOT}/jestify-manim-coder-v1"
MERGED_DIR="${ROOT}/jestify-manim-coder-v1-merged"
GGUF_PATH="${ROOT}/jestify-manim-coder-v1-q4_k_m.gguf"
OLLAMA_MODEL_NAME="jestify-manim-coder"
LLAMA_CPP_DIR="${HOME}/llama.cpp"       # update if llama.cpp is elsewhere
SKIP_MERGE=false

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --model-dir) MODEL_DIR="$2"; shift 2 ;;
        --skip-merge) SKIP_MERGE=true; shift ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

echo "=============================="
echo "Jestify GGUF Conversion"
echo "=============================="
echo "Model dir:  ${MODEL_DIR}"
echo "GGUF path:  ${GGUF_PATH}"
echo "Ollama model: ${OLLAMA_MODEL_NAME}"
echo ""

# ── Step 1: Merge LoRA adapters into base model ────────────────────────────────
if [ "$SKIP_MERGE" = false ]; then
    echo "Step 1: Merging LoRA adapters into base model..."
    python3 - <<'EOF'
import sys, torch
from pathlib import Path
from peft import AutoPeftModelForCausalLM
from transformers import AutoTokenizer

ROOT = Path(__file__).parent if "__file__" in dir() else Path(".")
model_dir = sys.argv[1] if len(sys.argv) > 1 else str(Path.cwd() / "jestify-manim-coder-v1")
merged_dir = model_dir + "-merged"

print(f"Loading LoRA model from: {model_dir}")
model = AutoPeftModelForCausalLM.from_pretrained(
    model_dir, device_map="cpu", torch_dtype=torch.bfloat16, trust_remote_code=True,
)
print("Merging LoRA adapters...")
merged = model.merge_and_unload()
tokenizer = AutoTokenizer.from_pretrained(model_dir, trust_remote_code=True)
print(f"Saving merged model to: {merged_dir}")
merged.save_pretrained(merged_dir, safe_serialization=True)
tokenizer.save_pretrained(merged_dir)
print("Merge complete!")
EOF
    echo "Merged model saved to: ${MERGED_DIR}"
else
    echo "Step 1: Skipping merge (--skip-merge specified)"
    MERGED_DIR="${MODEL_DIR}"
fi

# ── Step 2: Convert to GGUF ────────────────────────────────────────────────────
echo ""
echo "Step 2: Converting to GGUF with Q4_K_M quantization..."

if [ ! -f "${LLAMA_CPP_DIR}/convert_hf_to_gguf.py" ]; then
    echo "ERROR: llama.cpp not found at ${LLAMA_CPP_DIR}"
    echo "Install it:"
    echo "  git clone https://github.com/ggerganov/llama.cpp ${LLAMA_CPP_DIR}"
    echo "  cd ${LLAMA_CPP_DIR} && pip install -r requirements.txt"
    exit 1
fi

# First convert to f16 GGUF
F16_GGUF="${ROOT}/jestify-manim-coder-v1-f16.gguf"
python3 "${LLAMA_CPP_DIR}/convert_hf_to_gguf.py" \
    "${MERGED_DIR}" \
    --outfile "${F16_GGUF}" \
    --outtype f16

echo "F16 GGUF created: ${F16_GGUF}"

# Quantize to Q4_K_M (4-bit, best quality-size balance)
"${LLAMA_CPP_DIR}/llama-quantize" "${F16_GGUF}" "${GGUF_PATH}" Q4_K_M

echo "Q4_K_M GGUF created: ${GGUF_PATH}"
echo "Size: $(du -h "${GGUF_PATH}" | cut -f1)"

# Clean up f16 intermediate
rm -f "${F16_GGUF}"

# ── Step 3: Create Ollama Modelfile ────────────────────────────────────────────
echo ""
echo "Step 3: Creating Ollama Modelfile..."

MODELFILE="${ROOT}/scripts/Modelfile"
cat > "${MODELFILE}" <<MODELEOF
FROM ${GGUF_PATH}

PARAMETER temperature 0.3
PARAMETER top_p 0.9
PARAMETER top_k 40
PARAMETER num_ctx 4096
PARAMETER repeat_penalty 1.1

SYSTEM """You are an expert ManimCE animation developer generating code for Jestify educational videos.
Output ONLY valid JSON: {"scene_index": N, "manim_code": "from manim import *\\n..."}
NEVER use MathTex() or Tex(). Use Text() with Unicode math symbols (x², π, ∫, Σ, →).
Every self.play() must have run_time=1.0-2.5. End scenes with self.wait(2).
Class name must be Scene{N:03d} (e.g., Scene000, Scene001). Inherit from MovingCameraScene.
Keep all content in safe zone: x in [-6.0, 6.0], y in [-3.2, 3.2].
Axis labels MUST be Text() objects, never plain strings."""
MODELEOF

echo "Modelfile created: ${MODELFILE}"

# ── Step 4: Load into Ollama ───────────────────────────────────────────────────
echo ""
echo "Step 4: Loading model into Ollama..."

if ! command -v ollama &>/dev/null; then
    echo "ERROR: Ollama not found. Install from https://ollama.com"
    exit 1
fi

ollama create "${OLLAMA_MODEL_NAME}" -f "${MODELFILE}"
echo "Ollama model '${OLLAMA_MODEL_NAME}' created successfully!"

# ── Step 5: Quick smoke test ───────────────────────────────────────────────────
echo ""
echo "Step 5: Running quick smoke test..."

RESPONSE=$(ollama run "${OLLAMA_MODEL_NAME}" \
    "Generate ManimCE code for Scene 0 of 'Test' (concept_reveal, 15s). Narration: 'Hello world.' Visual: 'Show hello world text.'" \
    2>/dev/null || echo "")

if echo "${RESPONSE}" | grep -q "manim_code"; then
    echo "✓ Smoke test passed — model generates JSON with manim_code"
else
    echo "✗ Smoke test failed — check response:"
    echo "${RESPONSE:0:300}"
fi

# ── Done ───────────────────────────────────────────────────────────────────────
echo ""
echo "=============================="
echo "Conversion complete!"
echo "=============================="
echo ""
echo "To use in Jestify, add to .env:"
echo "  CODE_PROVIDER=ollama"
echo "  OLLAMA_CODE_MODEL=${OLLAMA_MODEL_NAME}"
echo ""
echo "Then restart the backend and test:"
echo "  python scripts/ab_test.py --topic 'Derivatives' --difficulty beginner"
