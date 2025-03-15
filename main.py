import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.middleware import FSMContextMiddleware
from aiogram.types import Message
from aiogram.dispatcher.middlewares.base import BaseMiddleware

from bot.config import BOT_TOKEN
from bot.utils.logger import logger
from bot.database.database import Base, async_engine, AsyncSessionLocal
from bot.database.models import User, City, Store, Category, Article, Test  # Импортируем все модели

# Middleware для работы с базой данных
class DbSessionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        async with AsyncSessionLocal() as session:
            data["session"] = session
            return await handler(event, data)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Регистрация middleware
dp.update.middleware(DbSessionMiddleware())
# Добавляем параметр events_isolation для FSMContextMiddleware
dp.update.middleware(FSMContextMiddleware(storage, events_isolation=False))

async def main():
    logger.info("Бот запускается...")
    
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
    
    # Регистрация обработчиков
    try:
        from bot.handlers import setup_routers
        dp.include_router(setup_routers())
        logger.info("Обработчики зарегистрированы")
    except Exception as e:
        logger.error(f"Ошибка при регистрации обработчиков: {e}")
        # Регистрируем базовый обработчик
        @dp.message()
        async def echo_handler(message: Message):
            await message.answer("Я получил ваше сообщение!")
    
    # Запуск бота в режиме long polling
    logger.info("Запуск бота...")
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        print("Запуск бота...")
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен!")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {e}", exc_info=True)
        print(f"Ошибка: {e}")