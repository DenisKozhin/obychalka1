import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.middleware import FSMContextMiddleware
from aiogram.types import Message
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

async def cmd_start(message: Message, session: AsyncSessionLocal):
    await message.answer("Привет! Бот работает и база данных подключена!")
    await message.answer("Чтобы протестировать регистрацию, напиши /register")

async def cmd_register(message: Message, session: AsyncSessionLocal):
    from sqlalchemy import select
    from bot.database.models import User
    
    # Проверяем, есть ли пользователь в базе
    user_id = message.from_user.id
    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    
    if user:
        await message.answer(f"Вы уже зарегистрированы как {user.first_name} {user.last_name}")
    else:
        await message.answer("Начинаем регистрацию! Введите ваше имя и фамилию:")
        # В полноценной регистрации здесь бы использовалась FSM

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
    
    # Регистрация middleware
    dp.update.middleware(DbSessionMiddleware())
    dp.update.middleware(FSMContextMiddleware(storage, events_isolation=False))
    
    # Регистрация хендлеров напрямую
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(cmd_register, Command("register"))
    
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
        