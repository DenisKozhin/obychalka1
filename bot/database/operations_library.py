from datetime import datetime
from sqlalchemy import select, insert, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import Category, Article, ArticleImage, Test, User
from bot.utils.logger import logger
from sqlalchemy import select, insert, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from bot.database.models import Test, Question, Answer, Article, AdminLog, User
from datetime import datetime

# ====================== ФУНКЦИИ ДЛЯ РАБОТЫ С КАТЕГОРИЯМИ ======================

async def get_categories(session: AsyncSession, parent_id=None, level=1):
    """
    Получение списка категорий
    
    Args:
        session: Сессия SQLAlchemy
        parent_id: ID родительской категории (None для корневых категорий)
        level: Уровень категорий (1: тип товара, 2: категория, 3: группа товаров)
    
    Returns:
        List[Category]: Список объектов категорий
    """
    try:
        if parent_id is None:
            result = await session.execute(
                select(Category).where(Category.level == level)
            )
        else:
            result = await session.execute(
                select(Category).where(
                    Category.parent_id == parent_id,
                    Category.level == level
                )
            )
        
        categories = result.scalars().all()
        return categories
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        return []

async def get_category_by_id(session: AsyncSession, category_id: int):
    """
    Получение категории по ID
    
    Args:
        session: Сессия SQLAlchemy
        category_id: ID категории
    
    Returns:
        Category: Объект категории или None
    """
    try:
        result = await session.execute(
            select(Category).where(Category.category_id == category_id)
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Error getting category by ID: {e}")
        return None

async def create_category(session: AsyncSession, name: str, parent_id=None, level=1):
    """
    Создание новой категории
    
    Args:
        session: Сессия SQLAlchemy
        name: Название категории
        parent_id: ID родительской категории (None для корневых категорий)
        level: Уровень категории (1: тип товара, 2: категория, 3: группа товаров)
    
    Returns:
        Category: Созданная категория или None в случае ошибки
    """
    try:
        # Проверяем, существует ли уже такая категория
        existing = await session.execute(
            select(Category).where(
                Category.name == name,
                Category.parent_id == parent_id,
                Category.level == level
            )
        )
        if existing.scalar_one_or_none():
            logger.warning(f"Category with name '{name}' already exists")
            return None
        
        # Создаем новую категорию
        new_category = Category(
            name=name,
            parent_id=parent_id,
            level=level
        )
        session.add(new_category)
        await session.commit()
        await session.refresh(new_category)
        return new_category
    except Exception as e:
        await session.rollback()
        logger.error(f"Error creating category: {e}")
        return None

async def create_default_categories(session: AsyncSession):
    """
    Создание стандартных категорий, если их нет
    
    Args:
        session: Сессия SQLAlchemy
    
    Returns:
        List[Category]: Список созданных категорий
    """
    try:
        # Проверяем, есть ли уже категории
        result = await session.execute(select(Category))
        existing_categories = result.scalars().all()
        
        if existing_categories:
            return existing_categories
        
        # Создаем корневые категории
        food = await create_category(session, "Продовольчі товари", None, 1)
        non_food = await create_category(session, "Непродовольчі товари", None, 1)
        
        # Создаем подкатегории для продовольственных товаров
        if food:
            bakery = await create_category(session, "Хлібобулочні вироби", food.category_id, 2)
            dairy = await create_category(session, "Молочні продукти", food.category_id, 2)
            meat = await create_category(session, "М'ясні вироби", food.category_id, 2)
            
            # Добавляем группы товаров
            if bakery:
                await create_category(session, "Хліб", bakery.category_id, 3)
                await create_category(session, "Булочки", bakery.category_id, 3)
            
            if dairy:
                await create_category(session, "Молоко", dairy.category_id, 3)
                await create_category(session, "Сир", dairy.category_id, 3)
            
            if meat:
                await create_category(session, "Ковбаси", meat.category_id, 3)
                await create_category(session, "Свіже м'ясо", meat.category_id, 3)
        
        # Создаем подкатегории для непродовольственных товаров
        if non_food:
            household = await create_category(session, "Побутові товари", non_food.category_id, 2)
            electronics = await create_category(session, "Електроніка", non_food.category_id, 2)
            
            # Добавляем группы товаров
            if household:
                await create_category(session, "Миючі засоби", household.category_id, 3)
                await create_category(session, "Посуд", household.category_id, 3)
            
            if electronics:
                await create_category(session, "Батарейки", electronics.category_id, 3)
                await create_category(session, "Зарядні пристрої", electronics.category_id, 3)
        
        # Возвращаем созданные корневые категории
        result = await session.execute(select(Category).where(Category.level == 1))
        return result.scalars().all()
    except Exception as e:
        await session.rollback()
        logger.error(f"Error creating default categories: {e}")
        return []

async def update_category(session: AsyncSession, category_id: int, name: str):
    """
    Обновление названия категории
    
    Args:
        session: Сессия SQLAlchemy
        category_id: ID категории
        name: Новое название категории
    
    Returns:
        bool: True если обновление успешно, иначе False
    """
    try:
        # Проверяем, что категория существует
        category = await get_category_by_id(session, category_id)
        if not category:
            logger.warning(f"Category with ID {category_id} not found")
            return False
        
        # Обновляем название
        category.name = name
        await session.commit()
        return True
    except Exception as e:
        await session.rollback()
        logger.error(f"Error updating category: {e}")
        return False

async def delete_category(session: AsyncSession, category_id: int):
    """
    Удаление категории и всех её подкатегорий
    
    Args:
        session: Сессия SQLAlchemy
        category_id: ID категории
    
    Returns:
        bool: True если удаление успешно, иначе False
    """
    try:
        # Получаем категорию
        category = await get_category_by_id(session, category_id)
        if not category:
            logger.warning(f"Category with ID {category_id} not found")
            return False
        
        # Рекурсивно удаляем все подкатегории
        if category.level < 3:  # Если это не группа товаров
            subcategories = await get_categories(session, category_id, category.level + 1)
            for subcategory in subcategories:
                await delete_category(session, subcategory.category_id)
        
        # Удаляем статьи в этой категории
        articles = await get_articles_by_category(session, category_id)
        for article in articles:
            await delete_article(session, article.article_id)
        
        # Удаляем саму категорию
        await session.delete(category)
        await session.commit()
        return True
    except Exception as e:
        await session.rollback()
        logger.error(f"Error deleting category: {e}")
        return False

# ====================== ФУНКЦИИ ДЛЯ РАБОТЫ СО СТАТЬЯМИ ======================

async def get_articles_by_category(session: AsyncSession, category_id: int):
    """
    Получение списка статей в категории
    
    Args:
        session: Сессия SQLAlchemy
        category_id: ID категории
    
    Returns:
        List[Article]: Список статей
    """
    try:
        result = await session.execute(
            select(Article).where(Article.category_id == category_id)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Error getting articles by category: {e}")
        return []

async def get_article_by_id(session: AsyncSession, article_id: int):
    """
    Получение статьи по ID
    
    Args:
        session: Сессия SQLAlchemy
        article_id: ID статьи
    
    Returns:
        Article: Объект статьи или None
    """
    try:
        result = await session.execute(
            select(Article).where(Article.article_id == article_id)
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Error getting article by ID: {e}")
        return None

async def get_article_with_details(session: AsyncSession, article_id: int):
    """
    Получение статьи со всеми деталями (изображения, тесты, категория, автор)
    
    Args:
        session: Сессия SQLAlchemy
        article_id: ID статьи
    
    Returns:
        dict: Словарь с данными статьи или None
    """
    try:
        # Получаем статью
        article_result = await session.execute(
            select(Article).where(Article.article_id == article_id)
        )
        article = article_result.scalar_one_or_none()
        
        if not article:
            return None
        
        # Получаем категорию
        category_result = await session.execute(
            select(Category).where(Category.category_id == article.category_id)
        )
        category = category_result.scalar_one_or_none()
        
        # Получаем автора
        author_result = await session.execute(
            select(User).where(User.user_id == article.created_by)
        )
        author = author_result.scalar_one_or_none()
        
        # Получаем изображения
        images_result = await session.execute(
            select(ArticleImage)
            .where(ArticleImage.article_id == article_id)
            .order_by(ArticleImage.position)
        )
        images = images_result.scalars().all()
        
        # Получаем тесты
        tests_result = await session.execute(
            select(Test).where(Test.article_id == article_id)
        )
        tests = tests_result.scalars().all()
        
        # Форматируем результат
        result = {
            "article_id": article.article_id,
            "title": article.title,
            "content": article.content,
            "category_id": article.category_id,
            "category_name": category.name if category else "Без категорії",
            "created_at": article.created_at.strftime("%d.%m.%Y %H:%M") if article.created_at else "",
            "updated_at": article.updated_at.strftime("%d.%m.%Y %H:%M") if article.updated_at else "",
            "author": f"{author.first_name} {author.last_name}" if author else "Невідомий",
            "images": [
                {
                    "image_id": img.image_id,
                    "file_id": img.file_id,
                    "file_unique_id": img.file_unique_id,
                    "position": img.position
                }
                for img in images
            ],
            "tests": [
                {
                    "test_id": test.test_id,
                    "title": test.title,
                    "pass_threshold": test.pass_threshold
                }
                for test in tests
            ]
        }
        
        return result
    except Exception as e:
        logger.error(f"Error getting article with details: {e}")
        return None

async def create_article(session: AsyncSession, title: str, content: str, category_id: int, user_id: int):
    """
    Создание новой статьи
    
    Args:
        session: Сессия SQLAlchemy
        title: Заголовок статьи
        content: Содержание статьи
        category_id: ID категории
        user_id: ID пользователя (автора)
    
    Returns:
        Article: Созданная статья или None в случае ошибки
    """
    try:
        # Проверяем, что категория существует
        category = await get_category_by_id(session, category_id)
        if not category:
            logger.warning(f"Category with ID {category_id} not found")
            return None
        
        # Создаем новую статью
        new_article = Article(
            title=title,
            content=content,
            category_id=category_id,
            created_by=user_id,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        session.add(new_article)
        await session.commit()
        await session.refresh(new_article)
        return new_article
    except Exception as e:
        await session.rollback()
        logger.error(f"Error creating article: {e}")
        return None

async def update_article(session: AsyncSession, article_id: int, title=None, content=None, category_id=None):
    """
    Обновление статьи
    
    Args:
        session: Сессия SQLAlchemy
        article_id: ID статьи
        title: Новый заголовок статьи (None, если не нужно менять)
        content: Новое содержание статьи (None, если не нужно менять)
        category_id: Новый ID категории (None, если не нужно менять)
    
    Returns:
        bool: True если обновление успешно, иначе False
    """
    try:
        # Проверяем, что статья существует
        article = await get_article_by_id(session, article_id)
        if not article:
            logger.warning(f"Article with ID {article_id} not found")
            return False
        
        # Обновляем поля, если они предоставлены
        if title is not None:
            article.title = title
        
        if content is not None:
            article.content = content
        
        if category_id is not None:
            # Проверяем, что новая категория существует
            category = await get_category_by_id(session, category_id)
            if not category:
                logger.warning(f"Category with ID {category_id} not found")
                return False
            
            article.category_id = category_id
        
        # Обновляем время последнего изменения
        article.updated_at = datetime.now()
        
        await session.commit()
        return True
    except Exception as e:
        await session.rollback()
        logger.error(f"Error updating article: {e}")
        return False

async def delete_article(session: AsyncSession, article_id: int):
    """
    Удаление статьи и всех связанных данных
    
    Args:
        session: Сессия SQLAlchemy
        article_id: ID статьи
    
    Returns:
        bool: True если удаление успешно, иначе False
    """
    try:
        # Получаем статью
        article = await get_article_by_id(session, article_id)
        if not article:
            logger.warning(f"Article with ID {article_id} not found")
            return False
        
        # Удаляем статью (каскадное удаление сработает для изображений и тестов)
        await session.delete(article)
        await session.commit()
        return True
    except Exception as e:
        await session.rollback()
        logger.error(f"Error deleting article: {e}")
        return False

# ====================== ФУНКЦИИ ДЛЯ РАБОТЫ С ИЗОБРАЖЕНИЯМИ ======================

async def get_article_images(session: AsyncSession, article_id: int):
    """
    Получение изображений статьи
    
    Args:
        session: Сессия SQLAlchemy
        article_id: ID статьи
    
    Returns:
        List[ArticleImage]: Список изображений
    """
    try:
        result = await session.execute(
            select(ArticleImage)
            .where(ArticleImage.article_id == article_id)
            .order_by(ArticleImage.position)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Error getting article images: {e}")
        return []

async def add_article_image(session: AsyncSession, article_id: int, file_id: str, file_unique_id: str):
    """
    Добавление изображения к статье
    
    Args:
        session: Сессия SQLAlchemy
        article_id: ID статьи
        file_id: Telegram file_id
        file_unique_id: Telegram file_unique_id
    
    Returns:
        ArticleImage: Созданное изображение или None в случае ошибки
    """
    try:
        # Проверяем, что статья существует
        article = await get_article_by_id(session, article_id)
        if not article:
            logger.warning(f"Article with ID {article_id} not found")
            return None
        
        # Проверяем, сколько уже есть изображений (максимум 5)
        images = await get_article_images(session, article_id)
        if len(images) >= 5:
            logger.warning(f"Article with ID {article_id} already has 5 images")
            return None
        
        # Создаем новое изображение
        new_image = ArticleImage(
            article_id=article_id,
            file_id=file_id,
            file_unique_id=file_unique_id,
            position=len(images)  # Позиция нового изображения (0, 1, 2, 3, 4)
        )
        session.add(new_image)
        await session.commit()
        await session.refresh(new_image)
        return new_image
    except Exception as e:
        await session.rollback()
        logger.error(f"Error adding article image: {e}")
        return None

async def delete_article_image(session: AsyncSession, image_id: int):
    """
    Удаление изображения статьи
    
    Args:
        session: Сессия SQLAlchemy
        image_id: ID изображения
    
    Returns:
        bool: True если удаление успешно, иначе False
    """
    try:
        # Получаем изображение
        result = await session.execute(
            select(ArticleImage).where(ArticleImage.image_id == image_id)
        )
        image = result.scalar_one_or_none()
        
        if not image:
            logger.warning(f"Image with ID {image_id} not found")
            return False
        
        # Запоминаем article_id и position удаляемого изображения
        article_id = image.article_id
        deleted_position = image.position
        
        # Удаляем изображение
        await session.delete(image)
        
        # Обновляем позиции других изображений этой статьи
        images_result = await session.execute(
            select(ArticleImage)
            .where(
                ArticleImage.article_id == article_id,
                ArticleImage.position > deleted_position
            )
            .order_by(ArticleImage.position)
        )
        images_to_update = images_result.scalars().all()
        
        # Смещаем позиции
        for img in images_to_update:
            img.position -= 1
        
        await session.commit()
        return True
    except Exception as e:
        await session.rollback()
        logger.error(f"Error deleting article image: {e}")
        return False

# ====================== УТИЛИТЫ ======================

async def check_user_is_admin(session: AsyncSession, user_id: int):
    """
    Проверка, является ли пользователь администратором
    
    Args:
        session: Сессия SQLAlchemy
        user_id: ID пользователя
    
    Returns:
        bool: True если пользователь администратор, иначе False
    """
    try:
        # Получаем пользователя из базы данных
        result = await session.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        # Проверяем, является ли пользователь администратором
        return user is not None and user.is_admin
    except Exception as e:
        logger.error(f"Error checking if user is admin: {e}")
        return False

async def log_admin_action(session: AsyncSession, admin_id: int, action_type: str, entity_type: str, entity_id: int = None, details=None):
    """
    Запись действия администратора в лог
    
    Args:
        session: Сессия SQLAlchemy
        admin_id: ID администратора
        action_type: Тип действия (ADD, EDIT, DELETE, SEND)
        entity_type: Тип сущности (ARTICLE, TEST, CITY, STORE, CATEGORY)
        entity_id: ID сущности (опционально)
        details: Дополнительные детали (опционально)
    
    Returns:
        bool: True если запись успешна, иначе False
    """
    try:
        from bot.database.models import AdminLog
        
        # Создаем запись в логе
        log = AdminLog(
            admin_id=admin_id,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details
        )
        session.add(log)
        await session.commit()
        return True
    except Exception as e:
        await session.rollback()
        logger.error(f"Error logging admin action: {e}")
        return False

# 
#==================== Функции для работы с тестами


async def get_test_by_id(session: AsyncSession, test_id: int):
    """
    Получение теста по ID с вопросами и ответами
    """
    result = await session.execute(
        select(Test)
        .options(
            joinedload(Test.questions).joinedload(Question.answers)
        )
        .where(Test.test_id == test_id)
    )
    test = result.scalar_one_or_none()
    return test

async def get_tests_by_article(session: AsyncSession, article_id: int):
    """
    Получение всех тестов для статьи
    """
    result = await session.execute(
        select(Test)
        .where(Test.article_id == article_id)
    )
    tests = result.scalars().all()
    return tests

async def create_test(session: AsyncSession, title: str, article_id: int, pass_threshold: int, admin_id: int):
    """
    Создание нового теста
    """
    try:
        # Проверяем, существует ли статья
        article_result = await session.execute(select(Article).where(Article.article_id == article_id))
        article = article_result.scalar_one_or_none()
        
        if not article:
            return None
        
        # Создаем новый тест
        new_test = Test(
            title=title,
            article_id=article_id,
            pass_threshold=pass_threshold,
            created_by=admin_id
        )
        
        session.add(new_test)
        await session.commit()
        await session.refresh(new_test)
        
        # Логируем действие администратора
        admin_log = AdminLog(
            admin_id=admin_id,
            action_type="ADD",
            entity_type="TEST",
            entity_id=new_test.test_id,
            details={"title": title, "article_id": article_id}
        )
        session.add(admin_log)
        await session.commit()
        
        return new_test
    except Exception as e:
        await session.rollback()
        raise e

async def update_test(session: AsyncSession, test_id: int, title: str = None, pass_threshold: int = None, admin_id: int = None):
    """
    Обновление теста
    """
    try:
        result = await session.execute(select(Test).where(Test.test_id == test_id))
        test = result.scalar_one_or_none()
        
        if not test:
            return False
        
        # Обновляем только переданные поля
        if title is not None:
            test.title = title
        
        if pass_threshold is not None:
            test.pass_threshold = pass_threshold
        
        await session.commit()
        
        # Логируем действие администратора, если указан ID админа
        if admin_id:
            admin_log = AdminLog(
                admin_id=admin_id,
                action_type="EDIT",
                entity_type="TEST",
                entity_id=test_id,
                details={"title": title, "pass_threshold": pass_threshold}
            )
            session.add(admin_log)
            await session.commit()
        
        return True
    except Exception as e:
        await session.rollback()
        raise e

async def delete_test(session: AsyncSession, test_id: int, admin_id: int = None):
    """
    Удаление теста со всеми вопросами и ответами
    """
    try:
        # Получаем информацию о тесте перед удалением для лога
        test_result = await session.execute(select(Test).where(Test.test_id == test_id))
        test = test_result.scalar_one_or_none()
        
        if not test:
            return False
        
        # Сохраняем информацию о тесте для лога
        test_info = {
            "title": test.title,
            "article_id": test.article_id
        }
        
        # Удаление теста (каскадно удалит все вопросы и ответы благодаря настройкам в моделях)
        await session.execute(delete(Test).where(Test.test_id == test_id))
        await session.commit()
        
        # Логируем действие администратора, если указан ID админа
        if admin_id:
            admin_log = AdminLog(
                admin_id=admin_id,
                action_type="DELETE",
                entity_type="TEST",
                entity_id=test_id,
                details=test_info
            )
            session.add(admin_log)
            await session.commit()
        
        return True
    except Exception as e:
        await session.rollback()
        raise e

# Функции для работы с вопросами теста

async def get_questions_by_test(session: AsyncSession, test_id: int):
    """
    Получение всех вопросов теста с ответами
    """
    result = await session.execute(
        select(Question)
        .options(joinedload(Question.answers))
        .where(Question.test_id == test_id)
        .order_by(Question.question_id)
    )
    questions = result.scalars().all()
    return questions

async def create_question(session: AsyncSession, test_id: int, question_text: str, points: int = 1, admin_id: int = None):
    """
    Создание вопроса для теста
    """
    try:
        # Проверяем, существует ли тест
        test_result = await session.execute(select(Test).where(Test.test_id == test_id))
        test = test_result.scalar_one_or_none()
        
        if not test:
            return None
        
        # Создаем новый вопрос
        new_question = Question(
            test_id=test_id,
            question_text=question_text,
            points=points
        )
        
        session.add(new_question)
        await session.commit()
        await session.refresh(new_question)
        
        # Логируем действие администратора, если указан ID админа
        if admin_id:
            admin_log = AdminLog(
                admin_id=admin_id,
                action_type="ADD",
                entity_type="QUESTION",
                entity_id=new_question.question_id,
                details={"test_id": test_id, "question_text": question_text}
            )
            session.add(admin_log)
            await session.commit()
        
        return new_question
    except Exception as e:
        await session.rollback()
        raise e

async def update_question(session: AsyncSession, question_id: int, question_text: str = None, points: int = None, admin_id: int = None):
    """
    Обновление вопроса
    """
    try:
        result = await session.execute(select(Question).where(Question.question_id == question_id))
        question = result.scalar_one_or_none()
        
        if not question:
            return False
        
        # Обновляем только переданные поля
        if question_text is not None:
            question.question_text = question_text
        
        if points is not None:
            question.points = points
        
        await session.commit()
        
        # Логируем действие администратора, если указан ID админа
        if admin_id:
            admin_log = AdminLog(
                admin_id=admin_id,
                action_type="EDIT",
                entity_type="QUESTION",
                entity_id=question_id,
                details={"question_text": question_text, "points": points}
            )
            session.add(admin_log)
            await session.commit()
        
        return True
    except Exception as e:
        await session.rollback()
        raise e

async def delete_question(session: AsyncSession, question_id: int, admin_id: int = None):
    """
    Удаление вопроса со всеми ответами
    """
    try:
        # Получаем информацию о вопросе перед удалением для лога
        question_result = await session.execute(select(Question).where(Question.question_id == question_id))
        question = question_result.scalar_one_or_none()
        
        if not question:
            return False
        
        # Сохраняем информацию о вопросе для лога
        question_info = {
            "test_id": question.test_id,
            "question_text": question.question_text
        }
        
        # Удаление вопроса (каскадно удалит все ответы благодаря настройкам в моделях)
        await session.execute(delete(Question).where(Question.question_id == question_id))
        await session.commit()
        
        # Логируем действие администратора, если указан ID админа
        if admin_id:
            admin_log = AdminLog(
                admin_id=admin_id,
                action_type="DELETE",
                entity_type="QUESTION",
                entity_id=question_id,
                details=question_info
            )
            session.add(admin_log)
            await session.commit()
        
        return True
    except Exception as e:
        await session.rollback()
        raise e

# Функции для работы с ответами

async def create_answer(session: AsyncSession, question_id: int, answer_text: str, is_correct: bool, position: int, admin_id: int = None):
    """
    Создание ответа для вопроса
    """
    try:
        # Проверяем, существует ли вопрос
        question_result = await session.execute(select(Question).where(Question.question_id == question_id))
        question = question_result.scalar_one_or_none()
        
        if not question:
            return None
        
        # Создаем новый ответ
        new_answer = Answer(
            question_id=question_id,
            answer_text=answer_text,
            is_correct=is_correct,
            position=position
        )
        
        session.add(new_answer)
        await session.commit()
        await session.refresh(new_answer)
        
        # Логируем действие администратора, если указан ID админа
        if admin_id:
            admin_log = AdminLog(
                admin_id=admin_id,
                action_type="ADD",
                entity_type="ANSWER",
                entity_id=new_answer.answer_id,
                details={"question_id": question_id, "answer_text": answer_text, "is_correct": is_correct}
            )
            session.add(admin_log)
            await session.commit()
        
        return new_answer
    except Exception as e:
        await session.rollback()
        raise e

async def update_answer(session: AsyncSession, answer_id: int, answer_text: str = None, is_correct: bool = None, position: int = None, admin_id: int = None):
    """
    Обновление ответа
    """
    try:
        result = await session.execute(select(Answer).where(Answer.answer_id == answer_id))
        answer = result.scalar_one_or_none()
        
        if not answer:
            return False
        
        # Обновляем только переданные поля
        if answer_text is not None:
            answer.answer_text = answer_text
        
        if is_correct is not None:
            answer.is_correct = is_correct
        
        if position is not None:
            answer.position = position
        
        await session.commit()
        
        # Логируем действие администратора, если указан ID админа
        if admin_id:
            admin_log = AdminLog(
                admin_id=admin_id,
                action_type="EDIT",
                entity_type="ANSWER",
                entity_id=answer_id,
                details={"answer_text": answer_text, "is_correct": is_correct, "position": position}
            )
            session.add(admin_log)
            await session.commit()
        
        return True
    except Exception as e:
        await session.rollback()
        raise e

async def delete_answer(session: AsyncSession, answer_id: int, admin_id: int = None):
    """
    Удаление ответа
    """
    try:
        # Получаем информацию об ответе перед удалением для лога
        answer_result = await session.execute(select(Answer).where(Answer.answer_id == answer_id))
        answer = answer_result.scalar_one_or_none()
        
        if not answer:
            return False
        
        # Сохраняем информацию об ответе для лога
        answer_info = {
            "question_id": answer.question_id,
            "answer_text": answer.answer_text,
            "is_correct": answer.is_correct
        }
        
        # Удаление ответа
        await session.execute(delete(Answer).where(Answer.answer_id == answer_id))
        await session.commit()
        
        # Логируем действие администратора, если указан ID админа
        if admin_id:
            admin_log = AdminLog(
                admin_id=admin_id,
                action_type="DELETE",
                entity_type="ANSWER",
                entity_id=answer_id,
                details=answer_info
            )
            session.add(admin_log)
            await session.commit()
        
        return True
    except Exception as e:
        await session.rollback()
        raise e

# Вспомогательные функции для статистики и анализа

async def get_test_statistics(session: AsyncSession, test_id: int):
    """
    Получение статистики по тесту (количество попыток, средний балл, процент успешных прохождений)
    """
    from bot.database.models import TestAttempt
    
    # Получаем все попытки прохождения этого теста
    attempts_result = await session.execute(
        select(TestAttempt).where(TestAttempt.test_id == test_id)
    )
    attempts = attempts_result.scalars().all()
    
    if not attempts:
        return {
            "total_attempts": 0,
            "unique_users": 0,
            "avg_score": 0,
            "success_rate": 0,
            "last_attempt": None
        }
    
    # Подсчитываем статистику
    total_attempts = len(attempts)
    unique_users = len(set(a.user_id for a in attempts))
    avg_score = sum(a.score for a in attempts) / total_attempts
    success_rate = sum(1 for a in attempts if a.is_passed) / total_attempts * 100
    last_attempt = max(a.created_at for a in attempts)
    
    return {
        "total_attempts": total_attempts,
        "unique_users": unique_users,
        "avg_score": round(avg_score, 2),
        "success_rate": round(success_rate, 2),
        "last_attempt": last_attempt
    }

async def check_test_availability(session: AsyncSession, test_id: int, user_id: int):
    """
    Проверка, доступен ли тест пользователю 
    (например, если у него уже есть успешная попытка с максимальным баллом)
    """
    from bot.database.models import TestAttempt
    
    # Получаем тест для проверки максимального балла
    test_result = await session.execute(select(Test).where(Test.test_id == test_id))
    test = test_result.scalar_one_or_none()
    
    if not test:
        return False, "Тест не найден"
    
    # Проверяем, есть ли у пользователя успешные попытки с максимальным баллом
    attempts_result = await session.execute(
        select(TestAttempt)
        .where(
            TestAttempt.test_id == test_id,
            TestAttempt.user_id == user_id,
            TestAttempt.score == 10,  # Максимальный балл
            TestAttempt.is_passed == True
        )
    )
    perfect_attempt = attempts_result.scalar_one_or_none()
    
    if perfect_attempt:
        return False, "У вас уже есть успешная попытка с максимальным баллом"
    
    return True, "Тест доступен"

#функции для операций с базой данных по тестам, которые ссылаются в коде, но еще не определены:
# Добавляем в bot/database/operations_library.py

# Импорты
from sqlalchemy import select, update, delete, case, func
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import Test, Question, Answer, TestAttempt, UserAnswer, User, Article, AdminLog
from sqlalchemy.orm import joinedload
from typing import List, Dict, Any, Optional
from datetime import datetime

# Функции для работы с тестами

async def get_test_by_id(session: AsyncSession, test_id: int) -> Optional[Test]:
    """
    Получает тест по ID
    
    Args:
        session: Сессия базы данных
        test_id: ID теста
    
    Returns:
        Test или None
    """
    result = await session.execute(
        select(Test)
        .options(joinedload(Test.questions))
        .where(Test.test_id == test_id)
    )
    return result.scalar_one_or_none()

async def get_tests_by_article(session: AsyncSession, article_id: int) -> List[Test]:
    """
    Получает все тесты для указанной статьи
    
    Args:
        session: Сессия базы данных
        article_id: ID статьи
    
    Returns:
        Список тестов
    """
    result = await session.execute(
        select(Test).where(Test.article_id == article_id)
    )
    return result.scalars().all()

async def create_test(
    session: AsyncSession, 
    title: str, 
    article_id: int, 
    pass_threshold: int = 80,
    admin_id: int = None
) -> Optional[Test]:
    """
    Создает новый тест
    
    Args:
        session: Сессия базы данных
        title: Заголовок теста
        article_id: ID статьи
        pass_threshold: Порог прохождения (%)
        admin_id: ID администратора
    
    Returns:
        Созданный тест или None в случае ошибки
    """
    try:
        # Проверяем существование статьи
        article_result = await session.execute(select(Article).where(Article.article_id == article_id))
        article = article_result.scalar_one_or_none()
        
        if not article:
            return None
        
        # Создаем тест
        new_test = Test(
            title=title,
            article_id=article_id,
            pass_threshold=pass_threshold,
            created_by=admin_id,
            created_at=datetime.now()
        )
        
        session.add(new_test)
        await session.commit()
        await session.refresh(new_test)
        
        # Логируем действия администратора
        if admin_id:
            admin_log = AdminLog(
                admin_id=admin_id,
                action_type="ADD",
                entity_type="TEST",
                entity_id=new_test.test_id,
                details={"title": title, "article_id": article_id, "pass_threshold": pass_threshold}
            )
            session.add(admin_log)
            await session.commit()
        
        return new_test
    except Exception as e:
        await session.rollback()
        raise e

async def update_test(
    session: AsyncSession, 
    test_id: int, 
    title: str = None, 
    pass_threshold: int = None,
    admin_id: int = None
) -> bool:
    """
    Обновляет существующий тест
    
    Args:
        session: Сессия базы данных
        test_id: ID теста
        title: Новый заголовок (None если не требуется изменение)
        pass_threshold: Новый порог прохождения (None если не требуется изменение)
        admin_id: ID администратора
    
    Returns:
        True если обновление успешно, иначе False
    """
    try:
        # Получаем текущий тест
        result = await session.execute(select(Test).where(Test.test_id == test_id))
        test = result.scalar_one_or_none()
        
        if not test:
            return False
        
        # Обновляем поля, если они предоставлены
        changes = {}
        
        if title is not None:
            test.title = title
            changes["title"] = title
        
        if pass_threshold is not None:
            test.pass_threshold = pass_threshold
            changes["pass_threshold"] = pass_threshold
        
        # Сохраняем изменения
        await session.commit()
        
        # Логируем действия администратора
        if admin_id and changes:
            admin_log = AdminLog(
                admin_id=admin_id,
                action_type="EDIT",
                entity_type="TEST",
                entity_id=test_id,
                details=changes
            )
            session.add(admin_log)
            await session.commit()
        
        return True
    except Exception as e:
        await session.rollback()
        return False

async def delete_test(session: AsyncSession, test_id: int, admin_id: int = None) -> bool:
    """
    Удаляет тест и все связанные с ним вопросы и ответы
    
    Args:
        session: Сессия базы данных
        test_id: ID теста
        admin_id: ID администратора
    
    Returns:
        True если удаление успешно, иначе False
    """
    try:
        # Получаем информацию о тесте перед удалением (для лога)
        result = await session.execute(select(Test).where(Test.test_id == test_id))
        test = result.scalar_one_or_none()
        
        if not test:
            return False
        
        test_info = {
            "title": test.title,
            "article_id": test.article_id,
            "pass_threshold": test.pass_threshold
        }
        
        # Удаляем тест (каскадное удаление удалит вопросы и ответы)
        await session.execute(delete(Test).where(Test.test_id == test_id))
        await session.commit()
        
        # Логируем действия администратора
        if admin_id:
            admin_log = AdminLog(
                admin_id=admin_id,
                action_type="DELETE",
                entity_type="TEST",
                entity_id=test_id,
                details=test_info
            )
            session.add(admin_log)
            await session.commit()
        
        return True
    except Exception as e:
        await session.rollback()
        return False

# Функции для работы с вопросами

async def get_questions_by_test(session: AsyncSession, test_id: int) -> List[Question]:
    """
    Получает все вопросы для указанного теста
    
    Args:
        session: Сессия базы данных
        test_id: ID теста
    
    Returns:
        Список вопросов
    """
    result = await session.execute(
        select(Question)
        .where(Question.test_id == test_id)
        .order_by(Question.question_id)
    )
    return result.scalars().all()

async def create_question(
    session: AsyncSession, 
    test_id: int, 
    question_text: str, 
    points: int = 1,
    admin_id: int = None
) -> Optional[Question]:
    """
    Создает новый вопрос для теста
    
    Args:
        session: Сессия базы данных
        test_id: ID теста
        question_text: Текст вопроса
        points: Количество баллов за вопрос
        admin_id: ID администратора
    
    Returns:
        Созданный вопрос или None в случае ошибки
    """
    try:
        # Проверяем существование теста
        test_result = await session.execute(select(Test).where(Test.test_id == test_id))
        test = test_result.scalar_one_or_none()
        
        if not test:
            return None
        
        # Создаем вопрос
        new_question = Question(
            test_id=test_id,
            question_text=question_text,
            points=points
        )
        
        session.add(new_question)
        await session.commit()
        await session.refresh(new_question)
        
        # Логируем действия администратора
        if admin_id:
            admin_log = AdminLog(
                admin_id=admin_id,
                action_type="ADD",
                entity_type="QUESTION",
                entity_id=new_question.question_id,
                details={
                    "test_id": test_id,
                    "question_text": question_text,
                    "points": points
                }
            )
            session.add(admin_log)
            await session.commit()
        
        return new_question
    except Exception as e:
        await session.rollback()
        raise e

async def update_question(
    session: AsyncSession, 
    question_id: int, 
    question_text: str = None, 
    points: int = None,
    admin_id: int = None
) -> bool:
    """
    Обновляет существующий вопрос
    
    Args:
        session: Сессия базы данных
        question_id: ID вопроса
        question_text: Новый текст вопроса (None если не требуется изменение)
        points: Новое количество баллов (None если не требуется изменение)
        admin_id: ID администратора
    
    Returns:
        True если обновление успешно, иначе False
    """
    try:
        # Получаем текущий вопрос
        result = await session.execute(select(Question).where(Question.question_id == question_id))
        question = result.scalar_one_or_none()
        
        if not question:
            return False
        
        # Обновляем поля, если они предоставлены
        changes = {}
        
        if question_text is not None:
            question.question_text = question_text
            changes["question_text"] = question_text
        
        if points is not None:
            question.points = points
            changes["points"] = points
        
        # Сохраняем изменения
        await session.commit()
        
        # Логируем действия администратора
        if admin_id and changes:
            admin_log = AdminLog(
                admin_id=admin_id,
                action_type="EDIT",
                entity_type="QUESTION",
                entity_id=question_id,
                details=changes
            )
            session.add(admin_log)
            await session.commit()
        
        return True
    except Exception as e:
        await session.rollback()
        return False

async def delete_question(session: AsyncSession, question_id: int, admin_id: int = None) -> bool:
    """
    Удаляет вопрос и все связанные с ним ответы
    
    Args:
        session: Сессия базы данных
        question_id: ID вопроса
        admin_id: ID администратора
    
    Returns:
        True если удаление успешно, иначе False
    """
    try:
        # Получаем информацию о вопросе перед удалением (для лога)
        result = await session.execute(select(Question).where(Question.question_id == question_id))
        question = result.scalar_one_or_none()
        
        if not question:
            return False
        
        question_info = {
            "test_id": question.test_id,
            "question_text": question.question_text,
            "points": question.points
        }
        
        # Удаляем вопрос (каскадное удаление удалит ответы)
        await session.execute(delete(Question).where(Question.question_id == question_id))
        await session.commit()
        
        # Логируем действия администратора
        if admin_id:
            admin_log = AdminLog(
                admin_id=admin_id,
                action_type="DELETE",
                entity_type="QUESTION",
                entity_id=question_id,
                details=question_info
            )
            session.add(admin_log)
            await session.commit()
        
        return True
    except Exception as e:
        await session.rollback()
        return False

# Функции для работы с ответами

async def create_answer(
    session: AsyncSession, 
    question_id: int, 
    answer_text: str, 
    is_correct: bool = False,
    position: int = 1,
    admin_id: int = None
) -> Optional[Answer]:
    """
    Создает новый ответ для вопроса
    
    Args:
        session: Сессия базы данных
        question_id: ID вопроса
        answer_text: Текст ответа
        is_correct: Является ли ответ правильным
        position: Позиция ответа в списке
        admin_id: ID администратора
    
    Returns:
        Созданный ответ или None в случае ошибки
    """
    try:
        # Проверяем существование вопроса
        question_result = await session.execute(select(Question).where(Question.question_id == question_id))
        question = question_result.scalar_one_or_none()
        
        if not question:
            return None
        
        # Создаем ответ
        new_answer = Answer(
            question_id=question_id,
            answer_text=answer_text,
            is_correct=is_correct,
            position=position
        )
        
        session.add(new_answer)
        await session.commit()
        await session.refresh(new_answer)
        
        # Логируем действия администратора
        if admin_id:
            admin_log = AdminLog(
                admin_id=admin_id,
                action_type="ADD",
                entity_type="ANSWER",
                entity_id=new_answer.answer_id,
                details={
                    "question_id": question_id,
                    "answer_text": answer_text,
                    "is_correct": is_correct,
                    "position": position
                }
            )
            session.add(admin_log)
            await session.commit()
        
        return new_answer
    except Exception as e:
        await session.rollback()
        raise e

async def update_answer(
    session: AsyncSession, 
    answer_id: int, 
    answer_text: str = None, 
    is_correct: bool = None,
    position: int = None,
    admin_id: int = None
) -> bool:
    """
    Обновляет существующий ответ
    
    Args:
        session: Сессия базы данных
        answer_id: ID ответа
        answer_text: Новый текст ответа (None если не требуется изменение)
        is_correct: Новый статус правильности (None если не требуется изменение)
        position: Новая позиция (None если не требуется изменение)
        admin_id: ID администратора
    
    Returns:
        True если обновление успешно, иначе False
    """
    try:
        # Получаем текущий ответ
        result = await session.execute(select(Answer).where(Answer.answer_id == answer_id))
        answer = result.scalar_one_or_none()
        
        if not answer:
            return False
        
        # Обновляем поля, если они предоставлены
        changes = {}
        
        if answer_text is not None:
            answer.answer_text = answer_text
            changes["answer_text"] = answer_text
        
        if is_correct is not None:
            answer.is_correct = is_correct
            changes["is_correct"] = is_correct
        
        if position is not None:
            answer.position = position
            changes["position"] = position
        
        # Сохраняем изменения
        await session.commit()
        
        # Логируем действия администратора
        if admin_id and changes:
            admin_log = AdminLog(
                admin_id=admin_id,
                action_type="EDIT",
                entity_type="ANSWER",
                entity_id=answer_id,
                details=changes
            )
            session.add(admin_log)
            await session.commit()
        
        return True
    except Exception as e:
        await session.rollback()
        return False

async def delete_answer(session: AsyncSession, answer_id: int, admin_id: int = None) -> bool:
    """
    Удаляет ответ
    
    Args:
        session: Сессия базы данных
        answer_id: ID ответа
        admin_id: ID администратора
    
    Returns:
        True если удаление успешно, иначе False
    """
    try:
        # Получаем информацию об ответе перед удалением (для лога)
        result = await session.execute(select(Answer).where(Answer.answer_id == answer_id))
        answer = result.scalar_one_or_none()
        
        if not answer:
            return False
        
        answer_info = {
            "question_id": answer.question_id,
            "answer_text": answer.answer_text,
            "is_correct": answer.is_correct,
            "position": answer.position
        }
        
        # Удаляем ответ
        await session.execute(delete(Answer).where(Answer.answer_id == answer_id))
        await session.commit()
        
        # Логируем действия администратора
        if admin_id:
            admin_log = AdminLog(
                admin_id=admin_id,
                action_type="DELETE",
                entity_type="ANSWER",
                entity_id=answer_id,
                details=answer_info
            )
            session.add(admin_log)
            await session.commit()
        
        return True
    except Exception as e:
        await session.rollback()
        return False

# Функция для получения статистики по тесту

async def get_test_statistics(session: AsyncSession, test_id: int) -> Dict[str, Any]:
    """
    Получает статистику по тесту
    
    Args:
        session: Сессия базы данных
        test_id: ID теста
    
    Returns:
        Словарь со статистикой
    """
    # Получаем общее количество попыток прохождения теста
    result = await session.execute(
        select(func.count(TestAttempt.attempt_id)).where(TestAttempt.test_id == test_id)
    )
    total_attempts = result.scalar() or 0
    
    # Получаем количество уникальных пользователей
    result = await session.execute(
        select(func.count(func.distinct(TestAttempt.user_id))).where(TestAttempt.test_id == test_id)
    )
    unique_users = result.scalar() or 0
    
    # Получаем средний балл
    result = await session.execute(
        select(func.avg(TestAttempt.score)).where(TestAttempt.test_id == test_id)
    )
    avg_score = result.scalar() or 0
    if avg_score:
        avg_score = round(avg_score, 1)
    
    # Получаем процент успешных прохождений
    result = await session.execute(
        select(
            func.sum(case((TestAttempt.is_passed == True, 1), else_=0)) * 100 / func.count(TestAttempt.attempt_id)
        ).where(TestAttempt.test_id == test_id)
    )
    success_rate = result.scalar() or 0
    if success_rate:
        success_rate = round(success_rate, 1)
    
    # Формируем результат
    return {
        "total_attempts": total_attempts,
        "unique_users": unique_users,
        "avg_score": avg_score,
        "success_rate": success_rate
    }