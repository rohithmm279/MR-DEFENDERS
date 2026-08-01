# Nyaya Sahayak - Local Legal Guidance MVP
## Project Report

---

## Executive Summary

**Nyaya Sahayak** ("Legal Helper") is an **offline-first, privacy-preserving legal information system** built as a hackathon prototype. It provides grounded legal guidance in three Indian law domains—**Consumer Complaints**, **Criminal Procedure Basics** (FIR/Bail), and **Family Law Basics** (Marriage/Dowry)—using only **locally verified statutory sources** and a **local LLM** (Qwen3-4B-Instruct GGUF). The system explicitly does **not** provide legal advice and includes safety escalation for crisis scenarios.

**Key Differentiators:**
- Zero network calls at runtime (fully offline after setup)
- Only verified human-reviewed sources are used for answers
- Safety-first design with crisis/active-case detection
- Lexical + semantic retrieval with conservative confidence thresholds
- GGUF local inference via llama.cpp (GPU accelerated)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React + Vite)                  │
│  http://127.0.0.1:5173                                          │
│  - Single-page chat UI with citations, steps, follow-ups       │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST API (JSON)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BACKEND (FastAPI + Uvicorn)                │
│  http://127.0.0.1:8000                                          │
│  - /api/v1/chat       → Main QA endpoint                        │
│  - /api/v1/health     → System status                           │
│  - /api/v1/corpus/reindex → Build Chroma index                 │
│  - /api/v1/sources/{id} → Source inspection                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  LocalRetriever│    │  LocalLlama   │    │ Safety Router │
│  (Chroma +     │    │  (llama.cpp   │    │ (Crisis/      │
│   MiniLM L6)   │    │   GGUF Q4_K_M)│    │  Domain guard)│
└───────────────┘    └───────────────┘    └───────────────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             ▼
              ┌───────────────────────────────┐
              │    Verified Corpus (JSON)     │
              │  corpus/legal_corpus.json     │
              │  (7 verified records)         │
              └───────────────────────────────┘
```

---

## Directory Structure

```
Programmes/TechSpark_Vcx/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI routes
│   │   ├── service.py        # Orchestration logic
│   │   ├── retrieval.py      # Chroma + lexical fallback
│   │   ├── llm.py            # GGUF inference + citation guard
│   │   ├── safety.py         # Crisis detection + domain classification
│   │   ├── schemas.py        # Pydantic models (request/response)
│   │   ├── settings.py       # Configuration (paths, thresholds)
│   │   └── test_api.py       # Integration tests
│   └── requirements.txt
├── corpus/
│   ├── legal_corpus.json              # 7 verified records (production)
│   └── legal_corpus_candidates.json   # 1059 needs_review records
├── data/
│   ├── chroma/                        # Persistent vector store (4 shards)
│   └── legal_dataset_manifest.json    # PDF ingestion manifest
├── docs/
│   └── legal_dataset_report.md        # Dataset inventory report
├── frontend/
│   ├── src/
│   │   ├── main.tsx          # React SPA (single file)
│   │   └── styles.css        # Minimal, responsive styling
│   ├── package.json
│   ├── index.html
│   └── vite.config.ts
├── models/
│   └── README.md              # Model download instructions (Qwen3-4B)
├── scripts/
│   ├── ingest_legal_pdfs.py       # PDF → section candidates (needs_review)
│   ├── report_legal_dataset.py    # Corpus inventory report
│   ├── validate_corpus.py         # Schema validation
│   ├── validate_training.py       # Instruction data validation
│   ├── reindex.py                 # Build Chroma index
│   ├── train_qlora.py             # Optional QLoRA entry point
│   └── split_training_data.py
├── training/
│   └── legal_training_candidates.jsonl  # 1059 review candidates
├── SRS_Legal_Assistance_SLM.pdf   # Software Requirements Spec
└── README.md
```

---

## Core Components Deep Dive

### 1. Backend Service Layer (`backend/app/service.py`)

**Flow for `/api/v1/chat`:**
1. **Safety Assessment** → `assess_safety(query)` checks for immediate danger, active court case
2. **Domain Classification** → `classify_domain(query)` scores consumer/criminal/family keywords
3. **Follow-up Detection** → Short queries or missing key terms trigger clarification questions
4. **Retrieval** → `LocalRetriever.retrieve(query, domain)` returns top-k verified records
5. **Confidence Gate** → Score < 0.40 → low_confidence response (no LLM)
6. **LLM Generation** → `LocalLlama.generate()` with strict citation validation
7. **Response Assembly** → Structured `ChatResponse` with blocks, citations, steps

**Key Design Decisions:**
- **Verified-only retrieval**: `verification_status == "verified"` filter (line 33, retrieval.py)
- **Conservative scoring**: Lexical overlap + exact section match bonus (lines 47-52)
- **Citation guard**: LLM output rejected if it cites sections/acts not in retrieved passages (llm.py:41-51)
- **Safe fallback**: If LLM unavailable or fails citation check → retrieval-only answer

### 2. Retrieval System (`backend/app/retrieval.py`)

**Two Modes:**
| Mode | Trigger | Description |
|------|---------|-------------|
| Lexical Fallback | Default / no Chroma index | Token overlap scoring, deterministic, no embeddings |
| Semantic (Chroma) | After `reindex.py` runs | MiniLM-L6-v2 embeddings, persisted to `data/chroma/` |

**Indexing (`reindex()`):**
- Loads all records from `corpus/legal_corpus.json`
- Embeds `section_text` with `sentence-transformers/all-MiniLM-L6-v2`
- Stores in Chroma with metadata (domain, act, section, etc.)
- Called explicitly via `POST /api/v1/corpus/reindex`

### 3. LLM Integration (`backend/app/llm.py`)

```python
# GGUF model loaded via llama.cpp
Llama(model_path=settings.gguf_model_path, n_ctx=4096, n_gpu_layers=-1)

# Prompt enforces:
# - ONLY use supplied verified records
# - No hallucinated acts/sections/fees/deadlines
# - Max 170 words
# - Explicit "not available in verified sources" for missing details

# Citation validation (post-generation):
# - Every "section N" in answer must exist in retrieved passages
# - Every Act name in answer must be among retrieved acts
```

**Model:** `Qwen/Qwen3-4B-Instruct-2507` (Apache-2.0, non-gated) → converted to GGUF Q4_K_M (~2.5 GB)

### 4. Safety & Domain Routing (`backend/app/safety.py`)

**Crisis Detection** (escalates immediately, no generation):
- "arrested now", "police are arresting", "immediate danger", "domestic violence now", "unsafe at home"
- "court hearing tomorrow", "active court case", "case-specific strategy"

**Domain Classification** (keyword scoring):
| Domain | Keywords |
|--------|----------|
| consumer | consumer, refund, defective, product, seller, e-commerce, complaint, service, warranty, purchase |
| criminal | fir, police, arrest, bail, zero fir, complaint refused, offence, cognizable |
| family | marriage, married, dowry, domestic, wife, husband, registration, spouse |

---

## Data Pipeline

### Ingestion (`scripts/ingest_legal_pdfs.py`)

```
Input: Local PDF folder (G:\DO_TOUCH\Programmes\Legal_SLM_Dataset)
         │
         ▼
   PDF text extraction (pypdf)
         │
         ▼
   Section regex: ^\s*(\d+[A-Za-z]?(\([^)]+\))?)\.\s+(.{3,})
         │
         ▼
   Outputs:
   ├── corpus/legal_corpus_candidates.json     (1059 records, needs_review)
   ├── data/legal_dataset_manifest.json        (12 PDFs, 10 unique, 2 dupes)
   └── training/legal_training_candidates.jsonl (1059 instruction records)
```

**All automated extractions are marked `verification_status: "needs_review"`** — they are **never** used for answers until human approval.

### Validation Scripts

| Script | Purpose |
|--------|---------|
| `validate_corpus.py` | Checks required fields, domain enum, verification_status, non-empty section_text, duplicate IDs |
| `validate_training.py` | Validates JSONL: instruction/context/response/cited_sections, cited sections must appear in context |

---

## Frontend (`frontend/src/main.tsx`)

**Single-file React SPA** (~380 lines) with:
- Chat interface with textarea + submit
- Structured answer rendering: status badge, domain, confidence %
- **Guidance blocks**: explanation, legal_basis, authority, procedure, documents, forms, timeline, fees
- **Follow-up questions** when clarification needed
- **Citations panel** with act/section, excerpt, link to IndiaCode source
- **Disclaimer footer** + response mode indicator
- Responsive CSS (mobile-first, ~500px breakpoint)

**API Contract:** Expects `ChatResponse` schema from backend.

---

## Verified Corpus (`corpus/legal_corpus.json`)

| ID | Domain | Act | Section | Status |
|----|--------|-----|---------|--------|
| consumer-cpa-2-7 | consumer | Consumer Protection Act, 2019 | Section 2(7) | verified |
| consumer-cpa-35 | consumer | Consumer Protection Act, 2019 | Section 35 | verified |
| criminal-bnss-173 | criminal | Bharatiya Nagarik Suraksha Sanhita, 2023 | Section 173 | verified |
| criminal-bnss-482 | criminal | Bharatiya Nagarik Suraksha Sanhita, 2023 | Section 482 | verified |
| family-dowry-3 | family | Dowry Prohibition Act, 1961 | Section 3 | verified |
| family-hma-8 | family | Hindu Marriage Act, 1955 | Section 8 | verified |

**7 verified records** — minimal but sufficient for prototype demonstration.

---

## Test Coverage (`backend/app/test_api.py`)

```python
# 5 integration tests using FastAPI TestClient
test_consumer_response_has_retrieved_citation()  # CPA Section 35
test_criminal_response_is_cited()                # BNSS Section 173
test_family_response_is_cited()                  # Dowry Act Section 3
test_crisis_bypasses_generation()                # "domestic violence now" → escalated
test_out_of_scope_query_is_refused()             # "income tax return" → out_of_scope
```

Run: `pytest backend/app/test_api.py -v`

---

## Setup & Operations

### Prerequisites
- Python 3.11+ (venv at `G:\DO_TOUCH\Programmes\.dumpEnv`)
- Node.js + pnpm (for frontend)
- GGUF model at `G:\OllaMa\FH_Models\qwen3-4b-instruct-2507-q4_k_m.gguf` (see `models/README.md`)

### Quick Start
```bash
# 1. Backend deps
G:\DO_TOUCH\Programmes\.dumpEnv\Scripts\python.exe -m pip install -r backend/requirements.txt

# 2. Build index (after model downloaded)
G:\DO_TOUCH\Programmes\.dumpEnv\Scripts\python.exe scripts/reindex.py

# 3. Start API
G:\DO_TOUCH\Programmes\.dumpEnv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload

# 4. Frontend
pnpm --dir frontend install
pnpm --dir frontend dev
```

### Data Management Commands
```bash
# Ingest new PDFs (produces needs_review candidates)
python scripts/ingest_legal_pdfs.py --input G:\DO_TOUCH\Programmes\Legal_SLM_Dataset \
  --output-corpus corpus/legal_corpus_candidates.json \
  --output-manifest data/legal_dataset_manifest.json \
  --output-training-candidates training/legal_training_candidates.jsonl

# Generate dataset report
python scripts/report_legal_dataset.py --input G:\DO_TOUCH\Programmes\Legal_SLM_Dataset --output docs/legal_dataset_report.md

# Validate corpus / training data
python scripts/validate_corpus.py
python scripts/validate_training.py

# Rebuild Chroma index
python scripts/reindex.py
```

---

## Configuration (`backend/app/settings.py`)

```python
embedding_model: "sentence-transformers/all-MiniLM-L6-v2"
chroma_path: ROOT / "data" / "chroma"
corpus_path: ROOT / "corpus" / "legal_corpus.json"
gguf_model_path: "G:\\OllaMa\\FH_Models\\qwen3-4b-instruct-2507-q4_k_m.gguf"
top_k: 3
confidence_threshold: 0.40
```

---

## Safety & Privacy Guarantees

| Guarantee | Implementation |
|-----------|----------------|
| **No user tracking** | No accounts, no DB, no query logging |
| **Offline at runtime** | Only local files + localhost services |
| **Crisis escalation** | Immediate danger/active case → static safety message, no LLM |
| **Citation integrity** | LLM output rejected if it references unseen sections/acts |
| **Verified-only answers** | `needs_review` records excluded from retrieval |
| **Scope limitation** | Out-of-domain queries explicitly refused |

---

## Current Limitations & Future Work

### Limitations
1. **Tiny verified corpus** (7 records) — prototype only
2. **Lexical retrieval default** — semantic search requires manual `reindex.py`
3. **No conversation memory** — stateless per request
4. **Single GGUF model** — no model switching / quantization options
5. **No authentication/multi-user** — by design for hackathon

### Planned Enhancements
- [ ] Expand verified corpus to 200+ sections across 3 domains
- [ ] Add Chroma index to repo (or CI build step)
- [ ] Streaming responses via Server-Sent Events
- [ ] Conversation history + session context
- [ ] Optional QLoRA fine-tuning pipeline (see `train_qlora.py`)
- [ ] More granular domain classification (sub-topics)
- [ ] Export chat as PDF for user records

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM hallucination | Medium | High | Citation guard + verified-only retrieval + low confidence threshold |
| Outdated legal info | Medium | High | Corpus versioning, source_url to IndiaCode, manual review gate |
| Crisis misclassification | Low | Critical | Conservative keyword list, explicit escalation UX |
| Model unavailable | Medium | Medium | Graceful fallback to retrieval-only mode |
| Corpus poisoning | Low | High | `needs_review` default, human verification required |

---

## Appendix: Key File Reference

| File | Purpose |
|------|---------|
| `backend/app/main.py` | FastAPI routes, CORS, dependency injection |
| `backend/app/service.py` | Core orchestration, answer pipeline |
| `backend/app/retrieval.py` | Lexical + Chroma retrieval |
| `backend/app/llm.py` | GGUF inference + citation validation |
| `backend/app/safety.py` | Crisis detection, domain classification |
| `backend/app/schemas.py` | All Pydantic request/response models |
| `backend/app/settings.py` | Centralized configuration |
| `scripts/ingest_legal_pdfs.py` | PDF → section candidates (needs_review) |
| `scripts/reindex.py` | Chroma index build |
| `scripts/validate_corpus.py` | Corpus schema validation |
| `scripts/validate_training.py` | Instruction data validation |
| `scripts/train_qlora.py` | Optional QLoRA entry point (validates first) |
| `frontend/src/main.tsx` | React chat UI |
| `corpus/legal_corpus.json` | Production verified sources |
| `data/chroma/` | Persistent vector store |

---

## Conclusion

**Nyaya Sahayak** demonstrates a **production-grade RAG architecture** constrained to **local-only execution** with **strong safety guards**. The system prioritizes **correctness over coverage** — refusing to answer rather than hallucinating — making it suitable for high-stakes legal information scenarios where accuracy and user safety are paramount.

The modular design (separate retriever, LLM, safety, schemas) enables independent upgrades: swap embedding models, upgrade GGUF quantization, expand corpus domains, or add streaming — all without rewriting the orchestration layer.

**Status: Hackathon MVP — Functional, Tested, Ready for Corpus Expansion**