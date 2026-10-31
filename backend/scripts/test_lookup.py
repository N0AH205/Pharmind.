import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import chromadb

from ingest.pubmed import mentions_identity
from ingest.dailymed import _parse_spl_xml
from rag.lookup import build_overview, identity_suggestions, lookup_stream
from rag.retriever import Retriever


STRUCTURE = {"common_name": "Triazolam", "pubchem_cid": 5556, "smiles": "CC"}
CHUNK = {"text": "Triazolam is used for insomnia.", "source": "DailyMed: Test label", "url": "https://example.org/label", "field": "indications", "pubchem_cid": "5556"}


class LookupTests(unittest.IsolatedAsyncioTestCase):
    async def test_educational_mechanism_question_does_not_use_unreliable_classifier(self):
        from rag.safety import check_query_safety
        with patch("rag.safety.generate_structured_output") as model:
            safe, _ = await check_query_safety("Explain triazolam's mechanism in two sentences.")
        self.assertTrue(safe)
        model.assert_not_called()

    async def test_patient_specific_advice_is_rejected_before_generation(self):
        from rag.safety import check_query_safety
        with patch("rag.safety.generate_structured_output") as model:
            safe, _ = await check_query_safety("Can I take triazolam for my insomnia?")
        self.assertFalse(safe)
        model.assert_not_called()

    def test_label_section_codes_do_not_mix_description_with_pharmacology(self):
        sections = {"34089-3": "description", "34090-1": "clinical_pharmacology", "34088-5": "overdosage", "34092-7": "clinical_studies", "34069-5": "how_supplied", "43684-0": "use_in_specific_populations", "34066-1": "boxed_warning"}
        xml = '<document xmlns="urn:hl7-org:v3">' + ''.join(f'<section><code code="{code}"/><text>{name}</text></section>' for code, name in sections.items()) + '</document>'
        self.assertEqual(_parse_spl_xml(xml), {name: name for name in sections.values()})

    def test_label_parent_collects_nested_unclassified_narrative(self):
        xml = '<document xmlns="urn:hl7-org:v3"><section><code code="43682-4"/><component><section><code code="42229-5"/><text>Example half-life is reported here.</text></section></component></section></document>'
        self.assertEqual(_parse_spl_xml(xml)["pharmacokinetics"], "Example half-life is reported here.")

    def test_spelling_suggestion_requires_confirmation(self):
        self.assertIn({"query": "Triazolam", "label": "Triazolam (halcion)"}, identity_suggestions("halicon"))

    def test_identity_matching_requires_whole_names(self):
        self.assertTrue(mentions_identity("HALCION (triazolam) tablets", ["Triazolam"]))
        self.assertFalse(mentions_identity("Unrelated pharmacology review", ["halicon"]))
        self.assertFalse(mentions_identity("nottriazolam", ["triazolam"]))

    async def test_unresolved_identity_never_starts_retrieval_or_generation(self):
        with patch("rag.lookup.resolve_query_structure", AsyncMock(return_value={"common_name": "halicon"})), patch("rag.lookup.get_retriever") as retriever, patch("rag.llm.generate_structured_output_stream") as model:
            events = [event async for event in lookup_stream("halicon")]
        self.assertEqual(events[-1]["type"], "clarification")
        self.assertEqual(events[-1]["suggestions"][0]["query"], "Triazolam")
        retriever.assert_not_called()
        model.assert_not_called()

    async def test_no_evidence_never_prompts_model(self):
        retriever = MagicMock(retrieve=AsyncMock(return_value=[]))
        with patch("rag.lookup.resolve_query_structure", AsyncMock(return_value=STRUCTURE)), patch("rag.lookup.get_retriever", return_value=retriever), patch("rag.lookup.sources_enabled", return_value=False), patch("rag.llm.generate_structured_output_stream") as model:
            events = [event async for event in lookup_stream("triazolam")]
        self.assertEqual(events[-1]["type"], "clarification")
        model.assert_not_called()

    async def test_lookup_returns_cited_source_excerpts_without_model_generation(self):
        retriever = MagicMock(retrieve=AsyncMock(return_value=[CHUNK]))
        with patch("rag.lookup.resolve_query_structure", AsyncMock(return_value=STRUCTURE)), patch("rag.lookup.get_retriever", return_value=retriever), patch("rag.lookup.sources_enabled", return_value=False), patch("rag.llm.generate_structured_output_stream") as model:
            events = [event async for event in lookup_stream("triazolam")]
        self.assertEqual(events[-1]["type"], "result")
        model.assert_not_called()
        field = events[-1]["data"]["therapeutic_profile"]["indications"]["summary"]
        self.assertFalse(field["missing"])
        self.assertEqual(field["sources"][0]["text"], CHUNK["text"])
        self.assertEqual(field["content"], CHUNK["text"])

    def test_unchecked_fields_are_not_reported_as_facts(self):
        overview = build_overview("triazolam", STRUCTURE, {"SOURCE_1": CHUNK})
        self.assertTrue(overview.pharmacodynamics.mechanism_of_action.missing)
        self.assertTrue(overview.therapeutic_profile.pharmacogenomics.missing)
        self.assertEqual(overview.therapeutic_profile.regulatory_status.indonesia.status, "Not evaluated")
        self.assertEqual(overview.drug_overview.identity.brand_names, [])

    def test_unverified_automatic_imports_are_excluded_without_deleting_pdfs(self):
        client = chromadb.EphemeralClient(settings=chromadb.config.Settings(anonymized_telemetry=False))
        retriever = Retriever.__new__(Retriever)
        retriever.collection = client.create_collection(f"lookup-{uuid.uuid4().hex}")
        self.addCleanup(client.delete_collection, retriever.collection.name)
        retriever.collection.add(ids=["wrong", "pdf", "verified"], documents=["Unrelated abstract", "User paper", "Verified label"], embeddings=[[1., 0., 0.]] * 3, metadatas=[
            {"drug": "halicon", "pubchem_cid": "", "field": "moa"},
            {"drug": "halicon", "pubchem_cid": "custom", "field": "research"},
            {"drug": "halicon", "pubchem_cid": "", "field": "moa", "identity_verified": True},
        ])
        with patch("rag.retriever._embed", return_value=[1., 0., 0.]):
            chunks = retriever._retrieve("mechanism", drug_name="halicon", include_custom_pdf=True)
        self.assertEqual({chunk["text"] for chunk in chunks}, {"User paper", "Verified label"})
        self.assertEqual(retriever.collection.count(), 3)


if __name__ == "__main__":
    unittest.main()
