import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from aiogram.filters import Command, CommandStart
from bot.config import BOT_TOKEN

# Определяем состояния
class RegistrationStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_city = State()

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Обработчик для команды /start
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    # Начинаем процесс регистрации
    await message.answer("Привет! Давайте познакомимся. Как вас зовут?")
    await state.set_state(RegistrationStates.waiting_for_name)

# Обработчик ввода имени
@dp.message(RegistrationStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    # Получаем имя пользователя
    name = message.text.strip()
    
    # Сохраняем имя в данных состояния
    await state.update_data(name=name)
    
    # Просим выбрать город
    await message.answer(f"Приятно познакомиться, {name}! Из какого вы города?")
    await state.set_state(RegistrationStates.waiting_for_city)

# Обработчик ввода города
@dp.message(RegistrationStates.waiting_for_city)
async def process_city(message: Message, state: FSMContext):
    # Получаем город
    city = message.text.strip()
    
    # Получаем данные состояния (имя)
    user_data = await state.get_data()
    name = user_data.get('name', 'Друг')
    
    # Завершаем регистрацию
    await message.answer(
        f"Отлично! {name}, вы из города {city}.\n"
        f"Регистрация завершена!"
    )
    
    # Сбрасываем состояние
    await state.clear()

# Обработчик для команды /help
@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer("Это тестовый бот с регистрацией. Используйте /start для начала регистрации.")

# Обработчик для всех остальных сообщений
@dp.message()
async def echo(message: Message):
    await message.answer(f"Вы написали: {message.text}")

async def main():
    print("Бот запускается...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен!")
    except Exception as e:
        print(f"Ошибка: {e}")