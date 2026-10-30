"""Offline tests for request isolation, provider routing, and network consent."""
import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from rag.config import ModelConnection, connection_context, get_connection, require_network_allowed
from rag.connection_api import model_connection_context, connection_validation_error, router, test_connection as verify_connection, ollama_models, ollama_host
from rag.llm import generate_chat_response


class ConnectionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.token = connection_context.set(ModelConnection())

    def tearDown(self):
        connection_context.reset(self.token)

    def test_local_defaults_block_online_sources(self):
        self.assertEqual(get_connection().provider, "ollama")
        with self.assertRaisesRegex(RuntimeError, "disabled"):
            require_network_allowed("PubMed lookup")

    def test_cloud_inference_does_not_enable_online_sources(self):
        connection_context.set(ModelConnection(provider="openai", model="test-model", api_key="dummy-key"))
        with self.assertRaises(RuntimeError):
            require_network_allowed("PubMed lookup")

    def test_online_sources_are_explicit(self):
        connection_context.set(ModelConnection(online_sources=True))
        require_network_allowed("PubMed lookup")

    def test_remote_ollama_and_credential_urls_are_rejected(self):
        for url in ["https://remote.example", "http://localhost@remote.example", "http://user:password@localhost:11434", "file:///tmp/model", "http://localhost:11434/proxy"]:
            with self.subTest(url=url), self.assertRaises(ValidationError):
                ModelConnection(base_url=url)

    async def test_concurrent_streams_keep_their_own_model(self):
        app = FastAPI()
        app.middleware("http")(model_connection_context)

        @app.get("/stream")
        async def stream():
            async def values():
                for _ in range(3):
                    await asyncio.sleep(0)
                    yield get_connection().model + "\n"
            return StreamingResponse(values())

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            responses = await asyncio.gather(*[client.get("/stream", headers={"X-Pharmind-Connection": ModelConnection(model=model).model_dump_json()}) for model in ["model-a", "model-b"]])
            self.assertEqual(responses[0].text, "model-a\n" * 3)
            self.assertEqual(responses[1].text, "model-b\n" * 3)
            invalid = await client.get("/stream", headers={"X-Pharmind-Connection": '{"api_key":"dummy-secret","provider":"invalid"}'})
            self.assertEqual(invalid.status_code, 400)
            self.assertNotIn("dummy-secret", invalid.text)
        self.assertEqual(get_connection().model, "qwen2.5:3b")

    async def test_connection_test_rejects_missing_cloud_key(self):
        response = await verify_connection(ModelConnection(provider="openai", model="test-model"))
        self.assertEqual(response.status_code, 400)

    async def test_validation_errors_never_return_entered_secrets(self):
        app = FastAPI()
        app.include_router(router)
        app.add_exception_handler(RequestValidationError, connection_validation_error)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/connection/test", json={"api_key": "dummy-secret" * 100})
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("dummy-secret", response.text)

    async def test_ollama_test_checks_installed_model(self):
        response = httpx.Response(200, json={"models": [{"name": "installed:latest"}]}, request=httpx.Request("GET", "http://localhost:11434/api/tags"))
        with patch("rag.connection_api.httpx.AsyncClient") as client:
            client.return_value.__aenter__.return_value.get = AsyncMock(return_value=response)
            client.return_value.__aenter__.return_value.post = AsyncMock(return_value=httpx.Response(200, json={"capabilities": ["completion"]}, request=httpx.Request("POST", "http://localhost:11434/api/show")))
            missing = await verify_connection(ModelConnection(model="missing"))
            present = await verify_connection(ModelConnection(model="installed"))
        self.assertEqual(missing.status_code, 400)
        self.assertTrue(present["success"])

    async def test_discovery_distinguishes_answer_and_embedding_models_without_inference(self):
        tags = httpx.Response(200, json={"models": [{"name": "answer:7b"}, {"name": "embed:latest"}]}, request=httpx.Request("GET", "http://localhost:11434/api/tags"))
        async def show(url, json):
            return httpx.Response(200, json={"capabilities": ["embedding"] if json["model"] == "embed:latest" else ["completion", "tools"]}, request=httpx.Request("POST", url))
        with patch("rag.connection_api.httpx.AsyncClient") as factory:
            client = factory.return_value.__aenter__.return_value
            client.get = AsyncMock(return_value=tags)
            client.post = AsyncMock(side_effect=show)
            result = await ollama_models(ModelConnection(api_key="dummy-secret"))
        self.assertEqual(result["models"], [{"name": "answer:7b", "can_chat": True}, {"name": "embed:latest", "can_chat": False}])
        self.assertNotIn("dummy-secret", json.dumps(result))
        self.assertTrue(all(call.args[0].endswith("/api/show") for call in client.post.await_args_list))

    async def test_embedding_model_is_rejected_for_answers(self):
        with patch("rag.connection_api.discover_ollama_models", new_callable=AsyncMock, return_value=[{"name": "embed:latest", "can_chat": False}]):
            result = await verify_connection(ModelConnection(model="embed"))
        self.assertEqual(result.status_code, 400)
        self.assertIn("cannot generate answers", result.body.decode())

    async def test_discovery_failure_is_actionable_and_redacted(self):
        with patch("rag.connection_api.discover_ollama_models", new_callable=AsyncMock, side_effect=httpx.ConnectError("dummy-secret")):
            result = await ollama_models(ModelConnection())
        self.assertEqual(result.status_code, 502)
        self.assertIn("ollama serve", result.body.decode())
        self.assertNotIn("dummy-secret", result.body.decode())

    async def test_older_ollama_without_capabilities_remains_unverified(self):
        tags = httpx.Response(200, json={"models": [{"name": "old:latest"}]}, request=httpx.Request("GET", "http://localhost:11434/api/tags"))
        with patch("rag.connection_api.httpx.AsyncClient") as factory:
            client = factory.return_value.__aenter__.return_value
            client.get = AsyncMock(return_value=tags)
            client.post = AsyncMock(return_value=httpx.Response(200, json={}, request=httpx.Request("POST", "http://localhost:11434/api/show")))
            result = await ollama_models(ModelConnection())
        self.assertIsNone(result["models"][0]["can_chat"])

    async def test_model_discovery_validates_endpoint_without_echoing_keys(self):
        app = FastAPI()
        app.include_router(router)
        app.add_exception_handler(RequestValidationError, connection_validation_error)
        with patch("rag.connection_api.discover_ollama_models", new_callable=AsyncMock) as discover:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/connection/ollama-models", json={"base_url": "https://outside.example", "api_key": "dummy-secret"})
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("dummy-secret", response.text)
        discover.assert_not_awaited()

    def test_docker_loopback_aliases_use_the_same_host_gateway(self):
        with patch.dict("os.environ", {"OLLAMA_BASE_URL": "http://host.docker.internal:11434"}):
            for address in ["http://localhost:11434", "http://127.0.0.1:11434", "http://[::1]:11434"]:
                self.assertEqual(ollama_host(ModelConnection(base_url=address)), "http://host.docker.internal:11434")
            self.assertEqual(ollama_host(ModelConnection(base_url="http://localhost:11435")), "http://localhost:11435")

    async def test_cloud_connection_test_never_echoes_key(self):
        key = "dummy-secret"
        response = httpx.Response(401, text=key, request=httpx.Request("GET", "https://api.openai.com/v1/models/test-model"))
        with patch("rag.connection_api.httpx.AsyncClient") as client:
            client.return_value.__aenter__.return_value.get = AsyncMock(return_value=response)
            result = await verify_connection(ModelConnection(provider="openai", model="test-model", api_key=key))
        self.assertEqual(result.status_code, 400)
        self.assertNotIn(key, result.body.decode())

    async def test_ollama_generation_uses_selected_model(self):
        connection_context.set(ModelConnection(model="my-local-model"))
        with patch("rag.llm.ollama_sdk.AsyncClient") as client:
            client.return_value.chat = AsyncMock(return_value=SimpleNamespace(message=SimpleNamespace(content="Local answer")))
            answer = await generate_chat_response("Research instructions", [{"role": "user", "content": "Question"}])
            self.assertEqual(client.return_value.chat.call_args.kwargs["model"], "my-local-model")
        self.assertEqual(answer, "Local answer")

    async def test_byok_generation_uses_request_key_with_sources_off(self):
        connection_context.set(ModelConnection(provider="openai", model="my-model", api_key="dummy-key"))
        client = MagicMock()
        with patch.dict("sys.modules", {"openai": SimpleNamespace(AsyncOpenAI=client)}):
            client.return_value.chat.completions.create = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Provider answer"))]))
            answer = await generate_chat_response("Research instructions", [{"role": "user", "content": "Question"}])
            client.assert_called_once_with(api_key="dummy-key")
            self.assertEqual(client.return_value.chat.completions.create.call_args.kwargs["model"], "my-model")
        self.assertEqual(answer, "Provider answer")

    async def test_source_adapters_block_before_network_access(self):
        from ingest.chembl import fetch_chembl_profile
        from ingest.unified_pharmacology import fetch_mychem_profile, fetch_pubchem_pugview_data, fetch_europe_pmc_passages
        from ingest.openfda import fetch_openfda_label
        from ingest.pubmed import search_pubmed
        with patch("httpx.AsyncClient") as client:
            for fetch, arg in [(fetch_chembl_profile, "aspirin"), (fetch_mychem_profile, "aspirin"), (fetch_pubchem_pugview_data, "2244"), (fetch_europe_pmc_passages, "aspirin"), (fetch_openfda_label, "aspirin"), (search_pubmed, "aspirin")]:
                with self.subTest(fetch=fetch.__name__), self.assertRaises(RuntimeError):
                    await fetch(arg)
            client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
