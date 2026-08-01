# SRS Compliance Gap Analysis - Nyaya Sahayak

## SRS Requirements vs Current Implementation

### ✅ FULLY IMPLEMENTED (Meeting SRS)

| SRS ID | Requirement | Status | Implementation |
|--------|-------------|--------|----------------|
| FR-1 | Accept natural-language query via text input | ✅ Done | `main.tsx` textarea + `POST /api/v1/chat` |
| FR-3 | Classify query into 3 domains or out-of-scope | ✅ Done | `safety.py:classify_domain()` keyword scoring |
| FR-4 | Route classified query to domain-specific index | ✅ Done | `retrieval.py` filters by `domain` field |
| FR-5 | Consumer rights under CPA 2019 | ✅ Partial | 2 verified records in corpus |
| FR-6 | Step-by-step filing guidance for District Forum | ✅ Partial | Service returns `steps` from `procedure` field |
| FR-7 | Cite specific Act and section | ✅ Done | `citations` array in response, `legal_basis` block |
| FR-8 | FIR filing, Zero FIR, refusal remedies | ✅ Partial | 2 BNSS records in corpus |
| FR-9 | Bailable/non-bailable, anticipatory bail concepts | ❌ Missing | No content in corpus for this |
| FR-10 | Mandatory criminal lawyer disclaimer | ✅ Done | `DISCLAIMER` constant + in every response |
| FR-11 | Marriage registration process & documents | ❌ Missing | Only HMA Section 8 in corpus |
| FR-12 | Dowry Prohibition Act protections & reporting | ✅ Partial | 1 record (Section 3) |
| FR-13 | Domestic violence → helpline escalation | ✅ Done | `assess_safety()` detects crisis keywords |
| FR-14 | Retrieve top-k from domain vector store | ✅ Done | `LocalRetriever.retrieve()` with `top_k=3` |
| FR-15 | Generate answer with fine-tuned local SLM | ⚠️ Partial | Uses base Qwen3-4B GGUF, not fine-tuned |
| FR-16 | No Act/section/case not in retrieved corpus | ✅ Done | `citations_are_allowed()` validation in `llm.py` |
| FR-17 | Numbered checklist: docs, authority, timeline, fees | ✅ Partial | Fields exist in schema, but few verified records populate them |
| FR-18 | Follow-up questions without losing context | ⚠️ Partial | `follow_up_questions` returned, but no conversation memory |
| FR-19 | Display source Act & Section for every claim | ✅ Done | Citations in response blocks |
| FR-20 | Confidence indicator + professional consultation | ✅ Done | `confidence` field + `low_confidence` status |
| FR-21 | Persistent disclaimer | ✅ Done | `DISCLAIMER` in footer + every response |
| FR-22 | Detect high-stakes queries → escalation | ✅ Done | `assess_safety()` for arrest/active case |

---

### ❌ NOT IMPLEMENTED / MAJOR GAPS

| SRS ID | Requirement | Gap Description | Priority |
|--------|-------------|-----------------|----------|
| FR-2 | Speech-to-text input | No STT module implemented | Medium |
| FR-9 | Bailable/non-bailable concepts | No corpus content for criminal concepts | High |
| FR-11 | Marriage registration process | Missing SMA 1954, state rules, documents | High |
| FR-15 | Fine-tuned SLM (QLoRA) | Using base model only; `train_qlora.py` is stub | High |
| FR-18 | Conversation context for follow-ups | Stateless API - no session memory | Medium |
| NFR-1 | ≤10s latency on 6GB GPU | Not measured; sync blocking may exceed | Medium |
| NFR-3 | Opt-in query logging | No logging infrastructure | Low |
| NFR-7 | Modular pipeline for new domains | Hardcoded 3 domains in multiple files | Medium |
| NFR-8 | Add domains without code changes | Domain enum in schemas, safety, retrieval | Medium |
| Phase 2 | QLoRA fine-tuning pipeline | `train_qlora.py` raises SystemExit | High |
| Phase 3 | Speech-to-text conversion | No implementation | Medium |
| Phase 4 | Anti-hallucination guardrails | Only citation check; no factual verification | High |

---

### ⚠️ PARTIALLY IMPLEMENTED - NEEDS PRODUCTION HARDENING

| Area | Issues |
|------|--------|
| **Corpus** | Only 7 verified records vs SRS target of comprehensive coverage; 1059 `needs_review` candidates unprocessed |
| **Retrieval** | Lexical fallback is default; Chroma index not built by default; score threshold uncalibrated (0.40) |
| **LLM** | Base model only; no structured output enforcement; no factual verification beyond citation check |
| **Safety** | Keyword-based crisis detection is brittle; no semantic intent classification |
| **Schema** | `SourceRecord` missing: `effective_date`, `source_hash` validation; `verification_status` not enforced at retrieval |
| **Tests** | Only 5 integration tests; no unit tests for retrieval, safety, citation validation |
| **Frontend** | No accessibility (ARIA); no loading states for citations; no keyboard navigation; single-file component |
| **Config** | Hardcoded Windows paths in `settings.py`; model path not configurable via env |

---

## Required Materials & Datasets for Production

### 1. Verified Legal Corpus (Target: 200+ records)
- **Current**: 7 verified, 1059 needs_review
- **Need**: Human review of candidates → verified corpus
- **Priority domains**: 
  - Consumer: CPA 2019 full (Sections 2, 35, 36-71, 83-102)
  - Criminal: BNSS 2023 (FIR: 173, 175; Bail: 482, 483, 438-440; Zero FIR)
  - Family: Dowry Act full, HMA 1955 (Sec 5, 7, 8), SMA 1954, DV Act 2005

### 2. Fine-Tuning Dataset (Target: 200-500 pairs)
- **Schema**: instruction, context, response, cited_sections
- **Current**: 1059 `needs_review` candidates in `training/legal_training_candidates.jsonl`
- **Need**: Human-curated gold standard with proper responses

### 3. Embedding Model
- **Current**: `sentence-transformers/all-MiniLM-L6-v2` (384-dim)
- **Production**: Consider `BAAI/bge-small-en-v1.5` or `jinaai/jina-embeddings-v2-small-en` for better legal retrieval

### 4. Local SLM Model
- **Current**: Qwen3-4B-Instruct-2507 GGUF Q4_K_M (~2.5GB)
- **SRS**: Phi-3.5-mini / Llama-3.2-4B / Gemma-2-2B with QLoRA
- **Need**: Fine-tuned adapter (~100-200MB) on base model

### 5. Speech-to-Text (Optional per FR-2)
- **Options**: Whisper.cpp (local), Vosk, faster-whisper
- **Integration**: Frontend audio capture → backend STT endpoint

### 6. Infrastructure
- ChromaDB persistent index (pre-built)
- GPU inference optimization (llama.cpp batching, KV cache)
- Health monitoring & metrics

---

## Code Corrections Required

### Backend (`backend/app/`)
1. **`settings.py`** - Add env var support, remove hardcoded Windows paths
2. **`schemas.py`** - Add `effective_date`, `state_rules_url`; make domain extensible
3. **`safety.py`** - Upgrade crisis detection; add statutory transition mapping
4. **`retrieval.py`** - Build Chroma index on startup; add cross-encoder reranking; calibrate threshold
5. **`llm.py`** - Add structured output (JSON mode); factual verification; streaming support
6. **`service.py`** - Add conversation memory; follow-up context; async generation
7. **`main.py`** - Add `/chat/stream` endpoint; request logging; metrics
8. **`test_api.py`** - Expand coverage: retrieval, safety, citation validation, edge cases

### Scripts (`scripts/`)
1. **`ingest_legal_pdfs.py`** - Improve PDF parsing (tables, schedules); add section hierarchy
2. **`validate_corpus.py`** - Add semantic deduplication; cross-reference India Code URLs
3. **`train_qlora.py`** - Implement actual QLoRA training loop with PEFT/TRL
4. **`split_training_data.py`** - Add train/val/test split with domain stratification
5. **`reindex.py`** - Add incremental indexing; metadata filtering options

### Frontend (`frontend/src/`)
1. **Componentize** - Split into Chat, Message, Citations, Steps, FollowUp components
2. **Accessibility** - ARIA labels, keyboard nav, screen reader support
3. **Speech Input** - MediaRecorder + Web Speech API integration
4. **Streaming** - SSE support for token-by-token display
5. **State Management** - Conversation history, session persistence

---

## Implementation Sequence

### Phase A: Core Hardening (Week 1)
1. Fix settings/config management
2. Make domain system extensible
3. Build Chroma index by default
4. Expand test coverage to 80%+

### Phase B: Corpus Expansion (Week 1-2)
1. Review & verify top 50 candidate records per domain
2. Add missing critical sections (bail concepts, marriage registration, SMA)
3. Build verified corpus to 100+ records

### Phase C: RAG Pipeline Upgrade (Week 2)
1. Add cross-encoder reranking
2. Implement factual verification in LLM output
3. Add conversation context for follow-ups
4. Optimize retrieval latency

### Phase D: Fine-Tuning Pipeline (Week 2-3)
1. Implement working `train_qlora.py`
2. Curate 200 gold-standard instruction pairs
3. Train and evaluate adapter
4. Integrate fine-tuned model

### Phase E: Frontend & UX (Week 3)
1. Componentize React app
2. Add accessibility
3. Implement speech-to-text (optional)
4. Add streaming response UI

### Phase F: Production Readiness (Week 3-4)
1. End-to-end integration testing
2. Latency benchmarking & optimization
3. Documentation & deployment scripts
4. Demo preparation