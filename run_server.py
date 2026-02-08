"""Run the Delta web server.

Usage:
    python run_server.py
    python run_server.py --port 8080
"""

import argparse
import uvicorn

from src.config import get_config


def main():
    parser = argparse.ArgumentParser(description="Delta Agent Web Server")
    parser.add_argument("--host", default=None, help="Host to bind to")
    parser.add_argument("--port", type=int, default=None, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()
    
    config = get_config()
    
    host = args.host or config.web.host
    port = args.port or config.web.port
    
    print(f"🚀 Starting Delta Agent Web Server at http://{host}:{port}")
    print(f"   Press Ctrl+C to stop")
    
    uvicorn.run(
        "src.web.server:app",
        host=host,
        port=port,
        reload=args.reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()
