from __future__ import annotations

import re
import logging
from functools import lru_cache
from pathlib import Path

from .schemas import SourceRecord
from .settings import Settings

logger = logging.getLogger(__name__)


class LocalLlama:
    """Local GGUF inference adapter using llama.cpp with strict anti-hallucination guardrails."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._llm_instance = None

    def _get_model(self):
        """Lazy load and cache llama_cpp Llama instance."""
        if self._llm_instance is not None:
            return self._llm_instance

        if not self.settings.gguf_model_path.exists():
            logger.warning(f"GGUF model path does not exist: {self.settings.gguf_model_path}")
            return None

        try:
            from llama_cpp import Llama
            logger.info(f"Loading GGUF model from {self.settings.gguf_model_path}...")
            self._llm_instance = Llama(
                model_path=str(self.settings.gguf_model_path),
                n_ctx=self.settings.n_ctx,
                n_gpu_layers=self.settings.n_gpu_layers,
                verbose=False,
            )
            logger.info("GGUF model loaded successfully.")
            return self._llm_instance
        except Exception as err:
            logger.error(f"Failed to load Llama model: {err}")
            return None

    def generate(self, query: str, passages: list[SourceRecord]) -> str | None:
        """Generate grounded answer strictly conditioned on retrieved passages."""
        model = self._get_model()
        if model is None or not passages:
            return None

        context_blocks = []
        for p in passages:
            block = f"[{p.act_name}, {p.section_number}]\n{p.section_text}"
            if p.procedure:
                block += f"\nProcedure: {p.procedure}"
            if p.documents:
                block += f"\nRequired Documents: {', '.join(p.documents)}"
            if p.authority:
                block += f"\nAuthority: {p.authority}"
            context_blocks.append(block)

        context = "\n\n".join(context_blocks)
        prompt = f"""You are Nyaya Sahayak, a cautious Indian legal-information assistant.
Answer the user's question in plain, clear English using ONLY the supplied verified legal records.

RULES:
1. Select only the sections that are directly useful for this question.
2. Do not provide case-specific advice or act as a licensed advocate.
3. Do NOT add any Act, section, case, fact, deadline, fee, authority, form, or document that is absent from the verified records.
4. If a requested detail is absent from the records, explicitly state: 'This detail is not available in the verified local sources.'
5. Include section citations in your text (e.g., 'Under Section 35 of the Consumer Protection Act, 2019...').

User Question: {query}

Verified Legal Records:
{context}

Answer (concise, max 200 words):"""

        try:
            output = model.create_completion(
                prompt,
                max_tokens=self.settings.max_tokens,
                temperature=self.settings.temperature,
                top_p=self.settings.top_p,
                stop=["User Question:", "\n\n\n"],
            )
            answer = output["choices"][0]["text"].strip()
        except Exception as exc:
            logger.error(f"LLM generation failed: {exc}")
            return None

        if answer and self.citations_are_allowed(answer, passages):
            return answer

        logger.warning("LLM generated answer rejected due to ungrounded citations or empty response.")
        return None

    @staticmethod
    def citations_are_allowed(answer: str, passages: list[SourceRecord]) -> bool:
        """Verify that all cited sections and acts in the generated answer match retrieved passages."""
        allowed_sections = {
            p.section_number.lower().replace(" ", "").replace("section", "")
            for p in passages
        }
        allowed_acts = {p.act_name.lower() for p in passages}

        # Find mentioned section numbers
        mentioned_sections = {
            num.lower().replace(" ", "")
            for num in re.findall(r"section\s+(\d+[A-Za-z]?(?:\(\d+\))?)", answer, flags=re.IGNORECASE)
        }

        # Check if mentioned sections are subset of allowed sections
        for sec in mentioned_sections:
            if not any(sec in allowed or allowed in sec for allowed in allowed_sections):
                logger.warning(f"Citation mismatch: Section '{sec}' not in allowed passages.")
                return False

        # Check mentioned Acts
        mentioned_acts = re.findall(r"(?:the\s+)?([A-Z][A-Za-z0-9\s,]+Act,?\s*\d{4})", answer)
        for act in mentioned_acts:
            act_clean = act.lower().strip()
            if not any(act_clean in allowed for allowed in allowed_acts):
                logger.warning(f"Citation mismatch: Act '{act}' not in allowed passages.")
                return False

        return True

