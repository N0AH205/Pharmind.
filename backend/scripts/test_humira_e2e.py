import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.pipeline import resolve_query_structure, run_pipeline
from rag.retriever import get_retriever

async def test_humira():
    print("=" * 60)
    print("Testing End-to-End Retrieval for 'Humira'")
    print("=" * 60)

    # 1. Test identity resolution
    print("\n[1] Resolving identity for 'Humira'...")
    structure = await resolve_query_structure("Humira")
    print(f"  Common Name    : {structure.get('common_name')}")
    print(f"  Brand Names    : {structure.get('brand_names')}")
    print(f"  Drug Type      : {structure.get('drug_type')}")
    print(f"  Biologic Class : {structure.get('biologic_class')}")
    print(f"  Primary Target : {structure.get('target')}")

    assert structure.get("common_name") == "adalimumab", f"Expected adalimumab, got {structure.get('common_name')}"
    assert structure.get("drug_type") == "biologic", f"Expected biologic, got {structure.get('drug_type')}"

    # 2. Test full pipeline debug run
    print("\n[2] Running full pipeline with debug=True for 'Humira'...")
    res = await run_pipeline("Humira", debug=True)
    drug_info = res["result"]
    debug_info = res["debug"]

    print(f"\n[3] Pipeline Results Summary:")
    print(f"  Total Chunks Retrieved: {len(debug_info.get('retrieved_chunks', []))}")
    print(f"  Chunk Sources Map Count: {len(debug_info.get('source_map_keys', []))}")
    print(f"  Retrieval Groups: {debug_info.get('retrieval_group_counts', {})}")

    # Inspect key fields
    info_dict = drug_info.model_dump() if hasattr(drug_info, "model_dump") else drug_info
    pd = info_dict.get("pharmacodynamics", {})
    tp = info_dict.get("therapeutic_profile", {})
    hist = info_dict.get("history", {})

    print("\n[4] Section Verification:")
    print(f"  MOA Missing? {(pd.get('mechanism_of_action') or {}).get('missing')}")
    print(f"  MOA Content Preview: {str((pd.get('mechanism_of_action') or {}).get('content'))[:140]}...")
    print(f"  Indications Missing? {(tp.get('indications') or {}).get('missing')}")
    print(f"  Indications Preview: {str((tp.get('indications') or {}).get('content'))[:140]}...")
    print(f"  Adverse Effects Missing? {(tp.get('adverse_effects') or {}).get('missing')}")
    print(f"  Clinical Trials Missing? {(hist.get('clinical_trials') or {}).get('missing')}")
    print(f"  Clinical Trials Preview: {str((hist.get('clinical_trials') or {}).get('content'))[:140]}...")

    print("\n" + "=" * 60)
    print("HUMIRA E2E TEST PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_humira())
