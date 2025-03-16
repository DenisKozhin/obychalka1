# test_import.py
try:
    from bot.database.database import Base, async_engine, AsyncSessionLocal
    print("Импорт успешен!")
    print(f"Base: {Base}")
    print(f"async_engine: {async_engine}")
    print(f"AsyncSessionLocal: {AsyncSessionLocal}")
except Exception as e:
    print(f"Ошибка импорта: {e}")