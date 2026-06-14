"""
Image processing utilities for FastMCP server.

Converts base64 images from stats-compass-core results to MCP ImageContent.
"""

import base64
import logging
from contextvars import ContextVar
from typing import Any

from fastmcp.utilities.types import Image

from stats_compass_mcp.workflow_summary import summarize_workflow_result

logger = logging.getLogger(__name__)

# Per-request flag: True = return inline images, False = strip and return download URLs only.
# Defaults to True (stdio mode). HTTP mode sets False globally via set_inline_images(),
# but individual requests can opt in via the X-Inline-Images header (ContextVar overrides global).
_INLINE_IMAGES: bool = True
_inline_images_ctx: ContextVar[bool | None] = ContextVar("inline_images", default=None)


def set_inline_images(enabled: bool) -> None:
    """Set global default for inline images. Call once at startup for HTTP mode."""
    global _INLINE_IMAGES
    _INLINE_IMAGES = enabled


def _inline_images() -> bool:
    """Return effective inline-images setting: per-request override if set, else global."""
    ctx = _inline_images_ctx.get()
    return ctx if ctx is not None else _INLINE_IMAGES


def process_images(obj: Any, images: list[Image] | None = None) -> tuple[Any, list[Image]]:
    """
    Recursively extract base64 images from result and convert to FastMCP Images.

    Returns:
        Tuple of (processed result, list of Image objects)
    """
    if images is None:
        images = []

    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in ("image_base64", "base64_image") and isinstance(v, str) and v:
                try:
                    images.append(Image(data=base64.b64decode(v), format="png"))
                    out["image_included"] = True
                except Exception as e:
                    logger.error(f"Failed to decode image: {e}")
                    out[k] = "<image decode error>"
            else:
                out[k], _ = process_images(v, images)
        return out, images

    if isinstance(obj, list):
        return [process_images(item, images)[0] for item in obj], images

    return obj, images


def strip_base64(obj: Any) -> Any:
    """Recursively remove base64 image fields from result (for HTTP transport)."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in ("image_base64", "base64_image"):
                out["image_included"] = False
            else:
                out[k] = strip_base64(v)
        return out
    if isinstance(obj, list):
        return [strip_base64(item) for item in obj]
    return obj


def with_images(result: dict, summarize: bool = False) -> Any:
    """
    Process result and return with images as MCP ImageContent (FastMCP).

    In HTTP transport mode (_INLINE_IMAGES=False), base64 payloads are stripped
    and only download URLs (already present in the result) are returned.

    Args:
        result: Result dict from stats-compass-core
        summarize: If True, summarize workflow results to reduce size

    Returns [result, Image, ...] if images found (stdio), else just result.
    """
    if not _inline_images():
        processed = strip_base64(result)
        if summarize and "steps" in processed and "artifacts" in processed:
            processed = summarize_workflow_result(processed)
        return processed

    processed, images = process_images(result)

    # Summarize workflow results if requested
    if summarize and "steps" in processed and "artifacts" in processed:
        processed = summarize_workflow_result(processed)

    return [processed, *images] if images else processed
