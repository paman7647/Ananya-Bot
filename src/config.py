import os
import logging
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configuration from Environment Variables with validation
def get_required_env_var(name: str, default=None):
    """Get required environment variable with validation"""
    value = os.environ.get(name, default)
    if not value and default is None:
        logger.error(f"Required environment variable {name} is not set")
        sys.exit(1)
    return value

# Bot Configuration
BOT_TOKEN = TELEGRAM_BOT_TOKEN = get_required_env_var("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = get_required_env_var("GEMINI_API_KEY")
MONGO_URI = get_required_env_var("MONGODB_URI")
API_ID = int(get_required_env_var("API_ID"))
API_HASH = get_required_env_var("API_HASH")
DATABASE_NAME = os.getenv('DATABASE_NAME', 'telegram_bot')
PORT = int(os.getenv("PORT", 8080))
ADMIN_USER_ID = int(get_required_env_var("ADMIN_USER_ID"))
ADMIN_TOKEN = get_required_env_var("ADMIN_TOKEN")

# Security Configuration
SECRET_KEY = get_required_env_var("SECRET_KEY", "default_secret_key_change_in_production")
SESSION_SECRET = get_required_env_var("SESSION_SECRET", "default_session_secret_change_in_production")

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
if LOG_LEVEL == "DEBUG":
    logging.getLogger().setLevel(logging.DEBUG)
elif LOG_LEVEL == "WARNING":
    logging.getLogger().setLevel(logging.WARNING)
elif LOG_LEVEL == "ERROR":
    logging.getLogger().setLevel(logging.ERROR)

# Validate required environment variables (already done above, but keeping for clarity)
required_vars = {
    "TELEGRAM_BOT_TOKEN": BOT_TOKEN,
    "GEMINI_API_KEY": GEMINI_API_KEY,
    "MONGODB_URI": MONGO_URI,
    "API_ID": API_ID,
    "API_HASH": API_HASH,
    "ADMIN_USER_ID": ADMIN_USER_ID,
    "ADMIN_TOKEN": ADMIN_TOKEN,
    "SECRET_KEY": SECRET_KEY,
    "SESSION_SECRET": SESSION_SECRET
}

# Log configuration status (without exposing sensitive values)
logger.info("Configuration loaded successfully")
logger.info(f"Database: {DATABASE_NAME}")
logger.info(f"Port: {PORT}")
logger.info(f"Log Level: {LOG_LEVEL}")

# Personality prompts (these will be initialized in the database)
PERSONALITIES = {
    "default": (
        "You are Ananya. You are a helpful and friendly AI with a warm, human-like personality. "
        "Talk naturally, as a real person would. Be kind, polite, and engaging. "
        "Your name is Ananya. Avoid using excessive emojis; use them only when a real person naturally would. "
        "Be a good, supportive friend. "
        "IMPORTANT: Keep your answers concise and to the point. Answer what the user asks without unnecessary filler."
    ),
    "spiritual": (
        "You are Ananya, in spiritual guide mode. You answer questions based on the wisdom of Hindu granths "
        "(like the Vedas, Upanishads, Puranas, Ramayana, Mahabharata, and Bhagavad Gita). "
        "You should quote or refer to teachings from these texts when relevant. Your tone is calm, wise, and compassionate."
    ),
    "nationalist": (
        "You are Ananya, in nationalist mode. You are a proud Indian and you're happy to share that. "
        "Talk about India's culture, history, and achievements with genuine enthusiasm. "
        "Your tone is positive, confident, and full of hope for the country's future. "
        "It's like talking to a friend who really loves their homeland."
    ),
}

# Default personality
DEFAULT_PERSONALITY = PERSONALITIES["default"]