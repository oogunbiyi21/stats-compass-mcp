"""
Image processing utilities for FastMCP remote server.

Converts base64 images from stats-compass-core results to MCP ImageContent.
"""

import base64
import logging
from typing import Any

from fastmcp.utilities.types import Image

from stats_compass_mcp.workflow_summary import summarize_workflow_result

logger = logging.getLogger(__name__)


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


def with_images(result: dict, summarize: bool = False) -> Any:
    """
    Process result and return with images as MCP ImageContent (FastMCP).
    
    Args:
        result: Result dict from stats-compass-core
        summarize: If True, summarize workflow results to reduce size
    
    Returns [result, Image, ...] if images found, else just result.
    """
    processed, images = process_images(result)
    
    # Summarize workflow results if requested
    if summarize and "steps" in processed and "artifacts" in processed:
        processed = summarize_workflow_result(processed)
    
    return [processed, *images] if images else processed
