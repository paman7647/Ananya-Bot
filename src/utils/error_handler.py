import functools
import logging
import traceback
import inspect
from datetime import datetime
from typing import Dict, Any, Callable, Optional

logger = logging.getLogger(__name__)

class ErrorStore:
    """Store for tracking and managing errors"""
    def __init__(self):
        self._errors = {}
        self._error_count = 0
        
    def add_error(self, error_details: Dict[str, Any]) -> str:
        """Add an error to the store"""
        error_id = f"ERR_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._error_count}"
        self._error_count += 1
        self._errors[error_id] = error_details
        return error_id
        
    def get_error(self, error_id: str) -> Optional[Dict[str, Any]]:
        """Get error details by ID"""
        return self._errors.get(error_id)
        
    def get_recent_errors(self, limit: int = 10) -> list[Dict[str, Any]]:
        """Get recent errors"""
        sorted_errors = sorted(
            self._errors.items(),
            key=lambda x: x[1]['timestamp'],
            reverse=True
        )
        return [error for _, error in sorted_errors[:limit]]

# Global error store instance
error_store = ErrorStore()

def error_handler(notify_admin: bool = True):
    """Decorator for handling errors in async functions"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = datetime.now()
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Get error details
                exc_type = type(e).__name__
                exc_msg = str(e)
                stack_trace = traceback.format_exc()
                
                try:
                    # Get source context
                    frame = inspect.trace()[-1]
                    filename = frame[1]
                    line_number = frame[2]
                    function_name = frame[3]
                    context_lines = inspect.getsourcelines(frame[0])[0]
                    error_line = context_lines[frame[2] - frame[4] - 1].strip()
                except Exception:
                    filename = "Unknown"
                    line_number = 0
                    function_name = func.__name__
                    error_line = "Context unavailable"
                
                # Calculate execution time
                execution_time = (datetime.now() - start_time).total_seconds()
                
                # Create error details
                error_details = {
                    'timestamp': datetime.now().isoformat(),
                    'function': function_name,
                    'file': filename,
                    'line_number': line_number,
                    'error_line': error_line,
                    'error_type': exc_type,
                    'error_message': exc_msg,
                    'stack_trace': stack_trace,
                    'execution_time': f"{execution_time:.3f}s"
                }
                
                # Store error
                error_id = error_store.add_error(error_details)
                
                # Log error
                logger.error(
                    f"Error ID: {error_id}\n"
                    f"Function: {function_name}\n"
                    f"Location: {filename}:{line_number}\n"
                    f"Error: {exc_type}: {exc_msg}\n"
                    f"Context: {error_line}\n"
                    f"Stack Trace:\n{stack_trace}"
                )
                
                # Handle user notification if event is present
                event = next((arg for arg in args if hasattr(arg, 'respond')), None)
                if event:
                    try:
                        from src.config import ADMIN_USER_ID
                        
                        # Send user-friendly message
                        await event.respond(
                            "❌ **Error**\n\n"
                            "An error occurred while processing your request.\n"
                            "An administrator has been notified.",
                            parse_mode='markdown'
                        )
                        
                        if notify_admin:
                            # Format admin notification
                            admin_msg = (
                                f"🚨 **Error Alert** `{error_id}`\n\n"
                                f"**Function:** `{function_name}`\n"
                                f"**File:** `{filename}`\n"
                                f"**Line:** {line_number}\n"
                                f"**Error Type:** `{exc_type}`\n"
                                f"**Message:** `{exc_msg}`\n\n"
                                f"**Context:**\n```python\n{error_line}\n```\n\n"
                                f"**Stack Trace:**\n```python\n{stack_trace[:800]}...\n```"
                            )
                            
                            try:
                                # Get bot instance from the first argument if it's a client
                                bot = args[0] if args and hasattr(args[0], 'send_message') else None
                                
                                # Send to admin if current user isn't admin
                                if hasattr(event, 'sender_id'):
                                    from src.utils.admin import is_admin
                                    if await is_admin(event.sender_id):
                                        await event.respond(admin_msg, parse_mode='markdown')
                                    elif bot:
                                        await bot.send_message(
                                            ADMIN_USER_ID,
                                            admin_msg,
                                            parse_mode='markdown'
                                        )
                            except Exception as notify_error:
                                logger.error(f"Failed to notify admin: {notify_error}")
                                
                    except Exception as response_error:
                        logger.error(f"Failed to send error response: {response_error}")
                
                # Re-raise the original exception
                raise
                
        return wrapper
    return decorator