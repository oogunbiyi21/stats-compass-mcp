"""Test the Stats Compass Remote MCP server.

This script tests an ALREADY RUNNING server - it doesn't start one.
Run the server first with: poetry run stats-compass-remote
"""
import sys
import requests

def test_remote_server():
    """Test the remote server via HTTP."""
    print("Testing Stats Compass Remote Server at http://localhost:8000")
    print("(Server must already be running)")
    
    # Try to connect to MCP endpoint
    try:
        response = requests.get(
            "http://localhost:8000/mcp",
            headers={"Accept": "text/event-stream"},
            timeout=5
        )
        
        print(f"\n✅ Server is running!")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
        # The server should reject this with "Missing session ID" - that's expected
        if "Missing session ID" in response.text or "Bad Request" in response.text:
            print("\n✅ Server is properly enforcing MCP protocol!")
            return 0
        else:
            print(f"\n⚠️ Unexpected response from server")
            return 1
        
    except requests.exceptions.ConnectionError:
        print("\n❌ Could not connect to server. Is it running?")
        print("Start it with: poetry run stats-compass-remote")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(test_remote_server())
