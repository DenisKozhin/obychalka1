from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_categories_kb(categories, include_back=True, admin_mode=False):
    """
    Создает клавиатуру с категориями
    
    Args:
        categories: Список кортежей (id, name) категорий
        include_back: Включать ли кнопку "Назад"
        admin_mode: Режим администратора (с дополнительными кнопками)
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с категориями
    """
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопки для каждой категории
    for category_id, category_name in categories:
        if admin_mode:
            builder.add(InlineKeyboardButton(
                text=category_name,
                callback_data=f"admin_category_{category_id}"
            ))
        else:
            builder.add(InlineKeyboardButton(
                text=category_name,
                callback_data=f"category_{category_id}"
            ))
    
    # В режиме администратора добавляем кнопку добавления категории
    if admin_mode:
        builder.add(InlineKeyboardButton(
            text="➕ Додати категорію",
            callback_data="add_category"
        ))
    
    # Добавляем кнопку "Назад" если нужно
    if include_back:
        if admin_mode:
            builder.add(InlineKeyboardButton(
                text="🔙 Назад",
                callback_data="admin_back_to_library"
            ))
        else:
            builder.add(InlineKeyboardButton(
                text="🔙 Назад",
                callback_data="back_to_library"
            ))
    
    # Размещаем кнопки по одной в строку
    builder.adjust(1)
    
    return builder.as_markup()

def get_category_actions_kb(category_id, parent_id=None):
    """
    Создает клавиатуру с действиями для категории (для администратора)
    
    Args:
        category_id: ID категории
        parent_id: ID родительской категории
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с действиями
    """
    builder = InlineKeyboardBuilder()
    
    # Кнопки действий с категорией
    builder.add(InlineKeyboardButton(
        text="📝 Редагувати назву",
        callback_data=f"edit_category_{category_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="❌ Видалити категорію",
        callback_data=f"delete_category_{category_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="📋 Перегляд статей",
        callback_data=f"list_articles_{category_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="📕 Додати статтю",
        callback_data=f"add_article_{category_id}"
    ))
    
    # Добавляем кнопку для добавления подкатегории, если уровень < 3
    builder.add(InlineKeyboardButton(
        text="➕ Додати підкатегорію",
        callback_data=f"add_subcategory_{category_id}"
    ))
    
    # Кнопка возврата
    if parent_id:
        builder.add(InlineKeyboardButton(
            text="🔙 Назад",
            callback_data=f"admin_category_{parent_id}"
        ))
    else:
        builder.add(InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="admin_library"
        ))
    
    # Размещаем кнопки по одной в строку
    builder.adjust(1)
    
    return builder.as_markup()

def get_articles_kb(articles, category_id, admin_mode=False):
    """
    Создает клавиатуру со списком статей
    
    Args:
        articles: Список статей
        category_id: ID категории
        admin_mode: Режим администратора
    
    Returns:
        InlineKeyboardMarkup: Клавиатура со статьями
    """
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопки для каждой статьи
    for article in articles:
        if admin_mode:
            builder.add(InlineKeyboardButton(
                text=article["title"],
                callback_data=f"admin_article_{article['article_id']}"
            ))
        else:
            builder.add(InlineKeyboardButton(
                text=article["title"],
                callback_data=f"article_{article['article_id']}"
            ))
    
    # В режиме администратора добавляем кнопку добавления статьи
    if admin_mode:
        builder.add(InlineKeyboardButton(
            text="➕ Додати статтю",
            callback_data=f"add_article_{category_id}"
        ))
    
    # Кнопка возврата
    if admin_mode:
        builder.add(InlineKeyboardButton(
            text="🔙 Назад",
            callback_data=f"admin_category_{category_id}"
        ))
    else:
        builder.add(InlineKeyboardButton(
            text="🔙 Назад",
            callback_data=f"category_{category_id}"
        ))
    
    # Размещаем кнопки по одной в строку
    builder.adjust(1)
    
    return builder.as_markup()

def get_article_actions_kb(article_id, category_id):
    """
    Создает клавиатуру с действиями для статьи (для администратора)
    
    Args:
        article_id: ID статьи
        category_id: ID категории
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с действиями
    """
    builder = InlineKeyboardBuilder()
    
    # Кнопки действий со статьей
    builder.add(InlineKeyboardButton(
        text="📝 Редагувати статтю",
        callback_data=f"edit_article_{article_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="🖼️ Управління зображеннями",
        callback_data=f"manage_images_{article_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="📨 Відправити користувачам",
        callback_data=f"send_article_{article_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="📋 Додати тест",
        callback_data=f"add_test_{article_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="❌ Видалити статтю",
        callback_data=f"delete_article_{article_id}"
    ))
    
    # Кнопка возврата
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data=f"list_articles_{category_id}"
    ))
    
    # Размещаем кнопки по одной в строку
    builder.adjust(1)
    
    return builder.as_markup()

def get_article_navigation_kb(article_id, test_id=None, category_id=None):
    """
    Создает клавиатуру навигации для статьи (для пользователя)
    
    Args:
        article_id: ID статьи
        test_id: ID теста (если есть)
        category_id: ID категории
    
    Returns:
        InlineKeyboardMarkup: Клавиатура навигации
    """
    builder = InlineKeyboardBuilder()
    
    # Если есть тест, добавляем кнопку
    if test_id:
        builder.add(InlineKeyboardButton(
            text="📝 Пройти тест",
            callback_data=f"start_test_{test_id}"
        ))
    
    # Кнопка возврата
    if category_id:
        builder.add(InlineKeyboardButton(
            text="🔙 Назад до списку статей",
            callback_data=f"category_{category_id}"
        ))
    else:
        builder.add(InlineKeyboardButton(
            text="🔙 Назад до бібліотеки",
            callback_data="back_to_library"
        ))
    
    # Размещаем кнопки по одной в строку
    builder.adjust(1)
    
    return builder.as_markup()

def get_send_article_kb(article_id):
    """
    Создает клавиатуру для выбора получателей рассылки статьи
    
    Args:
        article_id: ID статьи
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с вариантами рассылки
    """
    builder = InlineKeyboardBuilder()
    
    # Варианты рассылки
    builder.add(InlineKeyboardButton(
        text="🌐 Всім користувачам",
        callback_data=f"send_to_all_{article_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="🏙 По місту",
        callback_data=f"send_by_city_{article_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="🏪 По магазину",
        callback_data=f"send_by_store_{article_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="👤 Конкретному користувачу",
        callback_data=f"send_to_user_{article_id}"
    ))
    
    # Кнопка возврата
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data=f"admin_article_{article_id}"
    ))
    
    # Размещаем кнопки по одной в строку
    builder.adjust(1)
    
    return builder.as_markup()

def get_manage_images_kb(article_id, images):
    """
    Создает клавиатуру для управления изображениями статьи
    
    Args:
        article_id: ID статьи
        images: Список изображений
    
    Returns:
        InlineKeyboardMarkup: Клавиатура для управления изображениями
    """
    builder = InlineKeyboardBuilder()
    
    # Кнопки для каждого изображения
    for i, image in enumerate(images):
        builder.add(InlineKeyboardButton(
            text=f"🖼️ Зображення {i+1} 🗑",
            callback_data=f"delete_image_{image['image_id']}"
        ))
    
    # Кнопка добавления нового изображения
    if len(images) < 5:  # Максимум 5 изображений
        builder.add(InlineKeyboardButton(
            text="➕ Додати зображення",
            callback_data=f"add_image_{article_id}"
        ))
    
    # Кнопка возврата
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data=f"admin_article_{article_id}"
    ))
    
    # Размещаем кнопки по одной в строку
    builder.adjust(1)
    
    return builder.as_markup()

def get_confirm_delete_kb(entity_type, entity_id, return_callback):
    """
    Создает клавиатуру подтверждения удаления
    
    Args:
        entity_type: Тип сущности (category, article, image)
        entity_id: ID сущности
        return_callback: Callback для возврата
    
    Returns:
        InlineKeyboardMarkup: Клавиатура подтверждения
    """
    builder = InlineKeyboardBuilder()
    
    # Кнопки подтверждения/отмены
    builder.add(InlineKeyboardButton(
        text="✅ Так, видалити",
        callback_data=f"confirm_delete_{entity_type}_{entity_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="❌ Ні, скасувати",
        callback_data=return_callback
    ))
    
    # Размещаем кнопки по одной в строку
    builder.adjust(1)
    
    return builder.as_markup()
