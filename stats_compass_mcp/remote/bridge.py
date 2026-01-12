"""
stdio-to-HTTP bridge for MCP protocol.

Simple transparent proxy: forwards JSON-RPC between stdin/stdout and HTTP.
Handles MCP session ID management for Streamable HTTP transport.

Automatically starts the remote MCP server if not already running.
"""
import sys
import json
import logging
import subprocess
import time
import atexit
import signal
from urllib.parse import urlparse

import requests

# Log to stderr (Claude Desktop captures this)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [bridge] %(levelname)s: %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Global session ID - set after initialize request
mcp_session_id: str | None = None

# Global server process - so we can clean it up on exit
server_process: subprocess.Popen | None = None


def cleanup_server():
    """Terminate the server subprocess if we started it."""
    global server_process
    if server_process and server_process.poll() is None:
        logger.info("Shutting down remote server...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()
        logger.info("Remote server stopped")


def check_server_available(server_url: str, timeout: float = 1.0) -> bool:
    """Check if the remote server is responding."""
    try:
        # Just try a simple connection - we don't need a valid MCP request
        response = requests.get(
            server_url.replace("/mcp", "/"),  # Try base URL
            timeout=timeout
        )
        return True
    except requests.exceptions.RequestException:
        return False


def start_remote_server(port: int) -> subprocess.Popen:
    """Start the remote MCP server as a subprocess."""
    logger.info(f"Starting remote MCP server on port {port}...")
    
    # Use the same Python executable that's running the bridge
    python_exe = sys.executable
    
    # Start the server as a background process
    process = subprocess.Popen(
        [python_exe, "-m", "stats_compass_mcp.remote", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        # Don't inherit stdin - we need that for the bridge
        stdin=subprocess.DEVNULL,
    )
    
    return process


def ensure_server_running(server_url: str, max_wait: float = 10.0) -> bool:
    """Ensure the remote server is running, starting it if necessary."""
    global server_process
    
    # First check if server is already running
    if check_server_available(server_url):
        logger.info("Remote server is already running")
        return True
    
    # Parse port from URL
    parsed = urlparse(server_url)
    port = parsed.port or 8000
    
    # Start the server
    server_process = start_remote_server(port)
    
    # Register cleanup handler
    atexit.register(cleanup_server)
    signal.signal(signal.SIGTERM, lambda s, f: cleanup_server())
    
    # Wait for server to become available
    start_time = time.time()
    while time.time() - start_time < max_wait:
        # Check if process died
        if server_process.poll() is not None:
            logger.error("Remote server process died unexpectedly")
            return False
        
        if check_server_available(server_url):
            logger.info(f"Remote server started successfully on port {port}")
            return True
        
        time.sleep(0.5)
    
    logger.error(f"Timed out waiting for server to start after {max_wait}s")
    return False


def parse_sse_response(text: str) -> dict | None:
    """Parse SSE response to extract JSON data."""
    for line in text.split('\n'):
        if line.startswith('data: '):
            return json.loads(line[6:])
    return None


def proxy_message(server_url: str, message: dict) -> dict:
    """Forward JSON-RPC message to HTTP server and return response."""
    global mcp_session_id
    
    try:
        logger.debug(f"Forwarding: {message.get('method', 'unknown')}")
        
        # FastMCP requires these Accept headers
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json"
        }
        
        # Include session ID if we have one
        if mcp_session_id:
            headers["Mcp-Session-Id"] = mcp_session_id
        
        response = requests.post(
            server_url,
            json=message,
            headers=headers,
            timeout=30
        )
        
        # Capture session ID from response header (stored globally)
        new_session_id = response.headers.get('mcp-session-id')
        if new_session_id:
            mcp_session_id = new_session_id
            logger.info(f"Got MCP session ID: {mcp_session_id}")
        
        if response.status_code == 200:
            # Check if SSE format (text/event-stream)
            content_type = response.headers.get('content-type', '')
            if 'text/event-stream' in content_type:
                result = parse_sse_response(response.text)
                if result:
                    return result
                else:
                    logger.error(f"Failed to parse SSE: {response.text[:200]}")
                    # Only return error if this was a request (has id)
                    if message.get("id") is not None:
                        return {
                            "jsonrpc": "2.0",
                            "id": message["id"],
                            "error": {"code": -32603, "message": "Failed to parse SSE response"}
                        }
                    return None
            else:
                return response.json()
        else:
            logger.error(f"HTTP {response.status_code}: {response.text[:200]}")
            # Only return error if this was a request (has id)
            if message.get("id") is not None:
                return {
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "error": {
                        "code": -32000,
                        "message": f"Server error: {response.status_code}"
                    }
                }
            return None
    
    except Exception as e:
        logger.error(f"Request failed: {e}")
        # Only return error if this was a request (has id)
        if message.get("id") is not None:
            return {
                "jsonrpc": "2.0",
                "id": message["id"],
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
        return None


def run_bridge(server_url: str):
    """Main loop: read stdin, forward to HTTP, write stdout."""
    logger.info(f"Bridge starting → {server_url}")
    
    # Ensure the remote server is running (start it if needed)
    if not ensure_server_running(server_url):
        logger.error("Failed to start remote server, exiting")
        sys.exit(1)
    
    logger.info("Bridge ready, processing requests...")
    
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            
            try:
                # Parse JSON-RPC message
                message = json.loads(line)
                
                # Forward to HTTP server
                response = proxy_message(server_url, message)
                
                # Write response to stdout (only if we got one - notifications don't get responses)
                if response is not None:
                    sys.stdout.write(json.dumps(response) + "\n")
                    sys.stdout.flush()
            
            except json.JSONDecodeError as e:
                # Can't parse the message, so we can't get an id to respond to
                # Just log the error - we can't send a valid JSON-RPC error without an id
                logger.error(f"Invalid JSON from stdin: {e}")
    
    except KeyboardInterrupt:
        logger.info("Bridge stopped")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

def main():
    """Entry point for stdio bridge."""
    server_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/mcp"
    run_bridge(server_url)


if __name__ == "__main__":
    main()
