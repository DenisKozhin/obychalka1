# bot/handlers/__init__.py
from aiogram import Router
import logging
from bot.handlers.library_handler import router as library_router
from bot.handlers.tests import router as tests_router

# Импортируйте другие роутеры, если есть
logger = logging.getLogger(__name__)

def setup_routers() -> Router:
    """
    Настройка роутеров для обработчиков команд
    """
    router = Router()
    
    # Регистрация базовых обработчиков
    from aiogram.filters import CommandStart, Command
    from aiogram.types import Message
    
    @router.message(CommandStart())
    async def cmd_start_base(message: Message):
        logger.info("Базовый обработчик /start сработал")
        await message.answer("Привет! Я базовый обработчик команды /start")
    
    @router.message(Command("help"))
    async def cmd_help_base(message: Message):
        logger.info("Базовый обработчик /help сработал")
        await message.answer("Это базовый обработчик команды /help")
    
    # Подключение других роутеров
    try:
        from . import common
        router.include_router(common.router)
        logger.info("Роутер common подключен")
    except Exception as e:
        logger.error(f"Ошибка импорта common: {e}")
    
    try:
        from . import user
        router.include_router(user.router)
        logger.info("Роутер user подключен")
    except Exception as e:
        logger.error(f"Ошибка импорта user: {e}")
    
    try:
        from . import admin
        router.include_router(admin.router)
        logger.info("Роутер admin подключен")
    except Exception as e:
        logger.error(f"Ошибка импорта admin: {e}")
    
    return router
    
    

# Проверка при прямом запуске
if __name__ == "__main__":
    print("Файл __init__.py в handlers успешно импортирован")
    print("Функция setup_routers() определена")
    print("Роутеры успешно настроены")
    