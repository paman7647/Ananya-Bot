from telethon import events, Button
from telethon.errors import MessageNotModifiedError
import logging
from src.utils.error_handler import error_handler
from src.utils.admin import (
    is_admin, block_user, unblock_user, lookup_user_by_input,
    broadcast_message, add_personality, remove_personality,
    get_detailed_stats, get_user_details
)
from src.utils.database import users_collection, get_user_data
from src.config import ADMIN_USER_ID

logger = logging.getLogger(__name__)

async def safe_edit_message(event, text, buttons=None):
    """Safely edit a message, handling MessageNotModifiedError"""
    try:
        await event.edit(text, buttons=buttons)
    except MessageNotModifiedError:
        # Message content hasn't changed, just acknowledge the callback
        await event.answer()

from src.utils.admin_state import admin_states, admin_sessions

def is_user_in_admin_mode(user_id):
    """Check if user is in admin mode and clean up expired sessions"""
    from datetime import datetime
    
    # Clean up expired sessions (30 minutes timeout)
    current_time = datetime.now().timestamp()
    expired_users = []
    
    for uid, timestamp in admin_sessions.items():
        if current_time - timestamp > 1800:  # 30 minutes
            expired_users.append(uid)
    
    for uid in expired_users:
        del admin_sessions[uid]
        if uid in admin_states:
            del admin_states[uid]
    
    # User is in admin mode if they have an active session OR active state
    return user_id in admin_sessions or user_id in admin_states

# Admin panel pagination
ADMIN_PANEL_ITEMS = [
    {"text": "👥 User Management", "callback": b"user_mgmt"},
    {"text": "📢 Broadcast Message", "callback": b"broadcast"},
    {"text": "🎭 Personality Management", "callback": b"personality_mgmt"},
    {"text": "🔐 Web Credentials", "callback": b"web_credentials"},
    {"text": "📊 Statistics", "callback": b"show_stats"},
    {"text": "🔄 System Status", "callback": b"system_status"}
]

ITEMS_PER_PAGE = 4  # 2x2 grid
ITEMS_PER_ROW = 2

@error_handler()
async def handle_admin_command(event, command: str, params: str = None):
    """Handle admin commands"""
    user_id = event.sender_id
    
    if not await is_admin(user_id):
        await event.respond("You don't have permission to use admin commands.")
        return
        
    try:
        if command == "block":
            if not params:
                await event.respond("Please provide a user ID or username to block.")
                return
                
            target_user_id = await lookup_user_by_input(params)
            if not target_user_id:
                await event.respond(f"Could not find user: {params}")
                return
                
            if await block_user(target_user_id):
                await event.respond(f"Successfully blocked user ID: {target_user_id}")
            else:
                await event.respond(f"Failed to block user ID: {target_user_id}")
                
        elif command == "unblock":
            if not params:
                await event.respond("Please provide a user ID or username to unblock.")
                return
                
            target_user_id = await lookup_user_by_input(params)
            if not target_user_id:
                await event.respond(f"Could not find user: {params}")
                return
                
            if await unblock_user(target_user_id):
                await event.respond(f"Successfully unblocked user ID: {target_user_id}")
            else:
                await event.respond(f"Failed to unblock user ID: {target_user_id}")
                
        elif command == "stats":
            await show_stats(event)
            
        elif command == "lookup":
            if not params:
                await event.respond("Please provide a user ID or username to lookup.")
                return
                
            target_user_id = await lookup_user_by_input(params)
            if not target_user_id:
                await event.respond(f"Could not find user: {params}")
                return
                
            user_details = await get_user_details(target_user_id)
            if user_details:
                details_msg = (
                    f"👤 **User Details**\n\n"
                    f"🆔 ID: `{user_details['user_id']}`\n"
                    f"👤 Name: {user_details.get('first_name', 'Unknown')}\n"
                    f"📱 Username: @{user_details.get('username', 'None')}\n"
                    f"🚫 Blocked: {'Yes' if user_details.get('is_blocked') else 'No'}\n"
                    f"🎭 Personality: {user_details.get('personality', 'default')}\n"
                    f"💬 Messages: {user_details.get('total_messages', 0)}\n"
                    f"📅 Last Active: {user_details.get('last_activity', 'Never')}\n"
                )
                await event.respond(details_msg, parse_mode='markdown')
            else:
                await event.respond(f"Could not retrieve details for user: {params}")
            
    except Exception as e:
        logger.error(f"Error handling admin command: {e}")
        await event.respond(f"Error executing command: {str(e)}")

async def show_stats(event):
    """Show bot statistics"""
    try:
        stats = await get_detailed_stats()
        
        stats_msg = (
            "📊 **Bot Statistics**\n\n"
            f"👥 Total Users: {stats['total_users']}\n"
            f"✅ Active Users: {stats['active_users']}\n"
            f"🚫 Blocked Users: {stats['blocked_users']}\n"
            f"🎭 Personalities: {stats['personality_count']}\n"
            f"� Broadcasts: {stats['broadcast_count']}\n"
            f"📅 Total Messages: {stats['total_messages']}\n"
            f"📅 Active (24h): {stats['active_24h']}\n"
            f"📅 Active (7d): {stats['active_7d']}\n"
        )
        
        await event.respond(stats_msg, parse_mode='markdown')
        
    except Exception as e:
        logger.error(f"Error showing stats: {e}")
        await event.respond("Error retrieving statistics.")

async def show_personalities(event):
    """Show available personalities"""
    try:
        from src.utils import admin
        personalities = await admin.get_all_personalities()
        
        if not personalities:
            await event.edit("🎭 **Personalities**\n\nNo personalities configured.", buttons=[[Button.inline("⬅️ Back", b"personality_mgmt")]])
            return
        
        personality_list = "🎭 **Available Personalities**\n\n"
        for personality in personalities:
            personality_list += f"• **{personality['name']}**: {personality['description']}\n"
        
        buttons = [[Button.inline("⬅️ Back", b"personality_mgmt")]]
        await event.edit(personality_list, buttons=buttons)
        
    except Exception as e:
        logger.error(f"Error showing personalities: {e}")
        await event.edit("Error retrieving personalities.", buttons=[[Button.inline("⬅️ Back", b"personality_mgmt")]])

async def show_credentials(event):
    """Show web credentials usernames"""
    try:
        # Get credentials directly from database
        from src.utils.database import db
        
        web_credentials_collection = db.web_credentials
        creds_doc = web_credentials_collection.find_one({})
        
        if not creds_doc or 'credentials' not in creds_doc:
            await event.edit("🔐 **Web Credentials**\n\nNo credentials configured.\n\nDefault: `admin` / `admin123`", buttons=[[Button.inline("⬅️ Back", b"web_credentials")]])
            return
        
        usernames = list(creds_doc['credentials'].keys())
        
        if not usernames:
            await event.edit("🔐 **Web Credentials**\n\nNo credentials configured.\n\nDefault: `admin` / `admin123`", buttons=[[Button.inline("⬅️ Back", b"web_credentials")]])
            return
        
        credential_list = "🔐 **Web Credentials**\n\nConfigured usernames:\n\n"
        for username in usernames:
            credential_list += f"• `{username}`\n"
        
        credential_list += "\n💡 Use /login in web dashboard to access"
        
        buttons = [[Button.inline("⬅️ Back", b"web_credentials")]]
        await event.edit(credential_list, buttons=buttons)
        
    except Exception as e:
        logger.error(f"Error showing credentials: {e}")
        await event.edit("❌ Error retrieving credentials.", buttons=[[Button.inline("⬅️ Back", b"web_credentials")]])

def create_admin_panel_page(page: int = 0):
    """Create admin panel buttons for a specific page"""
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    
    current_items = ADMIN_PANEL_ITEMS[start_idx:end_idx]
    
    # Create buttons in rows
    buttons = []
    for i in range(0, len(current_items), ITEMS_PER_ROW):
        row_items = current_items[i:i + ITEMS_PER_ROW]
        row = [Button.inline(item["text"], item["callback"]) for item in row_items]
        buttons.append(row)
    
    # Add navigation buttons
    nav_buttons = []
    
    if page > 0:
        nav_buttons.append(Button.inline("⬅️ Previous", f"admin_page_{page-1}".encode()))
    
    # Show current page info
    total_pages = (len(ADMIN_PANEL_ITEMS) - 1) // ITEMS_PER_PAGE + 1
    nav_buttons.append(Button.inline(f"📄 {page+1}/{total_pages}", b"admin_page_info"))
    
    if end_idx < len(ADMIN_PANEL_ITEMS):
        nav_buttons.append(Button.inline("Next ➡️", f"admin_page_{page+1}".encode()))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # Add exit admin button
    buttons.append([Button.inline("🚪 Exit Admin Panel", b"exit_admin")])
    
    return buttons
    
    # Add navigation buttons
    nav_buttons = []
    
    if page > 0:
        nav_buttons.append(Button.inline("⬅️ Previous", f"admin_page_{page-1}".encode()))
    
    # Show current page info
    total_pages = (len(ADMIN_PANEL_ITEMS) - 1) // ITEMS_PER_PAGE + 1
    nav_buttons.append(Button.inline(f"📄 {page+1}/{total_pages}", b"admin_page_info"))
    
    if end_idx < len(ADMIN_PANEL_ITEMS):
        nav_buttons.append(Button.inline("Next ➡️", f"admin_page_{page+1}".encode()))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # Add exit admin button
    buttons.append([Button.inline("🚪 Exit Admin Panel", b"exit_admin")])
    
    return buttons

async def setup_admin_handlers(bot):
    """Setup admin handlers for the bot"""
    @bot.on(events.NewMessage(pattern=r'/admin'))
    @error_handler()
    async def admin_panel(event):
        """Show admin panel"""
        user_id = event.sender_id
        
        if not await is_admin(user_id):
            await event.respond("You don't have permission to access the admin panel.")
            return
        
        # Mark user as being in admin panel
        from datetime import datetime
        admin_sessions[user_id] = datetime.now().timestamp()
            
        buttons = create_admin_panel_page(0)
        
        await event.respond(
            "🔧 **Admin Panel**\n\nSelect an option:",
            buttons=buttons,
            parse_mode='markdown'
        )
    
    @bot.on(events.NewMessage(pattern=r'/block'))
    @error_handler()
    async def block_command(event):
        """Handle /block command"""
        params = event.message.text.split(maxsplit=1)
        params = params[1] if len(params) > 1 else None
        await handle_admin_command(event, "block", params)
    
    @bot.on(events.NewMessage(pattern=r'/unblock'))
    @error_handler()
    async def unblock_command(event):
        """Handle /unblock command"""
        params = event.message.text.split(maxsplit=1)
        params = params[1] if len(params) > 1 else None
        await handle_admin_command(event, "unblock", params)
    
    @bot.on(events.NewMessage(pattern=r'/stats'))
    @error_handler()
    async def stats_command(event):
        """Handle /stats command"""
        await handle_admin_command(event, "stats")
    
    @bot.on(events.CallbackQuery(pattern=b'user_mgmt'))
    @error_handler()
    async def user_management_callback(event):
        """Handle user management button"""
        user_id = event.sender_id
        
        if not await is_admin(user_id):
            await event.answer("Access denied")
            return
        
        # Refresh admin session
        from datetime import datetime
        admin_sessions[user_id] = datetime.now().timestamp()
        
        buttons = [
            [Button.inline("🚫 Block User", b"block_user")],
            [Button.inline("✅ Unblock User", b"unblock_user")],
            [Button.inline("👤 Lookup User", b"lookup_user")],
            [Button.inline("⬅️ Back", b"admin_panel")]
        ]
        
        await safe_edit_message(
            event,
            "👥 **User Management**\n\nSelect an action:",
            buttons=buttons
        )
    
    @bot.on(events.CallbackQuery(pattern=b'show_stats'))
    @error_handler()
    async def show_stats_callback(event):
        """Handle show stats button"""
        user_id = event.sender_id
        
        if not await is_admin(user_id):
            await event.answer("Access denied")
            return
        
        await show_stats(event)
    
    @bot.on(events.CallbackQuery(pattern=b'system_status'))
    @error_handler()
    async def system_status_callback(event):
        """Handle system status button"""
        user_id = event.sender_id
        
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
        
        if not await is_admin(user_id):
            await event.answer("Access denied")
            return
        
        buttons = [
            [Button.inline("📝 Send Text Message", b"broadcast_text")],
            [Button.inline("📎 Send with Media", b"broadcast_media")],
            [Button.inline("⬅️ Back", b"admin_panel")]
        ]
        
        await event.edit(
            "📢 **Broadcast Message**\n\nChoose broadcast type:",
            buttons=buttons
        )
    
    @bot.on(events.CallbackQuery(pattern=b'personality_mgmt'))
    @error_handler()
    async def personality_management_callback(event):
        """Handle personality management button"""
        user_id = event.sender_id
        
        if not await is_admin(user_id):
            await event.answer("Access denied")
            return
        
        buttons = [
            [Button.inline("➕ Add Personality", b"add_personality")],
            [Button.inline("➖ Remove Personality", b"remove_personality")],
            [Button.inline("📋 List Personalities", b"list_personalities")],
            [Button.inline("⬅️ Back", b"admin_panel")]
        ]
        
        await event.edit(
            "🎭 **Personality Management**\n\nSelect an action:",
            buttons=buttons
        )
    
    @bot.on(events.CallbackQuery(pattern=b'web_credentials'))
    @error_handler()
    async def web_credentials_callback(event):
        """Handle web credentials management button"""
        user_id = event.sender_id
        
        if not await is_admin(user_id):
            await event.answer("Access denied")
            return
        
        buttons = [
            [Button.inline("➕ Add/Update Credentials", b"add_credentials")],
            [Button.inline("➖ Remove Credentials", b"remove_credentials")],
            [Button.inline("📋 List Usernames", b"list_credentials")],
            [Button.inline("⬅️ Back", b"admin_panel")]
        ]
        
        await event.edit(
            "🔐 **Web Credentials Management**\n\nManage web dashboard login credentials:",
            buttons=buttons
        )
    
    @bot.on(events.CallbackQuery(pattern=b'admin_panel'))
    @error_handler()
    async def admin_panel_callback(event):
        """Handle admin panel back button"""
        user_id = event.sender_id
        
        if not await is_admin(user_id):
            await event.answer("Access denied")
            return
        
        buttons = create_admin_panel_page(0)
        
        await event.edit(
            "🔧 **Admin Panel**\n\nSelect an option:",
            buttons=buttons
        )
    
    @bot.on(events.CallbackQuery(pattern=b'admin_panel'))
    @error_handler()
    async def admin_panel_callback(event):
        """Handle admin panel back button"""
        user_id = event.sender_id
        
        if not await is_admin(user_id):
            await event.answer("Access denied")
            return
        
        buttons = create_admin_panel_page(0)
        
        await safe_edit_message(
            event,
            "🔧 **Admin Panel**\n\nSelect an option:",
            buttons=buttons
        )
    
    @bot.on(events.CallbackQuery(pattern=b'admin_page_'))
    @error_handler()
    async def admin_page_callback(event):
        """Handle admin panel page navigation"""
        user_id = event.sender_id
        
        if not await is_admin(user_id):
            await event.answer("Access denied")
            return
        
        # Extract page number from callback data
        data = event.data.decode('utf-8')
        page = int(data.split('_')[-1])
        
        buttons = create_admin_panel_page(page)
        
        await safe_edit_message(
            event,
            "🔧 **Admin Panel**\n\nSelect an option:",
            buttons=buttons
        )
    
    @bot.on(events.CallbackQuery(pattern=b'exit_admin'))
    @error_handler()
    async def exit_admin_callback(event):
        """Handle exit admin panel button"""
        user_id = event.sender_id
        
        if not await is_admin(user_id):
            await event.answer("Access denied")
            return
        
        # Remove user from admin sessions
        if user_id in admin_sessions:
            del admin_sessions[user_id]
        
        await safe_edit_message(
            event,
            "✅ **Exited Admin Panel**\n\nYou can now use normal bot commands.",
            buttons=None
        )
    
    @bot.on(events.CallbackQuery(pattern=b'block_user|unblock_user|lookup_user|broadcast_text|broadcast_media|add_personality|remove_personality|list_personalities|add_credentials|remove_credentials|list_credentials'))
    @error_handler()
    async def admin_action_callback(event):
        """Handle admin action buttons"""
        user_id = event.sender_id
        
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
        elif action == "broadcast_text":
            message = "📝 **Broadcast Text Message**\n\nSend me the message to broadcast to all users:"
        elif action == "broadcast_media":
            message = "📎 **Broadcast with Media**\n\nSend me a message with text and attach media (photo/video/audio/document) to broadcast:"
        elif action == "add_personality":
            message = "➕ **Add Personality - Step 1/3**\n\nSend me the personality name (2-50 characters):"
            admin_states[user_id] = "add_personality_name"
        elif action == "remove_personality":
            message = "➖ **Remove Personality**\n\nSend me the name of the personality to remove:"
        elif action == "list_personalities":
            await show_personalities(event)
            return
        elif action == "add_credentials":
            message = "➕ **Add/Update Web Credentials**\n\nSend me the credentials in format:\n\n`username|password`\n\nExample: `admin|mypassword123`\n\n⚠️ **Warning:** Passwords are hashed but choose strong passwords!"
        elif action == "remove_credentials":
            message = "➖ **Remove Web Credentials**\n\nSend me the username to remove:"
        elif action == "list_credentials":
            await show_credentials(event)
            return
        
        # Set admin state for next message (skip for multi-step actions that set their own state)
        if action != "add_personality":
            admin_states[user_id] = action
        
        if action in ["block_user", "unblock_user", "lookup_user"]:
            buttons = [[Button.inline("⬅️ Cancel", b"user_mgmt")]]
        elif action in ["broadcast_text", "broadcast_media"]:
            buttons = [[Button.inline("⬅️ Cancel", b"broadcast")]]
        elif action in ["add_personality", "remove_personality"]:
            buttons = [[Button.inline("⬅️ Cancel", b"personality_mgmt")]]
        elif action in ["add_credentials", "remove_credentials"]:
            buttons = [[Button.inline("⬅️ Cancel", b"web_credentials")]]
        
        await event.edit(message, buttons=buttons)
    
    @bot.on(events.NewMessage)
    @error_handler()
    async def admin_message_handler(event):
        """Handle admin state messages"""
        user_id = event.sender_id
        
        if not await is_admin(user_id):
            return
        
        if user_id not in admin_states:
            return
            
        state = admin_states[user_id]
        params = event.message.text.strip()
        
        # Extract action from state (can be string or dict with 'action' key)
        if isinstance(state, dict):
            action = state.get("action")
            logger.info(f"Admin handler: User {user_id}, Dict state with action='{action}', full state={state}")
        else:
            action = state
            logger.info(f"Admin handler: User {user_id}, String action='{action}'")
        
        if not action:
            logger.error(f"Admin handler: No action found for user {user_id}, state={state}")
            return
        
        if action in ["block_user", "unblock_user", "lookup_user"]:
            command_map = {
                "block_user": "block",
                "unblock_user": "unblock", 
                "lookup_user": "lookup"
            }
            
            await handle_admin_command(event, command_map[action], params)
            del admin_states[user_id]
            
        elif action == "broadcast_text":
            if not params:
                await event.respond("Please provide a message to broadcast.")
                return
            
            # Broadcast text message
            result = await broadcast_message(params, user_id)
            if result['success']:
                await event.respond(f"✅ Broadcast sent successfully!\n\n📊 Sent to: {result['success_count']} users\n❌ Failed: {result['fail_count']} users")
            else:
                await event.respond(f"❌ Broadcast failed: {result['error']}")
            
            del admin_states[user_id]
            
        elif action == "broadcast_media":
            # Handle media broadcast
            if not event.message.media:
                await event.respond("Please attach media (photo/video/audio/document) to your message.")
                return
            
            # Get media data
            media_data = {
                'type': 'unknown',
                'file_id': None
            }
            
            if event.message.photo:
                media_data['type'] = 'photo'
                media_data['file_id'] = event.message.photo.id
            elif event.message.video:
                media_data['type'] = 'video'
                media_data['file_id'] = event.message.video.id
            elif event.message.audio:
                media_data['type'] = 'audio'
                media_data['file_id'] = event.message.audio.id
            elif event.message.document:
                media_data['type'] = 'document'
                media_data['file_id'] = event.message.document.id
            
            result = await broadcast_message(params, user_id, media_data)
            if result['success']:
                await event.respond(f"✅ Media broadcast sent successfully!\n\n📊 Sent to: {result['success_count']} users\n❌ Failed: {result['fail_count']} users")
            else:
                await event.respond(f"❌ Media broadcast failed: {result['error']}")
            
            del admin_states[user_id]
            
        elif action == "add_personality_name":
            # Step 1: Store personality name and ask for description
            if not params or len(params.strip()) < 2 or len(params.strip()) > 50:
                await event.respond("❌ Personality name must be between 2 and 50 characters. Please try again:")
                return
            
            # Store the name and move to next step
            admin_states[user_id] = {"action": "add_personality_desc", "name": params.strip()}
            await event.respond(f"✅ Name: **{params.strip()}**\n\n➕ **Add Personality - Step 2/3**\n\nSend me the personality description (brief summary):")
            
        elif action == "add_personality_desc":
            # Step 2: Store description and ask for prompt
            if not params or len(params.strip()) < 5:
                await event.respond("❌ Description must be at least 5 characters. Please try again:")
                return
            
            # Store the description and move to next step
            state_data = admin_states[user_id]
            state_data["description"] = params.strip()
            state_data["action"] = "add_personality_prompt"
            admin_states[user_id] = state_data
            
            await event.respond(f"✅ Description: **{params.strip()}**\n\n➕ **Add Personality - Step 3/3**\n\nSend me the detailed personality prompt (can be long):\n\n💡 **Tip:** Make this detailed for better AI responses!")
            
        elif action == "add_personality_prompt":
            # Step 3: Create the personality with all collected data
            if not params or len(params.strip()) < 10:
                await event.respond("❌ Prompt must be at least 10 characters. Please try again:")
                return
            
            state_data = admin_states[user_id]
            name = state_data["name"]
            description = state_data["description"]
            prompt = params.strip()
            
            try:
                success, message = await add_personality(name, description, prompt, auto_add_to_users=True)
                if success:
                    await event.respond(f"✅ Personality '{name}' added successfully and auto-added to all users!\n\n📝 **Summary:**\n• **Name:** {name}\n• **Description:** {description}\n• **Prompt Length:** {len(prompt)} characters")
                else:
                    await event.respond(f"❌ {message}")
                    
            except Exception as e:
                await event.respond(f"❌ Error adding personality: {str(e)}")
            
            del admin_states[user_id]
            
        elif action == "remove_personality":
            if not params:
                await event.respond("Please provide a personality name to remove.")
                return
            
            success = await remove_personality(params)
            if success:
                await event.respond(f"✅ Personality '{params}' removed successfully!")
            else:
                await event.respond(f"❌ Failed to remove personality '{params}'. It may not exist.")
            
            del admin_states[user_id]
            
        elif action == "add_credentials":
            # Parse credentials data
            try:
                parts = params.split('|', 1)
                if len(parts) != 2:
                    await event.respond("Invalid format. Use: `username|password`")
                    return
                
                username, password = [part.strip() for part in parts]
                
                # Add/update credentials via web API
                import aiohttp
                import json
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        'http://localhost:8080/admin/credentials',
                        json={'username': username, 'password': password}
                    ) as response:
                        if response.status == 200:
                            await event.respond(f"✅ Web credentials for '{username}' updated successfully!")
                        else:
                            error_data = await response.json()
                            await event.respond(f"❌ Failed to update credentials: {error_data.get('detail', 'Unknown error')}")
                    
            except Exception as e:
                await event.respond(f"❌ Error updating credentials: {str(e)}")
            
            del admin_states[user_id]
            
        elif action == "remove_credentials":
            if not params:
                await event.respond("Please provide a username to remove.")
                return
            
            # Remove credentials via web API
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.delete(f'http://localhost:8080/admin/credentials/{params}') as response:
                    if response.status == 200:
                        await event.respond(f"✅ Web credentials for '{params}' removed successfully!")
                    else:
                        error_data = await response.json()
                        await event.respond(f"❌ Failed to remove credentials: {error_data.get('detail', 'Unknown error')}")
                
                del admin_states[user_id]