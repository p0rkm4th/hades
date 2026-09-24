"""Add explicit client-disconnect cancellation to the pinned Open WebUI proxy."""

from pathlib import Path

MIDDLEWARE = Path("/app/backend/open_webui/utils/middleware.py")
MARKER = "# HADES client-disconnect compatibility"
IMPORT = "from open_webui.utils.hades_stream_disconnect_compat import stream_with_client_disconnect\n"
OLD = """        return StreamingResponse(
            stream_wrapper(response.body_iterator, events),
            headers=dict(response.headers),
            background=response.background,
        )
"""
NEW = """        return StreamingResponse(
            stream_with_client_disconnect(request, stream_wrapper(response.body_iterator, events)),
            headers=dict(response.headers),
            background=response.background,
        )
"""

def main() -> None:
    text = MIDDLEWARE.read_text(encoding="utf-8")
    if MARKER in text:
        raise SystemExit("client-disconnect compatibility patch already present")
    if text.count(OLD) != 1:
        raise SystemExit(f"expected one streaming response wrapper, found {text.count(OLD)}")
    anchor = "from open_webui.utils.json_codec import JSONCodec"
    if anchor not in text:
        raise SystemExit("Open WebUI middleware import anchor not found")
    text = text.replace(anchor, f"{MARKER}\n{IMPORT}{anchor}", 1)
    text = text.replace(OLD, NEW, 1)
    MIDDLEWARE.write_text(text, encoding="utf-8")
    print("PASS Open WebUI client-disconnect compatibility patch applied")

if __name__ == "__main__":
    main()
