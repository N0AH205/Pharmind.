import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from rag.requests import run_until_disconnect


class RequestTests(unittest.IsolatedAsyncioTestCase):
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
