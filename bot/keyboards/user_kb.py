from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from bot.database.models import City, Store
from sqlalchemy.ext.asyncio import AsyncSession

# Создание основной клавиатуры
def get_main_menu_kb():
    """Клавиатура главного меню пользователя"""
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

# Создание клавиатуры с городами
async def get_cities_kb(session: AsyncSession):
    """Клавиатура для выбора города"""
    from bot.database.operations_library import get_cities, create_default_cities
    
    builder = InlineKeyboardBuilder()
    
    # Получаем список городов из БД или создаем стандартные
    cities = await get_cities(session)
    if not cities:
        cities = await create_default_cities(session)
    
    # Добавляем кнопки для каждого города
    for city in cities:
        builder.add(InlineKeyboardButton(
            text=city.name,
            callback_data=f"city_{city.city_id}"
        ))
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()

# Создание клавиатуры с магазинами
async def get_stores_kb(session: AsyncSession, city_id: int):
    """Клавиатура для выбора магазина"""
    from bot.database.operations_library import get_stores_by_city, create_default_stores
    
    builder = InlineKeyboardBuilder()
    
    # Получаем список магазинов для выбранного города или создаем стандартные
    stores = await get_stores_by_city(session, city_id)
    if not stores:
        stores = await create_default_stores(session, city_id)
    
    # Добавляем кнопки для каждого магазина
    for store in stores:
        builder.add(InlineKeyboardButton(
            text=store.name,
            callback_data=f"store_{store.store_id}"
        ))
    
    # Добавляем кнопку "Назад" для возврата к выбору города
    builder.add(InlineKeyboardButton(
        text="🔙 Назад до вибору міста",
        callback_data=f"back_to_cities"
    ))
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()