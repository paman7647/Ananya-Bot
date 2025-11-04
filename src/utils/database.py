from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import logging
import time
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from src.config import MONGO_URI, DATABASE_NAME

logger = logging.getLogger(__name__)

# MongoDB client and database initialization with connection pooling
def create_mongo_client():
    """Create MongoDB client with proper connection pooling and configuration"""
    try:
        client = MongoClient(
            MONGO_URI,
            maxPoolSize=10,  # Maximum number of connections in the connection pool
            minPoolSize=2,   # Minimum number of connections in the connection pool
            maxIdleTimeMS=30000,  # Close connections after 30 seconds of inactivity
            serverSelectionTimeoutMS=10000,  # Timeout after 10 seconds instead of 30
            connectTimeoutMS=10000,  # Connection timeout
            socketTimeoutMS=30000,   # Socket timeout increased to 30s for slow admin queries
            retryWrites=True,  # Retry writes on failure
            retryReads=True    # Retry reads on failure
        )
        # Test the connection
        client.admin.command('ping')
        logger.info("Successfully connected to MongoDB")
        return client
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise

# Initialize MongoDB client with retry logic
mongo_client = None
db = None
max_retries = 3
retry_delay = 2

for attempt in range(max_retries):
    try:
        mongo_client = create_mongo_client()
        db = mongo_client[DATABASE_NAME]
        break
    except Exception as e:
        if attempt < max_retries - 1:
            logger.warning(f"MongoDB connection attempt {attempt + 1} failed, retrying in {retry_delay}s: {e}")
            time.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff
        else:
            logger.error(f"Failed to connect to MongoDB after {max_retries} attempts: {e}")
            raise

# Collections
users_collection = db.users
chats_collection = db.chats
admins_collection = db.admins
personalities_collection = db.personalities
broadcasts_collection = db.broadcasts
ai_config_collection = db.ai_config
web_credentials_collection = db.web_credentials

# User data cache
user_cache = {}
CACHE_EXPIRY = 300  # 5 minutes

async def get_user_data(user_id: int, sender=None, force_refresh=False) -> Dict:
    """Get user data from database with caching and real-time updates"""
    try:
        current_time = datetime.now()

        # Check cache first (unless force refresh)
        if not force_refresh and user_id in user_cache:
            cached_data, cache_time = user_cache[user_id]
            if (current_time - cache_time).seconds < CACHE_EXPIRY:
                # Update last activity in background if we have sender info
                if sender:
                    from src.utils.background_tasks import update_user_activity_async
                    await update_user_activity_async(user_id, sender)
                return cached_data

        # Fetch from database
        user = users_collection.find_one({'user_id': user_id})

        # If we have sender information, update user data in real-time
        if sender:
            await _update_user_from_sender(user_id, sender, user)
            # Fetch updated data
            user = users_collection.find_one({'user_id': user_id})
        elif not user:
            # Create new user entry if doesn't exist
            user = await _create_new_user(user_id)

        # Validate and clean data
        user = _validate_and_clean_user_data(user)

        # Cache the result
        user_cache[user_id] = (user, current_time)

        return user

    except Exception as e:
        logger.error(f"Error getting user data for {user_id}: {e}")
        # Return basic user data on error
        return {
            'user_id': user_id,
            'username': None,
            'first_name': 'Unknown',
            'last_name': None,
            'joined_date': datetime.now(),
            'chat_count': 0,
            'last_activity': datetime.now(),
            'is_blocked': False,
            'personality': 'default'
        }

async def _update_user_from_sender(user_id: int, sender, existing_user=None):
    """Update user data from Telegram sender information"""
    try:
        update_data = {
            'last_activity': datetime.now()
        }

        # Extract and validate sender information
        if hasattr(sender, 'username') and sender.username:
            update_data['username'] = str(sender.username).strip()[:32]
        if hasattr(sender, 'first_name') and sender.first_name:
            update_data['first_name'] = str(sender.first_name).strip()[:64]
        if hasattr(sender, 'last_name') and sender.last_name:
            update_data['last_name'] = str(sender.last_name).strip()[:64]

        # Only update if we have meaningful data
        if len(update_data) > 1:  # More than just last_activity
            users_collection.update_one(
                {'user_id': user_id},
                {
                    '$set': update_data,
                    '$setOnInsert': {
                        'user_id': user_id,
                        'joined_date': datetime.now(),
                        'chat_count': 0,
                        'is_blocked': False,
                        'personality': 'default',
                        'first_seen': datetime.now()
                    }
                },
                upsert=True
            )

    except Exception as e:
        logger.error(f"Error updating user {user_id} from sender: {e}")

async def _create_new_user(user_id: int) -> Dict[str, Any]:
    """Create a new user entry with validated data"""
    try:
        user_data = {
            'user_id': user_id,
            'username': None,
            'first_name': None,
            'last_name': None,
            'joined_date': datetime.now(),
            'first_seen': datetime.now(),
            'chat_count': 0,
            'last_activity': datetime.now(),
            'is_blocked': False,
            'personality': 'default',
            'total_messages': 0,
            'active_days': 0,
            'last_message_date': None,
            'audio_enabled': False,  # Default to text-only responses
            'last_settings_update': datetime.now(),
            'language_preferences': {
                'interface': 'en',  # Interface language (menus, buttons)
                'input': 'auto',    # Language for user input
                'output': 'auto',   # Language for AI responses
                'voice': 'auto'     # Language for voice responses
            }
        }

        result = users_collection.insert_one(user_data)
        if result.inserted_id:
            logger.info(f"Created new user entry for {user_id}")
            return user_data
        else:
            raise Exception("Failed to insert user data")

    except Exception as e:
        logger.error(f"Error creating new user {user_id}: {e}")
        raise

def _validate_and_clean_user_data(user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate and clean user data for consistency"""
    if not user:
        return {}

    # Ensure required fields exist with proper defaults
    defaults = {
        'username': None,
        'first_name': None,
        'last_name': None,
        'joined_date': datetime.now(),
        'first_seen': user.get('joined_date', datetime.now()),
        'chat_count': 0,
        'total_messages': 0,
        'last_activity': datetime.now(),
        'is_blocked': False,
        'personality': 'default',
        'active_days': 0,
        'last_message_date': None
    }

    # Apply defaults for missing fields
    for key, default_value in defaults.items():
        if key not in user or user[key] is None:
            user[key] = default_value

    # Clean string fields
    string_fields = ['username', 'first_name', 'last_name', 'personality']
    for field in string_fields:
        if isinstance(user.get(field), str):
            user[field] = user[field].strip()
            if user[field] == '' or user[field].lower() == 'none':
                user[field] = None

    # Ensure numeric fields are valid
    numeric_fields = ['chat_count', 'total_messages', 'active_days']
    for field in numeric_fields:
        if not isinstance(user.get(field), int) or user[field] < 0:
            user[field] = 0

    # Ensure boolean fields are valid
    if not isinstance(user.get('is_blocked'), bool):
        user['is_blocked'] = False

    return user

async def update_user_activity(user_id: int, message_sent=True):
    """Update user's activity with real-time statistics"""
    try:
        current_time = datetime.now()
        current_date = current_time.date()

        # First, update the basic activity fields
        users_collection.update_one(
            {'user_id': user_id},
            {
                '$set': {
                    'last_activity': current_time
                }
            },
            upsert=True
        )

        # Then handle message counting and daily activity separately
        if message_sent:
            # Increment message counts
            users_collection.update_one(
                {'user_id': user_id},
                {
                    '$inc': {
                        'chat_count': 1,
                        'total_messages': 1
                    }
                },
                upsert=True
            )

            # Check if this is a new day for the user
            user = users_collection.find_one({'user_id': user_id}, {'last_message_date': 1})
            if user:
                last_date = user.get('last_message_date')
                if last_date and isinstance(last_date, str):
                    try:
                        last_date = datetime.fromisoformat(last_date).date()
                    except ValueError:
                        last_date = None

                if not last_date or last_date != current_date:
                    # Increment active days and update last message date
                    users_collection.update_one(
                        {'user_id': user_id},
                        {
                            '$inc': {'active_days': 1},
                            '$set': {'last_message_date': current_date.isoformat()}
                        },
                        upsert=True
                    )

        # Invalidate cache to ensure fresh data
        if user_id in user_cache:
            del user_cache[user_id]

    except Exception as e:
        logger.error(f"Error updating activity for user {user_id}: {e}")

async def save_chat_history(user_id: int, user_message: str, bot_response: str, media_parts: list = None):
    """Save chat history to database"""
    chat_data = {
        'user_id': user_id,
        'timestamp': datetime.now(),
        'user_message': user_message,
        'bot_response': bot_response,
        'media_parts': media_parts or []
    }
    chats_collection.insert_one(chat_data)

def check_db_connection() -> bool:
    """Check if database connection is healthy"""
    try:
        if mongo_client:
            mongo_client.admin.command('ping')
            return True
        return False
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False

def close_db_connection():
    """Close the MongoDB connection and cleanup resources"""
    global mongo_client, db
    try:
        if mongo_client:
            # Clear the cache
            user_cache.clear()

            # Close the connection
            mongo_client.close()
            mongo_client = None
            db = None
            logger.info("Database connection closed successfully")
    except Exception as e:
        logger.error(f"Error closing database connection: {e}")