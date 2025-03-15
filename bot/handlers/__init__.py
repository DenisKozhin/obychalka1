from aiogram import Router

def setup_routers() -> Router:
    """
    Настройка роутеров для обработчиков команд
    """
    router = Router()
    
    # Важно: меняем порядок импорта, чтобы более специфичные обработчики были первыми
    try:
        from . import user
        router.include_router(user.router)
        print("Роутер user импортирован")
    except Exception as e:
        print(f"Ошибка импорта user: {e}")
    
    try:
        from . import admin
        router.include_router(admin.router)
        print("Роутер admin импортирован")
    except Exception as e:
        print(f"Ошибка импорта admin: {e}")
    
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