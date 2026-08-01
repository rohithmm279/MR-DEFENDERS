from __future__ import annotations

import os
from pathlib import Path
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_project_root() -> Path:
    """Get project root, works from any working directory."""
    return Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Project paths
    project_root: Path = Field(default_factory=get_project_root)
    
    # Model settings
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    gguf_model_path: Path = Field(
        default_factory=lambda: Path(os.getenv(
            "NYAYA_GGUF_MODEL_PATH",
            r"G:\OllaMa\FH_Models\qwen3-4b-instruct-2507-q4_k_m.gguf",
        ))
    )
    
    # Data paths
    chroma_path: Path = Field(default_factory=lambda: get_project_root() / "data" / "chroma")
    corpus_path: Path = Field(default_factory=lambda: get_project_root() / "corpus" / "legal_corpus.json")
    candidates_path: Path = Field(default_factory=lambda: get_project_root() / "corpus" / "legal_corpus_candidates.json")
    training_data_path: Path = Field(default_factory=lambda: get_project_root() / "training" / "legal_training_candidates.jsonl")
    
    # Retrieval settings
    top_k: int = 5
    confidence_threshold: float = 0.35
    rerank_top_k: int = 10
    enable_reranker: bool = False
    
    # LLM settings
    max_tokens: int = 512
    temperature: float = 0.1
    top_p: float = 0.9
    n_ctx: int = 4096
    n_gpu_layers: int = -1
    
    # Safety settings
    enable_crisis_detection: bool = True
    enable_statutory_mapping: bool = True
    
    # Logging
    log_level: str = "INFO"
    log_queries: bool = False


settings = Settings()
