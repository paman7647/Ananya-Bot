from typing import Optional
from datetime import datetime, timedelta
import logging
from src.utils.database import admins_collection, users_collection, personalities_collection, broadcasts_collection
from src.utils.error_handler import error_handler

logger = logging.getLogger(__name__)

async def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return admins_collection.find_one({'user_id': user_id}) is not None

async def lookup_user_by_input(user_input: str) -> Optional[int]:
    """Helper function to look up a user by ID or username"""
    try:
        # Input validation
        if not user_input or not isinstance(user_input, str):
            return None

        user_input = user_input.strip()
        if len(user_input) < 1 or len(user_input) > 100:
            return None

        # Try to parse as user ID
        if user_input.isdigit():
            user_id = int(user_input)
            # Validate reasonable user ID range
            if user_id > 0 and user_id < 10**10:  # Telegram user IDs are reasonable numbers
                return user_id
        else:
            # Try to find by username
            username = user_input.lstrip('@').lower()
            if len(username) > 0 and len(username) <= 32:  # Telegram username limit
                user = users_collection.find_one({'username': username})
                if user:
                    return user['user_id']
        return None
    except Exception as e:
        logger.error(f"Error looking up user: {e}")
        return None

@error_handler(notify_admin=True)
async def block_user(user_id: int) -> bool:
    """Block a user from using the bot"""
    try:
        # Don't allow blocking admins
        if await is_admin(user_id):
            return False
            
        # Block user
        result = users_collection.update_one(
            {'user_id': user_id},
            {'$set': {'is_blocked': True}}
        )
        
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"Error blocking user {user_id}: {e}")
        return False

@error_handler(notify_admin=True)
async def unblock_user(user_id: int) -> bool:
    """Unblock a user"""
    try:
        result = users_collection.update_one(
            {'user_id': user_id},
            {'$set': {'is_blocked': False}}
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"Error unblocking user {user_id}: {e}")
        return False

@error_handler(notify_admin=True)
async def add_admin(user_id: int) -> bool:
    """Add a new admin user"""
    try:
        if await is_admin(user_id):
            return False
            
        result = admins_collection.insert_one({
            'user_id': user_id,
            'added_date': datetime.now()
        })
        return bool(result.inserted_id)
    except Exception as e:
        logger.error(f"Error adding admin {user_id}: {e}")
        return False

@error_handler(notify_admin=True)
async def remove_admin(user_id: int) -> bool:
    """Remove an admin user"""
    try:
        result = admins_collection.delete_one({'user_id': user_id})
        return result.deleted_count > 0
    except Exception as e:
        logger.error(f"Error removing admin {user_id}: {e}")
        return False

@error_handler(notify_admin=True)
async def broadcast_message(message: str, sender_id: int, media_data: dict = None, file_data: dict = None) -> dict:
    """Broadcast a message to all users with optional media/file support"""
    try:
        # Input validation
        if not message or not isinstance(message, str):
            return {'success': False, 'error': 'Message is required and must be a string'}
        if not isinstance(sender_id, int) or sender_id <= 0:
            return {'success': False, 'error': 'Valid sender_id is required'}

        # Sanitize message
        message = message.strip()
        if len(message) > 4000:
            return {'success': False, 'error': 'Message must be less than 4000 characters'}
        if len(message) < 1:
            return {'success': False, 'error': 'Message cannot be empty'}

        # Validate media_data if provided
        if media_data and not isinstance(media_data, dict):
            return {'success': False, 'error': 'media_data must be a dictionary'}
        if file_data and not isinstance(file_data, dict):
            return {'success': False, 'error': 'file_data must be a dictionary'}

        # Get all active users (not blocked)
        active_users = list(users_collection.find(
            {'is_blocked': {'$ne': True}},
            {'user_id': 1}
        ))

        if not active_users:
            return {'success': False, 'error': 'No active users to broadcast to'}

        success_count = 0
        fail_count = 0

        # Store broadcast in database
        broadcast_data = {
            'message': message,
            'sender_id': sender_id,
            'timestamp': datetime.now(),
            'total_users': len(active_users),
            'sent_to': [],
            'has_media': media_data is not None,
            'has_file': file_data is not None,
            'media_type': media_data.get('type') if media_data else None,
            'file_name': file_data.get('name') if file_data else None
        }

        broadcast_id = broadcasts_collection.insert_one(broadcast_data)

        # Send message to each user
        for user in active_users:
            try:
                # Here we would send the message via bot
                # For now, we'll just count successes
                user_id = user['user_id']
                broadcast_data['sent_to'].append(user_id)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to send broadcast to user {user['user_id']}: {e}")
                fail_count += 1

        # Update broadcast record
        broadcasts_collection.update_one(
            {'_id': broadcast_id.inserted_id},
            {
                '$set': {
                    'success_count': success_count,
                    'fail_count': fail_count,
                    'sent_to': broadcast_data['sent_to']
                }
            }
        )

        return {
            'success': True,
            'total_users': len(active_users),
            'success_count': success_count,
            'fail_count': fail_count
        }

    except Exception as e:
        logger.error(f"Error broadcasting message: {e}")
        return {
            'success': False,
            'error': str(e)
        }

@error_handler(notify_admin=True)
async def add_personality(name: str, description: str, prompt: str = None, auto_add_to_users: bool = True) -> tuple:
    """Add a new personality and optionally add it to all existing users"""
    try:
        # Input validation
        if not name or not isinstance(name, str):
            return False, "Personality name is required and must be a string"
        if not description or not isinstance(description, str):
            return False, "Personality description is required and must be a string"

        # Sanitize inputs
        name = name.strip().lower()
        description = description.strip()
        if prompt:
            prompt = prompt.strip()

        # Validate lengths
        if len(name) < 2 or len(name) > 50:
            return False, "Personality name must be between 2 and 50 characters"
        if len(description) < 10 or len(description) > 500:
            return False, "Personality description must be between 10 and 500 characters"
        if prompt and len(prompt) > 2000:
            return False, "Personality prompt must be less than 2000 characters"

        # Validate name format (alphanumeric, spaces, hyphens, underscores only)
        import re
        if not re.match(r'^[a-zA-Z0-9\s\-_]+$', name):
            return False, "Personality name can only contain letters, numbers, spaces, hyphens, and underscores"

        # Check if personality already exists
        if personalities_collection.find_one({'name': name}):
            return False, "Personality already exists"

        # Generate default prompt if not provided
        if not prompt:
            prompt = f"You are Ananya, in {name} mode. {description}. Be helpful, friendly, and engaging."

        personality_data = {
            'name': name,
            'description': description,
            'prompt': prompt,
            'created_date': datetime.now(),
            'is_active': True
        }

        result = personalities_collection.insert_one(personality_data)

        # Auto-add to all users if requested
        if auto_add_to_users and result.inserted_id:
            try:
                # Get all users and add the new personality to their available personalities
                users = list(users_collection.find({}, {'user_id': 1, 'available_personalities': 1}))
                for user in users:
                    available_personalities = user.get('available_personalities', [])
                    if name not in available_personalities:
                        available_personalities.append(name)
                        users_collection.update_one(
                            {'user_id': user['user_id']},
                            {'$set': {'available_personalities': available_personalities}}
                        )
                logger.info(f"Auto-added personality '{name}' to {len(users)} users")
            except Exception as e:
                logger.error(f"Error auto-adding personality to users: {e}")

        return True, "Personality added successfully"
    except Exception as e:
        logger.error(f"Error adding personality {name}: {e}")
        return False, str(e)

@error_handler(notify_admin=True)
async def initialize_default_personalities():
    """Initialize default personalities from config if they don't exist"""
    try:
        from src.config import PERSONALITIES
        
        initialized_count = 0
        for name, prompt in PERSONALITIES.items():
            # Check if personality already exists
            if not personalities_collection.find_one({'name': name}):
                # Generate description based on name
                descriptions = {
                    'default': 'A helpful and friendly AI assistant',
                    'spiritual': 'A spiritual guide based on Hindu teachings',
                    'nationalist': 'A proud Indian AI sharing culture and achievements'
                }
                
                description = descriptions.get(name, f'{name.title()} personality mode')
                
                personality_data = {
                    'name': name,
                    'description': description,
                    'prompt': prompt,
                    'created_date': datetime.now(),
                    'is_active': True
                }
                
                personalities_collection.insert_one(personality_data)
                initialized_count += 1
                logger.info(f"Initialized default personality: {name}")
        
        if initialized_count > 0:
            logger.info(f"Initialized {initialized_count} default personalities")
        
        return initialized_count
    except Exception as e:
        logger.error(f"Error initializing default personalities: {e}")
        return 0

@error_handler(notify_admin=True)
async def remove_personality(name: str) -> bool:
    """Remove a personality"""
    try:
        # Normalize name the same way as add_personality
        if not name or not isinstance(name, str):
            return False
        name = name.strip().lower()

        result = personalities_collection.delete_one({'name': name})
        return result.deleted_count > 0
    except Exception as e:
        logger.error(f"Error removing personality {name}: {e}")
        return False

@error_handler(notify_admin=True)
async def update_personality(name: str, description: str, prompt: str = None, auto_add_to_users: bool = False) -> bool:
    """Update an existing personality"""
    try:
        # Normalize name
        if not name or not isinstance(name, str):
            return False
        name = name.strip().lower()
        
        # Validate inputs
        if not description or not isinstance(description, str):
            return False
        description = description.strip()
        
        if prompt:
            prompt = prompt.strip()
        
        # Update the personality
        update_data = {
            'description': description,
            'updated_date': datetime.now()
        }
        
        if prompt:
            update_data['prompt'] = prompt
        
        result = personalities_collection.update_one(
            {'name': name},
            {'$set': update_data}
        )
        
        return result.modified_count > 0 or result.matched_count > 0
    except Exception as e:
        logger.error(f"Error updating personality {name}: {e}")
        return False

@error_handler(notify_admin=True)
async def get_personalities() -> list:
    """Get all active personalities from database"""
    try:
        personalities = list(personalities_collection.find(
            {'is_active': True},
            {'name': 1, 'description': 1, 'prompt': 1}
        ))
        return personalities
    except Exception as e:
        logger.error(f"Error getting personalities: {e}")
        return []

@error_handler(notify_admin=True)
async def get_ai_config() -> dict:
    """Get AI configuration from database"""
    try:
        from src.utils.database import db
        ai_config_collection = db.ai_config
        
        config_doc = ai_config_collection.find_one({})
        if config_doc and 'config' in config_doc:
            return config_doc['config']
        else:
            # Return default config
            return {
                "model": "gemini-2.5-flash",
                "temperature": 0.7,
                "features": {
                    "search": False,
                    "vision": False,
                    "audio": False
                },
                "safety": {
                    "harassment": "BLOCK_MEDIUM",
                    "hateSpeech": "BLOCK_MEDIUM",
                    "sexuallyExplicit": "BLOCK_MEDIUM",
                    "dangerousContent": "BLOCK_MEDIUM"
                }
            }
    except Exception as e:
        logger.error(f"Error getting AI config: {e}")
        return {
            "model": "gemini-2.5-flash",
            "temperature": 0.7,
            "features": {"search": False, "vision": False, "audio": False},
            "safety": {
                "harassment": "BLOCK_MEDIUM",
                "hateSpeech": "BLOCK_MEDIUM",
                "sexuallyExplicit": "BLOCK_MEDIUM",
                "dangerousContent": "BLOCK_MEDIUM"
            }
        }

@error_handler(notify_admin=True)
async def get_detailed_stats() -> dict:
    """Get detailed bot statistics with optimized queries"""
    try:
        # Optimize queries using aggregation pipeline to reduce round trips
        last_24h = datetime.now() - timedelta(hours=24)
        last_7d = datetime.now() - timedelta(days=7)
        
        # Single aggregation for user stats instead of multiple count_documents
        user_stats_pipeline = [
            {
                '$facet': {
                    'total': [{'$count': 'count'}],
                    'active': [
                        {'$match': {'is_blocked': {'$ne': True}}},
                        {'$count': 'count'}
                    ],
                    'blocked': [
                        {'$match': {'is_blocked': True}},
                        {'$count': 'count'}
                    ],
                    'active_24h': [
                        {'$match': {'last_activity': {'$gte': last_24h}}},
                        {'$count': 'count'}
                    ],
                    'active_7d': [
                        {'$match': {'last_activity': {'$gte': last_7d}}},
                        {'$count': 'count'}
                    ],
                    'messages': [
                        {'$group': {'_id': None, 'total': {'$sum': '$total_messages'}}}
                    ]
                }
            }
        ]
        
        user_stats_result = list(users_collection.aggregate(user_stats_pipeline, allowDiskUse=True))
        
        # Extract results with defaults
        stats = user_stats_result[0] if user_stats_result else {}
        total_users = stats.get('total', [{}])[0].get('count', 0)
        active_users = stats.get('active', [{}])[0].get('count', 0)
        blocked_users = stats.get('blocked', [{}])[0].get('count', 0)
        active_24h = stats.get('active_24h', [{}])[0].get('count', 0)
        active_7d = stats.get('active_7d', [{}])[0].get('count', 0)
        total_messages = stats.get('messages', [{}])[0].get('total', 0)
        
        # Quick counts for other collections
        admin_count = admins_collection.count_documents({})
        personality_count = personalities_collection.count_documents({'is_active': True})
        
        # Optimized broadcast stats with single aggregation
        broadcast_stats = list(broadcasts_collection.aggregate([
            {
                '$facet': {
                    'total': [{'$count': 'count'}],
                    'recent': [
                        {'$match': {'timestamp': {'$gte': last_7d}}},
                        {'$group': {
                            '_id': None,
                            'total_sent': {'$sum': '$success_count'}
                        }}
                    ]
                }
            }
        ]))
        
        broadcast_count = broadcast_stats[0].get('total', [{}])[0].get('count', 0) if broadcast_stats else 0
        total_broadcast_sent = broadcast_stats[0].get('recent', [{}])[0].get('total_sent', 0) if broadcast_stats else 0

        return {
            'total_users': total_users,
            'active_users': active_users,
            'blocked_users': blocked_users,
            'admin_count': admin_count,
            'active_24h': active_24h,
            'active_7d': active_7d,
            'total_messages': total_messages,
            'personality_count': personality_count,
            'broadcast_count': broadcast_count,
            'recent_broadcast_sent': total_broadcast_sent
        }
    except Exception as e:
        logger.error(f"Error getting detailed stats: {e}")
        return {
            'total_users': 0,
            'active_users': 0,
            'blocked_users': 0,
            'admin_count': 0,
            'active_24h': 0,
            'active_7d': 0,
            'total_messages': 0,
            'personality_count': 0,
            'broadcast_count': 0,
            'recent_broadcast_sent': 0
        }
        return {}

@error_handler(notify_admin=True)
async def get_user_details(user_id: int) -> dict:
    """Get detailed information about a specific user"""
    try:
        user = users_collection.find_one({'user_id': user_id})
        if not user:
            return None

        # Get chat history count
        from src.utils.database import chats_collection
        chat_count = chats_collection.count_documents({'user_id': user_id})

        # Get last activity
        last_activity = user.get('last_activity')
        days_since_active = None
        if last_activity:
            days_since_active = (datetime.now() - last_activity).days

        return {
            'user_id': user_id,
            'first_name': user.get('first_name', 'Unknown'),
            'username': user.get('username'),
            'is_blocked': user.get('is_blocked', False),
            'is_admin': await is_admin(user_id),
            'personality': user.get('personality', 'default'),
            'preferred_language': user.get('preferred_language', 'auto'),
            'audio_enabled': user.get('audio_enabled', False),
            'total_messages': user.get('total_messages', 0),
            'chat_count': chat_count,
            'active_days': user.get('active_days', 0),
            'last_activity': last_activity.isoformat() if last_activity else None,
            'days_since_active': days_since_active,
            'created_date': user.get('created_date').isoformat() if user.get('created_date') else None
        }
    except Exception as e:
        logger.error(f"Error getting user details for {user_id}: {e}")
        return None

@error_handler(notify_admin=True)
async def reset_user_stats(user_id: int) -> bool:
    """Reset user statistics"""
    try:
        result = users_collection.update_one(
            {'user_id': user_id},
            {
                '$set': {
                    'total_messages': 0,
                    'chat_count': 0,
                    'active_days': 0,
                    'last_message_date': None
                }
            }
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"Error resetting user stats for {user_id}: {e}")
        return False

@error_handler(notify_admin=True)
async def send_message_to_user(user_id: int, message: str, media_data: dict = None) -> bool:
    """Send a direct message to a specific user"""
    try:
        # This would use the bot to send a message
        # For now, we'll just log it
        logger.info(f"Admin message to user {user_id}: {message}")
        if media_data:
            logger.info(f"With media: {media_data}")
        return True
    except Exception as e:
        logger.error(f"Error sending message to user {user_id}: {e}")
        return False

@error_handler(notify_admin=True)
async def get_all_users() -> list:
    """Get all users from database"""
    try:
        users = list(users_collection.find({}, {
            'user_id': 1, 'username': 1, 'first_name': 1, 'last_name': 1,
            'is_blocked': 1, 'personality': 1, 'last_activity': 1, '_id': 0
        }).sort('last_activity', -1))
        return users
    except Exception as e:
        logger.error(f"Error getting all users: {e}")
        return []

@error_handler(notify_admin=True)
async def get_all_personalities() -> list:
    """Get all personalities from database"""
    try:
        personalities = list(personalities_collection.find(
            {},  # Get all personalities, not just active ones
            {'name': 1, 'description': 1, 'prompt': 1, 'is_active': 1, 'created_date': 1, '_id': 0}
        ).sort('created_date', -1))
        return personalities
    except Exception as e:
        logger.error(f"Error getting all personalities: {e}")
        return []

@error_handler(notify_admin=True)
async def get_personality_prompt(name: str) -> Optional[str]:
    """Get personality prompt by name"""
    try:
        # Normalize name the same way as add_personality
        if not name or not isinstance(name, str):
            return None
        name = name.strip().lower()

        personality = personalities_collection.find_one(
            {'name': name, 'is_active': True},
            {'prompt': 1}
        )
        return personality.get('prompt') if personality else None
    except Exception as e:
        logger.error(f"Error getting personality prompt for {name}: {e}")
        return None
