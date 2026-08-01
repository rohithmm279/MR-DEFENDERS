from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from .schemas import Domain, STATUTORY_TRANSITIONS, CRISIS_RESOURCES, CrisisResource

DISCLAIMER = "This is general legal information, not legal advice. For case-specific action, consult a qualified legal professional."

CRISIS_MESSAGE = (
    "Your safety comes first. If there is immediate danger, contact local emergency services now. "
    "For domestic violence or urgent legal-aid support, contact a verified local women's helpline or legal-aid service. "
    "This app cannot safely handle an emergency or an active case."
)


@dataclass(frozen=True)
class SafetyResult:
    escalate: bool
    reason: str | None = None
    crisis_type: Literal["immediate_risk", "active_case", "domestic_violence", "arrest", "none"] = "none"
    resources: list[CrisisResource] = None
    
    def __post_init__(self):
        if self.escalate and self.resources is None:
            object.__setattr__(self, 'resources', self._get_resources())
    
    def _get_resources(self) -> list[CrisisResource]:
        if self.crisis_type == "domestic_violence":
            return CRISIS_RESOURCES.get("domestic_violence", [])
        elif self.crisis_type in ("immediate_risk", "arrest"):
            return CRISIS_RESOURCES.get("domestic_violence", []) + CRISIS_RESOURCES.get("legal_aid", [])
        return CRISIS_RESOURCES.get("legal_aid", [])


# Expanded crisis detection patterns
CRISIS_PATTERNS = {
    "immediate_risk": [
        "immediate danger", "being beaten", "unsafe at home", "he will kill", "she will kill",
        "threatening to kill", "weapon", "knife", "gun", "hurt me", "hurt us", "children",
        "scared", "fear", "protect", "running away", "shelter", "hide"
    ],
    "arrest": [
        "arrested now", "police are arresting", "arrest in progress", "police station now",
        "being taken", "handcuffed", "remand", "custody", "lockup", "jail now"
    ],
    "active_case": [
        "court hearing tomorrow", "active court case", "case-specific strategy", "what should i say in court",
        "my lawyer says", "judge asked", "next hearing", "bail hearing", "chargesheet", "charge sheet",
        "summons", "warrant", "plead guilty", "confess"
    ],
    "domestic_violence": [
        "domestic violence", "husband beat", "wife beat", "beating", "abuse", "abusive",
        "mental harassment", "physical abuse", "emotional abuse", "controlling", "isolating",
        "forced", "coerced", "threatened", "dowry harassment", "torture", "marital rape"
    ]
}

# Domain classification keywords with weights
DOMAIN_KEYWORDS = {
    "consumer": {
        "consumer": 2, "refund": 2, "defective": 2, "product": 1, "seller": 1, 
        "e-commerce": 2, "complaint": 1, "service": 1, "warranty": 2, "purchase": 1,
        "delivery": 1, "online": 0.5, "payment": 0.5, "fraud": 1, "scam": 1,
        "replacement": 1, "repair": 1, "deficiency": 2, "unfair": 1, "trade practice": 2
    },
    "criminal": {
        "fir": 3, "police": 2, "arrest": 2, "bail": 3, "zero fir": 3, 
        "complaint refused": 3, "offence": 1, "cognizable": 2, "non-cognizable": 2,
        "anticipatory bail": 3, "remand": 2, "custody": 2, "chargesheet": 2,
        "investigation": 1, "accused": 1, "victim": 1, "crime": 1, "ipc": 1,
        "bnss": 1, "bns": 1, "section": 0.5, "offence": 1, "punishment": 1
    },
    "family": {
        "marriage": 2, "married": 1, "dowry": 3, "domestic": 1, "wife": 1, 
        "husband": 1, "registration": 1, "spouse": 1, "divorce": 2, "maintenance": 2,
        "alimony": 2, "custody": 2, "child": 0.5, "adoption": 2, "hindu marriage": 2,
        "special marriage": 2, "protection of women": 3, "dv act": 3
    },
    "property": {
        "property": 2, "rent": 2, "tenant": 2, "landlord": 2, "lease": 2,
        "eviction": 2, "title": 1, "deed": 1, "registration": 1, "sale": 1,
        "inheritance": 1, "will": 1, "succession": 1
    },
    "labour": {
        "employee": 2, "employer": 2, "salary": 2, "wage": 2, "termination": 2,
        "wrongful": 1, "dismissal": 2, "labour": 2, "factory": 1, "workmen": 1,
        "provident fund": 2, "pf": 2, "epf": 2
    },
    "rti": {
        "rti": 3, "right to information": 3, "information": 0.5, "pio": 2,
        "public information officer": 3, "commission": 0.5, "appeal": 0.5
    }
}


def assess_safety(query: str, enable_crisis_detection: bool = True) -> SafetyResult:
    """
    Assess if query indicates crisis requiring escalation.
    Returns SafetyResult with escalate=True if crisis detected.
    """
    if not enable_crisis_detection:
        return SafetyResult(False)
    
    text = query.lower()
    
    # Check each crisis category
    for crisis_type, patterns in CRISIS_PATTERNS.items():
        matches = sum(1 for pattern in patterns if pattern in text)
        if matches >= 2 or (matches >= 1 and crisis_type in ("immediate_risk", "arrest")):
            return SafetyResult(
                escalate=True,
                reason=f"crisis_detected:{crisis_type}",
                crisis_type=crisis_type
            )
    
    # Single strong indicators
    strong_indicators = ["suicide", "kill myself", "end my life", "poison", "overdose"]
    if any(indicator in text for indicator in strong_indicators):
        return SafetyResult(
            escalate=True,
            reason="crisis_detected:self_harm",
            crisis_type="immediate_risk"
        )
    
    return SafetyResult(False)


def classify_domain(query: str) -> tuple[Domain | None, dict[str, float]]:
    """
    Classify query into legal domain with confidence scores.
    Returns (best_domain, all_scores) or (None, all_scores) if no domain meets threshold.
    """
    text = query.lower()
    scores = {}
    
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = 0.0
        for keyword, weight in keywords.items():
            if keyword in text:
                score += weight
        # Normalize by query length to avoid bias toward long queries
        query_length_factor = min(1.0, len(text.split()) / 5.0)
        scores[domain] = score * (0.5 + 0.5 * query_length_factor)
    
    # Find best domain
    if not scores:
        return None, {}
    
    best_domain = max(scores, key=scores.get)
    best_score = scores[best_domain]
    
    # Threshold for confident classification
    threshold = 2.0
    if best_score >= threshold:
        return best_domain, scores
    
    # Check for out-of-scope indicators
    out_of_scope_keywords = ["tax", "income tax", "gst", "gst filing", "company registration", 
                            "startup", "trademark", "copyright", "patent", "visa", "passport",
                            "driving license", "rto", "vehicle registration"]
    if any(kw in text for kw in out_of_scope_keywords):
        return None, scores
    
    return None, scores


def get_statutory_transition(domain: Domain | None, query: str) -> dict | None:
    """
    Detect if query references old laws and provide mapping to new laws.
    Returns transition info if applicable, None otherwise.
    """
    if domain != "criminal" or not STATUTORY_TRANSITIONS.get("criminal"):
        return None
    
    text = query.upper()
    transitions = STATUTORY_TRANSITIONS["criminal"]
    
    # Check for old law references
    found_transitions = {}
    
    # Check act name transitions
    for old_act, new_act in transitions["old_to_new"].items():
        if old_act in text:
            found_transitions["act_change"] = {
                "old": old_act,
                "new": new_act,
                "effective_date": "July 1, 2024",
                "note": f"The {old_act} has been replaced by {new_act} for offences after July 1, 2024."
            }
    
    # Check section mappings
    for (old_act, old_section), (new_act, new_section) in transitions["section_mapping"].items():
        if f"{old_section} {old_act}" in text or f"{old_act} {old_section}" in text:
            if "section_mapping" not in found_transitions:
                found_transitions["section_mapping"] = []
            found_transitions["section_mapping"].append({
                "old": f"Section {old_section} {old_act}",
                "new": f"Section {new_section} {new_act}",
                "note": "Section numbering has changed under the new law."
            })
    
    return found_transitions if found_transitions else None
