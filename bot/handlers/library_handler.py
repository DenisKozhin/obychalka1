# bot/handlers/library_handler.py
"""
Consolidated knowledge library handler that combines both admin and user functionality.
This file replaces the separate admin.py and library.py handlers to resolve conflicts.
"""

import sys
import os
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from bot.database.models import Category, Article, ArticleImage, User, Test, AdminLog
from bot.keyboards.admin_kb import get_admin_menu_kb
from bot.keyboards.user_kb import get_main_menu_kb
from bot.utils.logger import logger
from bot.database.operations_library import (
    get_categories, get_category_by_id, create_category, update_category, delete_category,
    get_articles_by_category, get_article_by_id, create_article, update_article, delete_article,
    get_article_images, add_article_image, delete_article_image
)


    
# Create one consolidated router for the library
router = Router()

# Define FSM states for library operations
class LibraryStates(StatesGroup):
    # Admin states
    waiting_for_category_name = State()
    waiting_for_subcategory_name = State()
    waiting_for_edit_category_name = State()
    waiting_for_article_title = State()
    waiting_for_article_content = State()
    waiting_for_article_images = State()
    waiting_for_edit_article_title = State()
    waiting_for_edit_article_content = State()
    waiting_for_select_city = State()
    waiting_for_select_store = State()
    waiting_for_select_user = State()
    waiting_for_confirm_send = State()
    
    # User states 
    browsing_category = State()
    reading_article = State()

# Helper function to check if user is admin
async def is_admin(user_id: int, session: AsyncSession) -> bool:
    """Check if user is an admin"""
    result = await session.execute(
        select(User).where(User.user_id == user_id, User.is_admin == True)
    )
    return result.scalar_one_or_none() is not None

# ADMIN HANDLERS
# --------------

# Admin library entry point
@router.callback_query(F.data == "admin_articles")
async def admin_articles_command(callback: CallbackQuery, session: AsyncSession):
    """Entry point for admin library management"""
    # First check if user is admin
    if not await is_admin(callback.from_user.id, session):
        await callback.answer("This feature is only available for administrators.", show_alert=True)
        return
        
    try:
        await callback.message.edit_text(
            "Управління бібліотекою знань. Виберіть категорію:",
            reply_markup=await get_admin_categories_kb(session)
        )
        
        # Log admin action
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
        logger.error(f"Error in admin_articles_command: {e}")
        await callback.message.edit_text(
            "Виникла помилка при завантаженні бібліотеки. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Admin category selection handler
@router.callback_query(F.data.startswith("admin_category_"))
async def admin_category_selection(callback: CallbackQuery, session: AsyncSession):
    """Admin handler for selecting a category"""
    # First check if user is admin
    if not await is_admin(callback.from_user.id, session):
        await callback.answer("This feature is only available for administrators.", show_alert=True)
        return
        
    try:
        # Extract category ID and level from callback data
        parts = callback.data.split("_")
        category_id = int(parts[2])
        level = int(parts[3])
        
        # Get category information
        category = await get_category_by_id(session, category_id)
        
        if not category:
            await callback.message.edit_text(
                "Категорія не знайдена. Поверніться до головного меню.",
                reply_markup=await get_admin_categories_kb(session)
            )
            await callback.answer()
            return
        
        # Check category level
        if category.level < 3:
            # If this is level 1 or 2 category, show subcategories
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
            # If this is level 3 category (product group), show actions with category
            await callback.message.edit_text(
                f"Група товарів: {category.name}\n\n"
                f"Виберіть дію:",
                reply_markup=await get_category_actions_kb(session, category_id)
            )
        
        # Log admin action
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
        logger.error(f"Error in admin_category_selection: {e}")
        await callback.message.edit_text(
            "Виникла помилка при завантаженні категорії. Спробуйте пізніше.",
            reply_markup=get_admin_menu_kb()
        )
        await callback.answer()

# Continue with other admin handlers...
# [Additional admin handler implementations would go here]

# USER HANDLERS
# -------------

# User library entry point
@router.message(F.text == "📚 Бібліотека знань")
async def user_library_command(message: Message, session: AsyncSession):
    """Entry point for user to browse the knowledge library"""
    try:
        # Get root categories (level 1)
        categories = await get_categories(session, parent_id=None, level=1)
        
        if not categories:
            await message.answer(
                "Бібліотека знань поки порожня. Зверніться до адміністратора."
            )
            return
        
        from bot.keyboards.library_kb import get_categories_kb
        
        await message.answer(
            "Ласкаво просимо до бібліотеки знань! Виберіть категорію:",
            reply_markup=await get_categories_kb(categories)
        )
    except Exception as e:
        logger.error(f"Error in user_library_command: {e}")
        await message.answer(
            "Виникла помилка при завантаженні бібліотеки. Спробуйте пізніше.",
            reply_markup=get_main_menu_kb()
        )

# User category selection handler
@router.callback_query(F.data.startswith("category_"))
async def user_category_selection(callback: CallbackQuery, session: AsyncSession):
    """User handler for selecting a category"""
    try:
        # Extract category ID from callback data
        parts = callback.data.split("_")
        category_id = int(parts[1])
        
        # Get category information
        category = await get_category_by_id(session, category_id)
        
        if not category:
            await callback.message.edit_text(
                "Категорія не знайдена. Поверніться до головного меню.",
                reply_markup=get_main_menu_kb()
            )
            await callback.answer()
            return
        
        # Check category level
        if category.level < 3:
            # If this is level 1 or 2 category, show subcategories
            subcategories = await get_categories(session, parent_id=category_id)
            
            from bot.keyboards.library_kb import get_categories_kb
            
            if not subcategories:
                await callback.message.edit_text(
                    f"Категорія: {category.name}\n\n"
                    f"У цій категорії немає підкатегорій.",
                    reply_markup=await get_categories_kb([], include_back=True)
                )
            else:
                await callback.message.edit_text(
                    f"Категорія: {category.name}\n\n"
                    f"Виберіть підкатегорію:",
                    reply_markup=await get_categories_kb(subcategories, include_back=True)
                )
        else:
            # If this is level 3 category (product group), show articles
            articles = await get_articles_by_category(session, category_id)
            
            from bot.keyboards.library_kb import get_articles_kb
            
            if not articles:
                await callback.message.edit_text(
                    f"Група товарів: {category.name}\n\n"
                    f"У цій категорії немає статей.",
                    reply_markup=await get_categories_kb([], include_back=True)
                )
            else:
                await callback.message.edit_text(
                    f"Статті в групі \"{category.name}\":",
                    reply_markup=await get_articles_kb(articles, category_id)
                )
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in user_category_selection: {e}")
        await callback.message.edit_text(
            "Виникла помилка при завантаженні категорії. Спробуйте пізніше.",
            reply_markup=get_main_menu_kb()
        )
        await callback.answer()

# Article view handler
@router.callback_query(F.data.startswith("article_"))
async def user_article_view(callback: CallbackQuery, session: AsyncSession):
    """User handler for viewing an article"""
    try:
        # Extract article ID from callback data
        article_id = int(callback.data.split("_")[1])
        
        # Get article information
        article = await get_article_by_id(session, article_id)
        
        if not article:
            await callback.message.edit_text(
                "Стаття не знайдена. Поверніться до головного меню.",
                reply_markup=get_main_menu_kb()
            )
            await callback.answer()
            return
        
        # Get category information
        category = await get_category_by_id(session, article.category_id)
        
        # Check if there's a test for this article
        result = await session.execute(
            select(Test).where(Test.article_id == article_id)
        )
        test = result.scalar_one_or_none()
        
        from bot.keyboards.library_kb import get_article_navigation_kb
        
        # Display article text
        await callback.message.edit_text(
            f"<b>{article.title}</b>\n\n{article.content}",
            parse_mode="HTML",
            reply_markup=await get_article_navigation_kb(
                article_id, 
                test_id=test.test_id if test else None,
                category_id=article.category_id
            )
        )
        
        # Get article images
        images = await get_article_images(session, article_id)
        
        # Send images if any
        for image in images:
            await callback.message.answer_photo(
                photo=image.file_id,
                caption=f"Зображення до статті \"{article.title}\""
            )
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in user_article_view: {e}")
        await callback.message.edit_text(
            "Виникла помилка при завантаженні статті. Спробуйте пізніше.",
            reply_markup=get_main_menu_kb()
        )
        await callback.answer()

# Continue with other user handlers...
# [Additional user handler implementations would go here]

# COMMON HANDLERS
# --------------

# Back to main menu handler
@router.callback_query(F.data == "back_to_main_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    """Handler for returning to main menu"""
    try:
        # Check if user is admin
        session = callback.bot.get('db_session')
        is_user_admin = await is_admin(callback.from_user.id, session) if session else False
        
        # Clear any active state
        await state.clear()
        
        await callback.message.edit_text(
            "Ви повернулись до головного меню."
        )
        
        # Show appropriate menu based on user role
        if is_user_admin:
            await callback.message.answer(
                "Виберіть опцію з меню адміністратора:",
                reply_markup=get_admin_menu_kb()
            )
        else:
            await callback.message.answer(
                "Виберіть опцію з меню:",
                reply_markup=get_main_menu_kb()
            )
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in back_to_main_menu: {e}")
        await callback.message.edit_text(
            "Виникла помилка. Повернення до головного меню."
        )
        await callback.message.answer(
            "Виберіть опцію з меню:",
            reply_markup=get_main_menu_kb()
        )
        await callback.answer()

# Export the router for registration with the dispatcher
# This way we have a single router for all library functionality
