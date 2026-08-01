# Legal SLM Dataset Report

- Input folder: `G:\DO_TOUCH\Programmes\Legal_SLM_Dataset`
- PDFs inspected: 12
- Unique PDFs: 10
- Duplicate files by SHA-256: 2
- Extracted source candidates: 1059
- Automated candidates are marked `needs_review`; they must not be used for answers or QLoRA until reviewed.

## Domain counts
- consumer: 4 PDFs
- criminal: 4 PDFs
- family: 4 PDFs

## Training readiness

The source PDFs are suitable as an input to RAG ingestion after section-level review. They are not a fine-tuning dataset. Create 200-500 reviewed JSONL records with instruction, context, response, and cited_sections before QLoRA training.
