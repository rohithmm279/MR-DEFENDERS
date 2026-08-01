"""Write a compact inventory report for the external legal PDF dataset."""
from __future__ import annotations

import argparse
from pathlib import Path

from ingest_legal_pdfs import build_records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    records, manifest = build_records(args.input)
    duplicates = [item for item in manifest if item["duplicate_of"]]
    lines = [
        "# Legal SLM Dataset Report",
        "",
        f"- Input folder: `{args.input}`",
        f"- PDFs inspected: {len(manifest)}",
        f"- Unique PDFs: {len(manifest) - len(duplicates)}",
        f"- Duplicate files by SHA-256: {len(duplicates)}",
        f"- Extracted source candidates: {len(records)}",
        "- Automated candidates are marked `needs_review`; they must not be used for answers or QLoRA until reviewed.",
        "",
        "## Domain counts",
    ]
    for domain in ("consumer", "criminal", "family"):
        lines.append(f"- {domain}: {sum(item['domain'] == domain for item in manifest)} PDFs")
    lines += ["", "## Training readiness", "", "The source PDFs are suitable as an input to RAG ingestion after section-level review. They are not a fine-tuning dataset. Create 200-500 reviewed JSONL records with instruction, context, response, and cited_sections before QLoRA training."]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote report: {args.output}")


if __name__ == "__main__":
    main()
