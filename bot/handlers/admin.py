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
            f"Відправте зображення або натисніть кнопку, щоб пропустити цей крок:",
            reply_markup=await get_image_skip_kb(article.article_id)
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

# Другие обработчики для админ-интерфейса библиотеки знаний

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
        
        # Формируем сообщение для подтверждения удаления
        message_text = f"Ви впевнені, що хочете видалити статтю \"{article.title}\"?\n\n"
        message_text += "Увага! Будуть видалені всі зображення та тести, пов'язані з цією статтею!"
        
        # Определяем callback для возврата
        return_callback = f"admin_article_{article_id}"
        
        await callback.message.edit_text(
            message_text,
            reply_markup=await get_confirm_delete_kb("article", article_id, return_callback)
        )
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в delete_article_command: {e}")
        await callback.message.edit_text(
            "Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик подтверждения удаления статьи
@router.callback_query(F.data.startswith("confirm_delete_article_"))
async def confirm_delete_article(callback: CallbackQuery, session: AsyncSession):
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
        
        # Сохраняем данные о статье для логирования
        article_data = {
            "id": article.article_id,
            "title": article.title,
            "category_id": article.category_id
        }
        
        # Сохраняем ID категории для возврата
        category_id = article.category_id
        
        # Удаляем статью и связанные данные
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
        
        # Сообщаем об успешном удалении статьи
        await callback.message.edit_text(
            f"Стаття \"{article.title}\" успішно видалена!"
        )
        
        # Получаем информацию о категории
        category = await get_category_by_id(session, category_id)
        
        if category:
            # Показываем список статей в категории
            await callback.message.answer(
                f"Повернення до списку статей в категорії \"{category.name}\":",
                reply_markup=await get_admin_articles_kb(session, category_id)
            )
        else:
            # Если категория не найдена, возвращаемся к списку категорий
            await callback.message.answer(
                "Повернення до бібліотеки знань:",
                reply_markup=await get_admin_categories_kb(session)
            )
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в confirm_delete_article: {e}")
        await callback.message.edit_text(
            "Виникла помилка при видаленні статті. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Обработчик для возврата в админ-меню
@router.callback_query(F.data == "back_to_admin_menu")
async def back_to_admin_menu(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_text(
            "Ви повернулися до адміністративного меню."
        )
        
        await callback.message.answer(
            "Виберіть опцію з меню адміністратора:",
            reply_markup=get_admin_menu_kb()
        )
        
        # Сбрасываем состояние
        await state.clear()
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в back_to_admin_menu: {e}")
        await callback.message.edit_text("Виникла помилка. Спробуйте пізніше.")
        await callback.answer()
import sys
import os
from datetime import datetime

if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, and_, or_
from sqlalchemy.orm import joinedload

from bot.database.models import User, Article, Test, Question, Answer, TestAttempt, UserAnswer
from bot.keyboards.user_kb import get_main_menu_kb
from bot.utils.logger import logger

# Создаем роутер для тестов (пользовательская часть)
router = Router()

# Определяем состояния для FSM
class UserTestStates(StatesGroup):
    answering_question = State()
    test_completed = State()


# Создаем клавиатуру для выбора теста
async def get_available_tests_kb(session: AsyncSession, user_id: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    # Получаем все тесты из базы данных
    result = await session.execute(
        select(Test, Article)
        .join(Article, Test.article_id == Article.article_id)
        .order_by(Article.title, Test.title)
    )
    tests_data = result.all()
    
    if not tests_data:
        # Если тестов нет, добавляем только кнопку возврата в главное меню
        builder.add(InlineKeyboardButton(
            text="🏠 Головне меню",
            callback_data="back_to_main_menu"
        ))
        return builder.as_markup()
    
    # Проверяем, какие тесты пользователь прошел с максимальным баллом
    completed_tests = {}
    for test, _ in tests_data:
        result = await session.execute(
            select(TestAttempt)
            .where(
                TestAttempt.user_id == user_id,
                TestAttempt.test_id == test.test_id
            )
            .order_by(TestAttempt.created_at.desc())
        )
        latest_attempt = result.scalar_one_or_none()
        
        if latest_attempt:
            completed_tests[test.test_id] = {
                'score': latest_attempt.score,
                'is_passed': latest_attempt.is_passed,
                'date': latest_attempt.created_at
            }
    
    # Добавляем кнопки для каждого теста с информацией о прохождении
    for test, article in tests_data:
        test_info = completed_tests.get(test.test_id)
        
        if test_info and test_info['score'] == 10:
            # Пройден с максимальным баллом
            button_text = f"✅ {test.title} ({article.title}) - 10/10"
        elif test_info:
            # Пройден, но не с максимальным баллом
            button_text = f"⚠️ {test.title} ({article.title}) - {test_info['score']}/10"
        else:
            # Не пройден
            button_text = f"📝 {test.title} ({article.title})"
        
        builder.add(InlineKeyboardButton(
            text=button_text,
            callback_data=f"start_user_test_{test.test_id}"
        ))
    
    # Добавляем кнопку для возврата в главное меню
    builder.add(InlineKeyboardButton(
        text="🏠 Головне меню",
        callback_data="back_to_main_menu"
    ))
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()


# Создаем клавиатуру для ответов на вопрос
async def get_user_answers_kb(session: AsyncSession, question_id: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    # Получаем список вариантов ответов для данного вопроса
    result = await session.execute(
        select(Answer)
        .where(Answer.question_id == question_id)
        .order_by(Answer.position)
    )
    answers = result.scalars().all()
    
    # Добавляем кнопки для каждого варианта ответа
    for answer in answers:
        builder.add(InlineKeyboardButton(
            text=answer.answer_text,
            callback_data=f"user_answer_{answer.answer_id}"
        ))
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()


# Клавиатура после завершения теста
async def get_test_completion_kb(test_id: int, max_score: bool = False):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопку для повторного прохождения, если не набрано максимальное количество баллов
    if not max_score:
        builder.add(InlineKeyboardButton(
            text="🔄 Пройти тест ще раз",
            callback_data=f"restart_test_{test_id}"
        ))
        
        builder.add(InlineKeyboardButton(
            text="✅ Завершити тест",
            callback_data="complete_test"
        ))
    
    # Добавляем кнопку для просмотра статьи
    builder.add(InlineKeyboardButton(
        text="📚 Переглянути статтю",
        callback_data=f"view_article_for_test_{test_id}"
    ))
    
    # Добавляем кнопку для возврата к списку тестов
    builder.add(InlineKeyboardButton(
        text="📋 До списку тестів",
        callback_data="back_to_tests_list"
    ))
    
    # Добавляем кнопку для возврата в главное меню
    builder.add(InlineKeyboardButton(
        text="🏠 Головне меню",
        callback_data="back_to_main_menu"
    ))
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()


# Обработчик команды "Пройти тест"
@router.message(F.text == "📝 Пройти тест")
async def start_tests_command(message: Message, session: AsyncSession):
    """Обработчик команды для запуска прохождения тестов"""
    await message.answer(
        "Виберіть тест для проходження:",
        reply_markup=await get_available_tests_kb(session, message.from_user.id)
    )


# Обработчик выбора теста
@router.callback_query(F.data.startswith("start_user_test_"))
async def start_user_test(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик начала прохождения теста пользователем"""
    # Извлекаем ID теста из callback_data
    test_id = int(callback.data.split("_")[3])
    
    # Получаем информацию о тесте
    result = await session.execute(
        select(Test)
        .options(joinedload(Test.questions))
        .where(Test.test_id == test_id)
    )
    test = result.scalar_one_or_none()
    
    if not test:
        await callback.message.edit_text(
            "Тест не знайдено. Виберіть інший тест:",
            reply_markup=await get_available_tests_kb(session, callback.from_user.id)
        )
        await callback.answer()
        return
    
    # Получаем информацию о статье
    result = await session.execute(
        select(Article).where(Article.article_id == test.article_id)
    )
    article = result.scalar_one_or_none()
    
    # Проверяем, есть ли у пользователя уже пройденный тест с максимальным баллом
    user_id = callback.from_user.id
    result = await session.execute(
        select(TestAttempt)
        .where(
            TestAttempt.user_id == user_id,
            TestAttempt.test_id == test_id,
            TestAttempt.score == 10
        )
        .order_by(TestAttempt.created_at.desc())
    )
    max_score_attempt = result.scalar_one_or_none()
    
    if max_score_attempt:
        # У пользователя уже есть попытка с максимальным баллом
        await callback.message.edit_text(
            f"Ви вже пройшли тест \"{test.title}\" з максимальним балом (10)!\n\n"
            f"Бажаєте переглянути статтю чи вибрати інший тест?",
            reply_markup=await get_test_completion_kb(test_id, max_score=True)
        )
        await callback.answer()
        return
    
    # Получаем предыдущую попытку пользователя (если есть)
    result = await session.execute(
        select(TestAttempt)
        .where(
            TestAttempt.user_id == user_id,
            TestAttempt.test_id == test_id
        )
        .order_by(TestAttempt.created_at.desc())
    )
    previous_attempt = result.scalar_one_or_none()
    
    previous_score = previous_attempt.score if previous_attempt else 0
    
    # Получаем вопросы для теста
    questions = test.questions if hasattr(test, 'questions') else []
    
    if not questions:
        await callback.message.edit_text(
            "У цьому тесті немає питань. Виберіть інший тест:",
            reply_markup=await get_available_tests_kb(session, callback.from_user.id)
        )
        await callback.answer()
        return
    
    # Создаем новую попытку прохождения теста
    new_attempt = TestAttempt(
        user_id=user_id,
        test_id=test_id,
        score=10,  # Начинаем с максимального балла и вычитаем за ошибки
        is_passed=False  # Пока не прошли до конца
    )
    session.add(new_attempt)
    await session.commit()
    await session.refresh(new_attempt)
    
    # Сохраняем данные теста и текущего вопроса в состоянии
    await state.update_data(
        test_id=test_id,
        attempt_id=new_attempt.attempt_id,
        questions_ids=[q.question_id for q in questions],
        current_question_index=0,
        errors_count=0,
        score=10,
        article_id=test.article_id
    )
    
    # Отображаем информацию о тесте перед началом
    await callback.message.edit_text(
        f"📝 <b>Тест:</b> {test.title}\n"
        f"📄 <b>Стаття:</b> {article.title if article else 'Невідома'}\n"
        f"❓ <b>Кількість питань:</b> {len(questions)}\n"
        f"🏆 <b>Прохідний бал:</b> {test.pass_threshold}%\n"
        f"👤 <b>Ваш попередній результат:</b> {previous_score}/10\n\n"
        f"<i>Починаємо тестування. Кожне неправильна відповідь знімає 2 бали. "
        f"Після 5 помилок тест буде перервано.</i>",
        parse_mode="HTML"
    )
    
    # Получаем первый вопрос
    first_question = questions[0]
    
    # Показываем первый вопрос
    await callback.message.answer(
        f"Питання 1 з {len(questions)}:\n\n{first_question.question_text}",
        reply_markup=await get_user_answers_kb(session, first_question.question_id)
    )
    
    # Переходим в состояние ответа на вопросы
    await state.set_state(UserTestStates.answering_question)
    
    await callback.answer()


# Обработчик выбора ответа на вопрос
@router.callback_query(UserTestStates.answering_question, F.data.startswith("user_answer_"))
async def process_user_answer(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора ответа пользователем"""
    # Извлекаем ID ответа из callback_data
    answer_id = int(callback.data.split("_")[2])
    
    # Получаем данные теста из состояния
    data = await state.get_data()
    test_id = data.get("test_id")
    attempt_id = data.get("attempt_id")
    current_question_index = data.get("current_question_index", 0)
    questions_ids = data.get("questions_ids", [])
    errors_count = data.get("errors_count", 0)
    score = data.get("score", 10)
    article_id = data.get("article_id")
    
    if not test_id or not attempt_id or not questions_ids:
        await callback.message.edit_text(
            "Помилка: відсутні дані про тест. Почніть проходження тесту заново.",
            reply_markup=await get_available_tests_kb(session, callback.from_user.id)
        )
        await state.clear()
        await callback.answer()
        return
    
    # Получаем информацию о текущем вопросе
    current_question_id = questions_ids[current_question_index]
    result = await session.execute(
        select(Question).where(Question.question_id == current_question_id)
    )
    question = result.scalar_one_or_none()
    
    if not question:
        await callback.message.edit_text(
            "Помилка: питання не знайдено. Тест буде перервано.",
            reply_markup=get_main_menu_kb()
        )
        await state.clear()
        await callback.answer()
        return
    
    # Получаем информацию о выбранном ответе
    result = await session.execute(
        select(Answer).where(Answer.answer_id == answer_id)
    )
    answer = result.scalar_one_or_none()
    
    if not answer:
        await callback.answer("Помилка: відповідь не знайдена.")
        return
    
    # Сохраняем ответ пользователя
    user_answer = UserAnswer(
        attempt_id=attempt_id,
        question_id=question.question_id,
        answer_id=answer.answer_id,
        is_correct=answer.is_correct,
        created_at=datetime.now()
    )
    session.add(user_answer)
    await session.commit()
    
    # Проверяем правильность ответа
    if answer.is_correct:
        # Правильный ответ
        await callback.message.edit_text(
            f"{callback.message.text}\n\n✅ Супер! відповідь правильна."
        )
    else:
        # Неправильный ответ
        errors_count += 1
        score -= 2  # Вычитаем 2 балла за ошибку
        if score < 0:
            score = 0
            
        await callback.message.edit_text(
            f"{callback.message.text}\n\n❌ Здається, щось пропустили в матеріалі.."
        )
        
        # Обновляем данные в состоянии
        await state.update_data(errors_count=errors_count, score=score)
        
        # Проверяем, не превышено ли максимальное количество ошибок (5)
        if errors_count >= 5:
            # Обновляем данные попытки в БД
            result = await session.execute(
                select(TestAttempt).where(TestAttempt.attempt_id == attempt_id)
            )
            attempt = result.scalar_one_or_none()
            
            if attempt:
                attempt.score = score
                attempt.is_passed = False
                await session.commit()
            
            # Завершаем тест из-за большого количества ошибок
            await callback.message.answer(
                "⚠️ Ви допустили 5 помилок. Будь ласка, перечитайте матеріал і спробуйте ще раз.",
                reply_markup=await get_test_completion_kb(test_id)
            )
            
            # Выходим из состояния ответа на вопросы
            await state.clear()
            await callback.answer()
            return
    
    # Проверяем, есть ли еще вопросы
    current_question_index += 1
    
    if current_question_index < len(questions_ids):
        # Если есть еще вопросы, показываем следующий
        next_question_id = questions_ids[current_question_index]
        
        # Получаем информацию о следующем вопросе
        result = await session.execute(
            select(Question).where(Question.question_id == next_question_id)
        )
        next_question = result.scalar_one_or_none()
        
        if not next_question:
            await callback.message.answer(
                "Помилка: питання не знайдено. Тест буде перервано.",
                reply_markup=get_main_menu_kb()
            )
            await state.clear()
            await callback.answer()
            return
        
        # Обновляем индекс текущего вопроса в состоянии
        await state.update_data(current_question_index=current_question_index)
        
        # Показываем следующий вопрос
        await callback.message.answer(
            f"Питання {current_question_index + 1} з {len(questions_ids)}:\n\n{next_question.question_text}",
            reply_markup=await get_user_answers_kb(session, next_question.question_id)
        )
    else:
        # Если вопросов больше нет, завершаем тест
        # Получаем информацию о тесте
        result = await session.execute(
            select(Test).where(Test.test_id == test_id)
        )
        test = result.scalar_one_or_none()
        
        if not test:
            await callback.message.answer(
                "Помилка: тест не знайдено.",
                reply_markup=get_main_menu_kb()
            )
            await state.clear()
            await callback.answer()
            return
        
        # Обновляем данные попытки в БД
        result = await session.execute(
            select(TestAttempt).where(TestAttempt.attempt_id == attempt_id)
        )
        attempt = result.scalar_one_or_none()
        
        if attempt:
            # Определяем, пройден ли тест
            pass_threshold = test.pass_threshold
            max_score = 10
            pass_score = max_score * (pass_threshold / 100)
            is_passed = score >= pass_score
            
            attempt.score = score
            attempt.is_passed = is_passed
            await session.commit()
        
        # Формируем сообщение о результате
        if score == 10:
            result_message = f"🏆 Тест завершено! Ви отримали {score} балів. Чудова робота! Ми пишаємось тобою!"
        elif score >= 2 and is_passed:
            result_message = f"🏆 Тест завершено! Ви отримали {score} балів. Тест пройдено"
        else:
            result_message = f"⚠️ Ви не набрали достатньо балів для проходження тесту. " \
                           f"Ви можете ще раз переглянути матеріал і спробувати знову. 🔄"
        
        # Показываем результат теста
        await callback.message.answer(result_message)
        
        # Предлагаем варианты дальнейших действий
        max_score_achieved = score == 10
        await callback.message.answer(
            "Що бажаєте зробити далі?",
            reply_markup=await get_test_completion_kb(test_id, max_score=max_score_achieved)
        )
        
        # Переходим в состояние завершения теста
        await state.set_state(UserTestStates.test_completed)
    
    await callback.answer()


# Обработчик для перезапуска теста
@router.callback_query(F.data.startswith("restart_test_"))
async def restart_test(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик перезапуска теста"""
    # Сбрасываем состояние
    await state.clear()
    
    # Перезапускаем тест
    await start_user_test(callback, state, session)


# Обработчик для завершения теста
@router.callback_query(F.data == "complete_test")
async def complete_test(callback: CallbackQuery, state: FSMContext):
    """Обработчик завершения теста"""
    await callback.message.edit_text(
        "Тест завершено. Дякуємо за участь!"
    )
    
    await callback.message.answer(
        "Виберіть опцію з меню нижче:",
        reply_markup=get_main_menu_kb()
    )
    
    await state.clear()
    await callback.answer()


# Обработчик для возврата к списку тестов
@router.callback_query(F.data == "back_to_tests_list")
async def back_to_tests_list(callback: CallbackQuery, session: AsyncSession):
    """Обработчик возврата к списку тестов"""
    await callback.message.edit_text(
        "Виберіть тест для проходження:",
        reply_markup=await get_available_tests_kb(session, callback.from_user.id)
    )
    await callback.answer()


# Обработчик для просмотра статьи по тесту
@router.callback_query(F.data.startswith("view_article_for_test_"))
async def view_article_for_test(callback: CallbackQuery, session: AsyncSession):
    """Обработчик просмотра статьи, связанной с тестом"""
    # Извлекаем ID теста из callback_data
    test_id = int(callback.data.split("_")[4])
    
    # Получаем информацию о тесте
    result = await session.execute(
        select(Test).where(Test.test_id == test_id)
    )
    test = result.scalar_one_or_none()
    
    if not test:
        await callback.message.edit_text(
            "Тест не знайдено.",
            reply_markup=await get_available_tests_kb(session, callback.from_user.id)
        )
        await callback.answer()
        return
    
    # Получаем информацию о статье
    result = await session.execute(
        select(Article).where(Article.article_id == test.article_id)
    )
    article = result.scalar_one_or_none()
    
    if not article:
        await callback.message.edit_text(
            "Статтю не знайдено.",
            reply_markup=await get_available_tests_kb(session, callback.from_user.id)
        )
        await callback.answer()
        return
    
    # Формируем клавиатуру для возврата
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="📝 Пройти тест",
        callback_data=f"start_user_test_{test_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="📋 До списку тестів",
        callback_data="back_to_tests_list"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🏠 Головне меню",
        callback_data="back_to_main_menu"
    ))
    
    builder.adjust(1)
    
    # Отображаем статью
    await callback.message.edit_text(
        f"<b>{article.title}</b>\n\n{article.content}",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    
    # Получаем изображения для статьи
    result = await session.execute(
        select(ArticleImage)
        .where(ArticleImage.article_id == article.article_id)
        .order_by(ArticleImage.position)
    )
    images = result.scalars().all()
    
    # Отправляем изображения, если они есть
    for image in images:
        await callback.message.answer_photo(
            photo=image.file_id,
            caption=f"Ілюстрація до статті '{article.title}'"
        )
    
    await callback.answer()


# Обработчик для возврата в главное меню
@router.callback_query(F.data == "back_to_main_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    """Обработчик возврата в главное меню"""
    await callback.message.edit_text(
        "Ви повернулись до головного меню."
    )
    
    await callback.message.answer(
        "Виберіть опцію з меню нижче:",
        reply_markup=get_main_menu_kb()
    )
    
    await state.clear()
    await callback.answer()