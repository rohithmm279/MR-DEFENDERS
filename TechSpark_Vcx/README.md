# MR DEFENDERS- Local Legal Guidance MVP

An offline-first hackathon prototype for English legal-information guidance in three areas: consumer complaints, criminal procedure basics, and family-law basics. It is **not legal advice** and does not replace a licensed advocate.

## Quick start

1. Install Python dependencies only into `G:\DO_TOUCH\Programmes\.dumpEnv`:
   `G:\DO_TOUCH\Programmes\.dumpEnv\Scripts\python.exe -m pip install -r backend/requirements.txt`
2. Store locally downloaded model assets in `G:\OllaMa\FH_Models` (see `models/README.md`).
3. Build the local index: `G:\DO_TOUCH\Programmes\.dumpEnv\Scripts\python.exe scripts/reindex.py`
4. Start the API: `G:\DO_TOUCH\Programmes\.dumpEnv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload`
5. Install and run the frontend: `pnpm --dir frontend install` then `pnpm --dir frontend dev`.

The API runs at `http://127.0.0.1:8000`; the Vite UI runs at `http://127.0.0.1:5173`.

## Grounding and local tuning checks

Extract the external legal PDF collection into review-only candidates and provenance files:

`python scripts/ingest_legal_pdfs.py --input G:\DO_TOUCH\Programmes\Legal_SLM_Dataset --output-corpus corpus/legal_corpus_candidates.json --output-manifest data/legal_dataset_manifest.json --output-training-candidates training/legal_training_candidates.jsonl`

Generate the dataset inventory report:

`python scripts/report_legal_dataset.py --input G:\DO_TOUCH\Programmes\Legal_SLM_Dataset --output docs/legal_dataset_report.md`

The generated corpus candidates are marked `needs_review` and are not used by the live retriever until a human approves their source text and metadata.

Before indexing or training, validate the local source registry and instruction data:

`G:\DO_TOUCH\Programmes\.dumpEnv\Scripts\python.exe scripts/validate_corpus.py`

`G:\DO_TOUCH\Programmes\.dumpEnv\Scripts\python.exe scripts/validate_training.py`

Optional QLoRA preparation uses the local Hugging Face model snapshot, not a GGUF file:

`python scripts/train_qlora.py --model G:\OllaMa\FH_Models\models--Qwen--Qwen3-4B-Instruct-2507-FP8\snapshots\8591804019c8b22094c3b5b4454e0edc05dffc98`

The training entry point is local-only and stops safely when the optional CUDA, Transformers, PEFT, or TRL stack is unavailable.

## Privacy and safety

- No account, database of users, or query logging is implemented.
- At runtime the app only uses local files and localhost services.
- Crisis, arrest-in-progress, active-court-case, and immediate-danger requests bypass generation and show escalation guidance.
- Citations are rendered only from retrieved corpus metadata.

## Model download prerequisite

The selected model is `Qwen/Qwen3-4B-Instruct-2507`, an Apache-2.0, non-gated model. Download and conversion instructions are in `models/README.md`.
