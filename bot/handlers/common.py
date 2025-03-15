import sys
import os

# Для запуска файла напрямую
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command, CommandStart
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.user_kb import get_main_menu_kb
from bot.config import ADMIN_IDS
from bot.database.models import User

# Создаем роутер для общих команд
router = Router()

# Обработка команды /start передает управление в user.py
# Этот обработчик больше не нужен, так как мы перенесли логику в user.py
# Оставляем только обработчик help

# Обработка команды /help
@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "🤖 <b>Допомога по боту:</b>\n\n"
        "Цей бот допоможе вам:\n"
        "📚 Вивчати інформацію про товари\n"
        "📝 Проходити тести для перевірки знань\n"
        "🏆 Відстежувати свій рейтинг та бали\n"
        "📢 Отримувати оголошення від адміністрації\n\n"
        "<b>Доступні команди:</b>\n"
        "/start - Запустити бота / повернутися в головне меню\n"
        "/help - Показати цю довідку\n"
    )
    
    await message.answer(help_text, parse_mode="HTML")

# Проверка при прямом запуске
if __name__ == "__main__":
    print("Модуль common.py успешно загружен")
    print("router определен:", router is not None)
    