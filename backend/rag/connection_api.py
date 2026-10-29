"""Validate a user's selected connection without sending a research prompt."""
import os

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
    if request.url.path == "/connection/test":
        return JSONResponse(status_code=422, content={"success": False, "error": "Check the provider, model ID, and local endpoint in your connection settings."})
    from fastapi.exception_handlers import request_validation_exception_handler
    return await request_validation_exception_handler(request, exc)


def ollama_host(connection: ModelConnection) -> str:
    # Docker's loopback is the container, so use the configured host gateway.
    if connection.base_url == "http://localhost:11434":
        return os.getenv("OLLAMA_BASE_URL", connection.base_url)
    return connection.base_url


@router.post("/connection/test")
async def test_connection(connection: ModelConnection):
    if connection.provider != "ollama" and not connection.api_key.strip():
        return JSONResponse(status_code=400, content={"success": False, "error": "Enter your provider API key."})
    headers = {}
    if connection.provider == "ollama":
        url = f"{ollama_host(connection)}/api/tags"
    elif connection.provider == "openai":
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
        if connection.provider == "ollama":
            models = {item.get("name") for item in response.json().get("models", [])}
            if connection.model not in models and f"{connection.model}:latest" not in models:
                return JSONResponse(status_code=400, content={"success": False, "error": "Ollama is reachable, but this model is not installed. Download it with ollama pull, then test again."})
        return {"success": True, "message": "Connection verified. The selected model is available; no research prompt was sent."}
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        message = "The provider rejected the key." if status in (401, 403) else "The model could not be verified. Check the model ID and provider availability."
        return JSONResponse(status_code=400, content={"success": False, "error": message})
    except (httpx.HTTPError, ValueError):
        return JSONResponse(status_code=502, content={"success": False, "error": "Could not reach this model service. Check that it is running and the address is correct."})
