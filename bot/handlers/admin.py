import sys
import os

# Для запуска файла напрямую
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from bot.config import ADMIN_IDS
from bot.utils.logger import logger

# Создаем роутер для команд администратора
router = Router()

# Обработка команды /admin
@router.message(Command("admin"))
async def admin_command(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("У вас немає прав доступу до цієї команди.")
        return
    
    await message.answer(
        "Панель адміністратора в розробці."
    )

# Проверка при прямом запуске
if __name__ == "__main__":
    print("Модуль admin.py успешно загружен")
    print("router определен:", router is not None)
    