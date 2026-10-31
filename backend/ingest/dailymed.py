"""
DailyMed / FDA drug label fetcher — Phase 2.

DailyMed provides FDA-approved labels (Structured Product Labeling / SPL format).
The v2 REST API supports JSON for search but returns XML for label content.
We parse the XML to extract the clinically relevant sections.

API docs: https://dailymed.nlm.nih.gov/dailymed/app-support-web-services.cfm
SPL XML namespace: urn:hl7-org:v3
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx
from rag.config import require_network_allowed

BASE_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v2"

# SPL HL7 XML namespace
_NS = "urn:hl7-org:v3"

# LOINC section codes → our internal field keys
# These are the standard codes used in FDA SPL documents.
_LOINC_MAP: dict[str, str] = {
    "34066-1": "boxed_warning",
    "34068-7": "dosage_and_administration",
    "34067-9": "indications",           # INDICATIONS AND USAGE SECTION
    "34070-3": "contraindications",     # CONTRAINDICATIONS SECTION
    "34071-1": "warnings",
    "34072-9": "precautions",
    "43684-0": "use_in_specific_populations",
    "34088-5": "overdosage",
    "34089-3": "description",
    "34092-7": "clinical_studies",
    "34069-5": "how_supplied",
    "43680-8": "nonclinical_toxicology",
    "34083-6": "nonclinical_toxicology",
    "43685-7": "warnings",
    "34084-4": "adverse_effects",       # ADVERSE REACTIONS SECTION
    "34073-7": "drug_interactions",     # DRUG INTERACTIONS SECTION
    "43679-0": "mechanism_of_action",   # MECHANISM OF ACTION SECTION
    "43682-4": "pharmacokinetics",      # PHARMACOKINETICS SECTION
    "34090-1": "clinical_pharmacology",
    "43681-6": "pharmacodynamics",
    "90375-7": "adverse_effects",
}

# Keyword fallback for displayName matching when code not in map
_KEYWORD_MAP: dict[str, str] = {
    "dosage and administration": "dosage_and_administration",
    "indication": "indications",
    "contraindication": "contraindications",
    "warnings and precautions": "warnings",
    "warnings": "warnings",
    "precautions": "precautions",
    "use in specific populations": "use_in_specific_populations",
    "overdosage": "overdosage",
    "clinical studies": "clinical_studies",
    "nonclinical toxicology": "nonclinical_toxicology",
    "description": "description",
    "adverse reaction": "adverse_effects",
    "adverse effect": "adverse_effects",
    "side effect": "adverse_effects",
    "drug interaction": "drug_interactions",
    "clinical pharmacology": "clinical_pharmacology",
    "mechanism of action": "mechanism_of_action",
    "pharmacokinetic": "pharmacokinetics",
}


def _extract_text(element) -> str:
    """Recursively extract all text content from an XML element."""
    texts = []
    if element.text:
        texts.append(element.text.strip())
    for child in element:
        texts.append(_extract_text(child))
        if child.tail:
            texts.append(child.tail.strip())
    return " ".join(t for t in texts if t)


def _parse_spl_xml(xml_text: str) -> dict[str, str]:
    """
    Parse a DailyMed SPL XML document and extract clinical sections.

    Returns a dict mapping field key → section text.
    Uses LOINC codes first (reliable), then falls back to display name keywords.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return {}

    sections: dict[str, str] = {}

    # SPL sections are <section> elements containing a <code> and <text>
    for section_el in root.iter(f"{{{_NS}}}section"):
        code_el = section_el.find(f"{{{_NS}}}code")
        if code_el is None:
            continue

        loinc_code = code_el.get("code", "")
        display_name = code_el.get("displayName", "").lower()

        # Determine field key
        field_key: str | None = _LOINC_MAP.get(loinc_code)
        if not field_key:
            for keyword, key in _KEYWORD_MAP.items():
                if keyword in display_name:
                    field_key = key
                    break
        if not field_key:
            continue

        # SPL parents often have no narrative of their own; the content lives in
        # nested, unclassified subsections (including pharmacokinetics and interactions).
        text = " ".join(_extract_text(text_el) for text_el in section_el.iter(f"{{{_NS}}}text")).strip()
        if not text:
            continue

        # Keep the longest text if a field appears in multiple sections
        if field_key not in sections or len(text) > len(sections[field_key]):
            sections[field_key] = text

    return sections


async def search_drug_labels(drug_name: str, pagesize: int = 20) -> list[dict]:
    require_network_allowed("DailyMed label search")
    """
    Search DailyMed for SPL labels matching a drug name.
    Returns up to `pagesize` label metadata records (each has a 'setid').
    """
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            f"{BASE_URL}/spls.json",
            params={"drug_name": drug_name, "pagesize": pagesize},
        )
        if resp.status_code != 200:
            return []
        return resp.json().get("data", [])


async def get_label_sections(set_id: str) -> dict[str, str]:
    require_network_allowed("DailyMed label download")
    """
    Fetch and parse a full SPL label by set_id.

    Returns a dict mapping field key → section text, e.g.:
        {
            "indications": "Aspirin is indicated for...",
            "adverse_effects": "GI irritation...",
            ...
        }
    Only sections with non-empty text are included.
    """
    xml_url = f"{BASE_URL}/spls/{set_id}.xml"
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(xml_url)
        if resp.status_code != 200:
            return {}

    return _parse_spl_xml(resp.text)
