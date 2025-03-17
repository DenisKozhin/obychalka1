import asyncio
import logging
import sys
import uuid  # Для генерации уникального ID

# Генерируем уникальный ID для сессии бота
SESSION_ID = str(uuid.uuid4())[:8]

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from bot.config import BOT_TOKEN, ADMIN_IDS

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # Выводим уникальный ID сессии при старте
    logger.info(f"ЗАПУЩЕНА НОВАЯ ВЕРСИЯ БОТА С ID: {SESSION_ID}")
    
    # Инициализация бота и диспетчера
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    # Клавиатура
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Кнопка 1")],
            [KeyboardButton(text="Кнопка 2")]
        ],
        resize_keyboard=True
    )
    
    # Обработчик /start
    @dp.message(CommandStart())
    async def cmd_start(message: Message):
        await message.answer(f"Привет! Это новый бот (Сессия: {SESSION_ID})", reply_markup=kb)
    
    # Обработчик /help
    @dp.message(Command("help"))
    async def cmd_help(message: Message):
        await message.answer(f"Справка (Сессия: {SESSION_ID})")
    
    # Обработчик кнопок
    @dp.message(F.text == "Кнопка 1")
    async def button1_handler(message: Message):
        await message.answer(f"Нажата Кнопка 1 (Сессия: {SESSION_ID})")
    
    @dp.message(F.text == "Кнопка 2")
    async def button2_handler(message: Message):
        await message.answer(f"Нажата Кнопка 2 (Сессия: {SESSION_ID})")
    
    # Общий обработчик для всех сообщений
    @dp.message()
    async def echo(message: Message):
        await message.answer(f"Вы написали: {message.text} (Сессия: {SESSION_ID})")
    
    # Запуск поллинга
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)