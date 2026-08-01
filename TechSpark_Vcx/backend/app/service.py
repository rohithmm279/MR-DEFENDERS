from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from .llm import LocalLlama
from .retrieval import LocalRetriever
from .safety import (
    CRISIS_MESSAGE,
    DISCLAIMER,
    assess_safety,
    classify_domain,
    get_statutory_transition,
)
from .schemas import (
    ChatRequest,
    ChatResponse,
    Citation,
    FollowUpQuestion,
    ResponseBlock,
    SourceRecord,
)
from .settings import Settings

logger = logging.getLogger(__name__)


class LegalAssistantService:
    def __init__(self, settings: Settings, retriever: LocalRetriever | None = None):
        self.settings = settings
        self.retriever = retriever or LocalRetriever(settings)
        self.llm = LocalLlama(settings)

    def model_ready(self) -> bool:
        return self.settings.gguf_model_path.exists()

    def answer(self, payload: ChatRequest | str) -> ChatResponse:
        # Normalize request payload
        if isinstance(payload, str):
            query = payload
            domain_override = None
            include_old_law = True
        else:
            query = payload.query
            domain_override = payload.domain_override
            include_old_law = payload.include_old_law_mapping

        # 1. Crisis & Safety Assessment
        safety = assess_safety(query, self.settings.enable_crisis_detection)
        if safety.escalate:
            blocks = [
                ResponseBlock(
                    type="warning",
                    title="Urgent Support Required",
                    content=CRISIS_MESSAGE,
                    severity="critical",
                )
            ]
            if safety.resources:
                resource_lines = [
                    f"• {r.name} ({r.phone}): {r.description} [{r.available_hours}]"
                    for r in safety.resources
                ]
                blocks.append(
                    ResponseBlock(
                        type="authority",
                        title="Verified Helpline Resources",
                        content=resource_lines,
                        severity="warning",
                    )
                )

            return ChatResponse(
                status="escalated",
                answer=CRISIS_MESSAGE,
                confidence=1.0,
                disclaimer=DISCLAIMER,
                model_mode="none",
                blocks=blocks,
                response_generated_at=datetime.now(timezone.utc).isoformat(),
            )

        # 2. Domain Classification
        if domain_override:
            domain = domain_override
        else:
            domain, domain_scores = classify_domain(query)

        if domain is None:
            message = (
                "I can help with consumer complaints, basic FIR/bail procedure, marriage or dowry law, "
                "property/tenancy basics, labour wages, and RTI filing. Please rephrase your query within these supported areas."
            )
            return ChatResponse(
                status="out_of_scope",
                answer=message,
                confidence=0.0,
                disclaimer=DISCLAIMER,
                model_mode="none",
                blocks=[
                    ResponseBlock(
                        type="warning",
                        title="Outside Supported Scope",
                        content=message,
                        severity="info",
                    )
                ],
                response_generated_at=datetime.now(timezone.utc).isoformat(),
            )

        # 3. Follow-Up Clarification Check
        follow_ups = self._follow_ups(query, domain)
        if follow_ups:
            message = "I need a little more detail to accurately identify the relevant statutory provision and authority."
            return ChatResponse(
                status="low_confidence",
                domain=domain,
                answer=message,
                confidence=0.0,
                disclaimer=DISCLAIMER,
                model_mode="none",
                blocks=[
                    ResponseBlock(
                        type="follow_up",
                        title="Clarification Needed",
                        content=[item.question for item in follow_ups],
                        severity="info",
                    )
                ],
                follow_up_questions=follow_ups,
                needs_clarification=True,
                response_generated_at=datetime.now(timezone.utc).isoformat(),
            )

        # 4. Context Retrieval
        results = self.retriever.retrieve(query, domain)
        if not results or results[0][1] < self.settings.confidence_threshold:
            message = (
                "I cannot answer this query confidently from the verified local legal corpus. "
                "Please consult a qualified legal professional or a official legal-aid authority."
            )
            return ChatResponse(
                status="low_confidence",
                domain=domain,
                answer=message,
                confidence=results[0][1] if results else 0.0,
                disclaimer=DISCLAIMER,
                model_mode="none",
                blocks=[
                    ResponseBlock(
                        type="warning",
                        title="Insufficient Verified Corpus Evidence",
                        content=message,
                        severity="warning",
                    )
                ],
                response_generated_at=datetime.now(timezone.utc).isoformat(),
            )

        # 5. Statutory Transition Analysis (Old → New Laws, e.g. IPC to BNS)
        transition_info = None
        if include_old_law and self.settings.enable_statutory_mapping:
            transition_info = get_statutory_transition(domain, query)

        # 6. Citations & Primary Material Setup
        primary_record, top_score = results[0]
        # Do not display unrelated top-k records as sources. Keep records close
        # to the primary match; the LLM may still use the full retrieved context.
        citation_results = [
            item for index, item in enumerate(results)
            if index == 0 or item[1] >= top_score - 0.10
        ][:3]
        citations = [
            Citation(
                id=r.id,
                act_name=r.act_name,
                section_number=r.section_number,
                source_url=r.source_url,
                excerpt=r.section_text[:280] + ("..." if len(r.section_text) > 280 else ""),
                jurisdiction=r.jurisdiction,
            )
            for r, _ in citation_results
        ]
        # 7. LLM Response Generation with Retrieval Fallback
        generated = self.llm.generate(query, [record for record, _ in results])
        answer_text = (
            generated
            or f"Based on verified statutory text under {primary_record.act_name} ({primary_record.section_number}): {primary_record.section_text}"
        )
        model_mode = "local_llama" if generated else "retrieval_safe_fallback"

        # 8. Assemble Structural Response Blocks
        steps = self._procedural_checklist(primary_record)
        blocks = self._build_blocks(answer_text, primary_record, citations, transition_info)

        # Reading time estimate (avg 200 words per minute)
        word_count = len(answer_text.split())
        reading_time_sec = max(5, int((word_count / 200.0) * 60))

        return ChatResponse(
            status="answered",
            domain=domain,
            answer=answer_text,
            steps=steps,
            citations=citations,
            confidence=self._calibrated_confidence(top_score, primary_record),
            disclaimer=DISCLAIMER,
            model_mode=model_mode,
            blocks=blocks,
            statutory_transition=transition_info,
            reading_time_seconds=reading_time_sec,
            response_generated_at=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def _follow_ups(query: str, domain: str) -> list[FollowUpQuestion]:
        text = query.lower()
        words = text.split()
        if len(words) <= 3:
            return [
                FollowUpQuestion(
                    id="facts",
                    question="Could you describe the specific situation or outcome you are seeking?",
                    reason="The system requires a clear fact pattern to retrieve relevant statutory provisions.",
                    suggested_queries=[
                        "How do I file a complaint for a defective product?",
                        "What is the procedure to register an FIR?",
                        "What documents are required for marriage registration?",
                    ],
                )
            ]
        if domain == "consumer" and not any(
            w in text for w in ("product", "service", "seller", "refund", "defect", "complaint", "warranty", "e-commerce")
        ):
            return [
                FollowUpQuestion(
                    id="transaction",
                    question="Is this issue related to a defective product, service deficiency, or seller refund refusal?",
                    reason="Specifying product vs service helps pinpoint the relevant Consumer Protection Act section.",
                )
            ]
        if domain == "criminal" and not any(w in text for w in ("bail", "fir", "police", "arrest", "complaint", "cognizable")):
            return [
                FollowUpQuestion(
                    id="procedure",
                    question="Are you inquiring about filing an FIR, police refusal to register a complaint, or bail provisions?",
                    reason="FIR, refusal remedies, and bail operate under distinct sections of BNSS 2023.",
                )
            ]
        return []

    @staticmethod
    def _build_blocks(
        answer: str,
        primary: SourceRecord,
        citations: list[Citation],
        transition_info: dict | None,
    ) -> list[ResponseBlock]:
        blocks = [
            ResponseBlock(
                type="explanation",
                title="Legal Guidance Summary",
                content=answer,
                citation_ids=[c.id for c in citations],
            ),
            ResponseBlock(
                type="legal_basis",
                title="Verified Statutory Provision",
                content=f"{primary.act_name}, {primary.section_number}: {primary.section_text}",
                citation_ids=[primary.id],
            ),
        ]

        if transition_info:
            note_lines = []
            if "act_change" in transition_info:
                act_change = transition_info["act_change"]
                note_lines.append(f"• {act_change['old']} replaced by {act_change['new']} (Effective {act_change['effective_date']})")
            if "section_mapping" in transition_info:
                for mapping in transition_info["section_mapping"]:
                    note_lines.append(f"• {mapping['old']} → {mapping['new']}")

            if note_lines:
                blocks.append(
                    ResponseBlock(
                        type="statutory_transition",
                        title="Statutory Transition Notice (July 2024 Reform)",
                        content=note_lines,
                        severity="info",
                    )
                )

        # A procedural answer always exposes the same safety-critical checklist.
        # Missing fields are explicit; the system never invents them.
        checklist = LegalAssistantService._procedural_checklist(primary)
        blocks.append(
            ResponseBlock(
                type="procedure",
                title="Step-by-Step Procedural Guidance",
                content=checklist,
                citation_ids=[primary.id],
            )
        )

        optional_fields = (
            ("authority", "Responsible Authority / Forum", primary.authority),
            ("documents", "Required Documentation Checklist", primary.documents),
            ("forms", "Prescribed Forms / Applications", primary.forms),
            ("timeline", "Statutory Timeline / Limitation Period", primary.timeline),
            ("fees", "Applicable Statutory Fees", primary.fees),
        )

        for kind, title, content in optional_fields:
            if content:
                blocks.append(
                    ResponseBlock(
                        type=kind,  # type: ignore
                        title=title,
                        content=content,
                        citation_ids=[primary.id],
                    )
                )

        return blocks

    @staticmethod
    def _procedural_checklist(primary: SourceRecord) -> list[str]:
        unavailable = "Not available in the verified local sources."
        procedure = [step.strip() for step in (primary.procedure or "").split("\n") if step.strip()]
        return [
            f"1. Responsible office or authority: {primary.authority or unavailable}",
            f"2. Procedure: {'; '.join(procedure) if procedure else unavailable}",
            f"3. Required documents: {', '.join(primary.documents) if primary.documents else unavailable}",
            f"4. Forms or application method: {', '.join(primary.forms) if primary.forms else unavailable}",
            f"5. Applicable timeline: {primary.timeline or unavailable}",
            f"6. Applicable fees: {primary.fees or unavailable}",
        ]

    @staticmethod
    def _calibrated_confidence(score: float, primary: SourceRecord) -> float:
        """Prevent a keyword match from presenting incomplete procedure as certainty."""
        value = max(0.0, min(1.0, float(score)))
        required = (primary.authority, primary.procedure, primary.documents, primary.forms, primary.timeline)
        if any(not item for item in required):
            value = min(value, 0.65)
        return round(value, 2)
