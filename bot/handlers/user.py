import sys
import os

# Для запуска файла напрямую
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, CommandStart

from bot.keyboards.user_kb import get_main_menu_kb
from bot.utils.logger import logger
from bot.database.models import User, City, Store
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Создаем роутер для пользовательских команд
router = Router()

# Определяем состояния для машины состояний регистрации
class RegistrationStates(StatesGroup):
    waiting_for_name = State()  # Ожидание ввода имени
    waiting_for_city = State()  # Ожидание выбора города
    waiting_for_store = State()  # Ожидание выбора магазина

# Функция для создания клавиатуры с городами
async def get_cities_kb(session: AsyncSession):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
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
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
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
        callback_data=f"back_to_cities"
    ))
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()

# Обновляем обработчик команды /start для проверки регистрации
@router.message(CommandStart())
async def cmd_start_register(message: Message, state: FSMContext, session: AsyncSession):
    user_id = message.from_user.id
    
    # Проверяем, зарегистрирован ли пользователь
    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    
    if user:
        # Если пользователь уже зарегистрирован, показываем главное меню
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

# Обработчик ввода имени
@router.message(RegistrationStates.waiting_for_name)
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
    
    # Сохраняем имя и фамилию в данных состояния
    await state.update_data(first_name=name_parts[0], last_name=' '.join(name_parts[1:]))
    
    # Просим пользователя выбрать город
    await message.answer(
        "Дякую! Тепер, будь ласка, виберіть ваше місто:",
        reply_markup=await get_cities_kb(session)
    )
    
    # Переходим к состоянию выбора города
    await state.set_state(RegistrationStates.waiting_for_city)

# Обработчик выбора города
@router.callback_query(RegistrationStates.waiting_for_city, F.data.startswith("city_"))
async def process_city_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    # Извлекаем ID выбранного города из callback_data
    city_id = int(callback.data.split("_")[1])
    
    # Сохраняем ID города в данных состояния
    await state.update_data(city_id=city_id)
    
    # Получаем информацию о выбранном городе
    result = await session.execute(select(City).where(City.city_id == city_id))
    city = result.scalar_one_or_none()
    
    if city:
        # Просим пользователя выбрать магазин
        await callback.message.edit_text(
            f"Ви вибрали місто: {city.name}\nТепер, будь ласка, виберіть ваш магазин:",
            reply_markup=await get_stores_kb(session, city_id)
        )
        
        # Переходим к состоянию выбора магазина
        await state.set_state(RegistrationStates.waiting_for_store)
    else:
        # Если город не найден, просим выбрать снова
        await callback.message.edit_text(
            "На жаль, виникла помилка. Будь ласка, виберіть місто ще раз:",
            reply_markup=await get_cities_kb(session)
        )
    
    await callback.answer()

# Обработчик возврата к выбору города
@router.callback_query(RegistrationStates.waiting_for_store, F.data == "back_to_cities")
async def back_to_city_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    # Возвращаемся к выбору города
    await callback.message.edit_text(
        "Будь ласка, виберіть ваше місто:",
        reply_markup=await get_cities_kb(session)
    )
    
    # Возвращаемся к состоянию выбора города
    await state.set_state(RegistrationStates.waiting_for_city)
    
    await callback.answer()

# Обработчик выбора магазина
@router.callback_query(RegistrationStates.waiting_for_store, F.data.startswith("store_"))
async def process_store_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    # Извлекаем ID выбранного магазина из callback_data
    store_id = int(callback.data.split("_")[1])
    
    # Получаем данные состояния
    user_data = await state.get_data()
    
    # Создаем нового пользователя в базе данных
    new_user = User(
        user_id=callback.from_user.id,
        first_name=user_data["first_name"],
        last_name=user_data["last_name"],
        city_id=user_data["city_id"],
        store_id=store_id,
        is_admin=callback.from_user.id in [8067833192]  # Проверяем, является ли пользователь админом
    )
    
    # Сохраняем пользователя в базе данных
    session.add(new_user)
    await session.commit()
    
    # Получаем информацию о выбранном магазине
    result = await session.execute(select(Store).where(Store.store_id == store_id))
    store = result.scalar_one_or_none()
    
    # Завершаем регистрацию и показываем главное меню
    await callback.message.edit_text(
        f"Реєстрація завершена!\n\n"
        f"Ім'я: {user_data['first_name']} {user_data['last_name']}\n"
        f"Місто: {(await session.get(City, user_data['city_id'])).name}\n"
        f"Магазин: {store.name if store else 'Невідомий'}\n\n"
        f"Тепер ви можете користуватися всіма функціями бота."
    )
    
    # Отправляем сообщение с главным меню
    await callback.message.answer(
        "Виберіть опцію з меню нижче:",
        reply_markup=get_main_menu_kb()
    )
    
    # Сбрасываем состояние
    await state.clear()
    
    await callback.answer()

# Обработчики кнопок меню (заглушки на данном этапе)
@router.message(F.text == "📚 Бібліотека знань")
async def library_command(message: Message):
    await message.answer(
        "Функція бібліотеки знань знаходиться в розробці."
    )

@router.message(F.text == "📝 Пройти тест")
async def tests_command(message: Message):
    await message.answer(
        "Функція проходження тестів знаходиться в розробці."
    )

@router.message(F.text == "🏆 Мої бали")
async def my_points_command(message: Message):
    await message.answer(
        "Функція перегляду балів знаходиться в розробці."
    )

@router.message(F.text == "📢 Оголошення")
async def announcements_command(message: Message):
    await message.answer(
        "Функція оголошень знаходиться в розробці."
    )