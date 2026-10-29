"""Per-request model selection. Credentials are never written to disk."""
from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
import os

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, field_validator

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


class ModelConnection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["ollama", "openai", "anthropic", "gemini"] = "ollama"
    model: str = Field(default="qwen2.5:3b", min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9._:/-]+$")
    api_key: str = Field(default="", max_length=512, repr=False)
    base_url: str = "http://localhost:11434"
    online_sources: bool = False

    @field_validator("base_url")
    @classmethod
    def local_endpoint(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (parsed.scheme not in {"http", "https"}
                or parsed.hostname not in {"localhost", "127.0.0.1", "::1", "host.docker.internal"}
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in {"", "/"}):
            raise ValueError("Use a local Ollama address, such as http://localhost:11434.")
        return value.rstrip("/")


connection_context: ContextVar[ModelConnection | None] = ContextVar("model_connection", default=None)


def get_connection() -> ModelConnection:
    connection = connection_context.get()
    if connection is not None:
        return connection
    provider = os.getenv("LLM_PROVIDER", "ollama")
    defaults = {"ollama": "qwen2.5:3b", "openai": "gpt-4o", "anthropic": "claude-sonnet-4-5", "gemini": "gemini-2.5-flash"}
    prefix = provider.upper()
    return ModelConnection(
        provider=provider,
        model=os.getenv(f"{prefix}_MODEL", defaults.get(provider, "qwen2.5:3b")),
        api_key=os.getenv(f"{prefix}_API_KEY", ""),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        online_sources=os.getenv("ONLINE_SOURCES", "false").lower() == "true",
    )


def sources_enabled() -> bool:
    return get_connection().online_sources


def require_network_allowed(operation: str) -> None:
    if not sources_enabled():
        raise RuntimeError(f"{operation} is disabled. Enable online sources in connection settings.")


# Compatibility for standalone ingest scripts; requests use sources_enabled().
OFFLINE_MODE = not sources_enabled()
