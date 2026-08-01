# Optional QLoRA adapter

The MVP is intentionally grounded in local RAG. Add 200-500 human-reviewed instruction/context/response records to `training/legal_instruction_dataset.jsonl`, then validate them with `python scripts/validate_training.py` before training. Each record must contain `instruction`, `context`, `response`, and `cited_sections`; every cited section must occur in `context`.

`training/legal_training_candidates.jsonl` is generated from the external PDF collection as a review aid. It contains placeholders and must not be trained directly. Replace each placeholder with a reviewed user question and grounded response, then create deterministic train/validation/test files with `python scripts/split_training_data.py --input G:\DO_TOUCH\Programmes\Legal_SLM_Dataset\Training_Data\legal_instruction_dataset.jsonl --output-dir G:\DO_TOUCH\Programmes\Legal_SLM_Dataset\Training_Data\splits`.

Use `scripts/train_qlora.py` with the local Hugging Face model snapshot as the training base. A GGUF file is for inference and must not be passed as the QLoRA base. The script is intentionally local-only and stops when the optional CUDA/Transformers/PEFT/TRL stack is unavailable.
