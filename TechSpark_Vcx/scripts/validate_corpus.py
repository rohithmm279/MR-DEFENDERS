"""Validate the local legal source registry without contacting the network."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED = {"id", "domain", "act_name", "section_number", "section_text", "jurisdiction", "source_url", "source_type", "verification_status"}
DOMAINS = {"consumer", "criminal", "family"}


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not records:
        return ["corpus must be a non-empty JSON list"]
    ids: set[str] = set()
    for index, record in enumerate(records, 1):
        missing = REQUIRED - record.keys()
        if missing:
            errors.append(f"record {index}: missing {sorted(missing)}")
        if record.get("id") in ids:
            errors.append(f"record {index}: duplicate id {record.get('id')}")
        ids.add(record.get("id"))
        if record.get("domain") not in DOMAINS:
            errors.append(f"record {index}: unsupported domain")
        if record.get("verification_status") not in {"verified", "needs_review"}:
            errors.append(f"record {index}: invalid verification_status")
        if not str(record.get("section_text", "")).strip():
            errors.append(f"record {index}: section_text is empty")
    return errors


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parents[1] / "corpus" / "legal_corpus.json"
    problems = validate(target)
    if problems:
        print("Corpus validation failed:\n" + "\n".join(problems))
        raise SystemExit(1)
    print(f"Corpus validation passed: {target}")
