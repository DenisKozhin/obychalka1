import sys
import os
from datetime import datetime

if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, and_, or_

from bot.database.models import User, Announcement, AnnouncementDelivery, City, Store
from bot.keyboards.user_kb import get_main_menu_kb
from bot.keyboards.admin_kb import get_admin_menu_kb
from bot.utils.logger import logger

# Создаем роутер для объявлений
router = Router()

# Определяем состояния для FSM
class AnnouncementStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_content = State()
    waiting_for_recipients = State()
    confirm_sending = State()


# Создаем клавиатуру для выбора получателей объявления
async def get_recipients_kb(session: AsyncSession):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    # Базовые типы получателей
    recipients_types = [
        ("all", "🌎 Всім користувачам"),
        ("by_city", "🏙 За містом"),
        ("by_store", "🏪 За магазином"),
        ("by_user", "👤 Конкретному користувачу")
    ]
    
    for type_id, type_name in recipients_types:
        builder.add(InlineKeyboardButton(
            text=type_name,
            callback_data=f"recipients_{type_id}"
        ))
    
    # Добавляем кнопку для отмены отправки
    builder.add(InlineKeyboardButton(
        text="❌ Скасувати",
        callback_data="cancel_announcement"
    ))
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()


# Создаем клавиатуру для выбора города
async def get_cities_kb_for_announcement(session: AsyncSession):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    # Получаем список городов из БД
    result = await session.execute(select(City))
    cities = result.scalars().all()
    
    # Добавляем кнопки для каждого города
    for city in cities:
        builder.add(InlineKeyboardButton(
            text=city.name,
            callback_data=f"city_announcement_{city.city_id}"
        ))
    
    # Добавляем кнопку для возврата к выбору получателей
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_recipients"
    ))
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()


# Создаем клавиатуру для выбора магазина
async def get_stores_kb_for_announcement(session: AsyncSession, city_id=None):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    # Получаем список магазинов из БД
    if city_id:
        result = await session.execute(
            select(Store).where(Store.city_id == city_id)
        )
    else:
        result = await session.execute(select(Store))
    
    stores = result.scalars().all()
    
    # Добавляем кнопки для каждого магазина
    for store in stores:
        builder.add(InlineKeyboardButton(
            text=store.name,
            callback_data=f"store_announcement_{store.store_id}"
        ))
    
    # Добавляем кнопку для возврата к выбору получателей или городов
    if city_id:
        builder.add(InlineKeyboardButton(
            text="🔙 Назад до вибору міста",
            callback_data="back_to_cities_announcement"
        ))
    else:
        builder.add(InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="back_to_recipients"
        ))
    
    # Настраиваем расположение кнопок (по одной кнопке в строку)
    builder.adjust(1)
    
    return builder.as_markup()


# Обработчик команды "Объявления" для пользователя
@router.message(F.text == "📢 Оголошення")
async def announcements_command(message: Message, session: AsyncSession):
    user_id = message.from_user.id
    
    # Получаем список объявлений, адресованных пользователю
    announcements_result = await session.execute(
        select(Announcement, AnnouncementDelivery)
        .join(
            AnnouncementDelivery,
            and_(
                Announcement.announcement_id == AnnouncementDelivery.announcement_id,
                AnnouncementDelivery.user_id == user_id
            )
        )
        .order_by(Announcement.created_at.desc())
    )
    
    announcements = announcements_result.all()
    
    if not announcements:
        await message.answer(
            "У вас немає оголошень.",
            reply_markup=get_main_menu_kb()
        )
        return
    
    # Отправляем список объявлений
    await message.answer("Ваші оголошення:")
    
    for announcement, delivery in announcements:
        # Отмечаем объявление как прочитанное, если еще не отмечено
        if not delivery.is_delivered:
            delivery.is_delivered = True
            delivery.delivered_at = datetime.now()
            await session.commit()
        
        # Формируем сообщение с объявлением
        announcement_text = f"<b>{announcement.title}</b>\n\n{announcement.content}"
        
        # Отправляем объявление
        await message.answer(
            announcement_text,
            parse_mode="HTML"
        )
    
    await message.answer(
        "Це всі ваші оголошення.",
        reply_markup=get_main_menu_kb()
    )


# Обработчик команды "Рассылка" для администратора
@router.message(F.text == "📢 Розсилка")
async def broadcast_command(message: Message, state: FSMContext, session: AsyncSession):
    user_id = message.from_user.id
    
    # Проверяем, является ли пользователь администратором
    user_result = await session.execute(
        select(User).where(User.user_id == user_id)
    )
    user = user_result.scalar_one_or_none()
    
    if not user or not user.is_admin:
        await message.answer(
            "У вас немає прав доступу до цієї команди.",
            reply_markup=get_main_menu_kb()
        )
        return
    
    # Запрашиваем заголовок объявления
    await message.answer(
        "Створення нового оголошення.\n\n"
        "Введіть заголовок оголошення:"
    )
    
    await state.set_state(AnnouncementStates.waiting_for_title)


# Обработчик ввода заголовка объявления
@router.message(AnnouncementStates.waiting_for_title)
async def process_announcement_title(message: Message, state: FSMContext):
    # Получаем введенный заголовок
    title = message.text.strip()
    
    # Проверяем длину заголовка
    if len(title) > 200:
        await message.answer(
            "Занадто довгий заголовок. Максимальна довжина - 200 символів. "
            "Будь ласка, введіть коротший заголовок:"
        )
        return
    
    # Сохраняем заголовок в данных состояния
    await state.update_data(title=title)
    
    # Запрашиваем текст объявления
    await message.answer(
        "Введіть текст оголошення:"
    )
    
    await state.set_state(AnnouncementStates.waiting_for_content)


# Обработчик ввода текста объявления
@router.message(AnnouncementStates.waiting_for_content)
async def process_announcement_content(message: Message, state: FSMContext, session: AsyncSession):
    # Получаем введенный текст
    content = message.text.strip()
    
    # Проверяем длину текста
    if len(content) > 4000:
        await message.answer(
            "Занадто довгий текст. Максимальна довжина - 4000 символів. "
            "Будь ласка, введіть коротший текст:"
        )
        return
    
    # Сохраняем текст в данных состояния
    await state.update_data(content=content)
    
    # Получаем данные состояния
    data = await state.get_data()
    
    # Показываем предварительный просмотр объявления
    await message.answer(
        "Попередній перегляд оголошення:\n\n"
        f"<b>{data['title']}</b>\n\n{content}",
        parse_mode="HTML"
    )
    
    # Запрашиваем выбор получателей
    await message.answer(
        "Оберіть отримувачів оголошення:",
        reply_markup=await get_recipients_kb(session)
    )
    
    await state.set_state(AnnouncementStates.waiting_for_recipients)


# Обработчик выбора получателей объявления
@router.callback_query(AnnouncementStates.waiting_for_recipients, F.data.startswith("recipients_"))
async def select_recipients(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    # Извлекаем тип получателей из callback_data
    recipients_type = callback.data.split("_")[1]
    
    # Сохраняем тип получателей в данных состояния
    await state.update_data(recipients_type=recipients_type)
    
    if recipients_type == "all":
        # Отправляем объявление всем пользователям
        await callback.message.edit_text(
            "Ви вибрали відправку оголошення всім користувачам.\n\n"
            "Підтвердіть відправку:"
        )
        
        # Показываем кнопки подтверждения
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        
        builder = InlineKeyboardBuilder()
        
        builder.add(InlineKeyboardButton(
            text="✅ Підтвердити",
            callback_data="confirm_announcement"
        ))
        
        builder.add(InlineKeyboardButton(
            text="❌ Скасувати",
            callback_data="cancel_announcement"
        ))
        
        builder.adjust(1)
        
        await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
        
        await state.set_state(AnnouncementStates.confirm_sending)
    
    elif recipients_type == "by_city":
        # Выбор города для отправки
        await callback.message.edit_text(
            "Оберіть місто для відправки оголошення:",
            reply_markup=await get_cities_kb_for_announcement(session)
        )
    
    elif recipients_type == "by_store":
        # Выбор магазина для отправки
        await callback.message.edit_text(
            "Оберіть магазин для відправки оголошення:",
            reply_markup=await get_stores_kb_for_announcement(session)
        )
    
    elif recipients_type == "by_user":
        # Ввод ID пользователя для отправки
        await callback.message.edit_text(
            "Введіть ID користувача Telegram (user_id) для відправки оголошення:"
        )
        
        # Удаляем клавиатуру для ввода текста
        await callback.message.edit_reply_markup(reply_markup=None)
        
        await state.update_data(waiting_for_user_id=True)
    
    await callback.answer()


# Обработчик для возврата к выбору получателей
@router.callback_query(F.data == "back_to_recipients")
async def back_to_recipients(callback: CallbackQuery, session: AsyncSession):
    await callback.message.edit_text(
        "Оберіть отримувачів оголошення:",
        reply_markup=await get_recipients_kb(session)
    )
    
    await callback.answer()


# Обработчик выбора города для отправки объявления
@router.callback_query(AnnouncementStates.waiting_for_recipients, F.data.startswith("city_announcement_"))
async def select_city_for_announcement(callback: CallbackQuery, state: FSMContext):
    # Извлекаем ID города из callback_data
    city_id = int(callback.data.split("_")[2])
    
    # Сохраняем ID города в данных состояния
    await state.update_data(city_id=city_id)
    
    # Показываем кнопки подтверждения
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="✅ Підтвердити",
        callback_data="confirm_announcement"
    ))
    
    builder.add(InlineKeyboardButton(
        text="❌ Скасувати",
        callback_data="cancel_announcement"
    ))
    
    builder.adjust(1)
    
    await callback.message.edit_text(
        "Ви вибрали відправку оголошення користувачам певного міста.\n\n"
        "Підтвердіть відправку:",
        reply_markup=builder.as_markup()
    )
    
    await state.set_state(AnnouncementStates.confirm_sending)
    
    await callback.answer()


# Обработчик для возврата к выбору городов
@router.callback_query(F.data == "back_to_cities_announcement")
async def back_to_cities_announcement(callback: CallbackQuery, session: AsyncSession):
    await callback.message.edit_text(
        "Оберіть місто для відправки оголошення:",
        reply_markup=await get_cities_kb_for_announcement(session)
    )
    
    await callback.answer()


# Обработчик выбора магазина для отправки объявления
@router.callback_query(AnnouncementStates.waiting_for_recipients, F.data.startswith("store_announcement_"))
async def select_store_for_announcement(callback: CallbackQuery, state: FSMContext):
    # Извлекаем ID магазина из callback_data
    store_id = int(callback.data.split("_")[2])
    
    # Сохраняем ID магазина в данных состояния
    await state.update_data(store_id=store_id)
    
    # Показываем кнопки подтверждения
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="✅ Підтвердити",
        callback_data="confirm_announcement"
    ))
    
    builder.add(InlineKeyboardButton(
        text="❌ Скасувати",
        callback_data="cancel_announcement"
    ))
    
    builder.adjust(1)
    
    await callback.message.edit_text(
        "Ви вибрали відправку оголошення користувачам певного магазину.\n\n"
        "Підтвердіть відправку:",
        reply_markup=builder.as_markup()
    )
    
    await state.set_state(AnnouncementStates.confirm_sending)
    
    await callback.answer()


# Обработчик ввода ID пользователя
@router.message(AnnouncementStates.waiting_for_recipients)
async def process_user_id(message: Message, state: FSMContext, session: AsyncSession):
    # Получаем данные состояния
    data = await state.get_data()
    
    # Проверяем, что ожидается ввод ID пользователя
    if not data.get("waiting_for_user_id"):
        return
    
    # Получаем введенный ID пользователя
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer(
            "Невірний формат ID. Будь ласка, введіть число:"
        )
        return
    
    # Проверяем, существует ли пользователь с таким ID
    user_result = await session.execute(
        select(User).where(User.user_id == user_id)
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        await message.answer(
            "Користувач з таким ID не знайдений. Будь ласка, введіть інший ID:"
        )
        return
    
    # Сохраняем ID пользователя в данных состояния
    await state.update_data(target_user_id=user_id, waiting_for_user_id=False)
    
    # Показываем кнопки подтверждения
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="✅ Підтвердити",
        callback_data="confirm_announcement"
    ))
    
    builder.add(InlineKeyboardButton(
        text="❌ Скасувати",
        callback_data="cancel_announcement"
    ))
    
    builder.adjust(1)
    
    await message.answer(
        f"Ви вибрали відправку оголошення користувачу {user.first_name} {user.last_name}.\n\n"
        "Підтвердіть відправку:",
        reply_markup=builder.as_markup()
    )
    
    await state.set_state(AnnouncementStates.confirm_sending)


# Обработчик подтверждения отправки объявления
@router.callback_query(AnnouncementStates.confirm_sending, F.data == "confirm_announcement")
async def confirm_send_announcement(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    # Получаем данные состояния
    data = await state.get_data()
    
    # Извлекаем данные объявления
    title = data.get("title")
    content = data.get("content")
    recipients_type = data.get("recipients_type")
    
    # Создаем новое объявление в БД
    new_announcement = Announcement(
        title=title,
        content=content,
        created_by=callback.from_user.id
    )
    
    session.add(new_announcement)
    await session.commit()
    await session.refresh(new_announcement)
    
    # Получаем целевых пользователей
    if recipients_type == "all":
        # Все пользователи
        users_result = await session.execute(select(User))
        users = users_result.scalars().all()
    
    elif recipients_type == "by_city":
        # Пользователи определенного города
        city_id = data.get("city_id")
        users_result = await session.execute(
            select(User).where(User.city_id == city_id)
        )
        users = users_result.scalars().all()
    
    elif recipients_type == "by_store":
        # Пользователи определенного магазина
        store_id = data.get("store_id")
        users_result = await session.execute(
            select(User).where(User.store_id == store_id)
        )
        users = users_result.scalars().all()
    
    elif recipients_type == "by_user":
        # Конкретный пользователь
        target_user_id = data.get("target_user_id")
        users_result = await session.execute(
            select(User).where(User.user_id == target_user_id)
        )
        users = users_result.scalars().all()
    
    else:
        users = []
    
    if not users:
        await callback.message.edit_text(
            "Не знайдено користувачів для відправки оголошення.",
            reply_markup=get_admin_menu_kb()
        )
        await state.clear()
        await callback.answer()
        return
    
    # Записываем для каждого пользователя запись о доставке объявления
    delivery_count = 0
    
    for user in users:
        # Создаем запись о доставке
        delivery = AnnouncementDelivery(
            announcement_id=new_announcement.announcement_id,
            user_id=user.user_id,
            is_delivered=False
        )
        session.add(delivery)
        
        try:
            # Отправляем объявление пользователю
            announcement_text = f"<b>{title}</b>\n\n{content}"
            
            await bot.send_message(
                chat_id=user.user_id,
                text=announcement_text,
                parse_mode="HTML"
            )
            
            # Отмечаем как доставленное
            delivery.is_delivered = True
            delivery.delivered_at = datetime.now()
            
            delivery_count += 1
            
            # Каждые 30 пользователей делаем коммит и небольшую паузу
            if delivery_count % 30 == 0:
                await session.commit()
                import asyncio
                await asyncio.sleep(0.5)  # Пауза 0.5 секунды
                
                # Обновляем сообщение с прогрессом
                await callback.message.edit_text(
                    f"Відправлення оголошення... Відправлено: {delivery_count}/{len(users)}"
                )
                
        except Exception as e:
            # Если произошла ошибка при отправке, логируем и продолжаем
            logger.error(f"Ошибка при отправке объявления пользователю {user.user_id}: {e}")
    
    # Сохраняем все изменения
    await session.commit()
    
    # Логируем действие администратора
    from bot.database.models import AdminLog
    admin_log = AdminLog(
        admin_id=callback.from_user.id,
        action_type="SEND",
        entity_type="ANNOUNCEMENT",
        entity_id=new_announcement.announcement_id,
        details={
            "recipients_type": recipients_type,
            "users_count": len(users),
            "delivered_count": delivery_count
        }
    )
    session.add(admin_log)
    await session.commit()
    
    # Отправляем сообщение об успешной отправке
    await callback.message.edit_text(
        f"Оголошення успішно відправлено {delivery_count} користувачам.",
        reply_markup=get_admin_menu_kb()
    )
    
    await state.clear()
    await callback.answer()


# Обработчик отмены отправки объявления
@router.callback_query(F.data == "cancel_announcement")
async def cancel_announcement(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Відправку оголошення скасовано.",
    )
    
    await callback.message.answer(
        "Виберіть опцію з меню адміністратора:",
        reply_markup=get_admin_menu_kb()
    )
    
    await state.clear()
    await callback.answer()


# Обработчик для возврата в главное меню
@router.callback_query(F.data == "back_to_main_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user_id = callback.from_user.id
    
    # Проверяем, является ли пользователь администратором
    result = await session.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if user and user.is_admin:
        await callback.message.edit_text(
            "Ви повернулись до головного меню.",
        )
        await callback.message.answer(
            "Виберіть опцію з адміністративного меню:",
            reply_markup=get_admin_menu_kb()
        )
    else:
        await callback.message.edit_text(
            "Ви повернулись до головного меню.",
        )
        await callback.message.answer(
            "Виберіть опцію з меню:",
            reply_markup=get_main_menu_kb()
        )
    
    await state.clear()
    await callback.answer()


# Экспорт роутера
if __name__ == "__main__":
    print("Модуль announcements.py успешно загружен")
    print("router определен:", router is not None)