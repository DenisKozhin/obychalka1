import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен бота
from bot.config import BOT_TOKEN

async def main():
    # Инициализация бота и диспетчера
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    # Регистрация обработчиков
    @dp.message(CommandStart())
    async def cmd_start(message: Message):
        logger.info("Получена команда /start")
        await message.answer("Привет! Это тестовый бот.")
    
    @dp.message(Command("help"))
    async def cmd_help(message: Message):
        logger.info("Получена команда /help")
        await message.answer("Это сообщение помощи.")
    
    @dp.message(F.text == "тест")
    async def test_text(message: Message):
        logger.info("Получено текстовое сообщение 'тест'")
        await message.answer("Вы отправили 'тест'")
    
    @dp.message()
    async def echo(message: Message):
        logger.info(f"Получено сообщение: {message.text}")
        await message.answer(f"Вы сказали: {message.text}")
    
    # Запуск поллинга
    logger.info("Запуск бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        # Правильная политика цикла событий для Windows
        if asyncio.get_event_loop_policy().__class__.__name__ == 'WindowsSelectorEventLoopPolicy':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен!")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {e}", exc_info=True)