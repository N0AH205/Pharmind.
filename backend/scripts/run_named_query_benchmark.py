"""Run a small live retrieval benchmark across distinct drug query types."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import BaseModel

from rag.pipeline import run_pipeline
from rag.retriever import get_retriever
from rag import online_search

logging.getLogger("httpx").setLevel(logging.WARNING)

_refresh_compound_sources = online_search.refresh_compound_sources


async def refresh_if_uncached(structure_data, collection):
    retriever = get_retriever()
    cid = str(structure_data.get("pubchem_cid") or "")
    name = str(structure_data.get("common_name") or "")
    cached_count = retriever.get_drug_chunk_count(cid) if cid else 0
    if not cached_count and name:
        cached_count = retriever.get_drug_chunk_count(name)
    if cached_count:
        print(f"Reusing {cached_count} cached source chunks for {name or cid}", flush=True)
        return
    await _refresh_compound_sources(structure_data, collection)


online_search.refresh_compound_sources = refresh_if_uncached


CASES = [
    ("Caffeine", "single_molecule", "caffeine"),
    ("ozempic", "brand_to_active_ingredient", "semaglutide"),
    ("fentanyl", "single_molecule", "fentanyl"),
    ("anabolic steroids", "drug_class", None),
    ("cannabis", "plant_or_mixture", None),
]
KEY_GROUPS = {
    "mechanism": {"moa"},
    "indications": {"indications"},
    "contraindications": {"safety", "interactions"},
    "absorption": {"adme"},
    "distribution": {"adme"},
    "metabolism": {"adme"},
    "excretion": {"adme"},
}


def key_field(result, name: str) -> tuple[str | None, bool, bool]:
    if name == "mechanism":
        item = result.pharmacodynamics.mechanism_of_action
        return item.content, bool(item.sources), item.missing
    if name == "indications":
        item = result.therapeutic_profile.indications
        rows = item.approved_indications + item.off_label_use + item.investigational_uses
        text = "; ".join(row.indication for row in rows)
        summary = item.summary
        if summary and summary.content:
            text += ("; " if text else "") + summary.content
        cited = bool((summary and summary.sources) or any(row.source for row in rows))
        return text or None, cited, not bool(text)
    if name == "contraindications":
        item = result.toxicology_and_safety.clinical_safety.contraindications
        return item.content, bool(item.sources), item.missing
    items = {
        "absorption": result.pharmacokinetics.absorption.bioavailability,
        "distribution": result.pharmacokinetics.distribution.volume_of_distribution,
        "metabolism": result.pharmacokinetics.metabolism.metabolic_pathways,
        "excretion": result.pharmacokinetics.excretion.primary_route,
    }
    item = items[name]
    return item.content, bool(item.sources), item.missing


def all_field_values(value, path=""):
    if isinstance(value, BaseModel):
        if value.__class__.__name__ == "FieldValue":
            yield path, value
        else:
            for key, child in value:
                yield from all_field_values(child, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from all_field_values(child, f"{path}[{index}]")


def percentage(numerator: int, denominator: int) -> float:
    return round(100 * numerator / denominator, 1) if denominator else 0.0


async def main() -> None:
    report = {
        "run_date": "2026-10-24",
        "model": "gemini-flash-lite-latest",
        "cases": [],
    }
    for query, query_type, expected in CASES:
        print(f"START {query}", flush=True)
        started = time.monotonic()
        row = {"query": query, "query_type": query_type}
        try:
            output = await run_pipeline(query, debug=True)
            result, debug = output["result"], output["debug"]
            identity = result.drug_overview.identity.generic_name.content
            identity_norm = (identity or "").lower()
            if expected:
                identity_ok = expected in identity_norm
                identity_check = "pass" if identity_ok else "mismatch"
            else:
                alternatives = " ".join(result.drug_overview.identity.alternative_names)
                identity_ok = bool(
                    identity and query.lower() in (identity_norm + " " + alternatives.lower())
                )
                identity_check = (
                    "ambiguous_category_preserved" if identity_ok else "category_not_preserved"
                )

            field_results = {}
            for name in KEY_GROUPS:
                content, cited, missing = key_field(result, name)
                field_results[name] = {
                    "answered": bool(content and not missing),
                    "citation_attached": cited,
                }
            retrieved_groups = set()
            for chunk in debug.get("retrieved_chunks", []):
                retrieved_groups.update(
                    chunk.get(
                        "retrieval_groups",
                        [chunk.get("retrieval_group", chunk.get("field", ""))],
                    )
                )
            group_hit = {
                name: bool(groups & retrieved_groups)
                for name, groups in KEY_GROUPS.items()
            }
            field_values = list(all_field_values(result))
            answered = [
                (path, item)
                for path, item in field_values
                if not item.missing and bool((item.content or "").strip())
            ]
            cited = [(path, item) for path, item in answered if item.sources]
            answered_count = sum(value["answered"] for value in field_results.values())
            row.update(
                {
                    "status": "completed",
                    "identity": identity,
                    "identity_check": identity_check,
                    "identity_resolution_pct": 100.0 if identity_ok else 0.0,
                    "retrieved_chunk_count": len(debug.get("retrieved_chunks", [])),
                    "retrieval_group_counts": debug.get("retrieval_group_counts", {}),
                    "key_retrieval_coverage_pct": percentage(sum(group_hit.values()), len(group_hit)),
                    "key_answer_coverage_pct": percentage(answered_count, len(field_results)),
                    "answered_key_fields": [
                        name for name, value in field_results.items() if value["answered"]
                    ],
                    "missing_key_fields": [
                        name for name, value in field_results.items() if not value["answered"]
                    ],
                    "key_citation_coverage_pct": percentage(
                        sum(
                            value["citation_attached"]
                            for value in field_results.values()
                            if value["answered"]
                        ),
                        answered_count,
                    ),
                    "all_schema_field_answer_coverage_pct": percentage(
                        len(answered), len(field_values)
                    ),
                    "all_answered_field_citation_pct": percentage(len(cited), len(answered)),
                    "answered_field_count": len(answered),
                    "fieldvalue_count": len(field_values),
                    "reference_count": len(result.references.sources),
                    "schema_valid_pct": 100.0,
                    "duration_seconds": round(time.monotonic() - started, 1),
                }
            )
        except Exception as exc:
            row.update(
                {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:700],
                    "duration_seconds": round(time.monotonic() - started, 1),
                }
            )
        report["cases"].append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        report_path = Path(__file__).resolve().parents[2] / "data" / "named_query_model_test_2026-10-24.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    completed = [case for case in report["cases"] if case.get("status") == "completed"]
    answered_key_fields = sum(len(case.get("answered_key_fields", [])) for case in completed)
    schema_fields = sum(case.get("fieldvalue_count", 0) for case in completed)
    answered_schema_fields = sum(case.get("answered_field_count", 0) for case in completed)
    cited_schema_fields = sum(
        round(case.get("all_answered_field_citation_pct", 0) * case.get("answered_field_count", 0) / 100)
        for case in completed
    )
    report["summary"] = {
        "completed_queries_pct": percentage(len(completed), len(CASES)),
        "identity_resolution_pct": percentage(
            sum(case.get("identity_resolution_pct", 0) == 100 for case in completed), len(completed)
        ),
        "retrieval_group_presence_pct": round(
            sum(case.get("key_retrieval_coverage_pct", 0) for case in completed) / len(completed), 1
        ) if completed else 0.0,
        "key_answer_coverage_pct": percentage(answered_key_fields, len(completed) * len(KEY_GROUPS)),
        "key_citation_coverage_pct": percentage(
            sum(
                round(case.get("key_citation_coverage_pct", 0) * len(case.get("answered_key_fields", [])) / 100)
                for case in completed
            ),
            answered_key_fields,
        ),
        "schema_field_answer_coverage_pct": percentage(answered_schema_fields, schema_fields),
        "answered_schema_field_citation_pct": percentage(cited_schema_fields, answered_schema_fields),
        "valid_structured_output_pct": percentage(len(completed), len(CASES)),
    }
    report_path = Path(__file__).resolve().parents[2] / "data" / "named_query_model_test_2026-10-24.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"REPORT_SAVED {report_path}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
