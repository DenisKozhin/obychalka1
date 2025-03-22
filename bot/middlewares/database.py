# bot/middlewares/database.py
"""
Database middleware for providing database sessions to all handlers.
"""

from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from bot.database.database import AsyncSessionLocal



class DatabaseMiddleware(BaseMiddleware):
    """
    Middleware for injecting database session into handler data.
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        This method is called for each update.
        Creates a new database session and adds it to the data which is passed to handlers.
        After the handler is executed, the session is closed.
        """
        async with AsyncSessionLocal() as session:
            # Add the session to the data
            data["session"] = session
            
            # Save the session in the bot instance for easy access in callbacks
            if "bot" in data:
                data["bot"]["db_session"] = session
            
            # Call the handler with the updated data
            return await handler(event, data)
        
