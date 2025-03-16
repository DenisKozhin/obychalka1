import os
import sys

# Для запуска файла напрямую
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Загрузка переменных окружения
try:
    load_dotenv()
    print("Попытка загрузки .env файла")
except Exception as e:
    print(f"Ошибка при загрузке .env: {e}")

# Основные настройки бота
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    print("ВНИМАНИЕ: BOT_TOKEN не задан в переменных окружения!")
    BOT_TOKEN = "7450783621:AAH1TStAOwDyNZtf3FSuTAJFb1_W4tWSFYs"  # Ваш токен бота

# Админы бота
ADMIN_IDS = [8067833192]  # Ваш ID в Telegram
print(f"Админы: {ADMIN_IDS}")

# Настройки базы данных - используем SQLite вместо PostgreSQL
# Путь к файлу базы данных в корневой директории проекта
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bot.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Настройки логирования
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
LOG_FILE = os.path.join(LOG_PATH, "bot.log")

# Сообщение при загрузке модуля
print("Модуль config.py загружен. BOT_TOKEN определен:", BOT_TOKEN is not None)
