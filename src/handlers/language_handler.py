from telethon import events, Button
from src.utils.error_handler import error_handler
from src.utils.database import users_collection, user_cache, get_user_data
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Language configurations with flags, display names, and native names
LANGUAGES = {
    'auto': ('🔄', 'Auto-detect', 'Auto-detect'),
    'hi-IN': ('🇮🇳', 'Hindi', 'हिन्दी'),
    'bn-IN': ('🇮🇳', 'Bengali', 'বাংলা'),
    'te-IN': ('🇮🇳', 'Telugu', 'తెలుగు'),
    'ta-IN': ('🇮🇳', 'Tamil', 'தமிழ்'),
    'mr-IN': ('🇮🇳', 'Marathi', 'मराठी'),
    'ur-IN': ('🇮🇳', 'Urdu', 'اردو'),
    'gu-IN': ('🇮🇳', 'Gujarati', 'ગુજરાતી'),
    'kn-IN': ('🇮🇳', 'Kannada', 'ಕನ್ನಡ'),
    'ml-IN': ('🇮🇳', 'Malayalam', 'മലയാളം'),
    'or-IN': ('🇮🇳', 'Odia', 'ଓଡ଼ିଆ'),
    'pa-IN': ('🇮🇳', 'Punjabi', 'ਪੰਜਾਬੀ'),
    'as-IN': ('🇮🇳', 'Assamese', 'অসমীয়া'),
    'mai-IN': ('🇮🇳', 'Maithili', 'मैथिली'),
    'sat-IN': ('🇮🇳', 'Santali', 'ᱥᱟᱱᱛᱟᱲᱤ'),
    'ks-IN': ('🇮🇳', 'Kashmiri', 'कॉशुर'),
    'sd-IN': ('🇮🇳', 'Sindhi', 'سنڌي'),
    'kok-IN': ('🇮🇳', 'Konkani', 'कोंकणी'),
    'doi-IN': ('🇮🇳', 'Dogri', 'डोगरी'),
    'brx-IN': ('🇮🇳', 'Bodo', 'बड़ो'),
    'sa-IN': ('🇮🇳', 'Sanskrit', 'संस्कृतम्'),
    'nep-IN': ('🇮🇳', 'Nepali', 'नेपाली'),
    'mni-IN': ('��', 'Manipuri', 'মৈতৈলোন্'),
    'bho-IN': ('🇮🇳', 'Bhojpuri', 'भोजपुरी'),
    'en-IN': ('��', 'English (India)', 'English')
}

def format_lang_name(lang_code: str) -> str:
    """Format language name with flag and native name"""
    flag, name, native = LANGUAGES.get(lang_code, LANGUAGES['auto'])
    if native == name:
        return f"{flag} {name}"
    return f"{flag} {native} ({name})"

async def get_language_buttons(current_page: int = 0, items_per_page: int = 6) -> list:
    """Get paginated language selection buttons"""
    # Convert languages dict to list, excluding 'auto'
    all_languages = [(code, data) for code, data in LANGUAGES.items() if code != 'auto']
    
    # Calculate pagination
    total_pages = (len(all_languages) + items_per_page - 1) // items_per_page
    start_idx = current_page * items_per_page
    end_idx = start_idx + items_per_page
    page_languages = all_languages[start_idx:end_idx]
    
    # Create buttons for current page
    buttons = []
    current_row = []
    
    # Add auto-detect option on first page
    if current_page == 0:
        buttons.append([Button.inline(
            format_lang_name('auto'),
            b'lang_auto'
        )])
    
    # Add language buttons
    for lang_code, (flag, name, native) in page_languages:
        current_row.append(Button.inline(
            format_lang_name(lang_code),
            f"lang_{lang_code}".encode()
        ))
        
        if len(current_row) == 2:
            buttons.append(current_row)
            current_row = []
    
    if current_row:
        buttons.append(current_row)
    
    # Add navigation buttons
    nav_buttons = []
    if current_page > 0:
        nav_buttons.append(Button.inline("⬅️ Previous", f"lang_page_{current_page-1}".encode()))
    if current_page < total_pages - 1:
        nav_buttons.append(Button.inline("Next ➡️", f"lang_page_{current_page+1}".encode()))
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # Add back to settings button
    buttons.append([Button.inline("⬅️ Back to Settings", b"settings")])
    
    return buttons

async def setup_language_handlers(bot):
    """Setup handlers for language selection"""
    
    @bot.on(events.CallbackQuery(pattern=b'lang_page_'))
    @error_handler()
    async def language_page_callback(event):
        """Handle language page navigation"""
        page = int(event.data.decode('utf-8').split('_')[-1])
        buttons = await get_language_buttons(page)
        
        await event.edit(
            "🗣️ **Language Selection**\n\n"
            "Choose your preferred language:",
            buttons=buttons
        )
    
    @bot.on(events.CallbackQuery(pattern=b'more_langs'))
    @error_handler()
    async def more_languages_callback(event):
        """Show language selection menu"""
        buttons = await get_language_buttons()
        
        await event.edit(
            "🗣️ **Language Selection**\n\n"
            "Choose your preferred language:",
            buttons=buttons
        )
    
    @bot.on(events.CallbackQuery(pattern=b'lang_'))
    @error_handler()
    async def language_selection_callback(event):
        """Handle language selection"""
        if event.data.startswith(b'lang_page_'):
            return  # Let the page navigation handler handle this
            
        user_id = event.sender_id
        selected_lang = event.data.decode('utf-8')[5:]  # Remove 'lang_' prefix
        
        try:
            # Update user's language preferences
            lang_prefs = {
                'input': selected_lang if selected_lang != 'auto' else 'auto',
                'output': selected_lang if selected_lang != 'auto' else 'en-IN',
                'voice': selected_lang if selected_lang != 'auto' else 'en-IN'
            }
            
            # Update database
            users_collection.update_one(
                {'user_id': user_id},
                {
                    '$set': {
                        'language_preferences': lang_prefs,
                        'last_settings_update': datetime.now()
                    }
                }
            )
            
            # Clear cache to ensure fresh data
            if user_id in user_cache:
                del user_cache[user_id]
            
            # Show confirmation
            flag, name, native = LANGUAGES.get(selected_lang, LANGUAGES['auto'])
            await event.answer(f"Language set to: {flag} {native}")
            
            # Refresh settings menu
            user_data = await get_user_data(user_id, event.sender)
            from src.handlers.settings_handler import show_settings_menu
            await show_settings_menu(event, user_data)
            
        except Exception as e:
            logger.error(f"Error setting language: {e}")
            await event.answer("❌ Failed to update language settings")

# Simplified character range checks for language detection
SCRIPT_RANGES = {
    'hi-IN': [
        (0x0900, 0x097F),  # Devanagari
        (0xA8E0, 0xA8FF),  # Devanagari Extended
    ],
    'bn-IN': [
        (0x0980, 0x09FF),  # Bengali
    ],
    'ta-IN': [
        (0x0B80, 0x0BFF),  # Tamil
    ],
    'te-IN': [
        (0x0C00, 0x0C7F),  # Telugu
    ],
    'gu-IN': [
        (0x0A80, 0x0AFF),  # Gujarati
    ],
    'kn-IN': [
        (0x0C80, 0x0CFF),  # Kannada
    ],
    'ml-IN': [
        (0x0D00, 0x0D7F),  # Malayalam
    ],
    'or-IN': [
        (0x0B00, 0x0B7F),  # Oriya
    ],
    'pa-IN': [
        (0x0A00, 0x0A7F),  # Gurmukhi
    ],
    'ur-IN': [
        (0x0600, 0x06FF),  # Arabic (for Urdu)
    ],
    'sa-IN': [
        (0x0900, 0x097F),  # Devanagari (for Sanskrit)
    ]
}

async def detect_language(text: str) -> tuple:
    """
    Detect language based on character ranges.
    Returns (language_code, confidence)
    """
    if not text:
        return 'en-IN', 0.5
        
    # Count characters in each script range
    script_counts = {}
    total_chars = 0
    
    for char in text:
        total_chars += 1
        char_code = ord(char)
        
        # Check each language's script ranges
        for lang, ranges in SCRIPT_RANGES.items():
            for start, end in ranges:
                if start <= char_code <= end:
                    script_counts[lang] = script_counts.get(lang, 0) + 1
                    break
    
    if not script_counts:
        return 'en-IN', 0.8  # Default to English
    
    # Find the most used script
    max_lang = max(script_counts.items(), key=lambda x: x[1])
    confidence = max_lang[1] / total_chars
    
    return max_lang[0], confidence

async def translate_text(text: str, target_lang: str, source_lang: str = None) -> str:
    """
    Simple character substitution-based translation (for demonstration only).
    In production, use a proper translation service.
    """
    if not text or target_lang == 'auto':
        return text
        
    # For demonstration, we'll just append the target language
    return f"{text} [{target_lang}]"