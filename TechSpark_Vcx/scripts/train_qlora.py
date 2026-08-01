"""Minimal optional QLoRA entry point.

The script deliberately fails with an actionable message when the local
training stack is not installed. It never downloads models or calls a hosted
LLM service.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from validate_training import validate
from validate_corpus import validate as validate_corpus


def main() -> int:
    parser = argparse.ArgumentParser(description="Train a local QLoRA adapter after validating grounded records.")
    parser.add_argument("--model", required=True, help="Local Hugging Face model directory (not a GGUF file).")
    parser.add_argument("--dataset", default="training/legal_instruction_dataset.jsonl")
    parser.add_argument("--output", default="training/output/nyaya-sahayak-adapter")
    parser.add_argument("--corpus", default="corpus/legal_corpus.json")
    args = parser.parse_args()
    dataset = Path(args.dataset)
    problems = validate(dataset)
    if problems:
        raise SystemExit("Refusing to train on invalid data:\n" + "\n".join(problems))
    corpus_problems = validate_corpus(Path(args.corpus))
    if corpus_problems:
        raise SystemExit("Refusing to train with invalid corpus:\n" + "\n".join(corpus_problems))
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        import peft  # noqa: F401
        import trl  # noqa: F401
    except ImportError as exc:
        raise SystemExit(f"QLoRA dependencies are unavailable ({exc}). Install the optional local training stack first.") from exc
    if not Path(args.model).exists():
        raise SystemExit(f"Local training model does not exist: {args.model}")
    raise SystemExit("Dataset and environment validated. Add the approved trainer configuration before launching GPU training.")


if __name__ == "__main__":
    main()
