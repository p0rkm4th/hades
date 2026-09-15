"""HADES image-only gateway for the official PaddleOCR MCP server."""

from __future__ import annotations

import base64
import os

from fastmcp import FastMCP
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from input_boundary import ImageInputError, decode_image_input


mcp = FastMCP("hades-receipt-ocr-gateway")


async def _upstream_ocr(image: bytes, mime: str) -> dict:
    params = StdioServerParameters(
        command=os.environ.get("PADDLEOCR_MCP_COMMAND", "paddleocr_mcp"),
        args=["--model", os.environ.get("PADDLEOCR_MCP_MODEL", "PP-OCRv6"), "--ppocr_source", "local", "--device", "cpu"],
        env={**os.environ, "FLAGS_use_mkldnn": "0"},
    )
    data_url = f"data:{mime};base64,{base64.b64encode(image).decode('ascii')}"
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool("ocr", arguments={
                "input_data": data_url,
                "output_mode": "detailed",
                "return_images": False,
                "runtime_params": {
                    "use_doc_orientation_classify": False,
                    "use_doc_unwarping": False,
                    "use_textline_orientation": False,
                },
            })
    content = [item.text for item in result.content if getattr(item, "text", None) is not None]
    if getattr(result, "isError", False):
        return {"status": "FAILED", "error": "upstream PaddleOCR MCP failed", "content": content}
    return {"status": "SUCCEEDED", "content": content}


@mcp.tool()
async def receipt_ocr_extract(image_base64: str, mime: str | None = None) -> dict:
    """Extract receipt text from inline base64 PNG, JPEG, or WebP data only.

    Paths, URLs, filesystem access, and writes are not accepted. The result is
    upstream OCR evidence and never changes Grocy or finance state.
    """
    try:
        decoded = decode_image_input(image_base64, declared_mime=mime)
        return await _upstream_ocr(decoded["bytes"], decoded["mime"])
    except (ImageInputError, ValueError, OSError) as exc:
        return {"status": "FAILED", "error": str(exc)}


def main() -> None:
    transport = os.environ.get("HADES_OCR_TRANSPORT", "stdio").strip().lower()
    if transport == "streamable-http":
        mcp.run(
            transport="streamable-http",
            host=os.environ.get("HADES_OCR_HOST", "0.0.0.0"),
            port=int(os.environ.get("HADES_OCR_PORT", "8000")),
            path=os.environ.get("HADES_OCR_PATH", "/mcp"),
        )
        return
    if transport != "stdio":
        raise SystemExit("HADES_OCR_TRANSPORT must be stdio or streamable-http")
    mcp.run()


if __name__ == "__main__":
    main()
