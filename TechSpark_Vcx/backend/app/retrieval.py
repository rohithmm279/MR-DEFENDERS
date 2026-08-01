from __future__ import annotations

import json
import re
import logging
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

from .schemas import SourceRecord

logger = logging.getLogger(__name__)


def load_corpus(path: Path) -> list[SourceRecord]:
    """Load corpus from JSON file, filtering out deprecated records."""
    if not path.exists():
        logger.warning(f"Corpus file not found: {path}")
        return []
    
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        records = []
        for item in data:
            # Skip deprecated records
            if item.get("verification_status") == "deprecated":
                continue
            try:
                records.append(SourceRecord.model_validate(item))
            except Exception as e:
                logger.warning(f"Invalid record in corpus: {e}")
        return records
    except Exception as e:
        logger.error(f"Failed to load corpus: {e}")
        return []


def _tokens(text: str) -> set[str]:
    """Normalize words and section numbers for deterministic local retrieval."""
    return set(re.findall(r"[a-zA-Z][a-zA-Z-]{2,}|\d+(?:\(\d+\))?", text.lower()))


class LocalRetriever:
    """
    Hybrid retrieval: lexical fallback + Chroma semantic search + optional cross-encoder reranking.
    
    Retrieval strategy:
    1. If Chroma index exists and has records → use semantic search
    2. Otherwise → use lexical fallback (deterministic, no embeddings)
    3. Optional: rerank top-k results with cross-encoder for better precision
    """
    
    def __init__(self, settings, records: list[SourceRecord] | None = None):
        self.settings = settings
        self.records = records if records is not None else load_corpus(settings.corpus_path)
        self._collection = None
        self._embedder = None
        self._reranker = None
        self._chroma_client = None
        
        # Auto-initialize Chroma if available
        self._init_chroma_if_available()
    
    def _init_chroma_if_available(self):
        """Initialize ChromaDB if installed and index exists."""
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            
            self._chroma_client = chromadb.PersistentClient(
                path=str(self.settings.chroma_path),
                settings=ChromaSettings(anonymized_telemetry=False)
            )
            
            # Check if collection exists
            try:
                self._collection = self._chroma_client.get_collection("legal_sections")
                logger.info(f"Chroma collection loaded with {self._collection.count()} records")
            except Exception:
                logger.warning("Chroma collection 'legal_sections' not found. Run reindex.py to build index.")
                self._collection = None
                
        except ImportError:
            logger.warning("ChromaDB not installed. Using lexical retrieval only.")
        except Exception as e:
            logger.warning(f"Failed to initialize ChromaDB: {e}")
    
    def _init_embedder(self):
        """Lazy-load embedding model."""
        if self._embedder is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer(
                    self.settings.embedding_model,
                    local_files_only=True
                )
                logger.info(f"Embedding model loaded: {self.settings.embedding_model}")
            except Exception as e:
                logger.warning(f"Failed to load embedding model: {e}")
                return None
        return self._embedder
    
    def _init_reranker(self):
        """Lazy-load cross-encoder reranker."""
        if self._reranker is None:
            try:
                from sentence_transformers import CrossEncoder
                # Use a lightweight cross-encoder for reranking
                self._reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
                logger.info("Cross-encoder reranker loaded")
            except Exception as e:
                logger.warning(f"Failed to load reranker: {e}")
                return None
        return self._reranker
    
    def record_count(self) -> int:
        return len(self.records)
    
    def verified_count(self) -> int:
        return sum(1 for r in self.records if r.verification_status == "verified")
    
    def retrieve(
        self, 
        query: str, 
        domain: str, 
        top_k: int | None = None,
        use_reranking: bool | None = None
    ) -> list[tuple[SourceRecord, float]]:
        """
        Retrieve relevant records for query.
        
        Args:
            query: User query
            domain: Legal domain filter
            top_k: Number of results (defaults to settings.top_k)
            use_reranking: Whether to apply cross-encoder reranking
        
        Returns:
            List of (record, score) tuples sorted by score descending
        """
        top_k = top_k or self.settings.top_k
        if use_reranking is None:
            use_reranking = self.settings.enable_reranker
        
        # Filter candidates by domain and verification status
        candidates = [
            record for record in self.records 
            if record.domain == domain and record.verification_status == "verified"
        ]
        
        if not candidates:
            logger.warning(f"No verified records found for domain: {domain}")
            return []
        
        # Run both paths. A weak semantic match must not suppress a stronger
        # exact-term match, especially for short legal questions.
        semantic_results = self._semantic_retrieve(query, domain, candidates, top_k)
        lexical_results = self._lexical_retrieve(query, candidates, top_k)
        if not semantic_results:
            logger.info("Falling back to lexical retrieval")
            results = lexical_results
        elif not lexical_results:
            results = semantic_results
        else:
            semantic_score = semantic_results[0][1]
            lexical_score = lexical_results[0][1]
            results = lexical_results if lexical_score > semantic_score + 0.05 else semantic_results
        
        # Apply reranking if enabled and we have enough results
        if use_reranking and results and len(results) > 1:
            results = self._rerank_results(query, results, top_k)
        
        return results
    
    def _semantic_retrieve(
        self, 
        query: str, 
        domain: str,
        candidates: list[SourceRecord],
        top_k: int
    ) -> list[tuple[SourceRecord, float]]:
        """Retrieve using ChromaDB semantic search."""
        if not self._collection:
            return []
        
        embedder = self._init_embedder()
        if not embedder:
            return []
        
        try:
            # Encode query
            query_embedding = embedder.encode([query], normalize_embeddings=True).tolist()[0]
            
            # Query Chroma
            chroma_results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k * 2, len(candidates)),  # Get more for reranking
                where={"domain": domain},
                include=["metadatas", "distances"]
            )
            
            # Map back to SourceRecord objects
            results = []
            if chroma_results and chroma_results.get("metadatas"):
                ids = (chroma_results.get("ids") or [[]])[0]
                for i, metadata in enumerate(chroma_results["metadatas"][0]):
                    record_id = metadata.get("id") or (ids[i] if i < len(ids) else None)
                    # Find matching record
                    for record in candidates:
                        if record.id == record_id:
                            distance = chroma_results["distances"][0][i] if chroma_results.get("distances") else 0.5
                            # Convert distance to similarity score (Chroma returns L2 distance)
                            score = max(0.0, 1.0 - distance)
                            results.append((record, score))
                            break
            
            return results
            
        except Exception as e:
            logger.error(f"Semantic retrieval failed: {e}")
            return []
    
    def _lexical_retrieve(
        self, 
        query: str, 
        candidates: list[SourceRecord],
        top_k: int
    ) -> list[tuple[SourceRecord, float]]:
        """Fallback lexical retrieval using token overlap."""
        query_terms = _tokens(query)
        
        if not query_terms:
            return []
        
        ranked = []
        for record in candidates:
            searchable = " ".join(
                value for value in (
                    record.section_text, record.act_name, record.section_number,
                    record.authority, record.procedure, " ".join(record.documents),
                    " ".join(record.forms), record.fees, record.timeline,
                ) if value
            )
            text_terms = _tokens(searchable)
            
            # Calculate overlap score
            overlap = len(query_terms & text_terms)
            
            # Bonus for exact section number match
            exact_section = any(
                token in text_terms 
                for token in query_terms 
                if token.isdigit() or "(" in token
            )
            
            # Normalized score
            score = min(1.0, (overlap + 1 + (1 if exact_section else 0)) / (min(len(query_terms), 4) + 1))
            ranked.append((record, score))
        
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[:top_k]
    
    def _rerank_results(
        self, 
        query: str, 
        results: list[tuple[SourceRecord, float]],
        top_k: int
    ) -> list[tuple[SourceRecord, float]]:
        """Rerank results using cross-encoder."""
        reranker = self._init_reranker()
        if not reranker or len(results) < 2:
            return results
        
        try:
            # Prepare pairs for reranking
            pairs = [
                [query, f"{record.act_name} {record.section_number}: {record.section_text}"]
                for record, _ in results
            ]
            
            # Get reranking scores
            rerank_scores = reranker.predict(pairs)
            
            # Combine with original scores (weighted average)
            reranked = []
            for i, (record, orig_score) in enumerate(results):
                # Weight: 70% reranker, 30% original
                combined_score = 0.7 * rerank_scores[i] + 0.3 * orig_score
                reranked.append((record, combined_score))
            
            reranked.sort(key=lambda item: item[1], reverse=True)
            return reranked[:top_k]
            
        except Exception as e:
            logger.warning(f"Reranking failed: {e}")
            return results
    
    def reindex(self) -> int:
        """
        Build or rebuild Chroma index from verified corpus.
        Returns number of records indexed.
        """
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise RuntimeError("Install chromadb and sentence-transformers before indexing.") from error
        
        # Filter to verified records only
        verified_records = [r for r in self.records if r.verification_status == "verified"]
        
        if not verified_records:
            raise RuntimeError("No verified records to index. Review candidates first.")
        
        logger.info(f"Indexing {len(verified_records)} verified records...")
        
        # Load embedder
        embedder = SentenceTransformer(self.settings.embedding_model, local_files_only=False)
        
        # Initialize Chroma client
        self._chroma_client = chromadb.PersistentClient(
            path=str(self.settings.chroma_path),
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        
        # Delete existing collection
        try:
            self._chroma_client.delete_collection("legal_sections")
            logger.info("Deleted existing collection")
        except Exception:
            pass
        
        # Create new collection
        self._collection = self._chroma_client.create_collection(
            "legal_sections",
            metadata={"embedding_model": self.settings.embedding_model}
        )
        
        # Generate embeddings in batches
        batch_size = 32
        texts = [record.section_text for record in verified_records]
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_records = verified_records[i:i + batch_size]
            
            embeddings = embedder.encode(batch_texts, normalize_embeddings=True).tolist()
            
            # Prepare metadata
            metadatas = []
            for record in batch_records:
                raw = record.model_dump(exclude={"section_text", "id", "source_url"}) | {"source_url": record.source_url}
                # Filter out None/empty values
                metadata = {
                    key: value for key, value in raw.items() 
                    if value not in (None, "", [])
                }
                metadatas.append(metadata)
            
            # Add to collection
            self._collection.add(
                ids=[record.id for record in batch_records],
                documents=[record.section_text for record in batch_records],
                embeddings=embeddings,
                metadatas=metadatas,
            )
        
        logger.info(f"Indexed {len(verified_records)} records to Chroma")
        self.records = verified_records
        return len(verified_records)
