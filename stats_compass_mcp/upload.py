"""
File upload and download handling for Stats Compass MCP server.

Provides:
- HTML upload page
- File upload endpoint
- Session-isolated file storage
- File download endpoint for exports
"""

import logging
import mimetypes
import os
from pathlib import Path

from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.routing import Route

from stats_compass_mcp.exports import get_exports_dir

logger = logging.getLogger(__name__)

# Configuration
MAX_UPLOAD_MB = int(os.getenv("STATS_COMPASS_MAX_UPLOAD_MB", "50"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
UPLOAD_DIR = Path(os.getenv("LOCAL_STORAGE_PATH", "/tmp/stats-compass-uploads"))  # nosec B108


# HTML template for upload page
UPLOAD_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stats Compass - File Upload</title>
    <style>
        * {
            box-sizing: border-box;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        body {
            max-width: 600px;
            margin: 40px auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            margin-top: 0;
            color: #333;
            font-size: 24px;
        }
        .session-info {
            background: #e8f4fd;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
        }
        .session-info code {
            background: #d0e8f7;
            padding: 2px 6px;
            border-radius: 4px;
        }
        .upload-area {
            border: 2px dashed #ccc;
            border-radius: 8px;
            padding: 40px;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s;
        }
        .upload-area:hover, .upload-area.dragover {
            border-color: #007bff;
            background: #f8f9ff;
        }
        .upload-area input {
            display: none;
        }
        .upload-area p {
            margin: 0;
            color: #666;
        }
        .upload-area .icon {
            font-size: 48px;
            margin-bottom: 10px;
        }
        .file-info {
            margin-top: 15px;
            padding: 10px;
            background: #f0f0f0;
            border-radius: 6px;
            display: none;
        }
        .file-info.show {
            display: block;
        }
        button {
            background: #007bff;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            font-size: 16px;
            cursor: pointer;
            width: 100%;
            margin-top: 20px;
        }
        button:hover {
            background: #0056b3;
        }
        button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        .result {
            margin-top: 20px;
            padding: 15px;
            border-radius: 8px;
            display: none;
        }
        .result.success {
            display: block;
            background: #d4edda;
            border: 1px solid #c3e6cb;
        }
        .result.error {
            display: block;
            background: #f8d7da;
            border: 1px solid #f5c6cb;
        }
        .result h3 {
            margin-top: 0;
            font-size: 16px;
        }
        .result code {
            display: block;
            background: #fff;
            padding: 10px;
            border-radius: 4px;
            margin-top: 10px;
            word-break: break-all;
        }
        .limits {
            font-size: 12px;
            color: #888;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Stats Compass File Upload</h1>
        
        <div class="session-info">
            Session ID: <code id="sessionId">-</code>
        </div>
        
        <div class="upload-area" id="uploadArea">
            <div class="icon">📁</div>
            <p>Drop a CSV or Excel file here, or click to browse</p>
            <input type="file" id="fileInput" accept=".csv,.xlsx,.xls">
        </div>
        
        <div class="file-info" id="fileInfo">
            <strong>Selected:</strong> <span id="fileName"></span> (<span id="fileSize"></span>)
        </div>
        
        <button id="uploadBtn" disabled>Upload</button>
        
        <div class="result" id="result">
            <h3 id="resultTitle"></h3>
            <p id="resultMessage"></p>
            <code id="resultCode"></code>
        </div>
        
        <p class="limits">
            Max file size: {max_upload_mb}MB • Supported formats: CSV, Excel
        </p>
    </div>
    
    <script>
        const sessionId = new URLSearchParams(window.location.search).get('session_id') || 'default';
        document.getElementById('sessionId').textContent = sessionId;
        
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const fileInfo = document.getElementById('fileInfo');
        const uploadBtn = document.getElementById('uploadBtn');
        const result = document.getElementById('result');
        
        let selectedFile = null;
        
        // Drag and drop
        uploadArea.addEventListener('click', () => fileInput.click());
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            if (e.dataTransfer.files.length) {
                handleFile(e.dataTransfer.files[0]);
            }
        });
        
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length) {
                handleFile(e.target.files[0]);
            }
        });
        
        function handleFile(file) {
            const maxBytes = {max_upload_bytes};
            if (file.size > maxBytes) {
                showError('File too large', `Maximum size is {max_upload_mb}MB`);
                return;
            }
            
            selectedFile = file;
            document.getElementById('fileName').textContent = file.name;
            document.getElementById('fileSize').textContent = formatBytes(file.size);
            fileInfo.classList.add('show');
            uploadBtn.disabled = false;
            result.className = 'result';
        }
        
        function formatBytes(bytes) {
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
            return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        }
        
        uploadBtn.addEventListener('click', async () => {
            if (!selectedFile) return;
            
            uploadBtn.disabled = true;
            uploadBtn.textContent = 'Uploading...';
            
            const formData = new FormData();
            formData.append('file', selectedFile);
            formData.append('session_id', sessionId);
            
            try {
                const response = await fetch('/api/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    showSuccess(data);
                } else {
                    showError('Upload failed', data.error || 'Unknown error');
                }
            } catch (err) {
                showError('Upload failed', err.message);
            } finally {
                uploadBtn.disabled = false;
                uploadBtn.textContent = 'Upload';
            }
        });
        
        function showSuccess(data) {
            result.className = 'result success';
            document.getElementById('resultTitle').textContent = '✅ Upload successful!';
            document.getElementById('resultMessage').textContent = 
                'Now tell your AI assistant to load the file as below:';
            document.getElementById('resultCode').textContent = 
                `register_uploaded_file(file_key="${data.file_key}")`;
        }
        
        function showError(title, message) {
            result.className = 'result error';
            document.getElementById('resultTitle').textContent = '❌ ' + title;
            document.getElementById('resultMessage').textContent = message;
            document.getElementById('resultCode').textContent = '';
        }
    </script>
</body>
</html>
""".replace("{max_upload_mb}", str(MAX_UPLOAD_MB)).replace("{max_upload_bytes}", str(MAX_UPLOAD_BYTES))


async def upload_page(request: Request) -> HTMLResponse:
    """Serve the upload page."""
    return HTMLResponse(UPLOAD_PAGE_HTML)


async def upload_file(request: Request) -> JSONResponse:
    """Handle file upload."""
    try:
        form = await request.form()

        # Get session ID
        session_id = form.get("session_id", "default")

        # Get uploaded file
        uploaded_file = form.get("file")
        if not uploaded_file:
            return JSONResponse({"error": "No file provided"}, status_code=400)

        # Check file size
        contents = await uploaded_file.read()
        if len(contents) > MAX_UPLOAD_BYTES:
            return JSONResponse(
                {"error": f"File too large. Maximum size is {MAX_UPLOAD_MB}MB"},
                status_code=413
            )

        # Validate file extension
        filename = uploaded_file.filename
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ("csv", "xlsx", "xls"):
            return JSONResponse(
                {"error": "Invalid file type. Supported: CSV, Excel (.xlsx, .xls)"},
                status_code=400
            )

        # Create session directory
        session_path = UPLOAD_DIR / session_id
        session_path.mkdir(parents=True, exist_ok=True)

        # Save file
        file_path = session_path / filename
        file_path.write_bytes(contents)

        logger.info(f"Uploaded {filename} ({len(contents)} bytes) for session {session_id}")

        return JSONResponse({
            "success": True,
            "file_key": filename,
            "session_id": session_id,
            "size_bytes": len(contents),
            "message": f"File uploaded successfully. Use register_uploaded_file(file_key=\"{filename}\") to load it."
        })

    except Exception as e:
        logger.exception("Upload failed")
        return JSONResponse({"error": str(e)}, status_code=500)


async def download_file(request: Request) -> FileResponse | JSONResponse:
    """
    Handle file download.
    
    URL: /download/{session_id}/{category}/{filename}
    Categories: models, data, plots, timeseries
    """
    session_id = request.path_params.get("session_id")
    category = request.path_params.get("category")
    filename = request.path_params.get("filename")

    # Validate category
    valid_categories = ["models", "data", "plots", "timeseries"]
    if category not in valid_categories:
        return JSONResponse(
            {"error": f"Invalid category. Must be one of: {', '.join(valid_categories)}"},
            status_code=400
        )

    # Build file path
    exports_dir = get_exports_dir(session_id, category)  # type: ignore
    file_path = exports_dir / filename

    # Security: Ensure we're not escaping the exports directory
    try:
        file_path = file_path.resolve()
        exports_base = get_exports_dir(session_id).resolve()
        if not str(file_path).startswith(str(exports_base)):
            return JSONResponse({"error": "Invalid path"}, status_code=400)
    except Exception:
        return JSONResponse({"error": "Invalid path"}, status_code=400)

    # Check if file exists
    if not file_path.exists() or not file_path.is_file():
        return JSONResponse(
            {"error": f"File not found: {filename}"},
            status_code=404
        )

    # Determine content type
    content_type, _ = mimetypes.guess_type(str(file_path))
    if content_type is None:
        # Default content types by category
        if category == "models":
            content_type = "application/octet-stream"
        elif category == "data":
            content_type = "text/csv"
        elif category == "plots":
            content_type = "image/png"
        else:
            content_type = "application/octet-stream"

    logger.info(f"Download: {session_id}/{category}/{filename}")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type=content_type,
    )


def create_upload_routes() -> list[Route]:
    """Create routes for file upload and download functionality."""
    return [
        Route("/upload", upload_page, methods=["GET"]),
        Route("/api/upload", upload_file, methods=["POST"]),
        Route("/download/{session_id}/{category}/{filename:path}", download_file, methods=["GET"]),
    ]
