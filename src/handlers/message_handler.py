import io
import asyncio
import logging
from datetime import datetime
from telethon import events, Button
from src.utils.error_handler import error_handler
from src.utils.database import (
    get_user_data, save_chat_history, users_collection,
    user_cache
)
from src.utils.admin_state import admin_states

from src.utils.admin import get_personality_prompt, get_personalities, get_ai_config
from src.config import DEFAULT_PERSONALITY

logger = logging.getLogger(__name__)

@error_handler()
async def handle_message(event, bot):
    """Handle incoming messages"""
    try:
        user_id = event.sender_id
        
        # Check if user is in admin panel mode - don't respond to messages
        from src.handlers.admin_handler import is_user_in_admin_mode
        if is_user_in_admin_mode(user_id):
            logger.info(f"User {user_id} is in admin mode, ignoring message")
            return
        
        # Initial processing status
        await event.respond("🤔 Processing your message...")
        
        # Show typing action while processing
        async with event.client.action(event.chat_id, 'typing'):
            # Get user data
            user_id = event.sender_id
            user_data = await get_user_data(user_id, event.sender)
            
            if user_data.get('is_blocked'):
                await event.respond("🚫 Sorry, you are blocked from using this bot.")
                return
        
        # Get language preferences
        lang_prefs = user_data.get('language_preferences', {
            'input': 'auto',
            'output': user_data.get('preferred_language', 'auto'),
            'voice': user_data.get('preferred_language', 'auto')
        })
        
        # Process message
        user_message = event.message.text
        personality = user_data.get('personality', DEFAULT_PERSONALITY)
        audio_enabled = user_data.get('audio_enabled', False)
        
        # Handle input translation if needed
        if lang_prefs['input'] != 'auto':
            from src.utils.language_manager import language_manager
            detected_lang, confidence = await language_manager.detect_language(user_message)
            if detected_lang != lang_prefs['input']:
                user_message = await language_manager.translate_text(
                    user_message,
                    target_language=lang_prefs['input']
                )
        
        # Extract media if present
        media_parts = []
        if event.message.media:
            try:
                # Show download action for media
                async with event.client.action(event.chat_id, 'upload-document'):
                    await event.respond("📥 Processing attached media...")
                    from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
                    if isinstance(event.message.media, (MessageMediaPhoto, MessageMediaDocument)):
                        media = await event.message.download_media(bytes)
                        if media:
                            media_parts.append({
                                'inline_data': {
                                    'mime_type': 'image/jpeg' if isinstance(event.message.media, MessageMediaPhoto) else 'application/octet-stream',
                                    'data': media
                                }
                            })
                            await event.respond("✅ Media processed successfully")
            except Exception as media_error:
                logger.error(f"Error processing media: {media_error}")
        
        # Get bot response with streaming
        await event.respond("🧠 Thinking...")
        async with event.client.action(event.chat_id, 'typing'):
            from src.utils.gemini_handler import gemini_handler
            from src.utils.admin import get_ai_config
            
            # Get AI config from database
            ai_config = await get_ai_config()
            
            response = await gemini_handler.get_response(
                prompt=user_message,
                personality=personality,
                media_parts=media_parts,
                model_config=ai_config,
                stream=True
            )
        
        # Translate response if needed
        if lang_prefs['output'] != 'auto' and response:
            await event.respond("🌐 Translating response...")
            async with event.client.action(event.chat_id, 'typing'):
                from src.utils.language_manager import language_manager
                response = await language_manager.translate_text(
                    response,
                    target_language=lang_prefs['output']
                )
        
        # Save chat history
        await save_chat_history(user_id, user_message, response, media_parts)
        
        # Show typing while preparing response
        async with event.client.action(event.chat_id, 'typing'):
            # Send text response
            await asyncio.sleep(0.3)  # Brief pause for natural feel
            sent_message = await event.respond(response)
        
        # Send audio response if enabled
        if audio_enabled and response:
            status_msg = None
            try:
                # Show upload action for audio
                async with event.client.action(event.chat_id, 'record-audio'):
                    from src.utils.audio_handler import audio_handler
                from telethon.tl.types import DocumentAttributeFilename
                
                # Send "thinking" message
                status_msg = await event.respond("🤔 Processing your request...")
                
                # Split long text into chunks if needed
                text_chunks = await audio_handler.split_long_text(response)
                logger.info(f"Split text into {len(text_chunks)} chunks for TTS")
                
                # Get voice language
                voice_lang = lang_prefs['voice']
                if voice_lang == 'auto':
                    async with event.client.action(event.chat_id, 'typing'):
                        from src.utils.language_manager import language_manager
                        detected_lang, _ = await language_manager.detect_language(response)
                        voice_lang = language_manager.get_voice_language(detected_lang)
                
                logger.info(f"Using voice language: {voice_lang}")
                
                # Update status to generating voice
                await status_msg.edit("🎙️ Generating voice message...")
                
                total_chunks = len(text_chunks)
                success_count = 0
                
                for i, chunk in enumerate(text_chunks, 1):
                    # Show progress for multiple chunks
                    if total_chunks > 1:
                        await status_msg.edit(f"🎙️ Generating voice part {i}/{total_chunks}...")
                    
                    logger.info(f"Generating audio for chunk {i}/{total_chunks}: {chunk[:50]}...")
                    
                    async with event.client.action(event.chat_id, 'record-audio'):
                        audio_data = await audio_handler.text_to_speech(
                            text=chunk,
                            target_lang=voice_lang
                        )
                        if audio_data:
                            # Create a file-like object from the audio data
                            audio_file = io.BytesIO(audio_data)
                            audio_file.name = f"voice_message_{i}.mp3"
                        
                            # Send as voice message using send_file
                            await event.client.send_file(
                                event.chat_id,
                                audio_file,
                                voice_note=True,
                                attributes=[DocumentAttributeFilename(audio_file.name)],
                                reply_to=sent_message.id
                            )
                            success_count += 1
                            logger.info(f"Successfully sent voice message {i}/{total_chunks}")
                        else:
                            logger.warning(f"No audio data generated for chunk {i}")
                    await asyncio.sleep(0.5)  # Small delay between audio chunks
                
                # Delete status message after completion
                if status_msg:
                    await status_msg.delete()
                
                logger.info(f"Audio generation complete: {success_count}/{total_chunks} chunks successful")
                    
            except Exception as audio_error:
                logger.error(f"Error generating audio response: {audio_error}", exc_info=True)
                # Delete status message on error
                if status_msg:
                    try:
                        await status_msg.delete()
                    except Exception as del_error:
                        logger.warning(f"Could not delete status message: {del_error}")
                
                # Send error message
                try:
                    await event.respond(
                        "Sorry, I couldn't generate the audio response. "
                        "You can adjust voice settings using /settings.",
                        reply_to=sent_message.id
                    )
                except Exception as msg_error:
                    logger.error(f"Could not send error message: {msg_error}")
        
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        await event.respond("Sorry, there was an error processing your message.")

async def get_bot_response(message: str, personality: str = DEFAULT_PERSONALITY) -> str:
    """Get response from bot using configured AI"""
    try:
        # Get personality prompt from database
        prompt = await get_personality_prompt(personality)
        if not prompt:
            # Fallback to default personality if not found in database
            prompt = "You are Ananya. You are a helpful and friendly AI with a warm, human-like personality. Talk naturally, as a real person would. Be kind, polite, and engaging. Your name is Ananya. Avoid using excessive emojis; use them only when a real person naturally would. Be a good, supportive friend. IMPORTANT: Keep your answers concise and to the point. Answer what the user asks without unnecessary filler."
        
        # Get AI config from database
        ai_config = await get_ai_config()
        
        # TODO: Implement actual AI response generation with config
        return f"Echo: {message}"
        
    except Exception as e:
        logger.error(f"Error getting bot response: {e}")
        return "Sorry, I couldn't generate a response at the moment."

async def setup_message_handlers(bot):
    """Setup message handlers for the bot"""
    @bot.on(events.NewMessage(pattern='/start'))
    @error_handler()
    async def start_handler(event):
        """Handle /start command"""
        user_id = event.sender_id
        user_data = await get_user_data(user_id, event.sender)
        
        from src.utils.admin import is_admin
        is_user_admin = await is_admin(user_id)
        
        welcome_message = (
            f"👋 Hello, {user_data.get('first_name', 'there')}!\n\n"
            "I'm Ananya, your friendly AI assistant. How can I help you today?"
        )
        
        buttons = [
            [Button.inline("🎭 Change Personality", b"change_personality")],
            [Button.inline("⚙️ Settings", b"settings")],
            [Button.inline("❓ Help", b"help")]
        ]
        
        # Add admin button if user is admin
        if is_user_admin:
            buttons.insert(0, [Button.inline("🔧 Admin Panel", b"admin_panel")])
        
        await event.respond(welcome_message, buttons=buttons)
        
    @bot.on(events.NewMessage(pattern='/settings'))
    @error_handler()
    async def settings_command(event):
        """Handle /settings command"""
        user_id = event.sender_id
        user_data = await get_user_data(user_id, event.sender)
        await show_settings_menu(event, user_data)
        
    @bot.on(events.CallbackQuery(pattern=b'settings'))
    @error_handler()
    async def settings_callback(event):
        """Handle settings button callback"""
        user_id = event.sender_id
        user_data = await get_user_data(user_id, event.sender)
        await show_settings_menu(event, user_data)
        
    async def show_settings_menu(event, user_data):
        """Show settings menu"""
        audio_status = "🔊 Enabled" if user_data.get('audio_enabled', False) else "🔇 Disabled"
        preferred_lang = user_data.get('preferred_language', 'Auto-detect')
        
        from src.utils.language_utils import get_language_name
        lang_prefs = user_data.get('language_preferences', {
            'input': 'auto',
            'output': 'auto',
            'voice': 'auto'
        })
        
        settings_message = (
            "⚙️ **Settings**\n\n"
            f"🗣 Voice Responses: {audio_status}\n"
            f"📝 Input Language: {get_language_name(lang_prefs['input'])}\n"
            f"💬 Output Language: {get_language_name(lang_prefs['output'])}\n"
            f"🎙 Voice Language: {get_language_name(lang_prefs['voice'])}\n"
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
            
    @bot.on(events.CallbackQuery(pattern=b'toggle_audio'))
    @error_handler()
    async def toggle_audio_callback(event):
        """Handle audio toggle"""
        user_id = event.sender_id
        user_data = await get_user_data(user_id, event.sender)
        
        # Toggle audio setting
        current_setting = user_data.get('audio_enabled', False)
        new_setting = not current_setting
        
        # Update database
        users_collection.update_one(
            {'user_id': user_id},
            {
                '$set': {
                    'audio_enabled': new_setting,
                    'last_settings_update': datetime.now()
                }
            }
        )
        
        # Clear user cache to ensure fresh data
        if user_id in user_cache:
            del user_cache[user_id]
        
        # Show updated settings menu
        user_data['audio_enabled'] = new_setting
        await show_settings_menu(event, user_data)
        
    @bot.on(events.CallbackQuery(pattern=b'set_input_lang|set_output_lang|set_voice_lang'))
    @error_handler()
    async def language_menu_callback(event):
        """Handle language menu selection"""
        user_id = event.sender_id
        user_data = await get_user_data(user_id, event.sender)
        
        # Determine which language type was selected
        lang_type = event.data.decode('utf-8').replace('set_', '').replace('_lang', '')
        await show_language_menu(event, user_data, lang_type)
        
    @bot.on(events.CallbackQuery(pattern=b'lang_'))
    @error_handler()
    async def language_selection_callback(event):
        """Handle language selection"""
        user_id = event.sender_id
        user_data = await get_user_data(user_id, event.sender)
        
        # Parse callback data
        data = event.data.decode('utf-8').replace('lang_', '')
        lang_parts = data.split('_')
        
        if len(lang_parts) >= 2:
            lang_type = lang_parts[0]  # input/output/voice
            lang_code = '_'.join(lang_parts[1:])  # language code (e.g., hi-IN)
            
            # Update language preference
            lang_prefs = user_data.get('language_preferences', {
                'input': 'auto',
                'output': 'auto',
                'voice': 'auto'
            })
            lang_prefs[lang_type] = lang_code
            
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
            
            # Clear user cache
            if user_id in user_cache:
                del user_cache[user_id]
                
            user_data['language_preferences'] = lang_prefs
            await show_settings_menu(event, user_data)
            
    async def show_language_menu(event, user_data, lang_type):
        """Show language selection menu"""
        from src.utils.language_utils import get_language_name
        current_lang = user_data.get('language_preferences', {}).get(lang_type, 'auto')
        menu_title = {
            'input': '📝 Select Input Language',
            'output': '💬 Select Output Language',
            'voice': '🎙 Select Voice Language'
        }
        
        message = f"{menu_title[lang_type]}\n\nCurrent: {get_language_name(current_lang)}"
        
        lang_buttons = [
            [
                Button.inline("🔄 Auto-detect", f"lang_{lang_type}_auto"),
                Button.inline("🇮🇳 Hindi", f"lang_{lang_type}_hi-IN"),
            ],
            [
                Button.inline("🇮🇳 English", f"lang_{lang_type}_en-IN"),
                Button.inline("🇮🇳 Bengali", f"lang_{lang_type}_bn-IN"),
            ],
            [
                Button.inline("🇮🇳 Tamil", f"lang_{lang_type}_ta-IN"),
                Button.inline("🇮🇳 Telugu", f"lang_{lang_type}_te-IN"),
            ],
            [
                Button.inline("🇮🇳 Kannada", f"lang_{lang_type}_kn-IN"),
                Button.inline("🇮🇳 Malayalam", f"lang_{lang_type}_ml-IN"),
            ],
            [
                Button.inline("More Languages ➡️", f"more_langs_{lang_type}"),
                Button.inline("⬅️ Back", "settings"),
            ]
        ]
        
        await event.edit(message, buttons=lang_buttons)
    
    @bot.on(events.CallbackQuery(pattern=b'change_personality'))
    @error_handler()
    async def change_personality_callback(event):
        """Handle personality change"""
        user_id = event.sender_id
        user_data = await get_user_data(user_id, event.sender)
        
        current_personality = user_data.get('personality', 'default')
        
        # Get personalities from database
        personalities_list = await get_personalities()
        personality_options = [p['name'] for p in personalities_list]
        
        # Always include 'default' if not in database
        if 'default' not in personality_options:
            personality_options.insert(0, 'default')
        
        buttons = []
        
        for i in range(0, len(personality_options), 2):
            row = []
            for j in range(2):
                if i + j < len(personality_options):
                    personality = personality_options[i + j]
                    selected = " ✅" if personality == current_personality else ""
                    row.append(Button.inline(f"{personality.title()}{selected}", f"set_personality_{personality}"))
            buttons.append(row)
        
        buttons.append([Button.inline("⬅️ Back", b"main_menu")])
        
        message = (
            "🎭 **Choose Personality**\n\n"
            f"Current: {current_personality.title()}\n\n"
            "Select a personality for Ananya:"
        )
        
        await event.edit(message, buttons=buttons)
    
    @bot.on(events.CallbackQuery(pattern=b'set_personality_'))
    @error_handler()
    async def set_personality_callback(event):
        """Handle personality selection"""
        user_id = event.sender_id
        personality = event.data.decode('utf-8').replace('set_personality_', '')
        
        # Check if personality exists in database
        prompt = await get_personality_prompt(personality)
        if prompt or personality == 'default':
            # Update database
            users_collection.update_one(
                {'user_id': user_id},
                {
                    '$set': {
                        'personality': personality,
                        'last_settings_update': datetime.now()
                    }
                }
            )
            
            # Clear cache
            if user_id in user_cache:
                del user_cache[user_id]
            
            # Get preview text
            if personality == 'default':
                preview = "Default Ananya personality - helpful and friendly AI."
            else:
                preview = prompt[:100] + "..." if len(prompt) > 100 else prompt
            
            await event.edit(
                f"✅ Personality changed to: **{personality.title()}**\n\n"
                f"{preview}",
                buttons=[[Button.inline("⬅️ Back to Settings", b"settings")]]
            )
        else:
            await event.answer("Invalid personality selection")
    
    @bot.on(events.CallbackQuery(pattern=b'help'))
    @error_handler()
    async def help_callback(event):
        """Handle help button"""
        user_id = event.sender_id
        from src.utils.admin import is_admin
        
        # Check if user is admin
        is_user_admin = await is_admin(user_id)
        
        help_message = (
            "❓ **Help & Commands**\n\n"
            "**Available Commands:**\n"
            "• `/start` - Welcome message and main menu\n"
            "• `/settings` - Configure bot preferences\n"
            "• `/help` - Show this help message\n\n"
            "**Features:**\n"
            "• 💬 Text conversations with AI\n"
            "• 🎵 Voice responses (optional)\n"
            "• 🌐 Multi-language support\n"
            "• 🎭 Customizable personalities\n"
            "• 🔍 Web search integration\n"
            "• 📸 Image understanding\n\n"
        )
        
        if is_user_admin:
            help_message += (
                "**Admin Commands:**\n"
                "• `/admin` - Open admin panel\n"
                "• `/block <user>` - Block a user\n"
                "• `/unblock <user>` - Unblock a user\n"
                "• `/stats` - Show bot statistics\n\n"
            )
        
        help_message += "For more help, contact the administrator."
        
        buttons = [[Button.inline("⬅️ Back", b"main_menu")]]
        await event.edit(help_message, buttons=buttons)
    
    @bot.on(events.CallbackQuery(pattern=b'main_menu'))
    @error_handler()
    async def main_menu_callback(event):
        """Handle main menu button"""
        user_id = event.sender_id
        user_data = await get_user_data(user_id, event.sender)
        from src.utils.admin import is_admin
        is_user_admin = await is_admin(user_id)
        
        welcome_message = (
            f"👋 Hello, {user_data.get('first_name', 'there')}!\n\n"
            "I'm Ananya, your friendly AI assistant. How can I help you today?"
        )
        
        buttons = [
            [Button.inline("🎭 Change Personality", b"change_personality")],
            [Button.inline("⚙️ Settings", b"settings")],
            [Button.inline("❓ Help", b"help")]
        ]
        
        # Add admin button if user is admin
        if is_user_admin:
            buttons.insert(0, [Button.inline("🔧 Admin Panel", b"admin_panel")])
        
        await event.edit(welcome_message, buttons=buttons)
    
    @bot.on(events.CallbackQuery(pattern=b'admin_panel'))
    @error_handler()
    async def admin_panel_callback(event):
        """Handle admin panel button"""
        user_id = event.sender_id
        from src.utils.admin import is_admin
        
        if not await is_admin(user_id):
            await event.answer("Access denied")
            return
        
        buttons = [
            [Button.inline("👥 User Management", b"user_mgmt")],
            [Button.inline("📊 Statistics", b"show_stats")],
            [Button.inline("🔄 System Status", b"system_status")],
            [Button.inline("📢 Broadcast Message", b"broadcast")],
            [Button.inline("🎭 Personality Management", b"personality_mgmt")],
            [Button.inline("👑 Admin Management", b"admin_mgmt")]
        ]
        
        await event.edit(
            "🔧 **Admin Panel**\n\nSelect an option:",
            buttons=buttons
        )
    
    @bot.on(events.CallbackQuery(pattern=b'user_mgmt'))
    @error_handler()
    async def user_management_callback(event):
        """Handle user management button"""
        user_id = event.sender_id
        from src.utils.admin import is_admin
        
        if not await is_admin(user_id):
            await event.answer("Access denied")
            return
        
        buttons = [
            [Button.inline("🚫 Block User", b"block_user")],
            [Button.inline("✅ Unblock User", b"unblock_user")],
            [Button.inline("👤 Lookup User", b"lookup_user")],
            [Button.inline("⬅️ Back", b"admin_panel")]
        ]
        
        await event.edit(
            "👥 **User Management**\n\nSelect an action:",
            buttons=buttons
        )
    
    @bot.on(events.CallbackQuery(pattern=b'show_stats'))
    @error_handler()
    async def show_stats_callback(event):
        """Handle show stats button"""
        user_id = event.sender_id
        from src.utils.admin import is_admin
        
        if not await is_admin(user_id):
            await event.answer("Access denied")
            return
        
        # Get stats
        users_collection = await get_user_data(user_id, None)  # Just to get collection access
        from src.utils.database import users_collection
        total_users = users_collection.count_documents({})
        blocked_users = users_collection.count_documents({'is_blocked': True})
        
        stats = (
            "📊 **Bot Statistics**\n\n"
            f"👥 Total Users: {total_users}\n"
            f"🚫 Blocked Users: {blocked_users}\n"
        )
        
        buttons = [[Button.inline("⬅️ Back", b"admin_panel")]]
        await event.edit(stats, buttons=buttons)
    
    @bot.on(events.CallbackQuery(pattern=b'system_status'))
    @error_handler()
    async def system_status_callback(event):
        """Handle system status button"""
        user_id = event.sender_id
        from src.utils.admin import is_admin
        
        if not await is_admin(user_id):
            await event.answer("Access denied")
            return
        
        # Get system status
        import psutil
        import platform
        
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        status = (
            "🔄 **System Status**\n\n"
            f"🖥 OS: {platform.system()} {platform.release()}\n"
            f"⚡ CPU: {cpu_usage}%\n"
            f"💾 RAM: {memory.percent}% ({memory.used//1024//1024}MB/{memory.total//1024//1024}MB)\n"
            f"💿 Disk: {disk.percent}% ({disk.used//1024//1024//1024}GB/{disk.total//1024//1024//1024}GB)\n"
        )
        
        buttons = [[Button.inline("⬅️ Back", b"admin_panel")]]
        await event.edit(status, buttons=buttons)
    
    @bot.on(events.CallbackQuery(pattern=b'broadcast'))
    @error_handler()
    async def broadcast_callback(event):
        """Handle broadcast button"""
        user_id = event.sender_id
        from src.utils.admin import is_admin
        
        if not await is_admin(user_id):
            await event.answer("Access denied")
            return
        
        message = (
            "📢 **Broadcast Message**\n\n"
            "Send me the message you want to broadcast to all users.\n"
            "The message will be sent to all active users."
        )
        
        admin_states[user_id] = "broadcast"
        buttons = [[Button.inline("⬅️ Cancel", b"admin_panel")]]
        await event.edit(message, buttons=buttons)
    
    @bot.on(events.CallbackQuery(pattern=b'personality_mgmt'))
    @error_handler()
    async def personality_management_callback(event):
        """Handle personality management button"""
        user_id = event.sender_id
        from src.utils.admin import is_admin, get_personalities
        
        if not await is_admin(user_id):
            await event.answer("Access denied")
            return
        
        personalities = await get_personalities()
        
        message = "🎭 **Personality Management**\n\n"
        if personalities:
            message += "Current personalities:\n"
            for i, personality in enumerate(personalities[:5], 1):  # Show first 5
                message += f"{i}. **{personality['name']}** - {personality['description'][:50]}...\n"
            if len(personalities) > 5:
                message += f"... and {len(personalities) - 5} more\n\n"
        else:
            message += "No custom personalities found.\n\n"
        
        buttons = [
            [Button.inline("➕ Add Personality", b"add_personality")],
            [Button.inline("🗑️ Remove Personality", b"remove_personality")],
            [Button.inline("📋 List All", b"list_personalities")],
            [Button.inline("⬅️ Back", b"admin_panel")]
        ]
        
        await event.edit(message, buttons=buttons)
    
    @bot.on(events.CallbackQuery(pattern=b'admin_mgmt'))
    @error_handler()
    async def admin_management_callback(event):
        """Handle admin management button"""
        user_id = event.sender_id
        from src.utils.admin import is_admin
        
        if not await is_admin(user_id):
            await event.answer("Access denied")
            return
        
        # Get all admins
        from src.utils.database import admins_collection
        admins = list(admins_collection.find({}, {'user_id': 1}))
        admin_ids = [admin['user_id'] for admin in admins]
        
        message = "👑 **Admin Management**\n\n"
        message += f"Current admins: {len(admin_ids)}\n"
        for admin_id in admin_ids[:5]:  # Show first 5
            message += f"• `{admin_id}`\n"
        if len(admin_ids) > 5:
            message += f"... and {len(admin_ids) - 5} more\n\n"
        
        buttons = [
            [Button.inline("➕ Add Admin", b"add_admin")],
            [Button.inline("🗑️ Remove Admin", b"remove_admin")],
            [Button.inline("📋 List All Admins", b"list_admins")],
            [Button.inline("⬅️ Back", b"admin_panel")]
        ]
        
        await event.edit(message, buttons=buttons)
    
    @bot.on(events.CallbackQuery(pattern=b'add_personality'))
    @error_handler()
    async def add_personality_callback(event):
        """Handle add personality button"""
        user_id = event.sender_id
        from src.utils.admin import is_admin
        
        if not await is_admin(user_id):
            await event.answer("Access denied")
            return
        
        message = (
            "➕ **Add New Personality**\n\n"
            "Send me the personality details in this format:\n"
            "`NAME: Description of the personality`\n\n"
            "Example:\n"
            "`Teacher: You are a patient and knowledgeable teacher who explains concepts clearly.`\n\n"
            "The description will be used as the AI prompt."
        )
        
        admin_states[user_id] = "add_personality"
        buttons = [[Button.inline("⬅️ Cancel", b"personality_mgmt")]]
        await event.edit(message, buttons=buttons)
    
    @bot.on(events.CallbackQuery(pattern=b'remove_personality'))
    @error_handler()
    async def remove_personality_callback(event):
        """Handle remove personality button"""
        user_id = event.sender_id
        from src.utils.admin import is_admin
        
        if not await is_admin(user_id):
            await event.answer("Access denied")
            return
        
        message = (
            "🗑️ **Remove Personality**\n\n"
            "Send me the name of the personality to remove.\n"
            "This action cannot be undone."
        )
        
        admin_states[user_id] = "remove_personality"
        buttons = [[Button.inline("⬅️ Cancel", b"personality_mgmt")]]
        await event.edit(message, buttons=buttons)
    
    @bot.on(events.CallbackQuery(pattern=b'add_admin'))
    @error_handler()
    async def add_admin_callback(event):
        """Handle add admin button"""
        user_id = event.sender_id
        from src.utils.admin import is_admin
        
        if not await is_admin(user_id):
            await event.answer("Access denied")
            return
        
        message = (
            "➕ **Add New Admin**\n\n"
            "Send me the user ID or username of the person to make admin.\n"
            "They will have full access to the admin panel."
        )
        
        admin_states[user_id] = "add_admin"
        buttons = [[Button.inline("⬅️ Cancel", b"admin_mgmt")]]
        await event.edit(message, buttons=buttons)
    
    @bot.on(events.CallbackQuery(pattern=b'remove_admin'))
    @error_handler()
    async def remove_admin_callback(event):
        """Handle remove admin button"""
        user_id = event.sender_id
        from src.utils.admin import is_admin
        
        if not await is_admin(user_id):
            await event.answer("Access denied")
            return
        
        message = (
            "🗑️ **Remove Admin**\n\n"
            "Send me the user ID of the admin to remove.\n"
            "This action cannot be undone."
        )
        
        admin_states[user_id] = "remove_admin"
        buttons = [[Button.inline("⬅️ Cancel", b"admin_mgmt")]]
        await event.edit(message, buttons=buttons)
    
    @bot.on(events.CallbackQuery(pattern=b'list_personalities'))
    @error_handler()
    async def list_personalities_callback(event):
        """Handle list personalities button"""
        user_id = event.sender_id
        from src.utils.admin import is_admin, get_personalities
        
        if not await is_admin(user_id):
            await event.answer("Access denied")
            return
        
        personalities = await get_personalities()
        
        message = "📋 **All Personalities**\n\n"
        if personalities:
            for i, personality in enumerate(personalities, 1):
                message += f"{i}. **{personality['name']}**\n"
                message += f"   {personality['description'][:100]}{'...' if len(personality['description']) > 100 else ''}\n\n"
        else:
            message += "No custom personalities found."
        
        buttons = [[Button.inline("⬅️ Back", b"personality_mgmt")]]
        await event.edit(message, buttons=buttons)
    
    @bot.on(events.CallbackQuery(pattern=b'list_admins'))
    @error_handler()
    async def list_admins_callback(event):
        """Handle list admins button"""
        user_id = event.sender_id
        from src.utils.admin import is_admin
        
        if not await is_admin(user_id):
            await event.answer("Access denied")
            return
        
        from src.utils.database import admins_collection
        admins = list(admins_collection.find({}, {'user_id': 1, 'added_by': 1, 'added_at': 1}))
        
        message = "👑 **All Admins**\n\n"
        if admins:
            for admin in admins:
                added_by = admin.get('added_by', 'System')
                added_at = admin.get('added_at', 'Unknown')
                if isinstance(added_at, datetime):
                    added_at = added_at.strftime('%Y-%m-%d %H:%M')
                message += f"• `{admin['user_id']}` (Added by: {added_by}, {added_at})\n"
        else:
            message += "No admins found."
        
        buttons = [[Button.inline("⬅️ Back", b"admin_mgmt")]]
        await event.edit(message, buttons=buttons)
    
    @bot.on(events.CallbackQuery(pattern=b'block_user|unblock_user|lookup_user'))
    @error_handler()
    async def user_action_callback(event):
        """Handle user action buttons"""
        user_id = event.sender_id
        from src.utils.admin import is_admin
        
        if not await is_admin(user_id):
            await event.answer("Access denied")
            return
        
        action = event.data.decode('utf-8')
        
        if action == "block_user":
            message = "🚫 **Block User**\n\nSend me the user ID or username to block:"
        elif action == "unblock_user":
            message = "✅ **Unblock User**\n\nSend me the user ID or username to unblock:"
        elif action == "lookup_user":
            message = "👤 **Lookup User**\n\nSend me the user ID or username to lookup:"
        
        # Set admin state for next message
        admin_states[user_id] = action
        
        buttons = [[Button.inline("⬅️ Cancel", b"user_mgmt")]]
        await event.edit(message, buttons=buttons)
    
    @bot.on(events.NewMessage)
    @error_handler()
    async def admin_message_handler(event):
        """Handle admin state messages"""
        user_id = event.sender_id
        from src.utils.admin import is_admin
        
        if not await is_admin(user_id):
            return
        
        if user_id in admin_states:
            action = admin_states[user_id]
            params = event.message.text.strip()
            
            if action in ["block_user", "unblock_user", "lookup_user"]:
                from src.utils.admin import lookup_user_by_input, block_user, unblock_user
                
                target_user_id = await lookup_user_by_input(params)
                if not target_user_id:
                    await event.respond(f"Could not find user: {params}")
                    return
                
                if action == "block_user":
                    if await block_user(target_user_id):
                        await event.respond(f"Successfully blocked user ID: {target_user_id}")
                    else:
                        await event.respond(f"Failed to block user ID: {target_user_id}")
                elif action == "unblock_user":
                    if await unblock_user(target_user_id):
                        await event.respond(f"Successfully unblocked user ID: {target_user_id}")
                    else:
                        await event.respond(f"Failed to unblock user ID: {target_user_id}")
                elif action == "lookup_user":
                    # Simple lookup - just show the user ID
                    await event.respond(f"User found: {target_user_id}")
                
                del admin_states[user_id]
    
            elif action == "broadcast":
                from src.utils.admin import broadcast_message
                result = await broadcast_message(params, user_id)
                
                if result['success']:
                    await event.respond(f"✅ Broadcast sent successfully!\n\n📊 Sent to: {result['success_count']} users\n❌ Failed: {result['fail_count']} users")
                else:
                    await event.respond(f"❌ Broadcast failed: {result['error']}")
                
                del admin_states[user_id]
            
            elif action == "add_personality":
                if ":" not in params:
                    await event.respond("❌ Invalid format. Use: `NAME: Description`")
                    return
                
                name, description = params.split(":", 1)
                name = name.strip()
                description = description.strip()
                
                if not name or not description:
                    await event.respond("❌ Name and description cannot be empty.")
                    return
                
                from src.utils.admin import add_personality
                success, message = await add_personality(name, description)
                
                if success:
                    await event.respond(f"✅ Personality '{name}' added successfully!")
                else:
                    await event.respond(f"❌ Failed to add personality '{name}': {message}")
                
                del admin_states[user_id]
            
            elif action == "remove_personality":
                from src.utils.admin import remove_personality
                success = await remove_personality(params)
                
                if success:
                    await event.respond(f"✅ Personality '{params}' removed successfully!")
                else:
                    await event.respond(f"❌ Failed to remove personality '{params}'. It may not exist.")
                
                del admin_states[user_id]
            
            elif action == "add_admin":
                # Try to parse as user ID first, then username
                target_user = params
                
                try:
                    target_id = int(target_user)
                except ValueError:
                    # It's a username, try to resolve it
                    try:
                        user = await bot.get_entity(target_user)
                        target_id = user.id
                    except Exception:
                        await event.respond("❌ Could not find user. Please provide a valid user ID or username.")
                        return
                
                from src.utils.database import admins_collection
                if admins_collection.find_one({"user_id": target_id}):
                    await event.respond("❌ User is already an admin.")
                    del admin_states[user_id]
                    return
                
                admins_collection.insert_one({"user_id": target_id, "added_by": user_id, "added_at": datetime.now()})
                await event.respond(f"✅ User `{target_id}` added as admin!")
                
                del admin_states[user_id]
            
            elif action == "remove_admin":
                try:
                    target_id = int(params)
                except ValueError:
                    await event.respond("❌ Please provide a valid user ID.")
                    return
                
                from src.utils.database import admins_collection
                if not admins_collection.find_one({"user_id": target_id}):
                    await event.respond("❌ User is not an admin.")
                    del admin_states[user_id]
                    return
                
                if target_id == user_id:
                    await event.respond("❌ You cannot remove yourself as admin.")
                    del admin_states[user_id]
                    return
                
                admins_collection.delete_one({"user_id": target_id})
                await event.respond(f"✅ Admin `{target_id}` removed!")
                
                del admin_states[user_id]
    
    @bot.on(events.CallbackQuery(pattern=b'more_langs'))
    @error_handler()
    async def more_languages_callback(event):
        """Handle more languages button"""
        await show_extended_language_menu(event)
    
    @bot.on(events.CallbackQuery(pattern=b'more_langs_'))
    @error_handler()
    async def more_languages_typed_callback(event):
        """Handle more languages for specific type"""
        lang_type = event.data.decode('utf-8').replace('more_langs_', '')
        await show_extended_language_menu(event, lang_type)
    
    async def show_extended_language_menu(event, lang_type='general'):
        """Show extended language menu"""
        message = "🌐 **More Languages**\n\nSelect a language:"
        
        extended_buttons = [
            [
                Button.inline("🇺🇸 English (US)", f"lang_{lang_type}_en-US"),
                Button.inline("🇬🇧 English (UK)", f"lang_{lang_type}_en-GB"),
            ],
            [
                Button.inline("🇪🇸 Spanish", f"lang_{lang_type}_es-ES"),
                Button.inline("🇫🇷 French", f"lang_{lang_type}_fr-FR"),
            ],
            [
                Button.inline("🇩🇪 German", f"lang_{lang_type}_de-DE"),
                Button.inline("🇮🇹 Italian", f"lang_{lang_type}_it-IT"),
            ],
            [
                Button.inline("🇵🇹 Portuguese", f"lang_{lang_type}_pt-BR"),
                Button.inline("🇷🇺 Russian", f"lang_{lang_type}_ru-RU"),
            ],
            [
                Button.inline("🇯🇵 Japanese", f"lang_{lang_type}_ja-JP"),
                Button.inline("🇰🇷 Korean", f"lang_{lang_type}_ko-KR"),
            ],
            [
                Button.inline("🇨🇳 Chinese", f"lang_{lang_type}_zh-CN"),
                Button.inline("🇦🇷 Arabic", f"lang_{lang_type}_ar-SA"),
            ],
            [Button.inline("⬅️ Back", b"settings")]
        ]
        
        await event.edit(message, buttons=extended_buttons)
    
    @bot.on(events.NewMessage)
    @error_handler()
    async def message_handler(event):
        """Handle all other messages"""
        user_id = event.sender_id
        
        # Check if user is in admin panel mode or admin action - don't respond to messages
        from src.handlers.admin_handler import is_user_in_admin_mode, admin_states
        if is_user_in_admin_mode(user_id) or user_id in admin_states:
            logger.info(f"User {user_id} is in admin mode, ignoring message")
            return
            
        if event.message.text.startswith('/'):
            return  # Skip other commands
            
        await handle_message(event, bot)