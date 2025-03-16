import sys
import os

# Добавляем путь к корневой директории проекта, если запускаем файл напрямую
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from bot.config import DATABASE_URL

# Создаем базовый класс для моделей
Base = declarative_base()

# Создаем синхронный движок для Alembic и других задач
engine = create_engine(DATABASE_URL)

# Создаем асинхронный движок для работы бота
# Заменяем postgresql:// на postgresql+asyncpg:// для асинхронной работы
#async_engine = create_async_engine(
#    DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://'),
#    echo=False
#)
# Изменим создание async_engine
async_engine = create_async_engine(
    "sqlite+aiosqlite:///bot.db",  # Используем aiosqlite для асинхронного доступа
    echo=False
)


# Создаем фабрику сессий для синхронного использования
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Создаем фабрику сессий для асинхронного использования
AsyncSessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=async_engine, 
    class_=AsyncSession,
    expire_on_commit=False
)

def get_db():
    """
    Получение синхронной сессии базы данных.
    Используется как контекстный менеджер для Alembic и других синхронных операций.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_async_db():
    """
    Получение асинхронной сессии базы данных.
    Используется как контекстный менеджер для асинхронных операций в боте.
    """
    async with AsyncSessionLocal() as session:
        yield session

# Проверка при прямом запуске
if __name__ == "__main__":
    print("Модуль database.py успешно загружен")
    print("Base, engine, async_engine, SessionLocal, AsyncSessionLocal определены")