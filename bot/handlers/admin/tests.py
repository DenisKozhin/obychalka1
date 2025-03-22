import sys
import os
from typing import List, Dict, Any, Optional
import json

# Для запуска файла напрямую
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from bot.database.models import Article, Test, Question, Answer, User
from bot.utils.logger import logger
from bot.keyboards.admin_kb import get_admin_menu_kb

# Импортируем функции для работы с тестами
from bot.database.operations_library import (
    get_test_by_id, get_tests_by_article, create_test, update_test, delete_test,
    get_questions_by_test, create_question, update_question, delete_question,
    create_answer, update_answer, delete_answer
)

# Создаем класс для хранения состояний FSM (Finite State Machine)
class TestAdminStates(StatesGroup):
    # Состояния для работы с тестами
    waiting_for_test_title = State()
    waiting_for_pass_threshold = State()
    
    # Состояния для работы с вопросами
    waiting_for_question_text = State()
    waiting_for_question_points = State()
    waiting_for_edit_question = State()
    
    # Состояния для работы с ответами
    waiting_for_answer_text = State()
    waiting_for_answer_correct = State()
    waiting_for_another_answer = State()
    waiting_for_edit_answer = State()

# Создаем роутер для управления тестами
router = Router()

# Создание клавиатуры для управления тестами
def get_test_management_kb():
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    buttons = [
        InlineKeyboardButton(text="➕ Создать тест", callback_data="create_test"),
        InlineKeyboardButton(text="📋 Список тестов", callback_data="list_tests"),
        InlineKeyboardButton(text="🔙 Вернуться в меню администратора", callback_data="back_to_admin_menu")
    ]
    
    for button in buttons:
        builder.add(button)
    
    # Размещаем по одной кнопке в строку
    builder.adjust(1)
    
    return builder.as_markup()

# Клавиатура для теста
def get_test_actions_kb(test_id: int, article_id: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    buttons = [
        InlineKeyboardButton(text="📝 Редактировать тест", callback_data=f"edit_test_{test_id}"),
        InlineKeyboardButton(text="❓ Управление вопросами", callback_data=f"manage_questions_{test_id}"),
        InlineKeyboardButton(text="❌ Удалить тест", callback_data=f"delete_test_{test_id}"),
        InlineKeyboardButton(text="🔙 К списку тестов", callback_data=f"tests_for_article_{article_id}")
    ]
    
    for button in buttons:
        builder.add(button)
    
    # Размещаем по одной кнопке в строку
    builder.adjust(1)
    
    return builder.as_markup()

# Клавиатура для списка вопросов
def get_questions_list_kb(test_id: int, questions: List[Question]):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    # Кнопки для каждого вопроса
    for question in questions:
        builder.add(InlineKeyboardButton(
            text=f"❓ {question.question_text[:30]}...",
            callback_data=f"question_{question.question_id}"
        ))
    
    # Добавляем кнопки действий
    builder.add(InlineKeyboardButton(
        text="➕ Добавить вопрос",
        callback_data=f"add_question_{test_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 Назад к тесту",
        callback_data=f"test_details_{test_id}"
    ))
    
    # Размещаем по одной кнопке в строку
    builder.adjust(1)
    
    return builder.as_markup()

# Клавиатура для действий с вопросом
def get_question_actions_kb(question_id: int, test_id: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    buttons = [
        InlineKeyboardButton(text="📝 Редактировать вопрос", callback_data=f"edit_question_{question_id}"),
        InlineKeyboardButton(text="➕ Добавить ответ", callback_data=f"add_answer_{question_id}"),
        InlineKeyboardButton(text="👁 Просмотр ответов", callback_data=f"view_answers_{question_id}"),
        InlineKeyboardButton(text="❌ Удалить вопрос", callback_data=f"delete_question_{question_id}"),
        InlineKeyboardButton(text="🔙 К списку вопросов", callback_data=f"manage_questions_{test_id}")
    ]
    
    for button in buttons:
        builder.add(button)
    
    # Размещаем по одной кнопке в строку
    builder.adjust(1)
    
    return builder.as_markup()

# Клавиатура для ответов
def get_answers_list_kb(answers: List[Answer], question_id: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    # Сортируем ответы по позиции
    sorted_answers = sorted(answers, key=lambda x: x.position)
    
    # Кнопки для каждого ответа
    for answer in sorted_answers:
        prefix = "✅" if answer.is_correct else "❌"
        builder.add(InlineKeyboardButton(
            text=f"{prefix} {answer.answer_text[:30]}...",
            callback_data=f"answer_{answer.answer_id}"
        ))
    
    # Добавляем кнопки действий
    builder.add(InlineKeyboardButton(
        text="➕ Добавить ответ",
        callback_data=f"add_answer_{question_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 Назад к вопросу",
        callback_data=f"question_{question_id}"
    ))
    
    # Размещаем по одной кнопке в строку
    builder.adjust(1)
    
    return builder.as_markup()

# Клавиатура для подтверждения удаления
def get_confirm_delete_kb(entity_type: str, entity_id: int, return_callback: str):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    builder.add(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{entity_type}_{entity_id}"),
        InlineKeyboardButton(text="❌ Отменить", callback_data=return_callback)
    )
    
    # Размещаем по одной кнопке в строку
    builder.adjust(1)
    
    return builder.as_markup()

# Обработчик команды "Тесты" в меню администратора
@router.callback_query(F.data == "admin_tests")
async def admin_tests_command(callback: CallbackQuery):
    """Обработчик команды администратора для управления тестами"""
    await callback.message.edit_text(
        "Управление тестами. Выберите действие:",
        reply_markup=get_test_management_kb()
    )
    await callback.answer()

# Обработчик возврата в админ-меню
# Обработчик возврата в админ-меню (переопределяем глобальный обработчик)
@router.callback_query(F.data == "back_to_admin_menu")
async def back_to_admin_menu_from_tests(callback: CallbackQuery):
    """Обработчик возврата в административное меню"""
    await callback.message.edit_text(
        "Панель администратора. Выберите опцию:",
        reply_markup=get_admin_menu_kb()
    )
    await callback.answer()

# Обработчик просмотра списка тестов
@router.callback_query(F.data == "list_tests")
async def list_tests_command(callback: CallbackQuery, session: AsyncSession):
    """Обработчик просмотра списка тестов"""
    # Получаем список статей, для которых есть тесты
    from sqlalchemy import func
    
    # Получаем статьи, у которых есть тесты
    result = await session.execute(
        select(Article)
        .join(Test, Article.article_id == Test.article_id)
        .group_by(Article.article_id)
        .order_by(Article.title)
    )
    articles = result.scalars().all()
    
    if not articles:
        await callback.message.edit_text(
            "Тесты не найдены. Сначала создайте тест.",
            reply_markup=get_test_management_kb()
        )
        await callback.answer()
        return
    
    # Создаем клавиатуру для выбора статьи
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    for article in articles:
        builder.add(InlineKeyboardButton(
            text=article.title,
            callback_data=f"tests_for_article_{article.article_id}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="admin_tests"
    ))
    
    # Размещаем по одной кнопке в строку
    builder.adjust(1)
    
    await callback.message.edit_text(
        "Выберите статью для просмотра связанных тестов:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

# Обработчик просмотра тестов для конкретной статьи
@router.callback_query(F.data.startswith("tests_for_article_"))
async def tests_for_article(callback: CallbackQuery, session: AsyncSession):
    """Обработчик просмотра тестов для выбранной статьи"""
    # Извлекаем ID статьи из callback_data
    article_id = int(callback.data.split("_")[3])
    
    # Получаем информацию о статье
    article_result = await session.execute(select(Article).where(Article.article_id == article_id))
    article = article_result.scalar_one_or_none()
    
    if not article:
        await callback.message.edit_text(
            "Статья не найдена. Возможно, она была удалена.",
            reply_markup=get_test_management_kb()
        )
        await callback.answer()
        return
    
    # Получаем тесты для этой статьи
    tests = await get_tests_by_article(session, article_id)
    
    if not tests:
        # Создаем клавиатуру с кнопкой добавления теста
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        
        builder = InlineKeyboardBuilder()
        
        builder.add(InlineKeyboardButton(
            text="➕ Создать тест для этой статьи",
            callback_data=f"create_test_for_article_{article_id}"
        ))
        
        builder.add(InlineKeyboardButton(
            text="🔙 Назад к списку статей",
            callback_data="list_tests"
        ))
        
        builder.adjust(1)
        
        await callback.message.edit_text(
            f"Для статьи \"{article.title}\" нет тестов.",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
        return
    
    # Создаем клавиатуру для выбора теста
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    for test in tests:
        builder.add(InlineKeyboardButton(
            text=test.title,
            callback_data=f"test_details_{test.test_id}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="➕ Создать новый тест",
        callback_data=f"create_test_for_article_{article_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 Назад к списку статей",
        callback_data="list_tests"
    ))
    
    # Размещаем по одной кнопке в строку
    builder.adjust(1)
    
    await callback.message.edit_text(
        f"Тесты для статьи \"{article.title}\":",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

# Обработчик просмотра деталей теста
@router.callback_query(F.data.startswith("test_details_"))
async def test_details(callback: CallbackQuery, session: AsyncSession):
    """Обработчик просмотра деталей теста"""
    # Извлекаем ID теста из callback_data
    test_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о тесте
    test = await get_test_by_id(session, test_id)
    
    if not test:
        await callback.message.edit_text(
            "Тест не найден. Возможно, он был удален.",
            reply_markup=get_test_management_kb()
        )
        await callback.answer()
        return
    
    # Получаем информацию о статье
    article_result = await session.execute(select(Article).where(Article.article_id == test.article_id))
    article = article_result.scalar_one_or_none()
    
    if not article:
        await callback.message.edit_text(
            "Ошибка: статья для теста не найдена.",
            reply_markup=get_test_management_kb()
        )
        await callback.answer()
        return
    
    # Получаем статистику по тесту
    from bot.database.operations_library import get_test_statistics
    stats = await get_test_statistics(session, test_id)
    
    # Формируем сообщение с информацией о тесте
    message_text = (
        f"📝 <b>Тест:</b> {test.title}\n"
        f"📄 <b>Статья:</b> {article.title}\n"
        f"📊 <b>Порог прохождения:</b> {test.pass_threshold}%\n\n"
        f"<b>Статистика:</b>\n"
        f"📈 Всего попыток: {stats['total_attempts']}\n"
        f"👥 Уникальных пользователей: {stats['unique_users']}\n"
        f"⭐ Средний балл: {stats['avg_score']}\n"
        f"✅ Успешных прохождений: {stats['success_rate']}%\n"
    )
    
    # Получаем количество вопросов
    questions_count = len(test.questions)
    
    message_text += f"\n❓ Количество вопросов: {questions_count}"
    
    await callback.message.edit_text(
        message_text,
        reply_markup=get_test_actions_kb(test_id, article.article_id),
        parse_mode="HTML"
    )
    await callback.answer()

# Обработчик создания теста для статьи
@router.callback_query(F.data.startswith("create_test_for_article_"))
async def create_test_for_article(callback: CallbackQuery, state: FSMContext):
    """Обработчик создания нового теста для статьи"""
    # Извлекаем ID статьи из callback_data
    article_id = int(callback.data.split("_")[4])
    
    # Сохраняем ID статьи в состоянии
    await state.update_data(article_id=article_id)
    
    await callback.message.edit_text(
        "Введите название теста:"
    )
    
    # Устанавливаем состояние ожидания названия теста
    await state.set_state(TestAdminStates.waiting_for_test_title)
    await callback.answer()

# Обработчик ввода названия теста
@router.message(TestAdminStates.waiting_for_test_title)
async def process_test_title(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик ввода названия теста"""
    # Получаем введенное название
    title = message.text.strip()
    
    # Проверяем длину названия
    if len(title) < 3 or len(title) > 200:
        await message.answer(
            "Название теста должно содержать от 3 до 200 символов. Пожалуйста, введите корректное название:"
        )
        return
    
    # Сохраняем название теста в состоянии
    await state.update_data(test_title=title)
    
    # Запрашиваем порог прохождения теста
    await message.answer(
        "Укажите порог прохождения теста в процентах (число от 60 до 100):"
    )
    
    # Устанавливаем состояние ожидания порога прохождения
    await state.set_state(TestAdminStates.waiting_for_pass_threshold)

# Обработчик ввода порога прохождения теста
@router.message(TestAdminStates.waiting_for_pass_threshold)
async def process_pass_threshold(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик ввода порога прохождения теста"""
    # Получаем введенное значение
    try:
        threshold = int(message.text.strip())
        
        # Проверяем, что значение в допустимом диапазоне
        if threshold < 60 or threshold > 100:
            await message.answer(
                "Порог прохождения должен быть числом от 60 до 100. Пожалуйста, введите корректное значение:"
            )
            return
    except ValueError:
        await message.answer(
            "Пожалуйста, введите числовое значение для порога прохождения:"
        )
        return
    
    # Получаем данные из состояния
    data = await state.get_data()
    article_id = data.get("article_id")
    test_title = data.get("test_title")
    
    if not article_id or not test_title:
        await message.answer(
            "Ошибка: нет данных о статье или названии теста. Начните создание теста заново."
        )
        await state.clear()
        return
    
    # Получаем статью для проверки
    article_result = await session.execute(select(Article).where(Article.article_id == article_id))
    article = article_result.scalar_one_or_none()
    
    if not article:
        await message.answer(
            "Ошибка: статья не найдена. Возможно, она была удалена.",
            reply_markup=get_test_management_kb()
        )
        await state.clear()
        return
    
    # Создаем новый тест
    try:
        new_test = await create_test(
            session=session,
            title=test_title,
            article_id=article_id,
            pass_threshold=threshold,
            admin_id=message.from_user.id
        )
        
        if not new_test:
            await message.answer(
                "Ошибка при создании теста. Пожалуйста, попробуйте позже.",
                reply_markup=get_test_management_kb()
            )
            await state.clear()
            return
        
        # Создаем клавиатуру для добавления вопросов
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        
        builder = InlineKeyboardBuilder()
        
        builder.add(InlineKeyboardButton(
            text="➕ Добавить вопросы",
            callback_data=f"manage_questions_{new_test.test_id}"
        ))
        
        builder.add(InlineKeyboardButton(
            text="🔙 К деталям теста",
            callback_data=f"test_details_{new_test.test_id}"
        ))
        
        builder.adjust(1)
        
        # Сообщаем об успешном создании теста
        await message.answer(
            f"Тест \"{test_title}\" успешно создан для статьи \"{article.title}\"!\n\n"
            f"Порог прохождения: {threshold}%\n\n"
            f"Теперь вы можете добавить вопросы к тесту.",
            reply_markup=builder.as_markup()
        )
        
    except Exception as e:
        logger.error(f"Ошибка при создании теста: {e}")
        await message.answer(
            f"Произошла ошибка при создании теста: {e}",
            reply_markup=get_test_management_kb()
        )
    
    # Сбрасываем состояние
    await state.clear()

# Обработчик редактирования теста
@router.callback_query(F.data.startswith("edit_test_"))
async def edit_test_command(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик редактирования теста"""
    # Извлекаем ID теста из callback_data
    test_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о тесте
    test = await get_test_by_id(session, test_id)
    
    if not test:
        await callback.message.edit_text(
            "Тест не найден. Возможно, он был удален.",
            reply_markup=get_test_management_kb()
        )
        await callback.answer()
        return
    
    # Создаем клавиатуру с кнопками для редактирования различных параметров
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="✏️ Изменить название",
        callback_data=f"edit_test_title_{test_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="📊 Изменить порог прохождения",
        callback_data=f"edit_test_threshold_{test_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 Назад к тесту",
        callback_data=f"test_details_{test_id}"
    ))
    
    builder.adjust(1)
    
    await callback.message.edit_text(
        f"Редактирование теста \"{test.title}\"\n\n"
        f"Текущий порог прохождения: {test.pass_threshold}%\n\n"
        f"Выберите, что вы хотите изменить:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

# Обработчик изменения названия теста
@router.callback_query(F.data.startswith("edit_test_title_"))
async def edit_test_title(callback: CallbackQuery, state: FSMContext):
    """Обработчик изменения названия теста"""
    # Извлекаем ID теста из callback_data
    test_id = int(callback.data.split("_")[3])
    
    # Сохраняем ID теста в состоянии
    await state.update_data(test_id=test_id)
    
    await callback.message.edit_text(
        "Введите новое название теста:"
    )
    
    # Устанавливаем состояние ожидания нового названия теста
    await state.set_state(TestAdminStates.waiting_for_test_title)
    await callback.answer()

# Обработчик изменения порога прохождения теста
@router.callback_query(F.data.startswith("edit_test_threshold_"))
async def edit_test_threshold(callback: CallbackQuery, state: FSMContext):
    """Обработчик изменения порога прохождения теста"""
    # Извлекаем ID теста из callback_data
    test_id = int(callback.data.split("_")[3])
    
    # Сохраняем ID теста в состоянии
    await state.update_data(test_id=test_id)
    
    await callback.message.edit_text(
        "Введите новый порог прохождения теста в процентах (число от 60 до 100):"
    )
    
    # Устанавливаем состояние ожидания нового порога прохождения
    await state.set_state(TestAdminStates.waiting_for_pass_threshold)
    await callback.answer()

# Обработчик для изменения порога прохождения теста
@router.message(TestAdminStates.waiting_for_pass_threshold)
async def process_edit_threshold(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик ввода нового порога прохождения теста"""
    # Получаем введенное значение
    try:
        threshold = int(message.text.strip())
        
        # Проверяем, что значение в допустимом диапазоне
        if threshold < 60 or threshold > 100:
            await message.answer(
                "Порог прохождения должен быть числом от 60 до 100. Пожалуйста, введите корректное значение:"
            )
            return
    except ValueError:
        await message.answer(
            "Пожалуйста, введите числовое значение для порога прохождения:"
        )
        return
    
    # Получаем данные из состояния
    data = await state.get_data()
    test_id = data.get("test_id")
    
    # Если нет test_id, значит это создание нового теста
    if not test_id:
        # Логика создания теста (уже реализована выше)
        return await process_pass_threshold(message, state, session)
    
    # Обновляем порог прохождения теста
    try:
        success = await update_test(
            session=session,
            test_id=test_id,
            pass_threshold=threshold,
            admin_id=message.from_user.id
        )
        
        if not success:
            await message.answer(
                "Ошибка при обновлении теста. Тест не найден или возникла другая проблема.",
                reply_markup=get_test_management_kb()
            )
            await state.clear()
            return
        
        # Получаем обновленную информацию о тесте
        test = await get_test_by_id(session, test_id)
        
        # Сообщаем об успешном обновлении
        await message.answer(
            f"Порог прохождения теста \"{test.title}\" успешно изменен на {threshold}%",
            reply_markup=get_test_actions_kb(test_id, test.article_id)
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении теста: {e}")
        await message.answer(
            f"Произошла ошибка при обновлении теста: {e}",
            reply_markup=get_test_management_kb()
        )
    
    # Сбрасываем состояние
    await state.clear()

# Обработчик для удаления теста
@router.callback_query(F.data.startswith("delete_test_"))
async def delete_test_command(callback: CallbackQuery, session: AsyncSession):
    """Обработчик удаления теста"""
    # Извлекаем ID теста из callback_data
    test_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о тесте
    test = await get_test_by_id(session, test_id)
    
    if not test:
        await callback.message.edit_text(
            "Тест не найден. Возможно, он уже был удален.",
            reply_markup=get_test_management_kb()
        )
        await callback.answer()
        return
    
    # Показываем подтверждение удаления
    await callback.message.edit_text(
        f"Вы действительно хотите удалить тест \"{test.title}\"?\n\n"
        f"Внимание! Будут удалены все вопросы и ответы, связанные с этим тестом. "
        f"Эту операцию нельзя отменить.",
        reply_markup=get_confirm_delete_kb("test", test_id, f"test_details_{test_id}")
    )
    await callback.answer()

# Обработчик подтверждения удаления теста
@router.callback_query(F.data.startswith("confirm_delete_test_"))
async def confirm_delete_test(callback: CallbackQuery, session: AsyncSession):
    """Обработчик подтверждения удаления теста"""
    # Извлекаем ID теста из callback_data
    test_id = int(callback.data.split("_")[3])
    
    # Получаем информацию о тесте перед удалением
    test = await get_test_by_id(session, test_id)
    
    if not test:
        await callback.message.edit_text(
            "Тест не найден. Возможно, он уже был удален.",
            reply_markup=get_test_management_kb()
        )
        await callback.answer()
        return
    
    # Сохраняем article_id для возврата после удаления
    article_id = test.article_id
    
    # Удаляем тест
    try:
        success = await delete_test(
            session=session,
            test_id=test_id,
            admin_id=callback.from_user.id
        )
        
        if not success:
            await callback.message.edit_text(
                "Ошибка при удалении теста.",
                reply_markup=get_test_management_kb()
            )
            await callback.answer()
            return
        
        # Сообщаем об успешном удалении
        await callback.message.edit_text(
            f"Тест \"{test.title}\" успешно удален.",
            reply_markup=get_test_management_kb()
        )
        
        # Показываем список тестов для статьи
        await callback.message.answer(
            "Вернуться к списку тестов для этой статьи?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Да", callback_data=f"tests_for_article_{article_id}"),
                InlineKeyboardButton(text="Нет", callback_data="admin_tests")
            ]])
        )
        
    except Exception as e:
        logger.error(f"Ошибка при удалении теста: {e}")
        await callback.message.edit_text(
            f"Произошла ошибка при удалении теста: {e}",
            reply_markup=get_test_management_kb()
        )
    
    await callback.answer()

# Обработчик управления вопросами теста
@router.callback_query(F.data.startswith("manage_questions_"))
async def manage_questions_command(callback: CallbackQuery, session: AsyncSession):
    """Обработчик управления вопросами теста"""
    # Извлекаем ID теста из callback_data
    test_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о тесте
    test = await get_test_by_id(session, test_id)
    
    if not test:
        await callback.message.edit_text(
            "Тест не найден. Возможно, он был удален.",
            reply_markup=get_test_management_kb()
        )
        await callback.answer()
        return
    
    # Получаем вопросы теста
    questions = await get_questions_by_test(session, test_id)
    
    if not questions:
        # Создаем клавиатуру с кнопкой добавления вопроса
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        
        builder = InlineKeyboardBuilder()
        
        builder.add(InlineKeyboardButton(
            text="➕ Добавить вопрос",
            callback_data=f"add_question_{test_id}"
        ))
        
        builder.add(InlineKeyboardButton(
            text="🔙 Назад к тесту",
            callback_data=f"test_details_{test_id}"
        ))
        
        builder.adjust(1)
        
        await callback.message.edit_text(
            f"У теста \"{test.title}\" пока нет вопросов.\n\n"
            f"Добавьте вопросы, чтобы пользователи могли проходить тест.",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
        return
    
    # Создаем клавиатуру для управления вопросами
    await callback.message.edit_text(
        f"Вопросы теста \"{test.title}\" ({len(questions)} шт.):\n\n"
        f"Выберите вопрос для редактирования или добавьте новый:",
        reply_markup=get_questions_list_kb(test_id, questions)
    )
    await callback.answer()

# Обработчик добавления вопроса
@router.callback_query(F.data.startswith("add_question_"))
async def add_question_command(callback: CallbackQuery, state: FSMContext):
    """Обработчик добавления вопроса к тесту"""
    # Извлекаем ID теста из callback_data
    test_id = int(callback.data.split("_")[2])
    
    # Сохраняем ID теста в состоянии
    await state.update_data(test_id=test_id)
    
    await callback.message.edit_text(
        "Введите текст вопроса:"
    )
    
    # Устанавливаем состояние ожидания текста вопроса
    await state.set_state(TestAdminStates.waiting_for_question_text)
    await callback.answer()

# Обработчик ввода текста вопроса
@router.message(TestAdminStates.waiting_for_question_text)
async def process_question_text(message: Message, state: FSMContext):
    """Обработчик ввода текста вопроса"""
    # Получаем введенный текст
    question_text = message.text.strip()
    
    # Проверяем длину текста
    if len(question_text) < 5 or len(question_text) > 500:
        await message.answer(
            "Текст вопроса должен содержать от 5 до 500 символов. Пожалуйста, введите корректный текст:"
        )
        return
    
    # Сохраняем текст вопроса в состоянии
    await state.update_data(question_text=question_text)
    
    # Запрашиваем вес вопроса
    await message.answer(
        "Введите вес вопроса (количество баллов, от 1 до 5):"
    )
    
    # Устанавливаем состояние ожидания веса вопроса
    await state.set_state(TestAdminStates.waiting_for_question_points)

# Обработчик ввода веса вопроса
@router.message(TestAdminStates.waiting_for_question_points)
async def process_question_points(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик ввода веса вопроса"""
    # Получаем введенное значение
    try:
        points = int(message.text.strip())
        
        # Проверяем, что значение в допустимом диапазоне
        if points < 1 or points > 5:
            await message.answer(
                "Вес вопроса должен быть числом от 1 до 5. Пожалуйста, введите корректное значение:"
            )
            return
    except ValueError:
        await message.answer(
            "Пожалуйста, введите числовое значение для веса вопроса:"
        )
        return
    
    # Получаем данные из состояния
    data = await state.get_data()
    test_id = data.get("test_id")
    question_text = data.get("question_text")
    
    if not test_id or not question_text:
        await message.answer(
            "Ошибка: нет данных о тесте или тексте вопроса. Начните создание вопроса заново."
        )
        await state.clear()
        return
    
    # Создаем новый вопрос
    try:
        new_question = await create_question(
            session=session,
            test_id=test_id,
            question_text=question_text,
            points=points,
            admin_id=message.from_user.id
        )
        
        if not new_question:
            await message.answer(
                "Ошибка при создании вопроса. Пожалуйста, попробуйте позже."
            )
            await state.clear()
            return
        
        # Сохраняем ID вопроса в состоянии для добавления ответов
        await state.update_data(question_id=new_question.question_id)
        
        # Создаем клавиатуру для добавления ответов
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        
        builder = InlineKeyboardBuilder()
        
        builder.add(InlineKeyboardButton(
            text="➕ Добавить ответы",
            callback_data=f"add_answer_{new_question.question_id}"
        ))
        
        builder.add(InlineKeyboardButton(
            text="🔙 К списку вопросов",
            callback_data=f"manage_questions_{test_id}"
        ))
        
        builder.adjust(1)
        
        # Сообщаем об успешном создании вопроса
        await message.answer(
            f"Вопрос успешно создан!\n\n"
            f"Текст: {question_text}\n"
            f"Вес: {points}\n\n"
            f"Теперь нужно добавить варианты ответов.",
            reply_markup=builder.as_markup()
        )
        
    except Exception as e:
        logger.error(f"Ошибка при создании вопроса: {e}")
        await message.answer(
            f"Произошла ошибка при создании вопроса: {e}"
        )
    
    # Сбрасываем состояние
    await state.clear()

# Обработчик просмотра вопроса
@router.callback_query(F.data.startswith("question_"))
async def question_details(callback: CallbackQuery, session: AsyncSession):
    """Обработчик просмотра деталей вопроса"""
    # Извлекаем ID вопроса из callback_data
    question_id = int(callback.data.split("_")[1])
    
    # Получаем информацию о вопросе
    result = await session.execute(
        select(Question).where(Question.question_id == question_id).options(joinedload(Question.answers))
    )
    question = result.scalar_one_or_none()
    
    if not question:
        await callback.message.edit_text(
            "Вопрос не найден. Возможно, он был удален.",
            reply_markup=get_test_management_kb()
        )
        await callback.answer()
        return
    
    # Получаем информацию о тесте
    result = await session.execute(select(Test).where(Test.test_id == question.test_id))
    test = result.scalar_one_or_none()
    
    if not test:
        await callback.message.edit_text(
            "Тест не найден. Возможно, он был удален.",
            reply_markup=get_test_management_kb()
        )
        await callback.answer()
        return
    
    # Получаем ответы к вопросу
    answers = question.answers if hasattr(question, 'answers') else []
    
    # Формируем сообщение с информацией о вопросе
    correct_answers = sum(1 for a in answers if a.is_correct)
    answers_text = "\n".join([
        f"{'✅' if a.is_correct else '❌'} {a.answer_text}" for a in sorted(answers, key=lambda x: x.position)
    ])
    
    message_text = (
        f"<b>Вопрос:</b> {question.question_text}\n\n"
        f"<b>Вес:</b> {question.points}\n"
        f"<b>Тест:</b> {test.title}\n"
        f"<b>Количество ответов:</b> {len(answers)}\n"
        f"<b>Правильных ответов:</b> {correct_answers}\n\n"
    )
    
    if answers:
        message_text += f"<b>Варианты ответов:</b>\n{answers_text}"
    else:
        message_text += "У вопроса пока нет вариантов ответов."
    
    await callback.message.edit_text(
        message_text,
        reply_markup=get_question_actions_kb(question_id, test.test_id),
        parse_mode="HTML"
    )
    await callback.answer()

# Обработчик редактирования вопроса
@router.callback_query(F.data.startswith("edit_question_"))
async def edit_question_command(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик редактирования вопроса"""
    # Извлекаем ID вопроса из callback_data
    question_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о вопросе
    result = await session.execute(select(Question).where(Question.question_id == question_id))
    question = result.scalar_one_or_none()
    
    if not question:
        await callback.message.edit_text(
            "Вопрос не найден. Возможно, он был удален.",
            reply_markup=get_test_management_kb()
        )
        await callback.answer()
        return
    
    # Сохраняем ID вопроса и теста в состоянии
    await state.update_data(question_id=question_id, test_id=question.test_id)
    
    # Создаем клавиатуру с кнопками для редактирования различных параметров
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="✏️ Изменить текст вопроса",
        callback_data=f"edit_question_text_{question_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="📊 Изменить вес вопроса",
        callback_data=f"edit_question_points_{question_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 Назад к вопросу",
        callback_data=f"question_{question_id}"
    ))
    
    builder.adjust(1)
    
    await callback.message.edit_text(
        f"Редактирование вопроса:\n\n"
        f"<b>Текущий текст:</b> {question.question_text}\n\n"
        f"<b>Текущий вес:</b> {question.points}\n\n"
        f"Выберите, что вы хотите изменить:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()

# Обработчик редактирования текста вопроса
@router.callback_query(F.data.startswith("edit_question_text_"))
async def edit_question_text(callback: CallbackQuery, state: FSMContext):
    """Обработчик редактирования текста вопроса"""
    # Извлекаем ID вопроса из callback_data
    question_id = int(callback.data.split("_")[3])
    
    # Сохраняем ID вопроса в состоянии
    await state.update_data(question_id=question_id, edit_mode=True)
    
    await callback.message.edit_text(
        "Введите новый текст вопроса:"
    )
    
    # Устанавливаем состояние ожидания нового текста вопроса
    await state.set_state(TestAdminStates.waiting_for_question_text)
    await callback.answer()

# Обработчик редактирования веса вопроса
@router.callback_query(F.data.startswith("edit_question_points_"))
async def edit_question_points(callback: CallbackQuery, state: FSMContext):
    """Обработчик редактирования веса вопроса"""
    # Извлекаем ID вопроса из callback_data
    question_id = int(callback.data.split("_")[3])
    
    # Сохраняем ID вопроса в состоянии
    await state.update_data(question_id=question_id, edit_mode=True)
    
    await callback.message.edit_text(
        "Введите новый вес вопроса (количество баллов, от 1 до 5):"
    )
    
    # Устанавливаем состояние ожидания нового веса вопроса
    await state.set_state(TestAdminStates.waiting_for_question_points)
    await callback.answer()

# Обработчик удаления вопроса
@router.callback_query(F.data.startswith("delete_question_"))
async def delete_question_command(callback: CallbackQuery, session: AsyncSession):
    """Обработчик удаления вопроса"""
    # Извлекаем ID вопроса из callback_data
    question_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о вопросе
    result = await session.execute(select(Question).where(Question.question_id == question_id))
    question = result.scalar_one_or_none()
    
    if not question:
        await callback.message.edit_text(
            "Вопрос не найден. Возможно, он уже был удален.",
            reply_markup=get_test_management_kb()
        )
        await callback.answer()
        return
    
    # Показываем подтверждение удаления
    await callback.message.edit_text(
        f"Вы действительно хотите удалить вопрос: \"{question.question_text}\"?\n\n"
        f"Внимание! Будут удалены все ответы, связанные с этим вопросом. "
        f"Эту операцию нельзя отменить.",
        reply_markup=get_confirm_delete_kb("question", question_id, f"question_{question_id}")
    )
    await callback.answer()

# Обработчик подтверждения удаления вопроса
@router.callback_query(F.data.startswith("confirm_delete_question_"))
async def confirm_delete_question(callback: CallbackQuery, session: AsyncSession):
    """Обработчик подтверждения удаления вопроса"""
    # Извлекаем ID вопроса из callback_data
    question_id = int(callback.data.split("_")[3])
    
    # Получаем информацию о вопросе перед удалением
    result = await session.execute(select(Question).where(Question.question_id == question_id))
    question = result.scalar_one_or_none()
    
    if not question:
        await callback.message.edit_text(
            "Вопрос не найден. Возможно, он уже был удален.",
            reply_markup=get_test_management_kb()
        )
        await callback.answer()
        return
    
    # Сохраняем test_id для возврата после удаления
    test_id = question.test_id
    
    # Удаляем вопрос
    try:
        success = await delete_question(
            session=session,
            question_id=question_id,
            admin_id=callback.from_user.id
        )
        
        if not success:
            await callback.message.edit_text(
                "Ошибка при удалении вопроса.",
                reply_markup=get_test_management_kb()
            )
            await callback.answer()
            return
        
        # Сообщаем об успешном удалении
        await callback.message.edit_text(
            f"Вопрос успешно удален.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 К списку вопросов", callback_data=f"manage_questions_{test_id}")
            ]])
        )
        
    except Exception as e:
        logger.error(f"Ошибка при удалении вопроса: {e}")
        await callback.message.edit_text(
            f"Произошла ошибка при удалении вопроса: {e}",
            reply_markup=get_test_management_kb()
        )
    
    await callback.answer()

# Обработчик добавления ответа
@router.callback_query(F.data.startswith("add_answer_"))
async def add_answer_command(callback: CallbackQuery, state: FSMContext):
    """Обработчик добавления ответа к вопросу"""
    # Извлекаем ID вопроса из callback_data
    question_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о вопросе
    result = await session.execute(select(Question).where(Question.question_id == question_id).options(joinedload(Question.answers)))
    question = result.scalar_one_or_none()
    
    if not question:
        await callback.message.edit_text(
            "Вопрос не найден. Возможно, он был удален.",
            reply_markup=get_test_management_kb()
        )
        await callback.answer()
        return
    
    # Проверяем количество ответов (максимум 6)
    if hasattr(question, 'answers') and len(question.answers) >= 6:
        await callback.message.edit_text(
            "Достигнуто максимальное количество ответов (6) для этого вопроса.",
            reply_markup=get_question_actions_kb(question_id, question.test_id)
        )
        await callback.answer()
        return
    
    # Сохраняем ID вопроса и теста в состоянии
    await state.update_data(
        question_id=question_id, 
        test_id=question.test_id,
        position=len(question.answers) + 1 if hasattr(question, 'answers') else 1
    )
    
    await callback.message.edit_text(
        f"Добавление ответа для вопроса:\n\n"
        f"{question.question_text}\n\n"
        f"Введите текст ответа:"
    )
    
    # Устанавливаем состояние ожидания текста ответа
    await state.set_state(TestAdminStates.waiting_for_answer_text)
    await callback.answer()

# Обработчик ввода текста ответа
@router.message(TestAdminStates.waiting_for_answer_text)
async def process_answer_text(message: Message, state: FSMContext):
    """Обработчик ввода текста ответа"""
    # Получаем введенный текст
    answer_text = message.text.strip()
    
    # Проверяем длину текста
    if len(answer_text) < 1 or len(answer_text) > 200:
        await message.answer(
            "Текст ответа должен содержать от 1 до 200 символов. Пожалуйста, введите корректный текст:"
        )
        return
    
    # Сохраняем текст ответа в состоянии
    await state.update_data(answer_text=answer_text)
    
    # Запрашиваем, является ли ответ правильным
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="✅ Да, правильный",
        callback_data="answer_correct_true"
    ))
    
    builder.add(InlineKeyboardButton(
        text="❌ Нет, неправильный",
        callback_data="answer_correct_false"
    ))
    
    builder.adjust(1)
    
    await message.answer(
        "Является ли этот ответ правильным?",
        reply_markup=builder.as_markup()
    )
    
    # Устанавливаем состояние ожидания выбора правильности ответа
    await state.set_state(TestAdminStates.waiting_for_answer_correct)

# Обработчик выбора правильности ответа
@router.callback_query(TestAdminStates.waiting_for_answer_correct, F.data.startswith("answer_correct_"))
async def process_answer_correct(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора правильности ответа"""
    # Получаем выбор правильности
    is_correct = callback.data.split("_")[2] == "true"
    
    # Получаем данные из состояния
    data = await state.get_data()
    question_id = data.get("question_id")
    answer_text = data.get("answer_text")
    position = data.get("position", 1)
    
    if not question_id or not answer_text:
        await callback.message.edit_text(
            "Ошибка: нет данных о вопросе или тексте ответа. Начните создание ответа заново."
        )
        await state.clear()
        await callback.answer()
        return
    
    # Создаем новый ответ
    try:
        new_answer = await create_answer(
            session=session,
            question_id=question_id,
            answer_text=answer_text,
            is_correct=is_correct,
            position=position,
            admin_id=callback.from_user.id
        )
        
        if not new_answer:
            await callback.message.edit_text(
                "Ошибка при создании ответа. Пожалуйста, попробуйте позже."
            )
            await state.clear()
            await callback.answer()
            return
        
        # Получаем обновленную информацию о вопросе
        result = await session.execute(
            select(Question).where(Question.question_id == question_id).options(joinedload(Question.answers))
        )
        question = result.scalar_one_or_none()
        
        # Проверяем, нужно ли добавить еще ответы
        if hasattr(question, 'answers') and len(question.answers) < 6:
            # Спрашиваем, хочет ли пользователь добавить еще один ответ
            await callback.message.edit_text(
                f"Ответ успешно создан!\n\n"
                f"Текст: {answer_text}\n"
                f"Правильный: {'Да' if is_correct else 'Нет'}\n\n"
                f"Хотите добавить еще один ответ? (всего можно добавить до 6 ответов)"
            )
            
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            from aiogram.types import InlineKeyboardButton
            
            builder = InlineKeyboardBuilder()
            
            builder.add(InlineKeyboardButton(
                text="➕ Да, добавить еще ответ",
                callback_data=f"add_answer_{question_id}"
            ))
            
            builder.add(InlineKeyboardButton(
                text="✅ Нет, завершить",
                callback_data=f"view_answers_{question_id}"
            ))
            
            builder.adjust(1)
            
            await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
        else:
            # Показываем список всех ответов
            await callback.message.edit_text(
                f"Ответ успешно создан!\n\n"
                f"Достигнуто максимальное количество ответов (6) для этого вопроса."
            )
            
            await callback.message.answer(
                "Все ответы для вопроса:",
                reply_markup=get_answers_list_kb(question.answers, question_id)
            )
        
    except Exception as e:
        logger.error(f"Ошибка при создании ответа: {e}")
        await callback.message.edit_text(
            f"Произошла ошибка при создании ответа: {e}"
        )
    
    # Сбрасываем состояние
    await state.clear()
    await callback.answer()

# Обработчик просмотра ответов
@router.callback_query(F.data.startswith("view_answers_"))
async def view_answers(callback: CallbackQuery, session: AsyncSession):
    """Обработчик просмотра ответов на вопрос"""
    # Извлекаем ID вопроса из callback_data
    question_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о вопросе с ответами
    result = await session.execute(
        select(Question).where(Question.question_id == question_id).options(joinedload(Question.answers))
    )
    question = result.scalar_one_or_none()
    
    if not question:
        await callback.message.edit_text(
            "Вопрос не найден. Возможно, он был удален.",
            reply_markup=get_test_management_kb()
        )
        await callback.answer()
        return
    
    # Получаем ответы к вопросу
    answers = question.answers if hasattr(question, 'answers') else []
    
    if not answers:
        await callback.message.edit_text(
            f"У вопроса пока нет ответов. Добавьте хотя бы один ответ.",
            reply_markup=get_question_actions_kb(question_id, question.test_id)
        )
        await callback.answer()
        return
    
    # Показываем список ответов
    await callback.message.edit_text(
        f"Ответы на вопрос: {question.question_text}\n\n"
        f"Выберите ответ для редактирования или добавьте новый:",
        reply_markup=get_answers_list_kb(answers, question_id)
    )
    await callback.answer()

# Обработчик просмотра деталей ответа
@router.callback_query(F.data.startswith("answer_"))
async def answer_details(callback: CallbackQuery, session: AsyncSession):
    """Обработчик просмотра деталей ответа"""
    # Извлекаем ID ответа из callback_data
    answer_id = int(callback.data.split("_")[1])
    
    # Получаем информацию об ответе
    result = await session.execute(select(Answer).where(Answer.answer_id == answer_id))
    answer = result.scalar_one_or_none()
    
    if not answer:
        await callback.message.edit_text(
            "Ответ не найден. Возможно, он был удален.",
            reply_markup=get_test_management_kb()
        )
        await callback.answer()
        return
    
    # Получаем информацию о вопросе
    result = await session.execute(select(Question).where(Question.question_id == answer.question_id))
    question = result.scalar_one_or_none()
    
    if not question:
        await callback.message.edit_text(
            "Вопрос не найден. Возможно, он был удален.",
            reply_markup=get_test_management_kb()
        )
        await callback.answer()
        return"""Обработчик управления вопросами теста"""
    # Извлекаем ID теста из callback_data

    answer_id = int(callback.data.split("_")[1])
    
    # Получаем информацию об ответе
    result = await session.execute(select(Answer).where(Answer.answer_id == answer_id))
    answer = result.scalar_one_or_none()
    
    if not answer:
        await callback.message.edit_text(
            "Ответ не найден. Возможно, он был удален.",
            reply_markup=get_test_management_kb()
        )
        await callback.answer()
        return
    
    # Получаем информацию о вопросе
    result = await session.execute(select(Question).where(Question.question_id == answer.question_id))
    question = result.scalar_one_or_none()
    
    if not question:
        await callback.message.edit_text(
            "Вопрос не найден. Возможно, он был удален.",
            reply_markup=get_test_management_kb()
        )
        await callback.answer()
        return
    
    # Создаем клавиатуру для действий с ответом
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="✏️ Изменить текст ответа",
        callback_data=f"edit_answer_text_{answer_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text=f"{'✅' if not answer.is_correct else '❌'} Изменить статус ответа",
        callback_data=f"toggle_answer_correct_{answer_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🔼 Переместить вверх",
        callback_data=f"move_answer_up_{answer_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🔽 Переместить вниз",
        callback_data=f"move_answer_down_{answer_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="❌ Удалить ответ",
        callback_data=f"delete_answer_{answer_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 К списку ответов",
        callback_data=f"view_answers_{question.question_id}"
    ))
    
    builder.adjust(1)
    
    await callback.message.edit_text(
        f"<b>Ответ:</b> {answer.answer_text}\n\n"
        f"<b>Статус:</b> {'Правильный ✅' if answer.is_correct else 'Неправильный ❌'}\n"
        f"<b>Позиция:</b> {answer.position}\n"
        f"<b>Вопрос:</b> {question.question_text}\n\n"
        f"Выберите действие:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


# Обработчик редактирования текста ответа
@router.callback_query(F.data.startswith("edit_answer_text_"))
async def edit_answer_text(callback: CallbackQuery, state: FSMContext):
    """Обработчик редактирования текста ответа"""
    # Извлекаем ID ответа из callback_data
    answer_id = int(callback.data.split("_")[3])
    
    # Сохраняем ID ответа в состоянии
    await state.update_data(answer_id=answer_id)
    
    await callback.message.edit_text(
        "Введите новый текст ответа:"
    )
    
    # Устанавливаем состояние ожидания нового текста ответа
    await state.set_state(TestAdminStates.waiting_for_edit_answer)
    await callback.answer()


# Обработчик ввода нового текста ответа
@router.message(TestAdminStates.waiting_for_edit_answer)
async def process_edit_answer_text(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик ввода нового текста ответа"""
    # Получаем введенный текст
    answer_text = message.text.strip()
    
    # Проверяем длину текста
    if len(answer_text) < 1 or len(answer_text) > 200:
        await message.answer(
            "Текст ответа должен содержать от 1 до 200 символов. Пожалуйста, введите корректный текст:"
        )
        return
    
    # Получаем данные из состояния
    data = await state.get_data()
    answer_id = data.get("answer_id")
    
    if not answer_id:
        await message.answer(
            "Ошибка: нет данных об ответе. Начните редактирование заново."
        )
        await state.clear()
        return
    
    # Получаем информацию об ответе
    result = await session.execute(select(Answer).where(Answer.answer_id == answer_id))
    answer = result.scalar_one_or_none()
    
    if not answer:
        await message.answer(
            "Ответ не найден. Возможно, он был удален.",
            reply_markup=get_test_management_kb()
        )
        await state.clear()
        return
    
    # Обновляем текст ответа
    try:
        answer.answer_text = answer_text
        await session.commit()
        
        # Сообщаем об успешном обновлении
        await message.answer(
            f"Текст ответа успешно обновлен на: {answer_text}"
        )
        
        # Направляем обратно к деталям ответа
        await message.answer(
            "Вернуться к просмотру ответа?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Да", callback_data=f"answer_{answer_id}")
            ]])
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении ответа: {e}")
        await message.answer(
            f"Произошла ошибка при обновлении ответа: {e}"
        )
    
    # Сбрасываем состояние
    await state.clear()


# Обработчик изменения статуса ответа (правильный/неправильный)
@router.callback_query(F.data.startswith("toggle_answer_correct_"))
async def toggle_answer_correct(callback: CallbackQuery, session: AsyncSession):
    """Обработчик изменения статуса ответа"""
    # Извлекаем ID ответа из callback_data
    answer_id = int(callback.data.split("_")[3])
    
    # Получаем информацию об ответе
    result = await session.execute(select(Answer).where(Answer.answer_id == answer_id))
    answer = result.scalar_one_or_none()
    
    if not answer:
        await callback.message.edit_text(
            "Ответ не найден. Возможно, он был удален.",
            reply_markup=get_test_management_kb()
        )
        await callback.answer()
        return
    
    try:
        # Инвертируем статус ответа
        answer.is_correct = not answer.is_correct
        await session.commit()
        
        # Получаем обновленную информацию о вопросе для проверки количества правильных ответов
        result = await session.execute(
            select(Question).where(Question.question_id == answer.question_id).options(joinedload(Question.answers))
        )
        question = result.scalar_one_or_none()
        
        # Проверяем, есть ли хотя бы один правильный ответ
        if hasattr(question, 'answers'):
            correct_answers = [a for a in question.answers if a.is_correct]
            if not correct_answers:
                # Если нет правильных ответов, выводим предупреждение
                await callback.message.edit_text(
                    f"⚠️ Внимание! У вопроса нет ни одного правильного ответа. "
                    f"Пользователи не смогут правильно ответить на этот вопрос.\n\n"
                    f"<b>Ответ:</b> {answer.answer_text}\n"
                    f"<b>Статус:</b> {'Правильный ✅' if answer.is_correct else 'Неправильный ❌'}\n"
                    f"<b>Позиция:</b> {answer.position}\n"
                    f"<b>Вопрос:</b> {question.question_text}",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="Вернуться к ответу", callback_data=f"answer_{answer_id}")
                    ]]),
                    parse_mode="HTML"
                )
                await callback.answer("⚠️ Внимание! У вопроса нет правильных ответов!")
                return
        
        # Перенаправляем обратно к деталям ответа
        await callback.message.edit_text(
            f"Статус ответа изменен на {'правильный ✅' if answer.is_correct else 'неправильный ❌'}"
        )
        await callback.message.answer(
            "Вернуться к просмотру ответа?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Да", callback_data=f"answer_{answer_id}")
            ]])
        )
        
    except Exception as e:
        logger.error(f"Ошибка при изменении статуса ответа: {e}")
        await callback.message.edit_text(
            f"Произошла ошибка при изменении статуса ответа: {e}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Вернуться к ответу", callback_data=f"answer_{answer_id}")
            ]])
        )
    
    await callback.answer()


# Обработчик перемещения ответа вверх
@router.callback_query(F.data.startswith("move_answer_up_"))
async def move_answer_up(callback: CallbackQuery, session: AsyncSession):
    """Обработчик перемещения ответа вверх по списку"""
    # Извлекаем ID ответа из callback_data
    answer_id = int(callback.data.split("_")[3])
    
    # Получаем информацию об ответе
    result = await session.execute(select(Answer).where(Answer.answer_id == answer_id))
    answer = result.scalar_one_or_none()
    
    if not answer:
        await callback.message.edit_text(
            "Ответ не найден. Возможно, он был удален.",
            reply_markup=get_test_management_kb()
        )
        await callback.answer()
        return
    
    # Получаем все ответы на вопрос, отсортированные по позиции
    result = await session.execute(
        select(Answer).where(Answer.question_id == answer.question_id).order_by(Answer.position)
    )
    answers = result.scalars().all()
    
    # Находим текущую позицию ответа в отсортированном списке
    current_index = next((i for i, a in enumerate(answers) if a.answer_id == answer_id), None)
    
    if current_index is None or current_index == 0:
        # Если ответ уже на первой позиции, ничего не делаем
        await callback.answer("Этот ответ уже находится в начале списка")
        return
    
    try:
        # Меняем местами текущий ответ с предыдущим
        prev_answer = answers[current_index - 1]
        
        # Сохраняем позиции
        temp_position = answer.position
        answer.position = prev_answer.position
        prev_answer.position = temp_position
        
        await session.commit()
        
        # Перенаправляем к просмотру ответов
        await callback.message.edit_text(
            f"Ответ перемещен вверх."
        )
        await callback.message.answer(
            "Вернуться к списку ответов?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Да", callback_data=f"view_answers_{answer.question_id}")
            ]])
        )
        
    except Exception as e:
        logger.error(f"Ошибка при перемещении ответа: {e}")
        await callback.message.edit_text(
            f"Произошла ошибка при перемещении ответа: {e}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Вернуться к ответу", callback_data=f"answer_{answer_id}")
            ]])
        )
    
    await callback.answer()


# Обработчик перемещения ответа вниз
@router.callback_query(F.data.startswith("move_answer_down_"))
async def move_answer_down(callback: CallbackQuery, session: AsyncSession):
    """Обработчик перемещения ответа вниз по списку"""
    # Извлекаем ID ответа из callback_data
    answer_id = int(callback.data.split("_")[3])
    
    # Получаем информацию об ответе
    result = await session.execute(select(Answer).where(Answer.answer_id == answer_id))
    answer = result.scalar_one_or_none()
    
    if not answer:
        await callback.message.edit_text(
            "Ответ не найден. Возможно, он был удален.",
            reply_markup=get_test_management_kb()
        )
        await callback.answer()
        return
    
    # Получаем все ответы на вопрос, отсортированные по позиции
    result = await session.execute(
        select(Answer).where(Answer.question_id == answer.question_id).order_by(Answer.position)
    )
    answers = result.scalars().all()
    
    # Находим текущую позицию ответа в отсортированном списке
    current_index = next((i for i, a in enumerate(answers) if a.answer_id == answer_id), None)
    
    if current_index is None or current_index == len(answers) - 1:
        # Если ответ уже на последней позиции, ничего не делаем
        await callback.answer("Этот ответ уже находится в конце списка")
        return
    
    try:
        # Меняем местами текущий ответ со следующим
        next_answer = answers[current_index + 1]
        
        # Сохраняем позиции
        temp_position = answer.position
        answer.position = next_answer.position
        next_answer.position = temp_position
        
        await session.commit()
        
        # Перенаправляем к просмотру ответов
        await callback.message.edit_text(
            f"Ответ перемещен вниз."
        )
        await callback.message.answer(
            "Вернуться к списку ответов?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Да", callback_data=f"view_answers_{answer.question_id}")
            ]])
        )
        
    except Exception as e:
        logger.error(f"Ошибка при перемещении ответа: {e}")
        await callback.message.edit_text(
            f"Произошла ошибка при перемещении ответа: {e}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Вернуться к ответу", callback_data=f"answer_{answer_id}")
            ]])
        )
    
    await callback.answer()


# Обработчик удаления ответа
@router.callback_query(F.data.startswith("delete_answer_"))
async def delete_answer_command(callback: CallbackQuery, session: AsyncSession):
    """Обработчик удаления ответа"""
    # Извлекаем ID ответа из callback_data
    answer_id = int(callback.data.split("_")[2])
    
    # Получаем информацию об ответе
    result = await session.execute(select(Answer).where(Answer.answer_id == answer_id))
    answer = result.scalar_one_or_none()
    
    if not answer:
        await callback.message.edit_text(
            "Ответ не найден. Возможно, он уже был удален.",
            reply_markup=get_test_management_kb()
        )
        await callback.answer()
        return
    
    # Сохраняем question_id для возврата после удаления
    question_id = answer.question_id
    
    # Показываем подтверждение удаления
    await callback.message.edit_text(
        f"Вы действительно хотите удалить ответ: \"{answer.answer_text}\"?\n\n"
        f"Эту операцию нельзя отменить.",
        reply_markup=get_confirm_delete_kb("answer", answer_id, f"answer_{answer_id}")
    )
    await callback.answer()


# Обработчик подтверждения удаления ответа
@router.callback_query(F.data.startswith("confirm_delete_answer_"))
async def confirm_delete_answer(callback: CallbackQuery, session: AsyncSession):
    """Обработчик подтверждения удаления ответа"""
    # Извлекаем ID ответа из callback_data
    answer_id = int(callback.data.split("_")[3])
    
    # Получаем информацию об ответе перед удалением
    result = await session.execute(select(Answer).where(Answer.answer_id == answer_id))
    answer = result.scalar_one_or_none()
    
    if not answer:
        await callback.message.edit_text(
            "Ответ не найден. Возможно, он уже был удален.",
            reply_markup=get_test_management_kb()
        )
        await callback.answer()
        return
    
    # Сохраняем question_id для возврата после удаления
    question_id = answer.question_id
    is_correct = answer.is_correct
    
    # Удаляем ответ
    try:
        await session.delete(answer)
        await session.commit()
        
        # Проверяем, был ли удаленный ответ правильным, и есть ли еще правильные ответы
        if is_correct:
            # Получаем все ответы на этот вопрос
            result = await session.execute(
                select(Answer).where(Answer.question_id == question_id)
            )
            remaining_answers = result.scalars().all()
            
            # Проверяем, есть ли среди оставшихся ответов хотя бы один правильный
            has_correct = any(a.is_correct for a in remaining_answers)
            
            if not has_correct and remaining_answers:
                # Если нет правильных ответов, выводим предупреждение
                await callback.message.edit_text(
                    f"⚠️ Внимание! После удаления у вопроса не осталось правильных ответов. "
                    f"Пользователи не смогут правильно ответить на этот вопрос.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="К списку ответов", callback_data=f"view_answers_{question_id}")
                    ]])
                )
                await callback.answer("⚠️ Внимание! У вопроса не осталось правильных ответов!")
                return
        
        # Обновляем позиции оставшихся ответов
        result = await session.execute(
            select(Answer).where(Answer.question_id == question_id).order_by(Answer.position)
        )
        remaining_answers = result.scalars().all()
        
        for i, ans in enumerate(remaining_answers):
            ans.position = i + 1
        
        await session.commit()
        
        # Сообщаем об успешном удалении
        await callback.message.edit_text(
            f"Ответ успешно удален.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="К списку ответов", callback_data=f"view_answers_{question_id}")
            ]])
        )
        
    except Exception as e:
        logger.error(f"Ошибка при удалении ответа: {e}")
        await callback.message.edit_text(
            f"Произошла ошибка при удалении ответа: {e}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Вернуться к ответу", callback_data=f"answer_{answer_id}")
            ]])
        )
    
    await callback.answer()


# Вспомогательные функции для тестирования

async def generate_test_statistics(session: AsyncSession, test_id: int) -> Dict[str, Any]:
    """
    Генерирует статистику по тесту
    
    Args:
        session: Сессия базы данных
        test_id: ID теста
    
    Returns:
        Dict: Словарь со статистикой
    """
    from sqlalchemy import func
    
    # Получаем общее количество попыток прохождения теста
    result = await session.execute(
        select(func.count(TestAttempt.attempt_id)).where(TestAttempt.test_id == test_id)
    )
    total_attempts = result.scalar() or 0
    
    # Получаем количество уникальных пользователей
    result = await session.execute(
        select(func.count(func.distinct(TestAttempt.user_id))).where(TestAttempt.test_id == test_id)
    )
    unique_users = result.scalar() or 0
    
    # Получаем средний балл
    result = await session.execute(
        select(func.avg(TestAttempt.score)).where(TestAttempt.test_id == test_id)
    )
    avg_score = result.scalar() or 0
    if avg_score:
        avg_score = round(avg_score, 1)
    
    # Получаем процент успешных прохождений
    result = await session.execute(
        select(
            func.sum(case((TestAttempt.is_passed == True, 1), else_=0)) * 100 / func.count(TestAttempt.attempt_id)
        ).where(TestAttempt.test_id == test_id)
    )
    success_rate = result.scalar() or 0
    if success_rate:
        success_rate = round(success_rate, 1)
    
    # Формируем результат
    return {
        "total_attempts": total_attempts,
        "unique_users": unique_users,
        "avg_score": avg_score,
        "success_rate": success_rate
    }


# Регистрация дополнительных обработчиков

# Обработчик для создания теста (общий)
@router.callback_query(F.data == "create_test")
async def create_test_command(callback: CallbackQuery, session: AsyncSession):
    """Обработчик создания нового теста (выбор статьи)"""
    # Получаем список статей для выбора
    result = await session.execute(
        select(Article).order_by(Article.title)
    )
    articles = result.scalars().all()
    
    if not articles:
        await callback.message.edit_text(
            "Не найдено ни одной статьи. Сначала создайте статью в библиотеке знаний.",
            reply_markup=get_test_management_kb()
        )
        await callback.answer()
        return
    
    # Создаем клавиатуру для выбора статьи
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    for article in articles:
        builder.add(InlineKeyboardButton(
            text=article.title,
            callback_data=f"create_test_for_article_{article.article_id}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="admin_tests"
    ))
    
    # Размещаем по одной кнопке в строку
    builder.adjust(1)
    
    await callback.message.edit_text(
        "Выберите статью, для которой хотите создать тест:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()
#################################################################################################

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