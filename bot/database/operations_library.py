from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import User, City, Store


# Добавьте эти функции в bot/database/operations_library.py

# Функции для управления городами
async def create_city(session: AsyncSession, name: str):
    """Создание нового города"""
    try:
        city = City(name=name)
        session.add(city)
        await session.commit()
        await session.refresh(city)
        return city
    except Exception as e:
        await session.rollback()
        if "UNIQUE constraint failed" in str(e):
            return None  # Город с таким названием уже существует
        raise e

async def update_city_name(session: AsyncSession, city_id: int, new_name: str):
    """Обновление названия города"""
    try:
        result = await session.execute(
            select(City).where(City.city_id == city_id)
        )
        city = result.scalar_one_or_none()
        
        if not city:
            return False
        
        city.name = new_name
        await session.commit()
        return True
    except Exception as e:
        await session.rollback()
        if "UNIQUE constraint failed" in str(e):
            return False  # Город с таким названием уже существует
        raise e

async def delete_city(session: AsyncSession, city_id: int):
    """Удаление города и всех его магазинов"""
    try:
        # Удаляем все магазины в городе
        await session.execute(
            delete(Store).where(Store.city_id == city_id)
        )
        
        # Удаляем город
        result = await session.execute(
            delete(City).where(City.city_id == city_id)
        )
        
        await session.commit()
        return True
    except Exception as e:
        await session.rollback()
        raise e

# Функции для управления магазинами
async def create_store(session: AsyncSession, name: str, city_id: int):
    """Создание нового магазина"""
    try:
        store = Store(name=name, city_id=city_id)
        session.add(store)
        await session.commit()
        await session.refresh(store)
        return store
    except Exception as e:
        await session.rollback()
        raise e

async def update_store_name(session: AsyncSession, store_id: int, new_name: str):
    """Обновление названия магазина"""
    try:
        result = await session.execute(
            select(Store).where(Store.store_id == store_id)
        )
        store = result.scalar_one_or_none()
        
        if not store:
            return False
        
        store.name = new_name
        await session.commit()
        return True
    except Exception as e:
        await session.rollback()
        raise e

async def delete_store(session: AsyncSession, store_id: int):
    """Удаление магазина"""
    try:
        result = await session.execute(
            delete(Store).where(Store.store_id == store_id)
        )
        
        await session.commit()
        return True
    except Exception as e:
        await session.rollback()
        raise e

# Добавьте необходимые импорты в начало файла
from sqlalchemy import select, delete
from bot.database.models import City, Store, User