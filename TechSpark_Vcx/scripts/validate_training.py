"""Validate grounded instruction records before they are used for tuning."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED = {"instruction", "context", "response", "cited_sections"}


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_no}: invalid JSON ({exc.msg})")
            continue
        missing = REQUIRED - item.keys()
        if missing:
            errors.append(f"line {line_no}: missing {sorted(missing)}")
            continue
        if not all(isinstance(item[key], str) and item[key].strip() for key in ("instruction", "context", "response")):
            errors.append(f"line {line_no}: instruction/context/response must be non-empty strings")
        if not isinstance(item["cited_sections"], list) or not all(isinstance(value, str) for value in item["cited_sections"]):
            errors.append(f"line {line_no}: cited_sections must be a list of strings")
        elif any(section.lower() not in item["context"].lower() for section in item["cited_sections"]):
            errors.append(f"line {line_no}: every cited section must occur in context")
    return errors


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parents[1] / "training" / "legal_instruction_dataset.jsonl"
    problems = validate(target)
    if problems:
        print("Training validation failed:")
        print("\n".join(problems))
        raise SystemExit(1)
    print(f"Training validation passed: {target}")
