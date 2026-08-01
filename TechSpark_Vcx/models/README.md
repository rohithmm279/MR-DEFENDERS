# Local model assets

Canonical model directory: `G:\OllaMa\FH_Models`.

Expected runtime filename: `qwen3-4b-instruct-2507-q4_k_m.gguf`.

1. Download the original, non-gated Apache-2.0 model `Qwen/Qwen3-4B-Instruct-2507` to `G:\OllaMa\FH_Models\qwen3-4b-instruct-2507`.
2. Use the original weights for optional QLoRA fine-tuning.
3. Merge a validated adapter, convert with llama.cpp, and quantize to Q4_K_M. Place the output at the expected runtime filename above.

Never commit model weights or tokens. `models/` is ignored by Git except this guide.
