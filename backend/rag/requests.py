import asyncio

from fastapi import HTTPException, Request

REQUEST_TIMEOUT_SECONDS = 15 * 60


async def run_until_disconnect(request: Request, operation, timeout: float):
    """Cancel non-streaming model work when its local client disconnects."""
    async def disconnected():
        while not await request.is_disconnected():
            await asyncio.sleep(0.25)

    task = asyncio.create_task(asyncio.wait_for(operation, timeout))
    watcher = asyncio.create_task(disconnected())
    try:
        done, _ = await asyncio.wait({task, watcher}, return_when=asyncio.FIRST_COMPLETED)
        if task in done:
            return await task
        raise HTTPException(status_code=499, detail="Request stopped.")
    finally:
        task.cancel()
        watcher.cancel()
        await asyncio.gather(task, watcher, return_exceptions=True)
