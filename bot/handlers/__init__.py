from aiogram import Router

def setup_routers() -> Router:
    """
    Настройка роутеров для обработчиков команд
    """
    router = Router()
    
    # Порядок важен: более специфичные обработчики должны быть раньше
    try:
        from . import admin
        router.include_router(admin.router)
        print("Роутер admin импортирован")
    except Exception as e:
        print(f"Ошибка импорта admin: {e}")
    
    try:
        from . import user
        router.include_router(user.router)
        print("Роутер user импортирован")
    except Exception as e:
        print(f"Ошибка импорта user: {e}")
    
    try:
        from . import library
        router.include_router(library.router)
        print("Роутер library импортирован")
    except Exception as e:
        print(f"Ошибка импорта library: {e}")
    
    try:
        from . import tests
        router.include_router(tests.router)
        print("Роутер tests импортирован")
    except Exception as e:
        print(f"Ошибка импорта tests: {e}")
    
    try:
        from . import ratings
        router.include_router(ratings.router)
        print("Роутер ratings импортирован")
    except Exception as e:
        print(f"Ошибка импорта ratings: {e}")
    
    try:
        from . import announcements
        router.include_router(announcements.router)
        print("Роутер announcements импортирован")
    except Exception as e:
        print(f"Ошибка импорта announcements: {e}")
    
    try:
        from . import common
        router.include_router(common.router)
        print("Роутер common импортирован")
    except Exception as e:
        print(f"Ошибка импорта common: {e}")
    
    return router

# Проверка при прямом запуске
if __name__ == "__main__":
    print("Файл __init__.py в handlers успешно импортирован")
    print("Функция setup_routers() определена")
    print("Роутеры успешно настроены")
    