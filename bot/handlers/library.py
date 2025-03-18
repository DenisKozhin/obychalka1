import sys
import os
from datetime import datetime

if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from bot.database.models import Category, Article, ArticleImage, User, Test, AdminLog
from bot.keyboards.admin_kb import get_admin_menu_kb
from bot.utils.logger import logger
from bot.database.operations_library import (
    get_categories, get_category_by_id, create_category, update_category, delete_category,
    get_articles_by_category, get_article_by_id, create_article, update_article, delete_article,
    get_article_images, add_article_image, delete_article_image
)

# Создаем роутер для административного интерфейса библиотеки знаний
router = Router()

# Определяем состояния для машины состояний
class LibraryAdminStates(StatesGroup):
    # Состояния для работы с категориями
    waiting_for_category_name = State()
    waiting_for_subcategory_name = State()
    waiting_for_edit_category_name = State()
    
    # Состояния для работы со статьями
    waiting_for_article_title = State()
    waiting_for_article_content = State()
    waiting_for_article_images = State()
    
    # Состояния для редактирования статьи
    waiting_for_edit_article_title = State()
    waiting_for_edit_article_content = State()
    
    # Состояния для отправки статьи пользователям
    waiting_for_select_city = State()
    waiting_for_select_store = State()
    waiting_for_select_user = State()
    waiting_for_confirm_send = State()
    
    # Состояния для создания и редактирования тестов
    waiting_for_test_title = State()
    waiting_for_test_pass_threshold = State()
    waiting_for_question_text = State()
    waiting_for_answer_text = State()
    waiting_for_correct_answer = State()
    confirm_test_creation = State()

# Создаем клавиатуру для административного интерфейса библиотеки знаний
async def get_admin_categories_kb(session: AsyncSession, parent_id=None, level=1):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    # Получаем список категорий
    categories = await get_categories(session, parent_id=parent_id, level=level)
    
    # Добавляем кнопки для каждой категории
    for category in categories:
        builder.add(InlineKeyboardButton(
            text=category.name,
            callback_data=f"admin_category_{category.category_id}_{level}"
        ))
    
    # Добавляем кнопку добавления новой категории или подкатегории
    if parent_id is None and level == 1:
        builder.add(InlineKeyboardButton(
            text="➕ Додати категорію",
            callback_data="add_main_category"
        ))
    else:
        builder.add(InlineKeyboardButton(
            text="➕ Додати підкатегорію",
            callback_data=f"add_subcategory_{parent_id}_{level}"
        ))
    
    # Если не на верхнем уровне, добавляем кнопку "Назад"
    if level > 1 or parent_id is not None:
        # Получаем родительскую категорию
        if parent_id is not None:
            parent = await get_category_by_id(session, parent_id)
            back_parent_id = parent.parent_id if parent else None
            back_level = level - 1
        else:
            back_parent_id = None
            back_level = level - 1
        
        # Добавляем кнопку "Назад"
        builder.add(InlineKeyboardButton(
            text="🔙 Назад",
            callback_data=f"admin_back_to_categories_{back_level}_{back_parent_id or 0}"
        ))
    
    # Добавляем кнопку для возврата в админ-меню
    builder.add(InlineKeyboardButton(
        text="🔙 Назад до адмін-меню",
        callback_data="back_to_admin_menu"
    ))
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()

# Создаем клавиатуру для действий с категорией
async def get_category_actions_kb(session: AsyncSession, category_id: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    # Получаем информацию о категории
    category = await get_category_by_id(session, category_id)
    
    if not category:
        return None
    
    # Добавляем кнопку редактирования названия
    builder.add(InlineKeyboardButton(
        text="✏️ Редагувати назву",
        callback_data=f"edit_category_{category_id}"
    ))
    
    # Добавляем кнопку добавления подкатегории, если уровень < 3
    if category.level < 3:
        builder.add(InlineKeyboardButton(
            text="➕ Додати підкатегорію",
            callback_data=f"add_subcategory_{category_id}_{category.level}"
        ))
    
    # Если уровень = 3 (группа товаров), добавляем кнопку для статей
    if category.level == 3:
        builder.add(InlineKeyboardButton(
            text="📄 Статті в групі",
            callback_data=f"admin_articles_in_category_{category_id}"
        ))
        
        builder.add(InlineKeyboardButton(
            text="➕ Додати статтю",
            callback_data=f"add_article_{category_id}"
        ))
    
    # Добавляем кнопку удаления категории
    builder.add(InlineKeyboardButton(
        text="🗑 Видалити категорію",
        callback_data=f"delete_category_{category_id}"
    ))
    
    # Добавляем кнопку для возврата к списку категорий
    if category.parent_id:
        builder.add(InlineKeyboardButton(
            text="🔙 Назад до категорій",
            callback_data=f"admin_back_to_categories_{category.level}_{category.parent_id}"
        ))
    else:
        builder.add(InlineKeyboardButton(
            text="🔙 Назад до головних категорій",
            callback_data="admin_back_to_categories_1_0"
        ))
    
    # Добавляем кнопку для возврата в админ-меню
    builder.add(InlineKeyboardButton(
        text="🔙 Назад до адмін-меню",
        callback_data="back_to_admin_menu"
    ))
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()

# Создаем клавиатуру для списка статей
async def get_admin_articles_kb(session: AsyncSession, category_id: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    # Получаем список статей в категории
    articles = await get_articles_by_category(session, category_id)
    
    # Добавляем кнопки для каждой статьи
    for article in articles:
        builder.add(InlineKeyboardButton(
            text=article.title,
            callback_data=f"admin_article_{article.article_id}"
        ))
    
    # Добавляем кнопку добавления новой статьи
    builder.add(InlineKeyboardButton(
        text="➕ Додати статтю",
        callback_data=f"add_article_{category_id}"
    ))
    
    # Добавляем кнопку для возврата к категории
    builder.add(InlineKeyboardButton(
        text="🔙 Назад до категорії",
        callback_data=f"admin_category_{category_id}_3"
    ))
    
    # Добавляем кнопку для возврата в админ-меню
    builder.add(InlineKeyboardButton(
        text="🔙 Назад до адмін-меню",
        callback_data="back_to_admin_menu"
    ))
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()

# Создаем клавиатуру для действий со статьей
async def get_article_actions_kb(session: AsyncSession, article_id: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    # Получаем информацию о статье
    article = await get_article_by_id(session, article_id)
    
    if not article:
        return None
    
    # Добавляем кнопки действий
    builder.add(InlineKeyboardButton(
        text="✏️ Редагувати заголовок",
        callback_data=f"edit_article_title_{article_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="✏️ Редагувати зміст",
        callback_data=f"edit_article_content_{article_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🖼 Управління зображеннями",
        callback_data=f"manage_article_images_{article_id}"
    ))
    
    # Проверяем, есть ли тест для этой статьи
    test_result = await session.execute(
        select(Test).where(Test.article_id == article_id)
    )
    test = test_result.scalar_one_or_none()
    
    if test:
        builder.add(InlineKeyboardButton(
            text="📝 Редагувати тест",
            callback_data=f"edit_test_{test.test_id}"
        ))
    else:
        builder.add(InlineKeyboardButton(
            text="➕ Додати тест",
            callback_data=f"add_test_{article_id}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="📤 Відправити користувачам",
        callback_data=f"send_article_{article_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🗑 Видалити статтю",
        callback_data=f"delete_article_{article_id}"
    ))
    
    # Добавляем кнопку для возврата к списку статей
    builder.add(InlineKeyboardButton(
        text="🔙 Назад до списку статей",
        callback_data=f"admin_articles_in_category_{article.category_id}"
    ))
    
    # Добавляем кнопку для возврата в админ-меню
    builder.add(InlineKeyboardButton(
        text="🔙 Назад до адмін-меню",
        callback_data="back_to_admin_menu"
    ))
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()

# Создаем клавиатуру для управления изображениями
async def get_manage_images_kb(session: AsyncSession, article_id: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    # Получаем информацию о статье
    article = await get_article_by_id(session, article_id)
    
    if not article:
        return None
    
    # Получаем изображения статьи
    images = await get_article_images(session, article_id)
    
    # Добавляем кнопки для каждого изображения
    for i, image in enumerate(images):
        builder.add(InlineKeyboardButton(
            text=f"Зображення {i+1} 🗑",
            callback_data=f"delete_image_{image.image_id}"
        ))
    
    # Если изображений меньше 5, добавляем кнопку добавления
    if len(images) < 5:
        builder.add(InlineKeyboardButton(
            text="➕ Додати зображення",
            callback_data=f"add_image_{article_id}"
        ))
    
    # Добавляем кнопку для возврата к статье
    builder.add(InlineKeyboardButton(
        text="🔙 Назад до статті",
        callback_data=f"admin_article_{article_id}"
    ))
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()

# Создаем клавиатуру для подтверждения удаления
async def get_confirm_delete_kb(entity_type: str, entity_id: int, return_callback: str):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="✅ Так, видалити",
        callback_data=f"confirm_delete_{entity_type}_{entity_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="❌ Ні, скасувати",
        callback_data=return_callback
    ))
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()

# Создаем клавиатуру для выбора получателей статьи
async def get_send_article_kb(article_id: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопки для различных типов рассылки
    builder.add(InlineKeyboardButton(
        text="🌐 Всім користувачам",
        callback_data=f"send_to_all_{article_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🏙 За містом",
        callback_data=f"send_by_city_{article_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🏪 За магазином",
        callback_data=f"send_by_store_{article_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="👤 Конкретному користувачу",
        callback_data=f"send_to_user_{article_id}"
    ))
    
    # Добавляем кнопку для возврата к статье
    builder.add(InlineKeyboardButton(
        text="🔙 Назад до статті",
        callback_data=f"admin_article_{article_id}"
    ))
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()

# Создаем клавиатуру для выбора города при отправке статьи
async def get_cities_for_sending_kb(session: AsyncSession, article_id: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    from bot.database.models import City
    
    builder = InlineKeyboardBuilder()
    
    # Получаем список городов
    result = await session.execute(select(City).order_by(City.name))
    cities = result.scalars().all()
    
    # Добавляем кнопки для каждого города
    for city in cities:
        builder.add(InlineKeyboardButton(
            text=city.name,
            callback_data=f"send_city_{article_id}_{city.city_id}"
        ))
    
    # Добавляем кнопку для возврата к выбору получателей
    builder.add(InlineKeyboardButton(
        text="🔙 Назад до вибору отримувачів",
        callback_data=f"send_article_{article_id}"
    ))
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()

# Создаем клавиатуру для выбора магазина при отправке статьи
async def get_stores_for_sending_kb(session: AsyncSession, article_id: int, city_id=None):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    from bot.database.models import Store
    
    builder = InlineKeyboardBuilder()
    
    # Получаем список магазинов
    if city_id:
        result = await session.execute(
            select(Store).where(Store.city_id == city_id).order_by(Store.name)
        )
    else:
        result = await session.execute(
            select(Store).order_by(Store.name)
        )
    stores = result.scalars().all()
    
    # Добавляем кнопки для каждого магазина
    for store in stores:
        builder.add(InlineKeyboardButton(
            text=store.name,
            callback_data=f"send_store_{article_id}_{store.store_id}"
        ))
    
    # Добавляем кнопку для возврата к выбору города или получателей
    if city_id:
        builder.add(InlineKeyboardButton(
            text="🔙 Назад до вибору міста",
            callback_data=f"send_by_city_{article_id}"
        ))
    else:
        builder.add(InlineKeyboardButton(
            text="🔙 Назад до вибору отримувачів",
            callback_data=f"send_article_{article_id}"
        ))
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()

# Создаем клавиатуру для подтверждения отправки статьи
async def get_confirm_send_kb(article_id: int, recipients_type: str, recipient_id=None):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопки подтверждения/отмены
    builder.add(InlineKeyboardButton(
        text="✅ Так, відправити",
        callback_data=f"confirm_send_{article_id}_{recipients_type}_{recipient_id or 0}"
    ))
    
    # Определяем callback для возврата
    if recipients_type == "all":
        return_callback = f"send_article_{article_id}"
    elif recipients_type == "city":
        return_callback = f"send_by_city_{article_id}"
    elif recipients_type == "store":
        return_callback = f"send_by_store_{article_id}"
    elif recipients_type == "user":
        return_callback = f"send_article_{article_id}"
    else:
        return_callback = f"send_article_{article_id}"
    
    builder.add(InlineKeyboardButton(
        text="❌ Ні, скасувати",
        callback_data=return_callback
    ))
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()

# Создаем клавиатуру для работы с тестами
async def get_test_management_kb(test_id: int, article_id: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопки для управления тестом
    builder.add(InlineKeyboardButton(
        text="➕ Додати питання",
        callback_data=f"add_question_{test_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="📝 Список питань",
        callback_data=f"list_questions_{test_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="✏️ Редагувати назву тесту",
        callback_data=f"edit_test_title_{test_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="✏️ Змінити поріг проходження",
        callback_data=f"edit_test_threshold_{test_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🗑 Видалити тест",
        callback_data=f"delete_test_{test_id}"
    ))
    
    # Добавляем кнопку для возврата к статье
    builder.add(InlineKeyboardButton(
        text="🔙 Назад до статті",
        callback_data=f"admin_article_{article_id}"
    ))
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()

# Обработчик команды "Статьи" в админ-меню
@router.callback_query(F.data == "admin_articles")
async def admin_articles_command(callback: CallbackQuery, session: AsyncSession):
    try:
        await callback.message.edit_text(
            "Управління бібліотекою знань. Виберіть категорію:",
            reply_markup=await get_admin_categories_kb(session)
        )
        
        # Логируем действие администратора
        log = AdminLog(
            admin_id=callback.from_user.id,
            action_type="VIEW",
            entity_type="LIBRARY",
            details={"action": "view_library_categories"}
        )
        session.add(log)
        await session.commit()
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в admin_articles_command: {e}")
        await callback.message.edit_text(
            "Виникла помилка при завантаженні бібліотеки. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик для возврата к административным категориям
@router.callback_query(F.data.startswith("admin_back_to_categories_"))
async def admin_back_to_categories(callback: CallbackQuery, session: AsyncSession):
    try:
        # Извлекаем уровень и ID родительской категории из callback_data
        parts = callback.data.split("_")
        level = int(parts[4])
        parent_id = int(parts[5]) if parts[5] != "0" else None
        
        if level == 1 and parent_id is None:
            # Если возвращаемся к корневым категориям
            await callback.message.edit_text(
                "Управління бібліотекою знань. Виберіть категорію:",
                reply_markup=await get_admin_categories_kb(session)
            )
        else:
            # Если возвращаемся к подкатегориям
            parent = await get_category_by_id(session, parent_id)
            await callback.message.edit_text(
                f"Категорія: {parent.name if parent else 'Основні категорії'}\n\nВиберіть підкатегорію:",
                reply_markup=await get_admin_categories_kb(session, parent_id, level)
            )
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в admin_back_to_categories: {e}")
        await callback.message.edit_text(
            "Виникла помилка при поверненні до категорій. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик выбора категории администратором
@router.callback_query(F.data.startswith("admin_category_"))
async def admin_category_selection(callback: CallbackQuery, session: AsyncSession):
    try:
        # Извлекаем ID категории и уровень из callback_data
        parts = callback.data.split("_")
        category_id = int(parts[2])
        level = int(parts[3])
        
        # Получаем информацию о выбранной категории
        category = await get_category_by_id(session, category_id)
        
        if not category:
            await callback.message.edit_text(
                "Категорія не знайдена. Поверніться до головного меню.",
                reply_markup=await get_admin_categories_kb(session)
            )
            await callback.answer()
            return
        
        # Проверяем уровень категории
        if category.level < 3:
            # Если это категория 1 или 2 уровня, показываем подкатегории
            subcategories = await get_categories(session, parent_id=category_id)
            
            if not subcategories:
                await callback.message.edit_text(
                    f"Категорія: {category.name} (рівень {category.level})\n\n"
                    f"У цій категорії немає підкатегорій.",
                    reply_markup=await get_category_actions_kb(session, category_id)
                )
            else:
                await callback.message.edit_text(
                    f"Категорія: {category.name} (рівень {category.level})\n\n"
                    f"Виберіть підкатегорію або дію з поточною категорією:",
                    reply_markup=await get_admin_categories_kb(session, category_id, category.level + 1)
                )
        else:
            # Если это категория 3 уровня (группа товаров), показываем действия с категорией
            await callback.message.edit_text(
                f"Група товарів: {category.name}\n\n"
                f"Виберіть дію:",
                reply_markup=await get_category_actions_kb(session, category_id)
            )
        
        # Логируем действие администратора
        log = AdminLog(
            admin_id=callback.from_user.id,
            action_type="VIEW",
            entity_type="CATEGORY",
            entity_id=category_id,
            details={"category_name": category.name, "level": category.level}
        )
        session.add(log)
        await session.commit()
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в admin_category_selection: {e}")
        await callback.message.edit_text(
            "Виникла помилка при завантаженні категорії. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик добавления основной категории
@router.callback_query(F.data == "add_main_category")
async def add_main_category(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_text(
            "Введіть назву нової категорії (рівень 1):"
        )
        
        # Устанавливаем состояние ожидания ввода названия категории
        await state.set_state(LibraryAdminStates.waiting_for_category_name)
        
        # Сохраняем в состоянии данные о создаваемой категории
        await state.update_data(level=1, parent_id=None)
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в add_main_category: {e}")
        await callback.message.edit_text(
            "Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик добавления подкатегории
@router.callback_query(F.data.startswith("add_subcategory_"))
async def add_subcategory(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        # Извлекаем ID родительской категории и уровень из callback_data
        parts = callback.data.split("_")
        parent_id = int(parts[1])
        parent_level = int(parts[2])
        
        # Получаем информацию о родительской категории
        parent = await get_category_by_id(session, parent_id)
        
        if not parent:
            await callback.message.edit_text(
                "Батьківська категорія не знайдена. Поверніться до головного меню.",
                reply_markup=await get_admin_categories_kb(session)
            )
            await callback.answer()
            return
        
        # Проверяем уровень родительской категории (нельзя добавлять подкатегории к уровню 3)
        if parent.level >= 3:
            await callback.message.edit_text(
                "Неможливо додати підкатегорію до групи товарів (рівень 3).",
                reply_markup=await get_category_actions_kb(session, parent_id)
            )
            await callback.answer()
            return
        
        await callback.message.edit_text(
            f"Введіть назву нової підкатегорії для категорії \"{parent.name}\" (рівень {parent.level + 1}):"
        )
        
        # Устанавливаем состояние ожидания ввода названия подкатегории
        await state.set_state(LibraryAdminStates.waiting_for_subcategory_name)
        
        # Сохраняем в состоянии данные о создаваемой подкатегории
        await state.update_data(parent_id=parent_id, level=parent.level + 1)
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в add_subcategory: {e}")
        await callback.message.edit_text(
            "Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик ввода названия новой категории
@router.message(LibraryAdminStates.waiting_for_category_name)
async def process_category_name(message: Message, state: FSMContext, session: AsyncSession):
    try:
        # Получаем название категории из сообщения
        category_name = message.text.strip()
        
        # Валидация названия
        if len(category_name) < 3:
            await message.answer(
                "Назва категорії повинна містити не менше 3 символів. Введіть іншу назву:"
            )
            return
        
        if len(category_name) > 100:
            await message.answer(
                "Назва категорії не повинна перевищувати 100 символів. Введіть коротшу назву:"
            )
            return
        
        # Получаем данные из состояния
        data = await state.get_data()
        level = data.get("level", 1)
        parent_id = data.get("parent_id")
        
        # Создаем новую категорию
        category = await create_category(session, category_name, parent_id, level)
        
        if not category:
            await message.answer(
                f"Помилка: категорія з назвою '{category_name}' вже існує. Введіть іншу назву:"
            )
            return
        
        # Логируем действие администратора
        log = AdminLog(
            admin_id=message.from_user.id,
            action_type="ADD",
            entity_type="CATEGORY",
            entity_id=category.category_id,
            details={"category_name": category_name, "level": level, "parent_id": parent_id}
        )
        session.add(log)
        await session.commit()
        
        # Сообщаем об успешном создании категории
        if parent_id is None:
            # Если это основная категория
            await message.answer(
                f"Категорія '{category_name}' успішно створена!",
                reply_markup=await get_admin_categories_kb(session)
            )
        else:
            # Если это подкатегория
            parent = await get_category_by_id(session, parent_id)
            await message.answer(
                f"Підкатегорія '{category_name}' успішно створена в категорії '{parent.name if parent else ''}'!",
                reply_markup=await get_admin_categories_kb(session, parent_id, level)
            )
        
        # Сбрасываем состояние
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка в process_category_name: {e}")
        await message.answer(
            "Виникла помилка при створенні категорії. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await state.clear()

# Обработчик ввода названия новой подкатегории
@router.message(LibraryAdminStates.waiting_for_subcategory_name)
async def process_subcategory_name(message: Message, state: FSMContext, session: AsyncSession):
    try:
        # Получаем название подкатегории из сообщения
        subcategory_name = message.text.strip()
        
        # Валидация названия
        if len(subcategory_name) < 3:
            await message.answer(
                "Назва підкатегорії повинна містити не менше 3 символів. Введіть іншу назву:"
            )
            return
        
        if len(subcategory_name) > 100:
            await message.answer(
                "Назва підкатегорії не повинна перевищувати 100 символів. Введіть коротшу назву:"
            )
            return
        
        # Получаем данные из состояния
        data = await state.get_data()
        parent_id = data.get("parent_id")
        level = data.get("level", 2)
        
        if not parent_id:
            await message.answer(
                "Помилка: відсутній ідентифікатор батьківської категорії. Спробуйте ще раз."
            )
            await state.clear()
            return
        
        # Получаем информацию о родительской категории
        parent = await get_category_by_id(session, parent_id)
        
        if not parent:
            await message.answer(
                "Помилка: батьківська категорія не знайдена. Спробуйте ще раз."
            )
            await state.clear()
            return
        
        # Создаем новую подкатегорию
        subcategory = await create_category(session, subcategory_name, parent_id, level)
        
        if not subcategory:
            await message.answer(
                f"Помилка: підкатегорія з назвою '{subcategory_name}' вже існує. Введіть іншу назву:"
            )
            return
        
        # Логируем действие администратора
        log = AdminLog(
            admin_id=message.from_user.id,
            action_type="ADD",
            entity_type="CATEGORY",
            entity_id=subcategory.category_id,
            details={"category_name": subcategory_name, "level": level, "parent_id": parent_id, "parent_name": parent.name}
        )
        session.add(log)
        await session.commit()
        
        # Сообщаем об успешном создании подкатегории
        await message.answer(
            f"Підкатегорія '{subcategory_name}' успішно створена в категорії '{parent.name}'!",
            reply_markup=await get_admin_categories_kb(session, parent_id, parent.level + 1)
        )
        
        # Сбрасываем состояние
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка в process_subcategory_name: {e}")
        await message.answer(
            "Виникла помилка при створенні підкатегорії. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await state.clear()

# Обработчик редактирования категории
@router.callback_query(F.data.startswith("edit_category_"))
async def edit_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        # Извлекаем ID категории из callback_data
        category_id = int(callback.data.split("_")[2])
        
        # Получаем информацию о категории
        category = await get_category_by_id(session, category_id)
        
        if not category:
            await callback.message.edit_text(
                "Категорія не знайдена. Поверніться до головного меню.",
                reply_markup=await get_admin_categories_kb(session)
            )
            await callback.answer()
            return
        
        await callback.message.edit_text(
            f"Поточна назва категорії: \"{category.name}\"\n\n"
            f"Введіть нову назву для категорії:"
        )
        
        # Устанавливаем состояние ожидания ввода нового названия категории
        await state.set_state(LibraryAdminStates.waiting_for_edit_category_name)
        
        # Сохраняем ID категории в состоянии
        await state.update_data(category_id=category_id)
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в edit_category: {e}")
        await callback.message.edit_text(
            "Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик ввода нового названия категории
@router.message(LibraryAdminStates.waiting_for_edit_category_name)
async def process_edit_category_name(message: Message, state: FSMContext, session: AsyncSession):
    try:
        # Получаем новое название категории из сообщения
        new_name = message.text.strip()
        
        # Валидация названия
        if len(new_name) < 3:
            await message.answer(
                "Назва категорії повинна містити не менше 3 символів. Введіть іншу назву:"
            )
            return
        
        if len(new_name) > 100:
            await message.answer(
                "Назва категорії не повинна перевищувати 100 символів. Введіть коротшу назву:"
            )
            return
        
        # Получаем данные из состояния
        data = await state.get_data()
        category_id = data.get("category_id")
        
        if not category_id:
            await message.answer(
                "Помилка: відсутній ідентифікатор категорії. Спробуйте ще раз."
            )
            await state.clear()
            return
        
        # Получаем информацию о категории
        category = await get_category_by_id(session, category_id)
        
        if not category:
            await message.answer(
                "Помилка: категорія не знайдена. Спробуйте ще раз."
            )
            await state.clear()
            return
        
        # Сохраняем старое название для логирования
        old_name = category.name
        
        # Обновляем название категории
        success = await update_category(session, category_id, new_name)
        
        if not success:
            await message.answer(
                f"Помилка: не вдалося оновити назву категорії. Можливо, категорія з назвою '{new_name}' вже існує. Введіть іншу назву:"
            )
            return
        
        # Логируем действие администратора
        log = AdminLog(
            admin_id=message.from_user.id,
            action_type="EDIT",
            entity_type="CATEGORY",
            entity_id=category_id,
            details={"old_name": old_name, "new_name": new_name, "level": category.level}
        )
        session.add(log)
        await session.commit()
        
        # Сообщаем об успешном обновлении категории
        await message.answer(
            f"Назва категорії змінена з \"{old_name}\" на \"{new_name}\"!"
        )
        
        # Показываем соответствующую клавиатуру в зависимости от уровня категории
        if category.parent_id is None:
            # Если это корневая категория
            await message.answer(
                "Виберіть категорію:",
                reply_markup=await get_admin_categories_kb(session)
            )
        else:
            # Если это подкатегория
            await message.answer(
                "Виберіть дію з категорією:",
                reply_markup=await get_category_actions_kb(session, category_id)
            )
        
        # Сбрасываем состояние
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка в process_edit_category_name: {e}")
        await message.answer(
            "Виникла помилка при редагуванні назви категорії. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await state.clear()

# Обработчик удаления категории
@router.callback_query(F.data.startswith("delete_category_"))
async def delete_category_command(callback: CallbackQuery, session: AsyncSession):
    try:
        # Извлекаем ID категории из callback_data
        category_id = int(callback.data.split("_")[2])
        
        # Получаем информацию о категории
        category = await get_category_by_id(session, category_id)
        
        if not category:
            await callback.message.edit_text(
                "Категорія не знайдена. Поверніться до головного меню.",
                reply_markup=await get_admin_categories_kb(session)
            )
            await callback.answer()
            return
        
        # Определяем callback для возврата
        if category.parent_id:
            return_callback = f"admin_category_{category.parent_id}_{category.level-1}"
        else:
            return_callback = "admin_back_to_categories_1_0"
        
        # Проверяем, есть ли подкатегории
        subcategories = await get_categories(session, parent_id=category_id)
        
        # Проверяем, есть ли статьи (только для категорий уровня 3)
        articles_count = 0
        if category.level == 3:
            articles_result = await session.execute(
                select(func.count(Article.article_id))
                .where(Article.category_id == category_id)
            )
            articles_count = articles_result.scalar_one()
        
        # Формируем сообщение для подтверждения удаления
        message_text = f"Ви впевнені, що хочете видалити категорію \"{category.name}\"?"
        
        if subcategories:
            message_text += f"\n\nУвага! Буде видалено також {len(subcategories)} підкатегорій!"
        
        if articles_count > 0:
            message_text += f"\n\nУвага! Буде видалено також {articles_count} статей!"
        
        await callback.message.edit_text(
            message_text,
            reply_markup=await get_confirm_delete_kb("category", category_id, return_callback)
        )
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в delete_category_command: {e}")
        await callback.message.edit_text(
            "Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик подтверждения удаления категории
@router.callback_query(F.data.startswith("confirm_delete_category_"))
async def confirm_delete_category(callback: CallbackQuery, session: AsyncSession):
    try:
        # Извлекаем ID категории из callback_data
        category_id = int(callback.data.split("_")[3])
        
        # Получаем информацию о категории
        category = await get_category_by_id(session, category_id)
        
        if not category:
            await callback.message.edit_text(
                "Категорія не знайдена. Поверніться до головного меню.",
                reply_markup=await get_admin_categories_kb(session)
            )
            await callback.answer()
            return
        
        # Сохраняем данные категории для логирования
        category_data = {
            "id": category.category_id,
            "name": category.name,
            "level": category.level,
            "parent_id": category.parent_id
        }
        
        # Определяем, куда возвращаться после удаления
        parent_id = category.parent_id
        parent_level = category.level - 1 if category.level > 1 else 1
        
        # Удаляем категорию и её подкатегории
        success = await delete_category(session, category_id)
        
        if not success:
            await callback.message.edit_text(
                f"Помилка: не вдалося видалити категорію \"{category.name}\".",
                reply_markup=await get_category_actions_kb(session, category_id)
            )
            await callback.answer()
            return
        
        # Логируем действие администратора
        log = AdminLog(
            admin_id=callback.from_user.id,
            action_type="DELETE",
            entity_type="CATEGORY",
            entity_id=category_id,
            details=category_data
        )
        session.add(log)
        await session.commit()
        
        # Сообщаем об успешном удалении категории
        await callback.message.edit_text(
            f"Категорія \"{category.name}\" успішно видалена!"
        )
        
        # Показываем соответствующую клавиатуру
        if parent_id is None:
            # Если это была корневая категория
            await callback.message.answer(
                "Виберіть категорію:",
                reply_markup=await get_admin_categories_kb(session)
            )
        else:
            # Если это была подкатегория
            parent = await get_category_by_id(session, parent_id)
            if parent:
                await callback.message.answer(
                    f"Повернення до категорії \"{parent.name}\":",
                    reply_markup=await get_admin_categories_kb(session, parent_id, parent_level)
                )
            else:
                await callback.message.answer(
                    "Виберіть категорію:",
                    reply_markup=await get_admin_categories_kb(session)
                )
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в confirm_delete_category: {e}")
        await callback.message.edit_text(
            "Виникла помилка при видаленні категорії. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик просмотра статей в категории
@router.callback_query(F.data.startswith("admin_articles_in_category_"))
async def admin_articles_in_category(callback: CallbackQuery, session: AsyncSession):
    try:
        # Извлекаем ID категории из callback_data
        category_id = int(callback.data.split("_")[3])
        
        # Получаем информацию о категории
        category = await get_category_by_id(session, category_id)
        
        if not category:
            await callback.message.edit_text(
                "Категорія не знайдена. Поверніться до головного меню.",
                reply_markup=await get_admin_categories_kb(session)
            )
            await callback.answer()
            return
        
        # Получаем статьи в категории
        articles = await get_articles_by_category(session, category_id)
        
        if not articles:
            await callback.message.edit_text(
                f"У категорії \"{category.name}\" немає статей.\n\n"
                f"Ви можете додати нову статтю.",
                reply_markup=await get_admin_articles_kb(session, category_id)
            )
        else:
            await callback.message.edit_text(
                f"Статті в категорії \"{category.name}\":",
                reply_markup=await get_admin_articles_kb(session, category_id)
            )
        
        # Логируем действие администратора
        log = AdminLog(
            admin_id=callback.from_user.id,
            action_type="VIEW",
            entity_type="ARTICLES",
            details={"category_id": category_id, "category_name": category.name}
        )
        session.add(log)
        await session.commit()
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в admin_articles_in_category: {e}")
        await callback.message.edit_text(
            "Виникла помилка при завантаженні статей. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик добавления статьи
@router.callback_query(F.data.startswith("add_article_"))
async def add_article(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        # Извлекаем ID категории из callback_data
        category_id = int(callback.data.split("_")[2])
        
        # Получаем информацию о категории
        category = await get_category_by_id(session, category_id)
        
        if not category:
            await callback.message.edit_text(
                "Категорія не знайдена. Поверніться до головного меню.",
                reply_markup=await get_admin_categories_kb(session)
            )
            await callback.answer()
            return
        
        await callback.message.edit_text(
            f"Створення нової статті в категорії \"{category.name}\".\n\n"
            f"Введіть заголовок статті (максимум 200 символів):"
        )
        
        # Устанавливаем состояние ожидания ввода заголовка статьи
        await state.set_state(LibraryAdminStates.waiting_for_article_title)
        
        # Сохраняем ID категории в состоянии
        await state.update_data(category_id=category_id)
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в add_article: {e}")
        await callback.message.edit_text(
            "Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик ввода заголовка статьи
@router.message(LibraryAdminStates.waiting_for_article_title)
async def process_article_title(message: Message, state: FSMContext, session: AsyncSession):
    try:
        # Получаем заголовок статьи из сообщения
        title = message.text.strip()
        
        # Валидация заголовка
        if len(title) < 3:
            await message.answer(
                "Заголовок статті повинен містити не менше 3 символів. Введіть інший заголовок:"
            )
            return
        
        if len(title) > 200:
            await message.answer(
                "Заголовок статті не повинен перевищувати 200 символів. Введіть коротший заголовок:"
            )
            return
        
        # Сохраняем заголовок в состоянии
        await state.update_data(article_title=title)
        
        await message.answer(
            "Тепер введіть текст статті (максимум 4000 символів):\n\n"
            "Ви можете використовувати Markdown для форматування:\n"
            "**жирний текст** - виділення тексту жирним\n"
            "*курсив* - виділення тексту курсивом\n"
            "- список - створення списку\n"
            "1. нумерований список - створення нумерованого списку"
        )
        
        # Устанавливаем состояние ожидания ввода текста статьи
        await state.set_state(LibraryAdminStates.waiting_for_article_content)
    except Exception as e:
        logger.error(f"Ошибка в process_article_title: {e}")
        await message.answer(
            "Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await state.clear()

# Обработчик ввода текста статьи
@router.message(LibraryAdminStates.waiting_for_article_content)
async def process_article_content(message: Message, state: FSMContext, session: AsyncSession):
    try:
        # Получаем текст статьи из сообщения
        content = message.text.strip()
        
        # Валидация текста
        if len(content) < 10:
            await message.answer(
                "Текст статті повинен містити не менше 10 символів. Введіть інший текст:"
            )
            return
        
        if len(content) > 4000:
            await message.answer(
                "Текст статті не повинен перевищувати 4000 символів. Введіть коротший текст:"
            )
            return
        
        # Получаем данные из состояния
        data = await state.get_data()
        category_id = data.get("category_id")
        title = data.get("article_title")
        
        if not category_id or not title:
            await message.answer(
                "Помилка: відсутні дані про категорію або заголовок. Спробуйте ще раз."
            )
            await state.clear()
            return
        
        # Создаем новую статью
        article = await create_article(session, title, content, category_id, message.from_user.id)
        
        if not article:
            await message.answer(
                "Помилка: не вдалося створити статтю. Спробуйте ще раз."
            )
            await state.clear()
            return
        
        # Логируем действие администратора
        log = AdminLog(
            admin_id=message.from_user.id,
            action_type="ADD",
            entity_type="ARTICLE",
            entity_id=article.article_id,
            details={"title": title, "category_id": category_id}
        )
        session.add(log)
        await session.commit()
        
        # Сообщаем об успешном создании статьи и предлагаем добавить изображения
        await message.answer(
            f"Стаття \"{title}\" успішно створена!\n\n"
            f"Тепер ви можете додати зображення до статті (максимум 5 зображень).\n"
            f"Відправте зображення або натисніть кнопку, щоб пропустити цей крок:"
        )
        
        # Создаем клавиатуру для пропуска добавления изображений
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        
        builder = InlineKeyboardBuilder()
        
        builder.add(InlineKeyboardButton(
            text="Пропустити додавання зображень",
            callback_data=f"skip_images_{article.article_id}"
        ))
        
        await message.answer(
            "Пропустити?",
            reply_markup=builder.as_markup()
        )
        
        # Устанавливаем состояние ожидания загрузки изображений
        await state.set_state(LibraryAdminStates.waiting_for_article_images)
        
        # Сохраняем ID статьи и счетчик изображений в состоянии
        await state.update_data(article_id=article.article_id, image_count=0)
    except Exception as e:
        logger.error(f"Ошибка в process_article_content: {e}")
        await message.answer(
            "Виникла помилка при створенні статті. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await state.clear()

# Создаем клавиатуру для пропуска добавления изображений
async def get_image_skip_kb(article_id: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="Пропустити додавання зображень",
        callback_data=f"skip_images_{article_id}"
    ))
    
    return builder.as_markup()

# Обработчик загрузки изображения для статьи
@router.message(LibraryAdminStates.waiting_for_article_images, F.photo)
async def process_article_image(message: Message, state: FSMContext, session: AsyncSession):
    try:
        # Получаем данные из состояния
        data = await state.get_data()
        article_id = data.get("article_id")
        image_count = data.get("image_count", 0)
        
        if not article_id:
            await message.answer(
                "Помилка: відсутній ідентифікатор статті. Спробуйте ще раз."
            )
            await state.clear()
            return
        
        # Проверяем, не превышено ли максимальное количество изображений
        if image_count >= 5:
            await message.answer(
                "Ви вже додали максимальну кількість зображень (5)."
            )
            return
        
        # Получаем информацию о фото
        photo = message.photo[-1]  # Берем фото с наивысшим разрешением
        file_id = photo.file_id
        file_unique_id = photo.file_unique_id
        
        # Добавляем изображение к статье
        image = await add_article_image(session, article_id, file_id, file_unique_id, image_count)
        
        if not image:
            await message.answer(
                "Помилка: не вдалося додати зображення. Можливо, досягнуто максимальної кількості (5)."
            )
            return
        
        # Увеличиваем счетчик изображений
        image_count += 1
        await state.update_data(image_count=image_count)
        
        # Логируем действие администратора
        log = AdminLog(
            admin_id=message.from_user.id,
            action_type="ADD",
            entity_type="IMAGE",
            entity_id=image.image_id,
            details={"article_id": article_id, "position": image_count - 1}
        )
        session.add(log)
        await session.commit()
        
        if image_count < 5:
            # Если можно добавить еще изображения
            await message.answer(
                f"Зображення {image_count}/5 додано!\n\n"
                f"Відправте ще одне зображення або натисніть кнопку, щоб завершити:",
                reply_markup=await get_image_skip_kb(article_id)
            )
        else:
            # Если достигнуто максимальное количество изображений
            await message.answer(
                "Додано максимальну кількість зображень (5).\n\n"
                "Створення статті завершено!"
            )
            
            # Получаем информацию о статье для показа списка статей
            article = await get_article_by_id(session, article_id)
            
            if article:
                await message.answer(
                    f"Повернення до списку статей в категорії:",
                    reply_markup=await get_admin_articles_kb(session, article.category_id)
                )
            else:
                await message.answer(
                    "Виберіть опцію з меню адміністратора:",
                    reply_markup=get_admin_menu_kb()
                )
            
            # Сбрасываем состояние
            await state.clear()
    except Exception as e:
        logger.error(f"Ошибка в process_article_image: {e}")
        await message.answer(
            "Виникла помилка при додаванні зображення. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await state.clear()

# Обработчик пропуска добавления изображений
@router.callback_query(F.data.startswith("skip_images_"))
async def skip_images(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        # Извлекаем ID статьи из callback_data
        article_id = int(callback.data.split("_")[2])
        
        # Получаем информацию о статье
        article = await get_article_by_id(session, article_id)
        
        if not article:
            await callback.message.edit_text(
                "Стаття не знайдена. Поверніться до головного меню.",
                reply_markup=get_admin_menu_kb()
            )
            await callback.answer()
            await state.clear()
            return
        
        await callback.message.edit_text(
            "Створення статті завершено без додавання зображень."
        )
        
        await callback.message.answer(
            f"Повернення до списку статей в категорії:",
            reply_markup=await get_admin_articles_kb(session, article.category_id)
        )
        
        # Сбрасываем состояние
        await state.clear()
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в skip_images: {e}")
        await callback.message.edit_text(
            "Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()
        await state.clear()

# Обработчик просмотра статьи администратором
@router.callback_query(F.data.startswith("admin_article_"))
async def admin_article_view(callback: CallbackQuery, session: AsyncSession):
    try:
        # Извлекаем ID статьи из callback_data
        article_id = int(callback.data.split("_")[2])
        
        # Получаем информацию о статье
        article = await get_article_by_id(session, article_id)
        
        if not article:
            await callback.message.edit_text(
                "Стаття не знайдена. Поверніться до головного меню.",
                reply_markup=await get_admin_categories_kb(session)
            )
            await callback.answer()
            return
        
        # Получаем информацию о категории
        category = await get_category_by_id(session, article.category_id)
        
        # Получаем информацию об авторе
        author_result = await session.execute(
            select(User).where(User.user_id == article.created_by)
        )
        author = author_result.scalar_one_or_none()
        author_name = f"{author.first_name} {author.last_name}" if author else "Невідомий"
        
        # Формируем сообщение с информацией о статье
        article_text = f"<b>{article.title}</b>\n\n{article.content}\n\n"
        article_text += f"Категорія: {category.name if category else 'Невідома'}\n"
        article_text += f"Автор: {author_name}\n"
        article_text += f"Створено: {article.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        article_text += f"Оновлено: {article.updated_at.strftime('%d.%m.%Y %H:%M')}\n"
        
        # Получаем изображения статьи
        images = await get_article_images(session, article_id)
        article_text += f"Зображення: {len(images)}/5\n"
        
        # Получаем информацию о тестах статьи
        tests_result = await session.execute(
            select(Test).where(Test.article_id == article_id)
        )
        tests = tests_result.scalars().all()
        article_text += f"Тести: {len(tests)}\n"
        
        # Отправляем текст статьи
        await callback.message.edit_text(
            article_text,
            parse_mode="HTML"
        )
        
        # Отправляем изображения, если они есть
        for image in images:
            await callback.message.answer_photo(
                photo=image.file_id,
                caption=f"Зображення {image.position + 1}/{len(images)}"
            )
        
        # Отправляем клавиатуру с действиями со статьей
        await callback.message.answer(
            "Виберіть дію зі статтею:",
            reply_markup=await get_article_actions_kb(session, article_id)
        )
        
        # Логируем действие администратора
        log = AdminLog(
            admin_id=callback.from_user.id,
            action_type="VIEW",
            entity_type="ARTICLE",
            entity_id=article_id,
            details={"title": article.title, "category_id": article.category_id}
        )
        session.add(log)
        await session.commit()
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в admin_article_view: {e}")
        await callback.message.edit_text(
            "Виникла помилка при завантаженні статті. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик редактирования заголовка статьи
@router.callback_query(F.data.startswith("edit_article_title_"))
async def edit_article_title(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        # Извлекаем ID статьи из callback_data
        article_id = int(callback.data.split("_")[3])
        
        # Получаем информацию о статье
        article = await get_article_by_id(session, article_id)
        
        if not article:
            await callback.message.edit_text(
                "Стаття не знайдена. Поверніться до головного меню.",
                reply_markup=get_admin_menu_kb()
            )
            await callback.answer()
            return
        
        await callback.message.edit_text(
            f"Поточний заголовок статті: \"{article.title}\"\n\n"
            f"Введіть новий заголовок для статті (максимум 200 символів):"
        )
        
        # Устанавливаем состояние ожидания ввода нового заголовка
        await state.set_state(LibraryAdminStates.waiting_for_edit_article_title)
        
        # Сохраняем ID статьи в состоянии
        await state.update_data(article_id=article_id)
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в edit_article_title: {e}")
        await callback.message.edit_text(
            "Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик ввода нового заголовка статьи
@router.message(LibraryAdminStates.waiting_for_edit_article_title)
async def process_edit_article_title(message: Message, state: FSMContext, session: AsyncSession):
    try:
        # Получаем новый заголовок статьи из сообщения
        new_title = message.text.strip()
        
        # Валидация заголовка
        if len(new_title) < 3:
            await message.answer(
                "Заголовок статті повинен містити не менше 3 символів. Введіть інший заголовок:"
            )
            return
        
        if len(new_title) > 200:
            await message.answer(
                "Заголовок статті не повинен перевищувати 200 символів. Введіть коротший заголовок:"
            )
            return
        
        # Получаем данные из состояния
        data = await state.get_data()
        article_id = data.get("article_id")
        
        if not article_id:
            await message.answer(
                "Помилка: відсутній ідентифікатор статті. Спробуйте ще раз."
            )
            await state.clear()
            return
        
        # Получаем информацию о статье
        article = await get_article_by_id(session, article_id)
        
        if not article:
            await message.answer(
                "Помилка: стаття не знайдена. Спробуйте ще раз."
            )
            await state.clear()
            return
        
        # Сохраняем старый заголовок для логирования
        old_title = article.title
        
        # Обновляем заголовок статьи
        success = await update_article(session, article_id, title=new_title)
        
        if not success:
            await message.answer(
                "Помилка: не вдалося оновити заголовок статті. Спробуйте ще раз."
            )
            return
        
        # Логируем действие администратора
        log = AdminLog(
            admin_id=message.from_user.id,
            action_type="EDIT",
            entity_type="ARTICLE",
            entity_id=article_id,
            details={"field": "title", "old_value": old_title, "new_value": new_title}
        )
        session.add(log)
        await session.commit()
        
        # Сообщаем об успешном обновлении заголовка
        await message.answer(
            f"Заголовок статті змінено з \"{old_title}\" на \"{new_title}\"!"
        )
        
        # Получаем обновленную информацию о статье
        article = await get_article_by_id(session, article_id)
        
        # Показываем клавиатуру с действиями со статьей
        await message.answer(
            "Виберіть дію зі статтею:",
            reply_markup=await get_article_actions_kb(session, article_id)
        )
        
        # Сбрасываем состояние
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка в process_edit_article_title: {e}")
        await message.answer(
            "Виникла помилка при редагуванні заголовка статті. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await state.clear()

# Обработчик редактирования содержимого статьи
@router.callback_query(F.data.startswith("edit_article_content_"))
async def edit_article_content(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        # Извлекаем ID статьи из callback_data
        article_id = int(callback.data.split("_")[3])
        
        # Получаем информацию о статье
        article = await get_article_by_id(session, article_id)
        
        if not article:
            await callback.message.edit_text(
                "Стаття не знайдена. Поверніться до головного меню.",
                reply_markup=get_admin_menu_kb()
            )
            await callback.answer()
            return
        
        await callback.message.edit_text(
            f"Поточний зміст статті:\n\n{article.content}\n\n"
            f"Введіть новий зміст для статті (максимум 4000 символів).\n"
            f"Ви можете використовувати Markdown для форматування."
        )
        
        # Устанавливаем состояние ожидания ввода нового содержимого
        await state.set_state(LibraryAdminStates.waiting_for_edit_article_content)
        
        # Сохраняем ID статьи в состоянии
        await state.update_data(article_id=article_id)
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в edit_article_content: {e}")
        await callback.message.edit_text(
            "Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик ввода нового содержимого статьи
@router.message(LibraryAdminStates.waiting_for_edit_article_content)
async def process_edit_article_content(message: Message, state: FSMContext, session: AsyncSession):
    try:
        # Получаем новое содержимое статьи из сообщения
        new_content = message.text.strip()
        
        # Валидация содержимого
        if len(new_content) < 10:
            await message.answer(
                "Зміст статті повинен містити не менше 10 символів. Введіть інший зміст:"
            )
            return
        
        if len(new_content) > 4000:
            await message.answer(
                "Зміст статті не повинен перевищувати 4000 символів. Введіть коротший зміст:"
            )
            return
        
        # Получаем данные из состояния
        data = await state.get_data()
        article_id = data.get("article_id")
        
        if not article_id:
            await message.answer(
                "Помилка: відсутній ідентифікатор статті. Спробуйте ще раз."
            )
            await state.clear()
            return
        
        # Получаем информацию о статье
        article = await get_article_by_id(session, article_id)
        
        if not article:
            await message.answer(
                "Помилка: стаття не знайдена. Спробуйте ще раз."
            )
            await state.clear()
            return
        
        # Обновляем содержимое статьи
        success = await update_article(session, article_id, content=new_content)
        
        if not success:
            await message.answer(
                "Помилка: не вдалося оновити зміст статті. Спробуйте ще раз."
            )
            return
        
        # Логируем действие администратора
        log = AdminLog(
            admin_id=message.from_user.id,
            action_type="EDIT",
            entity_type="ARTICLE",
            entity_id=article_id,
            details={"field": "content", "content_length": len(new_content)}
        )
        session.add(log)
        await session.commit()
        
        # Сообщаем об успешном обновлении содержимого
        await message.answer(
            "Зміст статті успішно оновлено!"
        )
        
        # Показываем клавиатуру с действиями со статьей
        await message.answer(
            "Виберіть дію зі статтею:",
            reply_markup=await get_article_actions_kb(session, article_id)
        )
        
        # Сбрасываем состояние
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка в process_edit_article_content: {e}")
        await message.answer(
            "Виникла помилка при редагуванні змісту статті. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await state.clear()

# Обработчик управления изображениями статьи
@router.callback_query(F.data.startswith("manage_article_images_"))
async def manage_article_images(callback: CallbackQuery, session: AsyncSession):
    try:
        # Извлекаем ID статьи из callback_data
        article_id = int(callback.data.split("_")[3])
        
        # Получаем информацию о статье
        article = await get_article_by_id(session, article_id)
        
        if not article:
            await callback.message.edit_text(
                "Стаття не знайдена. Поверніться до головного меню.",
                reply_markup=get_admin_menu_kb()
            )
            await callback.answer()
            return
        
        # Получаем изображения статьи
        images = await get_article_images(session, article_id)
        
        # Формируем текст сообщения
        message_text = f"Управління зображеннями статті \"{article.title}\".\n\n"
        message_text += f"Поточна кількість зображень: {len(images)}/5\n\n"
        
        if len(images) > 0:
            message_text += "Натисніть на кнопку з номером зображення, щоб видалити його.\n"
        
        if len(images) < 5:
            message_text += "Натисніть кнопку \"Додати зображення\", щоб додати нове зображення."
        
        await callback.message.edit_text(
            message_text,
            reply_markup=await get_manage_images_kb(session, article_id)
        )
        
        # Отправляем изображения, если они есть
        for i, image in enumerate(images):
            await callback.message.answer_photo(
                photo=image.file_id,
                caption=f"Зображення {i+1}/{len(images)}"
            )
        
        # Логируем действие администратора
        log = AdminLog(
            admin_id=callback.from_user.id,
            action_type="VIEW",
            entity_type="IMAGES",
            details={"article_id": article_id, "article_title": article.title, "images_count": len(images)}
        )
        session.add(log)
        await session.commit()
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в manage_article_images: {e}")
        await callback.message.edit_text(
            "Виникла помилка при управлінні зображеннями. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик добавления изображения к статье
@router.callback_query(F.data.startswith("add_image_"))
async def add_image(callback: CallbackQuery, state: FSMContext):
    try:
        # Извлекаем ID статьи из callback_data
        article_id = int(callback.data.split("_")[2])
        
        await callback.message.edit_text(
            "Відправте зображення для статті.\n\n"
            "Підтримуються формати JPEG, PNG, GIF."
        )
        
        # Устанавливаем состояние ожидания загрузки изображения
        await state.set_state(LibraryAdminStates.waiting_for_article_images)
        
        # Сохраняем ID статьи в состоянии
        await state.update_data(article_id=article_id)
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в add_image: {e}")
        await callback.message.edit_text(
            "Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик удаления изображения
@router.callback_query(F.data.startswith("delete_image_"))
async def delete_image(callback: CallbackQuery, session: AsyncSession):
    try:
        # Извлекаем ID изображения из callback_data
        image_id = int(callback.data.split("_")[2])
        
        # Получаем информацию об изображении
        image_result = await session.execute(
            select(ArticleImage).where(ArticleImage.image_id == image_id)
        )
        image = image_result.scalar_one_or_none()
        
        if not image:
            await callback.message.edit_text(
                "Зображення не знайдено. Поверніться до управління статтею.",
                reply_markup=get_admin_menu_kb()
            )
            await callback.answer()
            return
        
        article_id = image.article_id
        
        # Удаляем изображение
        success = await delete_article_image(session, image_id)
        
        if not success:
            await callback.message.edit_text(
                "Помилка: не вдалося видалити зображення. Спробуйте ще раз.",
                reply_markup=await get_manage_images_kb(session, article_id)
            )
            await callback.answer()
            return
        
        # Логируем действие администратора
        log = AdminLog(
            admin_id=callback.from_user.id,
            action_type="DELETE",
            entity_type="IMAGE",
            entity_id=image_id,
            details={"article_id": article_id, "position": image.position}
        )
        session.add(log)
        await session.commit()
        
        # Получаем информацию о статье
        article = await get_article_by_id(session, article_id)
        
        if not article:
            await callback.message.edit_text(
                "Стаття не знайдена. Поверніться до головного меню.",
                reply_markup=get_admin_menu_kb()
            )
            await callback.answer()
            return
        
        # Получаем обновленный список изображений
        images = await get_article_images(session, article_id)
        
        # Формируем текст сообщения
        message_text = f"Зображення успішно видалено!\n\n"
        message_text += f"Управління зображеннями статті \"{article.title}\".\n\n"
        message_text += f"Поточна кількість зображень: {len(images)}/5\n\n"
        
        if len(images) > 0:
            message_text += "Натисніть на кнопку з номером зображення, щоб видалити його.\n"
        
        if len(images) < 5:
            message_text += "Натисніть кнопку \"Додати зображення\", щоб додати нове зображення."
        
        await callback.message.edit_text(
            message_text,
            reply_markup=await get_manage_images_kb(session, article_id)
        )
        
        # Отправляем обновленный список изображений
        for i, img in enumerate(images):
            await callback.message.answer_photo(
                photo=img.file_id,
                caption=f"Зображення {i+1}/{len(images)}"
            )
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в delete_image: {e}")
        await callback.message.edit_text(
            "Виникла помилка при видаленні зображення. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик удаления статьи
@router.callback_query(F.data.startswith("delete_article_"))
async def delete_article_command(callback: CallbackQuery, session: AsyncSession):
    try:
        # Извлекаем ID статьи из callback_data
        article_id = int(callback.data.split("_")[2])
        
        # Получаем информацию о статье
        article = await get_article_by_id(session, article_id)
        
        if not article:
            await callback.message.edit_text(
                "Стаття не знайдена. Поверніться до головного меню.",
                reply_markup=get_admin_menu_kb()
            )
            await callback.answer()
            return
        
        # Определяем callback для возврата
        return_callback = f"admin_articles_in_category_{article.category_id}"
        
        # Получаем количество изображений для уведомления
        images = await get_article_images(session, article_id)
        
        # Проверяем наличие теста
        test_result = await session.execute(
            select(Test).where(Test.article_id == article_id)
        )
        test = test_result.scalar_one_or_none()
        
        # Формируем текст сообщения
        message_text = f"Ви впевнені, що хочете видалити статтю \"{article.title}\"?"
        
        if images:
            message_text += f"\n\nУвага! Буде видалено також {len(images)} зображень!"
        
        if test:
            message_text += f"\n\nУвага! Буде видалено також тест для цієї статті!"
        
        await callback.message.edit_text(
            message_text,
            reply_markup=await get_confirm_delete_kb("article", article_id, return_callback)
        )
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в delete_article_command: {e}")
        await callback.message.edit_text(
            "Виникла помилка при видаленні статті. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик подтверждения удаления статьи
@router.callback_query(F.data.startswith("confirm_delete_article_"))
async def confirm_delete_article(callback: CallbackQuery, session: AsyncSession):
    try:
        # Извлекаем ID статьи из callback_data
        article_id = int(callback.data.split("_")[3])
        
        # Получаем информацию о статье перед удалением
        article = await get_article_by_id(session, article_id)
        
        if not article:
            await callback.message.edit_text(
                "Стаття не знайдена. Поверніться до головного меню.",
                reply_markup=get_admin_menu_kb()
            )
            await callback.answer()
            return
        
        # Сохраняем данные для логирования
        article_data = {
            "id": article.article_id,
            "title": article.title,
            "category_id": article.category_id
        }
        
        category_id = article.category_id
        
        # Удаляем статью и все связанные данные
        success = await delete_article(session, article_id)
        
        if not success:
            await callback.message.edit_text(
                f"Помилка: не вдалося видалити статтю \"{article.title}\".",
                reply_markup=await get_article_actions_kb(session, article_id)
            )
            await callback.answer()
            return
        
        # Логируем действие администратора
        log = AdminLog(
            admin_id=callback.from_user.id,
            action_type="DELETE",
            entity_type="ARTICLE",
            entity_id=article_id,
            details=article_data
        )
        session.add(log)
        await session.commit()
        
        # Сообщаем об успешном удалении
        await callback.message.edit_text(
            f"Стаття \"{article.title}\" успішно видалена!"
        )
        
        # Возвращаемся к списку статей в категории
        await callback.message.answer(
            "Повернення до списку статей:",
            reply_markup=await get_admin_articles_kb(session, category_id)
        )
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в confirm_delete_article: {e}")
        await callback.message.edit_text(
            "Виникла помилка при видаленні статті. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик отправки статьи пользователям
@router.callback_query(F.data.startswith("send_article_"))
async def send_article_command(callback: CallbackQuery, session: AsyncSession):
    try:
        # Извлекаем ID статьи из callback_data
        article_id = int(callback.data.split("_")[2])
        
        # Получаем информацию о статье
        article = await get_article_by_id(session, article_id)
        
        if not article:
            await callback.message.edit_text(
                "Стаття не знайдена. Поверніться до головного меню.",
                reply_markup=get_admin_menu_kb()
            )
            await callback.answer()
            return
        
        await callback.message.edit_text(
            f"Відправка статті \"{article.title}\" користувачам.\n\n"
            f"Виберіть отримувачів статті:",
            reply_markup=await get_send_article_kb(article_id)
        )
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в send_article_command: {e}")
        await callback.message.edit_text(
            "Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик выбора отправки всем пользователям
@router.callback_query(F.data.startswith("send_to_all_"))
async def send_to_all(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        # Извлекаем ID статьи из callback_data
        article_id = int(callback.data.split("_")[3])
        
        # Получаем информацию о статье
        article = await get_article_by_id(session, article_id)
        
        if not article:
            await callback.message.edit_text(
                "Стаття не знайдена. Поверніться до головного меню.",
                reply_markup=get_admin_menu_kb()
            )
            await callback.answer()
            return
        
        # Получаем количество пользователей
        users_count_result = await session.execute(select(func.count(User.user_id)))
        users_count = users_count_result.scalar_one()
        
        await callback.message.edit_text(
            f"Ви збираєтесь відправити статтю \"{article.title}\" всім користувачам ({users_count}).\n\n"
            f"Підтвердіть відправку:",
            reply_markup=await get_confirm_send_kb(article_id, "all")
        )
        
        # Сохраняем данные для отправки
        await state.update_data(
            article_id=article_id,
            recipients_type="all"
        )
        
        await state.set_state(LibraryAdminStates.waiting_for_confirm_send)
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в send_to_all: {e}")
        await callback.message.edit_text(
            "Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик выбора отправки по городу
@router.callback_query(F.data.startswith("send_by_city_"))
async def send_by_city(callback: CallbackQuery, session: AsyncSession):
    try:
        # Извлекаем ID статьи из callback_data
        article_id = int(callback.data.split("_")[3])
        
        # Получаем информацию о статье
        article = await get_article_by_id(session, article_id)
        
        if not article:
            await callback.message.edit_text(
                "Стаття не знайдена. Поверніться до головного меню.",
                reply_markup=get_admin_menu_kb()
            )
            await callback.answer()
            return
        
        await callback.message.edit_text(
            f"Відправка статті \"{article.title}\" користувачам певного міста.\n\n"
            f"Виберіть місто:",
            reply_markup=await get_cities_for_sending_kb(session, article_id)
        )
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в send_by_city: {e}")
        await callback.message.edit_text(
            "Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик выбора города для отправки
@router.callback_query(F.data.startswith("send_city_"))
async def send_city_selected(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        # Извлекаем ID статьи и города из callback_data
        parts = callback.data.split("_")
        article_id = int(parts[2])
        city_id = int(parts[3])
        
        # Получаем информацию о статье
        article = await get_article_by_id(session, article_id)
        
        if not article:
            await callback.message.edit_text(
                "Стаття не знайдена. Поверніться до головного меню.",
                reply_markup=get_admin_menu_kb()
            )
            await callback.answer()
            return
        
        # Получаем информацию о городе
        city_result = await session.execute(
            select(City).where(City.city_id == city_id)
        )
        city = city_result.scalar_one_or_none()
        
        if not city:
            await callback.message.edit_text(
                "Місто не знайдено. Поверніться до вибору отримувачів.",
                reply_markup=await get_send_article_kb(article_id)
            )
            await callback.answer()
            return
        
        # Получаем количество пользователей в городе
        users_count_result = await session.execute(
            select(func.count(User.user_id)).where(User.city_id == city_id)
        )
        users_count = users_count_result.scalar_one()
        
        await callback.message.edit_text(
            f"Ви збираєтесь відправити статтю \"{article.title}\" користувачам міста {city.name} ({users_count}).\n\n"
            f"Підтвердіть відправку:",
            reply_markup=await get_confirm_send_kb(article_id, "city", city_id)
        )
        
        # Сохраняем данные для отправки
        await state.update_data(
            article_id=article_id,
            recipients_type="city",
            recipient_id=city_id
        )
        
        await state.set_state(LibraryAdminStates.waiting_for_confirm_send)
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в send_city_selected: {e}")
        await callback.message.edit_text(
            "Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик выбора отправки по магазину
@router.callback_query(F.data.startswith("send_by_store_"))
async def send_by_store(callback: CallbackQuery, session: AsyncSession):
    try:
        # Извлекаем ID статьи из callback_data
        article_id = int(callback.data.split("_")[3])
        
        # Получаем информацию о статье
        article = await get_article_by_id(session, article_id)
        
        if not article:
            await callback.message.edit_text(
                "Стаття не знайдена. Поверніться до головного меню.",
                reply_markup=get_admin_menu_kb()
            )
            await callback.answer()
            return
        
        await callback.message.edit_text(
            f"Відправка статті \"{article.title}\" користувачам певного магазину.\n\n"
            f"Виберіть магазин:",
            reply_markup=await get_stores_for_sending_kb(session, article_id)
        )
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в send_by_store: {e}")
        await callback.message.edit_text(
            "Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик выбора магазина для отправки
@router.callback_query(F.data.startswith("send_store_"))
async def send_store_selected(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        # Извлекаем ID статьи и магазина из callback_data
        parts = callback.data.split("_")
        article_id = int(parts[2])
        store_id = int(parts[3])
        
        # Получаем информацию о статье
        article = await get_article_by_id(session, article_id)
        
        if not article:
            await callback.message.edit_text(
                "Стаття не знайдена. Поверніться до головного меню.",
                reply_markup=get_admin_menu_kb()
            )
            await callback.answer()
            return
        
        # Получаем информацию о магазине
        store_result = await session.execute(
            select(Store).where(Store.store_id == store_id)
        )
        store = store_result.scalar_one_or_none()
        
        if not store:
            await callback.message.edit_text(
                "Магазин не знайдено. Поверніться до вибору отримувачів.",
                reply_markup=await get_send_article_kb(article_id)
            )
            await callback.answer()
            return
        
        # Получаем количество пользователей в магазине
        users_count_result = await session.execute(
            select(func.count(User.user_id)).where(User.store_id == store_id)
        )
        users_count = users_count_result.scalar_one()
        
        await callback.message.edit_text(
            f"Ви збираєтесь відправити статтю \"{article.title}\" користувачам магазину {store.name} ({users_count}).\n\n"
            f"Підтвердіть відправку:",
            reply_markup=await get_confirm_send_kb(article_id, "store", store_id)
        )
        
        # Сохраняем данные для отправки
        await state.update_data(
            article_id=article_id,
            recipients_type="store",
            recipient_id=store_id
        )
        
        await state.set_state(LibraryAdminStates.waiting_for_confirm_send)
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в send_store_selected: {e}")
        await callback.message.edit_text(
            "Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик выбора отправки конкретному пользователю
@router.callback_query(F.data.startswith("send_to_user_"))
async def send_to_user(callback: CallbackQuery, state: FSMContext):
    try:
        # Извлекаем ID статьи из callback_data
        article_id = int(callback.data.split("_")[3])
        
        await callback.message.edit_text(
            "Введіть ID користувача Telegram (числове значення):"
        )
        
        # Сохраняем ID статьи в состоянии
        await state.update_data(
            article_id=article_id,
            recipients_type="user"
        )
        
        await state.set_state(LibraryAdminStates.waiting_for_select_user)
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в send_to_user: {e}")
        await callback.message.edit_text(
            "Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик ввода ID пользователя для отправки
@router.message(LibraryAdminStates.waiting_for_select_user)
async def process_user_id(message: Message, state: FSMContext, session: AsyncSession):
    try:
        # Получаем ID пользователя из сообщения
        try:
            user_id = int(message.text.strip())
        except ValueError:
            await message.answer(
                "Введено неправильний формат ID. Будь ласка, введіть числове значення."
            )
            return
        
        # Получаем данные из состояния
        data = await state.get_data()
        article_id = data.get("article_id")
        
        if not article_id:
            await message.answer(
                "Помилка: відсутній ідентифікатор статті. Спробуйте ще раз."
            )
            await state.clear()
            return
        
        # Получаем информацию о статье
        article = await get_article_by_id(session, article_id)
        
        if not article:
            await message.answer(
                "Стаття не знайдена. Поверніться до головного меню.",
                reply_markup=get_admin_menu_kb()
            )
            await state.clear()
            return
        
        # Проверяем существование пользователя
        user_result = await session.execute(
            select(User).where(User.user_id == user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            await message.answer(
                f"Користувач з ID {user_id} не знайдений у базі даних. Введіть інший ID:"
            )
            return
        
        # Формируем сообщение с подтверждением
        user_name = f"{user.first_name} {user.last_name}"
        
        await message.answer(
            f"Ви збираєтесь відправити статтю \"{article.title}\" користувачу {user_name} (ID: {user_id}).\n\n"
            f"Підтвердіть відправку:",
            reply_markup=await get_confirm_send_kb(article_id, "user", user_id)
        )
        
        # Сохраняем ID пользователя в состоянии
        await state.update_data(recipient_id=user_id)
        
        await state.set_state(LibraryAdminStates.waiting_for_confirm_send)
    except Exception as e:
        logger.error(f"Ошибка в process_user_id: {e}")
        await message.answer(
            "Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await state.clear()

# Обработчик подтверждения отправки статьи
@router.callback_query(F.data.startswith("confirm_send_"))
async def confirm_send_article(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        # Извлекаем данные из callback_data
        parts = callback.data.split("_")
        article_id = int(parts[2])
        recipients_type = parts[3]
        recipient_id = int(parts[4]) if len(parts) > 4 and parts[4] != "0" else None
        
        # Получаем данные из состояния
        data = await state.get_data()
        
        # Приоритет отдаем данным из callback_data, но если их нет, используем данные из состояния
        if not article_id:
            article_id = data.get("article_id")
        
        if not recipients_type:
            recipients_type = data.get("recipients_type")
        
        if not recipient_id and recipients_type != "all":
            recipient_id = data.get("recipient_id")
        
        # Проверяем наличие необходимых данных
        if not article_id or not recipients_type:
            await callback.message.edit_text(
                "Помилка: відсутні дані для відправки. Спробуйте ще раз.",
                reply_markup=get_admin_menu_kb()
            )
            await callback.answer()
            await state.clear()
            return
        
        # Получаем информацию о статье
        article = await get_article_by_id(session, article_id)
        
        if not article:
            await callback.message.edit_text(
                "Стаття не знайдена. Поверніться до головного меню.",
                reply_markup=get_admin_menu_kb()
            )
            await callback.answer()
            await state.clear()
            return
        
        # Получаем список пользователей в зависимости от типа рассылки
        if recipients_type == "all":
            # Получаем всех пользователей
            users_result = await session.execute(select(User))
            users = users_result.scalars().all()
            recipients_info = "всім користувачам"
        
        elif recipients_type == "city":
            # Проверяем наличие ID города
            if not recipient_id:
                await callback.message.edit_text(
                    "Помилка: відсутній ідентифікатор міста. Спробуйте ще раз.",
                    reply_markup=await get_send_article_kb(article_id)
                )
                await callback.answer()
                await state.clear()
                return
            
            # Получаем пользователей по городу
            users_result = await session.execute(
                select(User).where(User.city_id == recipient_id)
            )
            users = users_result.scalars().all()
            
            # Получаем название города
            city_result = await session.execute(
                select(City).where(City.city_id == recipient_id)
            )
            city = city_result.scalar_one_or_none()
            recipients_info = f"користувачам міста {city.name}" if city else f"користувачам міста (ID: {recipient_id})"
        
        elif recipients_type == "store":
            # Проверяем наличие ID магазина
            if not recipient_id:
                await callback.message.edit_text(
                    "Помилка: відсутній ідентифікатор магазину. Спробуйте ще раз.",
                    reply_markup=await get_send_article_kb(article_id)
                )
                await callback.answer()
                await state.clear()
                return
            
            # Получаем пользователей по магазину
            users_result = await session.execute(
                select(User).where(User.store_id == recipient_id)
            )
            users = users_result.scalars().all()
            
            # Получаем название магазина
            store_result = await session.execute(
                select(Store).where(Store.store_id == recipient_id)
            )
            store = store_result.scalar_one_or_none()
            recipients_info = f"користувачам магазину {store.name}" if store else f"користувачам магазину (ID: {recipient_id})"
        
        elif recipients_type == "user":
            # Проверяем наличие ID пользователя
            if not recipient_id:
                await callback.message.edit_text(
                    "Помилка: відсутній ідентифікатор користувача. Спробуйте ще раз.",
                    reply_markup=await get_send_article_kb(article_id)
                )
                await callback.answer()
                await state.clear()
                return
            
            # Получаем пользователя
            user_result = await session.execute(
                select(User).where(User.user_id == recipient_id)
            )
            users = [user_result.scalar_one_or_none()]
            
            # Фильтруем None значения
            users = [user for user in users if user]
            
            # Получаем имя пользователя
            if users:
                user = users[0]
                recipients_info = f"користувачу {user.first_name} {user.last_name}"
            else:
                recipients_info = f"користувачу (ID: {recipient_id})"
        
        else:
            await callback.message.edit_text(
                "Помилка: невідомий тип отримувачів. Спробуйте ще раз.",
                reply_markup=await get_send_article_kb(article_id)
            )
            await callback.answer()
            await state.clear()
            return
        
        # Проверяем, есть ли пользователи для отправки
        if not users:
            await callback.message.edit_text(
                f"Немає користувачів для відправки за обраним критерієм ({recipients_type}).",
                reply_markup=await get_send_article_kb(article_id)
            )
            await callback.answer()
            await state.clear()
            return
        
        # Получаем изображения статьи
        images = await get_article_images(session, article_id)
        
        # Получаем информацию о тесте статьи
        test_result = await session.execute(
            select(Test).where(Test.article_id == article_id)
        )
        test = test_result.scalar_one_or_none()
        
        # Формируем текст статьи
        article_text = f"<b>{article.title}</b>\n\n{article.content}"
        
        # Изменяем сообщение, показывая прогресс отправки
        await callback.message.edit_text(
            f"Починається відправка статті \"{article.title}\" {recipients_info}.\n"
            f"Загальна кількість отримувачів: {len(users)}"
        )
        
        # Создаем клавиатуру для теста, если он есть
        test_keyboard = None
        if test:
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            from aiogram.types import InlineKeyboardButton
            
            builder = InlineKeyboardBuilder()
            builder.add(InlineKeyboardButton(
                text="📝 Пройти тест",
                callback_data=f"start_test_{test.test_id}"
            ))
            test_keyboard = builder.as_markup()
        
        # Отправляем статью каждому пользователю
        sent_count = 0
        errors_count = 0
        
        from bot import bot  # Импортируем экземпляр бота
        
        for user in users:
            try:
                # Отправляем текст статьи
                message = await bot.send_message(
                    chat_id=user.user_id,
                    text=article_text,
                    parse_mode="HTML"
                )
                
                # Отправляем изображения статьи
                for image in images:
                    await bot.send_photo(
                        chat_id=user.user_id,
                        photo=image.file_id,
                        caption=f"Зображення до статті \"{article.title}\""
                    )
                
                # Отправляем кнопку для прохождения теста, если он есть
                if test:
                    await bot.send_message(
                        chat_id=user.user_id,
                        text=f"Для перевірки знань за статтею \"{article.title}\" ви можете пройти тест:",
                        reply_markup=test_keyboard
                    )
                
                sent_count += 1
                
                # Обновляем сообщение с прогрессом каждые 10 отправок
                if sent_count % 10 == 0:
                    await callback.message.edit_text(
                        f"Відправка статті \"{article.title}\" {recipients_info}.\n"
                        f"Прогрес: {sent_count}/{len(users)}"
                    )
            
            except Exception as e:
                logger.error(f"Ошибка при отправке статьи пользователю {user.user_id}: {e}")
                errors_count += 1
        
        # Логируем действие администратора
        log = AdminLog(
            admin_id=callback.from_user.id,
            action_type="SEND",
            entity_type="ARTICLE",
            entity_id=article_id,
            details={
                "title": article.title,
                "recipients_type": recipients_type,
                "recipient_id": recipient_id,
                "total_users": len(users),
                "sent_count": sent_count,
                "errors_count": errors_count
            }
        )
        session.add(log)
        await session.commit()
        
        # Сообщаем о результатах отправки
        result_message = f"Відправка статті \"{article.title}\" {recipients_info} завершена.\n\n"
        result_message += f"Успішно відправлено: {sent_count}/{len(users)}"
        
        if errors_count > 0:
            result_message += f"\nПомилки при відправці: {errors_count}"
        
        await callback.message.edit_text(
            result_message,
            reply_markup=await get_article_actions_kb(session, article_id)
        )
        
        await state.clear()
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в confirm_send_article: {e}")
        await callback.message.edit_text(
            "Виникла помилка при відправці статті. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()
        await state.clear()

# Обработчик добавления теста к статье
@router.callback_query(F.data.startswith("add_test_"))
async def add_test(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        # Извлекаем ID статьи из callback_data
        article_id = int(callback.data.split("_")[2])
        
        # Получаем информацию о статье
        article = await get_article_by_id(session, article_id)
        
        if not article:
            await callback.message.edit_text(
                "Стаття не знайдена. Поверніться до головного меню.",
                reply_markup=get_admin_menu_kb()
            )
            await callback.answer()
            return
        
        # Проверяем, есть ли уже тест для этой статьи
        test_result = await session.execute(
            select(Test).where(Test.article_id == article_id)
        )
        test = test_result.scalar_one_or_none()
        
        if test:
            await callback.message.edit_text(
                f"Для статті \"{article.title}\" вже існує тест. Ви можете редагувати його.",
                reply_markup=await get_test_management_kb(test.test_id, article_id)
            )
            await callback.answer()
            return
        
        await callback.message.edit_text(
            f"Створення нового тесту для статті \"{article.title}\".\n\n"
            f"Введіть назву тесту (максимум 200 символів):"
        )
        
        # Устанавливаем состояние ожидания ввода названия теста
        await state.set_state(LibraryAdminStates.waiting_for_test_title)
        
        # Сохраняем ID статьи в состоянии
        await state.update_data(article_id=article_id)
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в add_test: {e}")
        await callback.message.edit_text(
            "Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик ввода названия теста
@router.message(LibraryAdminStates.waiting_for_test_title)
async def process_test_title(message: Message, state: FSMContext, session: AsyncSession):
    try:
        # Получаем название теста из сообщения
        title = message.text.strip()
        
        # Валидация названия
        if len(title) < 3:
            await message.answer(
                "Назва тесту повинна містити не менше 3 символів. Введіть іншу назву:"
            )
            return
        
        if len(title) > 200:
            await message.answer(
                "Назва тесту не повинна перевищувати 200 символів. Введіть коротшу назву:"
            )
            return
        
        # Получаем данные из состояния
        data = await state.get_data()
        article_id = data.get("article_id")
        
        if not article_id:
            await message.answer(
                "Помилка: відсутній ідентифікатор статті. Спробуйте ще раз."
            )
            await state.clear()
            return
        
        # Получаем информацию о статье
        article = await get_article_by_id(session, article_id)
        
        if not article:
            await message.answer(
                "Стаття не знайдена. Поверніться до головного меню.",
                reply_markup=get_admin_menu_kb()
            )
            await state.clear()
            return
        
        # Сохраняем название теста в состоянии
        await state.update_data(test_title=title)
        
        await message.answer(
            "Введіть поріг проходження тесту у відсотках (від 1 до 100, за замовчуванням 80):"
        )
        
        # Устанавливаем состояние ожидания ввода порога прохождения
        await state.set_state(LibraryAdminStates.waiting_for_test_pass_threshold)
    except Exception as e:
        logger.error(f"Ошибка в process_test_title: {e}")
        await message.answer(
            "Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await state.clear()

# Обработчик ввода порога прохождения теста
@router.message(LibraryAdminStates.waiting_for_test_pass_threshold)
async def process_test_threshold(message: Message, state: FSMContext, session: AsyncSession):
    try:
        # Получаем порог прохождения из сообщения
        threshold_str = message.text.strip()
        
        # Если пользователь ввел пустую строку или "по умолчанию", используем стандартное значение
        if not threshold_str or threshold_str.lower() in ["за замовчуванням", "по умолчанию", "default"]:
            threshold = 80
        else:
            try:
                threshold = int(threshold_str)
                
                # Проверка корректности значения
                if threshold < 1 or threshold > 100:
                    await message.answer(
                        "Поріг проходження повинен бути від 1 до 100. Введіть коректне значення:"
                    )
                    return
            except ValueError:
                await message.answer(
                    "Неправильний формат. Введіть число від 1 до 100 або залиште поле порожнім для значення за замовчуванням (80):"
                )
                return
        
        # Получаем данные из состояния
        data = await state.get_data()
        article_id = data.get("article_id")
        test_title = data.get("test_title")
        
        if not article_id or not test_title:
            await message.answer(
                "Помилка: відсутні дані про статтю або назву тесту. Спробуйте ще раз."
            )
            await state.clear()
            return
        
        # Создаем новый тест
        from bot.database.operations_library import create_test
        test = await create_test(session, test_title, article_id, threshold, message.from_user.id)
        
        if not test:
            await message.answer(
                "Помилка: не вдалося створити тест. Можливо, тест з такою назвою вже існує."
            )
            await state.clear()
            return
        
        # Логируем действие администратора
        log = AdminLog(
            admin_id=message.from_user.id,
            action_type="ADD",
            entity_type="TEST",
            entity_id=test.test_id,
            details={
                "title": test_title,
                "article_id": article_id,
                "pass_threshold": threshold
            }
        )
        session.add(log)
        await session.commit()
        
        # Сообщаем об успешном создании теста
        await message.answer(
            f"Тест \"{test_title}\" з порогом проходження {threshold}% успішно створено!\n\n"
            f"Тепер ви можете додати питання до тесту."
        )
        
        # Показываем клавиатуру для управления тестом
        await message.answer(
            "Оберіть дію з тестом:",
            reply_markup=await get_test_management_kb(test.test_id, article_id)
        )
        
        # Сбрасываем состояние
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка в process_test_threshold: {e}")
        await message.answer(
            "Виникла помилка при створенні тесту. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await state.clear()

# Обработчик добавления вопроса к тесту
@router.callback_query(F.data.startswith("add_question_"))
async def add_question(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        # Извлекаем ID теста из callback_data
        test_id = int(callback.data.split("_")[2])
        
        # Получаем информацию о тесте
        test_result = await session.execute(
            select(Test).where(Test.test_id == test_id)
        )
        test = test_result.scalar_one_or_none()
        
        if not test:
            await callback.message.edit_text(
                "Тест не знайдено. Поверніться до головного меню.",
                reply_markup=get_admin_menu_kb()
            )
            await callback.answer()
            return
        
        # Получаем количество существующих вопросов
        from sqlalchemy import func
        from bot.database.models import Question
        
        question_count_result = await session.execute(
            select(func.count(Question.question_id)).where(Question.test_id == test_id)
        )
        question_count = question_count_result.scalar_one()
        
        # Проверяем, не достигнуто ли максимальное количество вопросов (20)
        if question_count >= 20:
            await callback.message.edit_text(
                "Досягнуто максимальної кількості питань для тесту (20).\n"
                "Видаліть існуючі питання, щоб додати нові.",
                reply_markup=await get_test_management_kb(test_id, test.article_id)
            )
            await callback.answer()
            return
        
        await callback.message.edit_text(
            f"Додавання нового питання до тесту \"{test.title}\".\n\n"
            f"Поточна кількість питань: {question_count}/20\n\n"
            f"Введіть текст питання:"
        )
        
        # Устанавливаем состояние ожидания ввода текста вопроса
        await state.set_state(LibraryAdminStates.waiting_for_question_text)
        
        # Сохраняем ID теста в состоянии
        await state.update_data(test_id=test_id)
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в add_question: {e}")
        await callback.message.edit_text(
            "Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик ввода текста вопроса
@router.message(LibraryAdminStates.waiting_for_question_text)
async def process_question_text(message: Message, state: FSMContext, session: AsyncSession):
    try:
        # Получаем текст вопроса из сообщения
        question_text = message.text.strip()
        
        # Валидация текста
        if len(question_text) < 3:
            await message.answer(
                "Текст питання повинен містити не менше 3 символів. Введіть інший текст:"
            )
            return
        
        if len(question_text) > 500:
            await message.answer(
                "Текст питання не повинен перевищувати 500 символів. Введіть коротший текст:"
            )
            return
        
        # Получаем данные из состояния
        data = await state.get_data()
        test_id = data.get("test_id")
        
        if not test_id:
            await message.answer(
                "Помилка: відсутній ідентифікатор тесту. Спробуйте ще раз."
            )
            await state.clear()
            return
        
        # Создаем новый вопрос
        from bot.database.operations_library import create_question
        question = await create_question(session, test_id, question_text)
        
        if not question:
            await message.answer(
                "Помилка: не вдалося створити питання. Спробуйте ще раз."
            )
            await state.clear()
            return
        
        # Логируем действие администратора
        log = AdminLog(
            admin_id=message.from_user.id,
            action_type="ADD",
            entity_type="QUESTION",
            entity_id=question.question_id,
            details={
                "test_id": test_id,
                "question_text": question_text
            }
        )
        session.add(log)
        await session.commit()
        
        # Сохраняем ID вопроса и счетчик ответов в состоянии
        await state.update_data(
            question_id=question.question_id,
            answer_count=0,
            correct_answers=[]
        )
        
        await message.answer(
            f"Питання успішно додано!\n\n"
            f"Тепер введіть варіант відповіді №1.\n"
            f"ВАЖЛИВО: Помітьте правильні варіанти символом '*' на початку!"
        )
        
        # Устанавливаем состояние ожидания ввода ответа
        await state.set_state(LibraryAdminStates.waiting_for_answer_text)
    except Exception as e:
        logger.error(f"Ошибка в process_question_text: {e}")
        await message.answer(
            "Виникла помилка при створенні питання. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await state.clear()

# Обработчик ввода текста ответа
@router.message(LibraryAdminStates.waiting_for_answer_text)
async def process_answer_text(message: Message, state: FSMContext, session: AsyncSession):
    try:
        # Получаем текст ответа из сообщения
        answer_text = message.text.strip()
        
        # Проверяем, не является ли это командой завершения
        if answer_text.lower() in ["завершити", "готово", "закінчити", "конец", "end", "finish"]:
            # Получаем данные из состояния
            data = await state.get_data()
            test_id = data.get("test_id")
            answer_count = data.get("answer_count", 0)
            correct_answers = data.get("correct_answers", [])
            
            if not test_id:
                await message.answer(
                    "Помилка: відсутній ідентифікатор тесту. Спробуйте ще раз."
                )
                await state.clear()
                return
            
            # Проверяем, добавлены ли ответы
            if answer_count < 2:
                await message.answer(
                    "Необхідно додати мінімум 2 варіанти відповіді. Введіть ще один варіант:"
                )
                return
            
            # Проверяем, есть ли правильные ответы
            if not correct_answers:
                await message.answer(
                    "Необхідно додати хоча б один правильний варіант відповіді (помічений * на початку).\n"
                    "Введіть варіант відповіді:"
                )
                return
            
            # Получаем информацию о тесте
            test_result = await session.execute(
                select(Test).where(Test.test_id == test_id)
            )
            test = test_result.scalar_one_or_none()
            
            if not test:
                await message.answer(
                    "Тест не знайдено. Поверніться до головного меню.",
                    reply_markup=get_admin_menu_kb()
                )
                await state.clear()
                return
            
            # Сообщаем об успешном добавлении ответов
            await message.answer(
                f"Додавання варіантів відповіді завершено!\n\n"
                f"Додано {answer_count} варіантів, з них {len(correct_answers)} правильних."
            )
            
            # Показываем клавиатуру для управления тестом
            await message.answer(
                "Оберіть дію з тестом:",
                reply_markup=await get_test_management_kb(test_id, test.article_id)
            )
            
            # Сбрасываем состояние
            await state.clear()
            return
        
        # Валидация текста
        if len(answer_text) < 1:
            await message.answer(
                "Текст відповіді не може бути порожнім. Введіть текст відповіді:"
            )
            return
        
        if len(answer_text) > 200:
            await message.answer(
                "Текст відповіді не повинен перевищувати 200 символів. Введіть коротший текст:"
            )
            return
        
        # Получаем данные из состояния
        data = await state.get_data()
        question_id = data.get("question_id")
        answer_count = data.get("answer_count", 0)
        correct_answers = data.get("correct_answers", [])
        
        if not question_id:
            await message.answer(
                "Помилка: відсутній ідентифікатор питання. Спробуйте ще раз."
            )
            await state.clear()
            return
        
        # Проверяем, не превышено ли максимальное количество ответов (6)
        if answer_count >= 6:
            await message.answer(
                "Досягнуто максимальної кількості варіантів відповіді (6).\n"
                "Для завершення введіть 'Готово'."
            )
            return
        
        # Определяем, является ли ответ правильным
        is_correct = False
        if answer_text.startswith('*'):
            is_correct = True
            answer_text = answer_text[1:].strip()
        
        # Создаем новый ответ
        from bot.database.operations_library import create_answer
        answer = await create_answer(session, question_id, answer_text, is_correct, answer_count)
        
        if not answer:
            await message.answer(
                "Помилка: не вдалося створити відповідь. Спробуйте ще раз."
            )
            return
        
        # Логируем действие администратора
        log = AdminLog(
            admin_id=message.from_user.id,
            action_type="ADD",
            entity_type="ANSWER",
            entity_id=answer.answer_id,
            details={
                "question_id": question_id,
                "answer_text": answer_text,
                "is_correct": is_correct,
                "position": answer_count
            }
        )
        session.add(log)
        await session.commit()
        
        # Увеличиваем счетчик ответов
        answer_count += 1
        
        # Если ответ правильный, добавляем его в список правильных ответов
        if is_correct:
            correct_answers.append(answer.answer_id)
        
        # Обновляем данные в состоянии
        await state.update_data(
            answer_count=answer_count,
            correct_answers=correct_answers
        )
        
        # Если достигнуто минимальное количество ответов (2), 
        # предлагаем возможность завершить или добавить еще
        if answer_count >= 2:
            if answer_count >= 6:
                # Если достигнуто максимальное количество, принудительно завершаем
                await message.answer(
                    "Досягнуто максимальної кількості варіантів відповіді (6)."
                )
                
                # Проверяем наличие правильных ответов
                if not correct_answers:
                    await message.answer(
                        "УВАГА! Не додано жодного правильного варіанту відповіді!\n"
                        "Необхідно відредагувати питання і додати правильний варіант."
                    )
                
                # Получаем информацию о тесте
                result = await session.execute(
                    select(Test).where(Test.test_id == data.get("test_id"))
                )
                test = result.scalar_one_or_none()
                
                # Показываем клавиатуру для управления тестом
                await message.answer(
                    "Оберіть дію з тестом:",
                    reply_markup=await get_test_management_kb(data.get("test_id"), test.article_id if test else None)
                )
                
                # Сбрасываем состояние
                await state.clear()
            else:
                # Предлагаем добавить еще или завершить
                await message.answer(
                    f"Додано варіант відповіді №{answer_count}.\n\n"
                    f"Ви можете додати ще {6 - answer_count} варіантів або завершити, "
                    f"ввівши 'Готово'.\n\n"
                    f"Введіть варіант відповіді №{answer_count + 1} або 'Готово':"
                )
        else:
            # Если добавлено менее 2 ответов, требуем добавить еще
            await message.answer(
                f"Додано варіант відповіді №{answer_count}.\n\n"
                f"Введіть варіант відповіді №{answer_count + 1}:"
            )
    except Exception as e:
        logger.error(f"Ошибка в process_answer_text: {e}")
        await message.answer(
            "Виникла помилка при додаванні відповіді. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await state.clear()

# Обработчик просмотра списка вопросов теста
@router.callback_query(F.data.startswith("list_questions_"))
async def list_questions(callback: CallbackQuery, session: AsyncSession):
    try:
        # Извлекаем ID теста из callback_data
        test_id = int(callback.data.split("_")[2])
        
        # Получаем информацию о тесте
        test_result = await session.execute(
            select(Test).where(Test.test_id == test_id)
        )
        test = test_result.scalar_one_or_none()
        
        if not test:
            await callback.message.edit_text(
                "Тест не знайдено. Поверніться до головного меню.",
                reply_markup=get_admin_menu_kb()
            )
            await callback.answer()
            return
        
        # Получаем вопросы теста
        from bot.database.models import Question
        
        questions_result = await session.execute(
            select(Question).where(Question.test_id == test_id)
        )
        questions = questions_result.scalars().all()
        
        if not questions:
            await callback.message.edit_text(
                f"У тесті \"{test.title}\" ще немає питань.\n\n"
                f"Додайте питання для повноцінного функціонування тесту.",
                reply_markup=await get_test_management_kb(test_id, test.article_id)
            )
            await callback.answer()
            return
        
        # Формируем список вопросов
        questions_text = f"Питання тесту \"{test.title}\":\n\n"
        
        for i, question in enumerate(questions):
            # Получаем ответы для вопроса
            from bot.database.models import Answer
            
            answers_result = await session.execute(
                select(Answer).where(Answer.question_id == question.question_id)
            )
            answers = answers_result.scalars().all()
            
            questions_text += f"{i+1}. {question.question_text}\n"
            
            for j, answer in enumerate(answers):
                correct_mark = "✅ " if answer.is_correct else "❌ "
                questions_text += f"   {correct_mark}{j+1}) {answer.answer_text}\n"
            
            questions_text += "\n"
        
        # Разбиваем на части, если текст слишком длинный
        max_message_length = 4000
        
        if len(questions_text) <= max_message_length:
            await callback.message.edit_text(
                questions_text,
                reply_markup=await get_test_management_kb(test_id, test.article_id)
            )
        else:
            # Если текст слишком длинный, разбиваем на части
            parts = [questions_text[i:i+max_message_length] for i in range(0, len(questions_text), max_message_length)]
            
            for i, part in enumerate(parts):
                if i == 0:
                    await callback.message.edit_text(part)
                else:
                    await callback.message.answer(part)
            
            # Показываем клавиатуру с последним сообщением
            await callback.message.answer(
                "Оберіть дію з тестом:",
                reply_markup=await get_test_management_kb(test_id, test.article_id)
            )
        
        # Логируем действие администратора
        log = AdminLog(
            admin_id=callback.from_user.id,
            action_type="VIEW",
            entity_type="QUESTIONS",
            details={"test_id": test_id, "test_title": test.title, "questions_count": len(questions)}
        )
        session.add(log)
        await session.commit()
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в list_questions: {e}")
        await callback.message.edit_text(
            "Виникла помилка при завантаженні питань. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик редактирования названия теста
@router.callback_query(F.data.startswith("edit_test_title_"))
async def edit_test_title(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        # Извлекаем ID теста из callback_data
        test_id = int(callback.data.split("_")[3])
        
        # Получаем информацию о тесте
        test_result = await session.execute(
            select(Test).where(Test.test_id == test_id)
        )
        test = test_result.scalar_one_or_none()
        
        if not test:
            await callback.message.edit_text(
                "Тест не знайдено. Поверніться до головного меню.",
                reply_markup=get_admin_menu_kb()
            )
            await callback.answer()
            return
        
        await callback.message.edit_text(
            f"Поточна назва тесту: \"{test.title}\"\n\n"
            f"Введіть нову назву для тесту (максимум 200 символів):"
        )
        
        # Устанавливаем состояние ожидания ввода нового названия теста
        # Для упрощения используем то же состояние, что и для создания теста
        await state.set_state(LibraryAdminStates.waiting_for_test_title)
        
        # Сохраняем ID теста и статьи в состоянии
        await state.update_data(test_id=test_id, article_id=test.article_id, is_editing=True)
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в edit_test_title: {e}")
        await callback.message.edit_text(
            "Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик редактирования порога прохождения теста
@router.callback_query(F.data.startswith("edit_test_threshold_"))
async def edit_test_threshold(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        # Извлекаем ID теста из callback_data
        test_id = int(callback.data.split("_")[3])
        
        # Получаем информацию о тесте
        test_result = await session.execute(
            select(Test).where(Test.test_id == test_id)
        )
        test = test_result.scalar_one_or_none()
        
        if not test:
            await callback.message.edit_text(
                "Тест не знайдено. Поверніться до головного меню.",
                reply_markup=get_admin_menu_kb()
            )
            await callback.answer()
            return
        
        await callback.message.edit_text(
            f"Поточний поріг проходження тесту: {test.pass_threshold}%\n\n"
            f"Введіть новий поріг проходження тесту у відсотках (від 1 до 100):"
        )
        
        # Устанавливаем состояние ожидания ввода нового порога
        # Для упрощения используем то же состояние, что и для создания теста
        await state.set_state(LibraryAdminStates.waiting_for_test_pass_threshold)
        
        # Сохраняем ID теста и статьи в состоянии
        await state.update_data(test_id=test_id, article_id=test.article_id, is_editing=True)
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в edit_test_threshold: {e}")
        await callback.message.edit_text(
            "Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик удаления теста
@router.callback_query(F.data.startswith("delete_test_"))
async def delete_test_command(callback: CallbackQuery, session: AsyncSession):
    try:
        # Извлекаем ID теста из callback_data
        test_id = int(callback.data.split("_")[2])
        
        # Получаем информацию о тесте
        test_result = await session.execute(
            select(Test).where(Test.test_id == test_id)
        )
        test = test_result.scalar_one_or_none()
        
        if not test:
            await callback.message.edit_text(
                "Тест не знайдено. Поверніться до головного меню.",
                reply_markup=get_admin_menu_kb()
            )
            await callback.answer()
            return
        
        # Определяем callback для возврата
        return_callback = f"admin_article_{test.article_id}"
        
        # Получаем количество вопросов для уведомления
        from sqlalchemy import func
        from bot.database.models import Question
        
        questions_count_result = await session.execute(
            select(func.count(Question.question_id)).where(Question.test_id == test_id)
        )
        questions_count = questions_count_result.scalar_one()
        
        await callback.message.edit_text(
            f"Ви впевнені, що хочете видалити тест \"{test.title}\"?\n\n"
            f"Увага! Буде видалено також {questions_count} питань та всі пов'язані відповіді.",
            reply_markup=await get_confirm_delete_kb("test", test_id, return_callback)
        )
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в delete_test_command: {e}")
        await callback.message.edit_text(
            "Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик подтверждения удаления теста
@router.callback_query(F.data.startswith("confirm_delete_test_"))
async def confirm_delete_test(callback: CallbackQuery, session: AsyncSession):
    try:
        # Извлекаем ID теста из callback_data
        test_id = int(callback.data.split("_")[3])
        
        # Получаем информацию о тесте перед удалением
        test_result = await session.execute(
            select(Test).where(Test.test_id == test_id)
        )
        test = test_result.scalar_one_or_none()
        
        if not test:
            await callback.message.edit_text(
                "Тест не знайдено. Поверніться до головного меню.",
                reply_markup=get_admin_menu_kb()
            )
            await callback.answer()
            return
        
        # Сохраняем данные для логирования
        test_data = {
            "id": test.test_id,
            "title": test.title,
            "article_id": test.article_id
        }
        
        article_id = test.article_id
        
        # Удаляем тест и все связанные данные
        from bot.database.operations_library import delete_test
        success = await delete_test(session, test_id)
        
        if not success:
            await callback.message.edit_text(
                f"Помилка: не вдалося видалити тест \"{test.title}\".",
                reply_markup=await get_test_management_kb(test_id, article_id)
            )
            await callback.answer()
            return
        
        # Логируем действие администратора
        log = AdminLog(
            admin_id=callback.from_user.id,
            action_type="DELETE",
            entity_type="TEST",
            entity_id=test_id,
            details=test_data
        )
        session.add(log)
        await session.commit()
        
        # Сообщаем об успешном удалении
        await callback.message.edit_text(
            f"Тест \"{test.title}\" успішно видалено!"
        )
        
        # Возвращаемся к статье
        await callback.message.answer(
            "Повернення до статті:",
            reply_markup=await get_article_actions_kb(session, article_id)
        )
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в confirm_delete_test: {e}")
        await callback.message.edit_text(
            "Виникла помилка при видаленні тесту. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик для возврата к меню администратора
@router.callback_query(F.data == "back_to_admin_menu")
async def back_to_admin_menu(callback: CallbackQuery):
    try:
        await callback.message.edit_text(
            "Ви повернулись до головного меню адміністратора.",
            reply_markup=get_admin_menu_kb()
        )
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в back_to_admin_menu: {e}")
        # В случае ошибки все равно пытаемся вернуться в админ-меню
        await callback.message.edit_text(
            "Виникла помилка. Повернення до головного меню адміністратора.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()
        
        