"""
Citation resolver — Phase 2.5.

Responsibility: convert the LLM's internal SOURCE_N references into trusted
Citation objects backed by ingestion metadata.

The LLM returns source_ids (e.g. ["SOURCE_1", "SOURCE_3"]).
This module validates them against the source_map, discards any IDs that
the LLM hallucinated or that don't exist, deduplicates, and returns a clean
list of Citation objects with URLs we control.

Why this matters:
    Without this layer, the LLM could fabricate URLs or cite the wrong source.
    With it, citation integrity is guaranteed — the LLM only gets to say
    "I used SOURCE_1" and we look up what SOURCE_1 actually is.

Usage in pipeline.py:

    citations = resolve_citations(
        source_ids=field_dict.get("source_ids", []),
        source_map=source_map,
    )
"""

from __future__ import annotations

import logging
import re

from rag.schema import Citation

logger = logging.getLogger(__name__)


def resolve_citations(
    source_ids: list[str] | None,
    source_map: dict[str, dict],
) -> list[Citation]:
    """
    Validate and resolve SOURCE_N IDs to trusted Citation objects.

    Args:
        source_ids: List of SOURCE_N strings returned by the LLM.
                    May contain invalid/hallucinated IDs — they are discarded.
        source_map: Dict of {"SOURCE_1": chunk, …} built by context_builder.

    Returns:
        Deduplicated list[Citation] with data sourced from ingestion metadata,
        not from the LLM's output.
    """
    if not source_ids:
        return []

    seen: set[str] = set()
    citations: list[Citation] = []

    for sid in source_ids:
        # Normalise in case the LLM wraps the ID in brackets or lowercase
        normalised = sid.strip().upper()
        if not normalised.startswith("SOURCE_"):
            normalised = f"SOURCE_{normalised}" if normalised.isdigit() else normalised

        if normalised in seen:
            continue  # deduplicate

        chunk = source_map.get(normalised)
        if chunk is None:
            logger.debug("Citation resolver: LLM returned unknown ID %r — discarded", sid)
            continue

        seen.add(normalised)
        raw_url = chunk.get("url") or None
        if raw_url and "pug_view/data/compound/" in raw_url:
            m = re.search(r"pug_view/data/compound/(\d+)/JSON(?:\?heading=([^&#]+))?", raw_url, flags=re.I)
            if m:
                cid_val = m.group(1)
                heading_val = m.group(2)
                raw_url = f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid_val}#section={heading_val}" if heading_val else f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid_val}"
        citations.append(
            Citation(
                source=chunk.get("source", "Unknown source"),
                url=raw_url,
                text=chunk.get("text") or None,
                publication_date=chunk.get("publication_date") or None,
                authors=chunk.get("authors") or None,
                journal=chunk.get("journal") or None,
                doi=chunk.get("doi") or None,
                pmid=chunk.get("pmid") or None,
                document_id=chunk.get("document_id") or None,
            )
        )

    return citations


def _resolve_field_dict(field: dict | str | None, source_map: dict) -> dict:
    """Normalise a single FieldValue-like dict, resolving source_ids → sources."""
    if not isinstance(field, dict):
        content_str = field if isinstance(field, str) else None
        return {
            "content": content_str,
            "missing": content_str is None,
            "sources": [],
        }

    # SOURCE_N references are converted into trusted citation badges below;
    # remove them from prose if the model also echoed them inline.
    if isinstance(field.get("content"), str):
        field["content"] = re.sub(r"\s*\[SOURCE_\d+\]", "", field["content"]).strip()

    raw_ids = field.pop("source_ids", None)
    citations = resolve_citations(raw_ids, source_map)

    if citations:
        field["sources"] = [c.model_dump() for c in citations]
    elif not field.get("sources"):
        field["sources"] = []

    if "missing" not in field:
        field["missing"] = field.get("content") is None

    return field


def _resolve_citations_recursive(node: Any, source_map: dict[str, dict]) -> Any:
    """Recursively walk dictionary/list trees and convert source_ids and string sources into Citation models."""
    if isinstance(node, dict):
        # 1. Clean inline [SOURCE_N] from content if present
        if isinstance(node.get("content"), str):
            node["content"] = re.sub(r"\s*\[SOURCE_\d+\]", "", node["content"]).strip()

        # 2. Resolve source_ids → sources
        raw_ids = node.pop("source_ids", None)
        if raw_ids:
            citations = resolve_citations(raw_ids, source_map)
            node["sources"] = [c.model_dump() for c in citations]
        elif "sources" in node and isinstance(node["sources"], list):
            new_sources = []
            for s in node["sources"]:
                if isinstance(s, str):
                    if s in source_map or s.startswith("SOURCE_"):
                        c = resolve_citations([s], source_map)
                        if c:
                            new_sources.extend([item.model_dump() for item in c])
                        else:
                            new_sources.append({"source": s})
                    else:
                        new_sources.append({"source": s})
                elif isinstance(s, dict):
                    new_sources.append(s)
            node["sources"] = new_sources

        # Recurse for all sub-keys
        for k, v in list(node.items()):
            node[k] = _resolve_citations_recursive(v, source_map)
        return node
    elif isinstance(node, list):
        return [_resolve_citations_recursive(item, source_map) for item in node]
    return node


def resolve_field_citations(
    llm_dict: dict,
    source_map: dict[str, dict],
    field_keys: list[str] | None = None,
) -> dict:
    """
    Walk through an LLM response dict, resolve source_ids → sources for every
    sub-dict across the 6-section schema, and remove internal source_ids keys.
    """
    result = dict(llm_dict)

    # 1. Top-level FieldValue fields
    for key in ["therapeutic_classes"]:
        if key in result:
            result[key] = _resolve_field_dict(result.get(key), source_map)

    # 2. Pharmacodynamics sub-fields
    pd = result.get("pharmacodynamics")
    if isinstance(pd, dict):
        for sub_key in [
            "mechanism_of_action", "physiologic_effect",
            "binding_affinity", "selectivity", "potency", "efficacy",
        ]:
            if sub_key in pd:
                pd[sub_key] = _resolve_field_dict(pd.get(sub_key), source_map)
        result["pharmacodynamics"] = pd

    # 3. ADME sub-fields
    adme = result.get("adme")
    if isinstance(adme, dict):
        for sub_key in ["absorption", "distribution", "metabolism", "excretion"]:
            if sub_key in adme:
                adme[sub_key] = _resolve_field_dict(adme.get(sub_key), source_map)
        result["adme"] = adme

    # 4. Toxicology sub-fields
    tox = result.get("toxicology")
    if isinstance(tox, dict):
        for sub_key in ["acute_toxicity", "cytotoxicity", "genetic_toxicology", "hazard_classifications"]:
            if sub_key in tox:
                tox[sub_key] = _resolve_field_dict(tox.get(sub_key), source_map)
        result["toxicology"] = tox

    # 5. History sub-fields
    hist = result.get("history")
    if isinstance(hist, dict):
        for sub_key in ["background", "discovery", "development", "clinical_trials"]:
            if sub_key in hist:
                hist[sub_key] = _resolve_field_dict(hist.get(sub_key), source_map)
        result["history"] = hist

    # 6. Drug Name
    dn = result.get("drug_name")
    if isinstance(dn, str):
        result["drug_name"] = {
            "generic": dn,
            "brand_names": [],
            "lab_codes": [],
            "sources": [],
        }
    elif isinstance(dn, dict):
        raw_ids = dn.pop("source_ids", None)
        citations = resolve_citations(raw_ids, source_map)
        if citations:
            dn["sources"] = [c.model_dump() for c in citations]
        elif not dn.get("sources"):
            dn["sources"] = []
        if dn.get("brand_names") is None:
            dn["brand_names"] = []
        if dn.get("lab_codes") is None:
            dn["lab_codes"] = []
        if not dn.get("generic"):
            dn["generic"] = "Unknown"

    # 7. Complete recursive resolution for the entire 6-section schema
    result = _resolve_citations_recursive(result, source_map)

    return result
