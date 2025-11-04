from typing import Dict, Tuple, Optional

# Language code to name mapping
LANGUAGE_NAMES = {
    'auto': '🔄 Auto-detect',
    'en-IN': '🇮🇳 English (India)',
    'hi-IN': '🇮🇳 Hindi',
    'bn-IN': '🇮🇳 Bengali',
    'ta-IN': '🇮🇳 Tamil',
    'te-IN': '🇮🇳 Telugu',
    'kn-IN': '🇮🇳 Kannada',
    'ml-IN': '🇮🇳 Malayalam',
    'mr-IN': '🇮🇳 Marathi',
    'gu-IN': '🇮🇳 Gujarati',
    'pa-IN': '🇮🇳 Punjabi',
    'ur-IN': '🇮🇳 Urdu',
    'or-IN': '🇮🇳 Odia',
}

# Voice language mapping (for specific voice models)
VOICE_LANGUAGES = {
    'hi': 'hi-IN',
    'bn': 'bn-IN',
    'ta': 'ta-IN',
    'te': 'te-IN',
    'kn': 'kn-IN',
    'ml': 'ml-IN',
    'en': 'en-IN',
}

def get_language_name(lang_code: str) -> str:
    """Convert language code to readable name"""
    return LANGUAGE_NAMES.get(lang_code, lang_code)

def get_voice_language(detected_lang: str) -> str:
    """Get appropriate voice language code based on detected language"""
    # Remove region code if present (e.g. 'en-US' -> 'en')
    base_lang = detected_lang.split('-')[0]
    return VOICE_LANGUAGES.get(base_lang, 'en-IN')  # Default to Indian English if no match