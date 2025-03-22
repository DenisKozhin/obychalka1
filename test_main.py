# bot/__main__.py
"""
Main entry point for the telegram bot with properly registered routers and middlewares.
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

# Import middleware
from bot.middlewares.database import DatabaseMiddleware

# Import all handlers
from bot.handlers.library_handler import router as library_router
from bot.handlers.tests import router as tests_router
# Import any other routers you have

# Import config
from bot.config import BOT_TOKEN

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define bot commands
async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="help", description="Get help"),
        BotCommand(command="menu", description="Show main menu")
    ]
    await bot.set_my_commands(commands)

async def main():
    # Initialize bot and dispatcher
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Register the database middleware
    dp.update.middleware(DatabaseMiddleware())
    
    # Register all routers
    dp.include_router(library_router)
    dp.include_router(tests_router)
    # Register any other routers you have
    
    # Set bot commands
    await set_commands(bot)
    
    # Start polling
    try:
        logger.info("Starting bot...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
        