# import os
# import sys
# from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# # Для запуска файла напрямую
# if __name__ == "__main__":
#     sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# from aiogram import Router, F
# from aiogram.types import Message, CallbackQuery
# from aiogram.fsm.context import FSMContext
# from aiogram.fsm.state import State, StatesGroup
# from aiogram.filters import Command

# # Импортируем функции для работы с базой данных
# from bot.database.operations_library import (
#     get_categories, get_category_info, add_category, update_category, delete_category,
#     get_articles_in_category, get_article, add_article, update_article, delete_article,
#     add_article_image, delete_article_image
# )

# # Импортируем клавиатуры
# from keyboards.library_kb import (
#     get_categories_kb, get_category_actions_kb, get_articles_kb, 
#     get_article_actions_kb, get_manage_images_kb, get_send_article_kb,
#     get_confirm_delete_kb
# )

# # Создаем класс для хранения состояний FSM (Finite State Machine)
# class LibraryAdminStates(StatesGroup):
#     # Состояния для работы с категориями
#     waiting_for_category_name = State()
#     waiting_for_subcategory_name = State()
#     waiting_for_edit_category_name = State()
    
#     # Состояния для работы со статьями
#     waiting_for_article_title = State()
#     waiting_for_article_content = State()
#     waiting_for_article_images = State()
    
#     # Состояния для редактирования статьи
#     waiting_for_edit_article_title = State()
#     waiting_for_edit_article_content = State()
    
#     # Состояния для отправки статьи пользователям
#     waiting_for_select_city = State()
#     waiting_for_select_store = State()
#     waiting_for_select_user = State()

# # Создаем роутер для библиотеки знаний (для администраторов)
# router = Router()

# @router.callback_query(F.data == "admin_articles")
# async def admin_articles_command(callback: CallbackQuery):
#     """Обработчик команды администратора для управления статьями"""
#     await show_admin_library_menu(callback)

# @router.callback_query(F.data == "admin_back_to_library")
# async def admin_back_to_library(callback: CallbackQuery):
#     """Обработчик возврата к административному меню библиотеки"""
#     await show_admin_library_menu(callback)

# @router.callback_query(F.data == "admin_library")
# async def admin_library_menu(callback: CallbackQuery):
#     """Обработчик входа в административное меню библиотеки"""
#     await show_admin_library_menu(callback)

# async def show_admin_library_menu(callback: CallbackQuery):
#     """Общая функция для отображения меню библиотеки администратора"""
#     # Получаем корневые категории (уровень 1)
#     categories = get_categories(parent_id=None)
    
#     if not categories:
#         # Если категорий нет, предлагаем создать первую
#         await callback.message.edit_text(
#             "Бібліотека знань порожня. Створіть першу категорію:",
#             reply_markup=get_categories_kb([], include_back=True, admin_mode=True)
#         )
#         return
    
#     await callback.message.edit_text(
#         "Управління бібліотекою знань. Оберіть категорію:",
#         reply_markup=get_categories_kb(categories, include_back=True, admin_mode=True)
#     )
#     await callback.answer()

# @router.callback_query(F.data == "add_category")
# async def add_category_command(callback: CallbackQuery, state: FSMContext):
#     """Обработчик добавления новой корневой категории"""
#     await callback.message.edit_text(
#         "Введіть назву нової категорії (рівень 1):"
#     )
#     await state.set_state(LibraryAdminStates.waiting_for_category_name)
#     await callback.answer()

# @router.message(LibraryAdminStates.waiting_for_category_name)
# async def process_category_name(message: Message, state: FSMContext):
#     """Обработчик ввода названия новой категории"""
#     category_name = message.text.strip()
    
#     if len(category_name) < 3:
#         await message.answer(
#             "Назва категорії повинна містити не менше 3 символів. Спробуйте ще раз:"
#         )
#         return
    
#     # Добавляем новую категорию уровня 1
#     category_id = add_category(category_name, parent_id=None, level=1)
    
#     if category_id:
#         # Категория успешно добавлена
#         await message.answer(
#             f"Категорія '{category_name}' успішно додана!"
#         )
        
#         # Показываем обновленное меню категорий
#         categories = get_categories(parent_id=None)
#         await message.answer(
#             "Управління бібліотекою знань. Оберіть категорію:",
#             reply_markup=get_categories_kb(categories, include_back=True, admin_mode=True)
#         )
#     else:
#         # Ошибка при добавлении категории
#         await message.answer(
#             f"Помилка: категорія з назвою '{category_name}' вже існує або виникла інша помилка."
#         )
    
#     # Сбрасываем состояние
#     await state.clear()

# @router.callback_query(F.data.startswith("admin_category_"))
# async def admin_category_selected(callback: CallbackQuery, state: FSMContext):
#     """Обработчик выбора категории администратором"""
#     # Извлекаем ID категории из callback_data
#     category_id = int(callback.data.split("_")[2])
    
#     # Получаем информацию о категории
#     category = get_category_info(category_id)
    
#     if not category:
#         await callback.message.edit_text(
#             "Категорія не знайдена. Поверніться до головного меню.",
#             reply_markup=get_categories_kb([], include_back=True, admin_mode=True)
#         )
#         await callback.answer()
#         return
    
#     # Проверяем уровень категории
#     if category["level"] < 3:
#         # Если это категория 1 или 2 уровня, показываем опции управления категорией
#         subcategories = get_categories(parent_id=category_id)
        
#         # Сохраняем ID и уровень категории в состоянии для дальнейшего использования
#         await state.update_data(category_id=category_id, level=category["level"])
        
#         if not subcategories:
#             await callback.message.edit_text(
#                 f"Категорія \"{category['name']}\" (рівень {category['level']}). Немає підкатегорій.\n\n"
#                 f"Виберіть дію:",
#                 reply_markup=get_category_actions_kb(category_id, category["parent_id"])
#             )
#         else:
#             # Показываем список подкатегорий и действия с текущей категорией
#             await callback.message.edit_text(
#                 f"Категорія \"{category['name']}\" (рівень {category['level']}). Підкатегорії:\n\n"
#                 f"Виберіть підкатегорію або дію з поточною категорією:",
#                 reply_markup=get_category_actions_kb(category_id, category["parent_id"])
#             )
            
#             # Показываем список подкатегорий в отдельном сообщении
#             await callback.message.answer(
#                 "Підкатегорії:",
#                 reply_markup=get_categories_kb(subcategories, include_back=False, admin_mode=True)
#             )
#     else:
#         # Если это категория 3 уровня (группа товаров), показываем опции и статьи
#         articles = get_articles_in_category(category_id)
        
#         # Сохраняем ID категории в состоянии для дальнейшего использования
#         await state.update_data(category_id=category_id)
        
#         await callback.message.edit_text(
#             f"Група товарів \"{category['name']}\".\n\n"
#             f"Виберіть дію:",
#             reply_markup=get_category_actions_kb(category_id, category["parent_id"])
#         )
        
#         # Если есть статьи, показываем их в отдельном сообщении
#         if articles:
#             await callback.message.answer(
#                 "Статті в цій групі товарів:",
#                 reply_markup=get_articles_kb(articles, category_id, admin_mode=True)
#             )
    
#     await callback.answer()

# @router.callback_query(F.data.startswith("add_subcategory_"))
# async def add_subcategory_command(callback: CallbackQuery, state: FSMContext):
#     """Обработчик добавления подкатегории"""
#     # Извлекаем ID родительской категории из callback_data
#     parent_id = int(callback.data.split("_")[1])
    
#     # Получаем информацию о родительской категории
#     parent_category = get_category_info(parent_id)
    
#     if not parent_category:
#         await callback.message.edit_text(
#             "Батьківська категорія не знайдена. Поверніться до головного меню.",
#             reply_markup=get_categories_kb([], include_back=True, admin_mode=True)
#         )
#         await callback.answer()
#         return
    
#     # Проверяем уровень родительской категории (можно добавлять подкатегорию только к уровням 1 и 2)
#     if parent_category["level"] >= 3:
#         await callback.message.edit_text(
#             "Неможливо додати підкатегорію до групи товарів (рівень 3).",
#             reply_markup=get_category_actions_kb(parent_id, parent_category["parent_id"])
#         )
#         await callback.answer()
#         return
    
#     # Сохраняем ID родительской категории и её уровень в состоянии
#     await state.update_data(parent_id=parent_id, parent_level=parent_category["level"])
    
#     await callback.message.edit_text(
#         f"Введіть назву нової підкатегорії для \"{parent_category['name']}\" (рівень {parent_category['level'] + 1}):"
#     )
#     await state.set_state(LibraryAdminStates.waiting_for_subcategory_name)
#     await callback.answer()

# @router.message(LibraryAdminStates.waiting_for_subcategory_name)
# async def process_subcategory_name(message: Message, state: FSMContext):
#     """Обработчик ввода названия новой подкатегории"""
#     subcategory_name = message.text.strip()
    
#     if len(subcategory_name) < 3:
#         await message.answer(
#             "Назва підкатегорії повинна містити не менше 3 символів. Спробуйте ще раз:"
#         )
#         return
    
#     # Получаем данные из состояния
#     data = await state.get_data()
#     parent_id = data.get("parent_id")
#     parent_level = data.get("parent_level")
    
#     if not parent_id or parent_level is None:
#         await message.answer(
#             "Помилка: відсутні дані про батьківську категорію. Почніть спочатку."
#         )
#         await state.clear()
#         return
    
#     # Добавляем новую подкатегорию
#     subcategory_id = add_category(subcategory_name, parent_id=parent_id, level=parent_level + 1)
    
#     if subcategory_id:
#         # Подкатегория успешно добавлена
#         await message.answer(
#             f"Підкатегорія '{subcategory_name}' успішно додана!"
#         )
        
#         # Показываем обновленное меню категорий
#         parent_category = get_category_info(parent_id)
#         subcategories = get_categories(parent_id=parent_id)
        
#         await message.answer(
#             f"Категорія \"{parent_category['name']}\" (рівень {parent_category['level']}). Підкатегорії:",
#             reply_markup=get_categories_kb(subcategories, include_back=True, admin_mode=True)
#         )
#     else:
#         # Ошибка при добавлении подкатегории
#         await message.answer(
#             f"Помилка: підкатегорія з назвою '{subcategory_name}' вже існує або виникла інша помилка."
#         )
    
#     # Сбрасываем состояние
#     await state.clear()

# @router.callback_query(F.data.startswith("edit_category_"))
# async def edit_category_command(callback: CallbackQuery, state: FSMContext):
#     """Обработчик редактирования названия категории"""
#     # Извлекаем ID категории из callback_data
#     category_id = int(callback.data.split("_")[2])
    
#     # Получаем информацию о категории
#     category = get_category_info(category_id)
    
#     if not category:
#         await callback.message.edit_text(
#             "Категорія не знайдена. Поверніться до головного меню.",
#             reply_markup=get_categories_kb([], include_back=True, admin_mode=True)
#         )
#         await callback.answer()
#         return
    
#     # Сохраняем ID категории в состоянии
#     await state.update_data(category_id=category_id)
    
#     await callback.message.edit_text(
#         f"Поточна назва: \"{category['name']}\"\n\n"
#         f"Введіть нову назву для категорії:"
#     )
#     await state.set_state(LibraryAdminStates.waiting_for_edit_category_name)
#     await callback.answer()

# @router.message(LibraryAdminStates.waiting_for_edit_category_name)
# async def process_edit_category_name(message: Message, state: FSMContext):
#     """Обработчик ввода нового названия категории"""
#     new_name = message.text.strip()
    
#     if len(new_name) < 3:
#         await message.answer(
#             "Назва категорії повинна містити не менше 3 символів. Спробуйте ще раз:"
#         )
#         return
    
#     # Получаем ID категории из состояния
#     data = await state.get_data()
#     category_id = data.get("category_id")
    
#     if not category_id:
#         await message.answer(
#             "Помилка: відсутні дані про категорію. Почніть спочатку."
#         )
#         await state.clear()
#         return
    
#     # Обновляем название категории
#     success = update_category(category_id, new_name)
    
#     if success:
#         # Название успешно обновлено
#         await message.answer(
#             f"Назва категорії змінена на '{new_name}'!"
#         )
        
#         # Получаем обновленную информацию о категории
#         category = get_category_info(category_id)
        
#         # Проверяем, есть ли у категории родитель
#         if category["parent_id"]:
#             # Если есть родитель, возвращаемся к списку подкатегорий родителя
#             parent_category = get_category_info(category["parent_id"])
#             subcategories = get_categories(parent_id=category["parent_id"])
            
#             await message.answer(
#                 f"Категорія \"{parent_category['name']}\". Підкатегорії:",
#                 reply_markup=get_categories_kb(subcategories, include_back=True, admin_mode=True)
#             )
#         else:
#             # Если это корневая категория, возвращаемся к списку корневых категорий
#             categories = get_categories(parent_id=None)
            
#             await message.answer(
#                 "Управління бібліотекою знань. Оберіть категорію:",
#                 reply_markup=get_categories_kb(categories, include_back=True, admin_mode=True)
#             )
#     else:
#         # Ошибка при обновлении названия
#         await message.answer(
#             f"Помилка: не вдалося змінити назву категорії. Можливо, категорія з назвою '{new_name}' вже існує."
#         )
    
#     # Сбрасываем состояние
#     await state.clear()

# @router.callback_query(F.data.startswith("delete_category_"))
# async def delete_category_command(callback: CallbackQuery):
#     """Обработчик удаления категории"""
#     # Извлекаем ID категории из callback_data
#     category_id = int(callback.data.split("_")[2])
    
#     # Получаем информацию о категории
#     category = get_category_info(category_id)
    
#     if not category:
#         await callback.message.edit_text(
#             "Категорія не знайдена. Поверніться до головного меню.",
#             reply_markup=get_categories_kb([], include_back=True, admin_mode=True)
#         )
#         await callback.answer()
#         return
    
#     # Определяем callback для возврата
#     if category["parent_id"]:
#         return_callback = f"admin_category_{category['parent_id']}"
#     else:
#         return_callback = "admin_library"
    
#     # Показываем подтверждение удаления
#     await callback.message.edit_text(
#         f"Ви впевнені, що хочете видалити категорію \"{category['name']}\"?\n\n"
#         f"Увага! Будуть видалені всі підкатегорії, статті та тести в цій категорії!",
#         reply_markup=get_confirm_delete_kb("category", category_id, return_callback)
#     )
#     await callback.answer()

# @router.callback_query(F.data.startswith("confirm_delete_category_"))
# async def confirm_delete_category(callback: CallbackQuery):
#     """Обработчик подтверждения удаления категории"""
#     # Извлекаем ID категории из callback_data
#     category_id = int(callback.data.split("_")[3])
    
#     # Получаем информацию о категории перед удалением
#     category = get_category_info(category_id)
    
#     if not category:
#         await callback.message.edit_text(
#             "Категорія не знайдена. Поверніться до головного меню.",
#             reply_markup=get_categories_kb([], include_back=True, admin_mode=True)
#         )
#         await callback.answer()
#         return
    
#     # Сохраняем parent_id перед удалением
#     parent_id = category["parent_id"]
    
#     # Удаляем категорию и все связанные данные
#     success = delete_category(category_id)
    
#     if success:
#         # Категория успешно удалена
#         if parent_id:
#             # Если это подкатегория, возвращаемся к родительской категории
#             parent_category = get_category_info(parent_id)
#             subcategories = get_categories(parent_id=parent_id)
            
#             if parent_category:
#                 await callback.message.edit_text(
#                     f"Категорія \"{category['name']}\" успішно видалена!\n\n"
#                     f"Категорія \"{parent_category['name']}\". Підкатегорії:",
#                     reply_markup=get_categories_kb(subcategories, include_back=True, admin_mode=True)
#                 )
#             else:
#                 # Если родительская категория не найдена, возвращаемся к корневым категориям
#                 categories = get_categories(parent_id=None)
                
#                 await callback.message.edit_text(
#                     f"Категорія \"{category['name']}\" успішно видалена!\n\n"
#                     f"Управління бібліотекою знань. Оберіть категорію:",
#                     reply_markup=get_categories_kb(categories, include_back=True, admin_mode=True)
#                 )
#         else:
#             # Если это корневая категория, возвращаемся к списку корневых категорий
#             categories = get_categories(parent_id=None)
            
#             await callback.message.edit_text(
#                 f"Категорія \"{category['name']}\" успішно видалена!\n\n"
#                 f"Управління бібліотекою знань. Оберіть категорію:",
#                 reply_markup=get_categories_kb(categories, include_back=True, admin_mode=True)
#             )
#     else:
#         # Ошибка при удалении категории
#         await callback.message.edit_text(
#             f"Помилка: не вдалося видалити категорію \"{category['name']}\".",
#             reply_markup=get_category_actions_kb(category_id, parent_id)
#         )
    
#     await callback.answer()

# @router.callback_query(F.data.startswith("list_articles_"))
# async def list_articles_command(callback: CallbackQuery):
#     """Обработчик просмотра списка статей в категории"""
#     # Извлекаем ID категории из callback_data
#     category_id = int(callback.data.split("_")[2])
    
#     # Получаем информацию о категории
#     category = get_category_info(category_id)
    
#     if not category:
#         await callback.message.edit_text(
#             "Категорія не знайдена. Поверніться до головного меню.",
#             reply_markup=get_categories_kb([], include_back=True, admin_mode=True)
#         )
#         await callback.answer()
#         return
    
#     # Получаем статьи в категории
#     articles = get_articles_in_category(category_id)
    
#     if not articles:
#         await callback.message.edit_text(
#             f"У категорії \"{category['name']}\" немає статей.",
#             reply_markup=get_category_actions_kb(category_id, category["parent_id"])
#         )
#         await callback.answer()
#         return
    
#     await callback.message.edit_text(
#         f"Статті в категорії \"{category['name']}\":",
#         reply_markup=get_articles_kb(articles, category_id, admin_mode=True)
#     )
#     await callback.answer()

# @router.callback_query(F.data.startswith("add_article_"))
# async def add_article_command(callback: CallbackQuery, state: FSMContext):
#     """Обработчик добавления новой статьи"""
#     # Извлекаем ID категории из callback_data
#     category_id = int(callback.data.split("_")[2])
    
#     # Получаем информацию о категории
#     category = get_category_info(category_id)
    
#     if not category:
#         await callback.message.edit_text(
#             "Категорія не знайдена. Поверніться до головного меню.",
#             reply_markup=get_categories_kb([], include_back=True, admin_mode=True)
#         )
#         await callback.answer()
#         return
    
#     # Сохраняем ID категории в состоянии
#     await state.update_data(category_id=category_id)
    
#     await callback.message.edit_text(
#         f"Створення нової статті в категорії \"{category['name']}\".\n\n"
#         f"Введіть заголовок статті (максимум 200 символів):"
#     )
#     await state.set_state(LibraryAdminStates.waiting_for_article_title)
#     await callback.answer()

# @router.message(LibraryAdminStates.waiting_for_article_title)
# async def process_article_title(message: Message, state: FSMContext):
#     """Обработчик ввода заголовка статьи"""
#     title = message.text.strip()
    
#     if len(title) < 3:
#         await message.answer(
#             "Заголовок статті повинен містити не менше 3 символів. Спробуйте ще раз:"
#         )
#         return
    
#     if len(title) > 200:
#         await message.answer(
#             "Заголовок статті не повинен перевищувати 200 символів. Поточна довжина: "
#             f"{len(title)} символів. Спробуйте ще раз:"
#         )
#         return
    
#     # Сохраняем заголовок в состоянии
#     await state.update_data(article_title=title)
    
#     await message.answer(
#         "Тепер введіть текст статті (максимум 4000 символів):\n\n"
#         "Ви можете використовувати Markdown для форматування:\n"
#         "**жирний текст** - виділення тексту жирним\n"
#         "*курсив* - виділення тексту курсивом\n"
#         "- список - створення списку\n"
#         "1. нумерований список - створення нумерованого списку"
#     )
#     await state.set_state(LibraryAdminStates.waiting_for_article_content)

# @router.message(LibraryAdminStates.waiting_for_article_content)
# async def process_article_content(message: Message, state: FSMContext):
#     """Обработчик ввода текста статьи"""
#     content = message.text.strip()
    
#     if len(content) < 10:
#         await message.answer(
#             "Текст статті повинен містити не менше 10 символів. Спробуйте ще раз:"
#         )
#         return
    
#     if len(content) > 4000:
#         await message.answer(
#             "Текст статті не повинен перевищувати 4000 символів. Поточна довжина: "
#             f"{len(content)} символів. Спробуйте ще раз:"
#         )
#         return
    
#     # Получаем данные из состояния
#     data = await state.get_data()
#     category_id = data.get("category_id")
#     title = data.get("article_title")
    
#     if not category_id or not title:
#         await message.answer(
#             "Помилка: відсутні дані про категорію або заголовок. Почніть спочатку."
#         )
#         await state.clear()
#         return
    
#     # Добавляем статью в базу данных
#     article_id = add_article(title, content, category_id, message.from_user.id)
    
#     if article_id:
#         # Статья успешно добавлена
#         await message.answer(
#             f"Стаття \"{title}\" успішно додана!\n\n"
#             f"Бажаєте додати зображення до статті? (максимум 5 зображень)\n"
#             f"Відправте зображення або натисніть 'Пропустити'.",
#             reply_markup=InlineKeyboardMarkup(inline_keyboard=[
#                 [InlineKeyboardButton(text="Пропустити", callback_data=f"skip_images_{article_id}")]
#             ])
#         )
        
#         # Сохраняем ID статьи и счетчик изображений в состоянии
#         await state.update_data(article_id=article_id, image_count=0)
#         await state.set_state(LibraryAdminStates.waiting_for_article_images)
#     else:
#         # Ошибка при добавлении статьи
#         await message.answer(
#             "Помилка: не вдалося додати статтю. Спробуйте ще раз або зверніться до адміністратора."
#         )
#         await state.clear()

# @router.message(LibraryAdminStates.waiting_for_article_images, F.photo)
# async def process_article_image(message: Message, state: FSMContext):
#     """Обработчик загрузки изображения для статьи"""
#     # Получаем данные из состояния
#     data = await state.get_data()
#     article_id = data.get("article_id")
#     image_count = data.get("image_count", 0)
    
#     if not article_id:
#         await message.answer(
#             "Помилка: відсутні дані про статтю. Почніть спочатку."
#         )
#         await state.clear()
#         return
    
#     # Проверяем, не превышено ли максимальное количество изображений
#     if image_count >= 5:
#         await message.answer(
#             "Ви вже додали максимальну кількість зображень (5)."
#         )
#         return
    
#     # Получаем информацию о фото
#     photo = message.photo[-1]  # Берем фото с наивысшим разрешением
#     file_id = photo.file_id
#     file_unique_id = photo.file_unique_id
    
#     # Добавляем изображение к статье
#     image_id = add_article_image(article_id, file_id, file_unique_id, image_count)




# Временный файл для устранения проблем с импортом
# Оригинальное содержимое закомментировано
"""
from database.operations_library import (...)
"""

# Пустой __init__.py
from bot.keyboards.admin_kb import get_admin_menu_kb
from bot.keyboards.user_kb import get_main_menu_kb
from bot.keyboards.library_kb import get_categories_kb, get_article_navigation_kb
# Импортируйте другие функции клавиатуры
    
    