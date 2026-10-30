"""Offline document regressions using real PDF extraction and an isolated Chroma collection."""
import io
import os
import tempfile
import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import chromadb
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from ingest import pdf_ingest
from rag.chat import answer_chat_question, format_chat_citations
from rag.retriever import Retriever, _resolve_chroma_path


def pdf_bytes(*pages):
    writer = PdfWriter()
    for text in pages:
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


class DocumentTests(unittest.TestCase):
    def test_explicit_new_database_path_never_falls_back_to_existing_data(self):
        path = os.path.join(self.directory.name, "new-database")
        with patch.dict(os.environ, {"CHROMA_PATH": path}):
            self.assertEqual(_resolve_chroma_path(), path)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.client = chromadb.EphemeralClient(settings=chromadb.config.Settings(anonymized_telemetry=False))
        self.retriever = Retriever.__new__(Retriever)
        self.retriever.collection = self.client.create_collection(f"test-{uuid.uuid4().hex}")
        self.addCleanup(self.client.delete_collection, self.retriever.collection.name)
        self.addCleanup(self.directory.cleanup)
        self.patches = [
            patch.dict(os.environ, {"PHARMIND_DOCUMENT_PATH": self.directory.name}),
            patch.object(pdf_ingest, "get_retriever", return_value=self.retriever),
            patch.object(pdf_ingest, "embed_batch_local", side_effect=lambda texts: [[1., 0., 0.] for _ in texts]),
            patch("rag.retriever._embed", return_value=[1., 0., 0.]),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def ingest(self, content, name="paper.pdf", drug="", replace=None):
        return pdf_ingest._ingest_pdf(content, name, "custom", drug, replace)

    def test_selected_document_isolates_same_named_and_untagged_papers(self):
        first = self.ingest(pdf_bytes("Aspirin first result"))
        second = self.ingest(pdf_bytes("Unrelated result"))
        self.assertNotEqual(first["document_id"], second["document_id"])
        chunks = self.retriever._retrieve("result", document_id=first["document_id"])
        self.assertEqual([chunk["text"] for chunk in chunks], ["Aspirin first result"])

    def test_compound_retrieval_excludes_unrelated_custom_pdfs(self):
        self.ingest(pdf_bytes("Aspirin result"), drug="aspirin")
        self.ingest(pdf_bytes("Warfarin result"), drug="warfarin")
        chunks = self.retriever._retrieve("result", pubchem_cid="2244", drug_name="aspirin", include_custom_pdf=True)
        self.assertEqual([chunk["drug"] for chunk in chunks], ["aspirin"])

    def test_shorter_replacement_removes_old_pages_and_original(self):
        old = self.ingest(pdf_bytes("First page", "Obsolete second page"))
        old_file = pdf_ingest.get_document_file(old["document_id"])
        new_bytes = pdf_bytes("Replacement page")
        new = self.ingest(new_bytes, replace=old["document_id"])
        self.assertEqual(new["document_id"], old["document_id"])
        self.assertEqual(self.retriever.collection.count(), 1)
        self.assertEqual(pdf_ingest.get_document_file(new["document_id"]).read_bytes(), new_bytes)
        self.assertFalse(old_file.exists())
        self.assertEqual(pdf_ingest._list_pdfs()[0]["pages"], 1)

    def test_failed_replacement_preserves_original(self):
        old = self.ingest(pdf_bytes("Original paper"))
        with self.assertRaises(ValueError):
            self.ingest(b"not a PDF", replace=old["document_id"])
        self.assertEqual(self.retriever.collection.count(), 1)
        self.assertIsNotNone(pdf_ingest.get_document_file(old["document_id"]))

    def test_identical_upload_is_idempotent_and_delete_uses_id(self):
        content = pdf_bytes("First result")
        first = self.ingest(content)
        self.ingest(content)
        second = self.ingest(pdf_bytes("Second result"))
        self.assertEqual(self.retriever.collection.count(), 2)
        self.assertTrue(pdf_ingest._delete_pdf(first["document_id"])["success"])
        self.assertIsNone(pdf_ingest.get_document_file(first["document_id"]))
        self.assertIsNotNone(pdf_ingest.get_document_file(second["document_id"]))

    def test_scanned_encrypted_and_oversize_files_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "OCR"):
            self.ingest(pdf_bytes(""))
        writer = PdfWriter(); writer.add_blank_page(width=10, height=10); writer.encrypt("password")
        output = io.BytesIO(); writer.write(output)
        with self.assertRaisesRegex(ValueError, "Unlock"):
            self.ingest(output.getvalue())
        with patch.object(pdf_ingest, "MAX_PDF_BYTES", 10), self.assertRaisesRegex(ValueError, "20 MB"):
            self.ingest(pdf_bytes("Large"))

    def test_original_endpoint_serves_pdf_and_returns_404_after_delete(self):
        from fastapi.testclient import TestClient
        from main import app
        content = pdf_bytes("Original")
        document = self.ingest(content)
        with TestClient(app) as client:
            url = f"/documents/{document['document_id']}/file"
            response = client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, content)
            self.assertEqual(response.headers["content-type"], "application/pdf")
            pdf_ingest._delete_pdf(document["document_id"])
            self.assertEqual(client.get(url).status_code, 404)


class CitationTests(unittest.TestCase):
    def test_pdf_marker_keeps_passage_page_and_trusted_link(self):
        text, sources = format_chat_citations("Finding [SOURCE_2](https://invented.test). Unknown [SOURCE_99].", {
            "SOURCE_2": {"source": "Uploaded paper (p.3)", "text": "Evidence passage", "document_id": "abc", "page": 3, "original_available": True},
        })
        self.assertIn("[1]", text)
        self.assertNotIn("SOURCE_99", text)
        self.assertNotIn("invented.test", text)
        self.assertEqual(sources[0]["url"], "/api/documents/abc/file#page=3")
        self.assertEqual(sources[0]["text"], "Evidence passage")

    def test_uncited_passages_are_not_claimed_as_citations(self):
        text, sources = format_chat_citations("A summary without citations.", {"SOURCE_1": {"source": "PDF", "text": "Passage"}})
        self.assertNotIn("[1]", text)
        self.assertFalse(sources[0]["cited"])
        self.assertEqual(sources[0]["url"], "")

    def test_mixed_case_repeated_labels_have_one_number(self):
        text, sources = format_chat_citations("A [source_1]. B [SOURCE_1].", {"SOURCE_1": {"source": "PDF"}})
        self.assertEqual(len(sources), 1)
        self.assertEqual(text.count("[1]"), 2)


class PaperChatTests(unittest.IsolatedAsyncioTestCase):
    async def test_selected_paper_overrides_stale_compound_and_skips_online_search(self):
        retriever = MagicMock()
        retriever.collection.get.return_value = {"ids": ["chunk"], "metadatas": [{"drug": "aspirin"}]}
        retriever.retrieve = AsyncMock(return_value=[{"text": "Selected paper evidence", "source": "trial.pdf p.1", "document_id": "paper-1", "page": 1}])
        with patch("rag.chat.get_retriever", return_value=retriever), \
             patch("rag.chat.sources_enabled", return_value=True), \
             patch("rag.chat.rerank_passages", side_effect=lambda query, chunks, top_k: chunks), \
             patch("rag.chat.generate_chat_response", new_callable=AsyncMock, return_value="Finding [SOURCE_1].") as llm, \
             patch("ingest.pubmed.search_pubmed", new_callable=AsyncMock) as online:
            answer, sources = await answer_chat_question("Summarize", active_drug={"name": "warfarin", "cid": "123"}, document_id="paper-1")
        self.assertEqual(retriever.retrieve.await_args.kwargs["document_id"], "paper-1")
        self.assertIsNone(retriever.retrieve.await_args.kwargs["pubchem_cid"])
        self.assertIn("Active compound: aspirin", llm.await_args.args[0])
        self.assertIn("[1]", answer)
        self.assertEqual(sources[0]["document_id"], "paper-1")
        online.assert_not_awaited()

    async def test_paper_mode_requires_an_explicit_selection(self):
        with patch("rag.chat.get_retriever") as factory:
            answer, sources = await answer_chat_question("Summarize the methods", mode="paper_learning")
            self.assertIn("Select a paper", answer)
            self.assertEqual(sources, [])
            factory.assert_not_called()

    async def test_missing_selected_paper_never_falls_back_to_other_documents(self):
        with patch("rag.chat.get_retriever") as factory, patch("rag.chat.generate_chat_response", new_callable=AsyncMock) as llm:
            factory.return_value.collection.get.return_value = {"ids": []}
            answer, sources = await answer_chat_question("What were the findings?", document_id="missing")
            self.assertIn("no longer", answer)
            self.assertEqual(sources, [])
            llm.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
