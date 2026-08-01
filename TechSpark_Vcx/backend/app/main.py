from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .schemas import ChatRequest, ChatResponse, HealthResponse
from .service import LegalAssistantService
from .settings import settings

app = FastAPI(title="Nyaya Sahayak Local API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"], allow_methods=["*"], allow_headers=["*"], allow_credentials=False)
service = LegalAssistantService(settings)


@app.get("/api/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    count = service.retriever.record_count()
    model_ready = service.model_ready()
    verified = service.retriever.verified_count()
    collection_exists = service.retriever._collection is not None
    gpu_available = False
    try:
        import torch
        gpu_available = bool(torch.cuda.is_available())
    except Exception:
        pass
    return HealthResponse(
        status="ready" if count and verified else "degraded",
        embedding_model=settings.embedding_model,
        vector_store=str(settings.chroma_path),
        local_model_ready=model_ready,
        corpus_records=count,
        verified_records=verified,
        chroma_collection_exists=collection_exists,
        gpu_available=gpu_available,
    )


@app.post("/api/v1/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    return service.answer(payload)


@app.post("/api/v1/corpus/reindex")
def reindex() -> dict[str, int | str]:
    try:
        count = service.retriever.reindex()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {"status": "indexed", "records": count}


@app.get("/api/v1/sources/{source_id}")
def source(source_id: str) -> dict:
    for record in service.retriever.records:
        if record.id == source_id:
            return record.model_dump()
    raise HTTPException(status_code=404, detail="Source not found")
