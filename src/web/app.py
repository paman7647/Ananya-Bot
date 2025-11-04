from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, UploadFile, File, Form, HTTPException, Depends, status
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from pathlib import Path
import json
from datetime import datetime
import logging
import asyncio
import secrets
import hashlib
from .bot_control import bot_controller
from src.utils import admin
from src.utils.database import db

# Authentication
security = HTTPBasic()

# Load credentials from MongoDB
async def load_credentials():
    """Load web credentials from MongoDB"""
    try:
        # Import here to avoid circular imports and ensure proper initialization
        from src.utils.database import db
        
        web_credentials_collection = db.web_credentials
        
        # Use asyncio.to_thread for synchronous MongoDB operations
        creds_doc = await asyncio.to_thread(web_credentials_collection.find_one, {})
        
        if creds_doc and 'credentials' in creds_doc:
            return creds_doc['credentials']
        else:
            # Create default credentials if none exist
            default_creds = {
                "admin": hashlib.sha256("admin123".encode()).hexdigest()
            }
            await asyncio.to_thread(
                web_credentials_collection.replace_one,
                {}, 
                {'credentials': default_creds}, 
                upsert=True
            )
            return default_creds
    except Exception as e:
        logger.error(f"Error loading credentials: {e}")
        return {"admin": hashlib.sha256("admin123".encode()).hexdigest()}

async def save_credentials(credentials: dict):
    """Save web credentials to MongoDB"""
    try:
        # Import here to avoid circular imports and ensure proper initialization
        from src.utils.database import db
        web_credentials_collection = db.web_credentials
        
        await asyncio.to_thread(
            web_credentials_collection.replace_one,
            {}, 
            {'credentials': credentials}, 
            upsert=True
        )
    except Exception as e:
        logger.error(f"Error saving credentials: {e}")

async def load_ai_config():
    """Load AI configuration from MongoDB"""
    try:
        # Import here to avoid circular imports and ensure proper initialization
        from src.utils.database import db
        
        ai_config_collection = db.ai_config
        
        # Use asyncio.to_thread for synchronous MongoDB operations
        config_doc = await asyncio.to_thread(ai_config_collection.find_one, {})
        
        if config_doc and 'config' in config_doc:
            return config_doc['config']
        else:
            # Create default configuration if none exists
            default_config = {
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
            await asyncio.to_thread(
                ai_config_collection.replace_one,
                {}, 
                {'config': default_config}, 
                upsert=True
            )
            return default_config
    except Exception as e:
        logger.error(f"Error loading AI config: {e}")
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

async def save_ai_config(config: dict):
    """Save AI configuration to MongoDB"""
    try:
        # Import here to avoid circular imports and ensure proper initialization
        from src.utils.database import db
        ai_config_collection = db.ai_config
        
        await asyncio.to_thread(
            ai_config_collection.replace_one,
            {}, 
            {'config': config}, 
            upsert=True
        )
    except Exception as e:
        logger.error(f"Error saving AI config: {e}")

# Global credentials cache
web_credentials = {}

async def initialize_credentials():
    """Initialize credentials on startup"""
    global web_credentials
    web_credentials = await load_credentials()

# Custom dependency for authentication (session or HTTP Basic)
def get_current_user(request: Request, credentials: HTTPBasicCredentials = Depends(security)):
    """Verify credentials using either session cookie or HTTP Basic auth"""
    
    # First try session-based authentication
    session_id = request.cookies.get("session_id")
    if session_id and session_id in sessions:
        return sessions[session_id]
    
    # Fall back to HTTP Basic authentication
    username = credentials.username
    password = credentials.password
    
    if username not in web_credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    if web_credentials[username] != hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    return username

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Bot Manager")

# Add startup and shutdown event handlers
@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup"""
    try:
        logger.info("Web server starting up...")
        await initialize_credentials()
        logger.info("Web server startup complete")
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown"""
    try:
        logger.info("Web server shutting down...")
        # Close database connections
        from src.utils.database import close_db_connection
        close_db_connection()
        # Clear sessions
        sessions.clear()
        logger.info("Web server shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

# Session-based authentication for web interface
from starlette.middleware.base import BaseHTTPMiddleware
import secrets

# Session store (in production, use Redis or database)
sessions = {}

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Skip auth for login page and static files
        if request.url.path in ["/login", "/static"] or request.url.path.startswith("/static/"):
            return await call_next(request)
        
        # Check for session cookie
        session_id = request.cookies.get("session_id")
        if session_id and session_id in sessions:
            request.state.user = sessions[session_id]
            return await call_next(request)
        
        # Redirect to login if no valid session
        if request.url.path.startswith("/api/"):
            # API routes use HTTP Basic auth
            return await call_next(request)
        else:
            # Web routes redirect to login
            return RedirectResponse(url="/login", status_code=302)

app.add_middleware(AuthMiddleware)

# Initialize credentials on startup
@app.on_event("startup")
async def startup_event():
    await initialize_credentials()
    global ai_config
    ai_config = await load_ai_config()

# Setup static files and templates
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Helper functions for WebSocket broadcasting
async def broadcast_to_all(message: dict):
    """Broadcast a message to all active WebSocket connections"""
    disconnected = []
    for connection in active_connections:
        try:
            await connection.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Failed to send message to WebSocket: {e}")
            disconnected.append(connection)

    # Clean up disconnected connections
    for conn in disconnected:
        if conn in active_connections:
            active_connections.remove(conn)

def get_recent_logs(limit: int = 50):
    """Get recent logs from the logging system"""
    # This is a simple implementation - in a real app you'd collect logs from a queue or file
    return [
        {"timestamp": datetime.now().isoformat(), "level": "info", "message": "WebSocket connection established"},
        {"timestamp": datetime.now().isoformat(), "level": "info", "message": "Dashboard loaded successfully"}
    ]

# Store active WebSocket connections and stats
active_connections = []
bot_stats = {
    "start_time": datetime.now().isoformat(),
    "total_messages": 0,
    "active_users": 0,
    "total_users": 0,
    "errors": 0,
    "status": "running",
    "uptime": "0:00:00"
}

# AI configuration and stats
ai_config = {}

ai_stats = {
    "totalRequests": 0,
    "successfulRequests": 0,
    "totalResponseTime": 0,
    "activeUsers": 0
}

# WebSocket Manager
# Routes
@app.get("/")
async def root(request: Request):
    """Render main dashboard"""
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request}
    )

@app.get("/login")
async def login_page(request: Request):
    """Render login page"""
    return templates.TemplateResponse(
        "login.html",
        {"request": request}
    )

@app.post("/login")
async def login(request: Request):
    """Handle login"""
    try:
        # Try to get JSON data first (from JavaScript)
        try:
            json_data = await request.json()
            username = json_data.get("username")
            password = json_data.get("password")
        except (json.JSONDecodeError, ValueError, AttributeError) as e:
            # Fall back to form data
            logger.debug(f"Failed to parse JSON login data, trying form data: {e}")
            form_data = await request.form()
            username = form_data.get("username")
            password = form_data.get("password")
        
        if not username or not password:
            return {"success": False, "detail": "Username and password are required"}
        
        if username in web_credentials:
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            if web_credentials[username] == hashed_password:
                # Create session
                session_id = secrets.token_urlsafe(32)
                sessions[session_id] = username
                
                response = JSONResponse({"success": True, "message": "Login successful"})
                response.set_cookie(
                    key="session_id", 
                    value=session_id, 
                    httponly=True, 
                    max_age=86400,  # 24 hours
                    secure=False,  # Set to True in production with HTTPS
                    samesite="lax"
                )
                return response
        
        return {"success": False, "detail": "Invalid username or password"}
    
    except Exception as e:
        logger.error(f"Login error: {e}")
        return {"success": False, "detail": "Login failed due to server error"}

@app.post("/logout")
async def logout(request: Request):
    """Handle logout"""
    # Clear session if it exists
    session_id = request.cookies.get("session_id")
    if session_id and session_id in sessions:
        del sessions[session_id]
    
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session_id")
    return response

# Protected routes
@app.get("/stats")
async def get_stats(username: str = Depends(get_current_user)):
    """Get current bot statistics"""
    return bot_stats

# Admin API Routes
@app.get("/admin/stats")
async def get_admin_stats(username: str = Depends(get_current_user)):
    """Get detailed admin statistics"""
    try:
        stats = await admin.get_detailed_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting admin stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get admin stats")

@app.get("/admin/user/{user_input}")
async def get_user_details(user_input: str, username: str = Depends(get_current_user)):
    """Get user details by ID or username"""
    try:
        user_id = await admin.lookup_user_by_input(user_input)
        if not user_id:
            return None
        
        user_details = await admin.get_user_details(user_id)
        return user_details
    except Exception as e:
        logger.error(f"Error getting user details: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user details")

@app.post("/admin/block/{user_input}")
async def block_user_endpoint(user_input: str, username: str = Depends(get_current_user)):
    """Block a user"""
    try:
        user_id = await admin.lookup_user_by_input(user_input)
        if not user_id:
            raise HTTPException(status_code=404, detail="User not found")
        
        success = await admin.block_user(user_id)
        return {"success": success}
    except Exception as e:
        logger.error(f"Error blocking user: {e}")
        raise HTTPException(status_code=500, detail="Failed to block user")

@app.post("/admin/unblock/{user_input}")
async def unblock_user_endpoint(user_input: str, username: str = Depends(get_current_user)):
    """Unblock a user"""
    try:
        user_id = await admin.lookup_user_by_input(user_input)
        if not user_id:
            raise HTTPException(status_code=404, detail="User not found")
        
        success = await admin.unblock_user(user_id)
        return {"success": success}
    except Exception as e:
        logger.error(f"Error unblocking user: {e}")
        raise HTTPException(status_code=500, detail="Failed to unblock user")

@app.post("/admin/broadcast")
async def broadcast_message_endpoint(
    message: str = Form(...),
    file: UploadFile = File(None),
    username: str = Depends(get_current_user)
):
    """Send broadcast message to all users"""
    try:
        # Get admin user_id from database (web admins use their admin ID)
        # For now use ADMIN_USER_ID from config until we map web users to telegram IDs
        from src.config import ADMIN_USER_ID
        sender_id = ADMIN_USER_ID  # Use configured admin ID instead of 0
        logger.info(f"Broadcast initiated by web user '{username}', using sender_id: {sender_id}")
        
        media_data = None
        file_data = None
        
        if file:
            # Read file content
            file_content = await file.read()
            file_data = {
                'name': file.filename,
                'content': file_content,
                'type': file.content_type
            }
        
        result = await admin.broadcast_message(message, sender_id, media_data, file_data)
        return result
    except Exception as e:
        logger.error(f"Error sending broadcast: {e}")
        raise HTTPException(status_code=500, detail="Failed to send broadcast")

@app.post("/admin/personality")
async def add_personality_endpoint(request: Request, username: str = Depends(get_current_user)):
    """Add a new personality"""
    try:
        data = await request.json()
        name = data.get('name')
        description = data.get('description')
        prompt = data.get('prompt')
        auto_add_to_users = data.get('auto_add_to_users', True)
        
        if not name or not description:
            raise HTTPException(status_code=400, detail="Name and description are required")
        
        # Prompt is optional - will be auto-generated if not provided
        success, message = await admin.add_personality(name, description, prompt, auto_add_to_users)
        
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        return {"success": True, "message": message}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding personality: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/admin/personality/{name}")
async def remove_personality_endpoint(name: str, username: str = Depends(get_current_user)):
    """Remove a personality"""
    try:
        success = await admin.remove_personality(name)
        return {"success": success}
    except Exception as e:
        logger.error(f"Error removing personality: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove personality")

# Web credential management
@app.get("/admin/credentials")
async def get_credentials(username: str = Depends(get_current_user)):
    """Get list of web credentials (usernames only)"""
    return {"usernames": list(web_credentials.keys())}

@app.post("/admin/credentials")
async def add_credential(request: Request, username: str = Depends(get_current_user)):
    """Add or update web credentials"""
    try:
        data = await request.json()
        new_username = data.get('username')
        password = data.get('password')
        
        if not new_username or not password:
            raise HTTPException(status_code=400, detail="Username and password required")
        
        global web_credentials
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        web_credentials[new_username] = hashed_password
        await save_credentials(web_credentials)
        
        return {"success": True, "message": f"Credentials for '{new_username}' updated"}
    except Exception as e:
        logger.error(f"Error updating credentials: {e}")
        raise HTTPException(status_code=500, detail="Failed to update credentials")

@app.delete("/admin/credentials/{username}")
async def delete_credential(username: str, current_user: str = Depends(get_current_user)):
    """Delete web credentials for a username"""
    try:
        global web_credentials
        if username not in web_credentials:
            raise HTTPException(status_code=404, detail="Username not found")
        
        del web_credentials[username]
        await save_credentials(web_credentials)
        
        return {"success": True, "message": f"Credentials for '{username}' deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting credentials: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete credentials")

@app.get("/admin/users")
async def get_users_list(username: str = Depends(get_current_user)):
    """Get list of all users"""
    try:
        users = await admin.get_all_users()
        return {"users": users}
    except Exception as e:
        logger.error(f"Error getting users list: {e}")
        raise HTTPException(status_code=500, detail="Failed to get users list")

@app.get("/admin/personalities")
async def get_personalities_list(username: str = Depends(get_current_user)):
    """Get list of all personalities"""
    try:
        personalities = await admin.get_all_personalities()
        return {"personalities": personalities}
    except Exception as e:
        logger.error(f"Error getting personalities list: {e}")
        raise HTTPException(status_code=500, detail="Failed to get personalities list")

@app.put("/admin/personality/{name}")
async def update_personality_endpoint(name: str, request: Request, username: str = Depends(get_current_user)):
    """Update a personality"""
    try:
        data = await request.json()
        description = data.get('description')
        prompt = data.get('prompt')
        auto_add_to_users = data.get('auto_add_to_users', False)

        if not description:
            raise HTTPException(status_code=400, detail="Description is required")

        # Prompt is optional - if not provided, existing prompt will be kept
        success = await admin.update_personality(name, description, prompt, auto_add_to_users)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Personality '{name}' not found or no changes made")
        
        return {"success": True, "message": f"Personality '{name}' updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating personality: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/user/{user_input}/personality")
async def assign_personality_to_user(user_input: str, request: Request, username: str = Depends(get_current_user)):
    """Assign personality to a user"""
    try:
        data = await request.json()
        personality_name = data.get('personality_name')

        if not personality_name:
            raise HTTPException(status_code=400, detail="Personality name required")

        user_id = await admin.lookup_user_by_input(user_input)
        if not user_id:
            raise HTTPException(status_code=404, detail="User not found")

        success = await admin.assign_personality_to_user(user_id, personality_name)
        return {"success": success}
    except Exception as e:
        logger.error(f"Error assigning personality: {e}")
        raise HTTPException(status_code=500, detail="Failed to assign personality")

@app.delete("/admin/user/{user_input}/personality")
async def remove_personality_from_user(user_input: str, username: str = Depends(get_current_user)):
    """Remove personality from a user"""
    try:
        user_id = await admin.lookup_user_by_input(user_input)
        if not user_id:
            raise HTTPException(status_code=404, detail="User not found")

        success = await admin.remove_personality_from_user(user_id)
        return {"success": success}
    except Exception as e:
        logger.error(f"Error removing personality: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove personality")

# AI Configuration endpoints
@app.get("/admin/ai-config")
async def get_ai_config(username: str = Depends(get_current_user)):
    """Get current AI configuration"""
    return ai_config

@app.post("/admin/ai-config")
async def update_ai_config(request: Request, username: str = Depends(get_current_user)):
    """Update AI configuration"""
    try:
        data = await request.json()
        global ai_config
        ai_config.update(data)
        
        # Save to database
        await save_ai_config(ai_config)

        # Broadcast to all WebSocket clients
        await broadcast_to_all({
            "type": "config_updated",
            "config": ai_config
        })

        return {"success": True, "config": ai_config}
    except Exception as e:
        logger.error(f"Error updating AI config: {e}")
        raise HTTPException(status_code=500, detail="Failed to update AI config")

# Bot control endpoints (for direct API calls)
@app.post("/bot/start")
async def start_bot_endpoint(username: str = Depends(get_current_user)):
    """Start the bot"""
    try:
        success = await bot_controller.start()
        if success:
            bot_stats["status"] = "running"
            await broadcast_to_all({"type": "status", "status": "running"})
        return {"success": success}
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise HTTPException(status_code=500, detail="Failed to start bot")

@app.post("/bot/stop")
async def stop_bot_endpoint(username: str = Depends(get_current_user)):
    """Stop the bot"""
    try:
        success = await bot_controller.stop()
        if success:
            bot_stats["status"] = "stopped"
            await broadcast_to_all({"type": "status", "status": "stopped"})
        return {"success": success}
    except Exception as e:
        logger.error(f"Error stopping bot: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop bot")

@app.post("/bot/restart")
async def restart_bot_endpoint(username: str = Depends(get_current_user)):
    """Restart the bot"""
    try:
        success = await bot_controller.restart()
        if success:
            bot_stats["status"] = "running"
            await broadcast_to_all({"type": "status", "status": "running"})
        return {"success": success}
    except Exception as e:
        logger.error(f"Error restarting bot: {e}")
        raise HTTPException(status_code=500, detail="Failed to restart bot")

@app.get("/bot/status")
async def get_bot_status(username: str = Depends(get_current_user)):
    """Get bot status"""
    status_info = bot_controller.get_status()
    bot_stats["status"] = status_info["status"]
    return status_info

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates with improved error handling"""
    await websocket.accept()
    active_connections.append(websocket)
    
    logger.info(f"WebSocket connection established. Active connections: {len(active_connections)}")

    try:
        # Send initial data in format expected by frontend
        await websocket.send_text(json.dumps({
            "type": "stats",
            "total_users": bot_stats.get("total_users", 0),
            "active_users": len(active_connections),
            "total_messages": bot_stats.get("total_messages", 0),
            "uptime": bot_stats.get("uptime", "0:00:00")
        }))

        # Send initial status
        actual_status = bot_controller.get_status()["status"]
        await websocket.send_text(json.dumps({
            "type": "status",
            "status": actual_status
        }))

        while True:
            # Add timeout to receive to prevent hanging connections
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                await websocket.send_text(json.dumps({"type": "ping"}))
                continue
            except (WebSocketDisconnect, ConnectionError, RuntimeError) as e:
                logger.info(f"WebSocket receive error: {e}")
                break
            try:
                command = json.loads(data)
                action = command.get("action")

                if action == "start":
                    logger.info("Bot start requested via WebSocket")
                    current_status = bot_controller.get_status()["status"]
                    
                    if current_status == "running":
                        await websocket.send_text(json.dumps({
                            "type": "status",
                            "status": "running",
                            "message": "Bot is already running"
                        }))
                    else:
                        await websocket.send_text(json.dumps({
                            "type": "status",
                            "status": "starting"
                        }))

                        success = await bot_controller.start()
                        new_status = bot_controller.get_status()["status"]
                        await websocket.send_text(json.dumps({
                            "type": "status",
                            "status": new_status
                        }))

                elif action == "restart":
                    logger.info("Bot restart requested via WebSocket")
                    await websocket.send_text(json.dumps({
                        "type": "status",
                        "status": "restarting"
                    }))

                    success = await bot_controller.restart()
                    new_status = bot_controller.get_status()["status"]
                    await websocket.send_text(json.dumps({
                        "type": "status",
                        "status": new_status
                    }))

                elif action == "stop":
                    logger.info("Bot stop requested via WebSocket")
                    current_status = bot_controller.get_status()["status"]
                    
                    if current_status == "stopped":
                        await websocket.send_text(json.dumps({
                            "type": "status",
                            "status": "stopped",
                            "message": "Bot is already stopped"
                        }))
                    else:
                        await websocket.send_text(json.dumps({
                            "type": "status",
                            "status": "stopping"
                        }))

                        success = await bot_controller.stop()
                        new_status = bot_controller.get_status()["status"]
                        await websocket.send_text(json.dumps({
                            "type": "status",
                            "status": new_status
                        }))

                elif action == "update_config":
                    logger.info("AI configuration update requested")
                    new_config = command.get("config", {})
                    ai_config.update(new_config)

                    # Broadcast config update
                    await broadcast_to_all({
                        "type": "config_updated",
                        "config": ai_config
                    })

                elif action == "get_logs":
                    # Send recent logs
                    recent_logs = get_recent_logs()
                    await websocket.send_text(json.dumps({
                        "type": "logs",
                        "logs": recent_logs
                    }))

            except json.JSONDecodeError:
                logger.error("Invalid WebSocket message format")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid message format"
                }))

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected normally")
    except ConnectionError as e:
        logger.warning(f"WebSocket connection error: {e}")
    except Exception as e:
        logger.error(f"WebSocket unexpected error: {e}")
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)
        logger.info(f"WebSocket connection closed. Active connections: {len(active_connections)}")

async def update_stats():
    """Background task to update statistics"""
    while True:
        try:
            # Update example statistics (replace with actual bot stats)
            bot_stats["total_messages"] += 1
            bot_stats["active_users"] = len(active_connections)
            
            # Broadcast updates
            for connection in active_connections:
                try:
                    await connection.send_text(json.dumps({
                        "type": "stats",
                        "data": bot_stats
                    }))
                except (ConnectionError, RuntimeError, json.JSONDecodeError) as e:
                    logger.error(f"Failed to send stats update: {e}")
                    
        except Exception as e:
            logger.error(f"Error updating stats: {e}")
            
        await asyncio.sleep(5)  # Update every 5 seconds

@app.on_event("startup")
async def startup_event():
    """Start background tasks on app startup"""
    asyncio.create_task(update_stats())

async def update_stats():
    """Background task to update statistics and broadcast to all clients"""
    while True:
        try:
            # Update uptime
            start_time = datetime.fromisoformat(bot_stats["start_time"])
            uptime = datetime.now() - start_time
            bot_stats["uptime"] = f"{uptime.days}d {uptime.seconds//3600}h {(uptime.seconds//60)%60}m"

            # Get real stats from admin module
            admin_stats = await admin.get_detailed_stats()
            bot_stats["total_users"] = admin_stats.get("total_users", 0)
            bot_stats["active_users"] = len(active_connections)
            bot_stats["total_messages"] = admin_stats.get("total_messages", 0)

            # Broadcast updated stats to all clients
            stats_message = {
                "type": "stats",
                "total_users": bot_stats["total_users"],
                "active_users": bot_stats["active_users"],
                "total_messages": bot_stats["total_messages"],
                "uptime": bot_stats["uptime"]
            }
            await broadcast_to_all(stats_message)

            # Send periodic log updates (simulated)
            log_message = {
                "type": "log",
                "level": "info",
                "message": f"Stats updated: {bot_stats['active_users']} active users, {bot_stats['total_messages']} messages"
            }
            await broadcast_to_all(log_message)

        except Exception as e:
            logger.error(f"Error updating stats: {e}")

        await asyncio.sleep(10)  # Update every 10 seconds
# Health Check Endpoints
@app.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with system status"""
    try:
        from src.utils.database import check_db_connection
        import psutil
        import os
        
        # Check database connection
        db_healthy = check_db_connection()
        
        # Check bot controller status
        bot_status = "unknown"
        try:
            if bot_controller.process and bot_controller.process.poll() is None:
                bot_status = "running"
            else:
                bot_status = "stopped"
        except (AttributeError, psutil.NoSuchProcess, TypeError) as e:
            logger.debug(f"Error checking bot status: {e}")
            bot_status = "error"
        
        # System resource usage
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        
        return {
            "status": "healthy" if db_healthy else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "database": "healthy" if db_healthy else "unhealthy",
                "bot": bot_status
            },
            "system": {
                "memory_usage_percent": memory.percent,
                "disk_usage_percent": disk.percent,
                "cpu_count": os.cpu_count()
            }
        }
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }

@app.get("/api/status")
async def api_status():
    """API status endpoint for external monitoring"""
    try:
        from src.utils.database import check_db_connection
        
        return {
            "status": "ok",
            "database": "connected" if check_db_connection() else "disconnected",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

