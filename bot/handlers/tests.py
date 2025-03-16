import sys
import os

if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update

from bot.database.models import Test, Question, Answer, TestAttempt, UserAnswer, User, Article
from bot.keyboards.user_kb import get_main_menu_kb
from bot.utils.logger import logger

# Создаем роутер для тестов
router = Router()

# Определяем состояния для FSM
class TestStates(StatesGroup):
    answering_questions = State()
    test_completed = State()


# Создаем клавиатуру для выбора теста
async def get_tests_kb(session: AsyncSession):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    # Получаем список тестов из БД
    result = await session.execute(
        select(Test, Article)
        .join(Article, Test.article_id == Article.article_id)
    )
    tests = result.all()
    
    # Добавляем кнопки для каждого теста
    for test, article in tests:
        builder.add(InlineKeyboardButton(
            text=f"{test.title} ({article.title})",
            callback_data=f"select_test_{test.test_id}"
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
async def get_answers_kb(session: AsyncSession, question_id):
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
            callback_data=f"answer_{answer.answer_id}"
        ))
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()


# Обработчик команды "Пройти тест"
@router.message(F.text == "📝 Пройти тест")
async def tests_command(message: Message, session: AsyncSession):
    await message.answer(
        "Виберіть тест для проходження:",
        reply_markup=await get_tests_kb(session)
    )


# Обработчик выбора теста
@router.callback_query(F.data.startswith("select_test_"))
async def select_test(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    # Извлекаем ID теста из callback_data
    test_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о тесте
    test_result = await session.execute(
        select(Test, Article)
        .join(Article, Test.article_id == Article.article_id)
        .where(Test.test_id == test_id)
    )
    test_data = test_result.first()
    
    if not test_data:
        await callback.message.edit_text(
            "Тест не знайдено. Виберіть інший тест:",
            reply_markup=await get_tests_kb(session)
        )
        await callback.answer()
        return
    
    test, article = test_data
    
    # Проверяем, нет ли у пользователя уже пройденного теста с максимальным баллом
    user_id = callback.from_user.id
    attempts_result = await session.execute(
        select(TestAttempt)
        .where(
            TestAttempt.user_id == user_id,
            TestAttempt.test_id == test_id,
            TestAttempt.score == 10
        )
    )
    max_score_attempt = attempts_result.scalar_one_or_none()
    
    if max_score_attempt:
        # У пользователя уже есть попытка с максимальным баллом
        await callback.message.edit_text(
            f"Ви вже пройшли тест \"{test.title}\" з максимальним балом (10)! "
            f"Виберіть інший тест:",
            reply_markup=await get_tests_kb(session)
        )
        await callback.answer()
        return
    
    # Получаем первый вопрос для теста
    questions_result = await session.execute(
        select(Question)
        .where(Question.test_id == test_id)
        .order_by(Question.question_id)
    )
    questions = questions_result.scalars().all()
    
    if not questions:
        await callback.message.edit_text(
            "У цьому тесті немає питань. Виберіть інший тест:",
            reply_markup=await get_tests_kb(session)
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
        current_question_index=0,
        questions=[q.question_id for q in questions],
        errors_count=0,
        score=10
    )
    
    # Показываем первый вопрос
    first_question = questions[0]
    
    await callback.message.edit_text(
        f"Тест: {test.title}\n\nПитання 1 з {len(questions)}:\n{first_question.question_text}",
        reply_markup=await get_answers_kb(session, first_question.question_id)
    )
    
    # Переходим в состояние ответа на вопросы
    await state.set_state(TestStates.answering_questions)
    
    await callback.answer()


# Обработчик выбора ответа на вопрос
@router.callback_query(TestStates.answering_questions, F.data.startswith("answer_"))
async def process_answer(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    # Извлекаем ID ответа из callback_data
    answer_id = int(callback.data.split("_")[1])
    
    # Получаем данные теста из состояния
    data = await state.get_data()
    test_id = data.get("test_id")
    attempt_id = data.get("attempt_id")
    current_question_index = data.get("current_question_index")
    questions = data.get("questions")
    errors_count = data.get("errors_count", 0)
    score = data.get("score", 10)
    
    # Получаем информацию о выбранном ответе
    answer_result = await session.execute(
        select(Answer, Question)
        .join(Question, Answer.question_id == Question.question_id)
        .where(Answer.answer_id == answer_id)
    )
    answer_data = answer_result.first()
    
    if not answer_data:
        await callback.answer("Помилка: відповідь не знайдена.")
        return
    
    answer, question = answer_data
    
    # Сохраняем ответ пользователя
    user_answer = UserAnswer(
        attempt_id=attempt_id,
        question_id=question.question_id,
        answer_id=answer.answer_id,
        is_correct=answer.is_correct
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
            await session.execute(
                update(TestAttempt)
                .where(TestAttempt.attempt_id == attempt_id)
                .values(score=score, is_passed=False)
            )
            await session.commit()
            
            # Завершаем тест из-за большого количества ошибок
            await callback.message.answer(
                "⚠️ Ви допустили 5 помилок. Будь ласка, перечитайте матеріал і спробуйте ще раз. "
                "Натисніть \"🔄 Почати тест заново\", щоб спробувати знову.",
                reply_markup=await get_restart_test_kb(test_id)
            )
            
            # Выходим из состояния ответа на вопросы
            await state.clear()
            return
    
    # Проверяем, есть ли еще вопросы
    current_question_index += 1
    
    if current_question_index < len(questions):
        # Если есть еще вопросы, показываем следующий
        next_question_id = questions[current_question_index]
        
        # Получаем информацию о следующем вопросе
        question_result = await session.execute(
            select(Question).where(Question.question_id == next_question_id)
        )
        next_question = question_result.scalar_one_or_none()
        
        if not next_question:
            await callback.message.answer(
                "Помилка: питання не знайдено. Тест завершено.",
                reply_markup=get_main_menu_kb()
            )
            await state.clear()
            return
        
        # Обновляем индекс текущего вопроса в состоянии
        await state.update_data(current_question_index=current_question_index)
        
        # Показываем следующий вопрос
        await callback.message.answer(
            f"Питання {current_question_index + 1} з {len(questions)}:\n{next_question.question_text}",
            reply_markup=await get_answers_kb(session, next_question.question_id)
        )
    else:
        # Если вопросов больше нет, завершаем тест
        # Обновляем данные попытки в БД
        is_passed = score >= (10 * 0.8)  # 80% от максимального балла
        
        await session.execute(
            update(TestAttempt)
            .where(TestAttempt.attempt_id == attempt_id)
            .values(score=score, is_passed=is_passed)
        )
        await session.commit()
        
        # Получаем информацию о тесте
        test_result = await session.execute(
            select(Test).where(Test.test_id == test_id)
        )
        test = test_result.scalar_one_or_none()
        
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
        if score < 10:
            # Если не набран максимальный балл, предлагаем пройти тест еще раз
            await callback.message.answer(
                "Оберіть дію:",
                reply_markup=await get_test_completion_kb(test_id)
            )
        else:
            # Если набран максимальный балл, завершаем тест
            await callback.message.answer(
                "Вітаємо з успішним проходженням тесту!",
                reply_markup=get_main_menu_kb()
            )
        
        # Переходим в состояние завершения теста
        await state.set_state(TestStates.test_completed)
    
    await callback.answer()


# Создаем клавиатуру для перезапуска теста
async def get_restart_test_kb(test_id):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="🔄 Почати тест заново",
        callback_data=f"restart_test_{test_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="📚 Повернутися до бібліотеки",
        callback_data="back_to_library"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🏠 Головне меню",
        callback_data="back_to_main_menu"
    ))
    
    builder.adjust(1)
    
    return builder.as_markup()


# Создаем клавиатуру для завершения теста
async def get_test_completion_kb(test_id):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="🔄 Пройти тест ще раз",
        callback_data=f"restart_test_{test_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="✅ Завершити тест",
        callback_data=f"complete_test_{test_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="📚 Повернутися до бібліотеки",
        callback_data="back_to_library"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🏠 Головне меню",
        callback_data="back_to_main_menu"
    ))
    
    builder.adjust(1)
    
    return builder.as_markup()


# Обработчик перезапуска теста
@router.callback_query(F.data.startswith("restart_test_"))
async def restart_test(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    # Извлекаем ID теста из callback_data
    test_id = int(callback.data.split("_")[2])
    
    # Сбрасываем состояние
    await state.clear()
    
    # Перезапускаем тест
    await select_test(callback, state, session)


# Обработчик завершения теста
@router.callback_query(F.data.startswith("complete_test_"))
async def complete_test(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Тест завершено. Дякуємо за участь!",
    )
    
    await callback.message.answer(
        "Виберіть опцію з меню нижче:",
        reply_markup=get_main_menu_kb()
    )
    
    await state.clear()
    await callback.answer()


# Обработчик для старта теста из статьи
@router.callback_query(F.data.startswith("start_test_"))
async def start_test_from_article(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    # Извлекаем ID теста из callback_data
    test_id = int(callback.data.split("_")[2])
    
    # Имитируем выбор теста из списка
    callback.data = f"select_test_{test_id}"
    await select_test(callback, state, session)


# Обработчик для возврата в библиотеку знаний
@router.callback_query(F.data == "back_to_library")
async def back_to_library(callback: CallbackQuery, session: AsyncSession):
    await callback.message.edit_text(
        "Ласкаво просимо до бібліотеки знань! Виберіть категорію:",
        reply_markup=await get_categories_kb(session)
    )
    await callback.answer()


# Вспомогательная функция для получения клавиатуры категорий
async def get_categories_kb(session: AsyncSession, parent_id=None, level=1):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    from bot.database.models import Category
    
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


# Обработчик для возврата в главное меню
@router.callback_query(F.data == "back_to_main_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user_id = callback.from_user.id
    
    # Проверяем, является ли пользователь администратором
    result = await session.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if user and user.is_admin:
        from bot.keyboards.admin_kb import get_admin_menu_kb
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
    
    await state.clear()
    await callback.answer()


# Экспорт роутера
if __name__ == "__main__":
    print("Модуль tests.py успешно загружен")
    print("router определен:", router is not None)
    