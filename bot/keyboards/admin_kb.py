from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# Основное меню администратора
def get_admin_menu_kb():
    builder = ReplyKeyboardBuilder()
    
    builder.add(
        KeyboardButton(text="📄 Статті"),
        KeyboardButton(text="✅ Тести"),
        KeyboardButton(text="📢 Розсилка"),
        KeyboardButton(text="🏙 Управління містами"),
        KeyboardButton(text="🏪 Управління магазинами"),
        KeyboardButton(text="🗑 Видалення даних"),
        KeyboardButton(text="📊 Статистика")
    )
    
    # Размещаем кнопки в 2 строки по 2 кнопки
    builder.adjust(2, 2, 2, 1)
    
    return builder.as_markup(resize_keyboard=True)


# Клавиатура для управления городами
def get_city_management_kb():
    builder = InlineKeyboardBuilder()
    
    builder.add(
        InlineKeyboardButton(text="🏙 Додати місто", callback_data="add_city"),
        InlineKeyboardButton(text="✏️ Редагувати місто", callback_data="edit_city"),
        InlineKeyboardButton(text="🗑 Видалити місто", callback_data="delete_city"),
        InlineKeyboardButton(text="📋 Список міст", callback_data="list_cities"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin_menu")
    )
    
    # Размещаем кнопки в одну колонку
    builder.adjust(1)
    
    return builder.as_markup()


# Клавиатура для управления магазинами
def get_store_management_kb():
    builder = InlineKeyboardBuilder()
    
    builder.add(
        InlineKeyboardButton(text="🏪 Додати магазин", callback_data="add_store"),
        InlineKeyboardButton(text="✏️ Редагувати магазин", callback_data="edit_store"),
        InlineKeyboardButton(text="🗑 Видалити магазин", callback_data="delete_store"),
        InlineKeyboardButton(text="📋 Список магазинів", callback_data="list_stores"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin_menu")
    )
    
    # Размещаем кнопки в одну колонку
    builder.adjust(1)
    
    return builder.as_markup()


# Клавиатура для управления статьями
def get_article_management_kb():
    builder = InlineKeyboardBuilder()
    
    builder.add(
        InlineKeyboardButton(text="📝 Додати статтю", callback_data="add_article"),
        InlineKeyboardButton(text="✏️ Редагувати статтю", callback_data="edit_article"),
        InlineKeyboardButton(text="🗑 Видалити статтю", callback_data="delete_article"),
        InlineKeyboardButton(text="📋 Список статей", callback_data="list_articles"),
        InlineKeyboardButton(text="📤 Відправити статтю", callback_data="send_article"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin_menu")
    )
    
    # Размещаем кнопки в одну колонку
    builder.adjust(1)
    
    return builder.as_markup()


# Клавиатура для управления тестами
def get_test_management_kb():
    builder = InlineKeyboardBuilder()
    
    builder.add(
        InlineKeyboardButton(text="📝 Додати тест", callback_data="add_test"),
        InlineKeyboardButton(text="✏️ Редагувати тест", callback_data="edit_test"),
        InlineKeyboardButton(text="🗑 Видалити тест", callback_data="delete_test"),
        InlineKeyboardButton(text="📋 Список тестів", callback_data="list_tests"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin_menu")
    )
    
    # Размещаем кнопки в одну колонку
    builder.adjust(1)
    
    return builder.as_markup()


# Клавиатура для удаления данных
def get_delete_data_kb():
    builder = InlineKeyboardBuilder()
    
    builder.add(
        InlineKeyboardButton(text="🧹 Очистити старі спроби тестів", callback_data="clear_old_test_attempts"),
        InlineKeyboardButton(text="🧹 Очистити старі оголошення", callback_data="clear_old_announcements"),
        InlineKeyboardButton(text="🧹 Очистити неактивних користувачів", callback_data="clear_inactive_users"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin_menu")
    )
    
    # Размещаем кнопки в одну колонку
    builder.adjust(1)
    
    return builder.as_markup()


# Клавиатура для подтверждения удаления
def get_confirm_deletion_kb(entity_type, entity_id):
    builder = InlineKeyboardBuilder()
    
    builder.add(
        InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"confirm_delete_{entity_type}_{entity_id}"),
        InlineKeyboardButton(text="❌ Скасувати", callback_data=f"cancel_delete_{entity_type}")
    )
    
    # Размещаем кнопки в одну строку
    builder.adjust(2)
    
    return builder.as_markup()


# Клавиатура для просмотра статистики
def get_statistics_kb():
    builder = InlineKeyboardBuilder()
    
    builder.add(
        InlineKeyboardButton(text="📊 Статистика тестів", callback_data="stats_tests"),
        InlineKeyboardButton(text="📊 Статистика користувачів", callback_data="stats_users"),
        InlineKeyboardButton(text="📊 Статистика активності", callback_data="stats_activity"),
        InlineKeyboardButton(text="📊 Журнал дій адміністраторів", callback_data="admin_logs"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin_menu")
    )
    
    # Размещаем кнопки в одну колонку
    builder.adjust(1)
    
    return builder.as_markup()


# Функция для создания клавиатуры списка городов
def build_cities_kb(cities, callback_prefix="city_", include_back=True):
    builder = InlineKeyboardBuilder()
    
    for city in cities:
        builder.add(InlineKeyboardButton(
            text=city.name,
            callback_data=f"{callback_prefix}{city.city_id}"
        ))
    
    if include_back:
        builder.add(InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="back_to_admin_menu"
        ))
    
    # Размещаем кнопки в одну колонку
    builder.adjust(1)
    
    return builder.as_markup()


# Функция для создания клавиатуры списка магазинов
def build_stores_kb(stores, callback_prefix="store_", include_back=True, back_callback="back_to_admin_menu"):
    builder = InlineKeyboardBuilder()
    
    for store in stores:
        builder.add(InlineKeyboardButton(
            text=store.name,
            callback_data=f"{callback_prefix}{store.store_id}"
        ))
    
    if include_back:
        builder.add(InlineKeyboardButton(
            text="🔙 Назад",
            callback_data=back_callback
        ))
    
    # Размещаем кнопки в одну колонку
    builder.adjust(1)
    
    return builder.as_markup()


# Функция для создания клавиатуры списка категорий
def build_categories_kb(categories, callback_prefix="category_", include_back=True, back_callback="back_to_admin_menu"):
    builder = InlineKeyboardBuilder()
    
    for category in categories:
        # Добавляем отступы в зависимости от уровня категории для визуальной иерархии
        indent = "  " * (category.level - 1) if hasattr(category, 'level') else ""
        
        builder.add(InlineKeyboardButton(
            text=f"{indent}{category.name}",
            callback_data=f"{callback_prefix}{category.category_id}"
        ))
    
    if include_back:
        builder.add(InlineKeyboardButton(
            text="🔙 Назад",
            callback_data=back_callback
        ))
    
    # Размещаем кнопки в одну колонку
    builder.adjust(1)
    
    return builder.as_markup()


# Функция для создания клавиатуры списка статей
def build_articles_kb(articles, callback_prefix="article_", include_back=True, back_callback="back_to_admin_menu"):
    builder = InlineKeyboardBuilder()
    
    for article in articles:
        builder.add(InlineKeyboardButton(
            text=article.title,
            callback_data=f"{callback_prefix}{article.article_id}"
        ))
    
    if include_back:
        builder.add(InlineKeyboardButton(
            text="🔙 Назад",
            callback_data=back_callback
        ))
    
    # Размещаем кнопки в одну колонку
    builder.adjust(1)
    
    return builder.as_markup()


# Функция для создания клавиатуры списка тестов
def build_tests_kb(tests, callback_prefix="test_", include_back=True, back_callback="back_to_admin_menu"):
    builder = InlineKeyboardBuilder()
    
    for test in tests:
        builder.add(InlineKeyboardButton(
            text=test.title,
            callback_data=f"{callback_prefix}{test.test_id}"
        ))
    
    if include_back:
        builder.add(InlineKeyboardButton(
            text="🔙 Назад",
            callback_data=back_callback
        ))
    
    # Размещаем кнопки в одну колонку
    builder.adjust(1)
    
    return builder.as_markup()
