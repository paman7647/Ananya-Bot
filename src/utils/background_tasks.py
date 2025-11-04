import asyncio
import logging
from datetime import datetime, timedelta
from src.utils.database import update_user_activity, users_collection, user_cache

logger = logging.getLogger(__name__)

async def update_user_activity_async(user_id: int, sender=None):
    """Asynchronously update user activity"""
    try:
        await update_user_activity(user_id)
    except Exception as e:
        logger.error(f"Error in async user activity update for {user_id}: {e}")

async def cleanup_expired_cache():
    """Periodically clean up expired cache entries"""
    while True:
        try:
            current_time = datetime.now()
            expired_users = []
            
            for user_id, (_, cache_time) in user_cache.items():
                if (current_time - cache_time).seconds > 300:  # 5 minutes
                    expired_users.append(user_id)
                    
            for user_id in expired_users:
                user_cache.pop(user_id, None)
                
            await asyncio.sleep(60)  # Run every minute
            
        except Exception as e:
            logger.error(f"Error in cache cleanup: {e}")
            await asyncio.sleep(60)

async def update_user_stats():
    """Update user statistics periodically"""
    while True:
        try:
            current_time = datetime.now()
            yesterday = current_time - timedelta(days=1)
            
            # Update active users count
            active_users = users_collection.count_documents({
                'last_activity': {'$gte': yesterday}
            })
            
            logger.info(f"Active users in last 24h: {active_users}")
            await asyncio.sleep(3600)  # Run every hour
            
        except Exception as e:
            logger.error(f"Error updating user stats: {e}")
            await asyncio.sleep(3600)

def start_background_tasks():
    """Start all background tasks"""
    asyncio.create_task(cleanup_expired_cache())
    asyncio.create_task(update_user_stats())