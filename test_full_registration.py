import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from bot.config import BOT_TOKEN, ADMIN_IDS
from bot.database.database import AsyncSessionLocal, Base, async_engine
from bot.database.models import User, City, Store
from sqlalchemy import select

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Определяем состояния для машины состояний регистрации
class RegistrationStates(StatesGroup):
    waiting_for_name = State()  # Ожидание ввода имени
    waiting_for_city = State()  # Ожидание выбора города
    waiting_for_store = State()  # Ожидание выбора магазина

# Middleware для работы с базой данных
class DbSessionMiddleware:
    async def __call__(self, handler, event, data):
        async with AsyncSessionLocal() as session:
            data["session"] = session
            return await handler(event, data)

# Создание клавиатуры с городами
async def get_cities_kb(session):
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
async def get_stores_kb(session, city_id: int):
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

# Обработчик команды /start
async def cmd_start(message: Message, state: FSMContext, session: AsyncSessionLocal):
    user_id = message.from_user.id
    
    # Проверяем, зарегистрирован ли пользователь
    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    
    if user:
        # Если пользователь уже зарегистрирован, показываем приветствие
        await message.answer(
            f"З поверненням, {user.first_name}! Виберіть опцію з меню нижче:"
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
async def process_name(message: Message, state: FSMContext, session: AsyncSessionLocal):
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
async def process_city_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSessionLocal):
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
async def back_to_city_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSessionLocal):
    # Возвращаемся к выбору города
    await callback.message.edit_text(
        "Будь ласка, виберіть ваше місто:",
        reply_markup=await get_cities_kb(session)
    )
    
    # Возвращаемся к состоянию выбора города
    await state.set_state(RegistrationStates.waiting_for_city)
    
    await callback.answer()

# Обработчик выбора магазина
async def process_store_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSessionLocal):
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
        is_admin=callback.from_user.id in ADMIN_IDS  # Проверяем, является ли пользователь админом
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
    
    # Сбрасываем состояние
    await state.clear()
    
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
    
    # Регистрация middleware только для базы данных
    dp.update.middleware(DbSessionMiddleware())
    
    # Регистрация хендлеров
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(process_name, RegistrationStates.waiting_for_name)
    dp.callback_query.register(process_city_selection, RegistrationStates.waiting_for_city, F.data.startswith("city_"))
    dp.callback_query.register(back_to_city_selection, RegistrationStates.waiting_for_store, F.data == "back_to_cities")
    dp.callback_query.register(process_store_selection, RegistrationStates.waiting_for_store, F.data.startswith("store_"))
    
    # Запуск бота
    logger.info("Бот запускается...")
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен!")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {e}", exc_info=True)