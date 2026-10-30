"""Validate a user's selected connection without sending a research prompt."""
import os
import asyncio

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from rag.config import ModelConnection, connection_context

router = APIRouter()


async def model_connection_context(request: Request, call_next):
    raw = request.headers.get("X-Pharmind-Connection")
    connection = None
    if raw:
        try:
            connection = ModelConnection.model_validate_json(raw)
        except ValueError:
            return JSONResponse(status_code=400, content={"success": False, "error": "Invalid model connection settings."})
    token = connection_context.set(connection)
    try:
        return await call_next(request)
    finally:
        connection_context.reset(token)


async def connection_validation_error(request: Request, exc):
    # FastAPI normally echoes invalid input, which may include an entered key.
    if request.url.path.startswith("/connection/"):
        return JSONResponse(status_code=422, content={"success": False, "error": "Check the provider, model ID, and local endpoint in your connection settings."})
    from fastapi.exception_handlers import request_validation_exception_handler
    return await request_validation_exception_handler(request, exc)


def ollama_host(connection: ModelConnection) -> str:
    # Docker's loopback is the container, so use the configured host gateway.
    if connection.base_url in {"http://localhost:11434", "http://127.0.0.1:11434", "http://[::1]:11434"}:
        return os.getenv("OLLAMA_BASE_URL", connection.base_url)
    return connection.base_url


async def discover_ollama_models(connection: ModelConnection) -> list[dict]:
    host = ollama_host(connection)
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get(f"{host}/api/tags")
        response.raise_for_status()
        entries = response.json()["models"]
        if not isinstance(entries, list):
            raise ValueError("Invalid Ollama model list")
        semaphore = asyncio.Semaphore(4)

        async def describe(entry):
            name = entry.get("name")
            if not isinstance(name, str) or not name:
                raise ValueError("Invalid Ollama model name")
            can_chat = None
            try:
                async with semaphore:
                    details = await client.post(f"{host}/api/show", json={"model": name})
                    details.raise_for_status()
                capabilities = details.json().get("capabilities")
                if isinstance(capabilities, list):
                    can_chat = "completion" in capabilities
            except (httpx.HTTPError, ValueError, TypeError, AttributeError):
                # Older Ollama releases may not expose model capabilities.
                pass
            return {"name": name, "can_chat": can_chat}

        return sorted(await asyncio.gather(*(describe(entry) for entry in entries)), key=lambda model: model["name"])


def find_ollama_model(models: list[dict], selected: str) -> dict | None:
    return next((model for model in models if model["name"] in {selected, f"{selected}:latest"}), None)


@router.post("/connection/ollama-models")
async def ollama_models(connection: ModelConnection):
    if connection.provider != "ollama":
        return JSONResponse(status_code=400, content={"success": False, "error": "Choose Ollama to inspect local models."})
    try:
        return {"success": True, "models": await discover_ollama_models(connection)}
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        return JSONResponse(status_code=502, content={"success": False, "error": "Ollama is unavailable. Open Ollama or run ollama serve on your computer, then refresh. Docker does not install Ollama or an answer model."})


@router.post("/connection/test")
async def test_connection(connection: ModelConnection):
    if connection.provider == "ollama":
        discovered = await ollama_models(connection)
        if isinstance(discovered, JSONResponse):
            return discovered
        models = discovered["models"]
        selected = find_ollama_model(models, connection.model)
        if selected is None:
            return JSONResponse(status_code=400, content={"success": False, "error": f"{connection.model} is not installed. Choose an installed answer model in Model & connection, or download a model with ollama pull.", "models": models})
        if selected["can_chat"] is False:
            return JSONResponse(status_code=400, content={"success": False, "error": f"{connection.model} cannot generate answers. Choose an installed text-generation model.", "models": models})
        return {"success": True, "message": "Connection verified. The selected model is installed; no research prompt was sent. This does not verify answer quality."}
    if connection.provider != "ollama" and not connection.api_key.strip():
        return JSONResponse(status_code=400, content={"success": False, "error": "Enter your provider API key."})
    headers = {}
    if connection.provider == "openai":
        url = f"https://api.openai.com/v1/models/{connection.model}"
        headers = {"Authorization": f"Bearer {connection.api_key}"}
    elif connection.provider == "anthropic":
        url = f"https://api.anthropic.com/v1/models/{connection.model}"
        headers = {"x-api-key": connection.api_key, "anthropic-version": "2023-06-01"}
    else:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{connection.model}"
        headers = {"x-goog-api-key": connection.api_key}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
        return {"success": True, "message": "Connection verified. The selected model is available; no research prompt was sent."}
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        message = "The provider rejected the key." if status in (401, 403) else "The model could not be verified. Check the model ID and provider availability."
        return JSONResponse(status_code=400, content={"success": False, "error": message})
    except (httpx.HTTPError, ValueError):
        return JSONResponse(status_code=502, content={"success": False, "error": "Could not reach this model service. Check that it is running and the address is correct."})
