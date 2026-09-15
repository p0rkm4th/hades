"""Apply the HADES compatibility fix for the pinned Open WebUI Channels path.

Open WebUI 0.11.1 returns a StreamingResponse from its chat-completion
handler.  Channels awaited that handler but did not consume the response body,
so a provider request could succeed while the channel model message remained
empty.  This build-time patch is intentionally exact and fails closed if the
upstream source changes.
"""

from pathlib import Path


path = Path("/app/backend/open_webui/routers/channels.py")
source = path.read_text(encoding="utf-8")
old = "                await request.app.state.CHAT_COMPLETION_HANDLER(request, form_data, user=user)"
new = """                response = await request.app.state.CHAT_COMPLETION_HANDLER(request, form_data, user=user)
                # The chat endpoint returns a StreamingResponse.  Consume it
                # here so its generator performs channel message persistence
                # and socket emission; awaiting the response object alone is
                # insufficient.
                if hasattr(response, 'body_iterator'):
                    async for _chunk in response.body_iterator:
                        pass"""
if source.count(old) != 1:
    raise SystemExit("expected exactly one Channels completion call to patch")
path.write_text(source.replace(old, new), encoding="utf-8")
print("PASS Open WebUI Channels response-consumption compatibility patch applied")
