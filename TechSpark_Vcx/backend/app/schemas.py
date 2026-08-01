from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator
from datetime import date


# Extensible domain system - add new domains here
Domain = Literal["consumer", "criminal", "family", "property", "labour", "rti"]

# Statutory transition mappings (Old → New laws effective July 1, 2024)
STATUTORY_TRANSITIONS = {
    "criminal": {
        "old_to_new": {
            "IPC": "BNS",
            "CrPC": "BNSS", 
            "IEA": "BSA",
        },
        "section_mapping": {
            # IPC → BNS examples
            ("IPC", "498A"): ("BNS", "85"),  # Cruelty by husband
            ("IPC", "304B"): ("BNS", "106"),  # Dowry death
            ("IPC", "376"): ("BNS", "64"),    # Rape
            # CrPC → BNSS examples  
            ("CrPC", "154"): ("BNSS", "173"),  # FIR
            ("CrPC", "437"): ("BNSS", "482"),  # Bail
            ("CrPC", "438"): ("BNSS", "483"),  # Anticipatory bail
        }
    }
}


class SourceRecord(BaseModel):
    id: str
    domain: Domain
    act_name: str
    section_number: str
    section_text: str = Field(min_length=1)
    jurisdiction: str = "India - Central"
    source_url: str = ""
    authority: str | None = None
    procedure: str | None = None
    documents: list[str] = []
    forms: list[str] = []
    fees: str | None = None
    timeline: str | None = None
    source_type: Literal["statute", "rule", "official_procedure", "form", "case_summary", "guideline"] = "statute"
    verification_status: Literal["verified", "needs_review", "deprecated"] = "verified"
    effective_date: str | None = None
    source_file: str | None = None
    source_hash: str | None = None
    state_rules_url: str | None = None
    old_law_reference: str | None = None  # For transitional mapping (e.g., "Section 154 CrPC")
    
    @field_validator("source_url")
    @classmethod
    def validate_india_code_url(cls, v: str) -> str:
        if v and not v.startswith(("http://", "https://", "")):
            raise ValueError("source_url must be a valid URL or empty")
        return v
    
    model_config = {"json_schema_extra": {"required": ["id", "domain", "act_name", "section_number", "section_text"]}}


class Citation(BaseModel):
    id: str
    act_name: str
    section_number: str
    source_url: str
    excerpt: str
    jurisdiction: str | None = None
    is_transitioned: bool = False  # True if this is a new law replacing old reference
    old_reference: str | None = None  # e.g., "Section 154 CrPC"


BlockType = Literal[
    "explanation", "legal_basis", "authority", "procedure", "documents",
    "forms", "timeline", "fees", "warning", "sources", "follow_up", "statutory_transition",
]


class ResponseBlock(BaseModel):
    type: BlockType
    title: str
    content: str | list[str]
    citation_ids: list[str] = []
    severity: Literal["info", "warning", "critical"] = "info"


class FollowUpQuestion(BaseModel):
    id: str
    question: str
    reason: str
    suggested_queries: list[str] = []  # Help user rephrase


class ChatRequest(BaseModel):
    query: str = Field(min_length=3, max_length=2000)
    session_id: str | None = Field(default=None, max_length=100)
    domain_override: Domain | None = None  # Allow expert users to skip classification
    include_old_law_mapping: bool = True  # Request transitional info


class ChatResponse(BaseModel):
    status: Literal["answered", "escalated", "out_of_scope", "low_confidence", "model_unavailable"]
    domain: Domain | None = None
    answer: str
    steps: list[str] = []
    citations: list[Citation] = []
    confidence: float = Field(ge=0, le=1)
    disclaimer: str
    model_mode: Literal["local_llama", "retrieval_safe_fallback", "none"]
    blocks: list[ResponseBlock] = []
    follow_up_questions: list[FollowUpQuestion] = []
    needs_clarification: bool = False
    statutory_transition: dict | None = None  # Old → new law mapping if applicable
    reading_time_seconds: int | None = None  # Estimated reading time
    response_generated_at: str | None = None  # ISO timestamp


class HealthResponse(BaseModel):
    status: Literal["ready", "degraded", "unavailable"]
    embedding_model: str
    vector_store: str
    local_model_ready: bool
    corpus_records: int
    verified_records: int
    chroma_collection_exists: bool
    gpu_available: bool = False
    version: str = "0.2.0"


class CrisisResource(BaseModel):
    """Emergency contact resources for crisis escalation."""
    name: str
    phone: str
    description: str
    available_hours: str = "24/7"
    languages: list[str] = ["English", "Hindi"]


CRISIS_RESOURCES: dict[str, list[CrisisResource]] = {
    "domestic_violence": [
        CrisisResource(
            name="National Women's Helpline",
            phone="181",
            description="24/7 helpline for women in distress",
        ),
        CrisisResource(
            name="Emergency Services",
            phone="112",
            description="Pan-India emergency number",
        ),
    ],
    "legal_aid": [
        CrisisResource(
            name="NALSA Legal Aid",
            phone="15100",
            description="Free legal aid services",
        ),
    ],
}
