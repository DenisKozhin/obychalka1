import sys
import os

if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from bot.database.models import Category, Article, ArticleImage, User
from bot.keyboards.user_kb import get_main_menu_kb
from bot.keyboards.admin_kb import get_admin_menu_kb
from bot.utils.logger import logger

# Создаем роутер для библиотеки знаний
router = Router()

# Определяем состояния для FSM
class ArticleStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_article = State()
    waiting_for_title = State()
    waiting_for_content = State()
    waiting_for_images = State()
    confirm_publication = State()


# Создаем клавиатуру для категорий
async def get_categories_kb(session: AsyncSession, parent_id=None, level=1):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    # Получаем список категорий из БД
    if parent_id is None:
        result = await session.execute(
            select(Category).where(Category.level == level)
        )
    else:
        result = await session.execute(
            select(Category).where(
                Category.parent_id == parent_id,
                Category.level == level
            )
        )
    
    categories = result.scalars().all()
    
    # Если категорий нет, создаем базовые категории для первого уровня
    if not categories and level == 1 and parent_id is None:
        default_categories = [
            {"name": "Продовольчі товари", "parent_id": None, "level": 1},
            {"name": "Непродовольчі товари", "parent_id": None, "level": 1}
        ]
        
        for cat_data in default_categories:
            category = Category(**cat_data)
            session.add(category)
        
        await session.commit()
        
        # Получаем категории снова
        result = await session.execute(
            select(Category).where(Category.level == level)
        )
        categories = result.scalars().all()
    
    # Добавляем кнопки для каждой категории
    for category in categories:
        builder.add(InlineKeyboardButton(
            text=category.name,
            callback_data=f"category_{category.category_id}_{level}"
        ))
    
    # Если мы не на первом уровне, добавляем кнопку "Назад"
    if level > 1 or parent_id is not None:
        # Получаем родительскую категорию, чтобы найти её родителя для кнопки "Назад"
        if parent_id is not None:
            parent_result = await session.execute(
                select(Category).where(Category.category_id == parent_id)
            )
            parent = parent_result.scalar_one_or_none()
            
            back_level = level - 1
            back_parent_id = parent.parent_id if parent else None
            
            builder.add(InlineKeyboardButton(
                text="🔙 Назад",
                callback_data=f"back_to_categories_{back_level}_{back_parent_id or 0}"
            ))
    
    # Добавляем кнопку для возврата в главное меню
    builder.add(InlineKeyboardButton(
        text="🏠 Головне меню",
        callback_data="back_to_main_menu"
    ))
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()


# Создаем клавиатуру для статей категории
async def get_articles_kb(session: AsyncSession, category_id):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    # Получаем список статей для выбранной категории
    result = await session.execute(
        select(Article).where(Article.category_id == category_id)
    )
    articles = result.scalars().all()
    
    # Получаем информацию о категории
    category_result = await session.execute(
        select(Category).where(Category.category_id == category_id)
    )
    category = category_result.scalar_one_or_none()
    
    # Добавляем кнопки для каждой статьи
    for article in articles:
        builder.add(InlineKeyboardButton(
            text=article.title,
            callback_data=f"article_{article.article_id}"
        ))
    
    # Добавляем кнопку "Назад" к категориям
    level = category.level if category else 1
    parent_id = category.parent_id if category else None
    
    builder.add(InlineKeyboardButton(
        text="🔙 Назад до категорій",
        callback_data=f"back_to_categories_{level}_{parent_id or 0}"
    ))
    
    # Добавляем кнопку для возврата в главное меню
    builder.add(InlineKeyboardButton(
        text="🏠 Головне меню",
        callback_data="back_to_main_menu"
    ))
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()


# Обработчик команды "Библиотека знаний"
@router.message(F.text == "📚 Бібліотека знань")
async def library_command(message: Message, session: AsyncSession):
    await message.answer(
        "Ласкаво просимо до бібліотеки знань! Виберіть категорію:",
        reply_markup=await get_categories_kb(session)
    )


# Обработчик выбора категории
@router.callback_query(F.data.startswith("category_"))
async def process_category_selection(callback: CallbackQuery, session: AsyncSession):
    # Извлекаем ID категории и уровень из callback_data
    parts = callback.data.split("_")
    category_id = int(parts[1])
    level = int(parts[2])
    
    # Получаем информацию о выбранной категории
    result = await session.execute(
        select(Category).where(Category.category_id == category_id)
    )
    category = result.scalar_one_or_none()
    
    if not category:
        await callback.message.edit_text(
            "Категорія не знайдена.",
            reply_markup=await get_categories_kb(session)
        )
        await callback.answer()
        return
    
    # Проверяем, есть ли подкатегории для данной категории
    subcategories_result = await session.execute(
        select(Category).where(Category.parent_id == category_id)
    )
    subcategories = subcategories_result.scalars().all()
    
    if subcategories:
        # Если есть подкатегории, показываем их
        next_level = level + 1
        await callback.message.edit_text(
            f"Категорія: {category.name}\n\nВиберіть підкатегорію:",
            reply_markup=await get_categories_kb(session, category_id, next_level)
        )
    else:
        # Если нет подкатегорий, показываем статьи данной категории
        await callback.message.edit_text(
            f"Категорія: {category.name}\n\nВиберіть статтю:",
            reply_markup=await get_articles_kb(session, category_id)
        )
    
    await callback.answer()


# Обработчик для возврата к категориям
@router.callback_query(F.data.startswith("back_to_categories_"))
async def back_to_categories(callback: CallbackQuery, session: AsyncSession):
    # Извлекаем уровень и ID родительской категории из callback_data
    parts = callback.data.split("_")
    level = int(parts[3])
    parent_id = int(parts[4]) if parts[4] != "0" else None
    
    await callback.message.edit_text(
        "Виберіть категорію:",
        reply_markup=await get_categories_kb(session, parent_id, level)
    )
    await callback.answer()


# Обработчик для возврата в главное меню
@router.callback_query(F.data == "back_to_main_menu")
async def back_to_main_menu(callback: CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    
    # Проверяем, является ли пользователь администратором
    result = await session.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if user and user.is_admin:
        await callback.message.edit_text(
            "Ви повернулись до головного меню.",
        )
        await callback.message.answer(
            "Виберіть опцію з адміністративного меню:",
            reply_markup=get_admin_menu_kb()
        )
    else:
        await callback.message.edit_text(
            "Ви повернулись до головного меню.",
        )
        await callback.message.answer(
            "Виберіть опцію з меню:",
            reply_markup=get_main_menu_kb()
        )
    
    await callback.answer()


# Обработчик выбора статьи
@router.callback_query(F.data.startswith("article_"))
async def show_article(callback: CallbackQuery, session: AsyncSession):
    # Извлекаем ID статьи из callback_data
    article_id = int(callback.data.split("_")[1])
    
    # Получаем информацию о статье
    result = await session.execute(
        select(Article).where(Article.article_id == article_id)
    )
    article = result.scalar_one_or_none()
    
    if not article:
        await callback.message.edit_text(
            "Стаття не знайдена.",
            reply_markup=await get_categories_kb(session)
        )
        await callback.answer()
        return
    
    # Формируем сообщение со статьей
    article_text = f"<b>{article.title}</b>\n\n{article.content}"
    
    # Отправляем текст статьи
    await callback.message.edit_text(
        article_text,
        parse_mode="HTML"
    )
    
    # Получаем изображения для статьи
    images_result = await session.execute(
        select(ArticleImage).where(ArticleImage.article_id == article_id).order_by(ArticleImage.position)
    )
    images = images_result.scalars().all()
    
    # Отправляем изображения, если они есть
    for image in images:
        await callback.message.answer_photo(
            photo=image.file_id,
            caption=f"Ілюстрація до статті '{article.title}'"
        )
    
    # Проверяем, есть ли тест для данной статьи
    from bot.database.models import Test
    test_result = await session.execute(
        select(Test).where(Test.article_id == article_id)
    )
    test = test_result.scalar_one_or_none()
    
    # Создаем клавиатуру для действий со статьей
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    # Если есть тест, добавляем кнопку для его прохождения
    if test:
        builder.add(InlineKeyboardButton(
            text="📝 Пройти тест",
            callback_data=f"start_test_{test.test_id}"
        ))
    
    # Добавляем кнопку для возврата к статьям категории
    builder.add(InlineKeyboardButton(
        text="🔙 Назад до статей",
        callback_data=f"back_to_articles_{article.category_id}"
    ))
    
    # Добавляем кнопку для возврата в главное меню
    builder.add(InlineKeyboardButton(
        text="🏠 Головне меню",
        callback_data="back_to_main_menu"
    ))
    
    # Отправляем клавиатуру
    await callback.message.answer(
        "Оберіть дію:",
        reply_markup=builder.as_markup()
    )
    
    await callback.answer()


# Обработчик для возврата к статьям категории
@router.callback_query(F.data.startswith("back_to_articles_"))
async def back_to_articles(callback: CallbackQuery, session: AsyncSession):
    # Извлекаем ID категории из callback_data
    category_id = int(callback.data.split("_")[3])
    
    # Получаем информацию о категории
    result = await session.execute(
        select(Category).where(Category.category_id == category_id)
    )
    category = result.scalar_one_or_none()
    
    if not category:
        await callback.message.edit_text(
            "Категорія не знайдена.",
            reply_markup=await get_categories_kb(session)
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        f"Категорія: {category.name}\n\nВиберіть статтю:",
        reply_markup=await get_articles_kb(session, category_id)
    )
    await callback.answer()


# Экспорт роутера
if __name__ == "__main__":
    print("Модуль library.py успешно загружен")
    print("router определен:", router is not None)
    