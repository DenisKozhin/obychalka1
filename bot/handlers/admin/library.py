import os
import sys
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Ensure the parent directory of 'bot' is in the system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Для запуска файла напрямую
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command

# Импортируем функции для работы с базой данных
from bot.database.operations_library import (
    get_categories, get_category_info, add_category, update_category, delete_category,
    get_articles_in_category, get_article, add_article, update_article, delete_article,
    add_article_image, delete_article_image
)

# Импортируем клавиатуры
from bot.keyboards.library_kb import (
    get_categories_kb, get_category_actions_kb, get_articles_kb, 
    get_article_actions_kb, get_manage_images_kb, get_send_article_kb,
    get_confirm_delete_kb
)

# Создаем класс для хранения состояний FSM (Finite State Machine)
class LibraryAdminStates(StatesGroup):
    # Состояния для работы с категориями
    waiting_for_category_name = State()
    waiting_for_subcategory_name = State()
    waiting_for_edit_category_name = State()
    
    # Состояния для работы со статьями
    waiting_for_article_title = State()
    waiting_for_article_content = State()
    waiting_for_article_images = State()
    
    # Состояния для редактирования статьи
    waiting_for_edit_article_title = State()
    waiting_for_edit_article_content = State()
    
    # Состояния для отправки статьи пользователям
    waiting_for_select_city = State()
    waiting_for_select_store = State()
    waiting_for_select_user = State()

# Создаем роутер для библиотеки знаний (для администраторов)
router = Router()

@router.callback_query(F.data == "admin_articles")
async def admin_articles_command(callback: CallbackQuery):
    """Обработчик команды администратора для управления статьями"""
    await show_admin_library_menu(callback)

@router.callback_query(F.data == "admin_back_to_library")
async def admin_back_to_library(callback: CallbackQuery):
    """Обработчик возврата к административному меню библиотеки"""
    await show_admin_library_menu(callback)

@router.callback_query(F.data == "admin_library")
async def admin_library_menu(callback: CallbackQuery):
    """Обработчик входа в административное меню библиотеки"""
    await show_admin_library_menu(callback)

async def show_admin_library_menu(callback: CallbackQuery):
    """Общая функция для отображения меню библиотеки администратора"""
    # Получаем корневые категории (уровень 1)
    categories = get_categories(parent_id=None)
    
    if not categories:
        # Если категорий нет, предлагаем создать первую
        await callback.message.edit_text(
            "Бібліотека знань порожня. Створіть першу категорію:",
            reply_markup=get_categories_kb([], include_back=True, admin_mode=True)
        )
        return
    
    await callback.message.edit_text(
        "Управління бібліотекою знань. Оберіть категорію:",
        reply_markup=get_categories_kb(categories, include_back=True, admin_mode=True)
    )
    await callback.answer()

@router.callback_query(F.data == "add_category")
async def add_category_command(callback: CallbackQuery, state: FSMContext):
    """Обработчик добавления новой корневой категории"""
    await callback.message.edit_text(
        "Введіть назву нової категорії (рівень 1):"
    )
    await state.set_state(LibraryAdminStates.waiting_for_category_name)
    await callback.answer()

@router.message(LibraryAdminStates.waiting_for_category_name)
async def process_category_name(message: Message, state: FSMContext):
    """Обработчик ввода названия новой категории"""
    category_name = message.text.strip()
    
    if len(category_name) < 3:
        await message.answer(
            "Назва категорії повинна містити не менше 3 символів. Спробуйте ще раз:"
        )
        return
    
    # Добавляем новую категорию уровня 1
    category_id = add_category(category_name, parent_id=None, level=1)
    
    if category_id:
        # Категория успешно добавлена
        await message.answer(
            f"Категорія '{category_name}' успішно додана!"
        )
        
        # Показываем обновленное меню категорий
        categories = get_categories(parent_id=None)
        await message.answer(
            "Управління бібліотекою знань. Оберіть категорію:",
            reply_markup=get_categories_kb(categories, include_back=True, admin_mode=True)
        )
    else:
        # Ошибка при добавлении категории
        await message.answer(
            f"Помилка: категорія з назвою '{category_name}' вже існує або виникла інша помилка."
        )
    
    # Сбрасываем состояние
    await state.clear()

@router.callback_query(F.data.startswith("admin_category_"))
async def admin_category_selected(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора категории администратором"""
    # Извлекаем ID категории из callback_data
    category_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о категории
    category = get_category_info(category_id)
    
    if not category:
        await callback.message.edit_text(
            "Категорія не знайдена. Поверніться до головного меню.",
            reply_markup=get_categories_kb([], include_back=True, admin_mode=True)
        )
        await callback.answer()
        return
    
    # Проверяем уровень категории
    if category["level"] < 3:
        # Если это категория 1 или 2 уровня, показываем опции управления категорией
        subcategories = get_categories(parent_id=category_id)
        
        # Сохраняем ID и уровень категории в состоянии для дальнейшего использования
        await state.update_data(category_id=category_id, level=category["level"])
        
        if not subcategories:
            await callback.message.edit_text(
                f"Категорія \"{category['name']}\" (рівень {category['level']}). Немає підкатегорій.\n\n"
                f"Виберіть дію:",
                reply_markup=get_category_actions_kb(category_id, category["parent_id"])
            )
        else:
            # Показываем список подкатегорий и действия с текущей категорией
            await callback.message.edit_text(
                f"Категорія \"{category['name']}\" (рівень {category['level']}). Підкатегорії:\n\n"
                f"Виберіть підкатегорію або дію з поточною категорією:",
                reply_markup=get_category_actions_kb(category_id, category["parent_id"])
            )
            
            # Показываем список подкатегорий в отдельном сообщении
            await callback.message.answer(
                "Підкатегорії:",
                reply_markup=get_categories_kb(subcategories, include_back=False, admin_mode=True)
            )
    else:
        # Если это категория 3 уровня (группа товаров), показываем опции и статьи
        articles = get_articles_in_category(category_id)
        
        # Сохраняем ID категории в состоянии для дальнейшего использования
        await state.update_data(category_id=category_id)
        
        await callback.message.edit_text(
            f"Група товарів \"{category['name']}\".\n\n"
            f"Виберіть дію:",
            reply_markup=get_category_actions_kb(category_id, category["parent_id"])
        )
        
        # Если есть статьи, показываем их в отдельном сообщении
        if articles:
            await callback.message.answer(
                "Статті в цій групі товарів:",
                reply_markup=get_articles_kb(articles, category_id, admin_mode=True)
            )
    
    await callback.answer()

@router.callback_query(F.data.startswith("add_subcategory_"))
async def add_subcategory_command(callback: CallbackQuery, state: FSMContext):
    """Обработчик добавления подкатегории"""
    # Извлекаем ID родительской категории из callback_data
    parent_id = int(callback.data.split("_")[1])
    
    # Получаем информацию о родительской категории
    parent_category = get_category_info(parent_id)
    
    if not parent_category:
        await callback.message.edit_text(
            "Батьківська категорія не знайдена. Поверніться до головного меню.",
            reply_markup=get_categories_kb([], include_back=True, admin_mode=True)
        )
        await callback.answer()
        return
    
    # Проверяем уровень родительской категории (можно добавлять подкатегорию только к уровням 1 и 2)
    if parent_category["level"] >= 3:
        await callback.message.edit_text(
            "Неможливо додати підкатегорію до групи товарів (рівень 3).",
            reply_markup=get_category_actions_kb(parent_id, parent_category["parent_id"])
        )
        await callback.answer()
        return
    
    # Сохраняем ID родительской категории и её уровень в состоянии
    await state.update_data(parent_id=parent_id, parent_level=parent_category["level"])
    
    await callback.message.edit_text(
        f"Введіть назву нової підкатегорії для \"{parent_category['name']}\" (рівень {parent_category['level'] + 1}):"
    )
    await state.set_state(LibraryAdminStates.waiting_for_subcategory_name)
    await callback.answer()

@router.message(LibraryAdminStates.waiting_for_subcategory_name)
async def process_subcategory_name(message: Message, state: FSMContext):
    """Обработчик ввода названия новой подкатегории"""
    subcategory_name = message.text.strip()
    
    if len(subcategory_name) < 3:
        await message.answer(
            "Назва підкатегорії повинна містити не менше 3 символів. Спробуйте ще раз:"
        )
        return
    
    # Получаем данные из состояния
    data = await state.get_data()
    parent_id = data.get("parent_id")
    parent_level = data.get("parent_level")
    
    if not parent_id or parent_level is None:
        await message.answer(
            "Помилка: відсутні дані про батьківську категорію. Почніть спочатку."
        )
        await state.clear()
        return
    
    # Добавляем новую подкатегорию
    subcategory_id = add_category(subcategory_name, parent_id=parent_id, level=parent_level + 1)
    
    if subcategory_id:
        # Подкатегория успешно добавлена
        await message.answer(
            f"Підкатегорія '{subcategory_name}' успішно додана!"
        )
        
        # Показываем обновленное меню категорий
        parent_category = get_category_info(parent_id)
        subcategories = get_categories(parent_id=parent_id)
        
        await message.answer(
            f"Категорія \"{parent_category['name']}\" (рівень {parent_category['level']}). Підкатегорії:",
            reply_markup=get_categories_kb(subcategories, include_back=True, admin_mode=True)
        )
    else:
        # Ошибка при добавлении подкатегории
        await message.answer(
            f"Помилка: підкатегорія з назвою '{subcategory_name}' вже існує або виникла інша помилка."
        )
    
    # Сбрасываем состояние
    await state.clear()

@router.callback_query(F.data.startswith("edit_category_"))
async def edit_category_command(callback: CallbackQuery, state: FSMContext):
    """Обработчик редактирования названия категории"""
    # Извлекаем ID категории из callback_data
    category_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о категории
    category = get_category_info(category_id)
    
    if not category:
        await callback.message.edit_text(
            "Категорія не знайдена. Поверніться до головного меню.",
            reply_markup=get_categories_kb([], include_back=True, admin_mode=True)
        )
        await callback.answer()
        return
    
    # Сохраняем ID категории в состоянии
    await state.update_data(category_id=category_id)
    
    await callback.message.edit_text(
        f"Поточна назва: \"{category['name']}\"\n\n"
        f"Введіть нову назву для категорії:"
    )
    await state.set_state(LibraryAdminStates.waiting_for_edit_category_name)
    await callback.answer()

@router.message(LibraryAdminStates.waiting_for_edit_category_name)
async def process_edit_category_name(message: Message, state: FSMContext):
    """Обработчик ввода нового названия категории"""
    new_name = message.text.strip()
    
    if len(new_name) < 3:
        await message.answer(
            "Назва категорії повинна містити не менше 3 символів. Спробуйте ще раз:"
        )
        return
    
    # Получаем ID категории из состояния
    data = await state.get_data()
    category_id = data.get("category_id")
    
    if not category_id:
        await message.answer(
            "Помилка: відсутні дані про категорію. Почніть спочатку."
        )
        await state.clear()
        return
    
    # Обновляем название категории
    success = update_category(category_id, new_name)
    
    if success:
        # Название успешно обновлено
        await message.answer(
            f"Назва категорії змінена на '{new_name}'!"
        )
        
        # Получаем обновленную информацию о категории
        category = get_category_info(category_id)
        
        # Проверяем, есть ли у категории родитель
        if category["parent_id"]:
            # Если есть родитель, возвращаемся к списку подкатегорий родителя
            parent_category = get_category_info(category["parent_id"])
            subcategories = get_categories(parent_id=category["parent_id"])
            
            await message.answer(
                f"Категорія \"{parent_category['name']}\". Підкатегорії:",
                reply_markup=get_categories_kb(subcategories, include_back=True, admin_mode=True)
            )
        else:
            # Если это корневая категория, возвращаемся к списку корневых категорий
            categories = get_categories(parent_id=None)
            
            await message.answer(
                "Управління бібліотекою знань. Оберіть категорію:",
                reply_markup=get_categories_kb(categories, include_back=True, admin_mode=True)
            )
    else:
        # Ошибка при обновлении названия
        await message.answer(
            f"Помилка: не вдалося змінити назву категорії. Можливо, категорія з назвою '{new_name}' вже існує."
        )
    
    # Сбрасываем состояние
    await state.clear()

@router.callback_query(F.data.startswith("delete_category_"))
async def delete_category_command(callback: CallbackQuery):
    """Обработчик удаления категории"""
    # Извлекаем ID категории из callback_data
    category_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о категории
    category = get_category_info(category_id)
    
    if not category:
        await callback.message.edit_text(
            "Категорія не знайдена. Поверніться до головного меню.",
            reply_markup=get_categories_kb([], include_back=True, admin_mode=True)
        )
        await callback.answer()
        return
    
    # Определяем callback для возврата
    if category["parent_id"]:
        return_callback = f"admin_category_{category['parent_id']}"
    else:
        return_callback = "admin_library"
    
    # Показываем подтверждение удаления
    await callback.message.edit_text(
        f"Ви впевнені, що хочете видалити категорію \"{category['name']}\"?\n\n"
        f"Увага! Будуть видалені всі підкатегорії, статті та тести в цій категорії!",
        reply_markup=get_confirm_delete_kb("category", category_id, return_callback)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_delete_category_"))
async def confirm_delete_category(callback: CallbackQuery):
    """Обработчик подтверждения удаления категории"""
    # Извлекаем ID категории из callback_data
    category_id = int(callback.data.split("_")[3])
    
    # Получаем информацию о категории перед удалением
    category = get_category_info(category_id)
    
    if not category:
        await callback.message.edit_text(
            "Категорія не знайдена. Поверніться до головного меню.",
            reply_markup=get_categories_kb([], include_back=True, admin_mode=True)
        )
        await callback.answer()
        return
    
    # Сохраняем parent_id перед удалением
    parent_id = category["parent_id"]
    
    # Удаляем категорию и все связанные данные
    success = delete_category(category_id)
    
    if success:
        # Категория успешно удалена
        if parent_id:
            # Если это подкатегория, возвращаемся к родительской категории
            parent_category = get_category_info(parent_id)
            subcategories = get_categories(parent_id=parent_id)
            
            if parent_category:
                await callback.message.edit_text(
                    f"Категорія \"{category['name']}\" успішно видалена!\n\n"
                    f"Категорія \"{parent_category['name']}\". Підкатегорії:",
                    reply_markup=get_categories_kb(subcategories, include_back=True, admin_mode=True)
                )
            else:
                # Если родительская категория не найдена, возвращаемся к корневым категориям
                categories = get_categories(parent_id=None)
                
                await callback.message.edit_text(
                    f"Категорія \"{category['name']}\" успішно видалена!\n\n"
                    f"Управління бібліотекою знань. Оберіть категорію:",
                    reply_markup=get_categories_kb(categories, include_back=True, admin_mode=True)
                )
        else:
            # Если это корневая категория, возвращаемся к списку корневых категорий
            categories = get_categories(parent_id=None)
            
            await callback.message.edit_text(
                f"Категорія \"{category['name']}\" успішно видалена!\n\n"
                f"Управління бібліотекою знань. Оберіть категорію:",
                reply_markup=get_categories_kb(categories, include_back=True, admin_mode=True)
            )
    else:
        # Ошибка при удалении категории
        await callback.message.edit_text(
            f"Помилка: не вдалося видалити категорію \"{category['name']}\".",
            reply_markup=get_category_actions_kb(category_id, parent_id)
        )
    
    await callback.answer()

@router.callback_query(F.data.startswith("list_articles_"))
async def list_articles_command(callback: CallbackQuery):
    """Обработчик просмотра списка статей в категории"""
    # Извлекаем ID категории из callback_data
    category_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о категории
    category = get_category_info(category_id)
    
    if not category:
        await callback.message.edit_text(
            "Категорія не знайдена. Поверніться до головного меню.",
            reply_markup=get_categories_kb([], include_back=True, admin_mode=True)
        )
        await callback.answer()
        return
    
    # Получаем статьи в категории
    articles = get_articles_in_category(category_id)
    
    if not articles:
        await callback.message.edit_text(
            f"У категорії \"{category['name']}\" немає статей.",
            reply_markup=get_category_actions_kb(category_id, category["parent_id"])
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        f"Статті в категорії \"{category['name']}\":",
        reply_markup=get_articles_kb(articles, category_id, admin_mode=True)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("add_article_"))
async def add_article_command(callback: CallbackQuery, state: FSMContext):
    """Обработчик добавления новой статьи"""
    # Извлекаем ID категории из callback_data
    category_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о категории
    category = get_category_info(category_id)
    
    if not category:
        await callback.message.edit_text(
            "Категорія не знайдена. Поверніться до головного меню.",
            reply_markup=get_categories_kb([], include_back=True, admin_mode=True)
        )
        await callback.answer()
        return
    
    # Сохраняем ID категории в состоянии
    await state.update_data(category_id=category_id)
    
    await callback.message.edit_text(
        f"Створення нової статті в категорії \"{category['name']}\".\n\n"
        f"Введіть заголовок статті (максимум 200 символів):"
    )
    await state.set_state(LibraryAdminStates.waiting_for_article_title)
    await callback.answer()

@router.message(LibraryAdminStates.waiting_for_article_title)
async def process_article_title(message: Message, state: FSMContext):
    """Обработчик ввода заголовка статьи"""
    title = message.text.strip()
    
    if len(title) < 3:
        await message.answer(
            "Заголовок статті повинен містити не менше 3 символів. Спробуйте ще раз:"
        )
        return
    
    if len(title) > 200:
        await message.answer(
            "Заголовок статті не повинен перевищувати 200 символів. Поточна довжина: "
            f"{len(title)} символів. Спробуйте ще раз:"
        )
        return
    
    # Сохраняем заголовок в состоянии
    await state.update_data(article_title=title)
    
    await message.answer(
        "Тепер введіть текст статті (максимум 4000 символів):\n\n"
        "Ви можете використовувати Markdown для форматування:\n"
        "**жирний текст** - виділення тексту жирним\n"
        "*курсив* - виділення тексту курсивом\n"
        "- список - створення списку\n"
        "1. нумерований список - створення нумерованого списку"
    )
    await state.set_state(LibraryAdminStates.waiting_for_article_content)

@router.message(LibraryAdminStates.waiting_for_article_content)
async def process_article_content(message: Message, state: FSMContext):
    """Обработчик ввода текста статьи"""
    content = message.text.strip()
    
    if len(content) < 10:
        await message.answer(
            "Текст статті повинен містити не менше 10 символів. Спробуйте ще раз:"
        )
        return
    
    if len(content) > 4000:
        await message.answer(
            "Текст статті не повинен перевищувати 4000 символів. Поточна довжина: "
            f"{len(content)} символів. Спробуйте ще раз:"
        )
        return
    
    # Получаем данные из состояния
    data = await state.get_data()
    category_id = data.get("category_id")
    title = data.get("article_title")
    
    if not category_id or not title:
        await message.answer(
            "Помилка: відсутні дані про категорію або заголовок. Почніть спочатку."
        )
        await state.clear()
        return
    
    # Добавляем статью в базу данных
    article_id = add_article(title, content, category_id, message.from_user.id)
    
    if article_id:
        # Статья успешно добавлена
        await message.answer(
            f"Стаття \"{title}\" успішно додана!\n\n"
            f"Бажаєте додати зображення до статті? (максимум 5 зображень)\n"
            f"Відправте зображення або натисніть 'Пропустити'.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Пропустити", callback_data=f"skip_images_{article_id}")]
            ])
        )
        
        # Сохраняем ID статьи и счетчик изображений в состоянии
        await state.update_data(article_id=article_id, image_count=0)
        await state.set_state(LibraryAdminStates.waiting_for_article_images)
    else:
        # Ошибка при добавлении статьи
        await message.answer(
            "Помилка: не вдалося додати статтю. Спробуйте ще раз або зверніться до адміністратора."
        )
        await state.clear()

@router.message(LibraryAdminStates.waiting_for_article_images, F.photo)
async def process_article_image(message: Message, state: FSMContext):
    """Обработчик загрузки изображения для статьи"""
    # Получаем данные из состояния
    data = await state.get_data()
    article_id = data.get("article_id")
    image_count = data.get("image_count", 0)
    
    if not article_id:
        await message.answer(
            "Помилка: відсутні дані про статтю. Почніть спочатку."
        )
        await state.clear()
        return
    
    # Проверяем, не превышено ли максимальное количество изображений
    if image_count >= 5:
        await message.answer(
            "Ви вже додали максимальну кількість зображень (5)."
        )
        return
    
    # Получаем информацию о фото
    photo = message.photo[-1]  # Берем фото с наивысшим разрешением
    file_id = photo.file_id
    file_unique_id = photo.file_unique_id
    
    # Добавляем изображение к статье
    image_id = add_article_image(article_id, file_id, file_unique_id, image_count)
    
    if image_id:
        # Изображение успешно добавлено
        image_count += 1
        await state.update_data(image_count=image_count)
        
        if image_count < 5:
            await message.answer(
                f"Зображення {image_count}/5 додано!\n\n"
                f"Відправте ще зображення або натисніть 'Завершити'.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Завершити", callback_data=f"skip_images_{article_id}")]
                ])
            )
        else:
            await message.answer(
                "Ви додали максимальну кількість зображень (5).",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Завершити", callback_data=f"skip_images_{article_id}")]
                ])
            )
    else:
        # Ошибка при добавлении изображения
        await message.answer(
            "Помилка: не вдалося додати зображення. Спробуйте ще раз або натисніть 'Пропустити'.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Пропустити", callback_data=f"skip_images_{article_id}")]
            ])
        )

@router.callback_query(F.data.startswith("skip_images_"))
async def skip_images(callback: CallbackQuery, state: FSMContext):
    """Обработчик пропуска добавления изображений"""
    # Извлекаем ID статьи из callback_data
    article_id = int(callback.data.split("_")[2])
    
    # Получаем данные из состояния
    data = await state.get_data()
    category_id = data.get("category_id")
    
    if not category_id:
        await callback.message.edit_text(
            "Помилка: відсутні дані про категорію. Повернутися до головного меню."
        )
        await state.clear()
        await callback.answer()
        return
    
    # Получаем статью
    article = get_article(article_id)
    
    if not article:
        await callback.message.edit_text(
            "Помилка: статтю не знайдено. Повернутися до головного меню."
        )
        await state.clear()
        await callback.answer()
        return
    
    # Получаем категорию
    category = get_category_info(category_id)
    
    # Завершаем добавление статьи
    await callback.message.edit_text(
        f"Стаття \"{article['title']}\" успішно створена!"
    )
    
    # Показываем статьи в категории
    articles = get_articles_in_category(category_id)
    
    await callback.message.answer(
        f"Статті в категорії \"{category['name']}\":",
        reply_markup=get_articles_kb(articles, category_id, admin_mode=True)
    )
    
    # Сбрасываем состояние
    await state.clear()
    await callback.answer()

@router.callback_query(F.data.startswith("admin_article_"))
async def admin_article_selected(callback: CallbackQuery):
    """Обработчик выбора статьи администратором"""
    # Извлекаем ID статьи из callback_data
    article_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о статье
    article = get_article(article_id)
    
    if not article:
        await callback.message.edit_text(
            "Стаття не знайдена. Поверніться до головного меню.",
            reply_markup=get_categories_kb([], include_back=True, admin_mode=True)
        )
        await callback.answer()
        return
    
    # Создаем текст сообщения с информацией о статье
    text = (
        f"📖 <b>{article['title']}</b>\n\n"
        f"{article['content']}\n\n"
        f"Категорія: {article['category_name']}\n"
        f"Автор: {article['author']}\n"
        f"Створено: {article['created_at']}\n"
        f"Останнє оновлення: {article['updated_at']}\n\n"
        f"Зображення: {len(article['images'])}/5\n"
        f"Тести: {len(article['tests'])}\n\n"
        f"Виберіть дію:"
    )
    
    # Показываем информацию о статье и клавиатуру действий
    await callback.message.edit_text(
        text,
        reply_markup=get_article_actions_kb(article_id, article['category_id']),
        parse_mode="HTML"
    )
    
    # Если у статьи есть изображения, отправляем их в отдельных сообщениях
    images = article.get("images", [])
    
    if images:
        for i, image in enumerate(images):
            await callback.message.answer_photo(
                photo=image['file_id'],
                caption=f"Зображення {i+1}/{len(images)}"
            )
    
    await callback.answer()

@router.callback_query(F.data.startswith("edit_article_"))
async def edit_article_command(callback: CallbackQuery, state: FSMContext):
    """Обработчик редактирования статьи"""
    # Извлекаем ID статьи из callback_data
    article_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о статье
    article = get_article(article_id)
    
    if not article:
        await callback.message.edit_text(
            "Стаття не знайдена. Поверніться до головного меню.",
            reply_markup=get_categories_kb([], include_back=True, admin_mode=True)
        )
        await callback.answer()
        return
    
    # Сохраняем ID статьи и категории в состоянии
    await state.update_data(article_id=article_id, category_id=article['category_id'])
    
    await callback.message.edit_text(
        f"Редагування статті \"{article['title']}\".\n\n"
        f"Поточний заголовок: {article['title']}\n\n"
        f"Введіть новий заголовок або відправте символ '-', щоб залишити поточний:"
    )
    await state.set_state(LibraryAdminStates.waiting_for_edit_article_title)
    await callback.answer()

@router.message(LibraryAdminStates.waiting_for_edit_article_title)
async def process_edit_article_title(message: Message, state: FSMContext):
    """Обработчик ввода нового заголовка статьи"""
    new_title = message.text.strip()
    
    # Получаем данные из состояния
    data = await state.get_data()
    article_id = data.get("article_id")
    
    if not article_id:
        await message.answer(
            "Помилка: відсутні дані про статтю. Почніть спочатку."
        )
        await state.clear()
        return
    
    # Получаем текущую статью
    article = get_article(article_id)
    
    if not article:
        await message.answer(
            "Помилка: статтю не знайдено. Повернутися до головного меню."
        )
        await state.clear()
        return
    
    # Проверяем, нужно ли обновлять заголовок
    if new_title == "-":
        # Пользователь решил оставить текущий заголовок
        new_title = None
    else:
        # Проверяем длину нового заголовка
        if len(new_title) < 3:
            await message.answer(
                "Заголовок статті повинен містити не менше 3 символів. Спробуйте ще раз:"
            )
            return
        
        if len(new_title) > 200:
            await message.answer(
                "Заголовок статті не повинен перевищувати 200 символів. Поточна довжина: "
                f"{len(new_title)} символів. Спробуйте ще раз:"
            )
            return
    
    # Сохраняем новый заголовок в состоянии
    await state.update_data(new_title=new_title)
    
    await message.answer(
        f"Поточний текст статті:\n\n{article['content']}\n\n"
        f"Введіть новий текст статті або відправте символ '-', щоб залишити поточний:"
    )
    await state.set_state(LibraryAdminStates.waiting_for_edit_article_content)

@router.message(LibraryAdminStates.waiting_for_edit_article_content)
async def process_edit_article_content(message: Message, state: FSMContext):
    """Обработчик ввода нового текста статьи"""
    new_content = message.text.strip()
    
    # Получаем данные из состояния
    data = await state.get_data()
    article_id = data.get("article_id")
    category_id = data.get("category_id")
    new_title = data.get("new_title")
    
    if not article_id or not category_id:
        await message.answer(
            "Помилка: відсутні дані про статтю або категорію. Почніть спочатку."
        )
        await state.clear()
        return
    
    # Проверяем, нужно ли обновлять содержание
    if new_content == "-":
        # Пользователь решил оставить текущее содержание
        new_content = None
    else:
        # Проверяем длину нового содержания
        if len(new_content) < 10:
            await message.answer(
                "Текст статті повинен містити не менше 10 символів. Спробуйте ще раз:"
            )
            return
        
        if len(new_content) > 4000:
            await message.answer(
                "Текст статті не повинен перевищувати 4000 символів. Поточна довжина: "
                f"{len(new_content)} символів. Спробуйте ще раз:"
            )
            return
    
    # Обновляем статью в базе данных
    success = update_article(article_id, title=new_title, content=new_content)
    
    if success:
        # Статья успешно обновлена
        await message.answer(
            "Стаття успішно оновлена!"
        )
        
        # Получаем обновленную статью
        updated_article = get_article(article_id)
        
        # Создаем текст сообщения с информацией о статье
        text = (
            f"📖 <b>{updated_article['title']}</b>\n\n"
            f"{updated_article['content']}\n\n"
            f"Категорія: {updated_article['category_name']}\n"
            f"Автор: {updated_article['author']}\n"
            f"Створено: {updated_article['created_at']}\n"
            f"Останнє оновлення: {updated_article['updated_at']}\n\n"
            f"Зображення: {len(updated_article['images'])}/5\n"
            f"Тести: {len(updated_article['tests'])}\n\n"
            f"Виберіть дію:"
        )
        
        # Показываем обновленную информацию о статье и клавиатуру действий
        await message.answer(
            text,
            reply_markup=get_article_actions_kb(article_id, category_id),
            parse_mode="HTML"
        )
        
        # Если у статьи есть изображения, отправляем их в отдельных сообщениях
        images = updated_article.get("images", [])
        
        if images:
            for i, image in enumerate(images):
                await message.answer_photo(
                    photo=image['file_id'],
                    caption=f"Зображення {i+1}/{len(images)}"
                )
    else:
        # Ошибка при обновлении статьи
        await message.answer(
            "Помилка: не вдалося оновити статтю. Спробуйте ще раз або зверніться до адміністратора."
        )
    
    # Сбрасываем состояние
    await state.clear()

@router.callback_query(F.data.startswith("manage_images_"))
async def manage_images_command(callback: CallbackQuery):
    """Обработчик управления изображениями статьи"""
    # Извлекаем ID статьи из callback_data
    article_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о статье
    article = get_article(article_id)
    
    if not article:
        await callback.message.edit_text(
            "Стаття не знайдена. Поверніться до головного меню.",
            reply_markup=get_categories_kb([], include_back=True, admin_mode=True)
        )
        await callback.answer()
        return
    
    # Получаем изображения статьи
    images = article.get("images", [])
    
    await callback.message.edit_text(
        f"Управління зображеннями статті \"{article['title']}\".\n\n"
        f"Поточна кількість зображень: {len(images)}/5\n\n"
        f"Натисніть на зображення, щоб видалити його, або додайте нове зображення:",
        reply_markup=get_manage_images_kb(article_id, images)
    )
    
    # Если у статьи есть изображения, отправляем их в отдельных сообщениях
    if images:
        for i, image in enumerate(images):
            await callback.message.answer_photo(
                photo=image['file_id'],
                caption=f"Зображення {i+1}/{len(images)}"
            )
    
    await callback.answer()

@router.callback_query(F.data.startswith("add_image_"))
async def add_image_command(callback: CallbackQuery, state: FSMContext):
    """Обработчик добавления изображения к статье"""
    # Извлекаем ID статьи из callback_data
    article_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о статье
    article = get_article(article_id)
    
    if not article:
        await callback.message.edit_text(
            "Стаття не знайдена. Поверніться до головного меню.",
            reply_markup=get_categories_kb([], include_back=True, admin_mode=True)
        )
        await callback.answer()
        return
    
    # Получаем изображения статьи
    images = article.get("images", [])
    
    if len(images) >= 5:
        await callback.message.edit_text(
            "Ви вже додали максимальну кількість зображень (5).",
            reply_markup=get_manage_images_kb(article_id, images)
        )
        await callback.answer()
        return
    
    # Сохраняем ID статьи в состоянии
    await state.update_data(article_id=article_id, image_count=len(images))
    
    await callback.message.edit_text(
        f"Відправте нове зображення для статті \"{article['title']}\":\n\n"
        f"Поточна кількість зображень: {len(images)}/5"
    )
    await state.set_state(LibraryAdminStates.waiting_for_article_images)
    await callback.answer()

@router.callback_query(F.data.startswith("delete_image_"))
async def delete_image_command(callback: CallbackQuery):
    """Обработчик удаления изображения"""
    # Извлекаем ID изображения из callback_data
    image_id = int(callback.data.split("_")[2])
    
    # Удаляем изображение
    success = delete_article_image(image_id)
    
    # Получаем ID статьи
    message_text = callback.message.text
    article_title = message_text.split('"')[1] if '"' in message_text else "неизвестной статьи"
    
    # Ищем ID статьи в тексте сообщения
    article_id = None
    for entity in callback.message.entities:
        if entity.type == "text_link" and "article_id=" in entity.url:
            article_id = int(entity.url.split("article_id=")[1])
            break
    
    if not article_id:
        # Если не удалось найти ID статьи в тексте, пытаемся найти его в inline_keyboard
        for row in callback.message.reply_markup.inline_keyboard:
            for button in row:
                if button.callback_data and button.callback_data.startswith("add_image_"):
                    article_id = int(button.callback_data.split("_")[2])
                    break
    
    if not article_id:
        await callback.message.edit_text(
            "Помилка: неможливо визначити ID статті. Поверніться до головного меню."
        )
        await callback.answer()
        return
    
    # Получаем обновленную информацию о статье
    article = get_article(article_id)
    
    if not article:
        await callback.message.edit_text(
            "Стаття не знайдена. Поверніться до головного меню.",
            reply_markup=get_categories_kb([], include_back=True, admin_mode=True)
        )
        await callback.answer()
        return
    
    # Получаем обновленный список изображений
    images = article.get("images", [])
    
    if success:
        await callback.message.edit_text(
            f"Зображення успішно видалене!\n\n"
            f"Управління зображеннями статті \"{article['title']}\".\n\n"
            f"Поточна кількість зображень: {len(images)}/5\n\n"
            f"Натисніть на зображення, щоб видалити його, або додайте нове зображення:",
            reply_markup=get_manage_images_kb(article_id, images)
        )
        
        # Если у статьи есть изображения, отправляем их в отдельных сообщениях
        if images:
            for i, image in enumerate(images):
                await callback.message.answer_photo(
                    photo=image['file_id'],
                    caption=f"Зображення {i+1}/{len(images)}"
                )
    else:
        await callback.message.edit_text(
            "Помилка: не вдалося видалити зображення. Спробуйте ще раз або зверніться до адміністратора.",
            reply_markup=get_manage_images_kb(article_id, images)
        )
    
    await callback.answer()

@router.callback_query(F.data.startswith("delete_article_"))
async def delete_article_command(callback: CallbackQuery):
    """Обработчик удаления статьи"""
    # Извлекаем ID статьи из callback_data
    article_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о статье
    article = get_article(article_id)
    
    if not article:
        await callback.message.edit_text(
            "Стаття не знайдена. Поверніться до головного меню.",
            reply_markup=get_categories_kb([], include_back=True, admin_mode=True)
        )
        await callback.answer()
        return
    
    # Определяем callback для возврата
    return_callback = f"list_articles_{article['category_id']}"
    
    # Показываем подтверждение удаления
    await callback.message.edit_text(
        f"Ви впевнені, що хочете видалити статтю \"{article['title']}\"?\n\n"
        f"Увага! Будуть видалені всі зображення та тести, пов'язані з цією статтею!",
        reply_markup=get_confirm_delete_kb("article", article_id, return_callback)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_delete_article_"))
async def confirm_delete_article(callback: CallbackQuery):
    """Обработчик подтверждения удаления статьи"""
    # Извлекаем ID статьи из callback_data
    article_id = int(callback.data.split("_")[3])
    
    # Получаем информацию о статье перед удалением
    article = get_article(article_id)
    
    if not article:
        await callback.message.edit_text(
            "Стаття не знайдена. Поверніться до головного меню.",
            reply_markup=get_categories_kb([], include_back=True, admin_mode=True)
        )
        await callback.answer()
        return
    
    # Сохраняем category_id перед удалением
    category_id = article["category_id"]
    
    # Удаляем статью и все связанные данные
    success = delete_article(article_id)
    
    if success:
        # Статья успешно удалена
        await callback.message.edit_text(
            f"Стаття \"{article['title']}\" успішно видалена!"
        )
        
        # Получаем обновленный список статей в категории
        articles = get_articles_in_category(category_id)
        
        if articles:
            # Если есть другие статьи, показываем их
            await callback.message.answer(
                f"Статті в категорії \"{article['category_name']}\":",
                reply_markup=get_articles_kb(articles, category_id, admin_mode=True)
            )
        else:
            # Если статей нет, возвращаемся к категории
            category = get_category_info(category_id)
            
            if category:
                await callback.message.answer(
                    f"У категорії \"{category['name']}\" немає статей.",
                    reply_markup=get_category_actions_kb(category_id, category["parent_id"])
                )
            else:
                # Если категория не найдена, возвращаемся к корневым категориям
                categories = get_categories(parent_id=None)
                
                await callback.message.answer(
                    "Управління бібліотекою знань. Оберіть категорію:",
                    reply_markup=get_categories_kb(categories, include_back=True, admin_mode=True)
                )
    else:
        # Ошибка при удалении статьи
        await callback.message.edit_text(
            f"Помилка: не вдалося видалити статтю \"{article['title']}\".",
            reply_markup=get_article_actions_kb(article_id, category_id)
        )
    
    await callback.answer()

@router.callback_query(F.data.startswith("send_article_"))
async def send_article_command(callback: CallbackQuery):
    """Обработчик отправки статьи пользователям"""
    # Извлекаем ID статьи из callback_data
    article_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о статье
    article = get_article(article_id)
    
    if not article:
        await callback.message.edit_text(
            "Стаття не знайдена. Поверніться до головного меню.",
            reply_markup=get_categories_kb([], include_back=True, admin_mode=True)
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        f"Відправка статті \"{article['title']}\" користувачам.\n\n"
        f"Виберіть отримувачів:",
        reply_markup=get_send_article_kb(article_id)
    )
    await callback.answer()

# Этот код нужно будет дополнить, когда будет реализована система тестирования
@router.callback_query(F.data.startswith("add_test_"))
async def add_test_command(callback: CallbackQuery):
    """Обработчик добавления теста к статье"""
    # Извлекаем ID статьи из callback_data
    article_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о статье
    article = get_article(article_id)
    
    if not article:
        await callback.message.edit_text(
            "Стаття не знайдена. Поверніться до головного меню.",
            reply_markup=get_categories_kb([], include_back=True, admin_mode=True)
        )
        await callback.answer()
        return
    
    # Проверяем, есть ли уже тесты у статьи
    if article.get("tests"):
        await callback.message.edit_text(
            "До цієї статті вже прикріплені тести. Спочатку видаліть існуючі тести.",
            reply_markup=get_article_actions_kb(article_id, article["category_id"])
        )
        await callback.answer()
        return
    
    # Пока тесты не реализованы, показываем сообщение
    await callback.message.edit_text(
        "Функція додавання тестів знаходиться в розробці.",
        reply_markup=get_article_actions_kb(article_id, article["category_id"])
    )
    await callback.answer()
    