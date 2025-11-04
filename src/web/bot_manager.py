from telethon import TelegramClient
from typing import Optional, Dict, Any
import asyncio
import logging
from datetime import datetime
from src.handlers.message_handler import setup_message_handlers
from src.utils.database import get_user_data

logger = logging.getLogger(__name__)

class BotManager:
    def __init__(self):
        self.client: Optional[TelegramClient] = None
        self.stats = {
            "start_time": datetime.now(),
            "total_messages": 0,
            "active_users": 0,
            "errors": 0,
            "last_error": None,
            "status": "stopped",
            "messages_per_minute": 0
        }
        self._message_count = 0
        self._last_minute = datetime.now().minute

    async def start_bot(self, config: Dict[str, Any]) -> bool:
        """Start the Telegram bot with given configuration"""
        try:
            if self.client and self.client.is_connected():
                await self.stop_bot()

            self.client = TelegramClient(
                'bot_session',
                config['api_id'],
                config['api_hash']
            )
            await self.client.start(bot_token=config['bot_token'])
            
            # Setup message handlers
            await setup_message_handlers(self.client)
            
            self.stats["status"] = "running"
            self.stats["start_time"] = datetime.now()
            logger.info("Bot started successfully")
            return True
            
        except Exception as e:
            self.stats["status"] = "error"
            self.stats["last_error"] = str(e)
            self.stats["errors"] += 1
            logger.error(f"Error starting bot: {e}")
            return False

    async def stop_bot(self) -> bool:
        """Stop the Telegram bot"""
        try:
            if self.client and self.client.is_connected():
                await self.client.disconnect()
                self.stats["status"] = "stopped"
                logger.info("Bot stopped successfully")
                return True
            return False
            
        except Exception as e:
            self.stats["last_error"] = str(e)
            self.stats["errors"] += 1
            logger.error(f"Error stopping bot: {e}")
            return False

    async def restart_bot(self, config: Dict[str, Any]) -> bool:
        """Restart the Telegram bot"""
        await self.stop_bot()
        return await self.start_bot(config)

    def update_stats(self, event_type: str, data: Any = None):
        """Update bot statistics"""
        current_minute = datetime.now().minute
        
        if current_minute != self._last_minute:
            self.stats["messages_per_minute"] = self._message_count
            self._message_count = 0
            self._last_minute = current_minute
            
        if event_type == "message":
            self._message_count += 1
            self.stats["total_messages"] += 1
        elif event_type == "error":
            self.stats["errors"] += 1
            self.stats["last_error"] = str(data)
        elif event_type == "user":
            self.stats["active_users"] = data

    async def get_active_users(self) -> int:
        """Get count of users who sent messages in the last 24 hours"""
        # This is a placeholder - implement actual database query
        return 0

    async def update_active_users(self):
        """Update active users count periodically"""
        while True:
            try:
                active_users = await self.get_active_users()
                self.stats["active_users"] = active_users
            except Exception as e:
                logger.error(f"Error updating active users: {e}")
            await asyncio.sleep(300)  # Update every 5 minutes

# Create global instance
bot_manager = BotManager()