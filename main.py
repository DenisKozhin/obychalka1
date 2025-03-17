import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import KeyboardButton, InlineKeyboardButton
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from bot.config import BOT_TOKEN, ADMIN_IDS
from bot.database.database import Base, async_engine, AsyncSessionLocal
from bot.database.models import User, City, Store
from bot.utils.logger import logger

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Определяем состояния для машины состояний регистрации
class RegistrationStates(StatesGroup):
    waiting_for_name = State()  # Ожидание ввода имени
    waiting_for_city = State()  # Ожидание выбора города
    waiting_for_store = State()  # Ожидание выбора магазина
    edit_profile = State()         # Редактирование профиля
    edit_profile_name = State()    # Редактирование имени
    edit_profile_city = State()    # Выбор нового города
    edit_profile_store = State()   # Выбор нового магазина

# Определяем состояния для администратора
class AdminStates(StatesGroup):
    waiting_for_city_name = State()  # Ожидание ввода названия города
    waiting_for_store_name = State()
    waiting_for_city_for_store = State()
    waiting_for_confirm_delete = State()
    waiting_for_store_new_name = State()
    waiting_for_city_new_name = State()

# Middleware для работы с базой данных
class DbSessionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        async with AsyncSessionLocal() as session:
            data["session"] = session
            return await handler(event, data)

# Создание основной клавиатуры
def get_main_menu_kb():
    """Клавиатура главного меню пользователя"""
    builder = ReplyKeyboardBuilder()
    
    builder.add(
        KeyboardButton(text="📚 Бібліотека знань"),
        KeyboardButton(text="📝 Пройти тест"),
        KeyboardButton(text="🏆 Мої бали"),
        KeyboardButton(text="📢 Оголошення"),
        KeyboardButton(text="👤 Мій профіль")  # Добавлена кнопка профиля
    )
    
    # Размещаем кнопки в 2 строки по 2 кнопки и последнюю отдельно
    builder.adjust(2, 2, 1)
    
    return builder.as_markup(resize_keyboard=True)

# Создание клавиатуры админ-меню
def get_admin_menu_kb():
    builder = InlineKeyboardBuilder()
    
    buttons = [
        InlineKeyboardButton(text="📄 Статьи", callback_data="admin_articles"),
        InlineKeyboardButton(text="✅ Тесты", callback_data="admin_tests"),
        InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"),
        InlineKeyboardButton(text="🏙 Управление городами и магазинами", callback_data="admin_locations"),
        InlineKeyboardButton(text="🗑 Удаление данных", callback_data="admin_delete"),
        InlineKeyboardButton(text="👤 Обычный режим", callback_data="user_mode")
    ]
    
    for button in buttons:
        builder.add(button)
    
    # Размещаем по одной кнопке в строку
    builder.adjust(1)
    
    return builder.as_markup()

# Клавиатура для управления городами и магазинами
def get_locations_management_kb():
    builder = InlineKeyboardBuilder()
    
    buttons = [
        InlineKeyboardButton(text="🏙 Добавить город", callback_data="add_city"),
        InlineKeyboardButton(text="🏙 Редактировать города", callback_data="edit_cities"),
        InlineKeyboardButton(text="🏙 Список городов", callback_data="list_cities"),
        InlineKeyboardButton(text="🏪 Добавить магазин", callback_data="add_store"),
        InlineKeyboardButton(text="🏪 Редактировать магазины", callback_data="edit_stores"),
        InlineKeyboardButton(text="🏪 Список магазинов", callback_data="list_stores"),
        InlineKeyboardButton(text="🔙 Назад в админ-меню", callback_data="back_to_admin")
    ]
    
    for button in buttons:
        builder.add(button)
    
    # Размещаем по одной кнопке в строку
    builder.adjust(1)
    
    return builder.as_markup()

# Создание клавиатуры с городами
async def get_cities_kb(session: AsyncSession):
    builder = InlineKeyboardBuilder()
    
    # Получаем список городов из БД
    result = await session.execute(select(City))
    cities = result.scalars().all()
    
    # Если городов нет, создаем тестовые города
    if not cities:
        default_cities = ["Київ", "Львів", "Одеса", "Харків", "Дніпро"]
        for city_name in default_cities:
            city = City(name=city_name)
            session.add(city)
        await session.commit()
        
        # Получаем список городов снова
        result = await session.execute(select(City))
        cities = result.scalars().all()
    
    # Добавляем кнопки для каждого города
    for city in cities:
        builder.add(InlineKeyboardButton(
            text=city.name,
            callback_data=f"city_{city.city_id}"
        ))
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()

# Функция для создания клавиатуры с магазинами
async def get_stores_kb(session: AsyncSession, city_id: int):
    builder = InlineKeyboardBuilder()
    
    try:
        # Получаем список магазинов для выбранного города
        result = await session.execute(
            select(Store).where(Store.city_id == city_id)
        )
        stores = result.scalars().all()
        
        # Если магазинов нет, создаем тестовые магазины
        if not stores:
            # Получаем город
            city_result = await session.execute(select(City).where(City.city_id == city_id))
            city = city_result.scalar_one_or_none()
            
            if city:
                # Создаем несколько магазинов для этого города
                store_count = 3  # Количество тестовых магазинов
                for i in range(1, store_count + 1):
                    store = Store(name=f"Магазин {city.name} #{i}", city_id=city_id)
                    session.add(store)
                await session.commit()
                
                # Получаем список магазинов снова
                result = await session.execute(select(Store).where(Store.city_id == city_id))
                stores = result.scalars().all()
        
        # Добавляем кнопки для каждого магазина
        for store in stores:
            builder.add(InlineKeyboardButton(
                text=store.name,
                callback_data=f"store_{store.store_id}"
            ))
        
        # Добавляем кнопку "Назад" для возврата к выбору города
        builder.add(InlineKeyboardButton(
            text="🔙 Назад до вибору міста",
            callback_data="back_to_cities"
        ))
    
    except Exception as e:
        logger.error(f"Ошибка при создании клавиатуры магазинов: {e}")
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()

# Получение списка городов для административной панели
async def get_admin_cities_kb(session: AsyncSession):
    builder = InlineKeyboardBuilder()
    
    # Получаем список городов из БД
    result = await session.execute(select(City))
    cities = result.scalars().all()
    
    # Добавляем кнопки для каждого города
    for city in cities:
        builder.add(InlineKeyboardButton(
            text=city.name,
            callback_data=f"admin_city_{city.city_id}"
        ))
    
    # Добавляем кнопку "Назад"
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_locations"
    ))
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()

# Создание клавиатуры для редактирования профиля
def get_edit_profile_kb():
    builder = InlineKeyboardBuilder()
    
    buttons = [
        InlineKeyboardButton(text="✏️ Изменить имя и фамилию", callback_data="edit_profile_name"),
        InlineKeyboardButton(text="🏙 Изменить город", callback_data="edit_profile_city"),
        InlineKeyboardButton(text="🏪 Изменить магазин", callback_data="edit_profile_store"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main_menu")
    ]
    
    for button in buttons:
        builder.add(button)
    
    # Размещаем по одной кнопке в строку
    builder.adjust(1)
    
    return builder.as_markup()

# Клавиатура для подтверждения
def get_confirmation_kb(action, entity_id):
    builder = InlineKeyboardBuilder()
    
    builder.add(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{action}_{entity_id}"),
        InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_delete")
    )
    
    # Размещаем по одной кнопке в строку
    builder.adjust(1)
    
    return builder.as_markup()

# Обработчик команды /start
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession):
    user_id = message.from_user.id
    
    try:
        # Проверяем, зарегистрирован ли пользователь
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()
        
        if user:
            # Если пользователь уже зарегистрирован, показываем приветствие
            if user.is_admin:
                await message.answer(
                    f"З поверненням, {user.first_name} {user.last_name}!\n"
                    f"Ви є адміністратором. Виберіть опцію:",
                    reply_markup=get_admin_menu_kb()
                )
            else:
                await message.answer(
                    f"З поверненням, {user.first_name}! Виберіть опцію з меню нижче:",
                    reply_markup=get_main_menu_kb()
                )
        else:
            # Если пользователь не зарегистрирован, начинаем процесс регистрации
            await message.answer(
                "Вітаю! Для початку роботи з ботом, будь ласка, заповніть наступні дані."
                "\n\nЯк вас звати? Введіть ім'я та прізвище:"
            )
            # Устанавливаем состояние "ожидание имени"
            await state.set_state(RegistrationStates.waiting_for_name)
    except Exception as e:
        logger.error(f"Ошибка в cmd_start: {e}")
        await message.answer("Виникла помилка. Спробуйте пізніше або зверніться до адміністратора.")

# Обработчик команды /help
async def cmd_help(message: Message):
    await message.answer(
        "🤖 <b>Допомога по боту:</b>\n\n"
        "Цей бот допоможе вам:\n"
        "📚 Вивчати інформацію про товари\n"
        "📝 Проходити тести для перевірки знань\n"
        "🏆 Відстежувати свій рейтинг та бали\n"
        "📢 Отримувати оголошення від адміністрації\n\n"
        "<b>Доступні команди:</b>\n"
        "/start - Запустити бота / повернутися в головне меню\n"
        "/help - Показати цю довідку\n"
        "/admin - Доступ до панелі адміністратора (тільки для адміністраторів)",
        parse_mode="HTML"
    )

# Обработчик для команды /admin
async def cmd_admin(message: Message, session: AsyncSession):
    user_id = message.from_user.id
    
    # Проверяем, является ли пользователь администратором
    if user_id in ADMIN_IDS:
        # Обновляем статус в базе данных
        user = await session.execute(select(User).where(User.user_id == user_id))
        user = user.scalar_one_or_none()
        
        if user:
            user.is_admin = True
            await session.commit()
        
        # Показываем админ-меню
        await message.answer(
            "Панель администратора. Выберите опцию:",
            reply_markup=get_admin_menu_kb()
        )
    else:
        await message.answer("У вас нет прав доступа к административной панели.")

# Обработчик для перехода в пользовательский режим
async def user_mode_command(callback: CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    
    # Получаем информацию о пользователе
    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    
    if user:
        await callback.message.edit_text(
            "Ви повернулись до звичайного режиму."
        )
        await callback.message.answer(
            "Виберіть опцію з меню користувача:",
            reply_markup=get_main_menu_kb()
        )
    else:
        await callback.message.edit_text(
            "Ви не зареєстровані. Використайте команду /start для реєстрації."
        )
    
    await callback.answer()

# Обработчик ввода имени
async def process_name(message: Message, state: FSMContext, session: AsyncSession):
    # Получаем введенное имя
    full_name = message.text.strip()
    
    # Проверяем, что имя состоит минимум из двух слов (имя и фамилия)
    name_parts = full_name.split()
    if len(name_parts) < 2:
        await message.answer(
            "Будь ласка, введіть повне ім'я та прізвище, розділені пробілом."
        )
        return
    
    try:
        # Сохраняем имя и фамилию в данных состояния
        await state.update_data(first_name=name_parts[0], last_name=' '.join(name_parts[1:]))
        
        # Просим пользователя выбрать город
        await message.answer(
            "Дякую! Тепер, будь ласка, виберіть ваше місто:",
            reply_markup=await get_cities_kb(session)
        )
        
        # Переходим к состоянию выбора города
        await state.set_state(RegistrationStates.waiting_for_city)
    except Exception as e:
        logger.error(f"Ошибка в process_name: {e}")
        await message.answer("Виникла помилка. Спробуйте пізніше або зверніться до адміністратора.")

# Обработчик выбора города (исправленный)
async def process_city_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        # Извлекаем ID выбранного города из callback_data
        city_id = int(callback.data.split("_")[1])
        
        # Сохраняем ID города в данных состояния
        await state.update_data(city_id=city_id)
        
        # Получаем текущее состояние
        current_state = await state.get_state()
        
        # Получаем информацию о выбранном городе
        result = await session.execute(select(City).where(City.city_id == city_id))
        city = result.scalar_one_or_none()
        
        if city:
            # Просим пользователя выбрать магазин
            await callback.message.edit_text(
                f"Ви вибрали місто: {city.name}\nТепер, будь ласка, виберіть ваш магазин:",
                reply_markup=await get_stores_kb(session, city_id)
            )
            
            # Переходим к следующему состоянию в зависимости от текущего
            if current_state == RegistrationStates.waiting_for_city:
                await state.set_state(RegistrationStates.waiting_for_store)
            elif current_state == RegistrationStates.edit_profile_city:
                await state.set_state(RegistrationStates.edit_profile_store)
        else:
            # Если город не найден, просим выбрать снова
            await callback.message.edit_text(
                "На жаль, виникла помилка. Будь ласка, виберіть місто ще раз:",
                reply_markup=await get_cities_kb(session)
            )
    except Exception as e:
        logger.error(f"Ошибка в process_city_selection: {e}")
        await callback.message.edit_text("Виникла помилка. Спробуйте пізніше або зверніться до адміністратора.")
    
    await callback.answer()

# Обработчик возврата к выбору города
async def back_to_city_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        # Возвращаемся к выбору города
        await callback.message.edit_text(
            "Будь ласка, виберіть ваше місто:",
            reply_markup=await get_cities_kb(session)
        )
        
        # Возвращаемся к состоянию выбора города
        current_state = await state.get_state()
        if current_state == RegistrationStates.waiting_for_store:
            await state.set_state(RegistrationStates.waiting_for_city)
        elif current_state == RegistrationStates.edit_profile_store:
            await state.set_state(RegistrationStates.edit_profile_city)
    except Exception as e:
        logger.error(f"Ошибка в back_to_city_selection: {e}")
        await callback.message.edit_text("Виникла помилка. Спробуйте пізніше або зверніться до адміністратора.")
    
    await callback.answer()

# Обработчик выбора магазина
async def process_store_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        # Извлекаем ID выбранного магазина из callback_data
        store_id = int(callback.data.split("_")[1])
        
        # Получаем данные состояния
        user_data = await state.get_data()
        current_state = await state.get_state()
        
        if current_state == RegistrationStates.waiting_for_store:
            # Это новая регистрация
            first_name = user_data.get('first_name')
            last_name = user_data.get('last_name')
            city_id = user_data.get('city_id')
            
            if not first_name or not last_name or not city_id:
                await callback.message.edit_text(
                    "Помилка: відсутні дані користувача. Почніть реєстрацію заново з команди /start"
                )
                await state.clear()
                await callback.answer()
                return
            
            # Проверяем, является ли пользователь администратором
            is_admin = callback.from_user.id in ADMIN_IDS
            
            # Создаем нового пользователя в базе данных
            new_user = User(
                user_id=callback.from_user.id,
                first_name=first_name,
                last_name=last_name,
                city_id=city_id,
                store_id=store_id,
                is_admin=is_admin
            )
            
            session.add(new_user)
            await session.commit()
            
            # Получаем информацию о городе и магазине
            city_result = await session.execute(select(City).where(City.city_id == city_id))
            city = city_result.scalar_one_or_none()
            
            store_result = await session.execute(select(Store).where(Store.store_id == store_id))
            store = store_result.scalar_one_or_none()
            
            city_name = city.name if city else "Невідоме місто"
            store_name = store.name if store else "Невідомий магазин"
            
            # Завершаем регистрацию и показываем главное меню
            await callback.message.edit_text(
                f"Реєстрація завершена!\n\n"
                f"Ім'я: {first_name} {last_name}\n"
                f"Місто: {city_name}\n"
                f"Магазин: {store_name}\n\n"
                f"Тепер ви можете користуватися всіма функціями бота."
            )
            
            # Показываем соответствующее меню
            if is_admin:
                await callback.message.answer(
                    "Ви є адміністратором. Виберіть опцію:",
                    reply_markup=get_admin_menu_kb()
                )
            else:
                await callback.message.answer(
                    "Виберіть опцію з меню нижче:",
                    reply_markup=get_main_menu_kb()
                )
        
        elif current_state == RegistrationStates.edit_profile_store:
            # Редактирование профиля
            city_id = user_data.get('city_id')
            
            # Получаем пользователя из БД
            user_result = await session.execute(
                select(User).where(User.user_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                await callback.message.edit_text(
                    "Помилка: профіль не знайдено. Будь ласка, зареєструйтеся з допомогою команди /start."
                )
                await state.clear()
                await callback.answer()
                return
            
            # Обновляем город и магазин пользователя
            user.city_id = city_id
            user.store_id = store_id
            await session.commit()
            
            # Получаем информацию о городе и магазине
            city_result = await session.execute(select(City).where(City.city_id == city_id))
            city = city_result.scalar_one_or_none()
            
            store_result = await session.execute(select(Store).where(Store.store_id == store_id))
            store = store_result.scalar_one_or_none()
            
            city_name = city.name if city else "Невідоме місто"
            store_name = store.name if store else "Невідомий магазин"
            
            # Уведомляем об успешном обновлении
            await callback.message.edit_text(
                f"Ваш профіль оновлено!\n\n"
                f"Ім'я: {user.first_name} {user.last_name}\n"
                f"Нове місто: {city_name}\n"
                f"Новий магазин: {store_name}"
            )
            
            # Показываем главное меню
            await callback.message.answer(
                "Виберіть опцію з меню нижче:",
                reply_markup=get_main_menu_kb()
            )
    
    except Exception as e:
        logger.error(f"Ошибка в process_store_selection: {e}")
        await callback.message.edit_text("Виникла помилка. Спробуйте пізніше або зверніться до адміністратора.")
    
    # Сбрасываем состояние
    await state.clear()
    await callback.answer()

# Обработчик для профиля пользователя
async def profile_command(message: Message, session: AsyncSession):
    user_id = message.from_user.id
    
    # Получаем информацию о пользователе
    result = await session.execute(
        select(User, City, Store)
        .join(City, User.city_id == City.city_id)
        .join(Store, User.store_id == Store.store_id)
        .where(User.user_id == user_id)
    )
    user_data = result.first()
    
    if user_data:
        user, city, store = user_data
        await message.answer(
            f"Ваш профіль:\n\n"
            f"Ім'я: {user.first_name} {user.last_name}\n"
            f"Місто: {city.name}\n"
            f"Магазин: {store.name}\n\n"
            f"Що бажаєте змінити?",
            reply_markup=get_edit_profile_kb()
        )
    else:
        await message.answer(
            "Ви ще не зареєстровані. Використайте команду /start для реєстрації."
        )

# Обработчик редактирования имени пользователя
async def edit_profile_name_command(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Введіть нове ім'я та прізвище:"
    )
    await state.set_state(RegistrationStates.edit_profile_name)
    await callback.answer()

# Обработчик ввода нового имени
async def process_edit_name(message: Message, state: FSMContext, session: AsyncSession):
    # Получаем введенное имя
    full_name = message.text.strip()
    
    # Проверяем, что имя состоит минимум из двух слов (имя и фамилия)
    name_parts = full_name.split()
    if len(name_parts) < 2:
        await message.answer(
            "Будь ласка, введіть повне ім'я та прізвище, розділені пробілом."
        )
        return
    
    try:
        # Получаем пользователя из БД
        user_result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            await message.answer(
                "Помилка: профіль не знайдено. Будь ласка, зареєструйтеся з допомогою команди /start."
            )
            await state.clear()
            return
        
        # Обновляем имя пользователя
        user.first_name = name_parts[0]
        user.last_name = ' '.join(name_parts[1:])
        await session.commit()
        
        await message.answer(
            f"Ваше ім'я змінено на {full_name}.",
            reply_markup=get_main_menu_kb()
        )
    except Exception as e:
        logger.error(f"Ошибка в process_edit_name: {e}")
        await message.answer("Виникла помилка. Спробуйте пізніше або зверніться до адміністратора.")
    
    # Сбрасываем состояние
    await state.clear()

# Обработчик редактирования города
async def edit_profile_city_command(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        # Получаем пользователя из БД
        user_result = await session.execute(
            select(User).where(User.user_id == callback.from_user.id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            await callback.message.edit_text(
                "Помилка: профіль не знайдено. Будь ласка, зареєструйтеся з допомогою команди /start."
            )
            await callback.answer()
            return
        
        # Сохраняем данные о пользователе в состоянии
        await state.update_data(
            user_id=user.user_id,
            first_name=user.first_name,
            last_name=user.last_name,
            city_id=user.city_id,
            store_id=user.store_id,
            is_admin=user.is_admin
        )
        
        # Показываем список городов
        await callback.message.edit_text(
            "Виберіть новий город:",
            reply_markup=await get_cities_kb(session)
        )
        
        # Устанавливаем состояние выбора города
        await state.set_state(RegistrationStates.edit_profile_city)
    except Exception as e:
        logger.error(f"Ошибка в edit_profile_city_command: {e}")
        await callback.message.edit_text("Виникла помилка. Спробуйте пізніше або зверніться до адміністратора.")
    
    await callback.answer()

# Обработчик редактирования магазина
async def edit_profile_store_command(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        # Получаем пользователя из БД
        user_result = await session.execute(
            select(User).where(User.user_id == callback.from_user.id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            await callback.message.edit_text(
                "Помилка: профіль не знайдено. Почніть реєстрацію заново з команди /start."
            )
            await callback.answer()
            return
        
        # Получаем информацию о городе
        city_result = await session.execute(
            select(City).where(City.city_id == user.city_id)
        )
        city = city_result.scalar_one_or_none()
        
        if not city:
            await callback.message.edit_text(
                "Помилка: місто не знайдено. Спочатку оновіть місто."
            )
            await callback.answer()
            return
        
        # Сохраняем ID города в состоянии
        await state.update_data(city_id=user.city_id)
        
        # Показываем список магазинов выбранного города
        await callback.message.edit_text(
            f"Виберіть новий магазин для міста {city.name}:",
            reply_markup=await get_stores_kb(session, user.city_id)
        )
        
        # Устанавливаем состояние редактирования магазина
        await state.set_state(RegistrationStates.edit_profile_store)
    except Exception as e:
        logger.error(f"Ошибка в edit_profile_store_command: {e}")
        await callback.message.edit_text("Виникла помилка. Спробуйте пізніше або зверніться до адміністратора.")
    
    await callback.answer()

# Обработчик возврата в главное меню
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
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
    
    await state.clear()
    await callback.answer()

# Обработчик для локаций администратора
async def admin_locations(callback: CallbackQuery):
    await callback.message.edit_text(
        "Управление городами и магазинами. Выберите действие:",
        reply_markup=get_locations_management_kb()
    )
    await callback.answer()

# Обработчик для возвращения к админ-меню
async def back_to_admin_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "Панель администратора. Выберите опцию:",
        reply_markup=get_admin_menu_kb()
    )
    await callback.answer()

# Обработчик для возврата к управлению локациями
async def back_to_locations(callback: CallbackQuery):
    await callback.message.edit_text(
        "Управление городами и магазинами. Выберите действие:",
        reply_markup=get_locations_management_kb()
    )
    await callback.answer()

# Обработчик добавления города
async def add_city_command(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Введите название нового города:"
    )
    await state.set_state(AdminStates.waiting_for_city_name)
    await callback.answer()

# Обработчик ввода названия города
async def process_city_name(message: Message, state: FSMContext, session: AsyncSession):
    city_name = message.text.strip()
    
    try:
        # Добавляем город в базу данных
        city = City(name=city_name)
        session.add(city)
        await session.commit()
        
        await message.answer(
            f"Город '{city_name}' успешно добавлен.",
            reply_markup=get_locations_management_kb()
        )
    except Exception as e:
        logger.error(f"Ошибка при добавлении города: {e}")
        await message.answer(
            f"Город '{city_name}' уже существует или произошла другая ошибка.",
            reply_markup=get_locations_management_kb()
        )
    
    await state.clear()

# Обработчик просмотра списка городов
async def list_cities_command(callback: CallbackQuery, session: AsyncSession):
    # Получаем список городов
    result = await session.execute(select(City))
    cities = result.scalars().all()
    
    if not cities:
        await callback.message.edit_text(
            "Список городов пуст.",
            reply_markup=get_locations_management_kb()
        )
        await callback.answer()
        return
    
    # Создаем сообщение со списком городов
    cities_list = "\n".join([f"🏙 {city.name} (ID: {city.city_id})" for city in cities])
    
    await callback.message.edit_text(
        f"Список городов:\n\n{cities_list}\n\nВыберите действие:",
        reply_markup=get_locations_management_kb()
    )
    await callback.answer()

# Обработчик добавления магазина
async def add_store_command(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await callback.message.edit_text(
        "Выберите город для нового магазина:",
        reply_markup=await get_admin_cities_kb(session)
    )
    await state.set_state(AdminStates.waiting_for_city_for_store)
    await callback.answer()

# Обработчик редактирования городов
async def edit_cities_command(callback: CallbackQuery, session: AsyncSession):
    result = await session.execute(select(City))
    cities = result.scalars().all()
    
    if not cities:
        await callback.message.edit_text(
            "Список городов пуст.",
            reply_markup=get_locations_management_kb()
        )
        await callback.answer()
        return
    
    # Создаем клавиатуру для выбора города
    builder = InlineKeyboardBuilder()
    
    for city in cities:
        builder.add(InlineKeyboardButton(
            text=city.name,
            callback_data=f"edit_city_{city.city_id}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_locations"
    ))
    
    builder.adjust(1)
    
    await callback.message.edit_text(
        "Выберите город для редактирования:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

# Обработчик выбора города для редактирования
async def edit_city_name_command(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    # Извлекаем ID города из callback_data
    city_id = int(callback.data.split("_")[2])
    
    # Сохраняем ID города в состоянии
    await state.update_data(city_id=city_id)
    
    # Получаем информацию о городе
    result = await session.execute(select(City).where(City.city_id == city_id))
    city = result.scalar_one_or_none()
    
    if not city:
        await callback.message.edit_text(
            "Город не найден.",
            reply_markup=get_locations_management_kb()
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        f"Текущее название города: {city.name}\n\nВведите новое название города:"
    )
    await state.set_state(AdminStates.waiting_for_city_new_name)
    await callback.answer()

# Обработчик ввода нового названия города
async def process_edit_city_name(message: Message, state: FSMContext, session: AsyncSession):
    # Получаем новое название города
    new_name = message.text.strip()
    
    # Получаем данные состояния
    data = await state.get_data()
    city_id = data.get("city_id")
    
    if not city_id:
        await message.answer(
            "Ошибка: ID города не найден.",
            reply_markup=get_locations_management_kb()
        )
        await state.clear()
        return
    
    try:
        # Получаем город
        result = await session.execute(select(City).where(City.city_id == city_id))
        city = result.scalar_one_or_none()
        
        if not city:
            await message.answer(
                "Город не найден.",
                reply_markup=get_locations_management_kb()
            )
            await state.clear()
            return
        
        old_name = city.name
        city.name = new_name
        await session.commit()
        
        await message.answer(
            f"Название города изменено с '{old_name}' на '{new_name}'.",
            reply_markup=get_locations_management_kb()
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании города: {e}")
        await message.answer(
            f"Ошибка при редактировании города: {e}",
            reply_markup=get_locations_management_kb()
        )
    
    await state.clear()
# Обработчик редактирования магазинов
async def edit_stores_command(callback: CallbackQuery, session: AsyncSession):
    # Получаем список городов для выбора
    result = await session.execute(select(City))
    cities = result.scalars().all()
    
    if not cities:
        await callback.message.edit_text(
            "Сначала добавьте города.",
            reply_markup=get_locations_management_kb()
        )
        await callback.answer()
        return
    
    # Создаем клавиатуру для выбора города
    builder = InlineKeyboardBuilder()
    
    for city in cities:
        builder.add(InlineKeyboardButton(
            text=city.name,
            callback_data=f"edit_stores_city_{city.city_id}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_locations"
    ))
    
    builder.adjust(1)
    
    await callback.message.edit_text(
        "Выберите город, магазины которого вы хотите редактировать:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

# Обработчик выбора города для редактирования магазинов
async def edit_stores_city(callback: CallbackQuery, session: AsyncSession):
    # Извлекаем ID города из callback_data
    city_id = int(callback.data.split("_")[3])
    
    # Получаем название города
    city_result = await session.execute(select(City).where(City.city_id == city_id))
    city = city_result.scalar_one_or_none()
    
    if not city:
        await callback.message.edit_text(
            "Город не найден.",
            reply_markup=get_locations_management_kb()
        )
        await callback.answer()
        return
    
    # Получаем список магазинов в этом городе
    stores_result = await session.execute(select(Store).where(Store.city_id == city_id))
    stores = stores_result.scalars().all()
    
    if not stores:
        await callback.message.edit_text(
            f"В городе '{city.name}' нет магазинов.",
            reply_markup=get_locations_management_kb()
        )
        await callback.answer()
        return
    
    # Создаем клавиатуру для выбора магазина
    builder = InlineKeyboardBuilder()
    
    for store in stores:
        builder.add(InlineKeyboardButton(
            text=store.name,
            callback_data=f"edit_store_{store.store_id}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="edit_stores"
    ))
    
    builder.adjust(1)
    
    await callback.message.edit_text(
        f"Выберите магазин для редактирования в городе '{city.name}':",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

# Обработчик выбора магазина для редактирования
async def edit_store_name_command(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    # Извлекаем ID магазина из callback_data
    store_id = int(callback.data.split("_")[2])
    
    # Сохраняем ID магазина в состоянии
    await state.update_data(store_id=store_id)
    
    # Получаем информацию о магазине
    result = await session.execute(select(Store).where(Store.store_id == store_id))
    store = result.scalar_one_or_none()
    
    if not store:
        await callback.message.edit_text(
            "Магазин не найден.",
            reply_markup=get_locations_management_kb()
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        f"Текущее название магазина: {store.name}\n\nВведите новое название магазина:"
    )
    await state.set_state(AdminStates.waiting_for_store_new_name)
    await callback.answer()

# Обработчик ввода нового названия магазина
async def process_edit_store_name(message: Message, state: FSMContext, session: AsyncSession):
    # Получаем новое название магазина
    new_name = message.text.strip()
    
    # Получаем данные состояния
    data = await state.get_data()
    store_id = data.get("store_id")
    
    if not store_id:
        await message.answer(
            "Ошибка: ID магазина не найден.",
            reply_markup=get_locations_management_kb()
        )
        await state.clear()
        return
    
    try:
        # Получаем магазин
        result = await session.execute(select(Store).where(Store.store_id == store_id))
        store = result.scalar_one_or_none()
        
        if not store:
            await message.answer(
                "Магазин не найден.",
                reply_markup=get_locations_management_kb()
            )
            await state.clear()
            return
        
        old_name = store.name
        store.name = new_name
        await session.commit()
        
        await message.answer(
            f"Название магазина изменено с '{old_name}' на '{new_name}'.",
            reply_markup=get_locations_management_kb()
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании магазина: {e}")
        await message.answer(
            f"Ошибка при редактировании магазина: {e}",
            reply_markup=get_locations_management_kb()
        )
    
    await state.clear()










# Обработчик выбора города для магазина
async def process_city_for_store(callback: CallbackQuery, state: FSMContext):
    # Извлекаем ID города из callback_data
    city_id = int(callback.data.split("_")[2])
    
    # Сохраняем ID города
    await state.update_data(city_id=city_id)
    
    # Запрашиваем название магазина
    await callback.message.edit_text(
        "Введите название нового магазина:"
    )
    await state.set_state(AdminStates.waiting_for_store_name)
    await callback.answer()

# Обработчик ввода названия магазина
async def process_store_name(message: Message, state: FSMContext, session: AsyncSession):
    store_name = message.text.strip()
    
    # Получаем данные состояния
    user_data = await state.get_data()
    city_id = user_data.get('city_id')
    
    if not city_id:
        await message.answer(
            "Ошибка: не выбран город. Попробуйте снова.",
            reply_markup=get_locations_management_kb()
        )
        await state.clear()
        return
    
    try:
        # Добавляем магазин в базу данных
        store = Store(name=store_name, city_id=city_id)
        session.add(store)
        await session.commit()
        
        # Получаем название города
        city_result = await session.execute(select(City).where(City.city_id == city_id))
        city = city_result.scalar_one_or_none()
        city_name = city.name if city else "Неизвестный город"
        
        await message.answer(
            f"Магазин '{store_name}' успешно добавлен в город '{city_name}'.",
            reply_markup=get_locations_management_kb()
        )
    except Exception as e:
        logger.error(f"Ошибка при добавлении магазина: {e}")
        await message.answer(
            f"Ошибка при добавлении магазина: {e}",
            reply_markup=get_locations_management_kb()
        )
    
    await state.clear()

# Обработчик просмотра списка магазинов
async def list_stores_command(callback: CallbackQuery, session: AsyncSession):
    # Получаем список городов для выбора
    result = await session.execute(select(City))
    cities = result.scalars().all()
    
    if not cities:
        await callback.message.edit_text(
            "Сначала добавьте города.",
            reply_markup=get_locations_management_kb()
        )
        await callback.answer()
        return
    
    # Создаем клавиатуру для выбора города
    builder = InlineKeyboardBuilder()
    
    for city in cities:
        builder.add(InlineKeyboardButton(
            text=city.name,
            callback_data=f"list_stores_city_{city.city_id}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_locations"
    ))
    
    builder.adjust(1)
    
    await callback.message.edit_text(
        "Выберите город для просмотра магазинов:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

# Обработчик выбора города для просмотра магазинов
async def list_stores_by_city(callback: CallbackQuery, session: AsyncSession):
    # Извлекаем ID города из callback_data
    city_id = int(callback.data.split("_")[3])
    
    # Получаем название города
    city_result = await session.execute(select(City).where(City.city_id == city_id))
    city = city_result.scalar_one_or_none()
    
    if not city:
        await callback.message.edit_text(
            "Город не найден.",
            reply_markup=get_locations_management_kb()
        )
        await callback.answer()
        return
    
    # Получаем список магазинов в этом городе
    stores_result = await session.execute(select(Store).where(Store.city_id == city_id))
    stores = stores_result.scalars().all()
    
    if not stores:
        await callback.message.edit_text(
            f"В городе '{city.name}' нет магазинов.",
            reply_markup=get_locations_management_kb()
        )
        await callback.answer()
        return
    
    # Создаем сообщение со списком магазинов
    stores_list = "\n".join([f"🏪 {store.name} (ID: {store.store_id})" for store in stores])
    
    await callback.message.edit_text(
        f"Магазины в городе '{city.name}':\n\n{stores_list}\n\nВыберите действие:",
        reply_markup=get_locations_management_kb()
    )
    await callback.answer()

async def main():
    # Создаем таблицы в базе данных, если их нет
    try:
        logger.info("Создание таблиц базы данных...")
        async with async_engine.begin() as conn:
            # Создаем новые таблицы
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Таблицы успешно созданы")
    except Exception as e:
        logger.error(f"Ошибка при создании таблиц: {e}")
        raise

    # Инициализация бота и диспетчера
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрация middleware
    dp.update.middleware(DbSessionMiddleware())
    
    # Регистрация обработчиков
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(cmd_admin, Command("admin"))
    dp.message.register(cmd_help, Command("help"))
    
    # Регистрация обработчиков пользователя
    dp.message.register(process_name, RegistrationStates.waiting_for_name)
    dp.callback_query.register(process_city_selection, RegistrationStates.waiting_for_city, F.data.startswith("city_"))
    dp.callback_query.register(back_to_city_selection, RegistrationStates.waiting_for_store, F.data == "back_to_cities")
    dp.callback_query.register(process_store_selection, RegistrationStates.waiting_for_store, F.data.startswith("store_"))
    
    # Профиль пользователя
    dp.message.register(profile_command, F.text == "👤 Мій профіль")
    dp.callback_query.register(edit_profile_name_command, F.data == "edit_profile_name")
    dp.message.register(process_edit_name, RegistrationStates.edit_profile_name)
    dp.callback_query.register(edit_profile_city_command, F.data == "edit_profile_city")
    dp.callback_query.register(edit_profile_store_command, F.data == "edit_profile_store")
    dp.callback_query.register(process_city_selection, RegistrationStates.edit_profile_city, F.data.startswith("city_"))
    dp.callback_query.register(back_to_city_selection, RegistrationStates.edit_profile_store, F.data == "back_to_cities")
    dp.callback_query.register(process_store_selection, RegistrationStates.edit_profile_store, F.data.startswith("store_"))
    
    # Общие обработчики
    dp.callback_query.register(back_to_main_menu, F.data == "back_to_main_menu")
    
    # Обработчики админа
    dp.callback_query.register(admin_locations, F.data == "admin_locations")
    dp.callback_query.register(back_to_admin_menu, F.data == "back_to_admin")
    dp.callback_query.register(back_to_locations, F.data == "back_to_locations")
    dp.callback_query.register(user_mode_command, F.data == "user_mode")
    
    # Обработчики для управления городами и магазинами
    dp.callback_query.register(add_city_command, F.data == "add_city")
    dp.message.register(process_city_name, AdminStates.waiting_for_city_name)
    dp.callback_query.register(list_cities_command, F.data == "list_cities")
    dp.callback_query.register(add_store_command, F.data == "add_store")
    dp.callback_query.register(process_city_for_store, F.data.startswith("admin_city_"))
    dp.message.register(process_store_name, AdminStates.waiting_for_store_name)
    dp.callback_query.register(list_stores_command, F.data == "list_stores")
    dp.callback_query.register(list_stores_by_city, F.data.startswith("list_stores_city_"))
    
     # Обработчики для редактирования городов и магазинов
    dp.callback_query.register(edit_cities_command, F.data == "edit_cities")
    dp.callback_query.register(edit_city_name_command, F.data.startswith("edit_city_"))
    dp.message.register(process_edit_city_name, AdminStates.waiting_for_city_new_name)
    dp.callback_query.register(edit_stores_command, F.data == "edit_stores")
    dp.callback_query.register(edit_stores_city, F.data.startswith("edit_stores_city_"))
    dp.callback_query.register(edit_store_name_command, F.data.startswith("edit_store_"))
    dp.message.register(process_edit_store_name, AdminStates.waiting_for_store_new_name)
    
       
    
    # Запуск бота
    logger.info("Бот запускается...")
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        # Настраиваем правильную политику цикла событий для Windows
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен!")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {e}", exc_info=True)