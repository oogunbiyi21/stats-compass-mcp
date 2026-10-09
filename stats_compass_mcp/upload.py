"""
File upload and download handling for Stats Compass MCP server.

Provides:
- HTML upload page
- File upload endpoint
- Session-isolated file storage
- File download endpoint for exports

Both endpoints take an encrypted, expiring token (stats_compass_mcp.tokens) and
derive every path from fixed folders, never from request data. They used to
take the session id itself and join caller-supplied names onto it: '..' as a
session id lifted /download's containment base to /tmp, and /api/upload wrote
wherever its session_id and file name pointed (security scan, 8 Oct 2026, F2,
F4).
"""

import logging
import mimetypes
import os
from pathlib import Path

from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.routing import Route

from stats_compass_mcp import exports
from stats_compass_mcp.safety import check_file_key, check_session_id, short_id
from stats_compass_mcp.tokens import read_token

logger = logging.getLogger(__name__)

# Configuration
MAX_UPLOAD_MB = int(os.getenv("STATS_COMPASS_MAX_UPLOAD_MB", "50"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
VALID_CATEGORIES = ("models", "data", "plots", "timeseries")


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
        
        <div class="upload-area" id="uploadArea">
            <div class="icon">📁</div>
            <p>Drop a CSV or Excel file here, or click to browse</p>
        </div>
        <input type="file" id="fileInput" accept=".csv,.xlsx,.xls" style="display:none">

        <div class="file-info" id="fileInfo">
            <strong>Selected:</strong> <span id="fileName"></span> (<span id="fileSize"></span>)
        </div>

        <button id="uploadBtn" disabled>Upload</button>

        <div id="successBox" style="display:none" class="result success">
            <h3>✅ Upload successful!</h3>
            <p>Tell your AI assistant you're done — it will load the file automatically.</p>
        </div>
        <div id="errorBox" style="display:none" class="result error">
            <h3 id="errorTitle"></h3>
            <p id="errorMsg"></p>
        </div>
        
        <p class="limits">
            Max file size: {max_upload_mb}MB • Supported formats: CSV, Excel
        </p>
    </div>
    
    <script>
        const uploadToken = new URLSearchParams(window.location.search).get('token') || '';
        
        var uploadArea = document.getElementById('uploadArea');
        var fileInput = document.getElementById('fileInput');
        var fileInfo = document.getElementById('fileInfo');
        var uploadBtn = document.getElementById('uploadBtn');
        var successBox = document.getElementById('successBox');
        var errorBox = document.getElementById('errorBox');

        var selectedFile = null;

        uploadArea.addEventListener('click', function() { fileInput.click(); });
        uploadArea.addEventListener('dragover', function(e) {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        uploadArea.addEventListener('dragleave', function() {
            uploadArea.classList.remove('dragover');
        });
        uploadArea.addEventListener('drop', function(e) {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            if (e.dataTransfer.files.length) { handleFile(e.dataTransfer.files[0]); }
        });

        fileInput.addEventListener('change', function(e) {
            if (e.target.files.length) { handleFile(e.target.files[0]); }
        });

        function handleFile(file) {
            var maxBytes = {max_upload_bytes};
            if (file.size > maxBytes) {
                showError('File too large', 'Maximum size is {max_upload_mb}MB');
                return;
            }
            selectedFile = file;
            document.getElementById('fileName').textContent = file.name;
            document.getElementById('fileSize').textContent = formatBytes(file.size);
            fileInfo.classList.add('show');
            uploadBtn.disabled = false;
        }

        function formatBytes(bytes) {
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
            return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        }

        uploadBtn.addEventListener('click', function() {
            if (!selectedFile) return;
            uploadBtn.disabled = true;
            uploadBtn.textContent = 'Uploading...';
            var formData = new FormData();
            formData.append('file', selectedFile);
            formData.append('token', uploadToken);
            fetch('/api/upload', { method: 'POST', body: formData })
                .then(function(response) {
                    return response.json().then(function(data) {
                        return { ok: response.ok, data: data };
                    });
                })
                .then(function(result) {
                    uploadBtn.disabled = false;
                    uploadBtn.textContent = 'Upload';
                    if (result.ok) {
                        successBox.style.display = 'block';
                        errorBox.style.display = 'none';
                    } else {
                        showError('Upload failed', result.data.error || 'Unknown error');
                    }
                })
                .catch(function(err) {
                    uploadBtn.disabled = false;
                    uploadBtn.textContent = 'Upload';
                    showError('Upload failed', err.message);
                });
        });

        function showError(title, message) {
            document.getElementById('errorTitle').textContent = '❌ ' + title;
            document.getElementById('errorMsg').textContent = message;
            errorBox.style.display = 'block';
            successBox.style.display = 'none';
        }
    </script>
</body>
</html>
""".replace("{max_upload_mb}", str(MAX_UPLOAD_MB)).replace("{max_upload_bytes}", str(MAX_UPLOAD_BYTES))


async def upload_page(request: Request) -> HTMLResponse:
    """Serve the upload page."""
    return HTMLResponse(UPLOAD_PAGE_HTML)


async def upload_file(request: Request) -> JSONResponse:
    """Handle file upload. The token decides the session; the name is reduced to a base name."""
    try:
        form = await request.form()

        claims = read_token(str(form.get("token") or ""), "upload")
        if claims is None:
            return JSONResponse(
                {"error": "This upload link is invalid or has expired. Ask for a new one."},
                status_code=403,
            )
        session_id = check_session_id(claims["session_id"])

        # Get uploaded file
        uploaded_file = form.get("file")
        if not uploaded_file or not getattr(uploaded_file, "filename", None):
            return JSONResponse({"error": "No file provided"}, status_code=400)

        # Check file size
        contents = await uploaded_file.read()
        if len(contents) > MAX_UPLOAD_BYTES:
            return JSONResponse(
                {"error": f"File too large. Maximum size is {MAX_UPLOAD_MB}MB"},
                status_code=413
            )

        # A base name only, whatever folders (either kind of slash) it named
        filename = uploaded_file.filename.replace("\\", "/").rsplit("/", 1)[-1]
        try:
            filename = check_file_key(filename)
        except ValueError:
            return JSONResponse({"error": "Invalid file name"}, status_code=400)
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ("csv", "xlsx", "xls"):
            return JSONResponse(
                {"error": "Invalid file type. Supported: CSV, Excel (.xlsx, .xls)"},
                status_code=400
            )

        session_path = (exports.UPLOADS_BASE_DIR / session_id).resolve()
        session_path.mkdir(parents=True, exist_ok=True)
        file_path = (session_path / filename).resolve()
        if not file_path.is_relative_to(session_path) or file_path == session_path:
            return JSONResponse({"error": "Invalid file name"}, status_code=400)
        file_path.write_bytes(contents)

        logger.info(f"Uploaded {filename} ({len(contents)} bytes) for session {short_id(session_id)}")

        return JSONResponse({
            "success": True,
            "file_key": filename,
            "size_bytes": len(contents),
            "message": f"File '{filename}' uploaded successfully."
        })

    except Exception:
        logger.exception("Upload failed")
        return JSONResponse({"error": "Upload failed"}, status_code=500)


async def download_file(request: Request) -> FileResponse | JSONResponse:
    """
    Handle file download.

    URL: /download/{token}. The token, encrypted by this server, names the
    session, category and file; the path is rebuilt from the fixed exports
    folder and must stay inside that session's folder.
    """
    claims = read_token(request.path_params.get("token", ""), "download")
    if claims is None:
        return JSONResponse({"error": "This download link is invalid or has expired."}, status_code=403)

    category = claims["category"]
    if category not in VALID_CATEGORIES:
        return JSONResponse({"error": "Invalid link"}, status_code=403)
    try:
        session_id = check_session_id(claims["session_id"])
        filename = check_file_key(claims["filename"])
    except ValueError:
        return JSONResponse({"error": "Invalid link"}, status_code=403)

    session_dir = (exports.EXPORTS_BASE_DIR / session_id).resolve()
    file_path = (session_dir / category / filename).resolve()
    if not file_path.is_relative_to(session_dir):
        return JSONResponse({"error": "Invalid link"}, status_code=403)

    # Check if file exists
    if not file_path.is_file():
        return JSONResponse({"error": "File not found"}, status_code=404)

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

    logger.info(f"Download: {short_id(session_id)}/{category}/{filename}")

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
        Route("/download/{token}", download_file, methods=["GET"]),
    ]
