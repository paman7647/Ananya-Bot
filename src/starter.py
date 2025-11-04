import asyncio
import sys
import os
from pathlib import Path
import logging
import json
import importlib.util

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def start_web_interface():
    """Start the web interface"""
    try:
        # Import the web app module
        web_module_path = Path(__file__).parent / "web" / "run.py"
        spec = importlib.util.spec_from_file_location("web_app", web_module_path)
        web_app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(web_app)
        
        # Start web interface
        logger.info("Starting web interface...")
        await web_app.start_app()
    except Exception as e:
        logger.error(f"Failed to start web interface: {e}")
        raise

async def start_bot():
    """Start the main bot"""
    try:
        # Import the main bot module
        bot_module_path = Path(__file__).parent / "new.py"
        spec = importlib.util.spec_from_file_location("bot_app", bot_module_path)
        bot_app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bot_app)
        
        # Start bot
        logger.info("Starting bot...")
        await bot_app.main()
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

async def main():
    """Start both web interface and bot"""
    try:
        # Set Python path
        sys.path.append(str(Path(__file__).parent.parent))
        os.environ["PYTHONPATH"] = str(Path(__file__).parent.parent)
        
        # Start both services
        await asyncio.gather(
            start_web_interface(),
            start_bot()
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())