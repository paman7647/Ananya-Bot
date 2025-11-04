from telethon import events, Button
from src.utils.error_handler import error_handler
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

async def show_settings_menu(event, user_data):
    """Show settings menu"""
    from src.utils.language_manager import get_language_name
    from src.handlers.language_handler import LANGUAGES
    
    audio_status = "🔊 Enabled" if user_data.get('audio_enabled', False) else "🔇 Disabled"
    lang_prefs = user_data.get('language_preferences', {
        'input': 'auto',
        'output': 'auto',
        'voice': 'auto'
    })
    
    # Format language names
    def format_lang(lang_code):
        flag, name, native = LANGUAGES.get(lang_code, LANGUAGES['auto'])
        if native == name:
            return f"{flag} {name}"
        return f"{flag} {native} ({name})"
    
    settings_message = (
        "⚙️ **Settings**\n\n"
        f"🗣 Voice Responses: {audio_status}\n"
        f"📝 Input Language: {format_lang(lang_prefs['input'])}\n"
        f"💬 Output Language: {format_lang(lang_prefs['output'])}\n"
        f"🎙 Voice Language: {format_lang(lang_prefs['voice'])}\n"
        f"🎭 Current Personality: {user_data.get('personality', 'default')}\n\n"
        "Select a setting to modify:"
    )
    
    buttons = [
        [Button.inline(
            "🔊 Disable Voice" if user_data.get('audio_enabled', False) else "🔇 Enable Voice",
            b"toggle_audio"
        )],
        [
            Button.inline("📝 Input Language", b"set_input_lang"),
            Button.inline("💬 Output Language", b"set_output_lang")
        ],
        [
            Button.inline("🎙 Voice Language", b"set_voice_lang"),
            Button.inline("🎭 Personality", b"change_personality")
        ],
        [Button.inline("⬅️ Back", b"main_menu")]
    ]
    
    if isinstance(event, events.CallbackQuery.Event):
        await event.edit(settings_message, buttons=buttons)
    else:
        await event.respond(settings_message, buttons=buttons)