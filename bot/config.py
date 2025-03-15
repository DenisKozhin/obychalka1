import os
from dotenv import load_dotenv

# Пытаемся загрузить .env
try:
    load_dotenv()
    print("Попытка загрузки .env файла")
except Exception as e:
    print(f"Ошибка при загрузке .env: {e}")

# Основные настройки бота
BOT_TOKEN = "7450783621:AAH1TStAOwDyNZtf3FSuTAJFb1_W4tWSFYs"  # Ваш токен бота
print(f"Используем токен: {BOT_TOKEN[:10]}...")

# Админы бота
ADMIN_IDS = [8067833192]  # Ваш ID в Telegram
print(f"Админы: {ADMIN_IDS}")

# Настройки базы данных
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASS = os.getenv('DB_PASS', 'postgres')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'telegram_shop_bot')

# Строка подключения к базе данных для SQLAlchemy
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Настройки логирования
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', 'logs/bot.log')

# Сообщение при загрузке модуля
print("Модуль config.py загружен. BOT_TOKEN определен:", BOT_TOKEN is not None)