from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# Основное меню пользователя
def get_main_menu_kb():
    builder = ReplyKeyboardBuilder()
    
    builder.add(
        KeyboardButton(text="📚 Бібліотека знань"),
        KeyboardButton(text="📝 Пройти тест"),
        KeyboardButton(text="🏆 Мої бали"),
        KeyboardButton(text="📢 Оголошення")
    )
    
    # Размещаем кнопки в 2 строки по 2 кнопки
    builder.adjust(2, 2)
    
    return builder.as_markup(resize_keyboard=True)