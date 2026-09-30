"""Request-disconnect-aware async stream wrapper for Open WebUI."""

import asyncio
from collections.abc import AsyncIterator

async def stream_with_client_disconnect(request, source: AsyncIterator, poll_seconds: float = 0.25):
    """Yield ``source`` until it ends or the downstream client disconnects."""
    iterator = source.__aiter__()
    pending = asyncio.create_task(iterator.__anext__())
    try:
        while True:
            if await request.is_disconnected():
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
                raise asyncio.CancelledError
            done, _ = await asyncio.wait({pending}, timeout=poll_seconds)
            if not done:
                continue
            try:
                item = pending.result()
            except StopAsyncIteration:
                return
            yield item
            pending = asyncio.create_task(iterator.__anext__())
    finally:
        if not pending.done():
            pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)
        aclose = getattr(iterator, "aclose", None)
        if aclose is not None:
            await aclose()
