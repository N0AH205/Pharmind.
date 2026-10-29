"""
openFDA Drug Label REST Client — Zero-Hallucination Package Inserts.

Fetches official FDA-approved structured product labeling (SPL) from api.fda.gov:
  - Boxed warnings & black box alerts
  - Indications and clinical usage
  - Absolute & relative Contraindications
  - Warnings & adverse reactions
  - Drug interactions (CYP enzymes, pharmacokinetic interactions)
  - Mechanism of action & Pharmacodynamics
  - Pharmacokinetics (ADME: Bioavailability, Vd, Half-Life, Metabolism, Excretion)
  - Nonclinical Toxicology (Carcinogenesis, Mutagenesis, Impairment of Fertility)
  - Overdosage & Acute Toxicity Management

100% verified FDA regulatory labeling.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional
import httpx
from rag.config import require_network_allowed

logger = logging.getLogger(__name__)

OPENFDA_BASE_URL = "https://api.fda.gov/drug/label.json"
CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "openfda"


def _get_cache(key: str) -> dict | None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _set_cache(key: str, data: dict) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = CACHE_DIR / f"{key}.json"
        cache_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed to cache openFDA response for %s: %s", key, exc)


def _clean_fda_text(values: list[str] | str | None) -> str | None:
    if not values:
        return None
    if isinstance(values, list):
        text = "\n\n".join(v.strip() for v in values if v.strip())
        return text if text else None
    return values.strip() if values.strip() else None


def _chunk_text(text: str, max_chars: int = 1500, overlap: int = 200) -> list[str]:
    """Split long FDA label sections into overlapping searchable passages."""
    text = " ".join(text.split())
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            boundary = text.rfind(". ", start, end)
            if boundary > start + max_chars // 2:
                end = boundary + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return [c for c in chunks if c]


async def fetch_openfda_label(drug_name: str, strict: bool = False) -> dict | None:
    """
    Query openFDA label endpoint by generic_name, brand_name, or substance_name.
    Returns structured label sections and openfda metadata.
    """
    require_network_allowed("fetch_openfda_label")
    clean_name = drug_name.strip().lower()
    if not clean_name:
        return None
    cache_key = f"label_{re.sub(r'[^\w\-]', '_', clean_name)}"
    cached = _get_cache(cache_key)
    if cached:
        return cached

    from ingest.unified_pharmacology import get_drug_synonym_expansions
    candidate_terms = get_drug_synonym_expansions(clean_name)

    search_queries = []
    for term in candidate_terms[:6]:
        term_clean = term.lower()
        search_queries.extend([
            f'openfda.generic_name:"{term_clean}"',
            f'openfda.brand_name:"{term_clean}"',
            f'openfda.substance_name:"{term_clean}"',
        ])

    request_failures = []
    async with httpx.AsyncClient(timeout=15) as client:
        for q in search_queries:
            try:
                r = await client.get(OPENFDA_BASE_URL, params={"search": q, "limit": 1})
                if r.status_code == 200:
                    results = r.json().get("results", [])
                    if results:
                        label = results[0]
                        openfda_meta = label.get("openfda", {})

                        parsed = {
                            "source": "openFDA Approved Drug Label",
                            "generic_name": openfda_meta.get("generic_name", [drug_name])[0],
                            "brand_names": openfda_meta.get("brand_name", []),
                            "spl_id": label.get("id") or (openfda_meta.get("spl_id", [None])[0]),
                            "boxed_warning": _clean_fda_text(label.get("boxed_warning")),
                            "indications": _clean_fda_text(label.get("indications_and_usage")),
                            "contraindications": _clean_fda_text(label.get("contraindications")),
                            "warnings": _clean_fda_text(label.get("warnings_and_cautions") or label.get("warnings")),
                            "adverse_reactions": _clean_fda_text(label.get("adverse_reactions")),
                            "drug_interactions": _clean_fda_text(label.get("drug_interactions")),
                            "mechanism_of_action": _clean_fda_text(label.get("mechanism_of_action")),
                            "pharmacodynamics": _clean_fda_text(label.get("pharmacodynamics")),
                            "pharmacokinetics": _clean_fda_text(label.get("pharmacokinetics")),
                            "clinical_pharmacology": _clean_fda_text(label.get("clinical_pharmacology")),
                            "nonclinical_toxicology": _clean_fda_text(label.get("nonclinical_toxicology")),
                            "carcinogenesis_mutagenesis": _clean_fda_text(label.get("carcinogenesis_and_mutagenesis_and_impairment_of_fertility")),
                            "animal_toxicology": _clean_fda_text(label.get("animal_pharmacology_and_or_toxicology")),
                            "overdosage": _clean_fda_text(label.get("overdosage")),
                            "specific_populations": _clean_fda_text(label.get("use_in_specific_populations")),
                        }
                        _set_cache(cache_key, parsed)
                        return parsed
                elif r.status_code != 404:
                    r.raise_for_status()
            except Exception as exc:
                request_failures.append(exc)
                logger.debug("openFDA query failed for %s: %s", q, exc)

    if strict and request_failures:
        raise RuntimeError(f"openFDA lookup failed for {drug_name}: {request_failures[-1]}")
    return None


async def fetch_openfda_passages(
    drug_name: str,
    canonical_name: str | None = None,
    cid_str: str | None = None,
    strict: bool = False,
) -> list[dict]:
    """
    Fetch FDA-approved structured product label sections and return chunked passages
    ready for retrieval and vector storage.
    """
    c_name = canonical_name or drug_name
    label = await fetch_openfda_label(c_name, strict=strict)
    if not label and c_name.lower() != drug_name.lower():
        label = await fetch_openfda_label(drug_name, strict=strict)

    if not label:
        return []

    brand = (label.get("brand_names") or [c_name])[0]
    spl_id = label.get("spl_id") or "FDA-SPL"
    source_label = f"openFDA SPL — {c_name} ({brand})"
    url = f"https://labels.fda.gov/"

    section_mapping = [
        ("mechanism_of_action", "moa"),
        ("pharmacodynamics", "physiologic_effect"),
        ("pharmacokinetics", "adme"),
        ("indications", "indications"),
        ("contraindications", "contraindications"),
        ("drug_interactions", "interactions"),
        ("boxed_warning", "safety"),
        ("warnings", "adverse_effects"),
        ("adverse_reactions", "adverse_effects"),
        ("overdosage", "acute_toxicity"),
        ("carcinogenesis_mutagenesis", "genetic_toxicology"),
        ("nonclinical_toxicology", "toxicology"),
        ("animal_toxicology", "toxicology"),
        ("clinical_pharmacology", "clinical_pharmacology"),
    ]

    passages: list[dict] = []
    for fda_field, schema_field in section_mapping:
        content = label.get(fda_field)
        if not content:
            continue
        chunks = _chunk_text(content)
        for chunk in chunks:
            passages.append({
                "text": f"FDA Approved Label [{fda_field.upper()}]: {chunk}",
                "source": source_label,
                "url": url,
                "drug": c_name,
                "pubchem_cid": cid_str or "",
                "field": schema_field,
                "retrieval_group": schema_field,
                "document_id": str(spl_id),
            })

    return passages
