"""
LLM client — provider-agnostic.

Switch providers via the LLM_PROVIDER environment variable:
  - ollama      → local Qwen/Llama via Ollama (default; no API key needed)
  - openai      → OpenAI GPT-4o
  - anthropic   → Anthropic Claude

Phase 2.5: Ollama branch is now fully implemented using the 0.6.x async API.
Phase 3:   pipeline.py calls generate_structured_output().
"""

import json
import logging
import os
from typing import Any

import ollama as ollama_sdk
from pydantic import BaseModel
from rag.config import get_connection
from rag.connection_api import ollama_host

logger = logging.getLogger(__name__)

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")


def _get_gemini_model_candidates() -> list[str]:
    """Return ordered list of Gemini models to try, falling back on 503/429/timeout errors."""
    raw_fallbacks = os.getenv(
        "GEMINI_FALLBACK_MODELS",
        "",
    )
    fallbacks = [m.strip() for m in raw_fallbacks.split(",") if m.strip()]
    candidates = [get_connection().model]
    for fb in fallbacks:
        if fb not in candidates:
            candidates.append(fb)
    return candidates


def _llm_output_schema(schema: type[BaseModel]) -> dict[str, Any]:
    """Use SOURCE_N strings in model output; trusted citations are resolved later."""
    result = schema.model_json_schema()

    def rewrite(node: Any) -> None:
        if isinstance(node, dict):
            properties = node.get("properties")
            if isinstance(properties, dict) and "sources" in properties:
                properties.pop("sources")
                properties["source_ids"] = {"type": "array", "items": {"type": "string"}}
            required = node.get("required")
            if isinstance(required, list):
                node["required"] = ["source_ids" if key == "sources" else key for key in required]
            for value in node.values():
                rewrite(value)
        elif isinstance(node, list):
            for value in node:
                rewrite(value)

    rewrite(result)
    return result


async def generate_structured_output(
    system_prompt: str,
    user_message: str,
    output_schema: type[BaseModel],
) -> dict[str, Any]:
    """
    Send a prompt to the configured LLM and return a dict matching output_schema.

    All providers receive:
      - system_prompt: instructions + JSON schema with SOURCE_N citation format
      - user_message:  labelled context chunks + drug query

    The LLM is instructed to cite using SOURCE_N identifiers only.
    Missing fields must be { "content": null, "missing": true }.
    Fabricating information is explicitly forbidden.
    """
    if get_connection().provider == "ollama":
        return await _call_ollama(system_prompt, user_message, output_schema)
    elif get_connection().provider == "openai":
        return await _call_openai(system_prompt, user_message, output_schema)
    elif get_connection().provider == "anthropic":
        return await _call_anthropic(system_prompt, user_message, output_schema)
    elif get_connection().provider == "gemini":
        return await _call_gemini(system_prompt, user_message, output_schema)
    else:
        raise ValueError(f"Unknown model provider: {get_connection().provider!r}")


async def generate_chat_response(
    system_prompt: str,
    messages: list[dict[str, str]],
) -> str:
    """Generate a conversational answer using the configured model provider."""
    if get_connection().provider == "ollama":
        client = ollama_sdk.AsyncClient(host=ollama_host(get_connection()))
        response = await client.chat(
            model=get_connection().model,
            messages=[{"role": "system", "content": system_prompt}, *messages],
            options={"temperature": 0.2, "num_ctx": 8192},
        )
        return response.message.content

    if get_connection().provider == "openai":

        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=get_connection().api_key)
        response = await client.chat.completions.create(
            model=get_connection().model,
            temperature=0.2,
            messages=[{"role": "system", "content": system_prompt}, *messages],
        )
        return response.choices[0].message.content or ""

    if get_connection().provider == "anthropic":

        import anthropic

        client = anthropic.AsyncAnthropic(api_key=get_connection().api_key)
        response = await client.messages.create(
            model=get_connection().model,
            max_tokens=2048,
            system=system_prompt,
            messages=messages,
        )
        return "".join(block.text for block in response.content if getattr(block, "text", None))

    if get_connection().provider == "gemini":

        import httpx

        if not get_connection().api_key:
            raise ValueError("Add a provider API key in connection settings.")

        # Ensure alternating user/model turns for the Gemini REST API
        normalized_contents: list[dict[str, Any]] = []
        for item in messages:
            role = "model" if item.get("role") == "assistant" else "user"
            text = (item.get("content") or "").strip()
            if not text:
                continue
            if normalized_contents and normalized_contents[-1]["role"] == role:
                normalized_contents[-1]["parts"][0]["text"] += f"\n\n{text}"
            else:
                normalized_contents.append({"role": role, "parts": [{"text": text}]})

        while normalized_contents and normalized_contents[0]["role"] != "user":
            normalized_contents.pop(0)

        if not normalized_contents:
            normalized_contents = [{"role": "user", "parts": [{"text": "Hello"}]}]

        model_candidates = _get_gemini_model_candidates()
        last_exc = None
        for i, model_name in enumerate(model_candidates):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
            try:
                async with httpx.AsyncClient(timeout=45.0) as client:
                    response = await client.post(url, headers={"x-goog-api-key": get_connection().api_key}, json={
                        "systemInstruction": {"parts": [{"text": system_prompt}]},
                        "contents": normalized_contents,
                        "generationConfig": {"temperature": 0.2},
                    })
                    if response.status_code in (503, 429, 404) and i < len(model_candidates) - 1:
                        logger.warning(
                            f"Gemini model '{model_name}' returned {response.status_code}, falling back to '{model_candidates[i+1]}'..."
                        )
                        continue
                    response.raise_for_status()
                    data = response.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as exc:
                last_exc = exc
                if i < len(model_candidates) - 1:
                    logger.warning(
                        f"Gemini model '{model_name}' failed ({exc}), falling back to '{model_candidates[i+1]}'..."
                    )
                    continue
                raise last_exc

    raise ValueError(f"Unknown model provider: {get_connection().provider!r}")


async def generate_structured_output_stream(
    system_prompt: str,
    user_message: str,
    output_schema: type[BaseModel],
):
    """
    Stream tokens from local Ollama instance while generating structured output.
    Yields chunks of generated text tokens.
    """
    if get_connection().provider == "ollama":
        client = ollama_sdk.AsyncClient(host=ollama_host(get_connection()))
        format_option: Any = "json"
        if output_schema and hasattr(output_schema, "model_json_schema"):
            format_option = _llm_output_schema(output_schema)

        async for chunk in await client.chat(
            model=get_connection().model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ],
            format=format_option,
            stream=True,
            options={
                "temperature": 0.1,
                "num_predict": 6144,
                "num_ctx": 32768,
            },
        ):
            if chunk and chunk.message and chunk.message.content:
                yield chunk.message.content
    else:
        full_res = await generate_structured_output(system_prompt, user_message, output_schema)
        yield json.dumps(full_res)


# ── Ollama (Phase 2.5 / Phase 3) ─────────────────────────────────────────────

async def _call_ollama(
    system_prompt: str,
    user_message: str,
    schema: type[BaseModel],
) -> dict:
    """
    Call local Ollama instance (Qwen, Llama, etc.) using the 0.6.x AsyncClient.

    Passes schema.model_json_schema() to strictly constrain Ollama to the Pydantic schema.
    Temperature 0.1 = factual and deterministic.
    """
    client = ollama_sdk.AsyncClient(host=ollama_host(get_connection()))

    format_option: Any = "json"
    if schema and hasattr(schema, "model_json_schema"):
        format_option = _llm_output_schema(schema)

    response = await client.chat(
        model=get_connection().model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
        format=format_option,
        options={
            "temperature": 0.1,
            # The monograph schema is large. Give the model enough room for
            # the retrieved evidence and a complete JSON response instead of
            # silently truncating the tail fields.
            "num_predict": 6144,
            "num_ctx": 32768,
        },
    )

    raw: str = response.message.content
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Ollama returned invalid JSON: {exc}\nRaw output (first 500 chars):\n{raw[:500]}"
        ) from exc


# ── OpenAI (optional) ─────────────────────────────────────────────────────────

async def _call_openai(
    system_prompt: str,
    user_message: str,
    schema: type[BaseModel],
) -> dict:
    """
    Call OpenAI API with JSON mode.
    Uses the OpenAI key from the current connection.
    """
    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise ImportError("Run: pip install openai") from None

    client = AsyncOpenAI(api_key=get_connection().api_key)
    resp = await client.chat.completions.create(
        model=get_connection().model,
        response_format={"type": "json_object"},
        temperature=0.1,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
    )
    raw = resp.choices[0].message.content
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"OpenAI returned invalid JSON: {exc}") from exc


# ── Anthropic (optional) ──────────────────────────────────────────────────────

async def _call_anthropic(
    system_prompt: str,
    user_message: str,
    schema: type[BaseModel],
) -> dict:
    """
    Call Anthropic Claude API.
    Uses the Anthropic key from the current connection.
    """
    try:
        import anthropic
    except ImportError:
        raise ImportError("Run: pip install anthropic") from None

    client = anthropic.AsyncAnthropic(api_key=get_connection().api_key)
    msg = await client.messages.create(
        model=get_connection().model,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    raw = msg.content[0].text
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Anthropic returned invalid JSON: {exc}") from exc


# ── Google Gemini (optional) ──────────────────────────────────────────────────

async def _call_gemini(
    system_prompt: str,
    user_message: str,
    schema: type[BaseModel],
) -> dict:
    """
    Call Google Gemini API with JSON mode.
    Uses the Gemini key from the current connection.
    """
    import httpx

    if not get_connection().api_key:
        raise ValueError("Add a provider API key in connection settings.")

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": user_message}
                ]
            }
        ],
        "systemInstruction": {
            "parts": [
                {"text": system_prompt}
            ]
        },
        "generationConfig": {
            "responseMimeType": "application/json",
            "maxOutputTokens": int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "16384")),
            "temperature": 0.1,
        }
    }

    model_candidates = _get_gemini_model_candidates()
    last_exc = None
    data = None
    for i, model_name in enumerate(model_candidates):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(url, headers={"x-goog-api-key": get_connection().api_key}, json=payload)
                if resp.status_code in (503, 429, 404) and i < len(model_candidates) - 1:
                    logger.warning(
                        f"Gemini model '{model_name}' returned {resp.status_code}, automatically falling back to '{model_candidates[i+1]}'..."
                    )
                    continue
                resp.raise_for_status()
                data = resp.json()
            break
        except Exception as exc:
            last_exc = exc
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in (404, 429, 503):
                raise
            if i < len(model_candidates) - 1:
                logger.warning(
                    f"Gemini model '{model_name}' failed ({exc}), automatically falling back to '{model_candidates[i+1]}'..."
                )
                continue
            raise last_exc

    try:
        candidate = data["candidates"][0]
        finish_reason = candidate.get("finishReason", "")
        if finish_reason and finish_reason != "STOP":
            raise ValueError(f"Gemini did not complete structured output (finishReason={finish_reason}).")
        parts = candidate["content"]["parts"]
        raw = "".join(part.get("text", "") for part in parts)
        if not raw:
            raise ValueError("Gemini returned no text for the structured response.")
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"Gemini API returned unexpected response format: {data}") from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Gemini returned invalid JSON: {exc}\nRaw output (first 500 chars):\n{raw[:500]}"
        ) from exc
    if not isinstance(parsed, dict):
        raise ValueError("Gemini structured response must be a JSON object.")
    return parsed
