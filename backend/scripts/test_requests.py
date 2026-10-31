import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from rag.requests import run_until_disconnect
from rag.streaming import stream_events, research_error


class RequestTests(unittest.IsolatedAsyncioTestCase):
    def test_protocol_disconnect_is_reported_as_an_interrupted_connection(self):
        import httpx
        self.assertIn("connection", research_error(httpx.RemoteProtocolError("private details")))
        self.assertNotIn("private details", research_error(httpx.RemoteProtocolError("private details")))

    async def test_model_stream_and_cleanup_stay_in_one_task(self):
        owners = []
        async def events():
            try:
                owners.append(asyncio.current_task())
                yield {"type": "status"}
                await asyncio.sleep(.02)
                owners.append(asyncio.current_task())
                yield {"type": "result"}
            finally:
                owners.append(asyncio.current_task())
        frames = [frame async for frame in stream_events(events(), heartbeat=.005)]
        self.assertTrue(any(frame.startswith(":") for frame in frames))
        self.assertEqual(len(owners), 3)
        self.assertTrue(all(owner is owners[0] for owner in owners))

    async def test_stream_sends_heartbeats_while_work_is_waiting(self):
        complete = asyncio.Event()
        async def events():
            await complete.wait()
            yield {"type": "result", "data": "answer"}
        stream = stream_events(events(), heartbeat=.01, timeout=1)
        self.assertEqual(await anext(stream), ": keep-alive\n\n")
        self.assertFalse(complete.is_set())
        complete.set()
        self.assertIn('"answer"', await anext(stream))
        await stream.aclose()

    async def test_late_stage_exception_becomes_a_terminal_error(self):
        async def events():
            yield {"type": "status", "stage": "review"}
            raise RuntimeError("private research text")
        frames = [frame async for frame in stream_events(events())]
        self.assertIn('"type": "error"', frames[-1])
        self.assertNotIn("private research text", "".join(frames))

    async def test_stream_deadline_cancels_model_and_reports_timeout(self):
        cancelled = asyncio.Event()
        async def events():
            try:
                await asyncio.sleep(10)
                yield {"type": "result"}
            finally:
                cancelled.set()
        frames = [frame async for frame in stream_events(events(), heartbeat=.005, timeout=.02)]
        self.assertIn("15-minute limit", frames[-1])
        self.assertTrue(cancelled.is_set())

    async def test_closed_client_cancels_pending_model_work(self):
        cancelled = asyncio.Event()
        async def events():
            try:
                await asyncio.sleep(10)
                yield {"type": "result"}
            finally:
                cancelled.set()
        stream = stream_events(events(), heartbeat=.01)
        await anext(stream)
        await stream.aclose()
        self.assertTrue(cancelled.is_set())

    async def test_unexpected_end_reports_incomplete_answer(self):
        async def events():
            yield {"type": "status"}
        frames = [frame async for frame in stream_events(events())]
        self.assertIn("before the answer was complete", frames[-1])

    async def test_chat_route_streams_results_without_sending_model_keys_back(self):
        import httpx
        from main import app
        with patch("main.chat_reply", new_callable=AsyncMock, return_value={"success": True, "answer": "A completed answer", "sources": []}):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/chat/stream", json={"question": "Explain the paper"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])
        self.assertIn("A completed answer", response.text)

    async def test_concurrent_research_streams_keep_their_model_selection(self):
        import httpx
        from main import app
        from rag.config import get_connection
        async def reply(req):
            await asyncio.sleep(.01)
            return {"success": True, "answer": get_connection().model, "sources": []}
        with patch("main.chat_reply", side_effect=reply):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                responses = await asyncio.gather(*[client.post("/chat/stream", json={"question": "smoke"}, headers={"X-Pharmind-Connection": json.dumps({"model": name})}) for name in ["model-a", "model-b"]])
        self.assertIn('"answer": "model-a"', responses[0].text)
        self.assertNotIn("model-b", responses[0].text)
        self.assertIn('"answer": "model-b"', responses[1].text)
        self.assertNotIn("model-a", responses[1].text)

    async def test_initial_profile_survives_failed_evidence_review(self):
        from rag.pipeline import build_fallback_drug_info, run_pipeline_stream
        structure = {"common_name": "Test compound", "pubchem_cid": 123, "smiles": "CCO"}
        initial = build_fallback_drug_info("CCO", structure, "Test compound").model_dump()
        async def tokens(**kwargs):
            yield json.dumps(initial)
        with patch("rag.safety.check_query_safety", new_callable=AsyncMock, return_value=(True, None)), \
             patch("rag.pipeline.get_retriever"), \
             patch("rag.pipeline.resolve_query_structure", new_callable=AsyncMock, return_value=structure), \
             patch("rag.pipeline.sources_enabled", return_value=False), \
             patch("rag.pipeline.retrieve_field_evidence", new_callable=AsyncMock, return_value=[{"text": "Test passage", "source": "Test PDF"}]), \
             patch("rag.llm.generate_structured_output_stream", tokens), \
             patch("rag.pipeline.fill_missing_fields_from_evidence", new_callable=AsyncMock, side_effect=RuntimeError("Review failed")):
            events = [event async for event in run_pipeline_stream("CCO")]
        self.assertIn("checkpoint", [event["type"] for event in events])
        self.assertIn("warning", [event["type"] for event in events])
        self.assertEqual(events[-1]["type"], "result")
        self.assertEqual(events[-1]["data"]["query_smiles"], "CCO")

    async def test_completed_result_is_returned(self):
        request = AsyncMock()
        request.is_disconnected.return_value = False
        self.assertEqual(await run_until_disconnect(request, asyncio.sleep(0, result="answer"), 1), "answer")

    async def test_disconnect_cancels_model_work(self):
        request = AsyncMock()
        request.is_disconnected.return_value = True
        cancelled = asyncio.Event()

        async def model():
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.set()

        with self.assertRaises(HTTPException) as error:
            await run_until_disconnect(request, model(), 5)
        self.assertEqual(error.exception.status_code, 499)
        self.assertTrue(cancelled.is_set())

    async def test_timeout_cancels_model_work(self):
        request = AsyncMock()
        request.is_disconnected.return_value = False
        with self.assertRaises(asyncio.TimeoutError):
            await run_until_disconnect(request, asyncio.sleep(10), .01)

    async def test_readiness_reports_missing_cache_without_a_download(self):
        from main import local_readiness
        with patch("main.health", new_callable=AsyncMock, return_value={"status": "ok", "chunk_count": 0}), \
             patch("rag.embeddings.get_embedding_model", side_effect=RuntimeError("Run prepare_local_models.py")):
            status = await local_readiness()
        self.assertFalse(status["embeddings_ready"])
        self.assertIn("prepare_local_models", status["message"])


if __name__ == "__main__":
    unittest.main()
