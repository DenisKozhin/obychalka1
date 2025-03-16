from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import User, City, Store

# Функции для работы с городами
async def get_cities(session: AsyncSession):
    """Получение списка всех городов"""
    result = await session.execute(select(City))
    return result.scalars().all()

async def get_city_by_id(session: AsyncSession, city_id: int):
    """Получение города по ID"""
    return await session.get(City, city_id)

async def create_default_cities(session: AsyncSession):
    """Создание стандартных городов, если их нет в базе"""
    cities = await get_cities(session)
    
    if not cities:
        default_cities = ["Київ", "Львів", "Одеса", "Харків", "Дніпро"]
        for city_name in default_cities:
            city = City(name=city_name)
            session.add(city)
        await session.commit()
        
        # Получаем список городов после добавления
        return await get_cities(session)
    
    return cities

# Функции для работы с магазинами
async def get_stores_by_city(session: AsyncSession, city_id: int):
    """Получение списка магазинов для конкретного города"""
    result = await session.execute(select(Store).where(Store.city_id == city_id))
    return result.scalars().all()

async def get_store_by_id(session: AsyncSession, store_id: int):
    """Получение магазина по ID"""
    return await session.get(Store, store_id)

async def create_default_stores(session: AsyncSession, city_id: int):
    """Создание стандартных магазинов для города, если их нет"""
    stores = await get_stores_by_city(session, city_id)
    
    if not stores:
        city = await get_city_by_id(session, city_id)
        if city:
            store_count = 3  # Количество тестовых магазинов
            for i in range(1, store_count + 1):
                store = Store(name=f"Магазин {city.name} #{i}", city_id=city_id)
                session.add(store)
            await session.commit()
            
            # Получаем список магазинов после добавления
            return await get_stores_by_city(session, city_id)
    
    return stores

# Функции для работы с пользователями
async def get_user_by_id(session: AsyncSession, user_id: int):
    """Получение пользователя по ID"""
    result = await session.execute(select(User).where(User.user_id == user_id))
    return result.scalar_one_or_none()

async def create_user(session: AsyncSession, user_id: int, first_name: str, last_name: str, 
                     city_id: int, store_id: int, is_admin: bool = False):
    """Создание нового пользователя"""
    new_user = User(
        user_id=user_id,
        first_name=first_name,
        last_name=last_name,
        city_id=city_id,
        store_id=store_id,
        is_admin=is_admin
    )
    
    session.add(new_user)
    await session.commit()
    return new_user
