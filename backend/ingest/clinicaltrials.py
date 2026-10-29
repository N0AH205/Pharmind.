"""ClinicalTrials.gov API v2 ingestion for registered study evidence."""

from __future__ import annotations

import httpx
from rag.config import require_network_allowed

API_URL = "https://clinicaltrials.gov/api/v2/studies"


def _module(study: dict, name: str) -> dict:
    return study.get("protocolSection", {}).get(name, {})


async def search_drug_trials(drug_name: str, limit: int = 15, strict: bool = False) -> list[dict]:
    """Fetch concise, attributable trial records mentioning a drug intervention."""
    require_network_allowed("ClinicalTrials.gov study search")
    params = {
        "query.intr": drug_name,
        "pageSize": min(max(limit, 1), 100),
        "format": "json",
        "countTotal": "false",
    }
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(API_URL, params=params)
            response.raise_for_status()
            studies = response.json().get("studies", [])
    except (httpx.HTTPError, ValueError):
        if strict:
            raise
        return []

    records = []
    for study in studies:
        ident = _module(study, "identificationModule")
        status = _module(study, "statusModule")
        design = _module(study, "designModule")
        desc = _module(study, "descriptionModule")
        arms = _module(study, "armsInterventionsModule")
        outcomes = _module(study, "outcomesModule")
        results = study.get("resultsSection", {})
        eligibility = _module(study, "eligibilityModule")
        nct_id = ident.get("nctId")
        if not nct_id:
            continue

        def outcome_lines(key: str) -> list[str]:
            return [
                f"{item.get('measure', '')}: {item.get('description', '')}".strip(": ")
                for item in outcomes.get(key, [])
                if item.get("measure") or item.get("description")
            ]

        intervention_lines = []
        for item in arms.get("interventions", []):
            label = item.get("name", "Intervention")
            kind = item.get("type")
            detail = item.get("description")
            intervention_lines.append(" — ".join(x for x in (label, kind, detail) if x))

        reported_results = []
        for result_group in results.get("outcomeMeasures", []):
            measure = result_group.get("title", "Outcome")
            for analysis in result_group.get("analyses", []):
                result_text = "; ".join(
                    f"{key}: {analysis[key]}" for key in (
                        "description", "paramType", "paramValue", "pValue",
                        "ciPctValue", "ciLowerLimit", "ciUpperLimit",
                    ) if analysis.get(key) not in (None, "")
                )
                if result_text:
                    reported_results.append(f"{measure}: {result_text}")

        parts = [
            f"Study: {ident.get('briefTitle') or ident.get('officialTitle', 'Untitled study')}",
            f"NCT ID: {nct_id}",
            f"Study type: {design.get('studyType', 'Not reported')}",
            f"Phase: {', '.join(design.get('phases', [])) or 'Not reported'}",
            f"Status: {status.get('overallStatus', 'Not reported')}",
            f"Study summary: {desc.get('briefSummary', 'Not reported')}",
            f"Interventions: {'; '.join(intervention_lines) or 'Not reported'}",
            f"Primary outcomes: {'; '.join(outcome_lines('primaryOutcomes')) or 'Not reported'}",
            f"Secondary outcomes: {'; '.join(outcome_lines('secondaryOutcomes')) or 'Not reported'}",
            f"Posted outcome results (when reported): {'; '.join(reported_results) or 'No tabular result summary available in this record'}",
            f"Enrollment: {design.get('enrollmentInfo', {}).get('count', 'Not reported')} ({design.get('enrollmentInfo', {}).get('type', 'type not reported')})",
            f"Eligibility: {eligibility.get('eligibilityCriteria', 'Not reported')}",
            f"First posted: {status.get('studyFirstPostDateStruct', {}).get('date', 'Not reported')}",
            f"Last updated: {status.get('studyLastUpdatePostDateStruct', {}).get('date', 'Not reported')}",
        ]
        records.append({
            "nct_id": nct_id,
            "title": ident.get("briefTitle") or ident.get("officialTitle") or nct_id,
            "text": "\n".join(parts),
            "url": f"https://clinicaltrials.gov/study/{nct_id}",
            "publication_date": status.get("studyLastUpdatePostDateStruct", {}).get("date", ""),
        })
    return records
