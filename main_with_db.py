import asyncio
import os
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.filters import Command, CommandStart
from bot.config import BOT_TOKEN, ADMIN_IDS

# Определяем состояния для регистрации пользователей
class RegistrationStates(StatesGroup):
    waiting_for_name = State()  # Ожидание ввода имени
    waiting_for_city = State()  # Ожидание выбора города
    waiting_for_store = State()  # Ожидание выбора магазина

# Определяем состояния для администратора
class AdminStates(StatesGroup):
    waiting_for_city_name = State()  # Ожидание ввода названия города
    waiting_for_store_name = State()  # Ожидание ввода названия магазина
    waiting_for_city_for_store = State()  # Ожидание выбора города для магазина
    waiting_for_confirm_delete = State()  # Ожидание подтверждения удаления

# Инициализация базы данных SQLite
DB_PATH = os.path.join(os.getcwd(), "bot.db")

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Создаем таблицу cities (города), если её нет
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cities (
        city_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )
    ''')
    
    # Создаем таблицу stores (магазины), если её нет
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS stores (
        store_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        city_id INTEGER,
        FOREIGN KEY (city_id) REFERENCES cities (city_id)
    )
    ''')
    
    # Создаем таблицу users (пользователи), если её нет
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        city_id INTEGER,
        store_id INTEGER,
        is_admin BOOLEAN DEFAULT 0,
        FOREIGN KEY (city_id) REFERENCES cities (city_id),
        FOREIGN KEY (store_id) REFERENCES stores (store_id)
    )
    ''')
    
    # Проверяем, есть ли уже данные в таблице городов
    cursor.execute("SELECT COUNT(*) FROM cities")
    count = cursor.fetchone()[0]
    
    # Если таблица городов пуста, добавляем тестовые данные
    if count == 0:
        # Добавляем тестовые города
        cities = ["Київ", "Львів", "Одеса", "Харків", "Дніпро"]
        for city_name in cities:
            cursor.execute("INSERT INTO cities (name) VALUES (?)", (city_name,))
        
        # Добавляем несколько тестовых магазинов
        test_stores = [
            ("Супермаркет 'Центральний'", 1),  # Київ
            ("Гіпермаркет 'Велика кишеня'", 1),  # Київ
            ("Супермаркет 'Галичина'", 2),  # Львів
            ("Маркет 'Море'", 3)  # Одеса
        ]
        
        for store_name, city_id in test_stores:
            cursor.execute("INSERT INTO stores (name, city_id) VALUES (?, ?)", (store_name, city_id))
    
    conn.commit()
    conn.close()
    print(f"База данных инициализирована: {DB_PATH}")

def get_cities():
    """Получение списка городов из базы данных"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT city_id, name FROM cities ORDER BY name")
    cities = cursor.fetchall()
    
    conn.close()
    return cities

def get_stores(city_id):
    """Получение списка магазинов для выбранного города"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT store_id, name FROM stores WHERE city_id = ? ORDER BY name", (city_id,))
    stores = cursor.fetchall()
    
    conn.close()
    return stores

def save_user(user_id, first_name, last_name, city_id, store_id, is_admin=False):
    """Сохранение пользователя в базу данных"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Проверяем, существует ли пользователь
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if user:
        # Обновляем данные пользователя
        cursor.execute(
            "UPDATE users SET first_name = ?, last_name = ?, city_id = ?, store_id = ?, is_admin = ? WHERE user_id = ?",
            (first_name, last_name, city_id, store_id, is_admin, user_id)
        )
    else:
        # Добавляем нового пользователя
        cursor.execute(
            "INSERT INTO users (user_id, first_name, last_name, city_id, store_id, is_admin) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, first_name, last_name, city_id, store_id, is_admin)
        )
    
    conn.commit()
    conn.close()
    print(f"Пользователь {first_name} {last_name} сохранен в базе данных")

def get_user(user_id):
    """Получение пользователя из базы данных"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT u.first_name, u.last_name, c.name AS city_name, s.name AS store_name, u.is_admin 
    FROM users u
    LEFT JOIN cities c ON u.city_id = c.city_id
    LEFT JOIN stores s ON u.store_id = s.store_id
    WHERE u.user_id = ?
    ''', (user_id,))
    user = cursor.fetchone()
    
    conn.close()
    
    if user:
        return {
            "first_name": user[0], 
            "last_name": user[1],
            "city_name": user[2],
            "store_name": user[3],
            "is_admin": bool(user[4])
        }
    return None

def add_city(city_name):
    """Добавление нового города"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("INSERT INTO cities (name) VALUES (?)", (city_name,))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        # Город с таким названием уже существует
        conn.close()
        return False

def add_store(store_name, city_id):
    """Добавление нового магазина"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("INSERT INTO stores (name, city_id) VALUES (?, ?)", (store_name, city_id))
    conn.commit()
    conn.close()
    return True

def delete_city(city_id):
    """Удаление города и связанных магазинов"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Удаляем магазины в этом городе
    cursor.execute("DELETE FROM stores WHERE city_id = ?", (city_id,))
    
    # Удаляем город
    cursor.execute("DELETE FROM cities WHERE city_id = ?", (city_id,))
    
    conn.commit()
    conn.close()
    return True

def delete_store(store_id):
    """Удаление магазина"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM stores WHERE store_id = ?", (store_id,))
    
    conn.commit()
    conn.close()
    return True

# Создание клавиатуры для главного меню
def get_main_menu_kb():
    builder = ReplyKeyboardBuilder()
    
    builder.add(
        KeyboardButton(text="📚 Бібліотека знань"),
        KeyboardButton(text="📝 Пройти тест"),
        KeyboardButton(text="🏆 Мої бали"),
        KeyboardButton(text="📢 Оголошення")
    )
    
    # Размещаем кнопки в 2 строки по 2 кнопки
    builder.adjust(2, 2)
    
    return builder.as_markup(resize_keyboard=True)

# Создание клавиатуры для админ-меню
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

# Создание клавиатуры для управления городами и магазинами
def get_locations_management_kb():
    builder = InlineKeyboardBuilder()
    
    buttons = [
        InlineKeyboardButton(text="🏙 Добавить город", callback_data="add_city"),
        InlineKeyboardButton(text="🏙 Список городов", callback_data="list_cities"),
        InlineKeyboardButton(text="🏪 Добавить магазин", callback_data="add_store"),
        InlineKeyboardButton(text="🏪 Список магазинов", callback_data="list_stores"),
        InlineKeyboardButton(text="🔙 Назад в админ-меню", callback_data="back_to_admin")
    ]
    
    for button in buttons:
        builder.add(button)
    
    # Размещаем по одной кнопке в строку
    builder.adjust(1)
    
    return builder.as_markup()

# Создание инлайн-клавиатуры для выбора города
def get_cities_kb():
    cities = get_cities()
    builder = InlineKeyboardBuilder()
    
    for city_id, city_name in cities:
        builder.add(InlineKeyboardButton(
            text=city_name,
            callback_data=f"city_{city_id}"
        ))
    
    # Размещаем по одной кнопке в строку
    builder.adjust(1)
    
    return builder.as_markup()

# Создание инлайн-клавиатуры для выбора города (для администратора)
def get_admin_cities_kb():
    cities = get_cities()
    builder = InlineKeyboardBuilder()
    
    for city_id, city_name in cities:
        builder.add(InlineKeyboardButton(
            text=city_name,
            callback_data=f"admin_city_{city_id}"
        ))
    
    # Добавляем кнопку "Назад"
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_locations"
    ))
    
    # Размещаем по одной кнопке в строку
    builder.adjust(1)
    
    return builder.as_markup()

# Создание инлайн-клавиатуры для списка городов (для администратора)
def get_cities_list_kb():
    cities = get_cities()
    builder = InlineKeyboardBuilder()
    
    for city_id, city_name in cities:
        builder.add(InlineKeyboardButton(
            text=f"{city_name} 🗑",
            callback_data=f"delete_city_{city_id}"
        ))
    
    # Добавляем кнопку "Назад"
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_locations"
    ))
    
    # Размещаем по одной кнопке в строку
    builder.adjust(1)
    
    return builder.as_markup()

# Создание инлайн-клавиатуры для списка магазинов по городам (для администратора)
def get_stores_list_kb():
    cities = get_cities()
    builder = InlineKeyboardBuilder()
    
    for city_id, city_name in cities:
        builder.add(InlineKeyboardButton(
            text=f"Магазины в {city_name}",
            callback_data=f"list_stores_{city_id}"
        ))
    
    # Добавляем кнопку "Назад"
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_locations"
    ))
    
    # Размещаем по одной кнопке в строку
    builder.adjust(1)
    
    return builder.as_markup()

# Создание инлайн-клавиатуры для списка магазинов в конкретном городе (для администратора)
def get_city_stores_list_kb(city_id):
    stores = get_stores(city_id)
    builder = InlineKeyboardBuilder()
    
    for store_id, store_name in stores:
        builder.add(InlineKeyboardButton(
            text=f"{store_name} 🗑",
            callback_data=f"delete_store_{store_id}"
        ))
    
    # Добавляем кнопку "Назад"
    builder.add(InlineKeyboardButton(
        text="🔙 Назад к списку городов",
        callback_data="list_stores"
    ))
    
    # Размещаем по одной кнопке в строку
    builder.adjust(1)
    
    return builder.as_markup()

# Создание инлайн-клавиатуры для выбора магазина
def get_stores_kb(city_id):
    stores = get_stores(city_id)
    builder = InlineKeyboardBuilder()
    
    for store_id, store_name in stores:
        builder.add(InlineKeyboardButton(
            text=store_name,
            callback_data=f"store_{store_id}"
        ))
    
    # Добавляем кнопку "Назад" для возврата к выбору города
    builder.add(InlineKeyboardButton(
        text="🔙 Назад до вибору міста",
        callback_data="back_to_cities"
    ))
    
    # Размещаем по одной кнопке в строку
    builder.adjust(1)
    
    return builder.as_markup()

# Создание клавиатуры подтверждения
def get_confirmation_kb(action, entity_id):
    builder = InlineKeyboardBuilder()
    
    builder.add(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{action}_{entity_id}"),
        InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_delete")
    )
    
    # Размещаем по одной кнопке в строку
    builder.adjust(1)
    
    return builder.as_markup()

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Обработчик для команды /start
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Проверяем, есть ли пользователь в базе данных
    user = get_user(user_id)
    
    # Проверяем, является ли пользователь администратором
    is_admin = user_id in ADMIN_IDS if user is None else user.get("is_admin", False)
    
    if user:
        # Если пользователь уже зарегистрирован
        if is_admin:
            await message.answer(
                f"З поверненням, {user['first_name']} {user['last_name']}!\n"
                f"Ви є адміністратором. Виберіть опцію:",
                reply_markup=get_admin_menu_kb()
            )
        else:
            await message.answer(
                f"З поверненням, {user['first_name']} {user['last_name']}!\n"
                f"Ваше місто: {user['city_name']}\n"
                f"Ваш магазин: {user['store_name']}",
                reply_markup=get_main_menu_kb()
            )
    else:
        # Если пользователь не зарегистрирован, начинаем процесс регистрации
        await message.answer(
            "Вітаю! Для початку роботи з ботом, будь ласка, заповніть наступні дані."
            "\n\nЯк вас звати? Введіть ім'я та прізвище:"
        )
        await state.set_state(RegistrationStates.waiting_for_name)

# Обработчик для команды /admin
@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    user_id = message.from_user.id
    
    # Проверяем, является ли пользователь администратором
    if user_id in ADMIN_IDS:
        # Обновляем статус в базе данных
        user = get_user(user_id)
        if user:
            save_user(
                user_id,
                user.get("first_name"),
                user.get("last_name"),
                None,  # city_id
                None,  # store_id
                True   # is_admin
            )
        
        # Показываем админ-меню
        await message.answer(
            "Панель администратора. Выберите опцию:",
            reply_markup=get_admin_menu_kb()
        )
    else:
        await message.answer("У вас нет прав доступа к административной панели.")

# Обработчик возвращения к административному меню
@dp.callback_query(lambda c: c.data == "back_to_admin")
async def back_to_admin_menu(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Панель администратора. Выберите опцию:",
        reply_markup=get_admin_menu_kb()
    )
    await callback.answer()

# Обработчик возвращения к управлению локациями
@dp.callback_query(lambda c: c.data == "back_to_locations")
async def back_to_locations_menu(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Управление городами и магазинами. Выберите действие:",
        reply_markup=get_locations_management_kb()
    )
    await callback.answer()

# Обработчик для управления городами и магазинами
@dp.callback_query(lambda c: c.data == "admin_locations")
async def admin_locations(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Управление городами и магазинами. Выберите действие:",
        reply_markup=get_locations_management_kb()
    )
    await callback.answer()

# Обработчик добавления города
@dp.callback_query(lambda c: c.data == "add_city")
async def add_city_command(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Введите название нового города:"
    )
    await state.set_state(AdminStates.waiting_for_city_name)
    await callback.answer()

# Обработчик ввода названия города
@dp.message(AdminStates.waiting_for_city_name)
async def process_city_name(message: Message, state: FSMContext):
    city_name = message.text.strip()
    
    # Добавляем город в базу данных
    success = add_city(city_name)
    
    if success:
        await message.answer(
            f"Город '{city_name}' успешно добавлен.",
            reply_markup=get_locations_management_kb()
        )
    else:
        await message.answer(
            f"Город '{city_name}' уже существует.",
            reply_markup=get_locations_management_kb()
        )
    
    await state.clear()

# Обработчик добавления магазина
@dp.callback_query(lambda c: c.data == "add_store")
async def add_store_command(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Выберите город для нового магазина:",
        reply_markup=get_admin_cities_kb()
    )
    await state.set_state(AdminStates.waiting_for_city_for_store)
    await callback.answer()

# Обработчик выбора города для магазина
@dp.callback_query(lambda c: c.data and c.data.startswith("admin_city_"))
async def process_city_for_store(callback: types.CallbackQuery, state: FSMContext):
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
@dp.message(AdminStates.waiting_for_store_name)
async def process_store_name(message: Message, state: FSMContext):
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
    
    # Добавляем магазин в базу данных
    add_store(store_name, city_id)
    
    cities = get_cities()
    city_name = next((name for id, name in cities if id == city_id), "Неизвестный город")
    
    await message.answer(
        f"Магазин '{store_name}' успешно добавлен в город '{city_name}'.",
        reply_markup=get_locations_management_kb()
    )
    
    await state.clear()

# Обработчик просмотра списка городов
@dp.callback_query(lambda c: c.data == "list_cities")
async def list_cities_command(callback: types.CallbackQuery):
    cities = get_cities()
    
    if not cities:
        await callback.message.edit_text(
            "Список городов пуст.",
            reply_markup=get_locations_management_kb()
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        "Список городов (нажмите на город для удаления):",
        reply_markup=get_cities_list_kb()
    )
    await callback.answer()

# Обработчик просмотра списка магазинов
@dp.callback_query(lambda c: c.data == "list_stores")
async def list_stores_command(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Выберите город для просмотра магазинов:",
        reply_markup=get_stores_list_kb()
    )
    await callback.answer()

# Обработчик просмотра магазинов в конкретном городе
@dp.callback_query(lambda c: c.data and c.data.startswith("list_stores_"))
async def list_city_stores_command(callback: types.CallbackQuery):
    city_id = int(callback.data.split("_")[2])
    
    stores = get_stores(city_id)
    cities = get_cities()
    city_name = next((name for id, name in cities if id == city_id), "Неизвестный город")
    
    if not stores:
        await callback.message.edit_text(
            f"В городе '{city_name}' нет магазинов.",
            reply_markup=get_stores_list_kb()
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        f"Магазины в городе '{city_name}' (нажмите на магазин для удаления):",
        reply_markup=get_city_stores_list_kb(city_id)
    )
    await callback.answer()

# Обработчик удаления города
@dp.callback_query(lambda c: c.data and c.data.startswith("delete_city_"))
async def delete_city_command(callback: types.CallbackQuery, state: FSMContext):
    city_id = int(callback.data.split("_")[2])
    
    # Сохраняем ID города и тип объекта для удаления
    await state.update_data(entity_id=city_id, entity_type="city")
    
    cities = get_cities()
    city_name = next((name for id, name in cities if id == city_id), "Неизвестный город")
    
    await callback.message.edit_text(
        f"Вы действительно хотите удалить город '{city_name}' и все его магазины?",
        reply_markup=get_confirmation_kb("city", city_id)
    )
    await state.set_state(AdminStates.waiting_for_confirm_delete)
    await callback.answer()

# Обработчик удаления магазина
@dp.callback_query(lambda c: c.data and c.data.startswith("delete_store_"))
async def delete_store_command(callback: types.CallbackQuery, state: FSMContext):
    store_id = int(callback.data.split("_")[2])
    
    # Сохраняем ID магазина и тип объекта для удаления
    await state.update_data(entity_id=store_id, entity_type="store")
    
    # Получаем название магазина
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, city_id FROM stores WHERE store_id = ?", (store_id,))
    store_data = cursor.fetchone()
    conn.close()
    
    if not store_data:
        await callback.message.edit_text(
            "Магазин не найден.",
            reply_markup=get_stores_list_kb()
        )
        await callback.answer()
        return
    
    store_name, city_id = store_data
    
    await callback.message.edit_text(
        f"Вы действительно хотите удалить магазин '{store_name}'?",
        reply_markup=get_confirmation_kb("store", store_id)
    )
    await state.set_state(AdminStates.waiting_for_confirm_delete)
    await callback.answer()

# Обработчик подтверждения удаления
@dp.callback_query(lambda c: c.data and c.data.startswith("confirm_"))
async def confirm_delete(callback: types.CallbackQuery, state: FSMContext):
    action_parts = callback.data.split("_")
    entity_type = action_parts[1]
    entity_id = int(action_parts[2])
    
    if entity_type == "city":
        cities = get_cities()
        city_name = next((name for id, name in cities if id == entity_id), "Неизвестный город")
        
        delete_city(entity_id)
        
        await callback.message.edit_text(
            f"Город '{city_name}' и все его магазины успешно удалены.",
            reply_markup=get_locations_management_kb()
        )
    elif entity_type == "store":
        # Получаем название магазина
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM stores WHERE store_id = ?", (entity_id,))
        store_data = cursor.fetchone()
        conn.close()
        
        store_name = store_data[0] if store_data else "Неизвестный магазин"
        
        delete_store(entity_id)
        
        await callback.message.edit_text(
            f"Магазин '{store_name}' успешно удален.",
            reply_markup=get_locations_management_kb()
        )
    
    await state.clear()
    await callback.answer()

# Обработчик отмены удаления
@dp.callback_query(lambda c: c.data == "cancel_delete")
async def cancel_delete(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Операция удаления отменена.",
        reply_markup=get_locations_management_kb()
    )
    await state.clear()
    await callback.answer()

# Обработчик перехода в пользовательский режим
@dp.callback_query(lambda c: c.data == "user_mode")
async def user_mode_command(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if user:
        await callback.message.edit_text(
            f"Вы вернулись в обычный режим.\nВыберите опцию из меню ниже:"
        )
        await callback.message.answer(
            "Меню пользователя:",
            reply_markup=get_main_menu_kb()
        )
    else:
        await callback.message.edit_text(
            "Вы не зарегистрированы. Используйте команду /start для регистрации."
        )
    
    await callback.answer()

# Обработчик ввода имени
@dp.message(RegistrationStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
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
    
    # Показываем инлайн-клавиатуру с городами
    await message.answer(
        "Дякую! Тепер, будь ласка, виберіть ваше місто:",
        reply_markup=get_cities_kb()
    )
    
    # Переходим к состоянию выбора города
    await state.set_state(RegistrationStates.waiting_for_city)

# Обработчик выбора города через инлайн-кнопки
@dp.callback_query(lambda c: c.data and c.data.startswith("city_"))
async def process_city_selection_callback(callback: types.CallbackQuery, state: FSMContext):
    # Извлекаем ID города из callback_data
    city_id = int(callback.data.split("_")[1])
    
    # Получаем информацию о выбранном городе
    cities = get_cities()
    city_name = next((name for id, name in cities if id == city_id), "Невідоме місто")
    
    # Сохраняем ID города в данных состояния
    await state.update_data(city_id=city_id)
    
    # Показываем инлайн-клавиатуру с магазинами
    await callback.message.edit_text(
        f"Ви вибрали місто: {city_name}\n\nТепер, будь ласка, виберіть ваш магазин:",
        reply_markup=get_stores_kb(city_id)
    )
    
    # Переходим к состоянию выбора магазина
    await state.set_state(RegistrationStates.waiting_for_store)
    
    # Отвечаем на callback-запрос
    await callback.answer()

# Обработчик возврата к выбору города
@dp.callback_query(lambda c: c.data == "back_to_cities")
async def back_to_city_selection_callback(callback: types.CallbackQuery, state: FSMContext):
    # Показываем инлайн-клавиатуру с городами
    await callback.message.edit_text(
        "Будь ласка, виберіть ваше місто:",
        reply_markup=get_cities_kb()
    )
    
    # Возвращаемся к состоянию выбора города
    await state.set_state(RegistrationStates.waiting_for_city)
    
    # Отвечаем на callback-запрос
    await callback.answer()

# Обработчик выбора магазина через инлайн-кнопки
@dp.callback_query(lambda c: c.data and c.data.startswith("store_"))
async def process_store_selection_callback(callback: types.CallbackQuery, state: FSMContext):
    # Извлекаем ID магазина из callback_data
    store_id = int(callback.data.split("_")[1])
    
    # Получаем данные состояния
    user_data = await state.get_data()
    city_id = user_data.get('city_id')
    
    if not city_id:
        await callback.message.answer(
            "Помилка: не вибрано місто. Почніть реєстрацію заново з команди /start"
        )
        await state.clear()
        await callback.answer()
        return
    
    # Получаем информацию о выбранном городе и магазине
    cities = get_cities()
    city_name = next((name for id, name in cities if id == city_id), "Невідоме місто")
    
    stores = get_stores(city_id)
    store_name = next((name for id, name in stores if id == store_id), "Невідомий магазин")
    
    # Проверяем, является ли пользователь администратором
    is_admin = callback.from_user.id in ADMIN_IDS
    
    # Сохраняем пользователя в базе данных
    save_user(
        callback.from_user.id,
        user_data.get('first_name'),
        user_data.get('last_name'),
        city_id,
        store_id,
        is_admin  # если ID пользователя в списке админов, устанавливаем флаг админа
    )
    
    # Завершаем регистрацию
    await callback.message.edit_text(
        f"Реєстрація завершена!\n\n"
        f"Ім'я: {user_data.get('first_name')} {user_data.get('last_name')}\n"
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
        # Показываем главное меню
        await callback.message.answer(
            "Виберіть опцію з меню нижче:",
            reply_markup=get_main_menu_kb()
        )
    
    # Сбрасываем состояние
    await state.clear()
    
    # Отвечаем на callback-запрос
    await callback.answer()

# Обработчики кнопок главного меню
@dp.message(lambda m: m.text == "📚 Бібліотека знань")
async def library_command(message: Message):
    await message.answer(
        "Функція бібліотеки знань знаходиться в розробці."
    )

@dp.message(lambda m: m.text == "📝 Пройти тест")
async def tests_command(message: Message):
    await message.answer(
        "Функція проходження тестів знаходиться в розробці."
    )

@dp.message(lambda m: m.text == "🏆 Мої бали")
async def my_points_command(message: Message):
    await message.answer(
        "Функція перегляду балів знаходиться в розробці."
    )

@dp.message(lambda m: m.text == "📢 Оголошення")
async def announcements_command(message: Message):
    await message.answer(
        "Функція оголошень знаходиться в розробці."
    )

# Обработчик для команды /help
@dp.message(Command("help"))
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

async def main():
    print("Инициализация базы данных...")
    init_db()
    
    print("Бот запускается...")
    await dp.start_polling(bot)
# Добавьте эти состояния в класс AdminStates
class AdminStates(StatesGroup):
    # ... существующие состояния ...
    waiting_for_store_new_name = State()  # Ожидание нового названия магазина
    waiting_for_city_new_name = State()   # Ожидание нового названия города

# Добавьте эти состояния в класс RegistrationStates
class RegistrationStates(StatesGroup):
    # ... существующие состояния ...
    edit_profile = State()         # Редактирование профиля
    edit_profile_name = State()    # Редактирование имени
    edit_profile_city = State()    # Выбор нового города
    edit_profile_store = State()   # Выбор нового магазина

# Добавьте эти функции для работы с базой данных
def update_store_name(store_id, new_name):
    """Обновление названия магазина"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("UPDATE stores SET name = ? WHERE store_id = ?", (new_name, store_id))
    
    conn.commit()
    conn.close()
    return True

def update_city_name(city_id, new_name):
    """Обновление названия города"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("UPDATE cities SET name = ? WHERE city_id = ?", (new_name, city_id))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        # Город с таким названием уже существует
        conn.close()
        return False

# Создайте клавиатуру для редактирования профиля
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

# Клавиатура для редактирования в админке
def get_edit_kb(entity_type, entity_id):
    builder = InlineKeyboardBuilder()
    
    builder.add(
        InlineKeyboardButton(text="✏️ Изменить название", callback_data=f"edit_{entity_type}_{entity_id}"),
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_{entity_type}_{entity_id}"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_locations")
    )
    
    # Размещаем по одной кнопке в строку
    builder.adjust(1)
    
    return builder.as_markup()

# Создание инлайн-клавиатуры для списка городов с редактированием
def get_cities_list_edit_kb():
    cities = get_cities()
    builder = InlineKeyboardBuilder()
    
    for city_id, city_name in cities:
        builder.add(InlineKeyboardButton(
            text=city_name,
            callback_data=f"edit_city_options_{city_id}"
        ))
    
    # Добавляем кнопку "Назад"
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_locations"
    ))
    
    # Размещаем по одной кнопке в строку
    builder.adjust(1)
    
    return builder.as_markup()

# Создание инлайн-клавиатуры для списка магазинов с редактированием
def get_stores_list_edit_kb(city_id):
    stores = get_stores(city_id)
    builder = InlineKeyboardBuilder()
    
    for store_id, store_name in stores:
        builder.add(InlineKeyboardButton(
            text=store_name,
            callback_data=f"edit_store_options_{store_id}"
        ))
    
    # Добавляем кнопку "Назад"
    builder.add(InlineKeyboardButton(
        text="🔙 Назад к списку городов",
        callback_data="list_stores"
    ))
    
    # Размещаем по одной кнопке в строку
    builder.adjust(1)
    
    return builder.as_markup()

# Добавьте кнопку редактирования профиля в главное меню
def get_main_menu_kb():
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

# Обработчик для редактирования профиля
@dp.message(lambda m: m.text == "👤 Мій профіль")
async def profile_command(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if user:
        await message.answer(
            f"Ваш профіль:\n\n"
            f"Ім'я: {user['first_name']} {user['last_name']}\n"
            f"Місто: {user['city_name']}\n"
            f"Магазин: {user['store_name']}\n\n"
            f"Що бажаєте змінити?",
            reply_markup=get_edit_profile_kb()
        )
    else:
        await message.answer(
            "Ви ще не зареєстровані. Використайте команду /start для реєстрації."
        )

# Обработчик возврата в главное меню
@dp.callback_query(lambda c: c.data == "back_to_main_menu")
async def back_to_main_menu(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Ви повернулися в головне меню."
    )
    await callback.answer()

# Обработчик редактирования имени пользователя
@dp.callback_query(lambda c: c.data == "edit_profile_name")
async def edit_profile_name_command(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Введіть нове ім'я та прізвище:"
    )
    await state.set_state(RegistrationStates.edit_profile_name)
    await callback.answer()

# Обработчик ввода нового имени
@dp.message(RegistrationStates.edit_profile_name)
async def process_edit_name(message: Message, state: FSMContext):
    # Получаем введенное имя
    full_name = message.text.strip()
    
    # Проверяем, что имя состоит минимум из двух слов (имя и фамилия)
    name_parts = full_name.split()
    if len(name_parts) < 2:
        await message.answer(
            "Будь ласка, введіть повне ім'я та прізвище, розділені пробілом."
        )
        return
    
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if user:
        # Обновляем имя пользователя
        save_user(
            user_id,
            name_parts[0],
            ' '.join(name_parts[1:]),
            None,  # Сохраняем текущий город
            None,  # Сохраняем текущий магазин
            user.get("is_admin", False)
        )
        
        await message.answer(
            f"Ваше ім'я змінено на {full_name}.",
            reply_markup=get_main_menu_kb()
        )
    else:
        await message.answer(
            "Помилка: профіль не знайдено. Будь ласка, зареєструйтеся з допомогою команди /start."
        )
    
    await state.clear()

# Обработчик редактирования города
@dp.callback_query(lambda c: c.data == "edit_profile_city")
async def edit_profile_city_command(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Виберіть новий город:",
        reply_markup=get_cities_kb()
    )
    await state.set_state(RegistrationStates.edit_profile_city)
    await callback.answer()

# Обработчик выбора нового города
@dp.callback_query(RegistrationStates.edit_profile_city, lambda c: c.data and c.data.startswith("city_"))
async def process_edit_city(callback: types.CallbackQuery, state: FSMContext):
    # Извлекаем ID города из callback_data
    city_id = int(callback.data.split("_")[1])
    
    # Получаем информацию о выбранном городе
    cities = get_cities()
    city_name = next((name for id, name in cities if id == city_id), "Невідоме місто")
    
    # Сохраняем ID города в данных состояния
    await state.update_data(city_id=city_id)
    
    # Показываем инлайн-клавиатуру с магазинами
    await callback.message.edit_text(
        f"Ви вибрали місто: {city_name}\n\nТепер, будь ласка, виберіть ваш магазин:",
        reply_markup=get_stores_kb(city_id)
    )
    
    # Переходим к состоянию выбора магазина
    await state.set_state(RegistrationStates.edit_profile_store)
    
    await callback.answer()

# Обработчик выбора нового магазина
@dp.callback_query(RegistrationStates.edit_profile_store, lambda c: c.data and c.data.startswith("store_"))
async def process_edit_store(callback: types.CallbackQuery, state: FSMContext):
    # Извлекаем ID магазина из callback_data
    store_id = int(callback.data.split("_")[1])
    
    # Получаем данные состояния
    user_data = await state.get_data()
    city_id = user_data.get('city_id')
    
    if not city_id:
        await callback.message.answer(
            "Помилка: не вибрано місто. Спробуйте ще раз."
        )
        await state.clear()
        await callback.answer()
        return
    
    # Получаем информацию о выбранном городе и магазине
    cities = get_cities()
    city_name = next((name for id, name in cities if id == city_id), "Невідоме місто")
    
    stores = get_stores(city_id)
    store_name = next((name for id, name in stores if id == store_id), "Невідомий магазин")
    
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if user:
        # Обновляем профиль пользователя
        save_user(
            user_id,
            user.get("first_name"),
            user.get("last_name"),
            city_id,
            store_id,
            user.get("is_admin", False)
        )
        
        # Уведомляем об успешном обновлении
        await callback.message.edit_text(
            f"Ваш профіль оновлено!\n\n"
            f"Ім'я: {user.get('first_name')} {user.get('last_name')}\n"
            f"Нове місто: {city_name}\n"
            f"Новий магазин: {store_name}"
        )
        
        # Показываем главное меню
        await callback.message.answer(
            "Виберіть опцію з меню нижче:",
            reply_markup=get_main_menu_kb()
        )
    else:
        await callback.message.edit_text(
            "Помилка: профіль не знайдено. Будь ласка, зареєструйтеся з допомогою команди /start."
        )
    
    # Сбрасываем состояние
    await state.clear()
    
    await callback.answer()

# Обработчики для редактирования городов и магазинов в админке

# Добавляем пункт редактирования в меню управления локациями
def get_locations_management_kb():
    builder = InlineKeyboardBuilder()
    
    buttons = [
        InlineKeyboardButton(text="🏙 Добавить город", callback_data="add_city"),
        InlineKeyboardButton(text="🏙 Редактировать города", callback_data="edit_cities"), # Новая кнопка
        InlineKeyboardButton(text="🏙 Список городов", callback_data="list_cities"),
        InlineKeyboardButton(text="🏪 Добавить магазин", callback_data="add_store"),
        InlineKeyboardButton(text="🏪 Редактировать магазины", callback_data="edit_stores"), # Новая кнопка
        InlineKeyboardButton(text="🏪 Список магазинов", callback_data="list_stores"),
        InlineKeyboardButton(text="🔙 Назад в админ-меню", callback_data="back_to_admin")
    ]
    
    for button in buttons:
        builder.add(button)
    
    # Размещаем по одной кнопке в строку
    builder.adjust(1)
    
    return builder.as_markup()

# Обработчик редактирования городов
@dp.callback_query(lambda c: c.data == "edit_cities")
async def edit_cities_command(callback: types.CallbackQuery):
    cities = get_cities()
    
    if not cities:
        await callback.message.edit_text(
            "Список городов пуст.",
            reply_markup=get_locations_management_kb()
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        "Выберите город для редактирования:",
        reply_markup=get_cities_list_edit_kb()
    )
    await callback.answer()

# Обработчик редактирования магазинов
@dp.callback_query(lambda c: c.data == "edit_stores")
async def edit_stores_command(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Выберите город, в котором находятся магазины для редактирования:",
        reply_markup=get_stores_list_kb()
    )
    await callback.answer()

# Обработчик выбора опций редактирования города
@dp.callback_query(lambda c: c.data and c.data.startswith("edit_city_options_"))
async def edit_city_options_command(callback: types.CallbackQuery):
    city_id = int(callback.data.split("_")[3])
    
    cities = get_cities()
    city_name = next((name for id, name in cities if id == city_id), "Неизвестный город")
    
    await callback.message.edit_text(
        f"Город: {city_name}\n\nВыберите действие:",
        reply_markup=get_edit_kb("city", city_id)
    )
    await callback.answer()

# Обработчик выбора опций редактирования магазина
@dp.callback_query(lambda c: c.data and c.data.startswith("edit_store_options_"))
async def edit_store_options_command(callback: types.CallbackQuery):
    store_id = int(callback.data.split("_")[3])
    
    # Получаем название магазина
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, city_id FROM stores WHERE store_id = ?", (store_id,))
    store_data = cursor.fetchone()
    conn.close()
    
    if not store_data:
        await callback.message.edit_text(
            "Магазин не найден.",
            reply_markup=get_stores_list_kb()
        )
        await callback.answer()
        return
    
    store_name, city_id = store_data
    
    await callback.message.edit_text(
        f"Магазин: {store_name}\n\nВыберите действие:",
        reply_markup=get_edit_kb("store", store_id)
    )
    await callback.answer()

# Обработчик редактирования названия города
@dp.callback_query(lambda c: c.data and c.data.startswith("edit_city_"))
async def edit_city_name_command(callback: types.CallbackQuery, state: FSMContext):
    city_id = int(callback.data.split("_")[2])
    
    # Сохраняем ID города
    await state.update_data(city_id=city_id)
    
    cities = get_cities()
    city_name = next((name for id, name in cities if id == city_id), "Неизвестный город")
    
    await callback.message.edit_text(
        f"Введите новое название для города '{city_name}':"
    )
    await state.set_state(AdminStates.waiting_for_city_new_name)
    await callback.answer()

# Обработчик ввода нового названия города
@dp.message(AdminStates.waiting_for_city_new_name)
async def process_city_new_name(message: Message, state: FSMContext):
    new_city_name = message.text.strip()
    
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
    
    # Обновляем название города
    success = update_city_name(city_id, new_city_name)
    
    if success:
        await message.answer(
            f"Название города успешно изменено на '{new_city_name}'.",
            reply_markup=get_locations_management_kb()
        )
    else:
        await message.answer(
            f"Город с названием '{new_city_name}' уже существует.",
            reply_markup=get_locations_management_kb()
        )
    
    await state.clear()

# Обработчик редактирования названия магазина
@dp.callback_query(lambda c: c.data and c.data.startswith("edit_store_"))
async def edit_store_name_command(callback: types.CallbackQuery, state: FSMContext):
    store_id = int(callback.data.split("_")[2])
    
    # Сохраняем ID магазина
    await state.update_data(store_id=store_id)
    
    # Получаем название магазина
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM stores WHERE store_id = ?", (store_id,))
    store_data = cursor.fetchone()
    conn.close()
    
    store_name = store_data[0] if store_data else "Неизвестный магазин"
    
    await callback.message.edit_text(
        f"Введите новое название для магазина '{store_name}':"
    )
    await state.set_state(AdminStates.waiting_for_store_new_name)
    await callback.answer()

# Обработчик ввода нового названия магазина
@dp.message(AdminStates.waiting_for_store_new_name)
async def process_store_new_name(message: Message, state: FSMContext):
    new_store_name = message.text.strip()
    
    # Получаем данные состояния
    user_data = await state.get_data()
    store_id = user_data.get('store_id')
    
    if not store_id:
        await message.answer(
            "Ошибка: не выбран магазин. Попробуйте снова.",
            reply_markup=get_locations_management_kb()
        )
        await state.clear()
        return
    
    # Обновляем название магазина
    update_store_name(store_id, new_store_name)
    
    await message.answer(
        f"Название магазина успешно изменено на '{new_store_name}'.",
        reply_markup=get_locations_management_kb()
    )
    
    await state.clear()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен!")
    except Exception as e:
        print(f"Ошибка: {e}")