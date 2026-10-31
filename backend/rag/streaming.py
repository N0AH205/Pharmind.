import asyncio
import json
import logging
from contextlib import aclosing

import httpx

from rag.requests import REQUEST_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

TIMEOUT_MESSAGE = "Research reached its 15-minute limit. Try a smaller model or a more focused question. Any saved initial profile is still available."


def research_error(exc: Exception) -> str:
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)) or "timeout" in type(exc).__name__.lower():
        return "The model or evidence service timed out. Check your model connection or try a smaller model. Any saved initial profile is still available."
    if isinstance(exc, (ConnectionError, httpx.NetworkError, httpx.ProtocolError)) or "connection" in type(exc).__name__.lower():
        return "The connection to the model or evidence service was interrupted. Check Model & connection and retry. Any saved initial profile is still available."
    return "The research process could not finish the answer. Try again or use a model that supports structured output. Any saved initial profile is still available."


async def stream_events(events, timeout=REQUEST_TIMEOUT_SECONDS, heartbeat=10):
    """Keep the response active while one task owns the model stream and its cleanup."""
    queue = asyncio.Queue(maxsize=1)

    async def produce():
        terminal = False
        try:
            async with aclosing(events) as iterator:
                async for event in iterator:
                    terminal = event.get("type") in {"result", "error"}
                    await queue.put(event)
                    if terminal:
                        return
            await queue.put({"type": "error", "message": "The backend stopped before the answer was complete. Any saved initial profile is still available."})
        except Exception as exc:
            logger.warning("Research stream failed (%s)", type(exc).__name__)
            if not terminal:
                await queue.put({"type": "error", "message": research_error(exc)})

    task = asyncio.create_task(produce())
    deadline = asyncio.get_running_loop().time() + timeout
    try:
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                yield f"data: {json.dumps({'type': 'error', 'message': TIMEOUT_MESSAGE})}\n\n"
                return
            try:
                event = await asyncio.wait_for(queue.get(), timeout=min(heartbeat, remaining))
            except TimeoutError:
                yield ": keep-alive\n\n"
                continue
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("type") in {"result", "error"}:
                return
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
