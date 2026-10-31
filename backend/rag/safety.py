"""
Safety classification layer (Phase 5).
Classifies incoming user queries to detect if they are seeking medical/clinical advice
and raises a refusal exception if so.
"""

from __future__ import annotations

import logging
import re
from pydantic import BaseModel, Field
from rag.llm import generate_structured_output

logger = logging.getLogger(__name__)


class QueryClassification(BaseModel):
    category: str = Field(
        ...,
        description="One of: 'chemical_smiles', 'drug_lookup', or 'clinical_advice'"
    )
    reason: str = Field(
        ...,
        description="Short reason explanation why the query fits this category."
    )


class ClinicalAdviceRefusal(ValueError):
    """Exception raised when a query is classified as requesting medical/clinical advice."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


CLINICAL_ADVICE_DISCLAIMER = (
    "Pharmer is designed for educational and reference purposes only. "
    "We cannot answer patient-specific clinical advice, diagnosis, treatment recommendation, "
    "or dosage instruction queries. Always consult a licensed clinician or pharmacist "
    "for professional medical guidance."
)

# Heuristic clinical advice trigger terms for fallback (patient-specific advice requests)
_CLINICAL_TRIGGERS = [
    "should i take", "can i take", "how much should i take",
    "what dose should i take", "my dose", "my dosage", "for my headache",
    "for my pain", "cure my", "treat my", "my symptoms", "my disease",
    "my doctor prescribed", "i am pregnant", "can i give my child",
    "am i allergic", "can i drink alcohol with my"
]


def looks_like_clinical_advice(query: str) -> bool:
    return any(trigger in query.casefold() for trigger in _CLINICAL_TRIGGERS)


async def check_query_safety(query: str) -> tuple[bool, str | None]:
    """
    Classify a user query to detect if it is seeking clinical advice.

    Returns:
        tuple (is_safe, refusal_message)
        If the query is unsafe (clinical advice), returns (False, disclaimer_message).
        Otherwise returns (True, None).
    """
    trimmed = query.strip()
    if not trimmed:
        return True, None

    if looks_like_clinical_advice(trimmed):
        return False, CLINICAL_ADVICE_DISCLAIMER

    # A small local classifier can mistake ordinary mechanism questions for treatment advice.
    # Reserve classification for questions that contain personal or recommendation cues.
    if not re.search(r"\b(i|my|me|mine|patient|child|pregnant|should|recommend|prescribe|treat|dose|dosage|safe|safest|best)\b", trimmed, re.I):
        return True, None

    # If it is a purely alphanumeric string with no spaces (e.g. "aspirin" or "CC(=O)..."),
    # we can bypass LLM classification to keep retrieval instantaneous.
    if " " not in trimmed:
        return True, None

    system_prompt = (
        "You are a medical safety classification assistant.\n"
        "Your task is to classify a user query into one of three categories:\n"
        "1. 'chemical_smiles': A pure chemical formula, IUPAC name, or SMILES string (e.g. 'CC(=O)Oc1ccccc1C(=O)O').\n"
        "2. 'drug_lookup': A simple lookup request for a drug name, synonyms, or general chemical information without asking for clinical recommendation or patient-specific advice (e.g. 'aspirin', 'what is caffeine', 'Metformin details').\n"
        "3. 'clinical_advice': A query asking for patient-specific clinical advice, medical recommendation, dosage instruction, disease treatment, pregnancy safety, interactions with patient's specific drugs, diagnosis, or clinical evaluation (e.g. 'Should I take aspirin for a fever?', 'what is the best dose of metformin for me?', 'will caffeine interact with my sleep meds?').\n\n"
        "You must output JSON matching the required schema."
    )

    user_message = f"User query: {query}"

    try:
        result = await generate_structured_output(
            system_prompt=system_prompt,
            user_message=user_message,
            output_schema=QueryClassification,
        )

        category = result.get("category", "drug_lookup")
        reason = result.get("reason", "")
        logger.info(f"Query safety check: category='{category}' reason='{reason}'")

        if category == "clinical_advice":
            refusal = f"Refusal: {CLINICAL_ADVICE_DISCLAIMER}\n\n(Reason: Classified as clinical advice - {reason})"
            return False, refusal

    except Exception as e:
        logger.error(f"Error running safety classification: {e}")
        # Fallback to heuristic classification:
        lower_q = trimmed.lower()
        if looks_like_clinical_advice(lower_q):
            return False, f"Refusal: {CLINICAL_ADVICE_DISCLAIMER} (Triggered heuristic safety guardrail)"

    return True, None
