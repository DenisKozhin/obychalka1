import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.middleware import FSMContextMiddleware
from bot.config import BOT_TOKEN
from bot.database.database import AsyncSessionLocal, Base, async_engine

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Middleware для работы с базой данных
class DbSessionMiddleware:
    async def __call__(self, handler, event, data):
        async with AsyncSessionLocal() as session:
            data["session"] = session
            return await handler(event, data)

async def main():
    # Создаем таблицы в базе данных, если их нет
    try:
        logger.info("Создание таблиц базы данных...")
        async with async_engine.begin() as conn:
            # Создаем новые таблицы
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Таблицы успешно созданы")
    except Exception as e:
        logger.error(f"Ошибка при создании таблиц: {e}")
        raise

    # Инициализация бота и диспетчера
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрация middleware с исправленным параметром
    dp.update.middleware(DbSessionMiddleware())
    dp.update.middleware(FSMContextMiddleware(storage, events_isolation=False))
    
    # Регистрация обработчиков
    try:
        from bot.handlers.user import router as user_router
        dp.include_router(user_router)
        logger.info("Обработчики зарегистрированы")
    except Exception as e:
        logger.error(f"Ошибка при регистрации обработчиков: {e}")
        raise
    
    # Запуск бота
    logger.info("Бот запускается...")
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен!")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {e}", exc_info=True)
        