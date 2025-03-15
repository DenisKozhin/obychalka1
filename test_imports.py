# test_imports.py в корне проекта
print("Проверка импортов...")

try:
    from bot.config import BOT_TOKEN
    print(f"BOT_TOKEN импортирован успешно: {BOT_TOKEN[:5]}...")
except Exception as e:
    print(f"Ошибка импорта BOT_TOKEN: {e}")

try:
    from bot.utils.logger import logger
    logger.info("Логгер работает!")
    print("Логгер импортирован успешно")
except Exception as e:
    print(f"Ошибка импорта logger: {e}")

print("Проверка завершена")
