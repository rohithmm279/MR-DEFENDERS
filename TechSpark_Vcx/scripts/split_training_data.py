"""Create deterministic train/validation/test JSONL splits after validation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from validate_training import validate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if not args.input.exists():
        candidate = args.input.with_name("legal_training_candidates.jsonl")
        hint = f" Review {candidate} and save approved records as {args.input}." if candidate.exists() else " Create the reviewed JSONL file first."
        raise SystemExit(f"Training input not found: {args.input}.{hint}")
    problems = validate(args.input)
    if problems:
        raise SystemExit("Refusing to split invalid data:\n" + "\n".join(problems))
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows.sort(key=lambda row: hashlib.sha256(row["instruction"].strip().lower().encode()).hexdigest())
    if len(rows) < 10:
        print(f"Warning: only {len(rows)} reviewed records; splits are for development only.")
    train_count = max(1, int(len(rows) * 0.8))
    validation_count = max(1, int(len(rows) * 0.1))
    while train_count + validation_count >= len(rows) and train_count > 1:
        train_count -= 1
    counts = {"train": train_count, "validation": validation_count, "test": len(rows) - train_count - validation_count}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    cursor = 0
    for name in ("train", "validation", "test"):
        batch = rows[cursor:cursor + counts[name]]
        cursor += counts[name]
        (args.output_dir / f"{name}.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in batch), encoding="utf-8")
    print(f"Wrote deterministic splits to {args.output_dir}")


if __name__ == "__main__":
    main()
