"""Extract auditable, section-level source candidates from local legal PDFs.

Automated extraction is intentionally marked ``needs_review``. These records
must be human-reviewed before they are used for answers or QLoRA training.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from pypdf import PdfReader


def domain_for(path: Path) -> str:
    value = str(path).lower()
    if "consumer" in value:
        return "consumer"
    if "criminal" in value:
        return "criminal"
    if "family" in value:
        return "family"
    raise ValueError(f"Cannot classify PDF domain: {path}")


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\x00", " ")).strip()


def extract_text(path: Path) -> str:
    return "\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages)


def title_from(text: str, path: Path) -> str:
    for line in (clean(line) for line in text.splitlines()[:80]):
        if "ACT" in line.upper() and len(line) < 180:
            return line
    return path.stem.replace("_", " ")


def sections(text: str) -> list[tuple[str, str]]:
    normalized = text.replace("\r", "")
    matches = list(re.finditer(r"(?im)(?:^|\n)\s*(\d+[A-Za-z]?(?:\([^)]+\))?)\.\s+([^\n]{3,})", normalized))
    if not matches:
        return [("Document overview", clean(normalized)[:12000])]
    output: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.start(1)
        end = matches[index + 1].start(1) if index + 1 < len(matches) else len(normalized)
        body = clean(normalized[start:end])
        if len(body) >= 40:
            output.append((f"Section {match.group(1)}", body[:16000]))
    return output


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_records(input_dir: Path) -> tuple[list[dict], list[dict]]:
    records: list[dict] = []
    manifest: list[dict] = []
    seen_hashes: dict[str, str] = {}
    for path in sorted(input_dir.rglob("*.pdf")):
        file_hash = sha256(path)
        text = extract_text(path)
        entry = {"source_file": str(path), "source_hash": file_hash, "pages": len(PdfReader(str(path)).pages), "characters": len(text), "domain": domain_for(path), "duplicate_of": seen_hashes.get(file_hash)}
        manifest.append(entry)
        if file_hash in seen_hashes:
            continue
        seen_hashes[file_hash] = str(path)
        act_name = title_from(text, path)
        for index, (section_number, section_text) in enumerate(sections(text)):
            records.append({
                "id": f"{domain_for(path)}-{file_hash[:12]}-{index}",
                "domain": domain_for(path),
                "act_name": act_name,
                "section_number": section_number,
                "section_text": section_text,
                "jurisdiction": "India - Central; state rules may apply",
                "source_url": "",
                "source_type": "statute" if "acts" in str(path).lower() else "official_procedure",
                "verification_status": "needs_review",
                "source_file": str(path),
                "source_hash": file_hash,
            })
    return records, manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-corpus", required=True, type=Path)
    parser.add_argument("--output-manifest", required=True, type=Path)
    parser.add_argument("--output-training-candidates", required=True, type=Path)
    args = parser.parse_args()
    records, manifest = build_records(args.input)
    for target in (args.output_corpus, args.output_manifest, args.output_training_candidates):
        target.parent.mkdir(parents=True, exist_ok=True)
    args.output_corpus.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    with args.output_training_candidates.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps({"instruction": "REVIEW: write a user question for this source", "context": record["section_text"], "response": "REVIEW REQUIRED", "cited_sections": [f'{record["act_name"]}, {record["section_number"]}'], "review_status": "needs_review"}, ensure_ascii=False) + "\n")
    print(f"Extracted {len(records)} source candidates from {len(manifest)} PDFs.")
    print("All generated records are marked needs_review and are not answerable until approved.")


if __name__ == "__main__":
    main()
