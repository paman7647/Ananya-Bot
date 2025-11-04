import asyncio
import logging
import signal
import sys
from telethon import TelegramClient, events, Button
from src.config import (
    API_ID, API_HASH, BOT_TOKEN, GEMINI_API_KEY,
    ADMIN_USER_ID, logger
)
from src.utils.database import close_db_connection
from src.utils.background_tasks import start_background_tasks
from src.utils.gemini_handler import gemini_handler
from src.utils.admin import initialize_default_personalities
from src.handlers.message_handler import setup_message_handlers
from src.handlers.admin_handler import setup_admin_handlers

# Global variables for graceful shutdown
bot = None
shutdown_event = asyncio.Event()

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_event.set()

async def main():
    """Main function to run the bot"""
    global bot

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Initialize bot
        bot = TelegramClient('bot', API_ID, API_HASH)
        await bot.start(bot_token=BOT_TOKEN)

        # Initialize default personalities
        await initialize_default_personalities()

        # Setup handlers - IMPORTANT: Admin handlers MUST be registered BEFORE message handlers
        # so admin messages are handled by admin handler, not general message handler
        await setup_admin_handlers(bot)
        await setup_message_handlers(bot)

        # Start background tasks
        start_background_tasks()

        logger.info("Bot started successfully!")

        # Create shutdown task
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        # Run the bot with shutdown handling
        try:
            # Create a task for the bot's run_until_disconnected
            bot_task = asyncio.create_task(bot.run_until_disconnected())

            # Wait for either the bot to finish or shutdown signal
            done, pending = await asyncio.wait(
                [bot_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        except asyncio.CancelledError:
            logger.info("Bot task was cancelled")

        logger.info("Bot shutdown initiated...")

    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise
    finally:
        # Cleanup
        await cleanup()

async def cleanup():
    """Cleanup resources during shutdown"""
    try:
        logger.info("Starting cleanup...")

        # Stop the bot if it's running
        if bot and not bot.is_connected():
            await bot.disconnect()
            logger.info("Bot disconnected")

        # Close database connection
        close_db_connection()

        # Cancel all background tasks
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if tasks:
            logger.info(f"Cancelling {len(tasks)} background tasks...")
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("Cleanup completed")

    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)