import os
import sys
from pathlib import Path

import uvicorn

from src.config import PORT, logger

def main():
    """Entry point when run directly"""
    # Add the project root to Python path
    project_root = str(Path(__file__).parent.parent.parent)
    sys.path.insert(0, project_root)
    os.environ["PYTHONPATH"] = project_root

    # Create static directory if it doesn't exist
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(exist_ok=True)

    logger.info("Starting web server...")

    # Run web server with proper configuration
    try:
        uvicorn.run(
            "src.web.app:app",
            host="0.0.0.0",
            port=PORT,
            reload=False,  # Disable reload in production
            workers=1,     # Single worker for simplicity
            log_level="info",
            access_log=True
        )
    except KeyboardInterrupt:
        logger.info("Web server stopped by user")
    except Exception as e:
        logger.error(f"Web server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
