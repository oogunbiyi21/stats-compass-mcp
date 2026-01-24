"""
Export utilities for Stats Compass MCP server.

Provides:
- Session-isolated export directories
- Download URL generation
- File path management for models, data, and plots
"""

import logging
import os
from pathlib import Path
from typing import Literal, Optional

logger = logging.getLogger(__name__)

# Configuration
EXPORTS_BASE_DIR = Path(os.getenv("STATS_COMPASS_EXPORTS_DIR", "/tmp/stats-compass-exports"))  # nosec B108
SERVER_URL = os.getenv("STATS_COMPASS_SERVER_URL", "")

# Export categories
ExportCategory = Literal["models", "data", "plots", "timeseries"]


def get_exports_dir(session_id: str, category: Optional[ExportCategory] = None) -> Path:
    """
    Get the exports directory for a session.
    
    Args:
        session_id: The session ID
        category: Optional category subdirectory (models, data, plots, timeseries)
    
    Returns:
        Path to the exports directory
    """
    base = EXPORTS_BASE_DIR / session_id
    if category:
        base = base / category
    return base


def ensure_exports_dir(session_id: str, category: ExportCategory) -> Path:
    """
    Ensure the exports directory exists and return its path.
    
    Args:
        session_id: The session ID
        category: Category subdirectory
    
    Returns:
        Path to the exports directory
    """
    exports_dir = get_exports_dir(session_id, category)
    exports_dir.mkdir(parents=True, exist_ok=True)
    return exports_dir


def get_export_path(session_id: str, category: ExportCategory, filename: str) -> Path:
    """
    Get the full path for an export file.
    
    Args:
        session_id: The session ID
        category: Category (models, data, plots, timeseries)
        filename: The filename
    
    Returns:
        Full path to the export file
    """
    exports_dir = ensure_exports_dir(session_id, category)
    return exports_dir / filename


def get_download_url(session_id: str, category: ExportCategory, filename: str) -> str:
    """
    Build a download URL for an exported file.
    
    Args:
        session_id: The session ID
        category: Category (models, data, plots, timeseries)
        filename: The filename
    
    Returns:
        Full download URL, or empty string if SERVER_URL not configured
    """
    if not SERVER_URL:
        # Local mode - no download URL available
        return ""

    # Build URL: {SERVER_URL}/download/{session_id}/{category}/{filename}
    return f"{SERVER_URL}/download/{session_id}/{category}/{filename}"


def cleanup_session_exports(session_id: str) -> None:
    """
    Clean up all exports for a session.
    
    Called when a session is deleted.
    
    Args:
        session_id: The session ID
    """
    import shutil

    exports_dir = get_exports_dir(session_id)
    if exports_dir.exists():
        try:
            shutil.rmtree(exports_dir)
            logger.info(f"Cleaned up exports for session: {session_id}")
        except Exception as e:
            logger.warning(f"Failed to cleanup exports for {session_id}: {e}")


def list_session_exports(session_id: str) -> dict[str, list[str]]:
    """
    List all exported files for a session.
    
    Returns:
        Dictionary mapping category to list of filenames
    """
    result: dict[str, list[str]] = {}

    base_dir = get_exports_dir(session_id)
    if not base_dir.exists():
        return result

    for category in ["models", "data", "plots", "timeseries"]:
        category_dir = base_dir / category
        if category_dir.exists():
            files = [f.name for f in category_dir.iterdir() if f.is_file()]
            if files:
                result[category] = files

    return result


def save_plot_export(
    session_id: str,
    image_base64: str,
    name_prefix: str,
) -> dict[str, str]:
    """
    Save a base64-encoded plot image to the exports directory.
    
    Args:
        session_id: The session ID
        image_base64: Base64-encoded image data
        name_prefix: Prefix for the filename (e.g., tool_name or step_name)
    
    Returns:
        Dictionary with 'filename', 'filepath', and 'download_url' (if available)
    """
    import base64
    from datetime import datetime

    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{name_prefix}_{timestamp}.png"

    # Get export path and save
    export_path = get_export_path(session_id, "plots", filename)

    try:
        image_data = base64.b64decode(image_base64)
        with open(export_path, "wb") as f:
            f.write(image_data)

        download_url = get_download_url(session_id, "plots", filename)

        return {
            "filename": filename,
            "filepath": str(export_path),
            "download_url": download_url,
        }
    except Exception as e:
        logger.warning(f"Failed to save plot {name_prefix}: {e}")
        return {
            "filename": "",
            "filepath": "",
            "download_url": "",
        }
