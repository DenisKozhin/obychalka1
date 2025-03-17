# test_sqlalchemy.py
try:
    import sqlalchemy
    print(f"SQLAlchemy успешно импортирован! Версия: {sqlalchemy.__version__}")
    
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    print("AsyncSession успешно импортирован!")
    
    from bot.database.models import User, City, Store
    print("Модели успешно импортированы!")
except Exception as e:
    print(f"Ошибка импорта: {e}")