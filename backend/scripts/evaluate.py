"""
RAG Pipeline Evaluation Script — Phase 4.

Queries the live RAG pipeline for all benchmark drugs, evaluates the results
against gold-standard reference data using schema, citation, keyword matching,
and LLM-assisted scoring, and saves a performance report.

Usage:
    cd backend
    .venv\\Scripts\\python -m scripts.evaluate
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
import asyncio
from datetime import datetime
from pydantic import BaseModel, Field

# Ensure backend directory is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from rag.pipeline import run_pipeline, retrieve_field_evidence
from rag.schema import DrugInfo
from rag.llm import LLM_PROVIDER, OLLAMA_MODEL, OPENAI_MODEL, ANTHROPIC_MODEL, GEMINI_MODEL, generate_structured_output
from rag.retriever import get_retriever
from ingest.local_chem import enrich_structure_local

MODEL_NAME = {
    "ollama": OLLAMA_MODEL,
    "openai": OPENAI_MODEL,
    "anthropic": ANTHROPIC_MODEL,
    "gemini": GEMINI_MODEL,
}.get(LLM_PROVIDER, "unknown")

# Console formatting
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"

# Paths
GOLD_STANDARD_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "gold_standard.json",
)
REPORT_OUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "evaluation_report.json",
)


# Pydantic model for LLM-assisted evaluation schema
class EvalMetrics(BaseModel):
    correctness_score: int | None = Field(
        ...,
        description="Factual correctness and detail recall score (0 to 100) compared to the gold standard.",
    )
    hallucination_score: int | None = Field(
        ...,
        description="Score indicating presence of unsupported or fabricated facts (0 to 100, where 0 is perfect and 100 means highly hallucinated/fabricated).",
    )
    rationale: str = Field(
        ...,
        description="Explanation and specific observations supporting the scores.",
    )


async def call_llm_evaluator(
    drug_name: str, field_name: str, generated_text: str, gold_standard_text: str
) -> EvalMetrics:
    """Audit a generated field with the configured provider."""

    system_prompt = (
        "You are an expert pharmaceutical research auditor. Your task is to evaluate RAG-generated drug summaries "
        "against the gold-standard reference facts. You must output a JSON object containing correctness_score, "
        "hallucination_score, and a detailed rationale."
    )

    user_message = f"""
Drug: {drug_name}
Field: {field_name}

---
[GOLD STANDARD FACTS]
{gold_standard_text}

---
[GENERATED TEXT]
{generated_text}

---
Evaluation Rules:
1. Correctness Score (0-100): Measure how much of the gold standard clinical facts, values, or mechanisms were successfully captured. 100 means all facts are present.
2. Hallucination Score (0-100): Measure if the generated text adds clinical details, claims, values, or enzymes that are NOT listed or supported in the gold standard facts. 0 means no hallucinations/unsupported details.
3. Rationale: Briefly explain your scores.
"""

    try:
        raw = await generate_structured_output(system_prompt, user_message, EvalMetrics)
        return EvalMetrics(**raw)
    except Exception as exc:
        return EvalMetrics(correctness_score=None, hallucination_score=None, rationale=f"Configured model evaluator failed: {exc}")


def _field_values(value, prefix=""):
    """Yield every FieldValue-shaped object from a serialized DrugInfo."""
    if isinstance(value, dict):
        if {"content", "missing", "sources"}.issubset(value):
            yield prefix, value
            return
        for key, child in value.items():
            yield from _field_values(child, f"{prefix}.{key}" if prefix else key)


def _retrieval_recall(gold_data: dict, chunks: list[dict]) -> dict:
    """Keyword recall proxy against retrieved passages; not semantic relevance."""
    terms = []

    def collect(value):
        if isinstance(value, list):
            terms.extend(str(item) for item in value)
        elif isinstance(value, dict):
            for child in value.values():
                collect(child)

    for key, value in gold_data.items():
        if key not in {"smiles", "generic"}:
            collect(value)
    corpus = " ".join(chunk.get("text", "") for chunk in chunks).lower()
    matched = [term for term in terms if term.lower() in corpus]
    return {
        "keyword_recall_proxy": round(100 * len(matched) / len(terms), 1) if terms else 0.0,
        "matched_terms": matched,
        "expected_term_count": len(terms),
    }


def evaluate_field(
    drug_name: str,
    field_name: str,
    generated_content: str | None,
    is_missing: bool,
    expected_keywords: list[str],
) -> dict:
    """Evaluate a single field using keyword matching."""
    if is_missing or not generated_content:
        return {
            "keyword_score": 0.0,
            "matched_keywords": [],
            "missing_keywords": expected_keywords,
            "length": 0,
        }

    content_lower = generated_content.lower()
    matched = []
    missing = []

    for kw in expected_keywords:
        if kw.lower() in content_lower:
            matched.append(kw)
        else:
            missing.append(kw)

    keyword_score = (len(matched) / len(expected_keywords) * 100) if expected_keywords else 100.0

    return {
        "keyword_score": round(keyword_score, 1),
        "matched_keywords": matched,
        "missing_keywords": missing,
        "length": len(generated_content),
    }


async def evaluate_drug(drug_key: str, gold_data: dict, llm_eval_enabled: bool = False) -> dict:
    """Run pipeline and evaluate generated profile against gold standard reference."""
    smiles = gold_data["smiles"]
    print(f"Querying RAG pipeline for {BOLD}{drug_key.upper()}{RESET} ({smiles}) ...")

    start_time = datetime.now()
    max_retries = 5
    delay = 3.0
    res = None
    schema_compliance = 100
    for i in range(max_retries):
        try:
            pipeline_out = await run_pipeline(smiles, debug=True)
            res = pipeline_out["result"]
            debug_info = pipeline_out.get("debug", {})
            retrieved_chunks = debug_info.get("retrieved_chunks", [])
            break
        except Exception as exc:
            if ("429" in str(exc) or "too many requests" in str(exc).lower()) and i < max_retries - 1:
                print(f"  {YELLOW}RAG query rate limited. Retrying in {delay:.1f}s...{RESET}")
                await asyncio.sleep(delay)
                delay *= 2
            else:
                print(f"  {RED}✗ RAG pipeline query failed: {exc}{RESET}")
                return {
                    "drug": drug_key,
                    "success": False,
                    "error": str(exc),
                    "schema_compliance": 0,
                    "overall_score": 0.0,
                }
    duration_sec = (datetime.now() - start_time).total_seconds()

    # Measure retrieval recall proxy over the evidence presented to the model
    if not retrieved_chunks:
        structure_data = await enrich_structure_local(smiles)
        cid = str(structure_data.get("pubchem_cid") or "") or None
        retrieved_chunks = await retrieve_field_evidence(
            structure_data,
            get_retriever(),
            cid,
            str(structure_data.get("common_name") or structure_data.get("iupac_name") or "").strip() or None,
        )
    retrieval_metrics = _retrieval_recall(gold_data, retrieved_chunks)

    if res is None:
        print(f"  {RED}✗ RAG pipeline query failed: rate limit exceeded after {max_retries} attempts.{RESET}")
        return {
            "drug": drug_key,
            "success": False,
            "error": "Rate limit exceeded (429)",
            "schema_compliance": 0,
            "overall_score": 0.0,
        }

    # Gather fields to evaluate
    fields_to_evaluate = {
        "mechanism_of_action": {
            "gen": res.pharmacodynamics.mechanism_of_action.content,
            "missing": res.pharmacodynamics.mechanism_of_action.missing,
            "sources": res.pharmacodynamics.mechanism_of_action.sources,
            "gold": gold_data["mechanism_of_action"],
        },
        "indications": {
            "gen": res.therapeutic_profile.indications.content,
            "missing": res.therapeutic_profile.indications.missing,
            "sources": res.therapeutic_profile.indications.sources,
            "gold": gold_data["indications"],
        },
        "contraindications": {
            "gen": res.therapeutic_profile.contraindications.content,
            "missing": res.therapeutic_profile.contraindications.missing,
            "sources": res.therapeutic_profile.contraindications.sources,
            "gold": gold_data["contraindications"],
        },
        "absorption": {
            "gen": res.adme.absorption.content,
            "missing": res.adme.absorption.missing,
            "sources": res.adme.absorption.sources,
            "gold": gold_data["adme"]["absorption"],
        },
        "distribution": {
            "gen": res.adme.distribution.content,
            "missing": res.adme.distribution.missing,
            "sources": res.adme.distribution.sources,
            "gold": gold_data["adme"]["distribution"],
        },
        "metabolism": {
            "gen": res.adme.metabolism.content,
            "missing": res.adme.metabolism.missing,
            "sources": res.adme.metabolism.sources,
            "gold": gold_data["adme"]["metabolism"],
        },
        "excretion": {
            "gen": res.adme.excretion.content,
            "missing": res.adme.excretion.missing,
            "sources": res.adme.excretion.sources,
            "gold": gold_data["adme"]["excretion"],
        },
    }
    retrieval_groups_by_field = {
        "mechanism_of_action": {"moa"},
        "indications": {"indications"},
        "contraindications": {"safety", "interactions"},
        "absorption": {"adme"},
        "distribution": {"adme"},
        "metabolism": {"adme"},
        "excretion": {"adme"},
    }

    # Evaluate each field
    evaluated_fields = {}
    citation_checks = []

    for f_name, data in fields_to_evaluate.items():
        gen_text = data["gen"]
        is_missing = data["missing"]
        sources = data["sources"]
        gold_kws = data["gold"]

        # 1. Keyword check
        field_eval = evaluate_field(drug_key, f_name, gen_text, is_missing, gold_kws)
        groups = retrieval_groups_by_field[f_name]
        field_chunks = [
            chunk for chunk in retrieved_chunks
            if groups.intersection(chunk.get("retrieval_groups", [chunk.get("retrieval_group", "")]))
        ]
        field_retrieval_text = " ".join(chunk.get("text", "") for chunk in field_chunks)
        retrieved_terms = [term for term in gold_kws if term.lower() in field_retrieval_text.lower()]
        field_eval["retrieval_keyword_recall"] = round(
            100 * len(retrieved_terms) / len(gold_kws), 1
        ) if gold_kws else 100.0
        field_eval["retrieved_gold_terms"] = retrieved_terms
        field_eval["retrieved_passage_count"] = len(field_chunks)

        # 2. Citation check
        if not is_missing and gen_text:
            has_sources = len(sources) > 0 and all(src.source and src.text for src in sources)
            citation_checks.append(100 if has_sources else 0)
        else:
            has_sources = True  # Missing fields don't need citations

        # 3. LLM evaluation check
        if llm_eval_enabled:
            gold_summary = ", ".join(gold_kws)
            llm_eval = await call_llm_evaluator(
                drug_key, f_name, gen_text or "Data unavailable / missing.", gold_summary
            )
            correctness = llm_eval.correctness_score
            hallucination = llm_eval.hallucination_score
            rationale = llm_eval.rationale
        else:
            correctness = None
            hallucination = None
            rationale = "LLM evaluation disabled (run with --llm-eval to enable)"

        field_eval.update({
            "has_sources": has_sources,
            "sources_count": len(sources),
            "correctness_score": correctness,
            "hallucination_score": hallucination,
            "rationale": rationale,
        })

        evaluated_fields[f_name] = field_eval

    citation_score = (sum(citation_checks) / len(citation_checks)) if citation_checks else 100.0

    serialized = res.model_dump()
    all_fields = list(_field_values(serialized))
    populated_fields = [(path, value) for path, value in all_fields if not value.get("missing") and value.get("content")]
    coverage_score = round(100 * len(populated_fields) / len(all_fields), 1) if all_fields else 0.0
    citation_evidence_score = round(
        100 * sum(bool(field.get("sources")) and all(src.get("source") and src.get("text") for src in field["sources"]) for _, field in populated_fields) / len(populated_fields),
        1,
    ) if populated_fields else 100.0

    # Calculate aggregate metrics
    kw_scores = [f["keyword_score"] for f in evaluated_fields.values()]
    avg_keyword_score = sum(kw_scores) / len(kw_scores) if kw_scores else 0.0

    corr_scores = [f["correctness_score"] for f in evaluated_fields.values() if isinstance(f["correctness_score"], int)]
    avg_correctness_score = sum(corr_scores) / len(corr_scores) if corr_scores else None

    hall_scores = [f["hallucination_score"] for f in evaluated_fields.values() if isinstance(f["hallucination_score"], int)]
    avg_hallucination_score = sum(hall_scores) / len(hall_scores) if hall_scores else None

    # Only report an overall quality score when factual correctness and hallucination were audited.
    if llm_eval_enabled and avg_correctness_score is not None and avg_hallucination_score is not None:
        overall_score = ((avg_correctness_score or 0.0) + (100.0 - avg_hallucination_score)) / 2.0
    else:
        overall_score = None
    field_retrieval_scores = [field["retrieval_keyword_recall"] for field in evaluated_fields.values()]
    avg_field_retrieval_recall = (
        sum(field_retrieval_scores) / len(field_retrieval_scores) if field_retrieval_scores else 0.0
    )

    print(f"  {GREEN}+ Completed evaluation for {drug_key.upper()}{RESET}")
    print(f"    Keyword Recall: {avg_keyword_score:.1f}%")
    correctness_display = f"{avg_correctness_score:.1f}%" if avg_correctness_score is not None else "not evaluated"
    hallucination_display = f"{avg_hallucination_score:.1f}%" if avg_hallucination_score is not None else "not evaluated"
    print(f"    Correctness:    {correctness_display}")
    print(f"    Hallucination:  {hallucination_display}")
    print(f"    Citation Rate:  {citation_score:.1f}%")
    print(f"    Field Coverage: {coverage_score:.1f}%")
    print(f"    Retrieval Recall Proxy: {retrieval_metrics['keyword_recall_proxy']:.1f}%")
    print(f"    Field Retrieval Recall: {avg_field_retrieval_recall:.1f}%")
    overall_display = f"{overall_score:.1f}%" if overall_score is not None else "not scored (enable --llm-eval)"
    print(f"    Overall Quality:  {overall_display}")

    return {
        "drug": drug_key,
        "success": True,
        "duration_sec": round(duration_sec, 2),
        "schema_compliance": schema_compliance,
        "citation_score": round(citation_score, 1),
        "citation_evidence_score": citation_evidence_score,
        "field_coverage_score": coverage_score,
        "field_count": len(all_fields),
        "populated_field_count": len(populated_fields),
        "retrieval_recall": retrieval_metrics,
        "avg_field_retrieval_recall": round(avg_field_retrieval_recall, 1),
        "avg_keyword_score": round(avg_keyword_score, 1),
        "avg_correctness_score": round(avg_correctness_score, 1) if avg_correctness_score is not None else None,
        "avg_hallucination_score": round(avg_hallucination_score, 1) if avg_hallucination_score is not None else None,
        "overall_score": round(overall_score, 1) if overall_score is not None else None,
        "fields": evaluated_fields,
    }


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="PharmaRAG Evaluation Suite")
    parser.add_argument("--llm-eval", action="store_true", help="Enable LLM-assisted evaluation (correctness & hallucination auditing)")
    args = parser.parse_args()

    print("=" * 70)
    print(f"{BOLD}PharmaRAG — RAG Evaluation Suite (Phase 4){RESET}")
    print("=" * 70)

    # 1. Load gold standard
    if not os.path.exists(GOLD_STANDARD_PATH):
        print(f"{RED}Error: Gold standard profiles not found at {GOLD_STANDARD_PATH}{RESET}")
        sys.exit(1)

    with open(GOLD_STANDARD_PATH, "r", encoding="utf-8") as f:
        gold_standards = json.load(f)

    print(f"Loaded {len(gold_standards)} gold-standard drug profiles from database.\n")

    results = []
    for drug_key, gold_data in gold_standards.items():
        res = await evaluate_drug(drug_key, gold_data, llm_eval_enabled=args.llm_eval)
        results.append(res)
        print()

    # 2. Print table report
    print("\n" + "=" * 92)
    print(f"{BOLD}{'Drug':<15} {'Field Ret %':<12} {'Coverage %':<12} {'Citations %':<12} {'Correct %':<10} {'Halluc %':<10} {'Overall %':<10}{RESET}")
    print("-" * 92)

    success_results = [r for r in results if r["success"]]
    for r in results:
        if r["success"]:
            drug_name = r["drug"].upper()
            ret = f"{r['avg_field_retrieval_recall']:.1f}%"
            cov = f"{r['field_coverage_score']:.1f}%"
            cit = f"{r['citation_evidence_score']:.1f}%"
            corr_value = r["avg_correctness_score"]
            corr = f"{corr_value:.1f}%" if corr_value is not None else "N/A"
            hall_value = r["avg_hallucination_score"]
            hall = f"{hall_value:.1f}%" if hall_value is not None else "N/A"
            ovr = f"{r['overall_score']:.1f}%" if r["overall_score"] is not None else "N/A"
            print(f"{drug_name:<15} {ret:<12} {cov:<12} {cit:<12} {corr:<10} {hall:<10} {ovr:<10}")
        else:
            print(f"{r['drug'].upper():<15} {RED}{'FAILED':<77}{RESET}")

    print("-" * 92)

    avg_corr = None
    avg_hall = None
    avg_ovr = None
    avg_global_retrieval = None
    if success_results:
        avg_kw = sum(r["avg_keyword_score"] for r in success_results) / len(success_results)
        scored_corr = [r["avg_correctness_score"] for r in success_results if r["avg_correctness_score"] is not None]
        avg_corr = sum(scored_corr) / len(scored_corr) if scored_corr else None
        scored_hall = [r["avg_hallucination_score"] for r in success_results if r["avg_hallucination_score"] is not None]
        avg_hall = sum(scored_hall) / len(scored_hall) if scored_hall else None
        avg_cit = sum(r["citation_score"] for r in success_results) / len(success_results)
        scored_overall = [r["overall_score"] for r in success_results if r["overall_score"] is not None]
        avg_ovr = sum(scored_overall) / len(scored_overall) if scored_overall else None
        avg_coverage = sum(r["field_coverage_score"] for r in success_results) / len(success_results)
        avg_global_retrieval = sum(r["retrieval_recall"]["keyword_recall_proxy"] for r in success_results) / len(success_results)
        avg_retrieval_recall = sum(r["avg_field_retrieval_recall"] for r in success_results) / len(success_results)
        avg_citation_evidence = sum(r["citation_evidence_score"] for r in success_results) / len(success_results)
        avg_corr_display = f"{avg_corr:.1f}%" if avg_corr is not None else "N/A"
        avg_hall_display = f"{avg_hall:.1f}%" if avg_hall is not None else "N/A"
        avg_ovr_display = f"{avg_ovr:.1f}%" if avg_ovr is not None else "N/A"
        print(f"{BOLD}{'AVERAGE':<15} {avg_retrieval_recall:.1f}%        {avg_coverage:.1f}%        {avg_citation_evidence:.1f}%        {avg_corr_display:<10} {avg_hall_display:<10} {avg_ovr_display}{RESET}")
    print("=" * 92)

    # 3. Save report output
    report_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "model_provider": LLM_PROVIDER,
        "model_evaluated": MODEL_NAME,
        "metric_notes": {
            "avg_overall_score": "Only populated when LLM correctness and hallucination audits run; otherwise null.",
            "retrieval_recall": "Keyword recall proxies are reported separately from answer quality.",
            "field_coverage_score": "Structural profile coverage; not a correctness score.",
        },
        "metrics_average": {
            "avg_keyword_score": round(avg_kw, 1) if success_results else 0,
            "avg_correctness_score": round(avg_corr, 1) if avg_corr is not None else None,
            "avg_hallucination_score": round(avg_hall, 1) if avg_hall is not None else None,
            "avg_citation_score": round(avg_cit, 1) if success_results else 0,
            "avg_overall_score": round(avg_ovr, 1) if avg_ovr is not None else None,
            "avg_field_coverage_score": round(avg_coverage, 1) if success_results else 0,
            "avg_citation_evidence_score": round(avg_citation_evidence, 1) if success_results else 0,
            "avg_retrieval_recall_keyword_proxy": round(avg_global_retrieval, 1) if avg_global_retrieval is not None else None,
            "avg_field_retrieval_recall": round(
                sum(r["avg_field_retrieval_recall"] for r in success_results) / len(success_results), 1
            ) if success_results else 0,
        },
        "drugs_detail": results,
    }

    with open(REPORT_OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    print(f"\nSaved full evaluation report to: {CYAN}{REPORT_OUT_PATH}{RESET}\n")


if __name__ == "__main__":
    asyncio.run(main())
