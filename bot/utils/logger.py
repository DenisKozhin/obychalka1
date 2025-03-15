import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# Добавляем корневой каталог проекта в путь импорта, если запускаем файл напрямую
if __name__ == "__main__":
    # Идем на две директории вверх от текущего файла (bot/utils/logger.py -> bot -> корень)
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Пытаемся импортировать из конфига, или используем значения по умолчанию
try:
    from bot.config import LOG_LEVEL, LOG_FILE
    print("Импорт из bot.config успешен")
except ImportError:
    # Значения по умолчанию, если импорт не удался
    LOG_LEVEL = "INFO"
    LOG_FILE = "logs/bot.log"
    print(f"Используем значения по умолчанию: LOG_LEVEL={LOG_LEVEL}, LOG_FILE={LOG_FILE}")

# Создаем директорию для логов, если она не существует
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# Настраиваем логгер
def setup_logger():
    _logger = logging.getLogger('bot')
    _logger.setLevel(getattr(logging, LOG_LEVEL))
    
    # Очищаем существующие обработчики для избежания дупликатов
    if _logger.handlers:
        _logger.handlers = []
    
    # Формат сообщения лога
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Обработчик для консоли
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Обработчик для файла с ротацией
    file_handler = RotatingFileHandler(
        LOG_FILE, 
        maxBytes=10*1024*1024,  # 10 МБ
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    
    # Добавляем обработчики к логгеру
    _logger.addHandler(console_handler)
    _logger.addHandler(file_handler)
    
    return _logger

# Создаем экземпляр логгера
logger = setup_logger()

# Добавляем сообщение для проверки при запуске как скрипта
if __name__ == "__main__":
    print("Логгер успешно настроен и доступен как переменная 'logger'")
    logger.debug("Это отладочное сообщение")
    logger.info("Это информационное сообщение")
    logger.warning("Это предупреждение")
    logger.error("Это сообщение об ошибке")