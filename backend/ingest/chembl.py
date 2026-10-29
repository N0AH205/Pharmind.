"""
ChEMBL REST Client — Deterministic Bioactivity & Mechanism Ingestion.

Direct async client for EMBL-EBI ChEMBL REST API:
  - Fetches curated mechanisms of action, action types (inhibitor, agonist, etc.)
  - Fetches measured bioactivities (Ki, Kd, IC50, EC50 in nM)
  - Targets, organisms, assay descriptions, and primary paper DOIs
  - Caches responses locally to data/cache/chembl to support offline runs & zero-redundancy calls
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional
import httpx
from rag.config import require_network_allowed

logger = logging.getLogger(__name__)

CHEMBL_API_BASE = "https://www.ebi.ac.uk/chembl/api/data"
CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "chembl"


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
        logger.warning("Failed to cache ChEMBL response for %s: %s", key, exc)


async def get_chembl_molecule(query: str, inchi_key: str | None = None) -> dict | None:
    """Resolve a drug name, SMILES, InChIKey, or ChEMBL ID to a molecule record."""
    cache_key = f"mol_{inchi_key or query.strip().lower()}"
    cached = _get_cache(cache_key)
    if cached:
        return cached

    clean_query = query.strip()
    async with httpx.AsyncClient(timeout=15) as client:
        # 1. Direct ChEMBL ID lookup
        if clean_query.upper().startswith("CHEMBL"):
            try:
                r = await client.get(f"{CHEMBL_API_BASE}/molecule/{clean_query.upper()}.json")
                if r.status_code == 200:
                    data = r.json()
                    _set_cache(cache_key, data)
                    return data
            except Exception:
                pass

        # 2. InChIKey lookup if available
        if inchi_key:
            try:
                r = await client.get(
                    f"{CHEMBL_API_BASE}/molecule.json",
                    params={"molecule_structures__standard_inchi_key": inchi_key},
                )
                if r.status_code == 200:
                    mols = r.json().get("molecules", [])
                    if mols:
                        _set_cache(cache_key, mols[0])
                        return mols[0]
            except Exception:
                pass

        # 3. Exact Preferred Name lookup
        try:
            r = await client.get(
                f"{CHEMBL_API_BASE}/molecule.json",
                params={"pref_name__iexact": clean_query},
            )
            if r.status_code == 200:
                mols = r.json().get("molecules", [])
                if mols:
                    _set_cache(cache_key, mols[0])
                    return mols[0]
        except Exception:
            pass

        # 4. Synonym lookup
        try:
            r = await client.get(
                f"{CHEMBL_API_BASE}/molecule.json",
                params={"molecule_synonyms__molecule_synonym__iexact": clean_query},
            )
            if r.status_code == 200:
                mols = r.json().get("molecules", [])
                if mols:
                    _set_cache(cache_key, mols[0])
                    return mols[0]
        except Exception:
            pass

    return None


async def get_chembl_mechanisms(chembl_id: str) -> list[dict]:
    """Fetch mechanism of action entries for a ChEMBL molecule ID."""
    cache_key = f"mech_{chembl_id}"
    cached = _get_cache(cache_key)
    if cached and "mechanisms" in cached:
        return cached["mechanisms"]

    mechanisms: list[dict] = []
    async with httpx.AsyncClient(timeout=15) as client:
        # Check both molecule_chembl_id and parent_molecule_chembl_id
        for param in ("molecule_chembl_id", "parent_molecule_chembl_id"):
            try:
                r = await client.get(
                    f"{CHEMBL_API_BASE}/mechanism.json",
                    params={param: chembl_id},
                )
                if r.status_code == 200:
                    data = r.json().get("mechanisms", [])
                    if data:
                        mechanisms = data
                        break
            except Exception:
                pass

    _set_cache(cache_key, {"mechanisms": mechanisms})
    return mechanisms


async def get_chembl_target(target_chembl_id: str) -> dict | None:
    """Fetch target details (protein name, organism, type)."""
    if not target_chembl_id:
        return None
    cache_key = f"target_{target_chembl_id}"
    cached = _get_cache(cache_key)
    if cached:
        return cached

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{CHEMBL_API_BASE}/target/{target_chembl_id}.json")
            if r.status_code == 200:
                data = r.json()
                _set_cache(cache_key, data)
                return data
        except Exception:
            pass
    return None


async def get_chembl_activities(chembl_id: str, limit: int = 30) -> list[dict]:
    """Fetch measured Ki, Kd, IC50, EC50 bioactivity records."""
    cache_key = f"act_{chembl_id}"
    cached = _get_cache(cache_key)
    if cached and "activities" in cached:
        return cached["activities"]

    activities: list[dict] = []
    async with httpx.AsyncClient(timeout=15) as client:
        for param in ("molecule_chembl_id", "parent_molecule_chembl_id"):
            try:
                r = await client.get(
                    f"{CHEMBL_API_BASE}/activity.json",
                    params={
                        param: chembl_id,
                        "standard_type__in": "Ki,Kd,IC50,EC50",
                        "limit": limit,
                    },
                )
                if r.status_code == 200:
                    data = r.json().get("activities", [])
                    if data:
                        activities = data
                        break
            except Exception:
                pass

    _set_cache(cache_key, {"activities": activities})
    return activities


async def fetch_chembl_profile(query: str, inchi_key: str | None = None) -> dict:
    """
    Main aggregator: returns a structured ChEMBL profile with:
      - chembl_id, pref_name, max_phase, molecule_type
      - mechanisms (list with target name, action_type)
      - bioactivities (top curated assays sorted by affinity value in nM)
    """
    require_network_allowed("fetch_chembl_profile")
    mol = await get_chembl_molecule(query, inchi_key=inchi_key)
    if not mol:
        return {
            "chembl_id": None,
            "max_phase": None,
            "mechanisms": [],
            "bioactivities": [],
        }

    chembl_id = mol.get("molecule_chembl_id")
    pref_name = mol.get("pref_name") or query
    max_phase = mol.get("max_phase")
    mol_type = mol.get("molecule_type")

    # Fetch mechanisms and raw activities in parallel
    import asyncio
    raw_mechs, raw_acts = await asyncio.gather(
        get_chembl_mechanisms(chembl_id),
        get_chembl_activities(chembl_id, limit=40),
    )

    # Enrich mechanisms with target details
    enriched_mechs = []
    for m in raw_mechs:
        t_id = m.get("target_chembl_id")
        t_info = await get_chembl_target(t_id) if t_id else None
        enriched_mechs.append({
            "mechanism_of_action": m.get("mechanism_of_action"),
            "action_type": m.get("action_type"),
            "target_chembl_id": t_id,
            "target_name": t_info.get("pref_name") if t_info else m.get("target_chembl_id"),
            "target_organism": t_info.get("organism") if t_info else "Homo sapiens",
        })

    # Process and rank bioactivities
    processed_acts = []
    seen_assays = set()
    for a in raw_acts:
        std_val = a.get("standard_value")
        std_type = a.get("standard_type")
        if std_val is None or not std_type:
            continue
        try:
            val_float = float(std_val)
        except (ValueError, TypeError):
            continue

        target_name = a.get("target_pref_name") or a.get("target_chembl_id") or "Unspecified target"
        organism = a.get("target_organism") or "Homo sapiens"
        assay_id = a.get("assay_chembl_id") or a.get("activity_id")

        key = f"{target_name}_{std_type}_{val_float}"
        if key in seen_assays:
            continue
        seen_assays.add(key)

        processed_acts.append({
            "target_name": target_name,
            "target_organism": organism,
            "standard_type": std_type,
            "value_nm": val_float,
            "relation": a.get("standard_relation") or "=",
            "pchembl_value": float(a["pchembl_value"]) if a.get("pchembl_value") else None,
            "assay_description": a.get("assay_description"),
            "chembl_assay_id": str(assay_id) if assay_id else None,
            "doi": a.get("document_doi"),
        })

    # Sort bioactivities: prioritize human assays, then lowest nM value (highest affinity)
    def _act_sort_key(item: dict):
        is_human = 0 if item.get("target_organism") == "Homo sapiens" else 1
        return (is_human, item.get("value_nm") or 9999999)

    processed_acts.sort(key=_act_sort_key)
    top_acts = processed_acts[:8]

    return {
        "chembl_id": chembl_id,
        "pref_name": pref_name,
        "max_phase": max_phase,
        "molecule_type": mol_type,
        "mechanisms": enriched_mechs,
        "bioactivities": top_acts,
    }


async def fetch_chembl_passages(
    drug_name: str,
    inchi_key: str | None = None,
    cid_str: str | None = None,
) -> list[dict]:
    """Return formatted ChEMBL mechanism and bioactivity chunk dicts for retrieval."""
    profile = await fetch_chembl_profile(drug_name, inchi_key=inchi_key)
    c_id = profile.get("chembl_id")
    if not c_id:
        return []

    passages: list[dict] = []
    # 1. Curated mechanisms
    for m in profile.get("mechanisms", []):
        target = m.get("target_name") or "Primary Target"
        org = m.get("target_organism") or "Human"
        action = m.get("action_type") or "modulator"
        moa = m.get("mechanism_of_action") or f"{action} of {target}"
        passages.append({
            "text": f"ChEMBL Curated Mechanism: {moa} | Action: {action} | Target: {target} ({org})",
            "source": f"ChEMBL Mechanism {c_id}",
            "url": f"https://www.ebi.ac.uk/chembl/compound_report_card/{c_id}/",
            "drug": drug_name,
            "pubchem_cid": cid_str or "",
            "field": "moa",
            "retrieval_group": "moa",
            "document_id": str(c_id),
        })

    # 2. Measured quantitative bioactivity assays (Ki, Kd, IC50, EC50 in nM)
    for a in profile.get("bioactivities", []):
        std_type = a.get("standard_type", "Affinity")
        val = a.get("value_nm")
        rel = a.get("relation") or "="
        target = a.get("target_name") or "Target Assay"
        org = a.get("target_organism") or "Human"
        desc = a.get("assay_description") or ""
        assay_id = a.get("chembl_assay_id") or c_id
        passages.append({
            "text": f"ChEMBL Quantitative Bioassay: Target {target} ({org}) — Measured {std_type} {rel} {val} nM. Assay details: {desc}",
            "source": f"ChEMBL Bioassay {assay_id}",
            "url": f"https://www.ebi.ac.uk/chembl/compound_report_card/{c_id}/",
            "drug": drug_name,
            "pubchem_cid": cid_str or "",
            "field": "binding_affinity",
            "retrieval_group": "binding_affinity",
            "document_id": str(assay_id),
        })

    return passages


async def get_chembl_activity_evidence(inchi_key: str | None) -> list[dict]:
    """Return formatted activity chunk dicts for run_ingest.py."""
    if not inchi_key:
        return []
    return await fetch_chembl_passages(inchi_key, inchi_key=inchi_key)
